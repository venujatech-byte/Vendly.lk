"""Check migration planning and safety gates using fake databases only."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from scripts import backfill_realtime_access as migration
from app.services import realtime_access_service as access


@pytest.fixture
def migration_data():
    # Mix current and removed identities so backfill must include denial tombstones.
    database = Mock()
    businesses = Mock()
    sessions = Mock()
    database.collection.side_effect = {"businesses": businesses, "publicChatSessions": sessions}.__getitem__
    businesses.stream.return_value = [SimpleNamespace(id="biz")]
    current_business = Mock()
    removed_business = Mock()
    businesses.document.side_effect = {"biz": current_business, "old-biz": removed_business}.__getitem__
    current_business.collection.return_value.stream.return_value = [SimpleNamespace(id="active")]
    removed_business.collection.return_value.stream.return_value = []
    sessions.stream.return_value = [SimpleNamespace(id="current-chat")]
    sessions.document.side_effect = lambda sid: SimpleNamespace(get=lambda: SimpleNamespace(id=sid))
    existing = {
        "members": {
            "biz": {"removed": {"chats": True}},
            "old-biz": {"old-user": {"pending": True, "changeId": "interrupted-update"}},
        },
        "chats": {"removed-chat": {"customerUid": "old-user"}},
        "disabledUsers": {"deleted-user": True},
    }
    return database, existing


def test_dry_run_counts_stale_records_without_writing(migration_data):
    database, existing = migration_data
    result = migration.backfill(database, existing)
    assert result == {"memberships": 3, "chats": 2, "pendingMemberships": 1}
    access.sync_business_member_access.assert_not_called()
    access.sync_chat_access.assert_not_called()
    access.disable_realtime_user.assert_not_called()


def test_apply_repairs_existing_barriers_and_includes_deleted_records(migration_data):
    database, existing = migration_data
    migration.backfill(database, existing, apply=True)
    access.sync_business_member_access.assert_has_calls([
        call(database, "biz", "active", None),
        call(database, "biz", "removed", None),
        call(database, "old-biz", "old-user", "interrupted-update"),
    ])
    assert {args.args[0].id for args in access.sync_chat_access.call_args_list} == {"current-chat", "removed-chat"}
    assert existing["disabledUsers"] == {"deleted-user": True}


def test_apply_requires_maintenance_before_any_cloud_initialization(monkeypatch):
    # A mistaken apply invocation must fail before credentials or cloud clients are loaded.
    initialize = Mock()
    monkeypatch.setattr(migration, "initialize_firebase", initialize)
    monkeypatch.setattr(migration.sys, "argv", ["backfill", "--project", "demo-test", "--apply"])
    with pytest.raises(SystemExit) as error:
        migration.main()
    assert error.value.code == 2
    initialize.assert_not_called()
