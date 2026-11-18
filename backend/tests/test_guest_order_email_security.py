"""Receipt destinations require verified ownership before any write or email."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from firebase_admin.auth import RevokedIdTokenError

from app import create_app
from app.core.errors import ApiError
from app.services import customer_portal_service as portal
from app.services import email_service
from app.services.public_chat_service import token_hash


@pytest.fixture
def receipt(monkeypatch):
    # Keep all order, session and delivery operations in memory.
    database = Mock()
    business = Mock()
    order = business.collection.return_value.document.return_value
    order.get.return_value.exists = True
    order.get.return_value.to_dict.return_value = {
        "customerUid": "customer-a", "customerSnapshot": {"name": "Customer"},
    }
    session = Mock()
    session.get.return_value.exists = True
    session.get.return_value.to_dict.return_value = {
        "businessId": "business-a", "orderIds": ["order-a"],
        "tokenHash": token_hash("original-secret"),
        "expiresAt": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    database.collection.side_effect = lambda name: {
        "businesses": Mock(document=Mock(return_value=business)),
        "publicChatSessions": Mock(document=Mock(return_value=session)),
    }[name]
    monkeypatch.setattr(portal, "resolve_store_business_id", lambda *args: "business-a")
    monkeypatch.setattr("app.api.public.get_firestore_client", lambda: database)
    send = Mock()
    monkeypatch.setattr(email_service, "send_order_confirmation_email", send)
    return database, order, session, send


@pytest.mark.parametrize("identity", [None, "customer-b"])
def test_order_ids_and_other_identities_cannot_redirect_receipts(receipt, identity):
    database, order, _, send = receipt
    with pytest.raises(ApiError):
        portal.update_order_guest_email(
            database, "store", "order-a", "attacker@example.com", customer_uid=identity,
        )
    order.update.assert_not_called()
    send.assert_not_called()


def test_verified_owner_can_update_and_receive_receipt(receipt):
    database, order, _, send = receipt
    result = portal.update_order_guest_email(
        database, "store", "order-a", " Owner@Example.com ", customer_uid="customer-a",
    )
    assert result == {"success": True, "email": "owner@example.com"}
    order.update.assert_called_once_with({
        "customerSnapshot": {"name": "Customer", "email": "owner@example.com"},
    })
    assert send.call_args.kwargs["recipient_email"] == "owner@example.com"


@pytest.mark.parametrize("legacy_field", ["orderId", "orderIds"])
def test_legacy_guest_can_use_original_order_session(receipt, legacy_field):
    database, order, session, send = receipt
    order.get.return_value.to_dict.return_value.pop("customerUid")
    data = session.get.return_value.to_dict.return_value
    data.pop("orderIds")
    data[legacy_field] = "order-a" if legacy_field == "orderId" else ["order-a"]
    portal.update_order_guest_email(
        database, "store", "order-a", "guest@example.com",
        session_id="session-a", session_token="original-secret",
    )
    order.update.assert_called_once()
    send.assert_called_once()


@pytest.mark.parametrize("failure", [
    "bad-token", "expired", "wrong-tenant", "wrong-order", "missing-session",
    "bound-session", "bound-order", "no-session-proof", "missing-order",
])
def test_invalid_ownership_never_writes_or_sends(receipt, failure):
    database, order, session, send = receipt
    data = session.get.return_value.to_dict.return_value
    order.get.return_value.to_dict.return_value.pop("customerUid")
    token = "original-secret"
    if failure == "bad-token":
        token = "forged"
    elif failure == "expired":
        data["expiresAt"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif failure == "wrong-tenant":
        data["businessId"] = "business-b"
    elif failure == "wrong-order":
        data["orderIds"] = ["order-b"]
    elif failure == "missing-session":
        session.get.return_value.exists = False
    elif failure == "bound-session":
        data["customerUid"] = "customer-b"
    elif failure == "bound-order":
        order.get.return_value.to_dict.return_value["customerUid"] = "customer-b"
    elif failure == "no-session-proof":
        token = None
    elif failure == "missing-order":
        order.get.return_value.exists = False
    with pytest.raises(ApiError) as error:
        portal.update_order_guest_email(
            database, "store", "order-a", "attacker@example.com", customer_uid="customer-a",
            session_id="session-a", session_token=token,
        )
    assert error.value.status_code == 404
    order.update.assert_not_called()
    send.assert_not_called()


@pytest.mark.parametrize("identity", [None, "customer-a", "customer-b", "revoked"])
def test_email_route_verifies_identity_and_ignores_payload_uid(receipt, monkeypatch, identity):
    _, order, _, send = receipt
    verify = Mock(return_value={"uid": identity})
    if identity == "revoked":
        verify.side_effect = RevokedIdTokenError("Revoked")
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", verify)
    app = create_app({"TESTING": True, "RATELIMIT_ENABLED": False})
    response = app.test_client().post(
        "/api/v1/public/stores/store/orders/order-a/email",
        json={"email": "owner@example.com", "customerUid": "customer-a", "userId": "customer-a"},
        headers={"Authorization": "Bearer test-token"} if identity else {},
    )
    assert response.status_code == (200 if identity == "customer-a" else 404 if identity == "customer-b" else 401)
    if identity:
        verify.assert_called_once_with("test-token", check_revoked=True)
    if identity != "customer-a":
        order.update.assert_not_called()
        send.assert_not_called()


@pytest.mark.parametrize("identity", [None, "customer-a"])
def test_email_route_accepts_original_legacy_session_credentials(receipt, monkeypatch, identity):
    _, order, session, send = receipt
    # Exercise the HTTP header and body together with the real session-token verifier.
    order.get.return_value.to_dict.return_value.pop("customerUid")
    if identity:
        session.get.return_value.to_dict.return_value["customerUid"] = identity
    monkeypatch.setattr(
        "app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": identity}),
    )
    headers = {"X-Chat-Session-Token": "original-secret"}
    if identity:
        headers["Authorization"] = "Bearer test-token"
    app = create_app({"TESTING": True})
    response = app.test_client().post(
        "/api/v1/public/stores/store/orders/order-a/email", headers=headers,
        json={"email": "guest@example.com", "sessionId": "session-a"},
    )
    assert response.status_code == 200
    order.update.assert_called_once()
    send.assert_called_once()
