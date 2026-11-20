"""Chat history must page by Firebase keys without reading whole conversations."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from json import loads
from urllib.parse import parse_qs
from unittest.mock import Mock

import pytest
from firebase_admin import db
from flask import Flask

from app.core.errors import ApiError
from app.services import message_service, public_chat_service
from firestore_memory import MemoryFirestore

TOKEN = "synthetic-chat-token"
SESSION = "publicChatSessions/session-a"
STAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)


class RealtimeTransport:
    """Use real Admin SDK queries, replacing only HTTP with bounded synthetic responses."""

    def __init__(self):
        self.messages = {}
        self.requests = []
        self.downloads = []
        self.fail = False
        self.after_cursor_read = None

    def body(self, method, path, params=None):
        assert method == "get"
        self.requests.append((path, params))
        if self.fail:
            raise RuntimeError("Synthetic RTDB outage")
        if path == "/chatMessages/session-a.json":
            # A bare get() would download everything and must fail the test.
            query = parse_qs(params or "")
            assert loads(query["orderBy"][0]) == "$key"
            limit = int(query["limitToLast"][0])
            assert 1 <= limit <= 52
            keys = sorted(self.messages)
            if "endAt" in query:
                boundary = loads(query["endAt"][0])
                keys = [key for key in keys if key <= boundary]
            keys = keys[-limit:]
            self.downloads.append(len(keys))
            # REST results are unordered; the real Query.get() must sort this response.
            return {key: deepcopy(self.messages[key]) for key in reversed(keys)} or None
        prefix = "/chatMessages/session-a/"
        assert path.startswith(prefix) and path.endswith(".json")
        key = path[len(prefix):-5]
        result = deepcopy(self.messages.get(key))
        if self.after_cursor_read:
            action, self.after_cursor_read = self.after_cursor_read, None
            action(self)
        return result


def key(number):
    return f"-SYNTHETIC{number:010d}"


@pytest.fixture
def history(monkeypatch):
    # Neither Firestore, Auth, RTDB nor realtime permission sync can reach the cloud.
    store = MemoryFirestore()
    store.put(SESSION, {
        "businessId": "business-a", "status": "active", "updatedAt": STAMP,
        "tokenHash": public_chat_service.token_hash(TOKEN),
        "expiresAt": datetime.now(timezone.utc) + timedelta(hours=1),
    })
    transport = RealtimeTransport()
    reference = db.Reference(path="chatMessages/session-a", client=transport)
    getter = Mock(side_effect=lambda path: reference if path == "chatMessages/session-a" else pytest.fail(path))
    monkeypatch.setattr(message_service, "get_rtdb_reference", getter)
    monkeypatch.setattr(public_chat_service, "get_rtdb_reference", getter)
    with Flask(__name__).app_context():
        yield store, transport, getter


def populate(transport, count):
    # Equal timestamps deliberately exercise ID-based boundaries instead of timestamp-only paging.
    transport.messages = {key(index): {"role": "customer", "message": str(index), "createdAt": STAMP.isoformat()} for index in range(count)}


def read(history, audience, limit=10, before=None):
    store, _, _ = history
    if audience == "public":
        return public_chat_service.get_public_chat_messages(store.client, "session-a", TOKEN, limit=limit, before=before)
    return message_service.get_chat_messages(store.client, "business-a", "session-a", limit=limit, before=before)


@pytest.mark.parametrize("audience", ["public", "seller"])
def test_large_conversation_downloads_only_the_requested_window(history, audience):
    _, transport, _ = history
    populate(transport, 10000)
    result = read(history, audience, limit=20)
    assert [row["id"] for row in result["messages"]] == [key(index) for index in range(9980, 10000)]
    assert result["hasMore"] is True
    assert result["nextCursor"] == key(9980)
    assert transport.downloads == [21]


@pytest.mark.parametrize("audience", ["public", "seller"])
def test_all_pages_cover_equal_timestamp_messages_once_with_bounded_reads(history, audience):
    _, transport, _ = history
    populate(transport, 53)
    cursor, seen = None, []
    for _ in range(6):
        result = read(history, audience, before=cursor)
        seen = [row["id"] for row in result["messages"]] + seen
        cursor = result["nextCursor"]
        if not result["hasMore"]:
            break
    assert seen == [key(index) for index in range(53)]
    assert len(set(seen)) == 53
    assert cursor is None
    assert max(transport.downloads) <= 12


@pytest.mark.parametrize("audience", ["public", "seller"])
def test_oldest_cursor_returns_empty_rtdb_page_instead_of_firestore_history(history, audience):
    store, transport, _ = history
    populate(transport, 5)
    store.put(f"{SESSION}/messages/firestore-only", {"createdAt": STAMP, "message": "Separate fallback record"})
    result = read(history, audience, before=key(0))
    assert result["messages"] == []
    assert not result["hasMore"] and result["nextCursor"] is None


@pytest.mark.parametrize("audience", ["public", "seller"])
def test_missing_cursor_retains_latest_page_behavior(history, audience):
    _, transport, _ = history
    populate(transport, 15)
    result = read(history, audience, before="missing-key")
    assert result["messages"][0]["id"] == key(5)
    assert transport.downloads == [11]


@pytest.mark.parametrize("audience", ["public", "seller"])
def test_new_messages_do_not_move_an_older_page_boundary(history, audience):
    _, transport, _ = history
    populate(transport, 25)
    first = read(history, audience)
    transport.messages[key(100)] = {"createdAt": STAMP.isoformat(), "message": "Concurrent new message"}
    older = read(history, audience, before=first["nextCursor"])
    assert [row["id"] for row in older["messages"]] == [key(index) for index in range(5, 15)]


@pytest.mark.parametrize("audience", ["public", "seller"])
def test_cursor_deleted_during_paging_does_not_switch_to_a_different_history_source(history, audience):
    store, transport, _ = history
    populate(transport, 2)
    store.put(f"{SESSION}/messages/fallback", {"createdAt": STAMP, "message": "Separate history"})
    transport.after_cursor_read = lambda current: current.messages.pop(key(0))
    result = read(history, audience, before=key(0))
    assert result["messages"] == []
    assert result["hasMore"] is False


@pytest.mark.parametrize("audience", ["public", "seller"])
def test_nonmessage_children_do_not_hide_valid_older_messages(history, audience):
    _, transport, _ = history
    populate(transport, 7)
    transport.messages[key(5)] = "Malformed legacy child"
    transport.messages[key(6)] = True
    first = read(history, audience, limit=2)
    assert [row["id"] for row in first["messages"]] == [key(3), key(4)]
    assert first["hasMore"]
    result = read(history, audience, limit=2, before=first["nextCursor"])
    assert [row["id"] for row in result["messages"]] == [key(1), key(2)]
    assert max(transport.downloads) <= 4


def test_legacy_inbox_summary_is_not_hidden_by_a_malformed_latest_child(history):
    store, transport, _ = history
    populate(transport, 5)
    transport.messages[key(4)] = "Malformed legacy child"
    result = message_service.list_chat_sessions(store.client, "business-a")
    assert result["sessions"][0]["lastMessage"] == "3"
    assert max(transport.downloads) <= 3


@pytest.mark.parametrize("audience", ["public", "seller"])
def test_display_sort_does_not_replace_the_key_based_cursor(history, audience):
    _, transport, _ = history
    populate(transport, 5)
    transport.messages[key(3)]["createdAt"] = "2020-01-01"
    result = read(history, audience, limit=2)
    assert result["nextCursor"] == key(3)
    # The server cursor is a traversal boundary; it need not be the first displayed timestamp.
    transport.messages[key(4)]["createdAt"] = "2019-01-01"
    result = read(history, audience, limit=2)
    assert result["messages"][0]["id"] == key(4)
    assert result["nextCursor"] == key(3)


@pytest.mark.parametrize("audience", ["public", "seller"])
@pytest.mark.parametrize("outage", [False, True])
def test_empty_or_unavailable_rtdb_preserves_bounded_firestore_fallback(history, audience, outage):
    store, transport, _ = history
    transport.fail = outage
    for index in range(15):
        store.put(f"{SESSION}/messages/fallback-{index:02d}", {"createdAt": STAMP + timedelta(seconds=index), "message": str(index)})
    result = read(history, audience)
    assert [row["id"] for row in result["messages"]] == [f"fallback-{index:02d}" for index in range(5, 15)]
    assert result["hasMore"] and result["nextCursor"] == "fallback-05"
    older = read(history, audience, before=result["nextCursor"])
    assert [row["id"] for row in older["messages"]] == [f"fallback-{index:02d}" for index in range(5)]
    assert not older["hasMore"] and older["nextCursor"] is None


def test_unchanged_public_poll_does_not_query_rtdb(history):
    store, transport, getter = history
    result = public_chat_service.get_public_chat_messages(store.client, "session-a", TOKEN, since=STAMP.isoformat())
    assert result["changed"] is False
    getter.assert_not_called()
    assert transport.requests == []


@pytest.mark.parametrize("audience", ["public", "seller"])
def test_authorization_rejects_wrong_tokens_or_tenants_before_rtdb_reads(history, audience):
    store, transport, getter = history
    with pytest.raises(ApiError):
        if audience == "public":
            public_chat_service.get_public_chat_messages(store.client, "session-a", "synthetic-wrong")
        else:
            message_service.get_chat_messages(store.client, "business-b", "session-a")
    getter.assert_not_called()
    assert transport.requests == []
