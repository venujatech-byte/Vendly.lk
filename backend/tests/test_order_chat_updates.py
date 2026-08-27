"""Order status updates reaching the chat that placed the order.

A session can place several orders. It records the newest in `orderId` and
every one of them in `orderIds`, and the notifier has to look in both - the
list for correctness, the single field so sessions written before the list
existed still receive updates.
"""

from app.services import chat_event_service
from app.services.chat_event_service import send_order_status_chat_message


class FakeMessages:
    def __init__(self):
        self.written = []

    def document(self):
        return self

    def set(self, data):
        self.written.append(data)


class FakeSessionReference:
    def __init__(self):
        self.messages = FakeMessages()
        self.merged = []

    def collection(self, _name):
        return self.messages

    def set(self, data, merge=False):
        self.merged.append(data)


class FakeSnapshot:
    def __init__(self, identifier, session):
        self.id = identifier
        self._session = session
        self.reference = FakeSessionReference()

    def to_dict(self):
        return self._session


class FakeQuery:
    def __init__(self, results):
        self.results = results

    def stream(self):
        return list(self.results)


class FakeCollection:
    """Answers the two queries the notifier makes, by field and value."""

    def __init__(self, snapshots):
        self.snapshots = snapshots

    def where(self, filter=None):
        field = filter.field_path
        value = filter.value
        matches = []

        for snapshot in self.snapshots:
            session = snapshot.to_dict()

            if field == "orderIds" and value in (session.get("orderIds") or []):
                matches.append(snapshot)
            elif field == "orderId" and session.get("orderId") == value:
                matches.append(snapshot)

        return FakeQuery(matches)


class FakeDatabase:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def collection(self, _name):
        return FakeCollection(self.snapshots)


def make_session(order_id, order_ids):
    return FakeSnapshot(
        "session-1",
        {
            "businessId": "biz",
            "language": "en",
            "orderId": order_id,
            "orderIds": order_ids,
        },
    )


def notify(monkeypatch, snapshot, order_id):
    monkeypatch.setattr(
        chat_event_service, "translate_chat_message", lambda text, _language: text,
    )
    send_order_status_chat_message(
        FakeDatabase([snapshot]),
        "biz",
        order_id,
        {"orderNumber": f"VD-0000{order_id[-2:]}"},
        "confirmed",
    )


def test_an_earlier_order_still_updates_its_chat(monkeypatch):
    # The reported bug. Orders 15 and 16 came from one chat; the session's
    # `orderId` held 16, so confirming 15 matched no session and the customer
    # was told about 16 only.
    snapshot = make_session("order-16", ["order-15", "order-16"])

    notify(monkeypatch, snapshot, "order-15")

    assert len(snapshot.reference.messages.written) == 1
    assert "order-15" == snapshot.reference.messages.written[0]["metadata"]["orderId"]


def test_the_newest_order_is_not_notified_twice(monkeypatch):
    # It matches both queries. Without deduplication by document id the
    # customer would get the same update two times.
    snapshot = make_session("order-16", ["order-15", "order-16"])

    notify(monkeypatch, snapshot, "order-16")

    assert len(snapshot.reference.messages.written) == 1


def test_a_session_written_before_the_list_existed_still_updates(monkeypatch):
    # Live data predates the field. Dropping the single-field query would have
    # silently stopped updates for every order already placed.
    snapshot = make_session("order-16", None)

    notify(monkeypatch, snapshot, "order-16")

    assert len(snapshot.reference.messages.written) == 1


def test_another_business_is_never_notified(monkeypatch):
    snapshot = FakeSnapshot(
        "session-2",
        {"businessId": "other", "orderId": "order-16", "orderIds": ["order-16"]},
    )

    notify(monkeypatch, snapshot, "order-16")

    assert snapshot.reference.messages.written == []
