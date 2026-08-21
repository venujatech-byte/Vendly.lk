import secrets
import string

from firebase_admin import firestore
from google.cloud import firestore as google_firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import required_text


SHORT_CODE_ALPHABET = string.ascii_letters + string.digits


def generate_short_code(length=7):
    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(length))


def create_or_get_business(database, firebase_user, payload):
    """Create the first business for a Firebase user, or return the existing one."""
    uid = firebase_user["uid"]
    user_reference = database.collection("users").document(uid)
    existing_user = user_reference.get()

    # Recover accounts created before defaultBusinessId was saved.  This keeps
    # an existing seller from being asked to create a second business after
    # logging in on another device or browser.
    owner_businesses = list(
        database.collection("businesses")
        .where("ownerUid", "==", uid)
        .limit(1)
        .stream()
    )

    if owner_businesses:
        existing_business = owner_businesses[0]
        timestamp = firestore.SERVER_TIMESTAMP
        membership_reference = (
            database.collection("businesses")
            .document(existing_business.id)
            .collection("members")
            .document(uid)
        )

        # Repair the two small references that the dashboard needs.  merge=True
        # preserves any profile fields that already exist.
        user_reference.set(
            {
                "uid": uid,
                "displayName": firebase_user.get("name") or "Business owner",
                "email": firebase_user.get("email") or "",
                "defaultBusinessId": existing_business.id,
                "businessIds": firestore.ArrayUnion([existing_business.id]),
                "status": "active",
                "updatedAt": timestamp,
            },
            merge=True,
        )
        membership_reference.set(
            {
                "uid": uid,
                "role": "owner",
                "permissions": ["*"],
                "status": "active",
                "joinedAt": timestamp,
            },
            merge=True,
        )
        return serialize_snapshot(existing_business), False

    if existing_user.exists:
        default_business_id = existing_user.to_dict().get("defaultBusinessId")

        if default_business_id:
            existing_business = (
                database.collection("businesses")
                .document(default_business_id)
                .get()
            )

            if existing_business.exists:
                return serialize_snapshot(existing_business), False

    try:
        owner_name = required_text(
            payload.get("ownerName") or firebase_user.get("name"),
            "Owner name",
        )
        business_name = required_text(payload.get("businessName"), "Business name")
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    business_reference = database.collection("businesses").document()
    membership_reference = business_reference.collection("members").document(uid)
    short_code = generate_short_code()
    short_link_reference = database.collection("shortLinks").document(short_code)
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        short_link_snapshot = short_link_reference.get(transaction=current_transaction)

        if short_link_snapshot.exists:
            raise ApiError(
                "short_code_conflict",
                "A public code conflict occurred. Please try again.",
                409,
            )

        timestamp = firestore.SERVER_TIMESTAMP

        current_transaction.set(
            business_reference,
            {
                "name": business_name,
                "ownerUid": uid,
                "shortCode": short_code,
                "logoPath": "",
                "phone": "",
                "email": firebase_user.get("email") or "",
                "address": {},
                "currency": "LKR",
                "timezone": "Asia/Colombo",
                "status": "active",
                "nextOrderSequence": 1,
                "nextWaybillSequence": 1,
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )
        current_transaction.set(
            membership_reference,
            {
                "uid": uid,
                "role": "owner",
                "permissions": ["*"],
                "status": "active",
                "joinedAt": timestamp,
            },
        )
        current_transaction.set(
            user_reference,
            {
                "uid": uid,
                "displayName": owner_name,
                "email": firebase_user.get("email") or "",
                "photoUrl": firebase_user.get("picture") or "",
                "defaultBusinessId": business_reference.id,
                "businessIds": firestore.ArrayUnion([business_reference.id]),
                "status": "active",
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
            merge=True,
        )
        current_transaction.set(
            short_link_reference,
            {
                "type": "store",
                "businessId": business_reference.id,
                "status": "active",
                "createdAt": timestamp,
            },
        )

    create_in_transaction(transaction)

    return serialize_snapshot(business_reference.get()), True
