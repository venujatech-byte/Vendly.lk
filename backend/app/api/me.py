from flask import Blueprint, g, jsonify
from firebase_admin import auth
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import FailedPrecondition
from time import time

from app.core.auth import require_firebase_user
from app.core.firebase import get_firestore_client
from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.business_service import create_or_get_business
from app.services.member_service import claim_pending_invitations_for_user
from app.services import realtime_access_service


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
            .where(filter=FieldFilter("ownerUid", "==", uid))
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

    # Refresh current membership before the dashboard attaches private RTDB listeners.
    if business:
        realtime_access_service.sync_business_member_access(database, business["id"], uid)

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
    """Delete a recently verified non-owner's account and known membership records."""
    # A refreshed bearer token alone is insufficient: require an actual recent sign-in.
    auth_time = g.current_user.get("auth_time")
    if isinstance(auth_time, bool) or not isinstance(auth_time, (int, float)) or not 0 <= time() - auth_time <= 300:
        raise ApiError("recent_login_required", "Please sign in again before deleting your account.", 401)
    uid = g.current_user["uid"]
    database = get_firestore_client()

    try:
        # Protect businesses even when an owner's profile links are missing or incomplete.
        owned_business = next(database.collection("businesses")
            .where(filter=FieldFilter("ownerUid", "==", uid)).limit(1).stream(), None)
        if owned_business is not None:
            raise ApiError("business_owner_deletion_blocked", "Business owners cannot delete their account until business ownership is resolved.", 409)

        user_ref = database.collection("users").document(uid)
        user_snapshot = user_ref.get()
        profile = user_snapshot.to_dict() or {}
        business_ids = profile.get("businessIds") or []
        if not isinstance(business_ids, list):
            raise ApiError("account_deletion_failed", "Account records could not be checked. Please retry.", 503)
        business_ids = [*business_ids, *([profile["defaultBusinessId"]] if profile.get("defaultBusinessId") else [])]
        if any(not isinstance(bid, str) or not bid or "/" in bid for bid in business_ids):
            raise ApiError("account_deletion_failed", "Account records could not be checked. Please retry.", 503)

        # Owner memberships also block legacy accounts whose business owner field is absent.
        memberships = []
        for bid in dict.fromkeys(business_ids):
            snapshot = database.collection("businesses").document(bid).collection("members").document(uid).get()
            if snapshot.exists:
                if (snapshot.to_dict() or {}).get("role") == "owner":
                    raise ApiError("business_owner_deletion_blocked", "Business owners cannot delete their account until business ownership is resolved.", 409)
                memberships.append(snapshot)

        # Revoke realtime reads before cleanup; failures retain the denial until a successful retry.
        realtime_access_service.disable_realtime_user(uid)
        batch = database.batch()
        for snapshot in [*memberships, *([user_snapshot] if user_snapshot.exists else [])]:
            # Reject concurrent role/profile changes rather than deleting a stale account version.
            batch.delete(snapshot.reference, option=database.write_option(last_update_time=snapshot.update_time))
        batch.delete(database.collection("sellers").document(uid))
        batch.commit()
    except ApiError:
        raise
    except FailedPrecondition as error:
        raise ApiError("account_changed", "Your account changed. Please reload and try again.", 409) from error
    except Exception as error:
        raise ApiError("account_deletion_failed", "Account cleanup could not be completed. Please retry.", 503) from error

    # Confirm Auth deletion only after known Firestore cleanup has succeeded.
    try:
        auth.delete_user(uid)
    except auth.UserNotFoundError:
        # A previously deleted Auth account needs no further deletion.
        pass
    except Exception as error:
        raise ApiError("account_deletion_failed", "Account deletion could not be completed. Please retry.", 503) from error

    return jsonify({"deleted": True})

