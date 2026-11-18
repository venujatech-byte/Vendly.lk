"""Use the real Firestore SDK with in-memory RPCs to exercise product-edit retries."""

from copy import deepcopy

import pytest

from firestore_memory import MemoryFirestore

from app.core.errors import ApiError
from app.services.product_service import update_product


BUSINESS = "businesses/business-a"
PRODUCT = f"{BUSINESS}/products/product-a"
VARIANT = f"{BUSINESS}/productVariants/variant-a"


@pytest.fixture
def store():
    # Seed a product with a retained FIFO batch and two units reserved by an order.
    store = MemoryFirestore()
    store.put(VARIANT, {
        "productId": "product-a", "sku": "SKU-A", "barcode": "BAR-A", "size": "M",
        "stockOnHand": 10, "stockReserved": 2, "stockAvailable": 8,
        "costPriceMinor": 10000, "sellingPriceMinor": 20000,
        "inventoryBatches": [{"batchId": "batch-a", "quantity": 10, "unitCostMinor": 10000}],
    })
    store.put(PRODUCT, {
        "name": "Product", "totalStock": 10, "reservedStock": 2, "availableStock": 8,
        "lowStockThreshold": 5, "variantSummaries": [{"id": "variant-a", **store.documents[VARIANT]}],
    })
    for kind, value in [("sku", "SKU-A"), ("barcode", "BAR-A")]:
        store.put(f"{BUSINESS}/{kind}Registry/{value}", {"productId": "product-a"})
    return store


def variant_payload(stock=10, sku="SKU-A", barcode="BAR-A"):
    return {"variants": [{
        "id": "variant-a", "size": "M", "sku": sku, "barcode": barcode,
        "stock": stock, "costPrice": 100, "sellingPrice": 200,
    }]}


def reserve(store, quantity):
    # Model checkout updating both the variant and its product aggregates atomically.
    variant = {**store.documents[VARIANT], "stockReserved": quantity, "stockAvailable": 10 - quantity}
    store.put(VARIANT, variant)
    store.put(PRODUCT, {
        **store.documents[PRODUCT], "reservedStock": quantity, "availableStock": 10 - quantity,
        "variantSummaries": [{"id": "variant-a", **variant}],
    })


def test_product_edit_retries_and_keeps_concurrent_checkout_reservation(store):
    original_batches = deepcopy(store.documents[VARIANT]["inventoryBatches"])
    store.before_commit = lambda current: reserve(current, 4)
    product = update_product(store.client, "business-a", "product-a", variant_payload(stock=12))
    assert store.attempts == 2
    assert store.commits == 1
    assert product["totalStock"] == 12
    assert product["reservedStock"] == 4
    assert product["availableStock"] == 8
    assert store.documents[VARIANT]["stockReserved"] == 4
    assert store.documents[VARIANT]["stockAvailable"] == 8
    assert store.documents[VARIANT]["inventoryBatches"] == original_batches


def test_retry_rejects_stock_below_new_reservation_without_partial_writes(store):
    store.before_commit = lambda current: reserve(current, 6)
    with pytest.raises(ApiError) as error:
        update_product(store.client, "business-a", "product-a", variant_payload(stock=3))
    assert error.value.code == "insufficient_adjustable_stock"
    assert store.attempts == 2
    assert store.commits == 0
    assert store.documents[VARIANT]["stockOnHand"] == 10
    assert store.documents[VARIANT]["stockReserved"] == 6


@pytest.mark.parametrize("kind", ["sku", "barcode"])
def test_identifier_claim_conflict_is_rechecked_on_retry(store, kind):
    path = f"{BUSINESS}/{kind}Registry/NEW-IDENTIFIER"
    store.before_commit = lambda current: current.put(path, {"productId": "product-b"})
    payload = variant_payload(**{kind: "NEW-IDENTIFIER"})
    with pytest.raises(ApiError) as error:
        update_product(store.client, "business-a", "product-a", payload)
    assert error.value.code == f"{kind}_already_exists"
    assert store.attempts == 2
    assert store.commits == 0
    assert store.documents[path]["productId"] == "product-b"
    assert store.documents[VARIANT]["sku"] == "SKU-A"


def test_metadata_edit_keeps_concurrent_stock_and_preserves_variant_status_calculation(store):
    store.before_commit = lambda current: reserve(current, 7)
    result = update_product(store.client, "business-a", "product-a", {"lowStockThreshold": 4})
    assert store.attempts == 2
    assert result["reservedStock"] == 7
    assert result["availableStock"] == 3
    assert result["stockStatus"] == "low-stock"
    assert result["variantSummaries"][0]["stockReserved"] == 7
    assert store.documents[VARIANT]["stockStatus"] == "low-stock"


def test_product_edit_reads_every_registry_before_writing_multiple_variants(store):
    payload = variant_payload(stock=12)
    payload["variants"].append({
        "size": "L", "sku": "SKU-L", "barcode": "BAR-L", "stock": 3,
        "costPrice": 100, "sellingPrice": 200,
    })
    result = update_product(store.client, "business-a", "product-a", payload)
    assert result["totalStock"] == 15
    assert result["reservedStock"] == 2
    assert len(result["variantSummaries"]) == 2
    assert store.commits == 1


def test_concurrent_reservation_prevents_variant_removal(store):
    second_path = f"{BUSINESS}/productVariants/variant-b"
    second = {**store.documents[VARIANT], "sku": "SKU-B", "barcode": "BAR-B", "stockReserved": 0}
    store.put(second_path, second)

    def reserve_second(current):
        current.put(second_path, {**second, "stockReserved": 1})

    store.before_commit = reserve_second
    with pytest.raises(ApiError) as error:
        update_product(store.client, "business-a", "product-a", variant_payload())
    assert error.value.code == "variant_in_use"
    assert store.attempts == 2
    assert store.commits == 0
    assert store.documents[second_path]["stockReserved"] == 1


@pytest.mark.parametrize("variants", [[], "invalid", [{"sku": "", "barcode": "BAR-A"}], [{"sku": "x" * 81, "barcode": "BAR-A"}]])
def test_invalid_variants_leave_stock_unchanged(store, variants):
    before = deepcopy(store.documents)
    with pytest.raises(ApiError) as error:
        update_product(store.client, "business-a", "product-a", {"variants": variants})
    assert error.value.code == "validation_error"
    assert error.value.status_code == 422
    assert store.documents == before
    assert store.commits == 0


def test_unicode_identifier_normalization_keeps_existing_length_validation(store):
    payload = variant_payload(sku="ß" * 80)
    update_product(store.client, "business-a", "product-a", payload)
    assert store.documents[VARIANT]["sku"] == "SS" * 80


def test_archiving_changes_no_stock_or_identifier_records(store):
    before = deepcopy(store.documents[VARIANT])
    result = update_product(store.client, "business-a", "product-a", {"status": "archived"})
    assert result["status"] == "archived"
    assert store.documents[VARIANT] == before
    assert store.commits == 1
