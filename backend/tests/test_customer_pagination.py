"""Verify complete customer scans, tenant-safe API pages and unchanged phone matching offline."""

from unittest.mock import Mock

import pytest

from firestore_memory import MemoryFirestore
from app import create_app
from app.core.errors import ApiError
from app.services.customer_service import CUSTOMER_PAGE_SIZE, list_customers, list_customers_page


BUSINESS = "businesses/business-a"
MEMBER = f"{BUSINESS}/members/member-a"
HEADERS = {"Authorization": "Bearer synthetic-token"}


def seed(count):
    store = MemoryFirestore()
    store.put(BUSINESS, {})
    store.put(MEMBER, {"role": "custom", "permissions": ["customers:read"], "status": "active"})
    for index in reversed(range(count)):
        store.put(f"{BUSINESS}/customers/customer-{index:04d}", {
            "name": f"Name {index:04d}", "normalizedPhone": f"947{index:08d}", "status": "active",
        })
    store.put("businesses/business-b/customers/private-customer", {"name": "Private customer", "normalizedPhone": "94712345678"})
    return store


@pytest.mark.parametrize("count", [0, 199, 200, 201, 400, 401])
def test_pages_cover_boundaries_and_duplicate_names_without_skips_or_duplicates(count):
    store = seed(count)
    for path, data in list(store.documents.items()):
        if path.startswith(f"{BUSINESS}/customers/"):
            store.put(path, {**data, "name": "Same name"})
    ids = []
    cursor = None
    while True:
        page = list_customers_page(store.client, "business-a", after=cursor)
        assert len(page["customers"]) <= CUSTOMER_PAGE_SIZE
        ids.extend(row["id"] for row in page["customers"])
        if not page["hasMore"]:
            assert page["nextCursor"] is None
            break
        assert page["nextCursor"] != cursor
        cursor = page["nextCursor"]
    assert ids == [f"customer-{index:04d}" for index in range(count)]
    assert len(set(ids)) == count
    requests = [call.kwargs["request"] for call in store.client._firestore_api.run_query.call_args_list]
    assert all(request["structured_query"].limit == CUSTOMER_PAGE_SIZE for request in requests)
    assert all(request["parent"].endswith(f"/documents/{BUSINESS}") for request in requests)


def test_archived_or_nonmatching_pages_still_advance_to_later_matches():
    store = seed(401)
    for index in range(200):
        path = f"{BUSINESS}/customers/customer-{index:04d}"
        store.put(path, {**store.documents[path], "status": "archived"})
    path = f"{BUSINESS}/customers/customer-0400"
    store.put(path, {**store.documents[path], "name": "Later MATCH customer"})
    first = list_customers_page(store.client, "business-a", search="match")
    assert first["customers"] == [] and first["hasMore"]
    second = list_customers_page(store.client, "business-a", search="match", after=first["nextCursor"])
    assert second["customers"] == [] and second["hasMore"]
    last = list_customers_page(store.client, "business-a", search="match", after=second["nextCursor"])
    assert [row["id"] for row in last["customers"]] == ["customer-0400"]
    assert last["hasMore"] is False


def test_scans_advance_when_a_cursor_customer_is_renamed_or_deleted():
    store = seed(201)
    first = list_customers_page(store.client, "business-a")
    cursor = first["nextCursor"]
    store.put(f"{BUSINESS}/customers/{cursor}", {"name": "ZZZ renamed customer"})
    renamed = list_customers_page(store.client, "business-a", after=cursor)
    assert [row["id"] for row in renamed["customers"]] == ["customer-0200"]
    del store.documents[f"{BUSINESS}/customers/{cursor}"]
    deleted = list_customers_page(store.client, "business-a", after=cursor)
    assert [row["id"] for row in deleted["customers"]] == ["customer-0200"]


@pytest.mark.parametrize("cursor", ["a/b", "../business-b/customers/private-customer", ".", "..", "__reserved__", "x" * 1501])
def test_invalid_customer_cursor_paths_are_rejected(cursor):
    with pytest.raises(ApiError) as error:
        list_customers_page(seed(1).client, "business-a", after=cursor)
    assert error.value.code == "invalid_customer_cursor"
    assert error.value.status_code == 422


def test_foreign_document_id_cannot_change_the_scan_tenant():
    store = seed(1)
    page = list_customers_page(store.client, "business-a", after="private-customer")
    assert page["customers"] == []
    request = store.client._firestore_api.run_query.call_args.kwargs["request"]
    assert request["parent"].endswith(f"/documents/{BUSINESS}")
    assert request["structured_query"].start_at.values[0].reference_value.endswith(f"/{BUSINESS}/customers/private-customer")


def test_internal_lists_find_later_customers_and_keep_existing_name_order_and_exclusions():
    store = seed(501)
    store.put(f"{BUSINESS}/customers/customer-0250", {"name": "ZZZ late sort", "status": "active"})
    store.put(f"{BUSINESS}/customers/archived", {"name": "Archived", "status": "archived"})
    store.put(f"{BUSINESS}/customers/nameless", {"normalizedPhone": "94712345678"})
    records = list_customers(store.client, "business-a")
    assert len(records) == 501
    assert records[-1]["id"] == "customer-0250"
    assert [row["id"] for row in list_customers(store.client, "business-a", search="0500")] == ["customer-0500"]
    assert list_customers_page(store.client, "business-a", after="customer-0500")["customers"] == []


def test_exact_phone_lookup_keeps_normalization_limit_and_archived_match_behavior():
    store = seed(0)
    store.put(f"{BUSINESS}/customers/archived", {"name": "Old customer", "normalizedPhone": "94712345678", "status": "archived"})
    for load in (list_customers, list_customers_page):
        result = load(store.client, "business-a", phone="+94 71 234 5678", search="not matching")
        records = result["customers"] if isinstance(result, dict) else result
        assert [row["id"] for row in records] == ["archived"]
        request = store.client._firestore_api.run_query.call_args.kwargs["request"]
        assert request["structured_query"].limit == 1
        if isinstance(result, dict):
            assert result["hasMore"] is False and result["nextCursor"] is None


@pytest.mark.parametrize("load", [list_customers, list_customers_page])
def test_invalid_phone_retains_existing_validation_error(load):
    with pytest.raises(ApiError) as error:
        load(seed(0).client, "business-a", phone="123")
    assert error.value.code == "validation_error"


@pytest.fixture
def api(monkeypatch):
    store = seed(201)
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.customers.get_firestore_client", lambda: store.client)
    return create_app({"TESTING": True}).test_client(), store


def test_api_finds_later_matches_after_an_empty_page_and_ignores_forged_scope(api):
    client, _store = api
    path = "/api/v1/businesses/business-a/customers?search=0200&limit=99999&businessId=business-b"
    first = client.get(path, headers=HEADERS)
    assert first.status_code == 200
    page = first.get_json()
    assert page["customers"] == [] and page["hasMore"]
    last = client.get(f"{path}&after={page['nextCursor']}", headers=HEADERS).get_json()
    assert [row["id"] for row in last["customers"]] == ["customer-0200"]
    assert last["hasMore"] is False


def test_api_rechecks_membership_before_each_page(api):
    client, store = api
    first = client.get("/api/v1/businesses/business-a/customers", headers=HEADERS).get_json()
    assert len(first["customers"]) == 200
    store.put(MEMBER, {"role": "custom", "permissions": ["customers:read"], "status": "inactive"})
    response = client.get(f"/api/v1/businesses/business-a/customers?after={first['nextCursor']}", headers=HEADERS)
    assert response.status_code == 403
    assert "customers" not in response.get_json()


@pytest.mark.parametrize("headers, tenant, permissions, status", [
    ({}, "business-a", ["customers:read"], 401),
    (HEADERS, "business-b", ["customers:read"], 403),
    (HEADERS, "business-a", ["orders:read"], 403),
])
def test_api_pages_require_the_authenticated_tenant_and_customer_read_permission(api, headers, tenant, permissions, status):
    client, store = api
    store.put(MEMBER, {"role": "custom", "permissions": permissions, "status": "active"})
    response = client.get(f"/api/v1/businesses/{tenant}/customers?after=customer-0001&permissions=*", headers=headers)
    assert response.status_code == status
    assert "customers" not in response.get_json()
