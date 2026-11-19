"""Reopening an owned chat must issue a usable, time-limited token."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import ApiError
from app.services import public_chat_service, realtime_access_service
from firestore_memory import MemoryFirestore

CHAT = "publicChatSessions/session-a"
OLD_TOKEN = "synthetic-old-token"


@pytest.fixture
def store():
    # Keep SDK reads and writes offline; permission publication is mocked by conftest.
    store = MemoryFirestore()
    store.put(CHAT, {
        "customerUid": "customer-a", "businessId": "business-a", "status": "completed",
        "tokenHash": public_chat_service.token_hash(OLD_TOKEN),
        "expiresAt": datetime.now(timezone.utc) - timedelta(days=2),
        "state": "collecting-review-rating", "orderId": "order-a", "language": "si",
        "cart": [{"productId": "product-a", "quantity": 2}],
        "customerDraft": {"name": "Synthetic customer"},
        "recentTurns": [{"role": "customer", "text": "Synthetic message"}],
    })
    return store


@pytest.mark.parametrize("expired", [True, False])
def test_reopening_grants_24_hours_and_rotates_the_token_without_losing_chat_state(store, expired):
    if not expired:
        store.put(CHAT, {**store.documents[CHAT], "expiresAt": datetime.now(timezone.utc) + timedelta(hours=1)})
    before = deepcopy(store.documents[CHAT])
    started = datetime.now(timezone.utc)
    result = public_chat_service.resume_public_chat_session(
        store.client, "session-a", "customer-a", customer_email="customer@example.test",
    )
    finished = datetime.now(timezone.utc)
    saved = store.documents[CHAT]
    assert started + timedelta(hours=24) <= saved["expiresAt"] <= finished + timedelta(hours=24)
    assert saved["status"] == result["status"] == "active"
    assert result["sessionToken"] != OLD_TOKEN
    assert saved["tokenHash"] == public_chat_service.token_hash(result["sessionToken"])
    for field in ("customerUid", "businessId", "state", "orderId", "language", "cart", "customerDraft", "recentTurns"):
        assert saved[field] == before[field]
    public_chat_service.authorize_public_chat_session(store.client, "session-a", result["sessionToken"])
    with pytest.raises(ApiError) as error:
        public_chat_service.authorize_public_chat_session(store.client, "session-a", OLD_TOKEN)
    assert error.value.code == "invalid_chat_session"
    realtime_access_service.sync_chat_access.assert_called_once()
    assert realtime_access_service.sync_chat_access.call_args.args[0].to_dict()["expiresAt"] == saved["expiresAt"]
    assert store.commits == 1


@pytest.mark.parametrize("owner,caller,code,status", [
    ("customer-a", None, "unauthorized", 401),
    ("customer-a", "customer-b", "forbidden", 403),
    (None, "customer-a", "forbidden", 403),
])
def test_reopening_requires_the_signed_in_owner_before_any_change(store, owner, caller, code, status):
    store.put(CHAT, {**store.documents[CHAT], "customerUid": owner})
    before = deepcopy(store.documents)
    with pytest.raises(ApiError) as error:
        public_chat_service.resume_public_chat_session(store.client, "session-a", caller)
    assert error.value.code == code
    assert error.value.status_code == status
    assert store.documents == before
    store.client._firestore_api.commit.assert_not_called()
    realtime_access_service.sync_chat_access.assert_not_called()
