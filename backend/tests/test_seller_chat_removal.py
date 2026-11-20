"""Removing a seller inbox row must leave the storefront conversation intact."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from flask import Flask

from app.core.errors import ApiError
from app.services import message_service as inbox, public_chat_service as storefront
from firestore_memory import MemoryFirestore

CHAT = "publicChatSessions/chat-a"
TOKEN = "synthetic-chat-token"


@pytest.fixture
def chat(monkeypatch):
    # Use the real Firestore SDK with memory transport and no RTDB network access.
    store = MemoryFirestore()
    now = datetime.now(timezone.utc)
    store.put(CHAT, {
        "businessId": "store-a", "status": "active", "orderId": "order-a",
        "lastMessage": "Earlier message", "tokenHash": storefront.token_hash(TOKEN),
        "updatedAt": now, "expiresAt": now + timedelta(hours=1),
    })
    store.put(f"{CHAT}/messages/earlier", {"createdAt": now, "message": "Earlier message"})
    realtime = Mock(return_value=None)
    monkeypatch.setattr(inbox, "get_rtdb_reference", realtime)
    monkeypatch.setattr(storefront, "get_rtdb_reference", realtime)
    return store, realtime


def test_seller_removal_preserves_customer_access_and_history(chat):
    store, realtime = chat
    expected = store.documents[CHAT].copy()
    for _ in range(2):
        assert inbox.delete_chat_session(store.client, "store-a", "chat-a")["deleted"]
    assert store.documents[CHAT] == {**expected, "hiddenFromSellerInbox": True}
    assert not inbox.list_chat_sessions(store.client, "store-a")["sessions"]
    with pytest.raises(ApiError) as failure:
        inbox.get_chat_messages(store.client, "store-a", "chat-a")
    assert failure.value.status_code == 404
    realtime.assert_not_called()
    result = storefront.get_public_chat_messages(store.client, "chat-a", TOKEN)
    assert [row["message"] for row in result["messages"]] == ["Earlier message"]


def test_seller_removal_cannot_hide_another_stores_chat(chat):
    store, _ = chat
    with pytest.raises(ApiError) as failure:
        inbox.delete_chat_session(store.client, "store-b", "chat-a")
    assert failure.value.status_code == 404
    assert "hiddenFromSellerInbox" not in store.documents[CHAT]


def test_hidden_rows_preserve_access_to_older_inbox_pages(chat):
    store, _ = chat
    store.put("publicChatSessions/older", {**store.documents[CHAT], "updatedAt": store.documents[CHAT]["updatedAt"] - timedelta(days=1)})
    inbox.delete_chat_session(store.client, "store-a", "chat-a")
    first = inbox.list_chat_sessions(store.client, "store-a", limit=1)
    assert first == {"sessions": [], "hasMore": True, "nextCursor": "chat-a"}
    older = inbox.list_chat_sessions(store.client, "store-a", limit=1, before=first["nextCursor"])
    assert [row["id"] for row in older["sessions"]] == ["older"]


def test_customer_message_reopens_inbox_before_activity_is_signaled(chat):
    store, realtime = chat
    inbox.delete_chat_session(store.client, "store-a", "chat-a")
    reference = store.client.collection("publicChatSessions").document("chat-a")
    session = store.documents[CHAT].copy()
    activity = Mock()
    visibility_at_signal = []
    activity.set.side_effect = lambda _event: visibility_at_signal.append(store.documents[CHAT]["hiddenFromSellerInbox"])
    realtime.side_effect = lambda path: activity if path == "businessChatActivity/store-a" else None
    # An automated notice keeps the chat hidden. An actual customer message reopens it.
    storefront.save_chat_message(reference, "seller", "Order updated", {"automated": True})
    assert not inbox.list_chat_sessions(store.client, "store-a")["sessions"]
    storefront.save_chat_message(reference, "customer", "New message", session=session)
    activity.set.assert_called_once()
    assert visibility_at_signal == [False]
    rows = inbox.list_chat_sessions(store.client, "store-a")["sessions"]
    assert [(row["id"], row["lastMessage"]) for row in rows] == [("chat-a", "New message")]
