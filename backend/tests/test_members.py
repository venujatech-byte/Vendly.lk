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


def test_non_owner_cannot_invite_admin():
    from app.services.member_service import add_member

    class MockDoc:
        exists = True

        def to_dict(self):
            return {"ownerUid": "owner-1"}

    class MockRef:
        def get(self):
            return MockDoc()

        def document(self, _id):
            return self

        def collection(self, _id):
            return self

    class MockDb:
        def collection(self, _id):
            return MockRef()

    with pytest.raises(ApiError) as error:
        add_member(
            MockDb(),
            "biz-1",
            invited_by="admin-peer",
            payload={"email": "newadmin@example.com", "role": "admin"},
        )
    assert error.value.code == "forbidden"


def test_non_owner_cannot_update_admin_member():
    from app.services.member_service import update_member

    class MockBusinessDoc:
        exists = True

        def to_dict(self):
            return {"ownerUid": "owner-1"}

    class MockMemberDoc:
        exists = True

        def to_dict(self):
            return {"role": "admin", "uid": "admin-target"}

    class MockRef:
        def __init__(self, doc):
            self._doc = doc

        def get(self):
            return self._doc

        def document(self, doc_id):
            if doc_id == "admin-target":
                return MockRef(MockMemberDoc())
            return MockRef(MockBusinessDoc())

        def collection(self, _id):
            return self

    class MockDb:
        def collection(self, _id):
            return MockRef(MockBusinessDoc())

    with pytest.raises(ApiError) as error:
        update_member(
            MockDb(),
            "biz-1",
            "admin-target",
            {"status": "inactive"},
            updated_by="admin-peer",
        )
    assert error.value.code == "forbidden"
