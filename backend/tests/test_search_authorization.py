"""Global search must not load or return records from unauthorized modules."""

from unittest.mock import Mock

import pytest

from app import create_app
from app.services import search_service


@pytest.fixture
def search_api(monkeypatch):
    # Keep the real authentication, membership gate, permission helper and search projection.
    database = Mock()
    member = database.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value
    member.exists = True
    member.to_dict.return_value = {"role": "custom", "status": "active", "permissions": []}
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: database)
    monkeypatch.setattr("app.api.search.get_firestore_client", lambda: database)
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "staff-a"}))
    loaders = {
        "orders": Mock(return_value=[{"id": "order-a", "orderNumber": "Match order", "customerSnapshot": {"name": "Private Customer"}}]),
        "products": Mock(return_value=[{"id": "product-a", "name": "Match product"}]),
        "customers": Mock(return_value=[{"id": "customer-a", "name": "Match customer", "normalizedPhone": "94771234567"}]),
    }
    for category, function in [("orders", "stream_orders"), ("products", "stream_products"), ("customers", "stream_customers")]:
        monkeypatch.setattr(search_service, function, loaders[category])
    return create_app({"TESTING": True}).test_client(), database, member, loaders


@pytest.mark.parametrize("role, permissions, allowed", [
    ("custom", ["inventory:read"], {"products"}),
    ("custom", ["orders:read"], {"orders"}),
    ("custom", ["customers:read"], {"customers"}),
    ("custom", ["orders:read", "inventory:read"], {"orders", "products"}),
    ("custom", ["inventory", "inventory:read"], {"products"}),
    ("custom", ["inventory:manage"], set()),
    ("custom", ["inventory:*"], {"products"}),
    ("custom", ["customers"], {"customers"}),
    ("custom", ["analytics:read"], set()),
    ("custom", [], set()),
    ("owner", [], {"orders", "products", "customers"}),
    ("admin", ["*"], {"orders", "products", "customers"}),
    ("admin", ["inventory:read"], {"products"}),
])
def test_search_obeys_server_verified_module_permissions(search_api, role, permissions, allowed):
    client, database, member, loaders = search_api
    member.to_dict.return_value.update(role=role, permissions=permissions)
    # Query parameters cannot forge broader membership rights.
    response = client.get(
        "/api/v1/businesses/business-a/search?q=Match&role=owner&permissions=*",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    results = response.get_json()["results"]
    assert set(results) == {"orders", "products", "customers"}
    for category, loader in loaders.items():
        if category in allowed:
            assert len(results[category]) == 1
            loader.assert_called_once_with(database, "business-a")
        else:
            assert results[category] == []
            loader.assert_not_called()


@pytest.mark.parametrize("membership", ["inactive", "missing"])
def test_search_denies_inactive_or_missing_tenant_membership(search_api, membership):
    client, database, member, loaders = search_api
    member.exists = membership != "missing"
    member.to_dict.return_value.update(role="owner", status="inactive")
    response = client.get(
        "/api/v1/businesses/business-a/search?q=Match", headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 403
    database.collection.return_value.document.assert_called_once_with("business-a")
    database.collection.return_value.document.return_value.collection.return_value.document.assert_called_once_with("staff-a")
    for loader in loaders.values():
        loader.assert_not_called()


def test_search_requires_authentication(search_api):
    client, database, _, loaders = search_api
    assert client.get("/api/v1/businesses/business-a/search?q=Match").status_code == 401
    database.collection.assert_not_called()
    for loader in loaders.values():
        loader.assert_not_called()


@pytest.mark.parametrize("query", ["", " <b>x</b> "])
def test_short_searches_still_verify_membership_but_never_load_module_data(search_api, query):
    client, database, member, loaders = search_api
    member.to_dict.return_value.update(role="owner")
    response = client.get(
        "/api/v1/businesses/business-a/search", query_string={"q": query},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.get_json()["results"] == {"orders": [], "products": [], "customers": []}
    member.to_dict.assert_called_once()
    for loader in loaders.values():
        loader.assert_not_called()
