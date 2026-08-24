from flask import Blueprint, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.shop_sale_service import (
    create_shop_sale, create_warranty_claim, delete_shop_sale,
    list_shop_sales, list_warranty_claims,
)

shop_sales_blueprint = Blueprint("shop_sales", __name__, url_prefix="/api/v1")


@shop_sales_blueprint.get("/businesses/<business_id>/shop-sales")
@require_firebase_user
@require_business_member(permission="orders:read")
def get_shop_sales(business_id):
    return jsonify({"shopSales": list_shop_sales(
        get_firestore_client(), business_id, request.args.get("search"),
        request.args.get("dateFrom"), request.args.get("dateTo"),
    )})


@shop_sales_blueprint.post("/businesses/<business_id>/shop-sales")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def add_shop_sale(business_id):
    sale = create_shop_sale(get_firestore_client(), business_id, g.current_user["uid"], get_json_object())
    return jsonify({"shopSale": sale}), 201


@shop_sales_blueprint.delete("/businesses/<business_id>/shop-sales/<sale_id>")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def remove_shop_sale(business_id, sale_id):
    sale = delete_shop_sale(get_firestore_client(), business_id, sale_id, g.current_user["uid"])
    return jsonify({"shopSale": sale})


@shop_sales_blueprint.get("/businesses/<business_id>/warranty-claims")
@require_firebase_user
@require_business_member(permission="orders:read")
def get_warranty_claims(business_id):
    return jsonify({"warrantyClaims": list_warranty_claims(get_firestore_client(), business_id)})


@shop_sales_blueprint.post("/businesses/<business_id>/warranty-claims")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def add_warranty_claim(business_id):
    claim = create_warranty_claim(get_firestore_client(), business_id, g.current_user["uid"], get_json_object())
    return jsonify({"warrantyClaim": claim}), 201
