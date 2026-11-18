"""Guest contact details must never come from a phone-matched customer profile."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from firestore_memory import MemoryFirestore
from app.core.errors import ApiError
from app.services import customer_portal_service as portal
from app.services import email_service, order_service, public_chat_service as chat


ADDRESS = {"line1": "1 Submitted Road", "city": "Matara", "district": "Matara"}
PRIVATE_CUSTOMER = {
    "id": "customer-a", "status": "active", "name": "Private Profile Name",
    "normalizedPhone": "94712345678", "normalizedSecondaryPhone": "94776543210",
    "email": "private-profile@example.test", "riskLevel": "high",
    "defaultAddress": {"line1": "Private Profile Road", "city": "Colombo", "district": "Colombo"},
}


@pytest.fixture
def checkout(monkeypatch):
    # Exercise the shared order transaction and mock only optional external delivery services.
    store = MemoryFirestore()
    business = "businesses/business-a"
    store.put(business, {"nextOrderSequence": 1, "orderPrefix": "VD"})
    store.put(f"{business}/customers/customer-a", PRIVATE_CUSTOMER)
    store.put(f"{business}/couriers/courier-a", {"status": "active", "nextWaybillSequence": 1})
    store.put(f"{business}/products/product-a", {
        "name": "Product", "status": "active", "totalStock": 2, "reservedStock": 0,
        "availableStock": 2, "lowStockThreshold": 0, "variantSummaries": [],
    })
    store.put(f"{business}/productVariants/variant-a", {
        "productId": "product-a", "status": "active", "sku": "SKU-A",
        "stockOnHand": 2, "stockReserved": 0, "stockAvailable": 2,
        "costPriceMinor": 1000, "sellingPriceMinor": 2000,
    })
    session = Mock()
    monkeypatch.setattr(chat, "authorize_public_chat_session", lambda *a: (session, {"businessId": "business-a"}))
    lookup = Mock(return_value=[deepcopy(PRIVATE_CUSTOMER)])
    monkeypatch.setattr(chat, "list_customers", lookup)
    monkeypatch.setattr(order_service, "choose_courier", lambda *a: {"id": "courier-a"})
    monkeypatch.setattr(order_service, "calculate_delivery_fee", lambda *a: 100)
    monkeypatch.setattr("app.services.operations_service.dispatch_notification", Mock())
    send = Mock()
    monkeypatch.setattr(email_service, "send_order_confirmation_email", send)
    return store, session, lookup, send


def place(checkout, email=""):
    store, _, _, _ = checkout
    return chat.create_public_chat_order(store.client, "session-a", "secret", {
        "customer": {"name": "Submitted Name", "phoneNumber": "0712345678", "email": email, "address": ADDRESS},
        "courierId": "courier-a", "items": [{"variantId": "variant-a", "quantity": 1}],
    })


@pytest.mark.parametrize("email", ["", "submitted@example.test"])
def test_phone_matching_cannot_disclose_or_change_private_contacts(checkout, email):
    store, session, lookup, send = checkout
    confirmation = place(checkout, email)
    assert confirmation["customerSnapshot"] == {
        "name": "Submitted Name", "normalizedPhone": "94712345678",
        "email": email, "secondaryPhoneNumber": "",
    }
    assert confirmation["deliveryAddress"]["line1"] == ADDRESS["line1"]
    assert "riskLevel" not in confirmation["customerSnapshot"]
    customer_path = "businesses/business-a/customers/customer-a"
    assert store.documents[customer_path]["email"] == PRIVATE_CUSTOMER["email"]
    assert store.documents[customer_path]["name"] == PRIVATE_CUSTOMER["name"]
    assert store.documents[customer_path]["defaultAddress"] == PRIVATE_CUSTOMER["defaultAddress"]
    summary = session.reference.update.call_args.args[0]["customerSummary"]
    assert summary["name"] == "Submitted Name"
    assert summary["email"] == email
    assert summary["secondaryPhoneNumber"] == ""
    lookup.assert_called_once_with(store.client, "business-a", phone="94712345678")
    waybill = next(value for path, value in store.documents.items() if "/waybills/" in path)
    assert waybill["customerSnapshot"]["name"] == "Submitted Name"
    if email:
        assert send.call_args.kwargs["recipient_email"] == email
    else:
        send.assert_not_called()


@pytest.mark.parametrize("missing", ["name", "phoneNumber", "address"])
def test_checkout_requires_fresh_details_before_customer_lookup(checkout, missing):
    store, _, lookup, _ = checkout
    details = {"name": "Submitted Name", "phoneNumber": "0712345678", "address": ADDRESS}
    del details[missing]
    with pytest.raises(ApiError) as error:
        chat.create_public_chat_order(store.client, "session-a", "secret", {"customer": details})
    assert error.value.status_code == 422
    lookup.assert_not_called()
    assert store.commits == 0


def test_guest_email_updates_only_the_owned_order(checkout, monkeypatch):
    store, _, lookup, send = checkout
    customer_path = "businesses/business-a/customers/customer-a"
    store.put(customer_path, {**store.documents[customer_path], "email": ""})
    lookup.return_value[0]["email"] = ""
    order = place(checkout)
    path = f"businesses/business-a/orders/{order['id']}"
    store.put(path, {**store.documents[path], "customerUid": "guest-a"})
    monkeypatch.setattr(portal, "resolve_store_business_id", lambda *a: "business-a")
    before = deepcopy(store.documents[customer_path])
    portal.update_order_guest_email(
        store.client, "store", order["id"], "new@example.test", customer_uid="guest-a",
    )
    assert store.documents[customer_path] == before
    assert store.documents[path]["customerSnapshot"]["email"] == "new@example.test"
    assert send.call_args.kwargs["recipient_email"] == "new@example.test"


def test_checkout_cannot_fill_a_matched_profiles_empty_email(checkout):
    store, _, lookup, _ = checkout
    path = "businesses/business-a/customers/customer-a"
    store.put(path, {**store.documents[path], "email": ""})
    lookup.return_value[0]["email"] = ""
    place(checkout, email="submitted@example.test")
    assert store.documents[path]["email"] == ""


def test_guest_email_cannot_modify_an_order_after_ownership_transfer(checkout, monkeypatch):
    store, _, _, send = checkout
    order = place(checkout)
    path = f"businesses/business-a/orders/{order['id']}"
    store.put(path, {**store.documents[path], "customerUid": "guest-a"})
    monkeypatch.setattr(portal, "resolve_store_business_id", lambda *a: "business-a")
    store.before_commit = lambda current: current.put(path, {**current.documents[path], "customerUid": "signed-in-account"})
    with pytest.raises(ApiError) as error:
        portal.update_order_guest_email(
            store.client, "store", order["id"], "stale-guest@example.test", customer_uid="guest-a",
        )
    assert error.value.status_code == 409
    assert store.documents[path]["customerSnapshot"]["email"] == ""
    send.assert_not_called()


def test_dashboard_order_keeps_its_existing_contact_behavior(checkout):
    store, _, _, send = checkout
    result = order_service.create_order(store.client, "business-a", "seller-a", {
        "customerId": "customer-a", "courierId": "courier-a",
        "source": "chatbot",
        "items": [{"variantId": "variant-a", "quantity": 1}],
    })
    assert result["customerSnapshot"]["name"] == PRIVATE_CUSTOMER["name"]
    assert chat.public_order_confirmation(result)["customerName"] == PRIVATE_CUSTOMER["name"]
    assert result["deliveryAddress"]["line1"] == PRIVATE_CUSTOMER["defaultAddress"]["line1"]
    assert send.call_args.kwargs["recipient_email"] == PRIVATE_CUSTOMER["email"]


def test_legacy_guest_contacts_are_hidden_without_changing_internal_records():
    order = {
        "id": "legacy-order", "createdBy": "public-chat:old-session", "source": "chatbot",
        "customerSnapshot": PRIVATE_CUSTOMER, "deliveryAddress": PRIVATE_CUSTOMER["defaultAddress"],
        "customerEmail": PRIVATE_CUSTOMER["email"], "customerName": PRIVATE_CUSTOMER["name"],
        "totalAmountMinor": 2100, "fulfilmentStatus": "confirmed",
    }
    before = deepcopy(order)
    result = chat.public_order_confirmation(order)
    assert not any(result["customerSnapshot"].values())
    assert result["customerEmail"] == result["customerName"] == ""
    assert result["deliveryAddress"] == {}
    assert result["totalAmountMinor"] == 2100
    assert result["fulfilmentStatus"] == "confirmed"
    assert order == before


def test_legacy_receipt_to_submitted_address_does_not_disclose_old_contacts(monkeypatch):
    send = Mock(return_value=True)
    monkeypatch.setattr(email_service, "send_brevo_email", send)
    order = {
        "id": "legacy-order", "createdBy": "public-chat:old-session",
        "customerSnapshot": PRIVATE_CUSTOMER, "deliveryAddress": PRIVATE_CUSTOMER["defaultAddress"],
    }
    assert email_service.send_order_confirmation_email(order, {"name": "Shop"}, recipient_email="submitted@example.test")
    html = send.call_args.kwargs["html_content"]
    assert PRIVATE_CUSTOMER["name"] not in html
    assert PRIVATE_CUSTOMER["email"] not in html
    assert PRIVATE_CUSTOMER["defaultAddress"]["line1"] not in html
    assert send.call_args.kwargs["to_email"] == "submitted@example.test"
    send.reset_mock()
    assert not email_service.send_customer_order_status_email(order, {"name": "Shop"}, "confirmed", recipient_email=PRIVATE_CUSTOMER["email"])
    send.assert_not_called()
