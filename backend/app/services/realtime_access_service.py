"""Mirror server-verified identities into private RTDB read permissions."""

from contextlib import contextmanager
from uuid import uuid4

from app.core.authorization import membership_has_permission
from app.core.errors import ApiError
from app.core.firebase import get_rtdb_reference


def access_reference(path):
    """Fail closed when the server cannot reach its permission store."""
    try:
        reference = get_rtdb_reference(f"_access/{path}")
    except Exception as error:
        raise ApiError("realtime_access_unavailable", "Realtime permissions could not be updated. Please retry.", 503) from error
    if reference is None:
        raise ApiError("realtime_access_unavailable", "Realtime permissions could not be updated. Please retry.", 503)
    return reference


def _version(snapshot):
    """Use the server read time, including nanoseconds, to reject stale grants."""
    timestamp = snapshot.read_time.timestamp_pb()
    return f"{timestamp.seconds:012d}{timestamp.nanos:09d}"


def _transaction(reference, update):
    """Return a safe API error instead of silently retaining an old permission."""
    try:
        return reference.transaction(update)
    except ApiError:
        raise
    except Exception as error:
        raise ApiError("realtime_access_unavailable", "Realtime permissions could not be updated. Please retry.", 503) from error


def _publish(reference, payload, change_id=None):
    """Keep revocations and newer snapshots ahead of delayed readers."""
    def update(current):
        current = current or {}
        # Only the writer holding this barrier may complete a membership change.
        if current.get("pending"):
            if not change_id or current.get("changeId") != change_id:
                return current
        elif change_id and current != payload:
            raise ApiError("realtime_access_conflict", "Membership permissions changed concurrently. Please retry.", 409)
        # A late read must not overwrite a later revocation or ownership change.
        if current.get("version", "") > payload["version"]:
            if change_id:
                raise ApiError("realtime_access_conflict", "Membership permissions changed concurrently. Please retry.", 409)
            return current
        return payload

    return _transaction(reference, update)


def sync_business_member_access(database, business_id, uid, change_id=None):
    """Publish only the current Firestore membership, including deletion tombstones."""
    snapshot = (
        database.collection("businesses").document(business_id)
        .collection("members").document(uid).get()
    )
    member = snapshot.to_dict() if snapshot.exists else {}
    active = member.get("status") == "active"
    payload = {
        "version": _version(snapshot),
        "notifications": active,
        "chats": active and membership_has_permission(member, "customers:read"),
    }
    published = _publish(access_reference(f"members/{business_id}/{uid}"), payload, change_id)
    if published.get("pending"):
        raise ApiError("realtime_access_conflict", "A membership update needs to finish before retrying.", 409)
    return published


@contextmanager
def changing_business_member_access(database, business_id, uid, changes=None):
    """Revoke reduced rights before an edit while preserving unaffected live reads."""
    reference = access_reference(f"members/{business_id}/{uid}")
    change_id = uuid4().hex

    # Serialize edits; do not interrupt subscriptions whose rights will stay unchanged.
    def block(current):
        current = current or {}
        if current.get("pending") and current.get("changeId") != change_id:
            raise ApiError("realtime_access_conflict", "A membership update needs to finish before retrying.", 409)
        return {**current, "version": current.get("version", ""), "pending": True, "changeId": change_id}

    _transaction(reference, block)
    try:
        # Re-read after taking the lock so concurrent earlier edits cannot affect this calculation.
        snapshot = (
            database.collection("businesses").document(business_id)
            .collection("members").document(uid).get()
        )
        member = snapshot.to_dict() if snapshot.exists else {}
        next_member = {**member, **changes} if changes is not None else {}
        active = next_member.get("status") == "active"

        def revoke(current):
            if not current or current.get("changeId") != change_id:
                raise ApiError("realtime_access_conflict", "Membership permissions changed concurrently. Please retry.", 409)
            return {
                **current,
                "notifications": current.get("notifications") is True and active,
                "chats": current.get("chats") is True and active and membership_has_permission(next_member, "customers:read"),
            }

        # Remove rights before Firestore changes, but grant new rights only after commit.
        _transaction(reference, revoke)
        yield
    finally:
        # A failed write restores its actual state; a failed sync retains revoked rights as denied.
        sync_business_member_access(database, business_id, uid, change_id)


def sync_chat_access(snapshot):
    """Mirror ownership from a server snapshot, never from a client request."""
    session = snapshot.to_dict() if snapshot.exists else {}
    payload = {
        "version": _version(snapshot),
        "businessId": session.get("businessId") or "",
        "customerUid": session.get("customerUid") or "",
    }
    return _publish(access_reference(f"chats/{snapshot.id}"), payload)


def disable_realtime_user(uid):
    """Revoke reads before account deletion, including still-unexpired ID tokens."""
    try:
        access_reference(f"disabledUsers/{uid}").set(True)
    except ApiError:
        raise
    except Exception as error:
        raise ApiError("realtime_access_unavailable", "Realtime permissions could not be revoked. Please retry.", 503) from error
