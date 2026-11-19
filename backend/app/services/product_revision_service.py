"""Track product cache freshness for web/mobile writes without scanning the inventory."""

from uuid import uuid4


def product_revision_reference(database, business_id):
    return database.collection("businesses").document(business_id).collection("_cacheVersions").document("products")


def mark_products_changed(database, business_id, writer):
    """Publish a new opaque revision atomically with the product batch/transaction."""
    writer.set(product_revision_reference(database, business_id), {"revision": uuid4().hex})


def get_product_revision(database, business_id):
    """Existing businesses start at zero; their next product write creates the marker."""
    snapshot = product_revision_reference(database, business_id).get()
    return (snapshot.to_dict() or {}).get("revision", "0")
