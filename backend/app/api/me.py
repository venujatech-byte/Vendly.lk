from flask import Blueprint, g, jsonify

from app.core.auth import require_firebase_user
from app.core.firebase import get_firestore_client
from app.core.serialization import serialize_snapshot


me_blueprint = Blueprint("me", __name__, url_prefix="/api/v1")


@me_blueprint.get("/me")
@require_firebase_user
def get_current_user():
    """Return the verified Firebase identity and current legacy seller profile."""
    uid = g.current_user["uid"]
    database = get_firestore_client()

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
