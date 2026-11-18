"""Enforce ledger write roles through the real Flask authentication and tenant gates."""

from unittest.mock import Mock

import pytest

from app import create_app


@pytest.fixture
def ledger_api(monkeypatch):
    # Replace only cloud reads and ledger services; keep route authorization active.
    database = Mock()
    snapshot = database.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value
    snapshot.exists = True
    snapshot.to_dict.return_value = {"role": "viewer", "permissions": ["analytics:read"], "status": "active"}
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: database)
    monkeypatch.setattr("app.api.analytics.get_firestore_client", lambda: database)
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "staff-a"}))
    create = Mock(return_value={"id": "entry-a"})
    delete = Mock(return_value={"id": "entry-a", "deleted": True})
    read = Mock(return_value={"entries": []})
    monkeypatch.setattr("app.api.analytics.record_ledger_entry", create)
    monkeypatch.setattr("app.api.analytics.delete_ledger_entry", delete)
    monkeypatch.setattr("app.api.analytics.get_business_ledger", read)
    client = create_app({"TESTING": True}).test_client()
    return client, database, snapshot, create, delete, read


def ledger_write(client, method, headers=None):
    # Use the same tenant path for both write routes and an attempted client-supplied role.
    path = "/api/v1/businesses/business-a/analytics/ledger/entries"
    if method == "DELETE":
        path += "/entry-a"
    return client.open(
        path, method=method, json={"role": "owner", "userId": "owner-a"},
        headers=headers if headers is not None else {"Authorization": "Bearer test-token"},
    )


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("role, permissions, allowed", [
    ("owner", [], True),
    ("admin", ["*"], True),
    ("admin", ["analytics:read"], True),
    ("admin", ["orders:read"], False),
    ("viewer", ["analytics:read"], False),
    ("viewer", ["*"], False),
    ("custom", ["analytics:*"], False),
    ("custom", ["*"], False),
    ("order_manager", ["*"], False),
    ("inventory_manager", ["*"], False),
    ("support", ["*"], False),
])
def test_ledger_writes_require_owner_or_admin(ledger_api, method, role, permissions, allowed):
    client, _, snapshot, create, delete, _ = ledger_api
    snapshot.to_dict.return_value.update(role=role, permissions=permissions)
    response = ledger_write(client, method)
    expected_status = (201 if method == "POST" else 200) if allowed else 403
    assert response.status_code == expected_status
    if allowed:
        if method == "POST":
            assert create.call_args.kwargs["user_id"] == "staff-a"
            delete.assert_not_called()
        else:
            delete.assert_called_once()
            create.assert_not_called()
    else:
        create.assert_not_called()
        delete.assert_not_called()


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("membership", ["inactive", "absent"])
def test_inactive_or_missing_tenant_membership_cannot_write(ledger_api, method, membership):
    client, database, snapshot, create, delete, _ = ledger_api
    snapshot.to_dict.return_value.update(role="owner", status="inactive" if membership == "inactive" else "active")
    snapshot.exists = membership != "absent"
    assert ledger_write(client, method).status_code == 403
    # The lookup must use the URL tenant and verified UID, not caller-supplied identity fields.
    database.collection.return_value.document.assert_called_once_with("business-a")
    database.collection.return_value.document.return_value.collection.return_value.document.assert_called_once_with("staff-a")
    create.assert_not_called()
    delete.assert_not_called()


@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_ledger_writes_require_authentication(ledger_api, method):
    client, database, _, create, delete, _ = ledger_api
    assert ledger_write(client, method, headers={}).status_code == 401
    database.collection.assert_not_called()
    create.assert_not_called()
    delete.assert_not_called()


def test_viewer_keeps_ledger_read_access(ledger_api):
    client, _, _, create, delete, read = ledger_api
    response = client.get(
        "/api/v1/businesses/business-a/analytics/ledger",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"ledger": {"entries": []}}
    read.assert_called_once()
    create.assert_not_called()
    delete.assert_not_called()
