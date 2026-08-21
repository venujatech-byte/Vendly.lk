from flask import Blueprint, g, jsonify, request

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
from app.services.fraud_service import (
    change_customer_fraud_risk,
    list_seller_fraud_customers,
    remove_customer_from_fraud_list,
    report_customer,
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


@customers_blueprint.get("/businesses/<business_id>/fraud-customers")
@require_firebase_user
@require_business_member(permission="customers:read")
def get_fraud_customers(business_id):
    customers = list_seller_fraud_customers(
        get_firestore_client(),
        business_id,
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


@customers_blueprint.post(
    "/businesses/<business_id>/customers/<customer_id>/fraud-report",
)
@require_firebase_user
@require_business_member(
    "owner",
    "admin",
    "order_manager",
    "support",
    permission="customers:manage",
)
def add_customer_fraud_report(business_id, customer_id):
    report = report_customer(
        get_firestore_client(),
        business_id,
        customer_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"fraudReport": report}), 201


@customers_blueprint.patch(
    "/businesses/<business_id>/customers/<customer_id>/fraud-risk",
)
@require_firebase_user
@require_business_member(
    "owner",
    "admin",
    "order_manager",
    "support",
    permission="customers:manage",
)
def change_fraud_risk(business_id, customer_id):
    customer = change_customer_fraud_risk(
        get_firestore_client(),
        business_id,
        customer_id,
        get_json_object(),
    )
    return jsonify({"customer": customer})


@customers_blueprint.delete(
    "/businesses/<business_id>/customers/<customer_id>/fraud-profile",
)
@require_firebase_user
@require_business_member(
    "owner",
    "admin",
    "order_manager",
    "support",
    permission="customers:manage",
)
def remove_fraud_profile(business_id, customer_id):
    result = remove_customer_from_fraud_list(
        get_firestore_client(),
        business_id,
        customer_id,
    )
    return jsonify(result)
