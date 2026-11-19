"""Registered customers reuse a store conversation without crossing ownership boundaries."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from flask import Flask, g
from google.api_core.exceptions import PermissionDenied

from app import create_app
from app.core.errors import ApiError
from app.services import public_chat_service as chat
from firestore_memory import MemoryFirestore

BUSINESS = {"id": "business-a", "shortCode": "store-a", "name": "Synthetic store"}
PRODUCT = {"id": "product-a", "shortCode": "product-link-a", "name": "Synthetic product", "variants": [
    {"id": "variant-a", "sellingPriceMinor": 1000, "availableStock": 10},
]}
POINTER = "businesses/business-a/customerChats/customer-a"


@pytest.fixture
def store(monkeypatch):
    # All database transports, catalogue lookups and realtime feeds remain offline.
    store = MemoryFirestore()
    monkeypatch.setattr(chat, "get_public_store", Mock(return_value={"business": BUSINESS, "products": [PRODUCT]}))
    monkeypatch.setattr(chat, "get_public_product", Mock(return_value={"business": BUSINESS, "product": PRODUCT}))
    monkeypatch.setattr(chat, "get_rtdb_reference", Mock(return_value=None))
    monkeypatch.setattr(chat, "translate_chat_message", lambda text, language: text)
    return store


def start(store, payload=None, uid="customer-a", shared=True):
    return chat.create_public_chat_session(store.client, payload or {"storeCode": "store-a"}, uid, share_customer_chat=shared)


def legacy(store, identifier, *, uid="customer-a", business_id="business-a", age=1):
    store.put(f"publicChatSessions/{identifier}", {
        "customerUid": uid, "businessId": business_id, "tokenHash": chat.token_hash("synthetic-old"),
        "updatedAt": datetime.now(timezone.utc) - timedelta(days=age),
        "expiresAt": datetime.now(timezone.utc) - timedelta(hours=1), "status": "completed",
        "state": "collecting-review-rating", "orderId": "order-a", "orderIds": ["order-a"],
        "cart": [{"variantId": "variant-a", "quantity": 2}], "customerDraft": {"name": "Synthetic customer"},
        "recentTurns": [{"role": "customer", "text": "Keep this"}], "aiPaused": True,
        "lastMessage": "Keep the conversation", "unreadBySeller": 3,
    })


def test_store_and_product_links_reuse_one_session_and_preserve_the_latest_legacy_chat(store):
    legacy(store, "older", age=3)
    legacy(store, "latest", age=2)
    legacy(store, "another-customer", uid="customer-b", age=0)
    legacy(store, "another-store", business_id="business-b", age=0)
    before = deepcopy(store.documents)
    first = start(store)
    second = start(store, {"productCode": "product-link-a"})
    assert first["sessionId"] == second["sessionId"] == "latest"
    assert store.documents[POINTER] == {"sessionId": "latest"}
    saved = store.documents["publicChatSessions/latest"]
    for field in ("state", "orderId", "orderIds", "cart", "customerDraft", "recentTurns", "aiPaused", "lastMessage", "unreadBySeller"):
        assert saved[field] == before["publicChatSessions/latest"][field]
    for identifier in ("older", "another-customer", "another-store"):
        assert store.documents[f"publicChatSessions/{identifier}"] == before[f"publicChatSessions/{identifier}"]
    assert saved["productId"] is None
    assert saved["selectedProductId"] == PRODUCT["id"]
    assert second["product"] == PRODUCT
    assert second["cartSummary"][0]["quantity"] == 2
    assert second["cartSummary"][0]["unitPriceMinor"] == 1000


def test_simultaneous_first_starts_cannot_create_two_conversations(store):
    competing = []
    store.before_commit = lambda current: competing.append(start(current, {"productCode": "product-link-a"}))
    result = start(store)
    assert result["sessionId"] == competing[0]["sessionId"]
    assert len([path for path in store.documents if path.startswith("publicChatSessions/")]) == 1
    assert store.attempts == 3


def test_different_customers_have_separate_conversations(store):
    first = start(store)
    second = start(store, uid="customer-b")
    assert first["sessionId"] != second["sessionId"]


def test_the_same_customer_cannot_share_a_conversation_across_stores(store, monkeypatch):
    first = start(store)
    monkeypatch.setattr(chat, "get_public_store", Mock(return_value={
        "business": {**BUSINESS, "id": "business-b", "shortCode": "store-b"}, "products": [],
    }))
    second = start(store, {"storeCode": "store-b"})
    assert first["sessionId"] != second["sessionId"]
    assert store.documents[f"publicChatSessions/{first['sessionId']}"]["businessId"] == "business-a"


def test_failed_reservation_does_not_leave_a_session_or_pointer_partially_saved(store):
    def reject(current):
        raise PermissionDenied("Synthetic rejected conversation reservation")

    store.before_commit = reject
    with pytest.raises(PermissionDenied):
        start(store)
    assert store.documents == {}


def test_guest_sessions_keep_existing_independent_behavior(store):
    first = start(store, uid="anonymous-a", shared=False)
    second = start(store, uid="anonymous-a", shared=False)
    assert first["sessionId"] != second["sessionId"]
    assert not any("/customerChats/" in path for path in store.documents)
    assert "sharedConversation" not in first


def test_deleted_shared_chat_does_not_resurrect_an_old_archive(store):
    legacy(store, "archive")
    store.put(POINTER, {"sessionId": "deleted-session"})
    result = start(store)
    assert result["sessionId"] != "archive"
    assert store.documents[POINTER]["sessionId"] == result["sessionId"]


@pytest.mark.parametrize("uid,business_id", [("customer-b", "business-a"), ("customer-a", "business-b")])
def test_corrupt_pointer_cannot_reassign_another_customer_or_stores_chat(store, uid, business_id):
    legacy(store, "foreign", uid=uid, business_id=business_id)
    store.put(POINTER, {"sessionId": "foreign"})
    before = deepcopy(store.documents)
    with pytest.raises(ApiError) as error:
        start(store)
    assert error.value.status_code == 409
    assert store.documents == before


@pytest.mark.parametrize("uid,shared,expired,allowed", [
    ("customer-a", True, False, True),
    ("customer-b", True, False, False),
    (None, True, False, False),
    ("customer-a", False, False, False),
    ("customer-a", True, True, False),
])
def test_only_verified_shared_owner_can_use_a_token_rotated_by_another_device(store, uid, shared, expired, allowed):
    result = start(store)
    path = f"publicChatSessions/{result['sessionId']}"
    store.put(path, {**store.documents[path], "sharedConversation": shared,
        "expiresAt": datetime.now(timezone.utc) + timedelta(hours=-1 if expired else 1)})
    with Flask(__name__).test_request_context():
        g.current_user = {"uid": uid} if uid else None
        if allowed:
            snapshot, _ = chat.authorize_public_chat_session(store.client, result["sessionId"], "synthetic-stale")
            assert snapshot.id == result["sessionId"]
        else:
            with pytest.raises(ApiError) as error:
                chat.authorize_public_chat_session(store.client, result["sessionId"], "synthetic-stale")
            assert error.value.code == ("chat_session_expired" if expired else "invalid_chat_session")


@pytest.mark.parametrize("provider,shared", [("password", True), ("anonymous", False)])
def test_start_api_uses_verified_identity_instead_of_client_customer_fields(store, monkeypatch, provider, shared):
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={
        "uid": "customer-a", "email_verified": True, "firebase": {"sign_in_provider": provider},
    }))
    monkeypatch.setattr("app.api.public.get_firestore_client", lambda: store.client)
    response = create_app({"TESTING": True}).test_client().post("/api/v1/public/chat/sessions", json={
        "storeCode": "store-a", "customerUid": "customer-b", "share_customer_chat": True,
    }, headers={"Authorization": "Bearer synthetic-id-token"})
    assert response.status_code == 201
    result = response.get_json()
    assert store.documents[f"publicChatSessions/{result['sessionId']}"]["customerUid"] == "customer-a"
    assert result.get("sharedConversation", False) == shared


@pytest.mark.parametrize("uid,expected", [("customer-a", 200), ("customer-b", 401)])
def test_history_api_verifies_owner_before_accepting_a_rotated_token(store, monkeypatch, uid, expected):
    result = start(store)
    monkeypatch.setattr("app.initialize_firebase", Mock())
    verify = Mock(return_value={"uid": uid})
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", verify)
    monkeypatch.setattr("app.api.public.get_firestore_client", lambda: store.client)
    response = create_app({"TESTING": True}).test_client().get(
        f"/api/v1/public/chat/sessions/{result['sessionId']}/messages", headers={
            "Authorization": "Bearer synthetic-id-token", "X-Chat-Session-Token": "synthetic-stale",
        },
    )
    assert response.status_code == expected
    verify.assert_called_once_with("synthetic-id-token", check_revoked=True)


@pytest.mark.parametrize("uid,expected", [("customer-a", 422), ("customer-b", 401)])
def test_image_api_checks_shared_ownership_before_upload_validation(store, monkeypatch, uid, expected):
    result = start(store)
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": uid}))
    monkeypatch.setattr("app.api.public.get_firestore_client", lambda: store.client)
    upload = Mock()
    monkeypatch.setattr(chat, "upload_chat_data_url", upload)
    response = create_app({"TESTING": True}).test_client().post(
        f"/api/v1/public/chat/sessions/{result['sessionId']}/images", json={}, headers={
            "Authorization": "Bearer synthetic-id-token", "X-Chat-Session-Token": "synthetic-stale",
        },
    )
    assert response.status_code == expected
    upload.assert_not_called()
