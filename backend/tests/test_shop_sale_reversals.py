"""Verify shop sale reversals retain FIFO costs using real SDK transaction retries."""

from copy import deepcopy

import pytest

from firestore_memory import MemoryFirestore

from app.core.errors import ApiError
from app.services.shop_sale_service import create_shop_sale, delete_shop_sale


BUSINESS = "businesses/business-a"
PRODUCT = f"{BUSINESS}/products/product-a"
VARIANT = f"{BUSINESS}/productVariants/variant-a"


@pytest.fixture
def store():
    # Two arrivals with different costs make a missing or averaged restoration observable.
    store = MemoryFirestore()
    batches = [
        {"batchId": "older", "quantity": 2, "initialQuantity": 2,
         "unitCostMinor": 10000, "createdAt": "2026-01-01T00:00:00+00:00", "fifoOrder": 0},
        {"batchId": "newer", "quantity": 3, "initialQuantity": 3,
         "unitCostMinor": 20000, "createdAt": "2026-02-01T00:00:00+00:00", "fifoOrder": 1},
    ]
    variant = {
        "productId": "product-a", "status": "active", "sku": "SKU-A",
        "stockOnHand": 5, "stockAvailable": 5, "stockReserved": 0,
        "inventoryBatches": batches, "costPriceMinor": 10000, "sellingPriceMinor": 30000,
    }
    store.put(BUSINESS, {"nextShopSaleSequence": 1})
    store.put(VARIANT, variant)
    store.put(PRODUCT, {
        "name": "Product", "totalStock": 5, "availableStock": 5, "costPriceMinor": 10000,
        "variantSummaries": [{"id": "variant-a", **variant}],
    })
    return store


def sell(store, quantity=1):
    return create_shop_sale(store.client, "business-a", "seller", {
        "items": [{"variantId": "variant-a", "quantity": quantity}],
    })


def reverse(store, sale):
    return delete_shop_sale(store.client, "business-a", sale["id"], "seller")


def test_reversal_restores_original_costs_and_next_sale_uses_oldest_batch(store):
    original = deepcopy(store.documents[VARIANT]["inventoryBatches"])
    sale = sell(store, 2)
    assert store.documents[VARIANT]["costPriceMinor"] == 20000
    assert sale["items"][0]["consumedBatches"] == [original[0]]
    assert reverse(store, sale)["status"] == "voided"
    variant = store.documents[VARIANT]
    assert variant["inventoryBatches"] == original
    assert variant["stockOnHand"] == variant["stockAvailable"] == 5
    assert variant["costPriceMinor"] == 10000
    product = store.documents[PRODUCT]
    assert product["totalStock"] == product["availableStock"] == 5
    assert product["costPriceMinor"] == 10000
    assert product["variantSummaries"][0]["inventoryBatches"] == original
    assert sell(store)["items"][0]["unitCostMinor"] == 10000


def test_multi_batch_reversal_retains_exact_cost_instead_of_rounded_average(store):
    original = deepcopy(store.documents[VARIANT]["inventoryBatches"])
    sale = sell(store, 3)
    item = sale["items"][0]
    assert item["unitCostMinor"] == 13333
    assert sum(batch["quantity"] * batch["unitCostMinor"] for batch in item["consumedBatches"]) == 40000
    reverse(store, sale)
    assert store.documents[VARIANT]["inventoryBatches"] == original


def test_partial_batch_reversals_out_of_sale_order_restore_original_fifo(store):
    original = deepcopy(store.documents[VARIANT]["inventoryBatches"])
    first = sell(store, 1)
    second = sell(store, 2)
    reverse(store, first)
    reverse(store, second)
    assert store.documents[VARIANT]["inventoryBatches"] == original


def test_same_date_arrivals_keep_original_order_across_separate_reversals(store):
    variant = deepcopy(store.documents[VARIANT])
    for batch in variant["inventoryBatches"]:
        batch["createdAt"] = "2026-01-01T00:00:00+00:00"
        del batch["fifoOrder"]
    store.put(VARIANT, variant)
    first = sell(store, 2)
    second = sell(store, 3)
    reverse(store, first)
    reverse(store, second)
    batches = store.documents[VARIANT]["inventoryBatches"]
    assert [batch["batchId"] for batch in batches] == ["older", "newer"]
    assert [batch["quantity"] for batch in batches] == [2, 3]


def test_reversal_retries_without_losing_concurrent_sale(store):
    sale = sell(store, 2)
    store.before_commit = lambda current: sell(current, 1)
    reverse(store, sale)
    variant = store.documents[VARIANT]
    assert variant["stockOnHand"] == variant["stockAvailable"] == 4
    assert [batch["quantity"] for batch in variant["inventoryBatches"]] == [2, 2]
    assert store.documents[PRODUCT]["totalStock"] == 4


def test_concurrent_reversal_cannot_restore_same_sale_twice(store):
    sale = sell(store, 2)
    store.before_commit = lambda current: reverse(current, sale)
    with pytest.raises(ApiError) as error:
        reverse(store, sale)
    assert error.value.code == "shop_sale_already_voided"
    assert store.documents[VARIANT]["stockOnHand"] == 5
    assert sum(batch["quantity"] for batch in store.documents[VARIANT]["inventoryBatches"]) == 5


def test_unbatched_stock_preserves_unsold_quantity_and_its_known_cost(store):
    store.put(VARIANT, {**store.documents[VARIANT], "inventoryBatches": []})
    sale = sell(store, 2)
    assert sum(batch["quantity"] for batch in store.documents[VARIANT]["inventoryBatches"]) == 3
    reverse(store, sale)
    batches = store.documents[VARIANT]["inventoryBatches"]
    assert sum(batch["quantity"] for batch in batches) == 5
    assert sum(batch["quantity"] * batch["unitCostMinor"] for batch in batches) == 50000


def test_incomplete_saved_allocations_fail_without_partial_stock_writes(store):
    sale = sell(store, 2)
    path = f"{BUSINESS}/shopSales/{sale['id']}"
    saved = deepcopy(store.documents[path])
    saved["items"][0]["consumedBatches"][0]["quantity"] = 1
    store.put(path, saved)
    before = deepcopy(store.documents)
    with pytest.raises(ApiError) as error:
        reverse(store, sale)
    assert error.value.code == "invalid_sale_cost_allocations"
    assert store.documents == before


def test_missing_product_cannot_partially_restore_stock(store):
    sale = sell(store, 2)
    del store.documents[PRODUCT]
    before = deepcopy(store.documents)
    with pytest.raises(ApiError) as error:
        reverse(store, sale)
    assert error.value.code == "stock_record_missing"
    assert store.documents == before


def test_legacy_reversal_restores_saved_average_cost_and_flags_estimate(store):
    sale = sell(store, 3)
    path = f"{BUSINESS}/shopSales/{sale['id']}"
    legacy = deepcopy(store.documents[path])
    del legacy["items"][0]["consumedBatches"]
    legacy["createdAt"] = "2026-01-15T00:00:00+00:00"
    store.put(path, legacy)
    reverse(store, sale)
    batches = store.documents[VARIANT]["inventoryBatches"]
    restored = [batch for batch in batches if batch.get("estimatedCost")]
    assert len(restored) == 1
    assert restored[0]["quantity"] == 3
    assert restored[0]["unitCostMinor"] == legacy["items"][0]["unitCostMinor"] == 13333
    assert sum(batch["quantity"] for batch in batches) == 5
    reversals = [data for path, data in store.documents.items()
                 if "/inventoryTransactions/" in path and data.get("type") == "shop-sale-reversal"]
    assert len(reversals) == 1
    assert reversals[0]["estimatedCost"] is True
    assert store.documents[path]["items"] == legacy["items"]

    # The estimate remains identifiable after another sale consumes and restores it.
    next_sale = sell(store, 1)
    assert next_sale["items"][0]["consumedBatches"][0]["estimatedCost"] is True
    reverse(store, next_sale)
    assert store.documents[VARIANT]["inventoryBatches"] == batches


def test_legacy_zero_cost_is_preserved_instead_of_using_current_product_cost(store):
    sale = sell(store, 2)
    path = f"{BUSINESS}/shopSales/{sale['id']}"
    legacy = deepcopy(store.documents[path])
    del legacy["items"][0]["consumedBatches"]
    legacy["items"][0]["unitCostMinor"] = 0
    store.put(path, legacy)
    reverse(store, sale)
    restored = [batch for batch in store.documents[VARIANT]["inventoryBatches"] if batch.get("estimatedCost")]
    assert restored[0]["unitCostMinor"] == 0
    assert restored[0]["quantity"] == 2


def test_legacy_reversal_keeps_current_stock_that_has_no_batch_records(store):
    sale = sell(store, 2)
    path = f"{BUSINESS}/shopSales/{sale['id']}"
    legacy = deepcopy(store.documents[path])
    del legacy["items"][0]["consumedBatches"]
    store.put(path, legacy)
    store.put(VARIANT, {**store.documents[VARIANT], "inventoryBatches": []})
    reverse(store, sale)
    batches = store.documents[VARIANT]["inventoryBatches"]
    assert sum(batch["quantity"] for batch in batches) == 5
    assert sum(batch["quantity"] for batch in batches if batch.get("estimatedCost")) == 2
