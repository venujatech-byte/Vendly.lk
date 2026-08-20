from flask import Blueprint, jsonify

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.category_service import (
    create_category,
    list_categories,
    update_category,
)


categories_blueprint = Blueprint("categories", __name__, url_prefix="/api/v1")


@categories_blueprint.get("/businesses/<business_id>/categories")
@require_firebase_user
@require_business_member(permission="inventory:read")
def get_categories(business_id):
    categories = list_categories(get_firestore_client(), business_id)
    return jsonify({"categories": categories})


@categories_blueprint.post("/businesses/<business_id>/categories")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def add_category(business_id):
    payload = get_json_object()

    category = create_category(
        get_firestore_client(),
        business_id,
        payload,
    )
    return jsonify({"category": category}), 201


@categories_blueprint.patch("/businesses/<business_id>/categories/<category_id>")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def edit_category(business_id, category_id):
    payload = get_json_object()

    category = update_category(
        get_firestore_client(),
        business_id,
        category_id,
        payload,
    )
    return jsonify({"category": category})


@categories_blueprint.delete("/businesses/<business_id>/categories/<category_id>")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def remove_category(business_id, category_id):
    category = update_category(
        get_firestore_client(),
        business_id,
        category_id,
        {"status": "archived"},
    )
    return jsonify({"category": category})
