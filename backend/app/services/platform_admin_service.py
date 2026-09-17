"""Read-only reporting used by the internal Vendly platform dashboard."""

from app.core.serialization import serialize_snapshot
from app.core.errors import ApiError


SELLER_PAGE_SIZE = 25


def _collection_count(collection_reference):
    """Return a Firestore aggregation count, falling back to document streaming if needed."""
    try:
        results = collection_reference.count().get()
        if results and len(results) > 0 and len(results[0]) > 0:
            val = int(results[0][0].value)
            if val > 0:
                return val
    except Exception:
        pass

    try:
        # Fallback for emulator or environments where count() aggregation returns 0 or fails
        return len(list(collection_reference.select([]).stream()))
    except Exception:
        return 0


def _total_chats_count(database):
    """Return total number of chat sessions across all accounts in the system."""
    # 1. Primary source: top-level publicChatSessions collection in Firestore
    chats = _collection_count(database.collection("publicChatSessions"))
    if chats > 0:
        return chats

    # 2. Check collection groups (e.g. if chats or messages exist as subcollections)
    for group_name in ("chatSessions", "chats", "messages"):
        try:
            group_count = _collection_count(database.collection_group(group_name))
            if group_count > 0:
                return group_count
        except Exception:
            pass

    # 3. Check Firebase Realtime Database (RTDB) chatMessages
    try:
        from app.core.firebase import get_rtdb_reference
        rtdb_ref = get_rtdb_reference("chatMessages")
        if rtdb_ref is not None:
            data = rtdb_ref.get()
            if isinstance(data, dict) and len(data) > 0:
                return len(data)
    except Exception:
        pass

    try:
        act_ref = get_rtdb_reference("businessChatActivity")
        if act_ref is not None:
            act_data = act_ref.get()
            if isinstance(act_data, dict) and len(act_data) > 0:
                return len(act_data)
    except Exception:
        pass

    return 0


def _seller_chats_count(database, business_id):
    """Return number of chats belonging to a specific business account."""
    try:
        count = _collection_count(
            database.collection("publicChatSessions").where("businessId", "==", business_id)
        )
        if count > 0:
            return count
    except Exception:
        pass

    try:
        from app.core.firebase import get_rtdb_reference
        act_ref = get_rtdb_reference(f"businessChatActivity/{business_id}")
        if act_ref is not None and act_ref.get():
            return 1
    except Exception:
        pass

    return 0


def get_seller_dashboard(database, limit=SELLER_PAGE_SIZE, after=None):
    """Return one bounded page of seller accounts and lightweight statistics."""
    limit = max(1, min(int(limit), SELLER_PAGE_SIZE))
    businesses = database.collection("businesses").order_by(
        "createdAt", direction="DESCENDING"
    )
    if after:
        cursor_snapshot = database.collection("businesses").document(after).get()
        if cursor_snapshot.exists:
            businesses = businesses.start_after(cursor_snapshot)

    business_snapshots = list(businesses.limit(limit + 1).stream())
    has_more = len(business_snapshots) > limit
    business_snapshots = business_snapshots[:limit]

    owner_references = [
        database.collection("users").document(snapshot.to_dict().get("ownerUid", ""))
        for snapshot in business_snapshots
        if snapshot.to_dict().get("ownerUid")
    ]
    owner_profiles = {
        snapshot.id: snapshot.to_dict() or {}
        for snapshot in (database.get_all(owner_references) if owner_references else [])
        if snapshot.exists
    }

    sellers = []
    for snapshot in business_snapshots:
        business = serialize_snapshot(snapshot)
        owner = owner_profiles.get(business.get("ownerUid"), {})
        stats = {
            "orders": _collection_count(snapshot.reference.collection("orders")),
            "products": _collection_count(snapshot.reference.collection("products")),
            "customers": _collection_count(snapshot.reference.collection("customers")),
            "chats": _seller_chats_count(database, business["id"]),
        }
        sellers.append(
            {
                "id": business["id"],
                "businessName": business.get("name") or "Unnamed business",
                "status": business.get("status", "active"),
                "createdAt": business.get("createdAt"),
                "lastActivityAt": business.get("updatedAt") or business.get("createdAt"),
                "owner": {
                    "name": owner.get("displayName") or "Business owner",
                    "email": owner.get("email") or business.get("email") or "",
                },
                "stats": stats,
            }
        )

    return {
        "summary": {
            # One aggregate query per collection group keeps the platform-wide
            # totals accurate even when the seller table is paginated.
            "registeredSellers": _collection_count(database.collection("businesses")),
            "activeSellers": _collection_count(
                database.collection("businesses").where("status", "==", "active")
            ),
            "totalChats": _total_chats_count(database),
            "chats": _total_chats_count(database),
            "orders": _collection_count(database.collection_group("orders")),
            "products": _collection_count(database.collection_group("products")),
            "customers": _collection_count(database.collection_group("customers")),
        },
        "sellers": sellers,
        "nextCursor": sellers[-1]["id"] if has_more and sellers else None,
        "hasMore": has_more,
    }


def get_seller_detail(database, business_id):
    """Return a single seller profile and a small recent-activity sample."""
    business_snapshot = database.collection("businesses").document(business_id).get()
    if not business_snapshot.exists:
        raise ApiError("seller_not_found", "Seller business not found.", 404)

    business = serialize_snapshot(business_snapshot)
    owner_uid = business.get("ownerUid")
    owner_snapshot = (
        database.collection("users").document(owner_uid).get()
        if owner_uid else None
    )
    owner = owner_snapshot.to_dict() if owner_snapshot and owner_snapshot.exists else {}
    business_reference = business_snapshot.reference
    recent_orders = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("orders")
        .order_by("createdAt", direction="DESCENDING")
        .limit(5)
        .stream()
    ]

    return {
        "id": business["id"],
        "businessName": business.get("name") or "Unnamed business",
        "status": business.get("status", "active"),
        "createdAt": business.get("createdAt"),
        "lastActivityAt": business.get("updatedAt") or business.get("createdAt"),
        "shortCode": business.get("shortCode"),
        "contact": {
            "email": owner.get("email") or business.get("email") or "",
            "phone": business.get("phone") or business.get("publicPhone") or "",
        },
        "owner": {
            "name": owner.get("displayName") or "Business owner",
            "email": owner.get("email") or business.get("email") or "",
        },
        "stats": {
            "orders": _collection_count(business_reference.collection("orders")),
            "products": _collection_count(business_reference.collection("products")),
            "customers": _collection_count(business_reference.collection("customers")),
            "chats": _seller_chats_count(database, business["id"]),
        },
        "recentOrders": [
            {
                "id": order["id"],
                "orderNumber": order.get("orderNumber") or order["id"],
                "status": order.get("fulfilmentStatus", "unknown"),
                "totalAmountMinor": order.get("totalAmountMinor", 0),
                "createdAt": order.get("createdAt"),
            }
            for order in recent_orders
        ],
    }
