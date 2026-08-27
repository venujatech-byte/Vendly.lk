import secrets
import string
import re

from firebase_admin import firestore
from google.cloud import firestore as google_firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import optional_text, required_text


SHORT_CODE_ALPHABET = string.ascii_letters + string.digits
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]{7,25}$")


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
                "publicPhone": "",
                "publicEmail": "",
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


def update_public_contact(database, business_id, payload):
    """Save the phone number and email shown on the public storefront."""
    business_reference = database.collection("businesses").document(business_id)
    business_snapshot = business_reference.get()

    if not business_snapshot.exists:
        raise ApiError("business_not_found", "Business not found.", 404)

    try:
        public_phone = optional_text(payload.get("phone"), 25)
        public_email = optional_text(payload.get("email"), 160)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if public_phone and not PHONE_PATTERN.fullmatch(public_phone):
        raise ApiError(
            "validation_error",
            "Enter a valid contact phone number.",
            422,
        )

    if public_email and not EMAIL_PATTERN.fullmatch(public_email):
        raise ApiError(
            "validation_error",
            "Enter a valid contact email address.",
            422,
        )

    changes = {
        "publicPhone": public_phone,
        "publicEmail": public_email.lower(),
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }

    # Free text rather than named policy fields: a seller can write about
    # returns, cash on delivery, exchanges or opening hours in their own words,
    # and the chatbot answers from it without a schema to keep in step.
    # Bank details are given to a customer who chooses to transfer, so they are
    # stored per business. They are deliberately NOT part of public_business:
    # an account number should not be handed to every anonymous storefront
    # visitor, only to someone who asked how to pay.
    if "bankDetails" in payload:
        raw_bank = payload.get("bankDetails") or {}

        if not isinstance(raw_bank, dict):
            raise ApiError("validation_error", "Bank details must be an object.", 422)

        try:
            changes["bankDetails"] = {
                "bankName": optional_text(raw_bank.get("bankName"), 120),
                "branch": optional_text(raw_bank.get("branch"), 120),
                "accountName": optional_text(raw_bank.get("accountName"), 160),
                "accountNumber": optional_text(raw_bank.get("accountNumber"), 40),
                "instructions": optional_text(raw_bank.get("instructions"), 500),
            }
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

    # Where the shop is, or that there is nowhere to visit. Unlike bank details
    # this is public by nature - a shop address exists to be found - so it is
    # part of the public store payload.
    if "storeLocation" in payload:
        raw_location = payload.get("storeLocation") or {}

        if not isinstance(raw_location, dict):
            raise ApiError("validation_error", "Store location must be an object.", 422)

        try:
            changes["storeLocation"] = {
                "isOnlineOnly": bool(raw_location.get("isOnlineOnly")),
                "addressLine": optional_text(raw_location.get("addressLine"), 200),
                "city": optional_text(raw_location.get("city"), 120),
                "district": optional_text(raw_location.get("district"), 120),
                "openingHours": optional_text(raw_location.get("openingHours"), 200),
                "mapUrl": optional_text(raw_location.get("mapUrl"), 500),
            }
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

    if "storefrontFaq" in payload:
        try:
            changes["storefrontFaq"] = optional_text(
                payload.get("storefrontFaq"),
                4000,
            )
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

    business_reference.update(changes)

    return serialize_snapshot(business_reference.get())
