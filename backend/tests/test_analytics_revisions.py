"""Analytics caching tracks shared source changes without scanning reports or adding writes."""

from unittest.mock import Mock

import pytest
from google.api_core.exceptions import PermissionDenied

from firestore_memory import MemoryFirestore
from app import create_app
from app.services.analytics_service import get_analytics_cache_revision, get_analytics_version

BUSINESS = "businesses/business-a"
MEMBER = f"{BUSINESS}/members/member-a"
HEADERS = {"Authorization": "Bearer synthetic-token"}


def seed():
    store = MemoryFirestore()
    store.put(BUSINESS, {"analyticsVersion": 4})
    store.put(MEMBER, {"role": "custom", "status": "active", "permissions": ["analytics:read"]})
    for collection in ("orders", "products", "customers"):
        store.put(f"{BUSINESS}/_cacheVersions/{collection}", {"revision": f"{collection}-original"})
    return store


@pytest.mark.parametrize("collection", ["orders", "products", "customers"])
def test_shared_service_changes_invalidate_analytics_without_a_legacy_counter_bump(collection):
    store = seed()
    original = get_analytics_cache_revision(store.client, "business-a")
    assert get_analytics_cache_revision(store.client, "business-a") == original
    store.put(f"{BUSINESS}/_cacheVersions/{collection}", {"revision": "shared-service-change"})
    updated = get_analytics_cache_revision(store.client, "business-a")
    assert updated["analyticsRevision"] != original["analyticsRevision"]
    assert updated["analyticsVersion"] == original["analyticsVersion"] == 4
    assert get_analytics_version(store.client, "business-a") == 4
    store.client._firestore_api.run_query.assert_not_called()
    store.client._firestore_api.commit.assert_not_called()


def test_legacy_counter_changes_still_invalidate_targets_and_other_existing_writers():
    store = seed()
    original = get_analytics_cache_revision(store.client, "business-a")
    store.put(BUSINESS, {"analyticsVersion": 5})
    updated = get_analytics_cache_revision(store.client, "business-a")
    assert updated["analyticsVersion"] == 5
    assert updated["analyticsRevision"] != original["analyticsRevision"]


def test_missing_markers_bootstrap_without_a_migration():
    store = MemoryFirestore()
    store.put(BUSINESS, {})
    original = get_analytics_cache_revision(store.client, "business-a")
    assert original["analyticsVersion"] == 0
    assert len(original["analyticsRevision"]) == 64
    assert get_analytics_cache_revision(store.client, "business-a") == original
    store.put(f"{BUSINESS}/_cacheVersions/orders", {"revision": "first-order"})
    assert get_analytics_cache_revision(store.client, "business-a") != original


def test_batch_response_order_does_not_change_the_revision():
    store = seed()
    original = get_analytics_cache_revision(store.client, "business-a")
    read = store.get_documents

    def reversed_markers(request, **kwargs):
        return read({**request, "documents": list(reversed(request["documents"]))}, **kwargs)

    store.client._firestore_api.batch_get_documents.side_effect = reversed_markers
    assert get_analytics_cache_revision(store.client, "business-a") == original


def test_metadata_is_pinned_to_one_read_time_during_concurrent_changes():
    store = seed()
    original = get_analytics_cache_revision(store.client, "business-a")
    read = store.get_documents
    changed = False

    def concurrent_read(request, **kwargs):
        nonlocal changed
        if any("/_cacheVersions/" in name for name in request["documents"]) and not changed:
            changed = True
            store.put(BUSINESS, {"analyticsVersion": 5})
            store.put(f"{BUSINESS}/_cacheVersions/orders", {"revision": "concurrent-order"})
        return read(request, **kwargs)

    store.client._firestore_api.batch_get_documents.side_effect = concurrent_read
    assert get_analytics_cache_revision(store.client, "business-a") == original
    assert changed
    assert get_analytics_cache_revision(store.client, "business-a") != original


def test_marker_read_failure_cannot_return_a_fallback_revision():
    store = seed()
    read = store.get_documents

    def failed_markers(request, **kwargs):
        if any("/_cacheVersions/" in name for name in request["documents"]):
            raise PermissionDenied("Synthetic denied marker read")
        return read(request, **kwargs)

    store.client._firestore_api.batch_get_documents.side_effect = failed_markers
    with pytest.raises(PermissionDenied):
        get_analytics_cache_revision(store.client, "business-a")


@pytest.fixture
def api(monkeypatch):
    store = seed()
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.analytics.get_firestore_client", lambda: store.client)
    return create_app({"TESTING": True}).test_client(), store


def test_opted_in_endpoint_reads_five_documents_in_three_rpcs_without_queries_or_writes(api):
    client, store = api
    response = client.get("/api/v1/businesses/business-a/analytics/version?includeRevision=1", headers=HEADERS)
    assert response.status_code == 200
    assert response.cache_control.no_store
    assert response.get_json()["analyticsVersion"] == 4
    assert len(response.get_json()["analyticsRevision"]) == 64
    reads = store.client._firestore_api.batch_get_documents.call_args_list
    assert len(reads) == 3
    assert sum(len(call.kwargs["request"]["documents"]) for call in reads) == 5
    assert any(len(call.kwargs["request"]["documents"]) == 3 and call.kwargs["request"].get("read_time") for call in reads)
    store.client._firestore_api.run_query.assert_not_called()
    store.client._firestore_api.commit.assert_not_called()


def test_existing_clients_keep_the_same_numeric_response_and_read_cost(api):
    client, store = api
    response = client.get("/api/v1/businesses/business-a/analytics/version", headers=HEADERS)
    assert response.get_json() == {"analyticsVersion": 4}
    reads = store.client._firestore_api.batch_get_documents.call_args_list
    assert sum(len(call.kwargs["request"]["documents"]) for call in reads) == 2


@pytest.mark.parametrize("headers, tenant, status, permission, expected", [
    ({}, "business-a", "active", "analytics:read", 401),
    (HEADERS, "business-b", "active", "analytics:read", 403),
    (HEADERS, "business-a", "inactive", "analytics:read", 403),
    (HEADERS, "business-a", "active", "orders:read", 403),
])
def test_revision_endpoint_rechecks_identity_tenant_and_analytics_read_access(api, headers, tenant, status, permission, expected):
    client, store = api
    store.put(MEMBER, {"role": "custom", "status": status, "permissions": [permission]})
    response = client.get(f"/api/v1/businesses/{tenant}/analytics/version?includeRevision=1&permissions=*", headers=headers)
    assert response.status_code == expected
    assert "analyticsRevision" not in response.get_json()
    reads = store.client._firestore_api.batch_get_documents.call_args_list
    assert all("/_cacheVersions/" not in name for call in reads for name in call.kwargs["request"]["documents"])
