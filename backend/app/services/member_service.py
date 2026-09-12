import uuid
from datetime import datetime, timezone
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
        "*",
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

MODULE_PERMISSIONS = {
    "orders": ["orders", "orders:*", "orders:read", "orders:manage"],
    "inventory": ["inventory", "inventory:*", "inventory:read", "inventory:manage"],
    "customers": ["customers", "customers:*", "customers:read", "customers:manage", "messages:*", "messages:read", "messages:manage"],
    "couriers": ["couriers", "couriers:*", "couriers:read", "couriers:manage"],
    "analytics": ["analytics", "analytics:*", "analytics:read"],
    "reviews": ["reviews", "reviews:*", "reviews:read", "reviews:manage"],
}

AVAILABLE_PERMISSIONS = {
    "*",
    "orders",
    "inventory",
    "customers",
    "couriers",
    "analytics",
    "reviews",
    "orders:read",
    "orders:manage",
    "orders:*",
    "inventory:read",
    "inventory:manage",
    "inventory:*",
    "customers:read",
    "customers:manage",
    "customers:*",
    "couriers:read",
    "couriers:manage",
    "couriers:*",
    "analytics:read",
    "analytics:*",
    "reviews:read",
    "reviews:manage",
    "reviews:*",
    "messages:read",
    "messages:manage",
    "messages:*",
    "staff:manage",
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

    if role != "custom" and role not in ROLE_PERMISSIONS:
        raise ApiError(
            "validation_error",
            "Choose a valid staff role.",
            422,
            {"allowedRoles": sorted(list(ROLE_PERMISSIONS) + ["custom"])},
        )

    # Check for custom permissions in payload
    custom_perms = payload.get("permissions")
    if custom_perms is not None and isinstance(custom_perms, list):
        cleaned_permissions = set()
        for perm in custom_perms:
            perm_str = str(perm).strip().lower()
            if perm_str == "*":
                cleaned_permissions.add("*")
            elif perm_str in MODULE_PERMISSIONS:
                cleaned_permissions.update(MODULE_PERMISSIONS[perm_str])
            elif perm_str in AVAILABLE_PERMISSIONS:
                cleaned_permissions.add(perm_str)
                prefix = perm_str.split(":", 1)[0]
                if prefix in MODULE_PERMISSIONS:
                    cleaned_permissions.add(prefix)
        permissions = sorted(list(cleaned_permissions))
    else:
        permissions = ROLE_PERMISSIONS.get(role, ["orders:read", "inventory:read"])

    return {"email": email, "role": role, "permissions": permissions}


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


def list_invitations(database, business_id):
    snapshots = (
        database.collection("businesses")
        .document(business_id)
        .collection("invitations")
        .where("status", "==", "pending")
        .stream()
    )
    invitations = []
    for doc in snapshots:
        item = serialize_snapshot(doc)
        item["token"] = item.get("token") or item.get("id") or doc.id
        invitations.append(item)
    return sorted(invitations, key=lambda item: str(item.get("createdAt", "")), reverse=True)


def add_member(database, business_id, invited_by, payload):
    member_data = validate_member_payload(payload)

    business_reference = database.collection("businesses").document(business_id)
    business_snapshot = business_reference.get()
    business_dict = business_snapshot.to_dict() if business_snapshot.exists else {}
    owner_uid = business_dict.get("ownerUid")
    business_name = business_dict.get("name") or "Store"

    # Only owner can invite admin role or grant staff:manage
    if (member_data["role"] == "admin" or "staff:manage" in member_data["permissions"]) and owner_uid and invited_by != owner_uid:
        raise ApiError(
            "forbidden",
            "Only the business owner can invite staff with the admin role.",
            403,
        )

    # 1. Check if the user is already registered in Firebase Auth
    try:
        auth.get_user_by_email(member_data["email"])
        user_already_registered = True
    except auth.UserNotFoundError:
        user_already_registered = False

    if user_already_registered:
        # Pre-registered users cannot be added as staff
        raise ApiError(
            "preregistered_user_cannot_be_staff",
            "This person is already registered to Vendly and cannot be added as staff. Staff accounts must be created via invitation.",
            409,
        )

    # 2. Check if an active invitation already exists for this email in this business
    existing_invitations = list(
        business_reference.collection("invitations")
        .where("email", "==", member_data["email"])
        .where("status", "==", "pending")
        .stream()
    )
    if existing_invitations:
        inv_doc = existing_invitations[0]
        inv_id = inv_doc.id
        updates = {
            "token": inv_id,
            "role": member_data["role"],
            "permissions": member_data["permissions"],
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
        inv_doc.reference.update(updates)
        top_ref = database.collection("businessInvitations").document(inv_id)
        if top_ref.get().exists:
            top_ref.update(updates)
        invitation = {**serialize_snapshot(inv_doc), **updates}
        return {
            "type": "invitation",
            "invitation": invitation,
            "inviteToken": inv_id,
            "inviteUrl": f"/join?token={inv_id}",
        }

    # 3. Create a new pending invitation with customized permissions
    invitation_id = str(uuid.uuid4())
    timestamp = firestore.SERVER_TIMESTAMP
    invitation_data = {
        "id": invitation_id,
        "token": invitation_id,
        "businessId": business_id,
        "businessName": business_name,
        "email": member_data["email"],
        "role": member_data["role"],
        "permissions": member_data["permissions"],
        "invitedBy": invited_by,
        "status": "pending",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }

    business_reference.collection("invitations").document(invitation_id).set(invitation_data)
    database.collection("businessInvitations").document(invitation_id).set(invitation_data)

    now_iso = str(datetime.now(timezone.utc))
    return {
        "type": "invitation",
        "invitation": {
            **invitation_data,
            "createdAt": now_iso,
            "updatedAt": now_iso,
        },
        "inviteToken": invitation_id,
        "inviteUrl": f"/join?token={invitation_id}",
    }


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
        validated = validate_member_payload(
            {"role": payload.get("role"), "permissions": payload.get("permissions")},
            False,
        )
        changes.update(
            {"role": validated["role"], "permissions": validated["permissions"]},
        )
    elif "permissions" in payload:
        validated = validate_member_payload(
            {"role": target_member.get("role", "custom"), "permissions": payload.get("permissions")},
            False,
        )
        changes["permissions"] = validated["permissions"]

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


def remove_member(database, business_id, member_uid, removed_by=None):
    business_reference = database.collection("businesses").document(business_id)
    business_snapshot = business_reference.get()
    owner_uid = business_snapshot.to_dict().get("ownerUid") if business_snapshot.exists else None

    if owner_uid and owner_uid == member_uid:
        raise ApiError(
            "owner_membership_protected",
            "The business owner cannot be removed.",
            409,
        )

    member_reference = business_reference.collection("members").document(member_uid)
    member_snapshot = member_reference.get()
    if not member_snapshot.exists:
        raise ApiError("staff_member_not_found", "Staff member not found.", 404)

    target_member = member_snapshot.to_dict()
    is_target_admin = target_member.get("role") == "admin"

    if removed_by and owner_uid and removed_by != owner_uid and is_target_admin:
        raise ApiError(
            "forbidden",
            "Only the business owner can remove an admin member.",
            403,
        )

    member_reference.delete()

    # Clean up user's businessIds
    user_reference = database.collection("users").document(member_uid)
    user_snapshot = user_reference.get()
    if user_snapshot.exists:
        user_dict = user_snapshot.to_dict() or {}
        user_updates = {
            "businessIds": firestore.ArrayRemove([business_id]),
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
        if user_dict.get("defaultBusinessId") == business_id:
            remaining = [bid for bid in (user_dict.get("businessIds") or []) if bid != business_id]
            user_updates["defaultBusinessId"] = remaining[0] if remaining else None
        user_reference.set(user_updates, merge=True)

    return {"id": member_uid, "removed": True}


def cancel_invitation(database, business_id, invitation_id, cancelled_by=None):
    inv_ref = (
        database.collection("businesses")
        .document(business_id)
        .collection("invitations")
        .document(invitation_id)
    )
    inv_snap = inv_ref.get()
    if not inv_snap.exists:
        raise ApiError("invitation_not_found", "Invitation not found.", 404)

    updates = {
        "status": "cancelled",
        "cancelledBy": cancelled_by,
        "cancelledAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }
    inv_ref.update(updates)

    top_ref = database.collection("businessInvitations").document(invitation_id)
    if top_ref.get().exists:
        top_ref.update(updates)

    return {"id": invitation_id, "status": "cancelled"}


def claim_pending_invitations_for_user(database, firebase_user):
    email = (firebase_user.get("email") or "").lower().strip()
    uid = firebase_user.get("uid")
    if not email or not uid:
        return []

    try:
        invitations = list(
            database.collection("businessInvitations")
            .where("email", "==", email)
            .where("status", "==", "pending")
            .stream()
        )
    except Exception:
        return []

    claimed_business_ids = []

    for inv_snap in invitations:
        inv = inv_snap.to_dict() or {}
        business_id = inv.get("businessId")
        if not business_id:
            continue

        role = inv.get("role") or "viewer"
        permissions = inv.get("permissions") or ROLE_PERMISSIONS.get(role, ["orders:read"])

        # Create active member document
        database.collection("businesses").document(business_id).collection("members").document(uid).set(
            {
                "uid": uid,
                "role": role,
                "permissions": permissions,
                "status": "active",
                "invitedBy": inv.get("invitedBy", ""),
                "joinedAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        timestamp = firestore.SERVER_TIMESTAMP
        inv_updates = {
            "status": "accepted",
            "acceptedByUid": uid,
            "acceptedAt": timestamp,
            "updatedAt": timestamp,
        }
        try:
            inv_snap.reference.update(inv_updates)
            inv_id = inv.get("id") or inv_snap.id
            sub_ref = (
                database.collection("businesses")
                .document(business_id)
                .collection("invitations")
                .document(inv_id)
            )
            if sub_ref.get().exists:
                sub_ref.update(inv_updates)
        except Exception:
            pass

        claimed_business_ids.append(business_id)

    if claimed_business_ids:
        user_ref = database.collection("users").document(uid)
        user_snap = user_ref.get()
        user_dict = user_snap.to_dict() if user_snap.exists else {}
        user_payload = {
            "uid": uid,
            "displayName": firebase_user.get("name") or email,
            "email": email,
            "businessIds": firestore.ArrayUnion(claimed_business_ids),
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
        if not user_dict.get("defaultBusinessId"):
            user_payload["defaultBusinessId"] = claimed_business_ids[0]
        user_ref.set(user_payload, merge=True)

    return claimed_business_ids


def get_invitation_by_token(database, token):
    inv_ref = database.collection("businessInvitations").document(token)
    inv_snap = inv_ref.get()
    if not inv_snap.exists:
        raise ApiError("invitation_not_found", "Invitation not found or has expired.", 404)
    inv = inv_snap.to_dict() or {}
    if inv.get("status") != "pending":
        raise ApiError("invitation_invalid", f"This invitation has already been {inv.get('status', 'used')}.", 410)
    return {
        "id": token,
        "businessId": inv.get("businessId"),
        "businessName": inv.get("businessName") or "Store",
        "email": inv.get("email"),
        "role": inv.get("role"),
        "permissions": inv.get("permissions") or [],
    }
