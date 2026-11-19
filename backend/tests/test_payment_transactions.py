"""Interleave real payment transactions through in-memory Firestore RPCs."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import Aborted, PermissionDenied

from firestore_memory import MemoryFirestore
from app.core.errors import ApiError
from app.services import order_service


ORDER = "businesses/business-a/orders/order-a"


@pytest.fixture
def store(monkeypatch):
    # Only the optional notification channel is mocked above the real SDK transport.
    store = MemoryFirestore()
    store.put(ORDER, {
        "orderNumber": "VD-TEST", "totalAmountMinor": 2000, "paidAmountMinor": 0,
        "balanceAmountMinor": 2000, "paymentMethod": "paid", "paymentStatus": "pending-payment",
        "paymentPending": True, "fulfilmentStatus": "needs-confirmation", "paymentReceipts": [],
    })
    store.notify = Mock()
    monkeypatch.setattr(order_service, "send_payment_recorded_chat_message", store.notify)
    return store


def record(store, amount=1200, receipt="https://example.test/receipt-a"):
    return order_service.record_order_payment(
        store.client, "business-a", "order-a", "seller-a",
        {"paidAmountMinor": amount, "receiptUrl": receipt},
    )


def change_payment(store, cod):
    if cod:
        return order_service.record_order_payment(
            store.client, "business-a", "order-a", "seller-a", {"convertToCashOnDelivery": True},
        )
    return record(store)


def events(store):
    return {path: entry for path, entry in store.documents.items() if path.startswith(f"{ORDER}/events/")}


def test_competing_payments_keep_both_receipts_and_cumulative_total(store):
    # The second service call commits while the first is awaiting commit, forcing its retry.
    store.before_commit = lambda current: record(current, 500, "https://example.test/receipt-b")
    result = record(store)
    assert store.attempts == 3
    assert store.commits == 2
    assert result["paidAmountMinor"] == 1200
    assert result["balanceAmountMinor"] == 800
    assert {receipt["url"] for receipt in result["paymentReceipts"]} == {
        "https://example.test/receipt-a", "https://example.test/receipt-b",
    }
    assert len(events(store)) == 2
    assert store.notify.call_count == 2


def test_cod_conversion_cannot_erase_a_competing_payment(store):
    store.before_commit = lambda current: record(current, 500)
    with pytest.raises(ApiError) as error:
        change_payment(store, cod=True)
    assert error.value.code == "payment_already_recorded"
    assert store.attempts == 3
    assert store.commits == 1
    assert store.documents[ORDER]["paidAmountMinor"] == 500
    assert store.documents[ORDER]["balanceAmountMinor"] == 1500
    assert store.documents[ORDER]["paymentMethod"] == "paid"
    assert len(events(store)) == 1
    store.notify.assert_called_once()


def test_receipt_attachment_keeps_a_competing_payment_and_its_receipt(store):
    store.before_commit = lambda current: record(current, 1200, "https://example.test/receipt-b")
    result = order_service.attach_order_payment_receipt(
        store.client, "business-a", "order-a", "seller-a", "https://example.test/receipt-a", 500,
    )
    assert store.attempts == 3
    assert store.commits == 2
    assert result["paidAmountMinor"] == 1200
    assert len(result["paymentReceipts"]) == 2
    assert len(events(store)) == 1


@pytest.mark.parametrize("cod", [False, True])
def test_rejected_payment_and_audit_commit_leaves_no_partial_writes(store, cod):
    before = deepcopy(store.documents)

    def reject_commit(request, **kwargs):
        names = {write.update.name.split("/documents/", 1)[1] for write in request["writes"]}
        # Payment state, audit event and cache freshness must succeed or fail together.
        assert len(names) == 3
        assert "businesses/business-a/_cacheVersions/orders" in names
        assert ORDER in names
        assert any(name.startswith(f"{ORDER}/events/") for name in names)
        raise PermissionDenied("Simulated audit write rejection")

    store.client._firestore_api_internal.commit.side_effect = reject_commit
    with pytest.raises(PermissionDenied):
        change_payment(store, cod)
    assert store.documents == before
    store.notify.assert_not_called()


@pytest.mark.parametrize("cod", [False, True])
def test_notification_failure_does_not_fail_committed_payment_or_leak_errors(store, cod, caplog):
    observed = []

    def fail_notification(*args):
        # Neither notifications nor their error handler may run inside a retried transaction.
        observed.append((store.commits, len(events(store))))
        raise RuntimeError("synthetic-provider-key-and-customer-data")

    store.notify.side_effect = fail_notification
    result = change_payment(store, cod)
    assert result["paidAmountMinor"] == (0 if cod else 1200)
    assert result["balanceAmountMinor"] == (2000 if cod else 800)
    assert result["paymentPending"] is False
    assert len(events(store)) == 1
    assert observed == [(1, 1)]
    assert "customer chat notification could not be delivered" in caplog.text
    assert "synthetic-provider-key-and-customer-data" not in caplog.text
    store.notify.assert_called_once()


def test_retry_revalidates_a_changed_order_total(store):
    store.before_commit = lambda current: current.put(ORDER, {**current.documents[ORDER], "totalAmountMinor": 1000})
    with pytest.raises(ApiError) as error:
        record(store, amount=1200)
    assert error.value.code == "invalid_payment"
    assert store.attempts == 2
    assert store.commits == 0
    assert store.documents[ORDER]["paidAmountMinor"] == 0
    assert not events(store)
    store.notify.assert_not_called()


@pytest.mark.parametrize("cod", [False, True])
def test_missing_order_saves_no_event_and_sends_no_notification(store, cod):
    del store.documents[ORDER]
    with pytest.raises(ApiError) as error:
        change_payment(store, cod)
    assert error.value.code == "order_not_found"
    assert store.commits == 0
    assert not events(store)
    store.notify.assert_not_called()


def test_exhausted_conflicts_leave_payment_unchanged_and_send_no_notification(store):
    before = deepcopy(store.documents)
    store.client._firestore_api_internal.commit.side_effect = Aborted("Simulated repeated contention")
    with pytest.raises(ValueError, match="Failed to commit transaction"):
        record(store)
    assert store.attempts == 5
    assert store.documents == before
    assert not events(store)
    store.notify.assert_not_called()
