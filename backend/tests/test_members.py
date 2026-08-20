import pytest

from app.core.errors import ApiError
from app.services.member_service import ROLE_PERMISSIONS, validate_member_payload
from app.core.authorization import membership_has_permission


def test_staff_role_maps_to_explicit_permissions():
    member = validate_member_payload(
        {"email": "staff@example.com", "role": "inventory_manager"},
    )
    assert member["permissions"] == ROLE_PERMISSIONS["inventory_manager"]
    assert "inventory:*" in member["permissions"]


def test_owner_cannot_be_assigned_through_staff_endpoint():
    with pytest.raises(ApiError):
        validate_member_payload(
            {"email": "staff@example.com", "role": "owner"},
        )


def test_role_wildcard_grants_resource_permission():
    membership = {"role": "order_manager", "permissions": ["orders:*"]}
    assert membership_has_permission(membership, "orders:read")
    assert membership_has_permission(membership, "orders:manage")
    assert not membership_has_permission(membership, "inventory:manage")


def test_owner_always_has_permission():
    assert membership_has_permission({"role": "owner", "permissions": ["*"]}, "staff:manage")
