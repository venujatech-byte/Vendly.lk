"""Bank transfers: promised, received, and what is left to collect.

The rule underneath all of these: a promise is not money. An order marked paid
before the transfer lands is a parcel shipped for free if it never arrives.
"""

from unittest.mock import Mock

import pytest

from firestore_memory import MemoryFirestore

from app.core.errors import ApiError
from app.services import order_service, public_chat_service
from app.services.order_service import record_order_payment, validate_order_request


def base_request(**overrides):
    return {
        "customerId": "cust-1",
        "courierId": "courier-1",
        "items": [{"variantId": "v-1", "quantity": 1}],
        "deliveryAddress": {
            "line1": "45 Park Road",
            "city": "Matara",
            "district": "Matara",
        },
        **overrides,
    }


def make_database(order):
    # Keep existing payment scenarios on real SDK transactions with in-memory RPCs.
    store = MemoryFirestore()
    store.put("businesses/biz/orders/order-1", order)
    return store.client, store


def test_a_promised_transfer_is_not_recorded_as_money():
    # The customer said they will transfer. Nothing has arrived.
    request = validate_order_request(
        base_request(paymentMethod="paid", paymentPending=True),
    )

    assert request["paymentPending"] is True


def test_a_seller_recorded_payment_is_not_pending():
    request = validate_order_request(base_request(paymentMethod="paid"))

    assert request["paymentPending"] is False


def test_recording_the_full_amount_leaves_nothing_to_collect(monkeypatch):
    order = {
        "totalAmountMinor": 180000,
        "paymentStatus": "pending-payment",
        "fulfilmentStatus": "needs-confirmation",
    }
    database, store = make_database(order)
    monkeypatch.setattr(
        order_service, "send_payment_recorded_chat_message", lambda *a: None,
    )
    monkeypatch.setattr(order_service, "_publish_order_status_change", lambda *a: None)

    result = record_order_payment(
        database, "biz", "order-1", "seller-1",
        {"paidAmountMinor": 180000, "receiptUrl": "https://cdn/slip.jpg"},
    )

    assert result["paymentStatus"] == "paid"
    assert result["balanceAmountMinor"] == 0
    assert result["paymentPending"] is False
    assert result["fulfilmentStatus"] == "confirmed"
    assert result["paymentReceipts"][0]["url"] == "https://cdn/slip.jpg"


def test_a_part_payment_leaves_the_rest_as_cash_on_delivery(monkeypatch):
    order = {
        "totalAmountMinor": 180000,
        "paymentStatus": "pending-payment",
        "fulfilmentStatus": "needs-confirmation",
    }
    database, store = make_database(order)
    monkeypatch.setattr(
        order_service, "send_payment_recorded_chat_message", lambda *a: None,
    )
    monkeypatch.setattr(order_service, "_publish_order_status_change", lambda *a: None)

    result = record_order_payment(
        database, "biz", "order-1", "seller-1", {"paidAmountMinor": 45000},
    )

    # The courier collects the difference. Half and full are the same
    # operation with different numbers.
    assert result["paymentStatus"] == "partially-paid"
    assert result["fulfilmentStatus"] == "confirmed"
    assert result["balanceAmountMinor"] == 135000


def test_more_than_the_total_is_refused(monkeypatch):
    order = {"totalAmountMinor": 180000}
    database, _reference = make_database(order)

    # A slipped digit would otherwise show the courier a negative amount to
    # collect.
    with pytest.raises(ApiError, match="more than the order total"):
        record_order_payment(
            database, "biz", "order-1", "seller-1", {"paidAmountMinor": 1800000},
        )


def test_zero_is_refused(monkeypatch):
    order = {"totalAmountMinor": 180000}
    database, _reference = make_database(order)

    with pytest.raises(ApiError, match="amount you received"):
        record_order_payment(
            database, "biz", "order-1", "seller-1", {"paidAmountMinor": 0},
        )


def test_the_receipt_is_kept_for_later_viewing(monkeypatch):
    order = {"totalAmountMinor": 180000, "fulfilmentStatus": "needs-confirmation"}
    database, store = make_database(order)
    monkeypatch.setattr(
        order_service, "send_payment_recorded_chat_message", lambda *a: None,
    )

    record_order_payment(
        database, "biz", "order-1", "seller-1",
        {"paidAmountMinor": 90000, "receiptUrl": "https://cdn/first.jpg"},
    )
    record_order_payment(
        database, "biz", "order-1", "seller-1",
        {"paidAmountMinor": 180000, "receiptUrl": "https://cdn/second.jpg"},
    )

    # Both slips are kept. A customer who pays in two transfers has two
    # receipts, and the seller may need either of them later.
    assert len(store.documents["businesses/biz/orders/order-1"]["paymentReceipts"]) == 2


def test_an_order_awaiting_a_transfer_cannot_be_confirmed():
    database, store = make_database({
        "fulfilmentStatus": "needs-confirmation", "paymentStatus": "pending-payment",
    })
    with pytest.raises(ApiError, match="Record the payment before confirming it") as failure:
        order_service.update_order_status(database, "biz", "order-1", "seller-1", {"status": "confirmed"})

    assert failure.value.code == "payment_not_received"
    assert store.commits == 0


def test_cancelling_stays_available_while_payment_is_pending():
    from app.services.order_service import STATUS_TRANSITIONS

    # An order that never gets paid has to be closable, or it sits in the
    # table forever.
    assert "cancelled" in STATUS_TRANSITIONS["needs-confirmation"]


def test_the_customer_is_told_their_payment_arrived(monkeypatch):
    sent = []
    order = {
        "totalAmountMinor": 180000,
        "orderNumber": "VD-000018",
        "fulfilmentStatus": "needs-confirmation",
    }
    database, store = make_database(order)
    monkeypatch.setattr(
        order_service,
        "send_payment_recorded_chat_message",
        lambda _db, _biz, _oid, _order, paid, balance: sent.append((paid, balance)),
    )

    record_order_payment(
        database, "biz", "order-1", "seller-1", {"paidAmountMinor": 90000},
    )

    # The customer sent a receipt and then heard nothing. Confirming closes the
    # loop they started, and the balance tells them what to have ready for the
    # courier.
    assert sent == [(90000, 90000)]


def test_changing_to_cash_on_delivery_frees_the_order(monkeypatch):
    order = {
        "totalAmountMinor": 180000,
        "orderNumber": "VD-000019",
        "paymentMethod": "paid",
        "paymentStatus": "pending-payment",
        "paymentPending": True,
        "paidAmountMinor": 0,
        "fulfilmentStatus": "needs-confirmation",
    }
    database, store = make_database(order)
    monkeypatch.setattr(
        order_service, "send_payment_recorded_chat_message", lambda *a: None,
    )

    result = record_order_payment(
        database, "biz", "order-1", "seller-1",
        {"convertToCashOnDelivery": True},
    )

    # The transfer never came. Without this the order is stuck: it cannot be
    # confirmed while payment is pending, and cancelling one the customer still
    # wants is the wrong remedy.
    assert result["paymentMethod"] == "cod"
    assert result["paymentStatus"] == "unpaid"
    assert result["paymentPending"] is False
    assert result["balanceAmountMinor"] == 180000


def test_money_already_banked_cannot_be_moved_to_cash_on_delivery(monkeypatch):
    order = {
        "totalAmountMinor": 180000,
        "paidAmountMinor": 90000,
        "fulfilmentStatus": "needs-confirmation",
    }
    database, _reference = make_database(order)

    # Half is already in the seller's account. Telling the courier to collect
    # the whole total would charge the customer twice for that half.
    with pytest.raises(ApiError, match="already paid"):
        record_order_payment(
            database, "biz", "order-1", "seller-1",
            {"convertToCashOnDelivery": True},
        )


def test_the_customer_is_told_about_the_change_not_a_zero_payment(monkeypatch):
    sent = []
    order = {
        "totalAmountMinor": 180000,
        "orderNumber": "VD-000019",
        "fulfilmentStatus": "needs-confirmation",
    }
    database, store = make_database(order)
    monkeypatch.setattr(
        order_service,
        "send_payment_recorded_chat_message",
        lambda _db, _biz, _oid, _order, paid, balance: sent.append((paid, balance)),
    )

    record_order_payment(
        database, "biz", "order-1", "seller-1", {"convertToCashOnDelivery": True},
    )

    # Zero paid, everything outstanding - the message builder reads this as a
    # change of method rather than announcing a payment of nothing.
    assert sent == [(0, 180000)]


def test_a_seller_typed_order_uses_the_same_pending_state():
    # The seller's "to be paid" and the storefront's bank-transfer choice are
    # the same state, so one row colour, one confirm guard and one way to
    # record the money serve both.
    request = validate_order_request(
        base_request(paymentMethod="paid", paymentPending=True),
    )

    assert request["paymentPending"] is True


def test_a_seller_typed_part_payment_is_a_deposit():
    # "Paid" with less than the total is a deposit order: the courier collects
    # the difference, exactly as it does for a half bank transfer.
    request = validate_order_request(
        base_request(paymentMethod="deposit", depositAmount=450),
    )

    assert request["paymentMethod"] == "deposit"
    assert request["depositMinor"] == 45000


@pytest.mark.parametrize("payment_method", ["paid", "deposit", " paid ", " deposit ", "cod", None])
@pytest.mark.parametrize("pending_fields", [{}, {"paymentPending": False}, {"paymentPending": True}])
def test_guest_payment_choices_cannot_claim_verified_money(monkeypatch, payment_method, pending_fields):
    # Fake every external boundary so checkout cannot access live customer or bank data.
    database = Mock()
    database.collection.return_value.document.return_value.get.return_value.exists = False
    snapshot = Mock()
    monkeypatch.setattr(
        public_chat_service, "authorize_public_chat_session",
        lambda *a: (snapshot, {"businessId": "biz"}),
    )
    monkeypatch.setattr(
        public_chat_service, "list_customers", lambda *a, **k: [{"id": "cust-1"}],
    )
    create_order = Mock(return_value={"id": "order-1"})
    monkeypatch.setattr(public_chat_service, "create_order", create_order)

    # Exercise the shared guest checkout path with forged payment amounts and flags.
    public_chat_service.create_public_chat_order(
        database, "session-1", "test-token",
        {
            "customer": {
                "name": "Guest", "phoneNumber": "0712345678",
                "address": {"line1": "1 Test Road", "city": "Matara", "district": "Matara"},
            },
            "courierId": "courier-1",
            "items": [{"variantId": "v-1", "quantity": 1}],
            "paymentMethod": payment_method,
            "depositAmount": 1800,
            "paidAmountMinor": 180000,
            **pending_fields,
        },
    )

    # Verify the actual order validator receives transfer intent, never received money.
    request = validate_order_request(create_order.call_args.args[3])
    method = payment_method.strip() if payment_method else "cod"
    assert request["paymentMethod"] == method
    assert request["paymentPending"] is (
        method in {"paid", "deposit"} or pending_fields.get("paymentPending") is True
    )
    assert request["depositMinor"] == 0
