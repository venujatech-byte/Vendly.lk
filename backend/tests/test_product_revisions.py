"""Exercise product cache revisions through real SDK batches/transactions and offline RPCs."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import PermissionDenied

from firestore_memory import MemoryFirestore
from app import create_app
from app.core.errors import ApiError
from app.services import media_service, order_service, spreadsheet_service
from app.services.cache_revision_service import get_cache_revision
from app.services.product_service import adjust_variant_stock, create_product, update_product
from app.services.review_service import moderate_review
from app.services.shop_sale_service import create_shop_sale, delete_shop_sale


BUSINESS = "businesses/business-a"
REVISION = f"{BUSINESS}/_cacheVersions/products"


class RevisionFirestore(MemoryFirestore):
    # Assert at the RPC boundary that every product mutation carries exactly one atomic marker write.
    def commit(self, request, **kwargs):
        prefix = f"{self.client._database_string}/documents/{BUSINESS}/products/"
        names = [write.update.name or write.delete for write in request["writes"]]
        if any(name.startswith(prefix) and "/" not in name[len(prefix):] for name in names):
            assert names.count(f"{self.client._database_string}/documents/{REVISION}") == 1
        return super().commit(request, **kwargs)


def product_payload():
    return {
        "name": "Synthetic product", "costPrice": 10, "sellingPrice": 20, "weightKg": 0.1,
        "variants": [{"sku": "SKU-A", "barcode": "BAR-A", "stock": 10}],
    }


@pytest.fixture
def store(monkeypatch):
    # Only external notifications/uploads are stubbed; Firestore service code and transactions stay real.
    monkeypatch.setattr("app.core.firebase.get_rtdb_reference", Mock(return_value=None))
    monkeypatch.setattr("app.services.operations_service.dispatch_notification", Mock())
    monkeypatch.setattr(order_service, "send_order_status_chat_message", Mock())
    monkeypatch.setattr("app.services.email_service.send_order_confirmation_email", Mock())
    monkeypatch.setattr("app.services.email_service.send_customer_order_status_email", Mock())
    monkeypatch.setattr(media_service, "upload_to_cloudinary", Mock(return_value={"url": "https://synthetic.example/image", "path": "synthetic/image"}))
    store = RevisionFirestore()
    store.put(BUSINESS, {"status": "active"})
    product = create_product(store.client, "business-a", "seller", product_payload())
    store.product_id = product["id"]
    store.variant_id = product["variantSummaries"][0]["id"]
    store.put(f"{BUSINESS}/customers/customer-a", {
        "name": "Synthetic customer", "status": "active", "normalizedPhone": "94712345678",
        "defaultAddress": {"line1": "Synthetic street", "city": "Colombo", "district": "Colombo"},
    })
    store.put(f"{BUSINESS}/couriers/courier-a", {"name": "Courier", "status": "active", "firstKgPriceMinor": 100})
    return store


def revision(store):
    return get_cache_revision(store.client, "business-a", "products")


def create_order(store):
    return order_service.create_order(store.client, "business-a", "mobile-user", {
        "customerId": "customer-a", "courierId": "courier-a",
        "items": [{"variantId": store.variant_id, "quantity": 1}],
    })


def test_existing_business_needs_no_backfill_and_product_creation_publishes_first_revision():
    store = RevisionFirestore()
    store.put(BUSINESS, {})
    assert revision(store) == "0"
    product = create_product(store.client, "business-a", "seller", product_payload())
    assert len(revision(store)) == 32
    assert f"{BUSINESS}/products/{product['id']}" in store.documents


@pytest.mark.parametrize("action", ["edit", "status", "stock", "product-media", "variant-image"])
def test_product_mutations_publish_revisions_with_their_data(store, action):
    before = revision(store)
    if action == "edit":
        update_product(store.client, "business-a", store.product_id, {"name": "Renamed"})
    elif action == "status":
        update_product(store.client, "business-a", store.product_id, {"status": "archived"})
    elif action == "stock":
        adjust_variant_stock(store.client, "business-a", store.product_id, store.variant_id, "seller", {"quantityChange": 1, "reason": "Stock arrival"})
    elif action == "product-media":
        media_service.upload_product_media(store.client, "business-a", store.product_id, "seller", [object()])
    else:
        media_service.upload_variant_image(store.client, "business-a", store.product_id, store.variant_id, object())
    assert revision(store) != before


def test_import_uses_the_same_revision_aware_product_writers(store, monkeypatch):
    before = revision(store)
    payload = product_payload()
    payload["name"] = "Imported rename"
    monkeypatch.setattr(spreadsheet_service, "parse_inventory_workbook", lambda _stream: {
        "categories": [], "products": [{"payload": payload, "categoryName": "", "status": "active", "sourceProductId": store.product_id}],
    })
    result = spreadsheet_service.import_inventory_workbook(store.client, "business-a", "seller", object())
    assert result["productsUpdated"] == 1
    assert revision(store) != before


def test_shop_sale_and_its_reversal_each_publish_inventory_changes(store):
    before = revision(store)
    sale = create_shop_sale(store.client, "business-a", "mobile-user", {"items": [{"variantId": store.variant_id, "quantity": 1}]})
    sold = revision(store)
    assert sold != before
    delete_shop_sale(store.client, "business-a", sale["id"], "seller")
    assert revision(store) != sold


def test_order_reservations_and_extra_items_publish_inventory_changes(store):
    before = revision(store)
    order = create_order(store)
    reserved = revision(store)
    assert reserved != before
    order_service.add_items_to_order(store.client, "business-a", order["id"], "mobile-user", [{"variantId": store.variant_id, "quantity": 1}])
    assert revision(store) != reserved


@pytest.mark.parametrize("terminal", ["cancelled", "delivered", "returned"])
def test_only_stock_changing_order_transitions_advance_product_revision(store, terminal):
    order = create_order(store)
    before = revision(store)
    if terminal != "cancelled":
        for status in ("confirmed", "packed", "shipped"):
            order_service.update_order_status(store.client, "business-a", order["id"], "seller", {"status": status})
            assert revision(store) == before
    order_service.update_order_status(store.client, "business-a", order["id"], "seller", {"status": terminal})
    assert revision(store) != before


@pytest.mark.parametrize("review_type, status, changes", [("product", "approved", True), ("product", "rejected", False), ("seller", "approved", False)])
def test_only_published_product_review_counts_affect_inventory_revision(store, review_type, status, changes):
    store.put(f"{BUSINESS}/reviews/review-a", {"type": review_type, "productId": store.product_id, "status": "pending", "rating": 5})
    before = revision(store)
    moderate_review(store.client, "business-a", "review-a", "seller", {"status": status})
    assert (revision(store) != before) is changes


@pytest.mark.parametrize("action", ["edit", "product-media", "variant-image"])
def test_failed_validation_and_failed_commit_cannot_publish_a_revision(store, action):
    before = deepcopy(store.documents)
    with pytest.raises(ApiError):
        update_product(store.client, "business-a", store.product_id, {"sellingPrice": "NaN"})
    assert store.documents == before

    def fail(_store):
        raise PermissionDenied("Synthetic denied commit")

    store.before_commit = fail
    with pytest.raises(PermissionDenied):
        if action == "edit":
            update_product(store.client, "business-a", store.product_id, {"name": "Rejected"})
        elif action == "product-media":
            media_service.upload_product_media(store.client, "business-a", store.product_id, "seller", [object()])
        else:
            media_service.upload_variant_image(store.client, "business-a", store.product_id, store.variant_id, object())
    assert store.documents == before


def test_order_validation_after_queued_stock_writes_does_not_publish_its_revision(store):
    before = deepcopy(store.documents)
    with pytest.raises(ApiError) as error:
        order_service.create_order(store.client, "business-a", "seller", {
            "customerId": "customer-a", "courierId": "courier-a", "depositAmount": 100000,
            "items": [{"variantId": store.variant_id, "quantity": 1}],
        })
    assert error.value.code == "invalid_deposit"
    assert store.documents == before


def test_transaction_retry_publishes_only_the_committed_revision(store):
    path = f"{BUSINESS}/products/{store.product_id}"
    before = revision(store)
    attempts = store.attempts
    store.before_commit = lambda current: current.put(path, {**current.documents[path], "name": "Concurrent name"})
    update_product(store.client, "business-a", store.product_id, {"brand": "Changed brand"})
    assert store.attempts == attempts + 2
    assert revision(store) != before
    assert store.documents[path]["name"] == "Concurrent name"
    assert store.documents[path]["brand"] == "Changed brand"


@pytest.fixture
def api(store, monkeypatch):
    member = f"{BUSINESS}/members/member-a"
    store.put(member, {"role": "custom", "permissions": ["inventory:read"], "status": "active"})
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.products.get_firestore_client", lambda: store.client)
    return create_app({"TESTING": True}).test_client(), store, member


def test_version_api_reads_only_membership_and_small_marker_not_products(api):
    client, store, member = api
    store.client._firestore_api.batch_get_documents.reset_mock()
    store.client._firestore_api.run_query.reset_mock()
    response = client.get("/api/v1/businesses/business-a/inventory/version", headers={"Authorization": "Bearer synthetic-token"})
    assert response.status_code == 200
    assert response.get_json() == {"revision": store.documents[REVISION]["revision"]}
    reads = store.client._firestore_api.batch_get_documents.call_args_list
    assert len(reads) == 2
    assert {call.kwargs["request"]["documents"][0].split("/documents/", 1)[1] for call in reads} == {member, REVISION}
    store.client._firestore_api.run_query.assert_not_called()


@pytest.mark.parametrize("headers, tenant, permissions, status, expected", [
    ({}, "business-a", ["inventory:read"], "active", 401),
    ({"Authorization": "Bearer synthetic-token"}, "business-b", ["inventory:read"], "active", 403),
    ({"Authorization": "Bearer synthetic-token"}, "business-a", ["orders:read"], "active", 403),
    ({"Authorization": "Bearer synthetic-token"}, "business-a", ["inventory:manage"], "active", 403),
    ({"Authorization": "Bearer synthetic-token"}, "business-a", ["inventory:read"], "inactive", 403),
])
def test_version_api_rechecks_current_tenant_and_module_access(api, headers, tenant, permissions, status, expected):
    client, store, member = api
    store.put(member, {"role": "custom", "permissions": permissions, "status": status})
    response = client.get(f"/api/v1/businesses/{tenant}/inventory/version?businessId=business-a&permissions=*", headers=headers)
    assert response.status_code == expected
    assert "revision" not in response.get_json()
