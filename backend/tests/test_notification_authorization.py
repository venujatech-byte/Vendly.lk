"""Apply the approved notification policy to reads, read markers and realtime routing."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from firestore_memory import MemoryFirestore
from app import create_app
from app.services import operations_service as operations
from app.services.notification_permissions import NOTIFICATION_SCOPES, notification_scope


TYPES = ["new-order", "order-cancelled", "chat-needs-attention", "fraud-report", "fraud-warning", "ai-status", "future-alert"]
MEMBER = "businesses/biz/members/staff"


@pytest.fixture
def notifications(monkeypatch):
    # Use actual SDK document preconditions and query behavior without cloud traffic.
    store = MemoryFirestore()
    store.put(MEMBER, {"role": "custom", "status": "active", "permissions": ["orders:read"]})
    for index, kind in enumerate(TYPES):
        store.put(f"businesses/biz/notifications/{kind}", {
            "type": kind, "title": kind, "message": "Private preview",
            "isRead": False, "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index),
        })
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.operations.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "staff"}))
    return store, create_app({"TESTING": True}).test_client()


@pytest.mark.parametrize("role, permissions, expected", [
    ("owner", [], set(TYPES)),
    ("admin", [], set(TYPES)),
    ("custom", ["orders:read"], set(TYPES[:2])),
    ("custom", ["customers:read"], set(TYPES[2:5])),
    ("custom", ["*"], set(TYPES[:5])),
    ("custom", ["inventory:read"], set()),
    ("custom", [], set()),
])
def test_notification_reads_follow_membership_policy(notifications, role, permissions, expected):
    store, client = notifications
    store.put(MEMBER, {"role": role, "status": "active", "permissions": permissions})
    response = client.get("/api/v1/businesses/biz/notifications?role=owner", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    records = response.get_json()["notifications"]
    assert {record["type"] for record in records} == expected
    assert all(record["scope"] == notification_scope(record) for record in records)
    if not expected:
        store.client._firestore_api_internal.run_query.assert_not_called()


@pytest.mark.parametrize("kind", TYPES)
def test_read_markers_cannot_disclose_or_change_other_scopes(notifications, kind):
    store, client = notifications
    response = client.patch(f"/api/v1/businesses/biz/notifications/{kind}/read", headers={"Authorization": "Bearer test-token"})
    allowed = kind in TYPES[:2]
    assert response.status_code == (200 if allowed else 404)
    assert store.documents[f"businesses/biz/notifications/{kind}"]["isRead"] is allowed
    if not allowed:
        assert response.get_json()["error"]["code"] == "notification_not_found"


def test_concurrent_type_change_cannot_bypass_read_marker_policy(notifications):
    store, client = notifications
    path = "businesses/biz/notifications/new-order"
    store.before_commit = lambda current: current.put(path, {**current.documents[path], "type": "ai-status"})
    response = client.patch("/api/v1/businesses/biz/notifications/new-order/read", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 409
    assert store.documents[path]["isRead"] is False


def test_unread_filter_preserves_permission_checks(notifications):
    store, client = notifications
    path = "businesses/biz/notifications/new-order"
    store.put(path, {**store.documents[path], "isRead": True})
    response = client.get("/api/v1/businesses/biz/notifications?unread=true", headers={"Authorization": "Bearer test-token"})
    assert [record["type"] for record in response.get_json()["notifications"]] == ["order-cancelled"]


@pytest.mark.parametrize("state", ["inactive", "removed", "other-business", "unauthenticated"])
def test_notification_access_requires_current_tenant_membership(notifications, state):
    store, client = notifications
    if state == "inactive":
        store.put(MEMBER, {"role": "owner", "status": "inactive"})
    elif state == "removed":
        del store.documents[MEMBER]
    business = "other-biz" if state == "other-business" else "biz"
    headers = {} if state == "unauthenticated" else {"Authorization": "Bearer test-token"}
    for method, path in [("GET", "notifications"), ("PATCH", "notifications/new-order/read")]:
        response = client.open(f"/api/v1/businesses/{business}/{path}", method=method, headers=headers)
        assert response.status_code == (401 if state == "unauthenticated" else 403)
    store.client._firestore_api_internal.run_query.assert_not_called()


@pytest.mark.parametrize("kind, scope", [(kind, notification_scope({"type": kind})) for kind in TYPES])
def test_realtime_payload_moves_atomically_to_its_permitted_scope(monkeypatch, kind, scope):
    reference = Mock()
    getter = Mock(return_value=reference)
    monkeypatch.setattr(operations, "get_rtdb_reference", getter)
    operations.push_rtdb_business_notification("biz", "notice", {"type": kind, "title": "Title", "message": "Preview"})
    getter.assert_called_once_with("businesses/biz/notificationFeeds")
    updates = reference.update.call_args.args[0]
    assert set(updates) == {f"{name}/notice" for name in NOTIFICATION_SCOPES}
    assert updates[f"{scope}/notice"]["message"] == "Preview"
    assert all(updates[f"{name}/notice"] is None for name in NOTIFICATION_SCOPES if name != scope)


def test_recovery_removes_notifications_from_all_feeds(monkeypatch):
    reference = Mock()
    monkeypatch.setattr(operations, "get_rtdb_reference", lambda path: reference)
    operations.remove_rtdb_business_notification("biz", "notice")
    reference.update.assert_called_once_with({f"{scope}/notice": None for scope in NOTIFICATION_SCOPES})
