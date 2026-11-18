"""Exercise malformed requests through real authentication and request-shape boundaries."""

import json
from unittest.mock import Mock

import pytest

from app import create_app
from app.core.errors import ApiError
from app.services.analytics_service import record_ledger_entry
from firestore_memory import MemoryFirestore


ROUTES = [
    ("PATCH", "/businesses/business-a/analytics/monthly-target", "update_monthly_revenue_target", 200),
    ("POST", "/businesses/business-a/analytics/ledger/entries", "record_ledger_entry", 201),
    ("PATCH", "/businesses/business-a/analytics/cod-reconciliation/order-a", "update_cod_settlement", 200),
    ("POST", "/businesses/business-a/analytics/cod-reconciliation/bulk", "update_bulk_cod_settlements", 200),
    ("POST", "/public/chat/sessions/session-a/claim", "claim_public_chat_session", 200),
]


@pytest.fixture
def api(monkeypatch):
    # Stub cloud I/O while keeping the actual auth, membership and JSON validation code active.
    database = Mock()
    membership = database.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value
    membership.exists = True
    membership.to_dict.return_value = {"role": "owner", "status": "active"}
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: database)
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "owner-a"}))
    monkeypatch.setattr("app.api.analytics.get_firestore_client", lambda: database)
    monkeypatch.setattr("app.api.public.get_firestore_client", lambda: database)
    services = {}
    for _, path, name, _ in ROUTES:
        services[name] = Mock(return_value=123 if name == "update_monthly_revenue_target" else {})
        module = "app.api.public" if path.startswith("/public/") else "app.api.analytics"
        monkeypatch.setattr(f"{module}.{name}", services[name])
    return create_app({"TESTING": True}).test_client(), services


@pytest.mark.parametrize("method, path, service, _status", ROUTES)
@pytest.mark.parametrize("payload", [[1], [], "invalid", True, False, 1])
def test_non_object_body_is_rejected_before_business_service(api, method, path, service, _status, payload):
    client, services = api
    response = client.open(
        f"/api/v1{path}", method=method, data=json.dumps(payload), content_type="application/json",
        headers={"Authorization": "Bearer synthetic-token"},
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"
    services[service].assert_not_called()


@pytest.mark.parametrize("method, path, service, status", ROUTES)
def test_object_bodies_keep_existing_service_contract(api, method, path, service, status):
    client, services = api
    payload = {"monthlyTargetMinor": 123, "email": "synthetic@example.test"}
    response = client.open(
        f"/api/v1{path}", method=method, json=payload,
        headers={"Authorization": "Bearer synthetic-token"},
    )
    assert response.status_code == status
    services[service].assert_called_once()
    if service == "claim_public_chat_session":
        assert services[service].call_args.kwargs["customer_email"] == payload["email"]
    else:
        assert payload in services[service].call_args.args


@pytest.mark.parametrize("field, value", [
    ("amount", "Infinity"), ("amount", "NaN"), ("amount", "1e1000"),
    ("amountMinor", float("inf")), ("amountMinor", float("nan")),
    ("amountMinor", 2**63), ("amount", "92233720368547759"),
])
def test_invalid_ledger_amount_fails_before_database_access(field, value):
    database = Mock()
    with pytest.raises(ApiError) as error:
        record_ledger_entry(database, "business-a", {field: value, "description": "Synthetic entry"})
    assert error.value.code == "validation_error"
    assert error.value.status_code == 422
    database.collection.assert_not_called()


@pytest.mark.parametrize("payload, expected", [
    ({"amount": "1.005"}, 100),
    ({"amount": "1.015"}, 101),
    ({"amountMinor": 2**63 - 1}, 2**63 - 1),
])
def test_valid_ledger_amounts_keep_existing_rounding_and_storage(payload, expected):
    # Ledger uses its existing float/round path; this fix must not silently switch its rounding policy.
    store = MemoryFirestore()
    store.put("businesses/business-a", {})
    entry = record_ledger_entry(store.client, "business-a", {**payload, "description": "Synthetic entry"})
    assert entry["amountMinor"] == expected
