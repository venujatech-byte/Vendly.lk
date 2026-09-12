from flask import Blueprint, g, jsonify
from firebase_admin import auth

from app.core.auth import require_firebase_user
from app.core.firebase import get_firestore_client
from app.core.serialization import serialize_snapshot
from app.services.business_service import create_or_get_business
from app.services.member_service import claim_pending_invitations_for_user


me_blueprint = Blueprint("me", __name__, url_prefix="/api/v1")


@me_blueprint.get("/me")
@require_firebase_user
def get_current_user():
    """Return the verified Firebase identity and current legacy seller profile."""
    uid = g.current_user["uid"]
    database = get_firestore_client()

    # Automatically claim any pending staff invitations sent to this email
    claim_pending_invitations_for_user(database, g.current_user)

    user_snapshot = database.collection("users").document(uid).get()
    seller_snapshot = database.collection("sellers").document(uid).get()

    profile = None
    business = None
    membership = None

    if user_snapshot.exists:
        profile = serialize_snapshot(user_snapshot)
        business_ids = profile.get("businessIds") or []
        business_id = profile.get("defaultBusinessId") or (
            business_ids[0] if business_ids else None
        )

        if business_id:
            business_snapshot = (
                database.collection("businesses")
                .document(business_id)
                .get()
            )
            membership_snapshot = (
                database.collection("businesses")
                .document(business_id)
                .collection("members")
                .document(uid)
                .get()
            )

            if business_snapshot.exists:
                business = serialize_snapshot(business_snapshot)

            if membership_snapshot.exists:
                membership = serialize_snapshot(membership_snapshot)
    elif seller_snapshot.exists:
        profile = serialize_snapshot(seller_snapshot)

    # Migrate older seller profiles automatically.  Older versions stored
    # businessName in sellers/{uid} but did not create a businesses document.
    # Without this migration, every new login incorrectly opened onboarding.
    if not business and profile and profile.get("businessName"):
        migrated_business, _ = create_or_get_business(
            database,
            g.current_user,
            {
                "ownerName": profile.get("ownerName")
                or profile.get("displayName")
                or g.current_user.get("name"),
                "businessName": profile.get("businessName"),
            },
        )
        business = migrated_business
        business_id = migrated_business.get("id")
        if business_id:
            membership_snapshot = (
                database.collection("businesses")
                .document(business_id)
                .collection("members")
                .document(uid)
                .get()
            )
            if membership_snapshot.exists:
                membership = serialize_snapshot(membership_snapshot)

    # Compatibility recovery for accounts whose business was created before
    # the users/{uid}.defaultBusinessId link was introduced.
    if not business:
        owner_businesses = list(
            database.collection("businesses")
            .where("ownerUid", "==", uid)
            .limit(1)
            .stream()
        )

        if owner_businesses:
            business_snapshot = owner_businesses[0]
            business = serialize_snapshot(business_snapshot)
            membership_snapshot = (
                database.collection("businesses")
                .document(business_snapshot.id)
                .collection("members")
                .document(uid)
                .get()
            )
            if membership_snapshot.exists:
                membership = serialize_snapshot(membership_snapshot)
            else:
                membership = {
                    "uid": uid,
                    "role": "owner",
                    "permissions": ["*"],
                    "status": "active",
                }

            profile = profile or {
                "uid": uid,
                "displayName": g.current_user.get("name") or "Business owner",
                "email": g.current_user.get("email") or "",
            }

    # The business owner must always retain owner permissions.  Some early
    # test records were accidentally saved with the default viewer role,
    # which made the dashboard show only Overview after a fresh login.
    if business and business.get("ownerUid") == uid:
        owner_membership = {
            "uid": uid,
            "role": "owner",
            "permissions": ["*"],
            "status": "active",
        }
        if not membership or membership.get("role") != "owner":
            database.collection("businesses").document(business["id"]).collection(
                "members"
            ).document(uid).set(owner_membership, merge=True)
        membership = {**(membership or {}), **owner_membership}

    return jsonify(
        {
            "user": {
                "uid": uid,
                "email": g.current_user.get("email"),
                "emailVerified": g.current_user.get("email_verified", False),
                "name": g.current_user.get("name"),
                "picture": g.current_user.get("picture"),
            },
            "profile": profile,
            "business": business,
            "membership": membership,
        },
    )


@me_blueprint.delete("/me")
@require_firebase_user
def delete_current_user():
    """Permanently delete user profile, business memberships, and auth account."""
    uid = g.current_user["uid"]
    database = get_firestore_client()

    user_ref = database.collection("users").document(uid)
    user_snapshot = user_ref.get()
    if user_snapshot.exists:
        user_dict = user_snapshot.to_dict() or {}
        business_ids = user_dict.get("businessIds") or []
        for bid in business_ids:
            try:
                mem_ref = database.collection("businesses").document(bid).collection("members").document(uid)
                if mem_ref.get().exists:
                    mem_ref.delete()
            except Exception:
                pass
        user_ref.delete()

    try:
        database.collection("sellers").document(uid).delete()
    except Exception:
        pass

    try:
        auth.delete_user(uid)
    except Exception:
        pass

    return jsonify({"deleted": True})

