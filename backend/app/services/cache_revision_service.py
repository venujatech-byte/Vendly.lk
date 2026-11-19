"""Track list-cache freshness for web/mobile writes without scanning business data."""

from uuid import uuid4


def cache_revision_reference(database, business_id, collection):
    return database.collection("businesses").document(business_id).collection("_cacheVersions").document(collection)


def mark_cache_changed(database, business_id, collection, writer):
    """Publish an opaque revision atomically with its collection's batch/transaction."""
    writer.set(cache_revision_reference(database, business_id, collection), {"revision": uuid4().hex})


def get_cache_revision(database, business_id, collection):
    """Existing businesses start at zero; their next tracked write creates the marker."""
    snapshot = cache_revision_reference(database, business_id, collection).get()
    return (snapshot.to_dict() or {}).get("revision", "0")
