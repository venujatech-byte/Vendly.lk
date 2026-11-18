"""Apply one notification policy to API responses, realtime feeds and membership changes."""

from app.core.authorization import membership_has_permission


NOTIFICATION_SCOPES = ("orders", "customers", "management")
NOTIFICATION_TYPES = {
    "new-order": "orders",
    "order-cancelled": "orders",
    "chat-needs-attention": "customers",
    "fraud-report": "customers",
    "fraud-warning": "customers",
}


def notification_scope(notification):
    # Unknown types fail closed to management rather than being inferred from their text.
    kind = notification.get("type")
    return NOTIFICATION_TYPES.get(kind.strip(), "management") if isinstance(kind, str) else "management"


def notification_permissions(membership):
    # Only the current active membership can grant module reads or management alerts.
    active = membership.get("status") == "active"
    management = membership.get("role") in {"owner", "admin"}
    return {
        "orders": active and (management or membership_has_permission(membership, "orders:read")),
        "customers": active and (management or membership_has_permission(membership, "customers:read")),
        "management": active and management,
    }


def can_read_notification(membership, notification):
    return notification_permissions(membership)[notification_scope(notification)]
