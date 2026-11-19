"""Search cache revisions use only current allowed modules and their existing atomic markers."""

from unittest.mock import Mock

import pytest

from firestore_memory import MemoryFirestore
from app import create_app
from app.services import search_service

BUSINESS = "businesses/business-a"
MEMBER = f"{BUSINESS}/members/member-a"
HEADERS = {"Authorization": "Bearer synthetic-token"}


def seed():
    store = MemoryFirestore()
    store.put(BUSINESS, {})
    store.put(MEMBER, {"role": "owner", "status": "active", "permissions": []})
    for name in ("orders", "products", "customers"):
        store.put(f"{BUSINESS}/_cacheVersions/{name}", {"revision": f"{name}-original"})
    return store


@pytest.mark.parametrize("permission, scope", [
    ("orders:read", "orders"), ("inventory:read", "products"), ("customers:read", "customers"),
    ("orders:manage", ""), ("inventory", "products"), ("*", "orders,products,customers"),
])
def test_search_revision_reads_only_permitted_markers_and_never_collection_data(permission, scope):
    store = seed()
    result = search_service.get_search_revision(store.client, "business-a", {"role": "custom", "permissions": [permission]})
    assert result["scope"] == scope
    assert len(result["revision"]) == 64
    reads = store.client._firestore_api.batch_get_documents.call_args_list
    actual = {call.kwargs["request"]["documents"][0].split("/documents/", 1)[1] for call in reads}
    assert actual == {f"{BUSINESS}/_cacheVersions/{name}" for name in scope.split(",") if name}
    store.client._firestore_api.run_query.assert_not_called()
    store.client._firestore_api.commit.assert_not_called()


def test_revision_changes_for_data_or_read_permissions_but_not_for_unreadable_modules():
    store = seed()
    member = {"role": "custom", "permissions": ["orders:read"]}
    original = search_service.get_search_revision(store.client, "business-a", member)
    assert search_service.get_search_revision(store.client, "business-a", member) == original
    store.put(f"{BUSINESS}/_cacheVersions/products", {"revision": "mobile-product-edit"})
    assert search_service.get_search_revision(store.client, "business-a", member) == original
    store.put(f"{BUSINESS}/_cacheVersions/orders", {"revision": "mobile-order-edit"})
    changed = search_service.get_search_revision(store.client, "business-a", member)
    assert changed["revision"] != original["revision"]
    expanded = search_service.get_search_revision(store.client, "business-a", {"role": "custom", "permissions": ["orders:read", "inventory:read"]})
    assert expanded["scope"] == "orders,products"
    assert expanded["revision"] != changed["revision"]


def test_missing_markers_and_equal_values_still_distinguish_permission_scopes():
    store = MemoryFirestore()
    orders = search_service.get_search_revision(store.client, "business-a", {"permissions": ["orders:read"]})
    customers = search_service.get_search_revision(store.client, "business-a", {"permissions": ["customers:read"]})
    assert orders["revision"] != customers["revision"]
    assert search_service.get_search_revision(store.client, "business-a", {"permissions": ["orders:read"]}) == orders


@pytest.fixture
def api(monkeypatch):
    store = seed()
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.search.get_firestore_client", lambda: store.client)
    return create_app({"TESTING": True}).test_client(), store


def test_search_version_endpoint_uses_four_document_reads_for_owner_and_no_queries_or_writes(api):
    client, store = api
    response = client.get("/api/v1/businesses/business-a/search/cache/version", headers=HEADERS)
    assert response.status_code == 200
    assert response.cache_control.no_store
    assert response.get_json()["scope"] == "orders,products,customers"
    reads = store.client._firestore_api.batch_get_documents.call_args_list
    assert len(reads) == 4
    store.client._firestore_api.run_query.assert_not_called()
    store.client._firestore_api.commit.assert_not_called()


@pytest.mark.parametrize("headers, tenant, status, expected", [
    ({}, "business-a", "active", 401), (HEADERS, "business-b", "active", 403),
    (HEADERS, "business-a", "inactive", 403),
])
def test_search_version_endpoint_rechecks_authentication_tenant_and_active_membership(api, headers, tenant, status, expected):
    client, store = api
    store.put(MEMBER, {"role": "owner", "status": status})
    response = client.get(f"/api/v1/businesses/{tenant}/search/cache/version?permissions=*&role=owner", headers=headers)
    assert response.status_code == expected
    assert "revision" not in response.get_json()
    reads = store.client._firestore_api.batch_get_documents.call_args_list
    assert all("/_cacheVersions/" not in call.kwargs["request"]["documents"][0] for call in reads)


def test_results_are_bound_to_data_request_membership_even_when_permissions_changed_after_version_check(api, monkeypatch):
    client, store = api
    monkeypatch.setattr(search_service, "stream_orders", Mock(return_value=[]))
    monkeypatch.setattr(search_service, "stream_products", Mock(return_value=[]))
    monkeypatch.setattr(search_service, "stream_customers", Mock(return_value=[]))
    store.put(MEMBER, {"role": "custom", "status": "active", "permissions": ["orders:read"]})
    version = client.get("/api/v1/businesses/business-a/search/cache/version", headers=HEADERS).get_json()
    store.put(MEMBER, {"role": "owner", "status": "active"})
    legacy = client.get("/api/v1/businesses/business-a/search?q=match", headers=HEADERS).get_json()
    assert set(legacy) == {"results"}
    results = client.get("/api/v1/businesses/business-a/search?q=match&includeScope=1", headers=HEADERS).get_json()
    assert version["scope"] == "orders"
    assert results["scope"] == "orders,products,customers"
    assert search_service.stream_products.call_count == 2
    search_service.stream_products.assert_called_with(store.client, "business-a")
