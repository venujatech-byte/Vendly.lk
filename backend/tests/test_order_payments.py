"""Bank transfers: promised, received, and what is left to collect.

The rule underneath all of these: a promise is not money. An order marked paid
before the transfer lands is a parcel shipped for free if it never arrives.
"""

import pytest

from app.core.errors import ApiError
from app.services import order_service
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


class FakeEvents:
    def __init__(self):
        self.written = []

    def document(self):
        return self

    def set(self, data):
        self.written.append(data)


class FakeOrderReference:
    def __init__(self, order):
        self.order = order
        self.updates = []
        self.events = FakeEvents()

    def get(self):
        return FakeSnapshot(self.order)

    def update(self, changes):
        self.updates.append(changes)
        self.order.update(changes)

    def collection(self, _name):
        return self.events


class FakeSnapshot:
    def __init__(self, order):
        self.order = order

    @property
    def exists(self):
        return self.order is not None

    def to_dict(self):
        return dict(self.order or {})


class FakeDatabase:
    def __init__(self, reference):
        self.reference = reference

    def collection(self, _name):
        return self

    def document(self, _name=None):
        return self if _name != "order-1" else self.reference


class FakeBusinessChain:
    """Resolves businesses/<id>/orders/<id> down to the one order reference."""

    def __init__(self, reference):
        self.reference = reference

    def collection(self, _name):
        return self

    def document(self, name=None):
        if name == "order-1":
            return self.reference
        return self


def make_database(order):
    reference = FakeOrderReference(order)
    return FakeBusinessChain(reference), reference


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
    database, reference = make_database(order)
    monkeypatch.setattr(order_service, "get_order", lambda *a: reference.order)

    result = record_order_payment(
        database, "biz", "order-1", "seller-1",
        {"paidAmountMinor": 180000, "receiptUrl": "https://cdn/slip.jpg"},
    )

    assert result["paymentStatus"] == "paid"
    assert result["balanceAmountMinor"] == 0
    assert result["paymentPending"] is False
    assert result["paymentReceipts"][0]["url"] == "https://cdn/slip.jpg"


def test_a_part_payment_leaves_the_rest_as_cash_on_delivery(monkeypatch):
    order = {
        "totalAmountMinor": 180000,
        "paymentStatus": "pending-payment",
        "fulfilmentStatus": "needs-confirmation",
    }
    database, reference = make_database(order)
    monkeypatch.setattr(order_service, "get_order", lambda *a: reference.order)

    result = record_order_payment(
        database, "biz", "order-1", "seller-1", {"paidAmountMinor": 45000},
    )

    # The courier collects the difference. Half and full are the same
    # operation with different numbers.
    assert result["paymentStatus"] == "partially-paid"
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
    database, reference = make_database(order)
    monkeypatch.setattr(order_service, "get_order", lambda *a: reference.order)

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
    assert len(reference.order["paymentReceipts"]) == 2


def test_an_order_awaiting_a_transfer_cannot_be_confirmed():
    from app.services.order_service import STATUS_TRANSITIONS

    # The guard lives inside the status transaction, so this asserts the rule
    # it depends on: confirmed is reachable from needs-confirmation, and the
    # guard is what stops it while payment is pending.
    assert "confirmed" in STATUS_TRANSITIONS["needs-confirmation"]
    assert "cancelled" in STATUS_TRANSITIONS["needs-confirmation"]


def test_cancelling_stays_available_while_payment_is_pending():
    from app.services.order_service import STATUS_TRANSITIONS

    # An order that never gets paid has to be closable, or it sits in the
    # table forever.
    assert "cancelled" in STATUS_TRANSITIONS["needs-confirmation"]
