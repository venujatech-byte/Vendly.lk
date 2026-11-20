from flask import Blueprint, current_app, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.media_service import payment_receipt_download_url, upload_review_data_url
from app.services.order_service import (
    create_order,
    get_order,
    list_orders_page,
    attach_order_payment_receipt,
    record_order_payment,
    update_order_status,
    update_order,
)
from app.services.cache_revision_service import get_cache_revision
from app.services.analytics_service import bump_analytics_version


orders_blueprint = Blueprint("orders", __name__, url_prefix="/api/v1")


def _receipt_cloudinary_config():
    # Keep receipt upload and download credentials on the server.
    return {
        "cloud_name": current_app.config.get("CLOUDINARY_CLOUD_NAME"),
        "api_key": current_app.config.get("CLOUDINARY_API_KEY"),
        "api_secret": current_app.config.get("CLOUDINARY_API_SECRET"),
    }


@orders_blueprint.get("/businesses/<business_id>/orders")
@require_firebase_user
@require_business_member(permission="orders:read")
def get_orders(business_id):
    # Bound each response while retaining the same tenant and read-permission checks on every page.
    result = list_orders_page(
        get_firestore_client(),
        business_id,
        after=request.args.get("after"),
        status=request.args.get("status"),
        search=request.args.get("search"),
        date_from=request.args.get("dateFrom"),
        date_to=request.args.get("dateTo"),
        courier_id=request.args.get("courierId"),
    )
    return jsonify(result)


# Recheck current order-read permission before allowing browser-cached order reuse.
@orders_blueprint.get("/businesses/<business_id>/orders/cache/version")
@require_firebase_user
@require_business_member(permission="orders:read")
def orders_version(business_id):
    return jsonify({"revision": get_cache_revision(get_firestore_client(), business_id, "orders")})


@orders_blueprint.post("/businesses/<business_id>/orders")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def add_order(business_id):
    payload = dict(get_json_object())
    receipt = payload.pop("receiptImage", "")
    order = create_order(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        payload,
    )
    bump_analytics_version(get_firestore_client(), business_id)

    # Uploaded after the order exists, because the receipt is stored against
    # it. The same path the Record payment popup uses, so a payment entered at
    # creation and one entered later leave identical records.
    if receipt:
        asset = upload_review_data_url(
            receipt,
            business_id,
            order["id"],
            _receipt_cloudinary_config(),
            folder="payment-receipts", authenticated=True,
        )
        order = attach_order_payment_receipt(
            get_firestore_client(),
            business_id,
            order["id"],
            g.current_user["uid"],
            "",
            order.get("paidAmountMinor", 0),
            receipt_asset=asset,
        )

    return jsonify({"order": order}), 201


@orders_blueprint.get("/businesses/<business_id>/orders/<order_id>")
@require_firebase_user
@require_business_member(permission="orders:read")
def get_order_by_id(business_id, order_id):
    order = get_order(get_firestore_client(), business_id, order_id)
    return jsonify({"order": order})


@orders_blueprint.get("/businesses/<business_id>/orders/<order_id>/payment-receipts/links")
@require_firebase_user
@require_business_member(permission="orders:read")
def get_payment_receipt_links(business_id, order_id):
    # Sign only receipts attached to this order after the current membership check.
    order = get_order(get_firestore_client(), business_id, order_id)
    config = _receipt_cloudinary_config()
    links = {
        asset["id"]: payment_receipt_download_url(business_id, order_id, asset, config)
        for receipt in order.get("paymentReceipts") or []
        if (asset := receipt.get("privateAsset"))
    }
    response = jsonify({"links": links})
    response.headers["Cache-Control"] = "no-store"
    return response


@orders_blueprint.patch(
    "/businesses/<business_id>/orders/<order_id>/payment",
)
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def record_payment(business_id, order_id):
    """Record money received against an order, with the receipt."""
    payload = dict(get_json_object())
    receipt = payload.pop("receiptImage", "")

    # Reuse image validation while requesting authenticated delivery for the receipt.
    asset = upload_review_data_url(
        receipt, business_id, order_id, _receipt_cloudinary_config(),
        folder="payment-receipts", authenticated=True,
    ) if receipt else None

    order = record_order_payment(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        payload,
        receipt_asset=asset,
    )
    bump_analytics_version(get_firestore_client(), business_id)
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
    bump_analytics_version(get_firestore_client(), business_id)
    return jsonify({"order": order})


@orders_blueprint.patch("/businesses/<business_id>/orders/<order_id>")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def edit_order(business_id, order_id):
    order = update_order(
        get_firestore_client(), business_id, order_id,
        g.current_user["uid"], get_json_object(),
    )
    bump_analytics_version(get_firestore_client(), business_id)
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
    bump_analytics_version(get_firestore_client(), business_id)
    return jsonify({"order": order})
