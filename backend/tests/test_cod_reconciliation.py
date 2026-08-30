from datetime import datetime, timedelta, timezone

from app.services.cod_reconciliation_service import build_cod_reconciliation


def test_cod_reconciliation_calculates_partial_settlement_and_skips_ineligible_orders():
    now = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
    result = build_cod_reconciliation(
        [
            {
                "id": "o1", "orderNumber": "VD-1", "fulfilmentStatus": "delivered",
                "paymentMethod": "cod", "totalAmountMinor": 100000,
                "paidAmountMinor": 0, "updatedAt": now - timedelta(days=2),
                "customerSnapshot": {"name": "Nimal"},
                "courierSnapshot": {"name": "Koombiyo"},
            },
            {"id": "o2", "fulfilmentStatus": "packed", "paymentMethod": "cod", "totalAmountMinor": 50000},
            {"id": "o3", "fulfilmentStatus": "delivered", "paymentMethod": "paid", "totalAmountMinor": 50000},
        ],
        [{"orderId": "o1", "amountCollectedMinor": 100000, "courierChargeMinor": 10000, "receivedSettlementMinor": 60000}],
        now=now,
    )
    assert result["summary"]["orderCount"] == 1
    assert result["summary"]["expectedSettlementMinor"] == 90000
    assert result["summary"]["varianceMinor"] == -30000
    assert result["entries"][0]["status"] == "partial"


def test_cod_reconciliation_marks_old_unrecorded_orders_overdue():
    now = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
    result = build_cod_reconciliation([{
        "id": "o1", "fulfilmentStatus": "delivered", "paymentMethod": "deposit",
        "totalAmountMinor": 120000, "paidAmountMinor": 20000,
        "updatedAt": now - timedelta(days=10),
    }], now=now)
    assert result["entries"][0]["expectedCollectionMinor"] == 100000
    assert result["entries"][0]["expectedSettlementMinor"] == 100000
    assert result["entries"][0]["status"] == "unreconciled"
    assert result["entries"][0]["isOverdue"] is True
    assert result["summary"]["overdueCount"] == 1
