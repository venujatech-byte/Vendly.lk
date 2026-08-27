"""The seller is told when a customer cancels.

Stock has just been released, anything already picked has to go back on the
shelf, and a courier may have been booked. Finding out by noticing a status
change in a table is not being told.
"""

import pytest

from app.services import order_service


class FakeDocument:
    def __init__(self, store, name):
        self.store = store
        self.name = name
        self.id = name or "generated"

    def get(self, transaction=None):
        return FakeSnapshot(self.store.get(self.name), self)

    def collection(self, name):
        return FakeCollection(self.store, name)


class FakeSnapshot:
    def __init__(self, data, reference):
        self._data = data
        self.reference = reference
        self.id = reference.id

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data or {})


class FakeCollection:
    def __init__(self, store, name):
        self.store = store
        self.name = name

    def document(self, name=None):
        return FakeDocument(self.store, name or f"{self.name}-generated")


class FakeDatabase:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        return FakeCollection(self.store, name)

    def transaction(self):
        return object()


class RecordingTransaction:
    def __init__(self):
        self.writes = []

    def update(self, reference, data):
        self.writes.append(("update", reference.id, data))

    def set(self, reference, data):
        self.writes.append(("set", reference.id, data))


def run_cancellation(monkeypatch, uid):
    """Drive update_order_status far enough to see what it writes."""
    order = {
        "id": "order-1",
        "orderNumber": "VD-000041",
        "fulfilmentStatus": "needs-confirmation",
        "customerId": "cust-1",
        "courierId": "courier-1",
        "customerSnapshot": {"name": "Nimal"},
        "items": [],
        "totalAmountMinor": 100000,
    }
    store = {
        "order-1": order,
        "cust-1": {"name": "Nimal"},
        "courier-1": {"name": "Koombiyo"},
    }
    recorded = RecordingTransaction()

    # The real decorator runs the function against a live transaction; here the
    # body is what is under test.
    def fake_transactional(function):
        def run(_transaction):
            return function(recorded)

        return run

    monkeypatch.setattr(
        order_service.google_firestore, "transactional", fake_transactional,
    )
    monkeypatch.setattr(order_service, "get_order", lambda *a: order)
    monkeypatch.setattr(
        order_service, "send_order_status_chat_message", lambda *a, **k: None,
    )

    order_service.update_order_status(
        FakeDatabase(store),
        "biz",
        "order-1",
        uid,
        {"status": "cancelled"},
    )
    return recorded.writes


def notifications(writes):
    return [
        data
        for action, _reference, data in writes
        if action == "set" and data.get("type") == "order-cancelled"
    ]


def test_a_customer_cancellation_notifies_the_seller(monkeypatch):
    writes = run_cancellation(monkeypatch, "public-chat:session-1")
    notices = notifications(writes)

    assert len(notices) == 1
    assert "VD-000041" in notices[0]["title"]
    assert "Nimal" in notices[0]["message"]
    # The seller has to know the stock is back before they go looking for it.
    assert "released" in notices[0]["message"]
    assert notices[0]["isRead"] is False


def test_a_seller_cancelling_is_not_notified_of_their_own_action(monkeypatch):
    writes = run_cancellation(monkeypatch, "seller-uid-1")

    assert notifications(writes) == []
