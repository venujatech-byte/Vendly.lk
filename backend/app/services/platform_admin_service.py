"""Read-only reporting used by the internal Vendly platform dashboard."""

from app.core.serialization import serialize_snapshot


SELLER_PAGE_SIZE = 25


def _collection_count(collection_reference):
    """Return a Firestore aggregation count without reading every document."""
    results = collection_reference.count().get()
    return int(results[0][0].value) if results else 0


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
            "orders": _collection_count(database.collection_group("orders")),
            "products": _collection_count(database.collection_group("products")),
            "customers": _collection_count(database.collection_group("customers")),
        },
        "sellers": sellers,
        "nextCursor": sellers[-1]["id"] if has_more and sellers else None,
        "hasMore": has_more,
    }
