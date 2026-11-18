"""Read grants cannot become writes through normalization or legacy aliases."""

from unittest.mock import Mock

import pytest

from app import create_app
from app.core.authorization import membership_has_permission
from app.core.errors import ApiError
from app.services.business_assistant_service import require_permission
from app.services.member_service import MODULE_PERMISSIONS, ROLE_PERMISSIONS, validate_member_payload


@pytest.mark.parametrize("module", [*MODULE_PERMISSIONS, "messages"])
def test_granular_read_stays_read_only(module):
    member = validate_member_payload(
        {"role": "custom", "permissions": [f"{module}:read"]}, require_email=False,
    )
    assert member["permissions"] == [f"{module}:read"]
    assert membership_has_permission(member, f"{module}:read")
    assert not membership_has_permission(member, f"{module}:manage")
    assert not membership_has_permission(member, f"{module}:*")


@pytest.mark.parametrize("module", [*MODULE_PERMISSIONS, "messages"])
def test_existing_bare_alias_does_not_widen_granular_read(module):
    member = {"role": "custom", "permissions": [module, f"{module}:read"]}
    assert membership_has_permission(member, f"{module}:read")
    assert not membership_has_permission(member, f"{module}:manage")
    assert not membership_has_permission(member, f"{module}:*")


@pytest.mark.parametrize("module", MODULE_PERMISSIONS)
def test_explicit_full_module_selections_keep_their_access(module):
    member = validate_member_payload(
        {"role": "custom", "permissions": [module]}, require_email=False,
    )
    assert membership_has_permission(member, f"{module}:read")
    assert membership_has_permission(member, f"{module}:manage")


@pytest.mark.parametrize("permissions", [["orders"], ["orders:*"], ["*"], ["orders", "orders:read", "orders:*"]])
def test_explicit_full_access_remains_valid(permissions):
    assert membership_has_permission({"role": "custom", "permissions": permissions}, "orders:manage")


@pytest.mark.parametrize("role", ROLE_PERMISSIONS)
@pytest.mark.parametrize("overrides", [["*"], ["orders", "inventory", "analytics"], [], "invalid"])
def test_preset_roles_ignore_client_permission_overrides(role, overrides):
    # A forged request cannot widen a preset even if an older form sends module IDs.
    member = validate_member_payload({"role": role, "permissions": overrides}, require_email=False)
    assert member["permissions"] == ROLE_PERMISSIONS[role]
    if role == "viewer":
        assert membership_has_permission(member, "orders:read")
        assert not membership_has_permission(member, "orders:manage")


@pytest.mark.parametrize("payload", [{}, {"status": "inactive"}])
def test_unrelated_member_updates_preserve_existing_permissions(monkeypatch, payload):
    from app.services import member_service

    # Exercise the update service while keeping all persistence and realtime calls mocked.
    database = Mock()
    business = database.collection.return_value.document.return_value
    business.get.return_value.exists = True
    business.get.return_value.to_dict.return_value = {"ownerUid": "owner-a"}
    member_ref = business.collection.return_value.document.return_value
    member_ref.get.return_value.exists = True
    original = {"role": "viewer", "permissions": ["orders", "orders:*"], "status": "active"}
    member_ref.get.return_value.to_dict.return_value = original
    monkeypatch.setattr(member_service, "list_members", lambda *args: [{"id": "staff-a", **original}])
    member_service.update_member(database, "business-a", "staff-a", payload, updated_by="owner-a")
    changes = member_ref.update.call_args.args[0]
    assert "role" not in changes
    assert "permissions" not in changes


def test_reselecting_a_preset_applies_server_grants(monkeypatch):
    from app.services import member_service

    database = Mock()
    business = database.collection.return_value.document.return_value
    business.get.return_value.exists = True
    business.get.return_value.to_dict.return_value = {"ownerUid": "owner-a"}
    member_ref = business.collection.return_value.document.return_value
    member_ref.get.return_value.exists = True
    member_ref.get.return_value.to_dict.return_value = {"role": "custom", "permissions": ["*"]}
    monkeypatch.setattr(member_service, "list_members", lambda *args: [{"id": "staff-a"}])
    member_service.update_member(
        database, "business-a", "staff-a", {"role": "viewer", "permissions": ["*"]}, updated_by="owner-a",
    )
    changes = member_ref.update.call_args.args[0]
    assert changes["role"] == "viewer"
    assert changes["permissions"] == ROLE_PERMISSIONS["viewer"]


def test_granular_modules_do_not_affect_each_other():
    member = {"role": "custom", "permissions": ["orders", "orders:read", "inventory", "inventory:manage"]}
    assert membership_has_permission(member, "orders:read")
    assert membership_has_permission(member, "inventory:manage")
    assert not membership_has_permission(member, "orders:manage")
    assert not membership_has_permission(member, "inventory:read")
    assert not membership_has_permission(member, "customers:read")


def test_assistant_rejects_write_from_existing_read_only_member():
    member = {"role": "custom", "permissions": ["inventory", "inventory:read"]}
    require_permission(member, "inventory:read")
    with pytest.raises(ApiError) as error:
        require_permission(member, "inventory:manage")
    assert error.value.status_code == 403


@pytest.mark.parametrize("permissions, status", [
    (["orders", "orders:read"], 403),
    (["orders:read"], 403),
    (["orders", "orders:*", "orders:read", "orders:manage"], 201),
])
def test_write_endpoint_enforces_actual_grants(monkeypatch, permissions, status):
    # Use the real route decorators and prove denied requests never reach the writer.
    database = Mock()
    member = database.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value
    member.exists = True
    member.to_dict.return_value = {"role": "custom", "status": "active", "permissions": permissions}
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: database)
    monkeypatch.setattr("app.api.operations.get_firestore_client", lambda: database)
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "staff-a"}))
    writer = Mock(return_value={"id": "report-a"})
    monkeypatch.setattr("app.api.operations.create_fraud_report", writer)
    response = create_app({"TESTING": True}).test_client().post(
        "/api/v1/businesses/business-a/orders/order-a/fraud-report",
        headers={"Authorization": "Bearer test-token"}, json={"reason": "Test"},
    )
    assert response.status_code == status
    if status == 403:
        writer.assert_not_called()
    else:
        writer.assert_called_once()
