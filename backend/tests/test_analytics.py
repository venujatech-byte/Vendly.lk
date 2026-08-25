from datetime import datetime, timezone

from app.services.analytics_service import calculate_analytics, recent_months


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
