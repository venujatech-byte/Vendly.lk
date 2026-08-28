from flask import Blueprint, current_app, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.media_service import upload_review_data_url
from app.services.order_service import (
    create_order,
    get_order,
    list_orders,
    record_order_payment,
    update_order_status,
    update_order,
)


orders_blueprint = Blueprint("orders", __name__, url_prefix="/api/v1")


@orders_blueprint.get("/businesses/<business_id>/orders")
@require_firebase_user
@require_business_member(permission="orders:read")
def get_orders(business_id):
    orders = list_orders(
        get_firestore_client(),
        business_id,
        status=request.args.get("status"),
        search=request.args.get("search"),
        date_from=request.args.get("dateFrom"),
        date_to=request.args.get("dateTo"),
        courier_id=request.args.get("courierId"),
    )
    return jsonify({"orders": orders})


@orders_blueprint.post("/businesses/<business_id>/orders")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def add_order(business_id):
    order = create_order(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"order": order}), 201


@orders_blueprint.get("/businesses/<business_id>/orders/<order_id>")
@require_firebase_user
@require_business_member(permission="orders:read")
def get_order_by_id(business_id, order_id):
    order = get_order(get_firestore_client(), business_id, order_id)
    return jsonify({"order": order})


@orders_blueprint.patch(
    "/businesses/<business_id>/orders/<order_id>/payment",
)
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def record_payment(business_id, order_id):
    """Record money received against an order, with the receipt."""
    payload = dict(get_json_object())
    receipt = payload.pop("receiptImage", "")

    # The receipt arrives as a data URL, the same shape the chatbot uses for
    # customer images, so it goes through the same uploader rather than a
    # second path to the same bucket.
    if receipt:
        uploaded = upload_review_data_url(
            receipt,
            business_id,
            order_id,
            {
                "cloud_name": current_app.config.get("CLOUDINARY_CLOUD_NAME"),
                "api_key": current_app.config.get("CLOUDINARY_API_KEY"),
                "api_secret": current_app.config.get("CLOUDINARY_API_SECRET"),
            },
            folder="payment-receipts",
        )
        payload["receiptUrl"] = uploaded["url"]

    order = record_order_payment(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        payload,
    )
    return jsonify({"order": order})


@orders_blueprint.patch(
    "/businesses/<business_id>/orders/<order_id>/status",
)
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def change_order_status(business_id, order_id):
    order = update_order_status(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"order": order})


@orders_blueprint.patch("/businesses/<business_id>/orders/<order_id>")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def edit_order(business_id, order_id):
    order = update_order(
        get_firestore_client(), business_id, order_id,
        g.current_user["uid"], get_json_object(),
    )
    return jsonify({"order": order})


@orders_blueprint.delete("/businesses/<business_id>/orders/<order_id>")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def remove_order(business_id, order_id):
    order = update_order_status(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        {"status": "cancelled", "note": "Removed by seller"},
    )
    return jsonify({"order": order})
