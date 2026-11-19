"""Verify bounded global search preserves results and reduces real SDK reads offline."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from firestore_memory import MemoryFirestore
from app.services.customer_service import list_customers
from app.services.order_service import list_orders
from app.services.product_service import list_products
from app.services.search_service import global_search, search_records

BUSINESS = "businesses/business-a"
OWNER = {"role": "owner"}


class CountingFirestore(MemoryFirestore):
    # Include the entire fetched batch in costs even when search stops consuming it early.
    def __init__(self):
        super().__init__()
        self.returned_rows = 0

    def query(self, request, **kwargs):
        for row in super().query(request, **kwargs):
            self.returned_rows += 1
            yield row


def seed(count, matches, *, tied=False):
    store = CountingFirestore()
    store.put(BUSINESS, {})
    for index in range(count):
        record_id = f"record-{index:04d}"
        name = "Same name" if tied else f"Record {index:04d}"
        match = "Needle" if index in matches else "Unrelated"
        store.put(f"{BUSINESS}/orders/{record_id}", {
            "orderNumber": f"VD-{index:06d}", "fulfilmentStatus": "needs-confirmation",
            "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=0 if tied else index),
            "customerSnapshot": {"name": name, "normalizedPhone": "94712345678"},
            "items": [{"name": match}],
        })
        store.put(f"{BUSINESS}/products/{record_id}", {
            "name": name, "status": "archived" if index == 0 else "active",
            "variantSummaries": [{"sku": f"SKU-{index}", "barcode": match}],
        })
        store.put(f"{BUSINESS}/customers/{record_id}", {
            "name": name, "email": f"{match.lower()}@example.test", "status": "active",
            "normalizedPhone": "94712345678",
        })
    for collection in ("orders", "products", "customers"):
        store.put(f"businesses/business-b/{collection}/private", {
            "name": "Needle", "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
        })
    return store


def complete_search(store, query):
    # Compare with the previous complete list scans, retaining the original projection/matching code.
    return search_records(
        list_orders(store.client, "business-a"), list_products(store.client, "business-a"),
        list_customers(store.client, "business-a"), query,
    )


@pytest.mark.parametrize("tied", [False, True])
def test_early_matches_preserve_eight_results_and_skip_later_batches(tied):
    store = seed(1001, set(range(1001)), tied=tied)
    expected = complete_search(store, "needle")
    assert store.returned_rows == 3003
    store.returned_rows = 0
    store.client._firestore_api.run_query.reset_mock()
    assert global_search(store.client, "business-a", "needle", OWNER) == expected
    assert all(len(rows) == 8 for rows in expected.values())
    assert store.returned_rows == 1500
    calls = store.client._firestore_api.run_query.call_args_list
    assert len(calls) == 3
    assert all(call.kwargs["request"]["parent"].endswith(f"/documents/{BUSINESS}") for call in calls)
    assert all(call.kwargs["request"]["structured_query"].limit == 500 for call in calls)


def test_sparse_matches_after_1000_remain_searchable_without_a_record_cap():
    store = seed(1008, set(range(1000, 1008)))
    expected = complete_search(store, "needle")
    store.returned_rows = 0
    store.client._firestore_api.run_query.reset_mock()
    assert global_search(store.client, "business-a", "needle", OWNER) == expected
    for rows in expected.values():
        assert [row["id"] for row in rows] == [f"record-{index:04d}" for index in range(1000, 1008)]
    assert store.returned_rows == 3024
    assert store.client._firestore_api.run_query.call_count == 9


def test_archived_customers_do_not_take_result_slots_but_archived_products_remain_searchable():
    store = seed(600, set(range(600)))
    for index in range(505):
        path = f"{BUSINESS}/customers/record-{index:04d}"
        store.put(path, {**store.documents[path], "status": "archived"})
    expected = complete_search(store, "needle")
    store.client._firestore_api.run_query.reset_mock()
    assert global_search(store.client, "business-a", "needle", OWNER) == expected
    assert [row["id"] for row in expected["customers"]] == [f"record-{index:04d}" for index in range(505, 513)]
    assert store.client._firestore_api.run_query.call_count == 4
    assert expected["products"][0]["id"] == "record-0000"


def test_no_matches_still_scans_to_the_end():
    store = seed(501, set())
    assert global_search(store.client, "business-a", "needle", OWNER) == {"orders": [], "products": [], "customers": []}
    assert store.returned_rows == 1503
    assert store.client._firestore_api.run_query.call_count == 6


@pytest.mark.parametrize("query", ["", "a", "  ", "\x00\x1f", "<b></b>", " <b>x</b> "])
def test_empty_or_short_sanitized_queries_do_not_read_business_data(query):
    database = Mock()
    assert global_search(database, "business-a", query, OWNER) == {"orders": [], "products": [], "customers": []}
    database.collection.assert_not_called()


def test_casefold_expansion_and_markup_preserve_matches():
    store = seed(2, set())
    path = f"{BUSINESS}/customers/record-0000"
    store.put(path, {**store.documents[path], "name": "Straße"})
    for query in ("ß", "<b>Straße</b>"):
        assert global_search(store.client, "business-a", query, OWNER) == complete_search(store, query)
    assert global_search(store.client, "business-a", "ß", OWNER)["customers"][0]["id"] == "record-0000"


def test_lazy_search_does_not_consume_records_after_eight_matches():
    def records():
        for index in range(8):
            yield {"id": str(index), "name": "Needle", "orderNumber": "Needle"}
        raise AssertionError("Read past the existing result limit")

    assert all(len(rows) == 8 for rows in search_records(records(), records(), records(), "needle").values())
