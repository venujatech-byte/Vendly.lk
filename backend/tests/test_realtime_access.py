"""Exercise permission revocation and stale-write races without cloud access."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.api_core.datetime_helpers import DatetimeWithNanoseconds

from app.core.errors import ApiError
from app.services import realtime_access_service as access


# Restore the real implementations only in tests that provide an in-memory RTDB.
REAL_FUNCTIONS = {
    name: getattr(access, name)
    for name in (
        "sync_business_member_access", "changing_business_member_access",
        "sync_chat_access", "disable_realtime_user",
    )
}


class RealtimeReference:
    def __init__(self, store, path):
        self.store = store
        self.path = path

    def transaction(self, update):
        if self.store.fail:
            raise OSError("Permission store unavailable")
        value = update(deepcopy(self.store.values.get(self.path)))
        # Model an acknowledged-late commit whose callback runs again with its own value.
        if self.store.retry_committed:
            value = update(deepcopy(value))
        self.store.values[self.path] = deepcopy(value)
        return value

    def set(self, value):
        if self.store.fail:
            raise OSError("Permission store unavailable")
        self.store.values[self.path] = value


@pytest.fixture
def store(monkeypatch, mock_realtime_access):
    # The real sync functions may write only to this fresh in-memory permission store.
    for name, function in REAL_FUNCTIONS.items():
        monkeypatch.setattr(access, name, function)
    result = SimpleNamespace(values={}, fail=False, retry_committed=False)
    monkeypatch.setattr(access, "get_rtdb_reference", lambda path: RealtimeReference(result, path))
    return result


def snapshot(data, nanoseconds=1, document_id="chat-1"):
    # Distinct nanoseconds test ordering even when two reads share one microsecond.
    return SimpleNamespace(
        exists=data is not None, id=document_id,
        read_time=DatetimeWithNanoseconds(2026, 1, 1, nanosecond=nanoseconds),
        to_dict=lambda: deepcopy(data),
    )


def database_for(member):
    database = Mock()
    reference = database.collection.return_value.document.return_value.collection.return_value.document.return_value
    reference.get.return_value = member
    return database, reference


@pytest.mark.parametrize("member,chats,notifications", [
    ({"role": "owner", "status": "active"}, True, True),
    ({"role": "support", "status": "active", "permissions": ["customers:read"]}, True, True),
    ({"role": "viewer", "status": "active", "permissions": ["orders:read"]}, False, True),
    ({"role": "owner", "status": "inactive"}, False, False),
    (None, False, False),
])
def test_member_read_rights_follow_current_backend_permissions(store, member, chats, notifications):
    database, _ = database_for(snapshot(member))
    result = access.sync_business_member_access(database, "biz", "staff")
    assert result["chats"] is chats
    assert any(result["notifications"].values()) is notifications


def test_notification_scope_revocation_keeps_unaffected_readers_live(store):
    member = {"role": "custom", "status": "active", "permissions": ["orders:read", "customers:read"]}
    database, reference = database_for(snapshot(member, 1))
    access.sync_business_member_access(database, "biz", "staff")
    with access.changing_business_member_access(database, "biz", "staff", {"permissions": ["orders:read"]}):
        rights = store.values["_access/members/biz/staff"]["notifications"]
        assert rights == {"orders": True, "customers": False, "management": False}
        reference.get.return_value = snapshot({**member, "permissions": ["orders:read"]}, 2)
    assert store.values["_access/members/biz/staff"]["notifications"] == rights


def test_delayed_grant_cannot_overwrite_deleted_membership(store):
    database, reference = database_for(snapshot({"role": "owner", "status": "active"}, 1))
    old_snapshot = reference.get.return_value
    access.sync_business_member_access(database, "biz", "staff")
    reference.get.return_value = snapshot(None, 2)
    revoked = access.sync_business_member_access(database, "biz", "staff")
    reference.get.return_value = old_snapshot
    assert access.sync_business_member_access(database, "biz", "staff") == revoked
    assert revoked["chats"] is False


def test_membership_edit_blocks_refreshes_until_revocation_is_published(store):
    database, reference = database_for(snapshot({"role": "owner", "status": "active"}, 1))
    access.sync_business_member_access(database, "biz", "staff")
    with access.changing_business_member_access(database, "biz", "staff"):
        assert store.values["_access/members/biz/staff"]["pending"] is True
        with pytest.raises(ApiError) as error:
            access.sync_business_member_access(database, "biz", "staff")
        assert error.value.code == "realtime_access_conflict"
        reference.get.return_value = snapshot(None, 2)
    result = store.values["_access/members/biz/staff"]
    assert result["chats"] is False and not any(result["notifications"].values())
    assert "pending" not in result


def test_concurrent_membership_edits_cannot_steal_the_barrier(store):
    database, _ = database_for(snapshot({"role": "owner", "status": "active"}))
    with access.changing_business_member_access(database, "biz", "staff"):
        change_id = store.values["_access/members/biz/staff"]["changeId"]
        with pytest.raises(ApiError):
            with access.changing_business_member_access(database, "biz", "staff"):
                pytest.fail("A concurrent membership write was allowed")
        assert store.values["_access/members/biz/staff"]["changeId"] == change_id
    assert store.values["_access/members/biz/staff"]["chats"] is True


def test_unchanged_permissions_keep_live_reads_during_an_edit(store):
    database, _ = database_for(snapshot({"role": "owner", "status": "active"}))
    access.sync_business_member_access(database, "biz", "staff")
    with access.changing_business_member_access(database, "biz", "staff", {"status": "active"}):
        rights = store.values["_access/members/biz/staff"]
        assert rights["chats"] is True and all(rights["notifications"].values())


def test_retry_after_committed_transaction_is_idempotent(store):
    database, _ = database_for(snapshot({"role": "owner", "status": "active"}))
    store.retry_committed = True
    with access.changing_business_member_access(database, "biz", "staff", {"status": "active"}):
        assert store.values["_access/members/biz/staff"]["pending"] is True
    assert store.values["_access/members/biz/staff"]["chats"] is True


def test_failed_firestore_edit_restores_only_its_actual_membership(store):
    database, _ = database_for(snapshot({"role": "owner", "status": "active"}))
    with pytest.raises(ValueError, match="write failed"):
        with access.changing_business_member_access(database, "biz", "staff"):
            raise ValueError("write failed")
    assert store.values["_access/members/biz/staff"]["chats"] is True


def test_permission_store_failure_blocks_the_write_before_it_starts(store):
    database, _ = database_for(snapshot({"role": "owner", "status": "active"}))
    store.fail = True
    with pytest.raises(ApiError) as error:
        with access.changing_business_member_access(database, "biz", "staff"):
            pytest.fail("Firestore was allowed to change before realtime revocation")
    assert error.value.status_code == 503


def test_failed_final_sync_leaves_access_blocked_for_explicit_repair(store):
    database, _ = database_for(snapshot(None))
    with pytest.raises(ApiError) as error:
        with access.changing_business_member_access(database, "biz", "staff"):
            store.fail = True
    assert error.value.status_code == 503
    assert store.values["_access/members/biz/staff"]["pending"] is True
    assert store.values["_access/members/biz/staff"]["chats"] is False
    assert not any(store.values["_access/members/biz/staff"]["notifications"].values())


def test_delayed_chat_snapshot_cannot_restore_a_deleted_chat(store):
    old = snapshot({"businessId": "biz", "customerUid": "customer"}, 1)
    access.sync_chat_access(old)
    tombstone = access.sync_chat_access(snapshot(None, 2))
    assert access.sync_chat_access(old) == tombstone
    assert tombstone["customerUid"] == "" and tombstone["businessId"] == ""


def test_chat_permissions_use_committed_owner_and_tenant(store):
    result = access.sync_chat_access(snapshot({"businessId": "biz", "customerUid": "guest"}))
    assert result["businessId"] == "biz" and result["customerUid"] == "guest"


def test_account_deletion_disables_remaining_realtime_tokens(store):
    access.disable_realtime_user("customer")
    assert store.values["_access/disabledUsers/customer"] is True


def test_missing_permission_store_fails_closed(store, monkeypatch):
    monkeypatch.setattr(access, "get_rtdb_reference", lambda path: None)
    with pytest.raises(ApiError) as error:
        access.disable_realtime_user("customer")
    assert error.value.status_code == 503


@pytest.mark.parametrize("operation", ["deactivate", "remove"])
def test_staff_service_revokes_reads_before_changing_firestore(store, monkeypatch, operation):
    from app.services import member_service

    # Exercise the actual staff mutator with fake Firestore and the real permission barrier.
    database = Mock()
    business = database.collection.return_value.document.return_value
    business.get.return_value.exists = True
    business.get.return_value.to_dict.return_value = {"ownerUid": "owner"}
    member = business.collection.return_value.document.return_value
    state = {"member": {"role": "support", "status": "active", "permissions": ["customers:read"]}, "reads": 0}

    def read_member():
        state["reads"] += 1
        return snapshot(state["member"], state["reads"])

    def write_member(changes=None):
        assert store.values["_access/members/biz/staff"]["pending"] is True
        if changes is None:
            state["member"] = None
        else:
            state["member"].update(changes)

    member.get.side_effect = read_member
    member.update.side_effect = write_member
    member.delete.side_effect = write_member
    monkeypatch.setattr(member_service, "list_members", lambda *args: [{"id": "staff", **(state["member"] or {})}])
    access.sync_business_member_access(database, "biz", "staff")

    # Both paths must leave the committed removal/inactivation mirrored as denied reads.
    if operation == "deactivate":
        member_service.update_member(database, "biz", "staff", {"status": "inactive"}, updated_by="owner")
    else:
        member_service.remove_member(database, "biz", "staff", removed_by="owner")
    assert store.values["_access/members/biz/staff"]["chats"] is False
    assert not any(store.values["_access/members/biz/staff"]["notifications"].values())
