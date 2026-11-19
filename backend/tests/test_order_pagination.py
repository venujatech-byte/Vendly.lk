"""Verify bounded order API pages and complete internal lists through real SDK cursors."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import Mock

import pytest

from firestore_memory import MemoryFirestore
from app import create_app
from app.core.errors import ApiError
from app.services import operations_service
from app.services.order_service import ORDER_PAGE_SIZE, list_orders, list_orders_page


BUSINESS = "businesses/business-a"
MEMBER = f"{BUSINESS}/members/member-a"
HEADERS = {"Authorization": "Bearer synthetic-token"}


def order(index, tied=False):
    return {
        "orderNumber": f"ORD-{index:04d}",
        "createdAt": datetime(2025, 1, 1, 20, tzinfo=timezone.utc) + timedelta(days=0 if tied else index),
        "fulfilmentStatus": "confirmed" if index == 0 else "packed",
        "courierId": "courier-old" if index == 0 else "courier-new",
        "customerSnapshot": {"name": "Archived customer" if index == 0 else "Current customer"},
        "items": [],
    }


def seed(count, tied=False):
    store = MemoryFirestore()
    store.put(BUSINESS, {})
    store.put(MEMBER, {"role": "custom", "permissions": ["orders:read"], "status": "active"})
    for index in range(count):
        store.put(f"{BUSINESS}/orders/order-{index:04d}", order(index, tied))
    store.put("businesses/business-b/orders/private-order", order(0))
    return store


@pytest.mark.parametrize("count", [0, 199, 200, 201, 400, 401])
def test_pages_are_bounded_and_equal_timestamps_never_skip_or_repeat_orders(count):
    store = seed(count, tied=True)
    ids = []
    cursor = None
    while True:
        page = list_orders_page(store.client, "business-a", after=cursor)
        assert len(page["orders"]) <= ORDER_PAGE_SIZE
        ids.extend(row["id"] for row in page["orders"])
        if not page["hasMore"]:
            assert page["nextCursor"] is None
            break
        assert page["nextCursor"] != cursor
        cursor = page["nextCursor"]
    assert ids == [f"order-{index:04d}" for index in reversed(range(count))]
    assert len(set(ids)) == count
    requests = [call.kwargs["request"] for call in store.client._firestore_api.run_query.call_args_list]
    assert all(request["structured_query"].limit == ORDER_PAGE_SIZE for request in requests)
    assert all(request["parent"].endswith(f"/documents/{BUSINESS}") for request in requests)


def test_sparse_filters_continue_past_empty_pages_to_find_old_orders():
    store = seed(401)
    filters = {"status": "confirmed", "courier_id": "courier-old", "search": "archiv",
               "date_from": "2025-01-02", "date_to": "2025-01-02"}
    first = list_orders_page(store.client, "business-a", **filters)
    assert first["orders"] == [] and first["hasMore"]
    second = list_orders_page(store.client, "business-a", after=first["nextCursor"], **filters)
    assert second["orders"] == [] and second["hasMore"]
    last = list_orders_page(store.client, "business-a", after=second["nextCursor"], **filters)
    assert [item["id"] for item in last["orders"]] == ["order-0000"]
    assert last["hasMore"] is False


@pytest.mark.parametrize("cursor", ["private-order", "missing", "../business-b/orders/private-order", "a/b", ".", "..", "__reserved__", "x" * 1501])
def test_invalid_and_foreign_cursors_fail_instead_of_resetting_or_crossing_tenants(cursor):
    store = seed(1)
    with pytest.raises(ApiError) as error:
        list_orders_page(store.client, "business-a", after=cursor)
    assert error.value.code == "invalid_order_cursor"
    assert error.value.status_code == 422


def test_deleted_cursor_fails_instead_of_returning_a_silently_incomplete_list():
    store = seed(201)
    first = list_orders_page(store.client, "business-a")
    del store.documents[f"{BUSINESS}/orders/{first['nextCursor']}"]
    with pytest.raises(ApiError) as error:
        list_orders_page(store.client, "business-a", after=first["nextCursor"])
    assert error.value.code == "invalid_order_cursor"


def test_internal_lists_and_selected_exports_include_orders_beyond_200(monkeypatch):
    store = seed(501)
    records = list_orders(store.client, "business-a")
    assert isinstance(records, list)
    assert len(records) == 501
    assert records[-1]["id"] == "order-0000"
    # Keep the real order loader in the export path; mock only the workbook/template boundary.
    monkeypatch.setattr(operations_service, "get_courier_export_template", Mock(return_value={"content": b"synthetic-template"}))
    workbook = Mock(return_value=BytesIO())
    monkeypatch.setattr(operations_service, "build_orders_workbook", workbook)
    operations_service.export_orders(
        store.client, "business-a", courier_id="courier-old", order_ids=["order-0000"],
    )
    assert [row["id"] for row in workbook.call_args.args[0]] == ["order-0000"]


@pytest.fixture
def api(monkeypatch):
    # Keep actual route authentication and tenant/module checks, with no Firebase/cloud access.
    store = seed(201)
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.orders.get_firestore_client", lambda: store.client)
    return create_app({"TESTING": True}).test_client(), store


def test_api_returns_continuation_and_rechecks_revoked_access_on_the_next_page(api):
    client, store = api
    first = client.get("/api/v1/businesses/business-a/orders?limit=99999&businessId=business-b", headers=HEADERS)
    assert first.status_code == 200
    data = first.get_json()
    assert len(data["orders"]) == 200
    assert data["hasMore"] is True
    store.put(MEMBER, {"role": "custom", "permissions": ["orders:read"], "status": "inactive"})
    response = client.get(f"/api/v1/businesses/business-a/orders?after={data['nextCursor']}", headers=HEADERS)
    assert response.status_code == 403
    assert "orders" not in response.get_json()


def test_api_continues_filtered_empty_pages_to_return_the_old_matching_order(api):
    client, _store = api
    path = "/api/v1/businesses/business-a/orders?status=confirmed&search=archiv&courierId=courier-old&dateFrom=2025-01-02&dateTo=2025-01-02"
    first = client.get(path, headers=HEADERS).get_json()
    assert first["orders"] == []
    assert first["hasMore"] is True
    response = client.get(f"{path}&after={first['nextCursor']}", headers=HEADERS)
    assert response.status_code == 200
    last = response.get_json()
    assert [row["id"] for row in last["orders"]] == ["order-0000"]
    assert last["hasMore"] is False


@pytest.mark.parametrize("headers, tenant, permissions, expected", [
    ({}, "business-a", ["orders:read"], 401),
    (HEADERS, "business-b", ["orders:read"], 403),
    (HEADERS, "business-a", ["inventory:read"], 403),
])
def test_api_pages_require_authenticated_tenant_order_read_access(api, headers, tenant, permissions, expected):
    client, store = api
    store.put(MEMBER, {"role": "custom", "permissions": permissions, "status": "active"})
    response = client.get(f"/api/v1/businesses/{tenant}/orders?after=order-0001&permissions=*", headers=headers)
    assert response.status_code == expected
    assert "orders" not in response.get_json()
