from functools import wraps

from flask import g

from app.core.errors import ApiError
from app.core.firebase import get_firestore_client


def membership_has_permission(membership, required_permission):
    """Return whether a membership grants one exact or wildcard permission."""
    if not required_permission:
        return True
    if membership.get("role") == "owner":
        return True

    permissions = set(membership.get("permissions") or [])
    if "*" in permissions or required_permission in permissions:
        return True

    resource = required_permission.split(":", 1)[0]
    return f"{resource}:*" in permissions


def require_business_member(*allowed_roles, permission=None):
    """Require the authenticated user to belong to the requested business."""

    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            business_id = kwargs.get("business_id")

            if not business_id:
                raise ApiError(
                    "business_required",
                    "A business ID is required.",
                    400,
                )

            uid = g.current_user["uid"]
            database = get_firestore_client()
            membership_snapshot = (
                database.collection("businesses")
                .document(business_id)
                .collection("members")
                .document(uid)
                .get()
            )

            if not membership_snapshot.exists:
                raise ApiError(
                    "business_access_denied",
                    "You do not have access to this business.",
                    403,
                )

            membership = membership_snapshot.to_dict()

            if membership.get("status") != "active":
                raise ApiError(
                    "business_access_denied",
                    "Your business membership is not active.",
                    403,
                )

            if allowed_roles and membership.get("role") not in allowed_roles:
                raise ApiError(
                    "permission_denied",
                    "You do not have permission to complete this action.",
                    403,
                )

            if permission and not membership_has_permission(membership, permission):
                raise ApiError(
                    "permission_denied",
                    "You do not have permission to complete this action.",
                    403,
                    {"requiredPermission": permission},
                )

            g.business_id = business_id
            g.membership = membership

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator
