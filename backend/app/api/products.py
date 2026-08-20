from flask import Blueprint, current_app, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.product_service import (
    adjust_variant_stock,
    create_product,
    get_product,
    list_products,
    update_product,
)
from app.services.media_service import upload_product_media, upload_variant_image
from app.services.ai_service import generate_product_description


products_blueprint = Blueprint("products", __name__, url_prefix="/api/v1")


@products_blueprint.get("/businesses/<business_id>/products")
@require_firebase_user
@require_business_member(permission="inventory:read")
def get_products(business_id):
    products = list_products(
        get_firestore_client(),
        business_id,
        category_id=request.args.get("categoryId"),
        status=request.args.get("status"),
    )
    return jsonify({"products": products})


@products_blueprint.post("/businesses/<business_id>/products")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def add_product(business_id):
    payload = get_json_object()

    product = create_product(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        payload,
    )
    return jsonify({"product": product}), 201


@products_blueprint.post("/businesses/<business_id>/products/generate-description")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def generate_description(business_id):
    payload = get_json_object()
    name = str(payload.get("name", "")).strip()
    if not name:
        return jsonify({"error": {"code": "validation_error", "message": "Enter a product name first."}}), 422

    description = generate_product_description(payload)
    generated_by = "ai"
    if not description:
        description = (
            f"{name} is available from this seller. Add the product's key features, "
            "materials, compatibility, usage details and important limitations here "
            "so customers can make an informed purchase."
        )
        generated_by = "template"

    return jsonify({"description": description, "generatedBy": generated_by})


@products_blueprint.get("/businesses/<business_id>/products/<product_id>")
@require_firebase_user
@require_business_member(permission="inventory:read")
def get_product_by_id(business_id, product_id):
    product = get_product(get_firestore_client(), business_id, product_id)
    return jsonify({"product": product})


@products_blueprint.patch("/businesses/<business_id>/products/<product_id>")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def edit_product(business_id, product_id):
    product = update_product(
        get_firestore_client(),
        business_id,
        product_id,
        get_json_object(),
    )
    return jsonify({"product": product})


@products_blueprint.delete("/businesses/<business_id>/products/<product_id>")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def remove_product(business_id, product_id):
    product = update_product(
        get_firestore_client(),
        business_id,
        product_id,
        {"status": "archived"},
    )
    return jsonify({"product": product})


@products_blueprint.post(
    "/businesses/<business_id>/products/<product_id>/variants/<variant_id>/adjust-stock",
)
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def adjust_stock(business_id, product_id, variant_id):
    product = adjust_variant_stock(
        get_firestore_client(),
        business_id,
        product_id,
        variant_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"product": product})


@products_blueprint.post(
    "/businesses/<business_id>/products/<product_id>/media",
)
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def add_product_media(business_id, product_id):
    product = upload_product_media(
        get_firestore_client(),
        business_id,
        product_id,
        g.current_user["uid"],
        request.files.getlist("files"),
        cloudinary_config={
            "cloud_name": current_app.config.get("CLOUDINARY_CLOUD_NAME"),
            "api_key": current_app.config.get("CLOUDINARY_API_KEY"),
            "api_secret": current_app.config.get("CLOUDINARY_API_SECRET"),
        },
    )
    return jsonify({"product": product}), 201


@products_blueprint.post("/businesses/<business_id>/products/<product_id>/variants/<variant_id>/image")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def add_variant_image(business_id, product_id, variant_id):
    upload = request.files.get("file")
    if upload is None:
        return jsonify({"error": {"code": "media_required", "message": "Choose a variant image."}}), 422
    product = upload_variant_image(
        get_firestore_client(), business_id, product_id, variant_id, upload,
        cloudinary_config={"cloud_name": current_app.config.get("CLOUDINARY_CLOUD_NAME"), "api_key": current_app.config.get("CLOUDINARY_API_KEY"), "api_secret": current_app.config.get("CLOUDINARY_API_SECRET")},
    )
    return jsonify({"product": product}), 201
