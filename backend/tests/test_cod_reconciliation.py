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


def test_update_bulk_cod_settlements_records_multiple_orders(monkeypatch):
    from unittest.mock import MagicMock
    from app.services.cod_reconciliation_service import update_bulk_cod_settlements

    mock_db = MagicMock()
    mock_batch = MagicMock()
    mock_db.batch.return_value = mock_batch

    # Mock order snapshots
    o1_snap = MagicMock()
    o1_snap.exists = True
    o1_snap.id = "o1"
    o1_snap.to_dict.return_value = {
        "orderNumber": "VD-1",
        "fulfilmentStatus": "delivered",
        "paymentMethod": "cod",
        "totalAmountMinor": 500000,
        "paidAmountMinor": 0,
        "balanceAmountMinor": 500000,
    }

    o2_snap = MagicMock()
    o2_snap.exists = True
    o2_snap.id = "o2"
    o2_snap.to_dict.return_value = {
        "orderNumber": "VD-2",
        "fulfilmentStatus": "delivered",
        "paymentMethod": "cod",
        "totalAmountMinor": 300000,
        "paidAmountMinor": 0,
        "balanceAmountMinor": 300000,
    }

    def mock_doc(doc_id):
        m = MagicMock()
        if doc_id == "o1":
            m.get.return_value = o1_snap
        elif doc_id == "o2":
            m.get.return_value = o2_snap
        return m

    mock_orders_coll = MagicMock()
    mock_orders_coll.document.side_effect = mock_doc
    mock_orders_coll.limit.return_value.stream.return_value = [o1_snap, o2_snap]

    mock_settlements_coll = MagicMock()
    mock_settlements_coll.limit.return_value.stream.return_value = []

    def mock_coll(name):
        if name == "orders":
            return mock_orders_coll
        if name == "codSettlements":
            return mock_settlements_coll
        return MagicMock()

    mock_biz_doc = MagicMock()
    mock_biz_doc.collection.side_effect = mock_coll
    mock_db.collection.return_value.document.return_value = mock_biz_doc

    result = update_bulk_cod_settlements(
        mock_db,
        "biz_1",
        {
            "orderIds": ["o1", "o2"],
            "settlementData": {
                "settlementDate": "2026-09-13",
                "settlementReference": "BATCH-001",
                "autoFullSettlement": True,
                "courierChargeMinor": 35000,
            },
        },
        "user_1",
    )

    assert mock_batch.set.call_count == 2
    assert mock_batch.commit.call_count == 1
    assert "summary" in result

