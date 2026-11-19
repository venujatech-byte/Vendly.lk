"""Verify customer-cache freshness at real SDK commit and authenticated API boundaries offline."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import PermissionDenied

from firestore_memory import MemoryFirestore
from app import create_app
from app.core.errors import ApiError
from app.services import operations_service, order_service
from app.services.cache_revision_service import get_cache_revision
from app.services.customer_service import create_customer, update_customer
from app.services.fraud_service import change_customer_fraud_risk, remove_customer_from_fraud_list, report_customer
from app.services.product_service import create_product


BUSINESS = "businesses/business-a"
REVISION = f"{BUSINESS}/_cacheVersions/customers"
HEADERS = {"Authorization": "Bearer synthetic-token"}


class CustomerRevisionFirestore(MemoryFirestore):
    # Every customer mutation must carry exactly one revision in the same atomic commit.
    def commit(self, request, **kwargs):
        prefix = f"{self.client._database_string}/documents/{BUSINESS}/customers/"
        names = [write.update.name or write.delete for write in request["writes"]]
        if any(name.startswith(prefix) and "/" not in name[len(prefix):] for name in names):
            assert names.count(f"{self.client._database_string}/documents/{REVISION}") == 1
        return super().commit(request, **kwargs)


def payload():
    return {
        "name": "Synthetic customer", "phoneNumber": "0712345678", "email": "synthetic@example.test",
        "address": {"line1": "Synthetic street", "city": "Colombo", "district": "Colombo"},
    }


@pytest.fixture
def store(monkeypatch):
    # Keep data services and Firestore transactions real; isolate notifications and external email/chat.
    monkeypatch.setattr(operations_service, "dispatch_notification", Mock())
    monkeypatch.setattr(order_service, "send_order_status_chat_message", Mock())
    monkeypatch.setattr("app.core.firebase.get_rtdb_reference", Mock(return_value=None))
    monkeypatch.setattr("app.services.email_service.send_order_confirmation_email", Mock())
    monkeypatch.setattr("app.services.email_service.send_customer_order_status_email", Mock())
    store = CustomerRevisionFirestore()
    store.put(BUSINESS, {"status": "active"})
    customer = create_customer(store.client, "business-a", payload())
    store.customer_id = customer["id"]
    product = create_product(store.client, "business-a", "seller", {
        "name": "Synthetic product", "costPrice": 10, "sellingPrice": 20, "weightKg": 0.1,
        "variants": [{"sku": "SKU-A", "barcode": "BAR-A", "stock": 10}],
    })
    store.variant_id = product["variantSummaries"][0]["id"]
    store.put(f"{BUSINESS}/couriers/courier-a", {"name": "Courier", "status": "active", "firstKgPriceMinor": 100})
    return store


def revision(store):
    return get_cache_revision(store.client, "business-a", "customers")


def create_order(store):
    return order_service.create_order(store.client, "business-a", "mobile-user", {
        "customerId": store.customer_id, "courierId": "courier-a",
        "items": [{"variantId": store.variant_id, "quantity": 1}],
    })


def test_first_customer_creates_marker_without_a_backfill():
    store = CustomerRevisionFirestore()
    assert revision(store) == "0"
    customer = create_customer(store.client, "business-a", payload())
    assert len(revision(store)) == 32
    assert store.documents[f"{BUSINESS}/customers/{customer['id']}"]["name"] == payload()["name"]


@pytest.mark.parametrize("changes", [{"name": "Mobile rename"}, {"email": "new@example.test"}, {"status": "archived"}, {"address": payload()["address"]}])
def test_contact_and_status_changes_publish_customer_revision(store, changes):
    before = revision(store)
    update_customer(store.client, "business-a", store.customer_id, changes)
    assert revision(store) != before


def test_order_creation_refreshes_customer_totals_without_changing_product_marker_contract(store):
    before = revision(store)
    product_revision = get_cache_revision(store.client, "business-a", "products")
    create_order(store)
    assert revision(store) != before
    assert get_cache_revision(store.client, "business-a", "products") != product_revision


@pytest.mark.parametrize("terminal, changed", [("delivered", True), ("returned", True), ("cancelled", False)])
def test_order_transitions_update_customer_revision_only_when_customer_data_changes(store, terminal, changed):
    order = create_order(store)
    before = revision(store)
    if terminal != "cancelled":
        for status in ("confirmed", "packed", "shipped"):
            order_service.update_order_status(store.client, "business-a", order["id"], "seller", {"status": status})
            assert revision(store) == before
    order_service.update_order_status(store.client, "business-a", order["id"], "seller", {"status": terminal})
    assert (revision(store) != before) is changed


def test_seller_fraud_report_risk_and_removal_each_refresh_the_customer_cache(store):
    before = revision(store)
    report_customer(store.client, "business-a", store.customer_id, "seller", {"reason": "seller-reported"})
    reported = revision(store)
    assert reported != before
    change_customer_fraud_risk(store.client, "business-a", store.customer_id, {"riskLevel": "medium"})
    risk = revision(store)
    assert risk != reported
    remove_customer_from_fraud_list(store.client, "business-a", store.customer_id)
    assert revision(store) != risk


def test_order_fraud_report_refreshes_customer_risk_in_same_transaction(store):
    order = create_order(store)
    before = revision(store)
    operations_service.create_fraud_report(store.client, "business-a", order["id"], "seller", {"type": "fake-details"})
    assert revision(store) != before


@pytest.mark.parametrize("action", ["create", "edit", "report", "risk", "remove", "order"])
def test_failed_commits_publish_neither_customer_changes_nor_revisions(store, action):
    before = deepcopy(store.documents)

    def fail(_store):
        raise PermissionDenied("Synthetic denied commit")

    store.before_commit = fail
    with pytest.raises(PermissionDenied):
        if action == "create":
            create_customer(store.client, "business-a", {**payload(), "phoneNumber": "0772345678"})
        elif action == "edit":
            update_customer(store.client, "business-a", store.customer_id, {"name": "Rejected edit"})
        elif action == "report":
            report_customer(store.client, "business-a", store.customer_id, "seller", {})
        elif action == "risk":
            change_customer_fraud_risk(store.client, "business-a", store.customer_id, {"riskLevel": "high"})
        elif action == "remove":
            remove_customer_from_fraud_list(store.client, "business-a", store.customer_id)
        else:
            create_order(store)
    assert store.documents == before


def test_invalid_contact_data_does_not_publish_a_revision(store):
    before = deepcopy(store.documents)
    with pytest.raises(ApiError):
        update_customer(store.client, "business-a", store.customer_id, {"name": ""})
    assert store.documents == before


@pytest.fixture
def api(store, monkeypatch):
    member = f"{BUSINESS}/members/member-a"
    store.put(member, {"role": "custom", "permissions": ["customers:read"], "status": "active"})
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.customers.get_firestore_client", lambda: store.client)
    return create_app({"TESTING": True}).test_client(), store, member


def test_version_endpoint_checks_membership_and_marker_without_scanning_customers(api):
    client, store, member = api
    store.client._firestore_api.batch_get_documents.reset_mock()
    store.client._firestore_api.run_query.reset_mock()
    response = client.get("/api/v1/businesses/business-a/customers/cache/version", headers=HEADERS)
    assert response.status_code == 200
    assert response.get_json() == {"revision": store.documents[REVISION]["revision"]}
    reads = store.client._firestore_api.batch_get_documents.call_args_list
    assert len(reads) == 2
    assert {call.kwargs["request"]["documents"][0].split("/documents/", 1)[1] for call in reads} == {member, REVISION}
    store.client._firestore_api.run_query.assert_not_called()


def test_version_endpoint_bootstraps_old_businesses_without_hiding_customer_named_version(api):
    client, store, _member = api
    store.documents.pop(REVISION)
    store.put(f"{BUSINESS}/customers/version", {"name": "Existing customer"})
    response = client.get("/api/v1/businesses/business-a/customers/cache/version", headers=HEADERS)
    assert response.get_json() == {"revision": "0"}
    response = client.get("/api/v1/businesses/business-a/customers/version", headers=HEADERS)
    assert response.status_code == 200
    assert response.get_json()["customer"]["name"] == "Existing customer"


@pytest.mark.parametrize("headers, tenant, permission, status, expected", [
    ({}, "business-a", "customers:read", "active", 401),
    (HEADERS, "business-b", "customers:read", "active", 403),
    (HEADERS, "business-a", "orders:read", "active", 403),
    (HEADERS, "business-a", "customers:manage", "active", 403),
    (HEADERS, "business-a", "customers:read", "inactive", 403),
])
def test_version_endpoint_rejects_wrong_tenant_removed_member_and_write_only_permission(api, headers, tenant, permission, status, expected):
    client, store, member = api
    store.put(member, {"role": "custom", "permissions": [permission], "status": status})
    response = client.get(f"/api/v1/businesses/{tenant}/customers/cache/version", headers=headers)
    assert response.status_code == expected
    assert "revision" not in response.get_json()
