"""Exercise complete financial scans through real Firestore SDK cursors and offline RPCs."""

from datetime import datetime, timezone

import pytest

from firestore_memory import MemoryFirestore
from app.services.analytics_service import (
    REPORT_BATCH_SIZE, get_business_analytics, get_business_ledger, stream_report_snapshots,
)
from app.services.cod_reconciliation_service import get_cod_reconciliation


BUSINESS = "businesses/business-a"
CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def store_for_report():
    store = MemoryFirestore()
    store.put(BUSINESS, {})
    return store


def order():
    return {
        "createdAt": CREATED_AT, "fulfilmentStatus": "delivered", "paymentMethod": "cod",
        "subtotalMinor": 100, "totalAmountMinor": 100, "balanceAmountMinor": 100,
        "items": [{"productId": "product-a", "quantity": 1, "unitCostMinor": 25, "lineTotalMinor": 100}],
    }


def assert_bounded_snapshot_reads(store):
    # Every financial query must keep the same server read time and remain inside the requested tenant.
    requests = [call.kwargs["request"] for call in store.client._firestore_api.run_query.call_args_list]
    financial = [request for request in requests if request["structured_query"].from_[0].collection_id != "notifications"]
    assert financial
    assert len({request["read_time"] for request in financial}) == 1
    assert all(request["structured_query"].limit == REPORT_BATCH_SIZE for request in financial)
    assert all(request["parent"].endswith(f"/documents/{BUSINESS}") for request in financial)
    assert all(not request["structured_query"].offset for request in financial)


@pytest.mark.parametrize("count", [0, 499, 500, 501, 1000])
@pytest.mark.parametrize("ordered", [False, True])
def test_report_scans_cover_exact_page_boundaries_and_equal_timestamps(count, ordered):
    store = store_for_report()
    # Insert in reverse order so transport insertion order cannot substitute for server ordering.
    for index in reversed(range(count)):
        store.put(f"{BUSINESS}/orders/order-{index:04d}", order())
    store.put("businesses/business-b/orders/private-order", order())
    store.put(f"{BUSINESS}/orders/order-0000/events/private-event", {"createdAt": CREATED_AT})
    read_time = store.client.document(BUSINESS).get().read_time
    query = store.client.document(BUSINESS).collection("orders")
    if ordered:
        query = query.order_by("createdAt", direction="DESCENDING")
    rows = list(stream_report_snapshots(query, read_time))
    expected = [f"order-{index:04d}" for index in range(count)]
    assert [row.id for row in rows] == (list(reversed(expected)) if ordered else expected)
    assert len({row.id for row in rows}) == count
    assert_bounded_snapshot_reads(store)


def test_analytics_includes_every_financial_dataset_above_1000_records():
    store = store_for_report()
    count = 1001
    for index in range(count):
        record_id = f"record-{index:04d}"
        store.put(f"{BUSINESS}/orders/{record_id}", order())
        store.put(f"{BUSINESS}/products/{record_id}", {"availableStock": 2, "costPriceMinor": 25})
        store.put(f"{BUSINESS}/customers/{record_id}", {"name": "Synthetic customer", "createdAt": CREATED_AT})
        store.put(f"{BUSINESS}/warrantyClaims/{record_id}", {"sourceType": "online-order", "revenueImpactMinor": 1})
        store.put(f"{BUSINESS}/shopSales/{record_id}", {**order(), "status": "completed"})
    store.put("businesses/business-b/orders/private-order", {**order(), "subtotalMinor": 999999})
    result = get_business_analytics(store.client, "business-a")
    assert result["orderCounts"]["all"] == count
    assert result["inventory"]["productCount"] == count
    assert result["inventory"]["totalUnits"] == count * 2
    assert result["customers"]["total"] == count
    assert result["financials"]["productRevenueMinor"] == count * 99
    assert result["financials"]["costOfGoodsMinor"] == count * 25
    assert result["financials"]["grossProfitMinor"] == count * 74
    shop = next(channel for channel in result["salesChannels"]["channels"] if channel["id"] == "shop")
    assert shop["saleCount"] == count
    assert shop["productRevenueMinor"] == count * 100
    assert_bounded_snapshot_reads(store)


def test_ledger_includes_sources_above_both_former_limits():
    store = store_for_report()
    for index in range(1001):
        record_id = f"record-{index:04d}"
        store.put(f"{BUSINESS}/orders/{record_id}", order())
        store.put(f"{BUSINESS}/shopSales/{record_id}", {**order(), "status": "completed"})
        store.put(f"{BUSINESS}/warrantyClaims/{record_id}", {"revenueImpactMinor": 3, "createdAt": CREATED_AT})
    for index in range(2001):
        record_id = f"record-{index:04d}"
        store.put(f"{BUSINESS}/inventoryTransactions/{record_id}", {
            "quantity": 1, "totalCostMinor": 5, "ledgerImpact": "inventory-debit", "createdAt": CREATED_AT,
        })
        store.put(f"{BUSINESS}/ledgerEntries/{record_id}", {
            "direction": "debit", "amountMinor": 7, "createdAt": CREATED_AT,
        })
    result = get_business_ledger(store.client, "business-a")
    assert result["summary"] == {
        "transactionCount": 1001 * 3 + 2001 * 2,
        "creditMinor": 1001 * 200,
        "debitMinor": 1001 * 3 + 2001 * 12,
        "netMinor": 1001 * 200 - 1001 * 3 - 2001 * 12,
    }
    assert len({entry["id"] for entry in result["entries"]}) == result["summary"]["transactionCount"]
    assert result["entries"][0]["balanceMinor"] == result["summary"]["netMinor"]
    assert_bounded_snapshot_reads(store)


def test_reconciliation_matches_orders_and_settlements_beyond_2000_records():
    store = store_for_report()
    count = 2001
    for index in range(count):
        record_id = f"record-{index:04d}"
        store.put(f"{BUSINESS}/orders/{record_id}", order())
        store.put(f"{BUSINESS}/codSettlements/{record_id}", {
            "orderId": record_id, "amountCollectedMinor": 100,
            "courierChargeMinor": 10, "receivedSettlementMinor": 90,
        })
    result = get_cod_reconciliation(store.client, "business-a")
    assert result["summary"]["orderCount"] == count
    assert result["summary"]["expectedCollectionMinor"] == count * 100
    assert result["summary"]["courierChargesMinor"] == count * 10
    assert result["summary"]["receivedSettlementMinor"] == count * 90
    assert result["summary"]["varianceMinor"] == 0
    assert all(entry["status"] == "reconciled" for entry in result["entries"])
    assert_bounded_snapshot_reads(store)


@pytest.mark.parametrize("report", [get_business_analytics, get_business_ledger, get_cod_reconciliation])
def test_concurrent_changes_cannot_move_records_between_report_pages(report):
    store = store_for_report()
    for index in range(501):
        store.put(f"{BUSINESS}/orders/order-{index:04d}", order())
    query = store.query
    changed = False

    def concurrent_query(request, **kwargs):
        nonlocal changed
        if request["structured_query"].start_at.values and not changed:
            changed = True
            # Change amounts/order dates and delete/create rows while a report is between pages.
            store.put(f"{BUSINESS}/orders/order-0500", {
                **order(), "createdAt": datetime(2027, 1, 1, tzinfo=timezone.utc),
                "subtotalMinor": 999999, "totalAmountMinor": 999999,
            })
            del store.documents[f"{BUSINESS}/orders/order-0000"]
            store.put(f"{BUSINESS}/orders/zz-new-order", order())
            store.put(f"{BUSINESS}/codSettlements/order-0500", {"orderId": "order-0500", "courierChargeMinor": 100})
        return query(request, **kwargs)

    store.client._firestore_api.run_query.side_effect = concurrent_query
    result = report(store.client, "business-a")
    assert changed
    if report is get_business_analytics:
        assert result["orderCounts"]["all"] == 501
        assert result["financials"]["productRevenueMinor"] == 50100
    elif report is get_business_ledger:
        assert result["summary"]["transactionCount"] == 501
        assert result["summary"]["creditMinor"] == 50100
    else:
        assert result["summary"]["orderCount"] == 501
        assert result["summary"]["expectedCollectionMinor"] == 50100
        assert result["summary"]["courierChargesMinor"] == 0
    assert_bounded_snapshot_reads(store)


def test_later_page_failure_does_not_return_a_partial_financial_report():
    store = store_for_report()
    for index in range(501):
        store.put(f"{BUSINESS}/orders/order-{index:04d}", order())
    query = store.query

    def failed_page(request, **kwargs):
        if request["structured_query"].start_at.values:
            raise RuntimeError("Synthetic page failure")
        return query(request, **kwargs)

    store.client._firestore_api.run_query.side_effect = failed_page
    with pytest.raises(RuntimeError, match="Synthetic page failure"):
        get_business_ledger(store.client, "business-a")
