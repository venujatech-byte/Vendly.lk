"""Warranty claim numbering and financial snapshots must commit together."""

from copy import deepcopy

import pytest
from google.api_core.exceptions import PermissionDenied

from app.core.errors import ApiError
from app.services.shop_sale_service import create_warranty_claim
from firestore_memory import MemoryFirestore

BUSINESS = "businesses/business-a"
SOURCE = f"{BUSINESS}/shopSales/sale-a"


@pytest.fixture
def store():
    # Use the real SDK transaction retries with synthetic records and no cloud traffic.
    store = MemoryFirestore()
    store.put(BUSINESS, {"nextWarrantyClaimSequence": 7})
    store.put(SOURCE, {
        "saleNumber": "SS-000001", "customerName": "Synthetic customer",
        "items": [{"name": "Test item", "quantity": 2, "unitPriceMinor": 12500}],
    })
    return store


def payload(**changes):
    return {
        "sourceType": "shop-sale", "sourceId": "sale-a", "reason": "Synthetic defect",
        "claimQuantity": 2, "otherExpenses": "5", **changes,
    }


def test_competing_claims_receive_distinct_numbers_without_losing_the_sequence(store):
    competing = []
    store.before_commit = lambda current: competing.append(
        create_warranty_claim(current.client, "business-a", "seller-b", payload()),
    )
    result = create_warranty_claim(store.client, "business-a", "seller-a", payload())
    assert {result["claimNumber"], competing[0]["claimNumber"]} == {"WC-000007", "WC-000008"}
    assert store.documents[BUSINESS]["nextWarrantyClaimSequence"] == 9
    assert len([path for path in store.documents if "/warrantyClaims/" in path]) == 2
    assert store.attempts == 3


def test_failed_commit_leaves_neither_a_claim_nor_a_consumed_number(store):
    before = deepcopy(store.documents)

    def reject(request, **kwargs):
        if any(write.update.name.endswith(f"/documents/{BUSINESS}") for write in request["writes"]):
            raise PermissionDenied("Synthetic rejected sequence write")
        return store.commit(request, **kwargs)

    store.client._firestore_api.commit.side_effect = reject
    with pytest.raises(PermissionDenied):
        create_warranty_claim(store.client, "business-a", "seller", payload())
    assert store.documents == before


def test_changed_source_is_revalidated_before_a_claim_can_commit(store):
    store.before_commit = lambda current: current.put(SOURCE, {
        **current.documents[SOURCE],
        "items": [{"name": "Test item", "quantity": 1, "unitPriceMinor": 12500}],
    })
    with pytest.raises(ApiError) as error:
        create_warranty_claim(store.client, "business-a", "seller", payload())
    assert error.value.status_code == 422
    assert store.documents[BUSINESS]["nextWarrantyClaimSequence"] == 7
    assert not any("/warrantyClaims/" in path for path in store.documents)


def test_online_order_claim_uses_the_same_atomic_number_allocation(store):
    store.put(f"{BUSINESS}/orders/order-a", {
        **store.documents[SOURCE], "orderNumber": "VD-SYNTHETIC",
        "customerSnapshot": {"name": "Online customer", "phoneNumber": "94700000123"},
    })
    result = create_warranty_claim(store.client, "business-a", "seller", payload(
        sourceType="online-order", sourceId="order-a",
    ))
    assert result["sourceNumber"] == "VD-SYNTHETIC"
    assert result["customerName"] == "Online customer"
    assert result["claimNumber"] == "WC-000007"
    assert store.documents[BUSINESS]["nextWarrantyClaimSequence"] == 8
    assert store.commits == 1


@pytest.mark.parametrize("claim_type,repair_cost,expected", [
    ("supplier-warranty", 0, 500),
    ("shop-warranty", 0, 25500),
    ("shop-repair", "12.50", 1750),
])
def test_claims_keep_existing_financial_formulas_and_source_snapshot(store, claim_type, repair_cost, expected):
    result = create_warranty_claim(store.client, "business-a", "seller", payload(
        claimType=claim_type, repairCost=repair_cost,
    ))
    assert result["otherExpensesMinor"] == 500
    assert result["totalExpensesMinor"] == result["revenueImpactMinor"] == expected
    assert result["item"] == store.documents[SOURCE]["items"][0]
    assert result["sourceNumber"] == "SS-000001"
    assert result["customerName"] == "Synthetic customer"
    assert result["createdBy"] == "seller"
