from flask import Blueprint, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.customer_service import (
    create_customer,
    get_customer,
    list_customers,
    update_customer,
)


customers_blueprint = Blueprint("customers", __name__, url_prefix="/api/v1")


@customers_blueprint.get("/businesses/<business_id>/customers")
@require_firebase_user
@require_business_member(permission="customers:read")
def get_customers(business_id):
    customers = list_customers(
        get_firestore_client(),
        business_id,
        phone=request.args.get("phone"),
        search=request.args.get("search"),
    )
    return jsonify({"customers": customers})


@customers_blueprint.post("/businesses/<business_id>/customers")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", "support", permission="customers:manage")
def add_customer(business_id):
    customer = create_customer(
        get_firestore_client(),
        business_id,
        get_json_object(),
    )
    return jsonify({"customer": customer}), 201


@customers_blueprint.get("/businesses/<business_id>/customers/<customer_id>")
@require_firebase_user
@require_business_member(permission="customers:read")
def get_customer_by_id(business_id, customer_id):
    customer = get_customer(get_firestore_client(), business_id, customer_id)
    return jsonify({"customer": customer})


@customers_blueprint.patch("/businesses/<business_id>/customers/<customer_id>")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", "support", permission="customers:manage")
def edit_customer(business_id, customer_id):
    customer = update_customer(
        get_firestore_client(),
        business_id,
        customer_id,
        get_json_object(),
    )
    return jsonify({"customer": customer})
