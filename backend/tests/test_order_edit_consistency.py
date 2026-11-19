"""Order edits and their waybill/cache metadata must reflect one accepted order version."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import PermissionDenied

from firestore_memory import MemoryFirestore
from app import create_app
from app.core.errors import ApiError
from app.services.order_service import update_order

BUSINESS = "businesses/business-a"
ORDER = f"{BUSINESS}/orders/order-a"
WAYBILL = f"{BUSINESS}/waybills/order-a"
REVISION = f"{BUSINESS}/_cacheVersions/orders"


@pytest.fixture
def store():
    # Keep real SDK batch/precondition behavior while isolating all reads and writes in memory.
    store = MemoryFirestore()
    store.put(BUSINESS, {})
    store.put(ORDER, {
        "orderNumber": "VD-SYNTHETIC", "fulfilmentStatus": "needs-confirmation",
        "customerSnapshot": {"name": "Old contact", "normalizedPhone": "94700000123", "email": "old@example.test"},
        "deliveryAddress": {"line1": "Old address", "city": "Colombo", "district": "Colombo"},
        "courierId": "courier-old", "courierSnapshot": {"id": "courier-old", "name": "Old courier"},
        "waybillNumber": "WB-OLD", "totalWeightGrams": 750,
    })
    store.put(WAYBILL, {
        "waybillNumber": "WB-OLD", "preservedField": "Keep this",
        "customerSnapshot": {"name": "Old label contact", "legacyField": "Old contact data"},
        "courierSnapshot": {"id": "courier-old", "legacyField": "Old courier data"},
        "deliveryAddress": {"line1": "Old label address", "line2": "Old second line"},
    })
    store.put(REVISION, {"revision": "previous"})
    store.put(f"{BUSINESS}/couriers/courier-new", {"name": "New courier", "status": "active"})
    return store


def combined_edit():
    return {
        "customerName": "New contact", "phoneNumber": "94700000456", "email": "new@example.test",
        "deliveryAddress": {"line1": "New address", "city": "Kandy", "district": "Kandy"},
        "courierId": "courier-new", "waybillNumber": "wb-new",
    }


@pytest.mark.parametrize("courier_id", ["courier-new", ""])
def test_combined_edit_saves_the_edited_contact_address_and_courier_into_the_waybill(store, courier_id):
    result = update_order(store.client, "business-a", "order-a", "seller", {**combined_edit(), "courierId": courier_id})
    saved = store.documents[WAYBILL]
    assert result["customerSnapshot"]["name"] == "New contact"
    for field in ("customerSnapshot", "deliveryAddress", "courierId", "courierSnapshot", "waybillNumber", "orderNumber", "totalWeightGrams"):
        assert saved[field] == result[field]
    assert saved["preservedField"] == "Keep this"
    assert saved["waybillNumber"] == "WB-NEW"
    assert store.documents[REVISION]["revision"] != "previous"
    assert store.commits == 1
    # Whole-map masks prevent real Firestore from retaining old nested address/contact fields.
    writes = store.client._firestore_api.commit.call_args.kwargs["request"]["writes"]
    waybill_write = next(write for write in writes if write.update.name.endswith(f"/documents/{WAYBILL}"))
    assert {"customerSnapshot", "courierSnapshot", "deliveryAddress"} <= set(waybill_write.update_mask.field_paths)


@pytest.mark.parametrize("changes, editable_statuses", [
    ({"fulfilmentStatus": "confirmed"}, {"needs-confirmation"}),
    ({"customerSnapshot": {"name": "Concurrent contact", "email": "other@example.test"}}, None),
])
def test_stale_guest_and_seller_edits_cannot_overwrite_a_concurrent_order_version(store, changes, editable_statuses):
    before_waybill = deepcopy(store.documents[WAYBILL])
    def concurrent(current):
        current.put(ORDER, {**current.documents[ORDER], **changes})

    store.before_commit = concurrent
    with pytest.raises(ApiError) as error:
        update_order(store.client, "business-a", "order-a", "public-chat:synthetic" if editable_statuses else "seller", combined_edit(), editable_statuses=editable_statuses)
    assert error.value.code == "order_changed"
    assert error.value.status_code == 409
    for field, value in changes.items():
        assert store.documents[ORDER][field] == value
    assert store.documents[WAYBILL] == before_waybill
    assert store.documents[REVISION] == {"revision": "previous"}
    assert store.commits == 0


def test_waybill_commit_failure_cannot_leave_the_order_or_cache_partially_updated(store):
    before = deepcopy(store.documents)

    def reject_waybill(request, **kwargs):
        names = {write.update.name.split("/documents/", 1)[1] for write in request["writes"]}
        if WAYBILL in names:
            raise PermissionDenied("Synthetic denied waybill write")
        return store.commit(request, **kwargs)

    store.client._firestore_api.commit.side_effect = reject_waybill
    with pytest.raises(PermissionDenied):
        update_order(store.client, "business-a", "order-a", "seller", combined_edit())
    assert store.documents == before


def test_confirmed_guest_order_still_uses_the_existing_editability_error(store):
    store.put(ORDER, {**store.documents[ORDER], "fulfilmentStatus": "confirmed"})
    before = deepcopy(store.documents)
    with pytest.raises(ApiError) as error:
        update_order(store.client, "business-a", "order-a", "public-chat:synthetic", {"customerName": "Change"}, editable_statuses={"needs-confirmation"})
    assert error.value.code == "order_not_editable"
    assert store.documents == before
    store.client._firestore_api.commit.assert_not_called()


def test_api_returns_a_clean_conflict_for_an_interleaved_edit(store, monkeypatch):
    store.put(f"{BUSINESS}/members/member-a", {"role": "owner", "status": "active"})
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.orders.get_firestore_client", lambda: store.client)
    store.before_commit = lambda current: current.put(ORDER, {**current.documents[ORDER], "privateNote": "Concurrent note"})
    response = create_app({"TESTING": True}).test_client().patch(
        "/api/v1/businesses/business-a/orders/order-a", json=combined_edit(),
        headers={"Authorization": "Bearer synthetic-token"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "order_changed"
    assert store.documents[ORDER]["privateNote"] == "Concurrent note"
    assert store.documents[REVISION]["revision"] == "previous"
