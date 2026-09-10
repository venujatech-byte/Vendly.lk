from firebase_admin import auth, firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import required_text


ROLE_PERMISSIONS = {
    "admin": [
        "orders:*",
        "inventory:*",
        "customers:*",
        "couriers:*",
        "analytics:read",
        "staff:manage",
        "messages:*",
    ],
    "order_manager": [
        "orders:*",
        "customers:*",
        "couriers:read",
        "inventory:read",
        "messages:*",
    ],
    "inventory_manager": ["inventory:*", "orders:read", "reviews:manage"],
    "support": ["orders:read", "customers:*", "messages:*"],
    "viewer": ["orders:read", "inventory:read", "analytics:read"],
}


def validate_member_payload(payload, require_email=True):
    try:
        email = (
            required_text(payload.get("email"), "Email", 254).lower()
            if require_email
            else ""
        )
        role = required_text(payload.get("role"), "Role", 40).lower()
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if role not in ROLE_PERMISSIONS:
        raise ApiError(
            "validation_error",
            "Choose a valid staff role.",
            422,
            {"allowedRoles": sorted(ROLE_PERMISSIONS)},
        )

    return {"email": email, "role": role, "permissions": ROLE_PERMISSIONS[role]}


def list_members(database, business_id):
    snapshots = (
        database.collection("businesses")
        .document(business_id)
        .collection("members")
        .stream()
    )
    members = []

    for snapshot in snapshots:
        member = serialize_snapshot(snapshot)
        user_reference = database.collection("users").document(snapshot.id)
        user_snapshot = user_reference.get()
        user = user_snapshot.to_dict() if user_snapshot.exists else {}

        # Repair staff assignments created before users stored their business link.
        # Existing users keep their current default business; this business is added
        # to the account and becomes the default only when no default exists yet.
        user_business_ids = user.get("businessIds") or []
        user_changes = {}
        if business_id not in user_business_ids:
            user_changes["businessIds"] = firestore.ArrayUnion([business_id])
        if not user.get("defaultBusinessId"):
            user_changes["defaultBusinessId"] = business_id
        if user_changes:
            user_changes["updatedAt"] = firestore.SERVER_TIMESTAMP
            user_reference.set(user_changes, merge=True)

        members.append(
            {
                **member,
                "displayName": user.get("displayName", "Staff member"),
                "email": user.get("email", ""),
                "photoUrl": user.get("photoUrl", ""),
            },
        )

    return sorted(members, key=lambda item: item.get("displayName", "").casefold())


def add_member(database, business_id, invited_by, payload):
    member_data = validate_member_payload(payload)

    business_reference = database.collection("businesses").document(business_id)
    business_snapshot = business_reference.get()
    owner_uid = business_snapshot.to_dict().get("ownerUid") if business_snapshot.exists else None

    if member_data["role"] == "admin" and owner_uid and invited_by != owner_uid:
        raise ApiError(
            "forbidden",
            "Only the business owner can invite staff with the admin role.",
            403,
        )

    try:
        firebase_user = auth.get_user_by_email(member_data["email"])
    except auth.UserNotFoundError as error:
        raise ApiError(
            "staff_account_not_found",
            "This person must create a Vendly account before being added as staff.",
            404,
        ) from error

    member_reference = business_reference.collection("members").document(
        firebase_user.uid,
    )

    if member_reference.get().exists:
        raise ApiError(
            "staff_member_exists",
            "This account already belongs to the business.",
            409,
        )

    timestamp = firestore.SERVER_TIMESTAMP
    member_reference.set(
        {
            "uid": firebase_user.uid,
            "role": member_data["role"],
            "permissions": member_data["permissions"],
            "status": "active",
            "invitedBy": invited_by,
            "joinedAt": timestamp,
            "updatedAt": timestamp,
        },
    )

    user_reference = database.collection("users").document(firebase_user.uid)
    user_snapshot = user_reference.get()
    user_dict = user_snapshot.to_dict() if user_snapshot.exists else {}

    user_payload = {
        "uid": firebase_user.uid,
        "displayName": firebase_user.display_name or member_data["email"],
        "email": member_data["email"],
        "photoUrl": firebase_user.photo_url or "",
        "businessIds": firestore.ArrayUnion([business_id]),
        "status": "active",
        "updatedAt": timestamp,
    }
    if not user_dict.get("defaultBusinessId"):
        user_payload["defaultBusinessId"] = business_id

    user_reference.set(user_payload, merge=True)

    return next(
        member
        for member in list_members(database, business_id)
        if member["id"] == firebase_user.uid
    )


def update_member(database, business_id, member_uid, payload, updated_by=None):
    business_reference = database.collection("businesses").document(business_id)
    business_snapshot = business_reference.get()
    owner_uid = business_snapshot.to_dict().get("ownerUid") if business_snapshot.exists else None

    if owner_uid and owner_uid == member_uid:
        raise ApiError(
            "owner_membership_protected",
            "The business owner role cannot be changed or disabled.",
            409,
        )

    member_reference = business_reference.collection("members").document(member_uid)
    member_snapshot = member_reference.get()

    if not member_snapshot.exists:
        raise ApiError("staff_member_not_found", "Staff member not found.", 404)

    target_member = member_snapshot.to_dict()
    is_target_admin = target_member.get("role") == "admin"

    # Only store owner can modify an admin or assign the admin role
    if updated_by and owner_uid and updated_by != owner_uid:
        if is_target_admin:
            raise ApiError(
                "forbidden",
                "Only the business owner can modify an admin member.",
                403,
            )
        if payload.get("role") == "admin":
            raise ApiError(
                "forbidden",
                "Only the business owner can assign the admin role.",
                403,
            )

    changes = {"updatedAt": firestore.SERVER_TIMESTAMP}

    if "role" in payload:
        validated = validate_member_payload({"role": payload.get("role")}, False)
        changes.update(
            {"role": validated["role"], "permissions": validated["permissions"]},
        )
    if "status" in payload:
        status = str(payload.get("status", "")).strip().lower()
        if status not in {"active", "inactive"}:
            raise ApiError(
                "validation_error",
                "Staff status must be active or inactive.",
                422,
            )
        changes["status"] = status

    member_reference.update(changes)
    return next(
        member
        for member in list_members(database, business_id)
        if member["id"] == member_uid
    )
