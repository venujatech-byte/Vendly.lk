from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import optional_text, required_text, slugify


def list_categories(database, business_id):
    query = (
        database.collection("businesses")
        .document(business_id)
        .collection("categories")
        .order_by("sortOrder")
    )

    return [serialize_snapshot(snapshot) for snapshot in query.stream()]


def create_category(database, business_id, payload):
    try:
        name = required_text(payload.get("name"), "Category name")
        description = optional_text(payload.get("description"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    category_collection = (
        database.collection("businesses")
        .document(business_id)
        .collection("categories")
    )
    slug = slugify(name)

    if slug:
        duplicate_query = category_collection.where(
            filter=FieldFilter("slug", "==", slug),
        ).limit(1)

        if next(duplicate_query.stream(), None) is not None:
            raise ApiError(
                "category_already_exists",
                "A category with this name already exists.",
                409,
            )

    category_reference = category_collection.document()
    sort_order = payload.get("sortOrder", 0)

    if not isinstance(sort_order, int) or sort_order < 0:
        raise ApiError(
            "validation_error",
            "Sort order must be a positive whole number or zero.",
            422,
        )

    category_reference.set(
        {
            "name": name,
            "slug": slug or category_reference.id.lower(),
            "description": description,
            "status": "active",
            "sortOrder": sort_order,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )

    return serialize_snapshot(category_reference.get())


def update_category(database, business_id, category_id, payload):
    category_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("categories")
        .document(category_id)
    )
    category_snapshot = category_reference.get()

    if not category_snapshot.exists:
        raise ApiError("category_not_found", "Category not found.", 404)

    changes = {"updatedAt": firestore.SERVER_TIMESTAMP}

    try:
        if "name" in payload:
            changes["name"] = required_text(payload.get("name"), "Category name")
            changes["slug"] = slugify(changes["name"]) or category_id.lower()

        if "description" in payload:
            changes["description"] = optional_text(payload.get("description"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if "status" in payload:
        status = payload.get("status")

        if status not in {"active", "archived"}:
            raise ApiError(
                "validation_error",
                "Status must be active or archived.",
                422,
            )

        changes["status"] = status

    if "sortOrder" in payload:
        sort_order = payload.get("sortOrder")

        if not isinstance(sort_order, int) or sort_order < 0:
            raise ApiError(
                "validation_error",
                "Sort order must be a positive whole number or zero.",
                422,
            )

        changes["sortOrder"] = sort_order

    category_reference.update(changes)

    return serialize_snapshot(category_reference.get())
