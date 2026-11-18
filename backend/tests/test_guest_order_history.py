"""Link guest order history only after both Firebase identities have been verified."""

from unittest.mock import Mock

import pytest
from firebase_admin.auth import RevokedIdTokenError, ExpiredIdTokenError, UserDisabledError

from firestore_memory import MemoryFirestore
from app import create_app
from app.services import customer_portal_service as portal


@pytest.fixture
def history(monkeypatch):
    store = MemoryFirestore()
    store.put("businesses/business-a/orders/order-a", {"customerUid": "guest-a", "customerId": "profile-a"})
    store.put("businesses/business-a/orders/order-b", {"customerUid": "guest-a", "customerId": "profile-b"})
    store.put("businesses/business-a/orders/private-order", {"customerUid": "private-user", "customerId": "profile-a"})
    store.put("businesses/business-b/orders/other-store-order", {"customerUid": "guest-a"})
    monkeypatch.setattr(portal, "resolve_store_business_id", lambda *a: "business-a")
    monkeypatch.setattr("app.api.public.get_firestore_client", lambda: store.client)
    verify = Mock(side_effect=lambda token, **kw: {
        "account-token": {"uid": "account-a", "email_verified": True, "firebase": {"sign_in_provider": "password"}},
        "guest-token": {"uid": "guest-a", "firebase": {"sign_in_provider": "anonymous"}},
    }[token])
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", verify)
    client = create_app({"TESTING": True}).test_client()
    return store, client, verify


def claim(client, token="guest-token", account_token="account-token"):
    # The forged UID fields must have no effect; both actual UIDs come from verified JWTs.
    return client.post(
        "/api/v1/public/stores/store/customer/claim-guest-orders",
        headers={"Authorization": f"Bearer {account_token}"},
        json={"guestIdToken": token, "guestUid": "private-user", "customerUid": "attacker"},
    )


def test_verified_guest_history_links_only_owned_orders_in_this_store(history):
    store, client, verify = history
    response = claim(client)
    assert response.status_code == 200
    assert response.get_json() == {"claimedOrders": 2}
    assert store.documents["businesses/business-a/orders/order-a"]["customerUid"] == "account-a"
    assert store.documents["businesses/business-a/orders/order-b"]["customerUid"] == "account-a"
    assert store.documents["businesses/business-a/orders/private-order"]["customerUid"] == "private-user"
    assert store.documents["businesses/business-b/orders/other-store-order"]["customerUid"] == "guest-a"
    verify.assert_any_call("account-token", check_revoked=True)
    verify.assert_any_call("guest-token", check_revoked=True)
    assert claim(client).get_json() == {"claimedOrders": 0}


def test_concurrent_reassignment_is_not_overwritten(history):
    store, client, _ = history
    path = "businesses/business-a/orders/order-a"
    store.before_commit = lambda current: current.put(path, {"customerUid": "another-account"})
    assert claim(client).get_json() == {"claimedOrders": 1}
    assert store.documents[path]["customerUid"] == "another-account"


@pytest.mark.parametrize("failure", ["expired", "revoked", "disabled", "missing", "not-guest"])
def test_invalid_source_identity_cannot_transfer_orders(history, failure):
    store, client, verify = history
    original = verify.side_effect

    def checked(token, **kwargs):
        if token == "account-token":
            return original(token, **kwargs)
        if failure == "expired":
            raise ExpiredIdTokenError("Expired", None)
        if failure == "revoked":
            raise RevokedIdTokenError("Revoked")
        if failure == "disabled":
            raise UserDisabledError("Disabled")
        if failure == "missing":
            raise ValueError("Missing guest token")
        return {"uid": "private-user", "firebase": {"sign_in_provider": "password"}}

    verify.side_effect = checked
    assert claim(client, token="" if failure == "missing" else "guest-token").status_code == (403 if failure == "not-guest" else 401)
    assert store.commits == 0


def test_anonymous_target_cannot_claim_another_guest_history(history):
    store, client, _ = history
    assert claim(client, account_token="guest-token").status_code == 403
    assert store.commits == 0


def test_history_link_requires_signed_in_account(history):
    store, client, _ = history
    assert client.post("/api/v1/public/stores/store/customer/claim-guest-orders", json={"guestIdToken": "guest-token"}).status_code == 401
    assert store.commits == 0


def test_unverified_destination_account_cannot_receive_guest_history(history):
    store, client, verify = history
    original = verify.side_effect
    verify.side_effect = lambda token, **kwargs: {**original(token, **kwargs), "email_verified": False}
    assert claim(client).status_code == 403
    verify.assert_called_once_with("account-token", check_revoked=True)
    assert store.commits == 0


def test_upgraded_guest_with_same_uid_needs_no_reassignment(history):
    store, _, _ = history
    result = portal.claim_guest_customer_orders(store.client, "store", "guest-a", "guest-a")
    assert result == {"claimedOrders": 0}
    assert store.commits == 0
