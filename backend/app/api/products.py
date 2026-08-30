from datetime import datetime, timezone

from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request, send_file

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
from app.services.spreadsheet_service import (
    export_inventory_workbook,
    import_inventory_workbook,
)


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


@products_blueprint.get("/businesses/<business_id>/inventory-export.xlsx")
@require_firebase_user
@require_business_member(permission="inventory:read")
def download_inventory(business_id):
    workbook = export_inventory_workbook(
        get_firestore_client(),
        business_id,
        product_ids=request.args.getlist("productId"),
    )
    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return send_file(
        workbook,
        as_attachment=True,
        download_name=f"vendly-inventory-{date_stamp}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@products_blueprint.post("/businesses/<business_id>/inventory-import")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def upload_inventory(business_id):
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"error": {"code": "file_required", "message": "Choose a Vendly inventory workbook."}}), 422
    if not upload.filename.lower().endswith(".xlsx"):
        return jsonify({"error": {"code": "invalid_file_type", "message": "Inventory imports must use the .xlsx format."}}), 422

    result = import_inventory_workbook(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        upload.stream,
    )
    return jsonify({"import": result})


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

    product_info = generate_product_description(payload)
    generated_by = "ai"
    if not product_info:
        description = (
            f"{name} is available from this seller. Add the product's key features, "
            "materials, compatibility, usage details and important limitations here "
            "so customers can make an informed purchase."
        )
        product_info = {
            "product_name": name,
            "brand": payload.get("brand") or None,
            "model": payload.get("model") or None,
            "category": payload.get("categoryName") or "",
            "description": description,
            "highlights": [],
            "specifications": [],
            "missing_information": ["Verified product specifications"],
            "confidence": "low",
        }
        generated_by = "template"

    return jsonify({
        "description": product_info["description"],
        "productInfo": product_info,
        "generatedBy": generated_by,
    })


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
