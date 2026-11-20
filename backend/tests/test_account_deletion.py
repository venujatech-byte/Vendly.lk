"""Account deletion must fail closed and never report partial cleanup as success."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from firebase_admin import auth
from google.api_core.exceptions import PermissionDenied

from app import create_app
from app.core.errors import ApiError
from app.services import realtime_access_service
from firestore_memory import MemoryFirestore

NOW = 1800000000
USER = "users/customer-a"
MEMBER = "businesses/business-a/members/customer-a"
SELLER = "sellers/customer-a"
HEADERS = {"Authorization": "Bearer synthetic-token"}


@pytest.fixture
def deletion(monkeypatch):
    # Use real SDK batches/preconditions with offline transports and Auth/realtime boundaries.
    store = MemoryFirestore()
    store.put(USER, {"businessIds": ["business-a"], "defaultBusinessId": "business-a"})
    store.put(MEMBER, {"uid": "customer-a", "role": "support"})
    store.put(SELLER, {"name": "Synthetic staff profile"})
    store.put("businesses/business-a", {"ownerUid": "owner-a"})
    store.put("businesses/business-a/orders/order-a", {"totalAmountMinor": 1000})
    claims = {"uid": "customer-a", "auth_time": NOW - 30}
    verify = Mock(side_effect=lambda *_a, **_k: dict(claims))
    delete_auth = Mock()
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.api.me.time", lambda: NOW)
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", verify)
    monkeypatch.setattr("app.api.me.auth.delete_user", delete_auth)
    monkeypatch.setattr("app.api.me.get_firestore_client", lambda: store.client)
    client = create_app({"TESTING": True}).test_client()
    return store, claims, delete_auth, client


def test_success_cleans_known_account_records_before_auth_without_touching_business_data(deletion):
    store, _, delete_auth, client = deletion
    retained = {path: deepcopy(data) for path, data in store.documents.items() if path not in {USER, MEMBER, SELLER}}

    def verify_cleanup(uid):
        assert uid == "customer-a"
        assert store.documents == retained
        realtime_access_service.disable_realtime_user.assert_called_once_with(uid)

    delete_auth.side_effect = verify_cleanup
    response = client.delete("/api/v1/me", headers=HEADERS)
    assert response.status_code == 200
    assert response.get_json() == {"deleted": True}
    assert store.commits == 1
    delete_auth.assert_called_once_with("customer-a")


@pytest.mark.parametrize("auth_time", [None, True, "1800000000", NOW - 301, NOW + 1, float("nan"), float("inf")])
def test_recent_sign_in_is_required_before_any_database_or_realtime_action(deletion, auth_time):
    store, claims, delete_auth, client = deletion
    claims["auth_time"] = auth_time
    response = client.delete("/api/v1/me", headers=HEADERS)
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "recent_login_required"
    store.client._firestore_api.run_query.assert_not_called()
    store.client._firestore_api.batch_get_documents.assert_not_called()
    realtime_access_service.disable_realtime_user.assert_not_called()
    delete_auth.assert_not_called()


@pytest.mark.parametrize("legacy", [False, True])
def test_business_owners_are_blocked_before_realtime_revocation_or_cleanup(deletion, legacy):
    store, _, delete_auth, client = deletion
    if legacy:
        store.put(MEMBER, {"uid": "customer-a", "role": "owner"})
        store.put("businesses/business-a", {})
    else:
        # Ownership lookup must catch a business missing from the profile's saved list.
        store.put("businesses/unlisted", {"ownerUid": "customer-a"})
        store.put(USER, {})
    before = deepcopy(store.documents)
    response = client.delete("/api/v1/me", headers=HEADERS)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "business_owner_deletion_blocked"
    assert store.documents == before
    realtime_access_service.disable_realtime_user.assert_not_called()
    delete_auth.assert_not_called()


@pytest.mark.parametrize("path,change", [(MEMBER, {"role": "owner"}), (USER, {"businessIds": ["business-a", "business-b"]})])
def test_concurrent_role_or_profile_changes_abort_the_entire_cleanup(deletion, path, change):
    store, _, delete_auth, client = deletion
    store.before_commit = lambda current: current.put(path, {**current.documents[path], **change})
    response = client.delete("/api/v1/me", headers=HEADERS)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "account_changed"
    assert {USER, MEMBER, SELLER} <= store.documents.keys()
    assert all(store.documents[path][key] == value for key, value in change.items())
    assert store.commits == 0
    delete_auth.assert_not_called()


@pytest.mark.parametrize("stage", ["query", "realtime", "commit"])
def test_cleanup_failures_never_delete_auth_or_report_success(deletion, stage):
    store, _, delete_auth, client = deletion
    before = deepcopy(store.documents)
    if stage == "query":
        store.client._firestore_api.run_query.side_effect = PermissionDenied("Synthetic denied ownership query")
    elif stage == "commit":
        store.client._firestore_api.commit.side_effect = PermissionDenied("Synthetic denied cleanup")
    else:
        realtime_access_service.disable_realtime_user.side_effect = ApiError("realtime_access_unavailable", "Synthetic realtime outage", 503)
    response = client.delete("/api/v1/me", headers=HEADERS)
    assert response.status_code == 503
    assert "deleted" not in response.get_json()
    assert store.documents == before
    delete_auth.assert_not_called()


def test_auth_failure_is_reported_and_partial_cross_service_cleanup_can_be_retried(deletion):
    store, _, delete_auth, client = deletion
    delete_auth.side_effect = RuntimeError("Synthetic private provider detail")
    response = client.delete("/api/v1/me", headers=HEADERS)
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "account_deletion_failed"
    assert "provider detail" not in response.get_data(as_text=True)
    assert not {USER, MEMBER, SELLER} & store.documents.keys()
    assert "businesses/business-a/orders/order-a" in store.documents
    delete_auth.side_effect = None
    response = client.delete("/api/v1/me", headers=HEADERS)
    assert response.status_code == 200
    assert delete_auth.call_count == 2


def test_already_missing_auth_account_counts_as_deleted(deletion):
    _, _, delete_auth, client = deletion
    delete_auth.side_effect = auth.UserNotFoundError("Synthetic missing account")
    assert client.delete("/api/v1/me", headers=HEADERS).get_json() == {"deleted": True}


def test_default_business_membership_is_cleaned_even_without_the_business_list(deletion):
    store, _, _, client = deletion
    store.put(USER, {"defaultBusinessId": "business-a"})
    assert client.delete("/api/v1/me", headers=HEADERS).status_code == 200
    assert MEMBER not in store.documents


def test_malformed_membership_links_fail_before_mutation(deletion):
    store, _, delete_auth, client = deletion
    store.put(USER, {"businessIds": "not-a-list"})
    before = deepcopy(store.documents)
    assert client.delete("/api/v1/me", headers=HEADERS).status_code == 503
    assert store.documents == before
    realtime_access_service.disable_realtime_user.assert_not_called()
    delete_auth.assert_not_called()
