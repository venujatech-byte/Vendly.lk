import pytest
from app.services.inventory_batches import (
    add_fifo_batch,
    consume_fifo_batches,
    get_active_unit_cost,
    normalize_batches,
)


def test_fifo_batches_consume_oldest_stock_first_and_switch_price():
    # Initial batch: 5 units @ LKR 1,000 (100,000 cents)
    batches = [
        {"batchId": "b1", "quantity": 5, "unitCostMinor": 100000},
    ]

    # Add new stock batch: 10 units @ LKR 1,500 (150,000 cents)
    batches = add_fifo_batch(batches, 10, 150000)
    assert len(batches) == 2
    assert batches[0]["quantity"] == 5
    assert batches[0]["unitCostMinor"] == 100000
    assert batches[1]["quantity"] == 10
    assert batches[1]["unitCostMinor"] == 150000

    # Active cost is still old stock (100,000)
    assert get_active_unit_cost(batches) == 100000

    # Sale 1: Order for 3 units -> takes from batch 1 @ 1,000
    batches, total_cost, weighted_cost, active_cost = consume_fifo_batches(batches, 3)
    assert total_cost == 300000  # 3 * 100,000
    assert weighted_cost == 100000
    assert active_cost == 100000  # batch 1 still has 2 units remaining
    assert len(batches) == 2
    assert batches[0]["quantity"] == 2

    # Sale 2: Order for 4 units -> 2 from batch 1 @ 1,000 + 2 from batch 2 @ 1,500
    batches, total_cost, weighted_cost, active_cost = consume_fifo_batches(batches, 4)
    assert total_cost == (2 * 100000) + (2 * 150000)  # 200,000 + 300,000 = 500,000
    assert weighted_cost == 125000  # 500,000 // 4 = 125,000 (LKR 1,250)
    # Batch 1 is now completely finished! Active cost automatically shifts to new stock (150,000)
    assert active_cost == 150000
    assert len(batches) == 1
    assert batches[0]["quantity"] == 8
    assert batches[0]["unitCostMinor"] == 150000

    # Sale 3: Order for 5 units -> all from batch 2 @ 1,500
    batches, total_cost, weighted_cost, active_cost = consume_fifo_batches(batches, 5)
    assert total_cost == 5 * 150000  # 750,000
    assert weighted_cost == 150000
    assert active_cost == 150000
    assert batches[0]["quantity"] == 3


def test_fifo_batches_handle_empty_and_fallback():
    # If no batches exist, fallback to default cost
    batches, total_cost, weighted_cost, active_cost = consume_fifo_batches([], 2, default_unit_cost_minor=80000)
    assert total_cost == 160000
    assert weighted_cost == 80000
    assert active_cost == 80000


def test_normalize_batches_cleans_empty_batches():
    raw = [
        {"quantity": 0, "unitCostMinor": 1000},
        {"quantity": 3, "unitCostMinor": 2000},
        "invalid",
    ]
    normalized = normalize_batches(raw)
    assert len(normalized) == 1
    assert normalized[0]["quantity"] == 3
    assert normalized[0]["unitCostMinor"] == 2000
