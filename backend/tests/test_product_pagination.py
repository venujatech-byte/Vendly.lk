"""Use real SDK queries/cursors to verify private product pagination and the public catalogue bound."""

from unittest.mock import Mock

import pytest
from openpyxl import load_workbook

from firestore_memory import MemoryFirestore
from app import create_app
from app.core.errors import ApiError
from app.services import public_catalog_service
from app.services.product_service import PRODUCT_PAGE_SIZE, list_products, list_products_page
from app.services.spreadsheet_service import export_inventory_workbook


BUSINESS = "businesses/business-a"
MEMBER = f"{BUSINESS}/members/member-a"
HEADERS = {"Authorization": "Bearer synthetic-token"}


def seed(count):
    store = MemoryFirestore()
    store.put(BUSINESS, {"name": "Synthetic store", "status": "active"})
    store.put(MEMBER, {"role": "custom", "permissions": ["inventory:read"], "status": "active"})
    for index in reversed(range(count)):
        store.put(f"{BUSINESS}/products/product-{index:04d}", {
            "name": f"Product {index:04d}", "categoryId": "cat-a" if index % 2 == 0 else "cat-b",
            "status": "active" if index % 3 else "archived", "costPriceMinor": 100,
            "supplierId": "synthetic-private-supplier", "variantSummaries": [],
        })
    store.put("businesses/business-b/products/private-product", {"name": "Private product", "status": "active"})
    return store


def collect_pages(store, **filters):
    records = []
    cursor = None
    while True:
        result = list_products_page(store.client, "business-a", after=cursor, **filters)
        assert len(result["products"]) <= PRODUCT_PAGE_SIZE
        records.extend(result["products"])
        if not result["hasMore"]:
            assert result["nextCursor"] is None
            return records
        assert result["nextCursor"] != cursor
        cursor = result["nextCursor"]


@pytest.mark.parametrize("count", [0, 199, 200, 201, 400, 401])
def test_private_pages_cover_boundaries_in_existing_document_id_order(count):
    store = seed(count)
    records = collect_pages(store)
    assert [row["id"] for row in records] == [f"product-{index:04d}" for index in range(count)]
    assert len({row["id"] for row in records}) == count
    requests = [call.kwargs["request"] for call in store.client._firestore_api.run_query.call_args_list]
    assert all(request["structured_query"].limit == PRODUCT_PAGE_SIZE for request in requests)
    assert all(request["parent"].endswith(f"/documents/{BUSINESS}") for request in requests)


@pytest.mark.parametrize("filters", [{"category_id": "cat-a"}, {"status": "active"}, {"category_id": "cat-a", "status": "active"}])
def test_existing_category_and_status_filters_apply_across_all_pages(filters):
    store = seed(901)
    expected = [f"product-{index:04d}" for index in range(901)
                if (not filters.get("category_id") or index % 2 == 0)
                and (not filters.get("status") or index % 3 != 0)]
    assert [row["id"] for row in collect_pages(store, **filters)] == expected
    assert [row["id"] for row in list_products(store.client, "business-a", **filters)] == expected


def test_internal_inventory_and_search_callers_receive_all_products():
    records = list_products(seed(501).client, "business-a")
    assert isinstance(records, list)
    assert len(records) == 501
    assert records[-1]["id"] == "product-0500"


def test_cursor_product_can_be_renamed_or_deleted_without_skipping_the_next_page():
    store = seed(201)
    first = list_products_page(store.client, "business-a")
    cursor = first["nextCursor"]
    store.put(f"{BUSINESS}/products/{cursor}", {"name": "Renamed product"})
    renamed = list_products_page(store.client, "business-a", after=cursor)
    assert [row["id"] for row in renamed["products"]] == ["product-0200"]
    del store.documents[f"{BUSINESS}/products/{cursor}"]
    deleted = list_products_page(store.client, "business-a", after=cursor)
    assert [row["id"] for row in deleted["products"]] == ["product-0200"]


@pytest.mark.parametrize("cursor", ["a/b", "../business-b/products/private-product", ".", "..", "__reserved__", "x" * 1501])
def test_invalid_product_cursor_paths_are_rejected(cursor):
    with pytest.raises(ApiError) as error:
        list_products_page(seed(1).client, "business-a", after=cursor)
    assert error.value.code == "invalid_product_cursor"
    assert error.value.status_code == 422


def test_foreign_cursor_id_never_changes_the_query_tenant():
    store = seed(1)
    page = list_products_page(store.client, "business-a", after="private-product")
    assert all(row["id"] != "private-product" for row in page["products"])
    request = store.client._firestore_api.run_query.call_args.kwargs["request"]
    assert request["parent"].endswith(f"/documents/{BUSINESS}")
    assert request["structured_query"].start_at.values[0].reference_value.endswith(f"/{BUSINESS}/products/private-product")


def test_public_catalogue_retains_the_200_active_product_cap_and_safe_projection(monkeypatch):
    store = seed(501)
    monkeypatch.setattr(public_catalog_service, "_STORE_CACHE", {})
    monkeypatch.setattr(public_catalog_service, "resolve_short_link", Mock(return_value={"businessId": "business-a"}))
    result = public_catalog_service.get_public_store(store.client, "synthetic-store")
    assert len(result["products"]) == 200
    assert all("costPriceMinor" not in row and "supplierId" not in row for row in result["products"])
    expected = [f"product-{index:04d}" for index in range(501) if index % 3 != 0][:200]
    assert [row["id"] for row in result["products"]] == expected
    request = store.client._firestore_api.run_query.call_args.kwargs["request"]
    assert request["structured_query"].limit == 200
    assert request["structured_query"].where.field_filter.value.string_value == "active"


def test_existing_inventory_export_accepts_a_product_beyond_the_first_200():
    workbook = load_workbook(export_inventory_workbook(seed(501).client, "business-a", ["product-0500"]), read_only=True)
    try:
        rows = list(workbook["Products"].values)
        assert len(rows) == 2
        assert rows[1][0] == "product-0500"
    finally:
        workbook.close()


@pytest.fixture
def api(monkeypatch):
    store = seed(901)
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.products.get_firestore_client", lambda: store.client)
    return create_app({"TESTING": True}).test_client(), store


def test_api_returns_bounded_filtered_pages_and_keeps_tenant_scope(api):
    client, _store = api
    path = "/api/v1/businesses/business-a/products?categoryId=cat-a&status=active&limit=99999&businessId=business-b"
    first = client.get(path, headers=HEADERS)
    assert first.status_code == 200
    page = first.get_json()
    assert len(page["products"]) == 200 and page["hasMore"]
    last = client.get(f"{path}&after={page['nextCursor']}", headers=HEADERS).get_json()
    records = page["products"] + last["products"]
    assert len(records) == 300
    assert last["hasMore"] is False
    assert all(row["categoryId"] == "cat-a" and row["status"] == "active" for row in records)


def test_api_rechecks_membership_before_each_page(api):
    client, store = api
    first = client.get("/api/v1/businesses/business-a/products", headers=HEADERS).get_json()
    store.put(MEMBER, {"role": "custom", "permissions": ["inventory:read"], "status": "inactive"})
    response = client.get(f"/api/v1/businesses/business-a/products?after={first['nextCursor']}", headers=HEADERS)
    assert response.status_code == 403
    assert "products" not in response.get_json()


@pytest.mark.parametrize("headers, tenant, permissions, status", [
    ({}, "business-a", ["inventory:read"], 401),
    (HEADERS, "business-b", ["inventory:read"], 403),
    (HEADERS, "business-a", ["orders:read"], 403),
])
def test_api_pages_require_the_authenticated_tenant_and_inventory_read_permission(api, headers, tenant, permissions, status):
    client, store = api
    store.put(MEMBER, {"role": "custom", "permissions": permissions, "status": "active"})
    response = client.get(f"/api/v1/businesses/{tenant}/products?after=product-0001&permissions=*", headers=headers)
    assert response.status_code == status
    assert "products" not in response.get_json()
