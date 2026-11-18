"""Plan or apply private RTDB permission backfill; never print identities or secrets."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.core.firebase import get_firestore_client, initialize_firebase
from app.services import realtime_access_service as access


def backfill(database, existing, apply=False):
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
    result = {"memberships": len(members), "chats": len(chat_ids), "pendingMemberships": pending_count}
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
        counts = backfill(get_firestore_client(), existing, apply=args.apply)
    except Exception:
        print("Migration stopped without a successful completion. Keep private rules undeployed until permissions are verified.", file=sys.stderr)
        return 1
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", **counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
