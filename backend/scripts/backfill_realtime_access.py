"""Plan or apply private RTDB permission backfill; never print identities or secrets."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.core.firebase import get_firestore_client, get_rtdb_reference, initialize_firebase
from app.services import realtime_access_service as access
from app.services.notification_permissions import NOTIFICATION_SCOPES, notification_scope


def notification_plan(business_data):
    """Preserve existing live history while moving each payload into its authorized scope."""
    plan = {}
    for business_id, data in business_data.items():
        # Completed businesses must not resurrect removed alerts from retained legacy copies.
        notifications = {} if data.get("notificationFeedsMigrated") is True else dict(data.get("notifications") or {})
        # Already migrated/current feed records take precedence over old, unscoped copies.
        for records in (data.get("notificationFeeds") or {}).values():
            notifications.update(records or {})
        if not notifications:
            continue
        groups = {scope: {} for scope in NOTIFICATION_SCOPES}
        for notification_id, notification in notifications.items():
            if not isinstance(notification, dict):
                raise ValueError("Invalid notification record; review the source before applying.")
            groups[notification_scope(notification)][notification_id] = notification
        plan[business_id] = groups
    return plan


def backfill(database, existing, business_data, apply=False):
    """Include old metadata keys so removed members/chats receive denial tombstones."""
    existing_members = existing.get("members") or {}
    members = set()
    business_ids = {item.id for item in database.collection("businesses").stream()}
    for business_id in business_ids | set(existing_members):
        references = database.collection("businesses").document(business_id).collection("members")
        user_ids = {item.id for item in references.stream()} | set(existing_members.get(business_id) or {})
        members.update((business_id, uid) for uid in user_ids)
    chat_ids = {item.id for item in database.collection("publicChatSessions").stream()}
    chat_ids.update(existing.get("chats") or {})

    # Count planned work without exposing customer/session IDs or changing either database.
    pending_count = sum(
        bool((existing_members.get(business_id) or {}).get(uid, {}).get("pending"))
        for business_id, uid in members
    )
    feeds = notification_plan(business_data)
    result = {
        "memberships": len(members), "chats": len(chat_ids), "pendingMemberships": pending_count,
        "notificationBusinesses": len(feeds),
        "notifications": sum(len(records) for groups in feeds.values() for records in groups.values()),
    }
    if not apply:
        return result

    # Writers must be stopped: repair a saved barrier only from the current Firestore state.
    for business_id, uid in sorted(members):
        previous = (existing_members.get(business_id) or {}).get(uid) or {}
        change_id = previous.get("changeId") if previous.get("pending") else None
        access.sync_business_member_access(database, business_id, uid, change_id)
    for session_id in sorted(chat_ids):
        snapshot = database.collection("publicChatSessions").document(session_id).get()
        access.sync_chat_access(snapshot)
    # All writers must remain stopped until both scoped permissions and historical payloads are ready.
    for business_id, groups in feeds.items():
        get_rtdb_reference(f"businesses/{business_id}").update({
            "notificationFeeds": groups, "notificationFeedsMigrated": True,
        })
    return result


def main():
    # Require an explicit matching project; applying also requires a maintenance confirmation.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--maintenance-confirmed", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.maintenance_confirmed:
        parser.error("Stop backend writers first, then pass --maintenance-confirmed.")

    # Initialization and all cloud calls happen only after the CLI safety checks.
    settings = Settings.from_environment()
    if settings.firebase_project_id != args.project:
        parser.error("The requested project does not match the configured Firebase project.")
    try:
        initialize_firebase(settings)
        existing = access.access_reference("").get() or {}
        business_data = get_rtdb_reference("businesses").get() or {}
        counts = backfill(get_firestore_client(), existing, business_data, apply=args.apply)
    except Exception:
        print("Migration stopped without a successful completion. Keep private rules undeployed until permissions are verified.", file=sys.stderr)
        return 1
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", **counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
