from datetime import datetime, timezone

from app.services.analytics_service import calculate_analytics, recent_months


def test_analytics_uses_only_delivered_orders_for_revenue_and_profit():
    now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
    analytics = calculate_analytics(
        [
            {
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


def test_recent_months_crosses_year_boundary():
    months = recent_months(datetime(2026, 2, 1, tzinfo=timezone.utc), count=4)
    assert months == ["2025-11", "2025-12", "2026-01", "2026-02"]
