"""Order status updates reaching the chat that placed the order.

A session can place several orders. It records the newest in `orderId` and
every one of them in `orderIds`, and the notifier has to look in both - the
list for correctness, the single field so sessions written before the list
existed still receive updates.
"""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from flask import Flask

from app.services import chat_event_service, message_service, public_chat_service
from app.services.chat_event_service import send_order_status_chat_message, send_payment_recorded_chat_message


@pytest.fixture(autouse=True)
def offline_chat(monkeypatch):
    # Every notification test must opt into an in-memory RTDB instead of reaching Firebase.
    reference = Mock(return_value=None)
    monkeypatch.setattr(public_chat_service, "get_rtdb_reference", reference)
    with Flask(__name__).app_context():
        yield reference


class FakeMessages:
    def __init__(self):
        self.written = []

    def document(self):
        return self

    def set(self, data):
        self.written.append(data)


class FakeSessionReference:
    def __init__(self, identifier):
        self.id = identifier
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
        self.reference = FakeSessionReference(identifier)

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


@pytest.fixture
def realtime_chat(offline_chat, monkeypatch):
    # Keep an existing customer message so history must read RTDB rather than Firestore.
    rows = {"old": {"role": "customer", "message": "Hello", "createdAt": "2025-01-01T00:00:00+00:00"}}
    messages, activity = Mock(), Mock()
    messages.push.side_effect = lambda data: rows.update({f"message-{len(rows)}": data})
    messages.get.side_effect = lambda: rows
    messages.order_by_key.return_value.limit_to_last.return_value.get.side_effect = lambda: rows
    offline_chat.side_effect = lambda path: {
        "chatMessages/session-1": messages, "businessChatActivity/biz": activity,
    }[path]
    monkeypatch.setattr(message_service, "get_rtdb_reference", offline_chat)
    monkeypatch.setattr(chat_event_service, "translate_chat_message", lambda text, language: f"{language}: {text}")
    return rows, messages, activity


@pytest.mark.parametrize("status,items,state", [
    ("confirmed", [], None),
    ("delivered", [{"productId": "product-a"}], "collecting-review-rating"),
    ("delivered", [{"productId": "product-a"}, {"productId": "product-b"}], "collecting-review-product"),
])
def test_status_messages_reach_existing_realtime_history_without_changing_ai_memory(realtime_chat, status, items, state):
    snapshot = make_session("order-16", ["order-15", "order-16"])
    snapshot._session.update({"language": "si", "recentTurns": [{"role": "customer", "text": "Keep this"}]})
    original = deepcopy(snapshot._session)
    send_order_status_chat_message(FakeDatabase([snapshot]), "biz", "order-16", {
        "orderNumber": "VD-000016", "items": items,
    }, status, "Synthetic note")
    rows, messages, activity = realtime_chat
    assert len(rows) == 2
    messages.push.assert_called_once()
    message = rows["message-1"]
    assert message["role"] == "seller"
    assert message["message"].startswith("si: Order VD-000016")
    assert "Synthetic note" in message["message"]
    assert message["metadata"] == {"automated": True, "action": "order-status-update", "orderId": "order-16", "status": status}
    assert snapshot.reference.messages.written == []
    assert snapshot._session == original
    assert len(snapshot.reference.merged) == 1
    saved = snapshot.reference.merged[0]
    assert "recentTurns" not in saved and "unreadBySeller" not in saved
    assert saved["lastMessage"] == message["message"]
    assert saved["lastMessageRole"] == "seller"
    if state:
        assert saved["state"] == state
        assert saved["reviewDraft"] == {"orderId": "order-16", "productId": "product-a", "media": []}
    else:
        assert "state" not in saved and "reviewDraft" not in saved
    activity.set.assert_called_once()
    assert activity.set.call_args.args[0]["sessionId"] == snapshot.id
    history, has_more, cursor = message_service._message_rows(snapshot.reference, limit=20)
    assert history[-1]["message"] == message["message"]
    assert not has_more and cursor is None


@pytest.mark.parametrize("paid,balance,expected", [
    (5000, 2000, "Payment received for order VD-000016: LKR 50.00."),
    (0, 7000, "has been changed to cash on delivery"),
])
def test_payment_messages_reach_rtdb_with_existing_wording(realtime_chat, paid, balance, expected):
    snapshot = make_session("order-16", ["order-16"])
    send_payment_recorded_chat_message(FakeDatabase([snapshot]), "biz", "order-16", {
        "orderNumber": "VD-000016",
    }, paid, balance)
    rows, messages, activity = realtime_chat
    messages.push.assert_called_once()
    assert expected in rows["message-1"]["message"]
    assert rows["message-1"]["metadata"] == {"automated": True, "action": "payment-recorded", "orderId": "order-16"}
    assert snapshot.reference.messages.written == []


def test_rtdb_message_failure_preserves_the_firestore_fallback(monkeypatch, realtime_chat):
    rows, messages, activity = realtime_chat
    messages.push.side_effect = RuntimeError("Synthetic RTDB failure")
    snapshot = make_session("order-16", ["order-16"])
    notify(monkeypatch, snapshot, "order-16")
    messages.push.assert_called_once()
    assert len(rows) == 1
    assert len(snapshot.reference.messages.written) == 1
    assert snapshot.reference.messages.written[0]["metadata"]["automated"] is True
    assert snapshot.reference.merged[0]["lastMessageRole"] == "seller"


def test_activity_failure_does_not_duplicate_or_lose_a_delivered_message(monkeypatch, realtime_chat):
    rows, messages, activity = realtime_chat
    activity.set.side_effect = RuntimeError("Synthetic activity failure")
    snapshot = make_session("order-16", ["order-16"])
    notify(monkeypatch, snapshot, "order-16")
    messages.push.assert_called_once()
    assert len(rows) == 2
    assert snapshot.reference.messages.written == []
    assert len(snapshot.reference.merged) == 1


def test_other_business_cannot_receive_realtime_messages(monkeypatch, offline_chat, realtime_chat):
    snapshot = make_session("order-16", ["order-16"])
    snapshot._session["businessId"] = "other"
    notify(monkeypatch, snapshot, "order-16")
    offline_chat.assert_not_called()
    assert snapshot.reference.merged == []


def test_failed_firestore_fallback_does_not_save_a_successful_preview(monkeypatch):
    snapshot = make_session("order-16", ["order-16"])
    snapshot.reference.messages.set = Mock(side_effect=RuntimeError("Synthetic Firestore failure"))
    with pytest.raises(RuntimeError, match="Synthetic Firestore failure"):
        notify(monkeypatch, snapshot, "order-16")
    assert snapshot.reference.merged == []
