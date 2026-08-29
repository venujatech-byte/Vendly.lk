from flask import Blueprint, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.courier_service import (
    create_courier,
    list_couriers,
    recommend_couriers,
    save_courier_export_template,
    update_courier,
)
from app.services.numbers import non_negative_integer


couriers_blueprint = Blueprint("couriers", __name__, url_prefix="/api/v1")


@couriers_blueprint.get("/businesses/<business_id>/couriers")
@require_firebase_user
@require_business_member(permission="couriers:read")
def get_couriers(business_id):
    couriers = list_couriers(get_firestore_client(), business_id)
    return jsonify({"couriers": couriers})


@couriers_blueprint.post("/businesses/<business_id>/couriers")
@require_firebase_user
@require_business_member("owner", "admin", permission="couriers:manage")
def add_courier(business_id):
    courier = create_courier(
        get_firestore_client(),
        business_id,
        get_json_object(),
    )
    return jsonify({"courier": courier}), 201


@couriers_blueprint.patch("/businesses/<business_id>/couriers/<courier_id>")
@require_firebase_user
@require_business_member("owner", "admin", permission="couriers:manage")
def edit_courier(business_id, courier_id):
    courier = update_courier(
        get_firestore_client(),
        business_id,
        courier_id,
        get_json_object(),
    )
    return jsonify({"courier": courier})


@couriers_blueprint.post(
    "/businesses/<business_id>/couriers/<courier_id>/order-export-template",
)
@require_firebase_user
@require_business_member("owner", "admin", permission="couriers:manage")
def upload_order_export_template(business_id, courier_id):
    uploaded_file = request.files.get("file")
    if uploaded_file is None:
        return jsonify(
            {
                "error": {
                    "code": "missing_export_template",
                    "message": "Choose an Excel template to upload.",
                },
            },
        ), 422

    courier = save_courier_export_template(
        get_firestore_client(),
        business_id,
        courier_id,
        uploaded_file,
    )
    return jsonify({"courier": courier})


@couriers_blueprint.post("/businesses/<business_id>/couriers/recommend")
@require_firebase_user
@require_business_member(permission="couriers:read")
def recommend_for_order(business_id):
    payload = get_json_object()

    try:
        weight_grams = non_negative_integer(
            payload.get("totalWeightGrams"),
            "Total weight",
        )
        if weight_grams == 0:
            raise ValueError("Total weight must be greater than zero.")
    except ValueError as error:
        return jsonify(
            {
                "error": {
                    "code": "validation_error",
                    "message": str(error),
                },
            },
        ), 422

    recommendations = recommend_couriers(
        get_firestore_client(),
        business_id,
        weight_grams,
        payload.get("district"),
    )
    return jsonify({"recommendations": recommendations})
