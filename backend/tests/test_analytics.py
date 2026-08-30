from datetime import datetime, timezone

from app.services.analytics_service import (
    build_customer_profitability_report,
    build_dead_stock_report,
    build_sales_channel_report,
    build_sales_forecast_report,
    build_transaction_ledger,
    calculate_analytics,
    recent_months,
)


def test_sales_forecast_uses_completed_months_and_recognized_sales_only():
    report = build_sales_forecast_report(
        [
            {"fulfilmentStatus": "delivered", "createdAt": "2026-05-10T10:00:00Z", "subtotalMinor": 100000, "items": []},
            {"fulfilmentStatus": "delivered", "createdAt": "2026-06-10T10:00:00Z", "subtotalMinor": 200000, "items": []},
            {"fulfilmentStatus": "delivered", "createdAt": "2026-07-10T10:00:00Z", "subtotalMinor": 300000, "items": []},
            {"fulfilmentStatus": "packed", "createdAt": "2026-07-11T10:00:00Z", "subtotalMinor": 900000, "items": []},
            {"fulfilmentStatus": "delivered", "createdAt": "2026-08-15T10:00:00Z", "subtotalMinor": 150000, "items": []},
        ],
        [
            {"status": "completed", "createdAt": "2026-07-12T10:00:00Z", "subtotalMinor": 60000, "items": []},
            {"status": "voided", "createdAt": "2026-07-13T10:00:00Z", "subtotalMinor": 800000, "items": []},
        ],
        now=datetime(2026, 8, 15, 12, tzinfo=timezone.utc),
    )

    summary = report["summary"]
    assert summary["nextMonthForecastMinor"] == 263333
    assert summary["suggestedTargetMinor"] == 289667
    assert summary["currentMonthRevenueMinor"] == 150000
    assert summary["currentMonthRunRateMinor"] == 310000
    assert summary["trendPercent"] == 80.0
    assert summary["confidence"] == "medium"
    assert report["history"][-1]["isCurrentMonth"] is True


def test_sales_forecast_tracks_a_saved_monthly_target_separately():
    report = build_sales_forecast_report(
        [{
            "fulfilmentStatus": "delivered",
            "createdAt": "2026-08-15T10:00:00Z",
            "subtotalMinor": 150000,
            "items": [],
        }],
        [],
        now=datetime(2026, 8, 15, 12, tzinfo=timezone.utc),
        monthly_target_minor=500000,
    )

    summary = report["summary"]
    assert summary["monthlyTargetMinor"] == 500000
    assert summary["activeTargetMinor"] == 500000
    assert summary["targetSource"] == "seller"
    assert summary["targetProgressPercent"] == 30.0
    assert summary["targetGapMinor"] == 350000


def test_sales_channel_report_compares_recognized_online_and_shop_sales():
    report = build_sales_channel_report(
        [
            {
                "fulfilmentStatus": "delivered", "createdAt": "2026-08-10T10:00:00Z",
                "subtotalMinor": 200000, "discountTotalMinor": 20000,
                "items": [{"quantity": 2, "unitCostMinor": 50000}],
            },
            {
                "fulfilmentStatus": "packed", "createdAt": "2026-08-11T10:00:00Z",
                "subtotalMinor": 900000,
            },
        ],
        [
            {
                "status": "completed", "createdAt": "2026-08-12T10:00:00Z",
                "subtotalMinor": 100000, "discountTotalMinor": 0,
                "items": [{"quantity": 1, "unitCostMinor": 40000}],
            },
            {
                "status": "voided", "createdAt": "2026-08-13T10:00:00Z",
                "subtotalMinor": 800000,
            },
        ],
        now=datetime(2026, 8, 30, 12, tzinfo=timezone.utc),
    )

    channels = {channel["id"]: channel for channel in report["channels"]}
    assert channels["online"]["saleCount"] == 1
    assert channels["online"]["unitsSold"] == 2
    assert channels["online"]["productRevenueMinor"] == 180000
    assert channels["online"]["grossProfitMinor"] == 80000
    assert channels["shop"]["saleCount"] == 1
    assert channels["shop"]["productRevenueMinor"] == 100000
    assert channels["shop"]["grossProfitMinor"] == 60000
    assert report["summary"] == {
        "saleCount": 2,
        "unitsSold": 3,
        "productRevenueMinor": 280000,
        "grossProfitMinor": 140000,
        "grossMarginPercent": 50.0,
        "strongestChannel": "Online orders",
    }


def test_customer_profitability_uses_delivered_sales_and_tracks_returns():
    report = build_customer_profitability_report(
        [
            {"id": "c1", "name": "Nimali", "normalizedPhone": "94771234567",
             "email": "nimali@example.com"},
            {"id": "c2", "name": "Kamal", "normalizedPhone": "94770000000"},
        ],
        [
            {
                "id": "o1", "customerId": "c1", "fulfilmentStatus": "delivered",
                "createdAt": "2026-08-20T10:00:00Z", "subtotalMinor": 200000,
                "discountTotalMinor": 20000,
                "items": [{"quantity": 2, "unitCostMinor": 50000}],
            },
            {
                "id": "o2", "customerId": "c1", "fulfilmentStatus": "returned",
                "createdAt": "2026-08-22T10:00:00Z", "subtotalMinor": 100000,
                "items": [{"quantity": 1, "unitCostMinor": 50000}],
            },
            {
                "id": "o3", "customerId": "c1", "fulfilmentStatus": "cancelled",
                "createdAt": "2026-08-23T10:00:00Z", "subtotalMinor": 900000,
            },
        ],
    )

    nimali = next(row for row in report["customers"] if row["id"] == "c1")
    assert nimali["orderCount"] == 2
    assert nimali["deliveredOrderCount"] == 1
    assert nimali["returnedOrderCount"] == 1
    assert nimali["productRevenueMinor"] == 180000
    assert nimali["discountTotalMinor"] == 20000
    assert nimali["costOfGoodsMinor"] == 100000
    assert nimali["grossProfitMinor"] == 80000
    assert nimali["grossMarginPercent"] == 44.4
    assert nimali["returnRatePercent"] == 50
    assert nimali["isHighReturn"] is True
    assert nimali["profitabilityState"] == "profitable"

    kamal = next(row for row in report["customers"] if row["id"] == "c2")
    assert kamal["profitabilityState"] == "no-sales"
    assert report["summary"] == {
        "customerCount": 2,
        "productRevenueMinor": 180000,
        "grossProfitMinor": 80000,
        "profitableCustomerCount": 1,
        "highReturnCustomerCount": 1,
    }


def test_dead_stock_report_includes_never_sold_and_old_stock_only():
    now = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
    products = [
        {"id": "never", "name": "Never sold", "status": "active", "availableStock": 4,
         "costPriceMinor": 5000, "sellingPriceMinor": 10000, "categoryName": "Audio"},
        {"id": "old", "name": "Old stock", "status": "active", "availableStock": 2,
         "costPriceMinor": 10000, "sellingPriceMinor": 20000},
        {"id": "recent", "name": "Recent", "status": "active", "availableStock": 5,
         "costPriceMinor": 10000, "sellingPriceMinor": 20000},
        {"id": "empty", "name": "Empty", "status": "active", "availableStock": 0},
    ]
    orders = [
        {"fulfilmentStatus": "delivered", "createdAt": "2026-05-01T12:00:00Z",
         "items": [{"productId": "old", "quantity": 1}]},
        {"fulfilmentStatus": "delivered", "createdAt": "2026-08-20T12:00:00Z",
         "items": [{"productId": "recent", "quantity": 2}]},
        {"fulfilmentStatus": "returned", "createdAt": "2026-08-25T12:00:00Z",
         "items": [{"productId": "old", "quantity": 10}]},
    ]

    report = build_dead_stock_report(products, orders, now=now)

    assert {item["id"] for item in report["products"]} == {"never", "old"}
    assert report["summary"] == {
        "productCount": 2,
        "stockUnits": 6,
        "tiedUpCostMinor": 40000,
        "neverSoldCount": 1,
    }
    old = next(item for item in report["products"] if item["id"] == "old")
    assert old["daysSinceLastSale"] == 121
    assert old["unitsSoldLast90Days"] == 0


def test_dead_stock_report_uses_variant_weighted_cost():
    report = build_dead_stock_report(
        [{"id": "p1", "name": "Shoes", "status": "active", "availableStock": 3,
          "sellingPriceMinor": 30000, "variantSummaries": [
              {"stockAvailable": 1, "costPriceMinor": 10000},
              {"stockAvailable": 2, "costPriceMinor": 16000},
          ]}],
        [],
        now=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    product = report["products"][0]
    assert product["unitCostMinor"] == 14000
    assert product["tiedUpCostMinor"] == 42000


def test_analytics_uses_only_delivered_orders_for_revenue_and_profit():
    now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
    analytics = calculate_analytics(
        [
            {
                "id": "order-1",
                "orderNumber": "VD-000001",
                "fulfilmentStatus": "delivered",
                "createdAt": now,
                "subtotalMinor": 200000,
                "discountTotalMinor": 10000,
                "totalAmountMinor": 235000,
                "items": [
                    {
                        "productId": "p1",
                        "name": "Watch",
                        "quantity": 2,
                        "unitCostMinor": 50000,
                        "lineTotalMinor": 200000,
                    },
                ],
            },
            {
                "fulfilmentStatus": "returned",
                "createdAt": now,
                "subtotalMinor": 500000,
                "totalAmountMinor": 545000,
                "items": [],
            },
        ],
        [],
        now=now,
    )

    assert analytics["financials"]["productRevenueMinor"] == 190000
    assert analytics["financials"]["costOfGoodsMinor"] == 100000
    assert analytics["financials"]["grossProfitMinor"] == 90000
    assert analytics["orderCounts"]["returned"] == 1
    assert analytics["topProducts"][0]["quantity"] == 2
    assert analytics["topProducts"][0]["revenueMinor"] == 190000
    assert analytics["productProfitability"][0] == {
        "id": "p1",
        "name": "Watch",
        "quantity": 2,
        "revenueMinor": 190000,
        "costOfGoodsMinor": 100000,
        "grossProfitMinor": 90000,
        "warrantyDeductionsMinor": 0,
        "grossMarginPercent": 47.4,
    }
    assert analytics["performance"]["ordersToday"] == 2
    assert analytics["performance"]["deliverySuccessPercent"] == 50
    assert analytics["performance"]["returnRatePercent"] == 50
    assert analytics["performance"]["grossMarginPercent"] == 47.4
    assert analytics["recentOrders"][0]["orderNumber"] == "VD-000001"


def test_recent_months_crosses_year_boundary():
    months = recent_months(datetime(2026, 2, 1, tzinfo=timezone.utc), count=4)
    assert months == ["2025-11", "2025-12", "2026-01", "2026-02"]


def test_warranty_claims_reduce_revenue_only_by_the_saved_claim_impact():
    now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
    analytics = calculate_analytics(
        [{"fulfilmentStatus": "delivered", "createdAt": now, "subtotalMinor": 50000,
          "discountTotalMinor": 0, "items": []}], [], now=now,
        warranty_claims=[
            {"claimType": "supplier-warranty", "revenueImpactMinor": 0, "sourceType": "online-order", "status": "open"},
            {"claimType": "shop-warranty", "revenueImpactMinor": 20000, "sourceType": "online-order", "status": "open"},
            {"claimType": "shop-repair", "revenueImpactMinor": 5000, "sourceType": "online-order", "status": "open"},
            {"claimType": "shop-warranty", "revenueImpactMinor": 9000, "sourceType": "online-order", "status": "cancelled"},
        ],
    )
    assert analytics["financials"]["warrantyDeductionsMinor"] == 25000
    assert analytics["financials"]["productRevenueMinor"] == 25000


def test_product_profitability_allocates_discount_and_product_warranty_cost():
    now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
    analytics = calculate_analytics(
        [{
            "fulfilmentStatus": "delivered",
            "createdAt": now,
            "subtotalMinor": 30000,
            "discountTotalMinor": 3000,
            "items": [
                {"productId": "p1", "name": "Watch", "quantity": 1,
                 "lineTotalMinor": 20000, "unitCostMinor": 10000},
                {"productId": "p2", "name": "Cable", "quantity": 1,
                 "lineTotalMinor": 10000, "unitCostMinor": 4000},
            ],
        }],
        [],
        now=now,
        warranty_claims=[{
            "sourceType": "online-order",
            "status": "open",
            "revenueImpactMinor": 2000,
            "item": {"productId": "p1", "name": "Watch"},
        }],
    )

    rows = {item["id"]: item for item in analytics["productProfitability"]}
    assert rows["p1"]["revenueMinor"] == 16000
    assert rows["p1"]["grossProfitMinor"] == 6000
    assert rows["p1"]["warrantyDeductionsMinor"] == 2000
    assert rows["p2"]["revenueMinor"] == 9000
    assert rows["p2"]["grossProfitMinor"] == 5000


def test_transaction_ledger_combines_sales_reversals_and_warranty_adjustments():
    created = datetime(2026, 8, 17, 9, tzinfo=timezone.utc)
    returned = datetime(2026, 8, 18, 9, tzinfo=timezone.utc)
    ledger = build_transaction_ledger(
        [
            {
                "id": "order-1",
                "orderNumber": "VD-000001",
                "fulfilmentStatus": "returned",
                "totalAmountMinor": 250000,
                "paymentMethod": "cod",
                "customerSnapshot": {"name": "Nimal"},
                "items": [{"name": "Watch"}],
                "createdAt": created,
                "statusHistory": [{"to": "returned", "changedAt": returned}],
            },
        ],
        [
            {
                "id": "sale-1",
                "saleNumber": "SHOP-000001",
                "status": "completed",
                "totalAmountMinor": 100000,
                "paymentMethod": "cash",
                "items": [{"name": "Earbuds"}],
                "createdAt": created,
            },
        ],
        [
            {
                "id": "claim-1",
                "claimNumber": "WC-000001",
                "sourceType": "online-order",
                "revenueImpactMinor": 20000,
                "item": {"name": "Watch"},
                "createdAt": returned,
            },
        ],
    )

    assert ledger["summary"] == {
        "transactionCount": 4,
        "creditMinor": 350000,
        "debitMinor": 270000,
        "netMinor": 80000,
    }
    assert ledger["entries"][0]["direction"] == "debit"
    assert ledger["entries"][-1]["balanceMinor"] in {250000, 350000}


def test_transaction_ledger_debits_only_costed_positive_inventory_additions():
    created = datetime(2026, 8, 19, 9, tzinfo=timezone.utc)
    ledger = build_transaction_ledger(
        [],
        [],
        [],
        [
            {
                "id": "stock-in-1",
                "productName": "Smart Watch",
                "variantSku": "WATCH-BLK",
                "quantity": 4,
                "unitCostMinor": 120000,
                "totalCostMinor": 480000,
                "ledgerImpact": "inventory-debit",
                "reference": "Supplier invoice INV-10",
                "createdAt": created,
            },
            {
                "id": "stock-out-1",
                "productName": "Smart Watch",
                "quantity": -1,
                "totalCostMinor": 0,
                "ledgerImpact": "none",
                "createdAt": created,
            },
        ],
    )

    assert ledger["summary"] == {
        "transactionCount": 1,
        "creditMinor": 0,
        "debitMinor": 480000,
        "netMinor": -480000,
    }
    entry = ledger["entries"][0]
    assert entry["transactionType"] == "inventory-purchase"
    assert entry["direction"] == "debit"
    assert entry["description"] == "Smart Watch · WATCH-BLK · 4 unit(s)"
