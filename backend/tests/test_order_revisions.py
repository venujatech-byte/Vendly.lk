"""Verify order-cache freshness at real SDK commits and protected APIs without cloud calls."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import PermissionDenied

from firestore_memory import MemoryFirestore
from app import create_app
from app.core.errors import ApiError
from app.services import customer_portal_service as portal, operations_service, order_service, public_chat_service
from app.services.cache_revision_service import get_cache_revision
from app.services.product_service import create_product

BUSINESS = "businesses/business-a"
REVISION = f"{BUSINESS}/_cacheVersions/orders"
HEADERS = {"Authorization": "Bearer synthetic-token"}


class OrderRevisionFirestore(MemoryFirestore):
    # Every order write must carry exactly one revision in its own atomic commit.
    def commit(self, request, **kwargs):
        prefix = f"{self.client._database_string}/documents/{BUSINESS}/orders/"
        names = [write.update.name or write.delete for write in request["writes"]]
        if any(name.startswith(prefix) and "/" not in name[len(prefix):] for name in names):
            assert names.count(f"{self.client._database_string}/documents/{REVISION}") == 1
        return super().commit(request, **kwargs)


@pytest.fixture
def store(monkeypatch):
    # Keep services and SDK commits real, isolating external email, chat and notification providers.
    monkeypatch.setattr(operations_service, "dispatch_notification", Mock())
    monkeypatch.setattr(order_service, "send_order_status_chat_message", Mock())
    monkeypatch.setattr(order_service, "send_payment_recorded_chat_message", Mock())
    monkeypatch.setattr("app.core.firebase.get_rtdb_reference", Mock(return_value=None))
    monkeypatch.setattr("app.services.email_service.send_order_confirmation_email", Mock())
    monkeypatch.setattr("app.services.email_service.send_customer_order_status_email", Mock())
    monkeypatch.setattr(portal, "resolve_store_business_id", lambda *_args: "business-a")
    store = OrderRevisionFirestore()
    store.put(BUSINESS, {"status": "active"})
    product = create_product(store.client, "business-a", "seller", {
        "name": "Synthetic product", "costPrice": 10, "sellingPrice": 20, "weightKg": 0.1,
        "variants": [{"sku": "SKU-A", "barcode": "BAR-A", "stock": 10}],
    })
    store.variant_id = product["variantSummaries"][0]["id"]
    store.put(f"{BUSINESS}/customers/customer-a", {
        "name": "Synthetic customer", "status": "active", "normalizedPhone": "94712345678",
        "defaultAddress": {"line1": "Synthetic street", "city": "Colombo", "district": "Colombo"},
    })
    store.put(f"{BUSINESS}/couriers/courier-a", {"name": "Courier", "status": "active", "firstKgPriceMinor": 100})
    return store


def revision(store):
    return get_cache_revision(store.client, "business-a", "orders")


def create_order(store):
    return order_service.create_order(store.client, "business-a", "mobile-user", {
        "customerId": "customer-a", "courierId": "courier-a",
        "items": [{"variantId": store.variant_id, "quantity": 1}],
    })


def mutate(store, order_id, action):
    # Cover every existing order writer, including guest and operations entry points.
    if action in {"edit", "waybill-edit"}:
        order_service.update_order(store.client, "business-a", order_id, "seller", {"privateNote": "Mobile edit"} if action == "edit" else {"waybillNumber": "WB-SYNTHETIC"})
    elif action in {"confirmed", "packed", "shipped", "delivered", "returned", "cancelled"}:
        order_service.update_order_status(store.client, "business-a", order_id, "seller", {"status": action})
    elif action == "items":
        order_service.add_items_to_order(store.client, "business-a", order_id, "mobile-user", [{"variantId": store.variant_id, "quantity": 1}])
    elif action == "payment":
        order_service.record_order_payment(store.client, "business-a", order_id, "seller", {"paidAmountMinor": 100})
    elif action == "cod":
        order_service.convert_order_to_cash_on_delivery(store.client, "business-a", order_id, "seller")
    elif action == "receipt":
        order_service.attach_order_payment_receipt(store.client, "business-a", order_id, "seller", "https://synthetic.example/receipt", 100)
    elif action == "fraud":
        operations_service.create_fraud_report(store.client, "business-a", order_id, "seller", {"type": "fake-details"})
    elif action == "courier-issue":
        operations_service.record_courier_issue(store.client, "business-a", order_id, "seller", {"type": "lost"})
    elif action == "waybill":
        operations_service.generate_waybill(store.client, "business-a", order_id, "seller")
    elif action == "email":
        portal.update_order_guest_email(store.client, "store", order_id, "new@example.test", customer_uid="account-a")
    elif action == "history":
        portal.claim_guest_customer_orders(store.client, "store", "guest-a", "account-a")
    else:
        raise AssertionError(action)


def test_first_order_creates_its_revision_without_a_migration(store):
    assert revision(store) == "0"
    create_order(store)
    assert len(revision(store)) == 32


@pytest.mark.parametrize("action", ["edit", "waybill-edit", "confirmed", "packed", "shipped", "delivered", "returned", "cancelled", "items", "payment", "cod", "receipt", "fraud", "courier-issue", "waybill", "email", "history"])
def test_order_writers_publish_revisions_in_the_same_commit(store, action):
    order_id = create_order(store)["id"]
    if action == "waybill":
        order_service.update_order(store.client, "business-a", order_id, "seller", {"waybillNumber": ""})
        mutate(store, order_id, "confirmed")
    transitions = ["confirmed", "packed", "shipped", "delivered"]
    if action in {"packed", "shipped", "delivered", "returned"}:
        for status in transitions[:transitions.index(action) if action != "returned" else 3]:
            mutate(store, order_id, status)
    if action in {"email", "history"}:
        path = f"{BUSINESS}/orders/{order_id}"
        store.put(path, {**store.documents[path], "customerUid": "account-a" if action == "email" else "guest-a"})
    before = revision(store)
    mutate(store, order_id, action)
    assert revision(store) != before


@pytest.mark.parametrize("action", ["edit", "cancelled", "items", "payment", "cod", "receipt", "fraud", "courier-issue", "waybill", "email", "history"])
def test_failed_commits_leave_orders_and_revision_unchanged(store, action):
    order_id = create_order(store)["id"]
    if action == "waybill":
        order_service.update_order(store.client, "business-a", order_id, "seller", {"waybillNumber": ""})
        mutate(store, order_id, "confirmed")
    if action in {"email", "history"}:
        path = f"{BUSINESS}/orders/{order_id}"
        store.put(path, {**store.documents[path], "customerUid": "account-a" if action == "email" else "guest-a"})
    before = deepcopy(store.documents)

    def fail(_store):
        raise PermissionDenied("Synthetic denied commit")

    store.before_commit = fail
    with pytest.raises(PermissionDenied):
        mutate(store, order_id, action)
    assert store.documents == before


def test_guest_email_still_rejects_concurrent_ownership_changes(store):
    order_id = create_order(store)["id"]
    path = f"{BUSINESS}/orders/{order_id}"
    store.put(path, {**store.documents[path], "customerUid": "account-a"})
    before = revision(store)
    store.before_commit = lambda current: current.put(path, {**current.documents[path], "customerUid": "different-account"})
    with pytest.raises(ApiError) as error:
        mutate(store, order_id, "email")
    assert error.value.code == "order_changed"
    assert revision(store) == before
    assert store.documents[path]["customerSnapshot"].get("email") != "new@example.test"


def test_public_chat_claim_updates_order_and_revision_atomically(store, monkeypatch):
    order_id = create_order(store)["id"]
    store.put("publicChatSessions/session-a", {"businessId": "business-a", "orderId": order_id})
    snapshot = store.client.collection("publicChatSessions").document("session-a").get()
    monkeypatch.setattr(public_chat_service, "authorize_public_chat_session", lambda *_args, **_kwargs: (snapshot, snapshot.to_dict()))
    before = revision(store)
    public_chat_service.claim_public_chat_session(store.client, "session-a", "synthetic-token", "account-a", "owner@example.test")
    assert revision(store) != before
    assert store.documents[f"{BUSINESS}/orders/{order_id}"]["customerUid"] == "account-a"


@pytest.fixture
def api(store, monkeypatch):
    member = f"{BUSINESS}/members/member-a"
    store.put(member, {"role": "custom", "permissions": ["orders:read"], "status": "active"})
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.orders.get_firestore_client", lambda: store.client)
    return create_app({"TESTING": True}).test_client(), store, member


def test_version_endpoint_reads_only_membership_and_marker_and_preserves_order_id_version(api):
    client, store, member = api
    store.put(f"{BUSINESS}/orders/version", {"orderNumber": "Existing order"})
    store.client._firestore_api.batch_get_documents.reset_mock()
    store.client._firestore_api.run_query.reset_mock()
    response = client.get("/api/v1/businesses/business-a/orders/cache/version", headers=HEADERS)
    assert response.status_code == 200
    assert response.get_json() == {"revision": "0"}
    reads = store.client._firestore_api.batch_get_documents.call_args_list
    assert len(reads) == 2
    assert {call.kwargs["request"]["documents"][0].split("/documents/", 1)[1] for call in reads} == {member, REVISION}
    store.client._firestore_api.run_query.assert_not_called()
    response = client.get("/api/v1/businesses/business-a/orders/version", headers=HEADERS)
    assert response.get_json()["order"]["orderNumber"] == "Existing order"


@pytest.mark.parametrize("headers, tenant, permission, status, expected", [
    ({}, "business-a", "orders:read", "active", 401),
    (HEADERS, "business-b", "orders:read", "active", 403),
    (HEADERS, "business-a", "inventory:read", "active", 403),
    (HEADERS, "business-a", "orders:manage", "active", 403),
    (HEADERS, "business-a", "orders:read", "inactive", 403),
])
def test_version_endpoint_checks_current_tenant_and_read_permission(api, headers, tenant, permission, status, expected):
    client, store, member = api
    store.put(member, {"role": "custom", "permissions": [permission], "status": status})
    response = client.get(f"/api/v1/businesses/{tenant}/orders/cache/version", headers=headers)
    assert response.status_code == expected
    assert "revision" not in response.get_json()
