from flask import Blueprint, current_app, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.errors import ApiError
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.billing_service import (
    create_checkout,
    get_billing_summary,
    process_payhere_notification,
)


billing_blueprint = Blueprint("billing", __name__, url_prefix="/api/v1")


def _payhere_settings():
    return {
        "sandbox": current_app.config.get("PAYHERE_SANDBOX", True),
        "merchant_id": current_app.config.get("PAYHERE_MERCHANT_ID"),
        "merchant_secret": current_app.config.get("PAYHERE_MERCHANT_SECRET"),
        "frontend_url": current_app.config.get("FRONTEND_PUBLIC_URL"),
        "backend_url": current_app.config.get("BACKEND_PUBLIC_URL"),
    }


@billing_blueprint.get("/businesses/<business_id>/billing")
@require_firebase_user
@require_business_member()
def get_billing(business_id):
    settings = _payhere_settings()
    return jsonify(
        {
            "billing": get_billing_summary(
                get_firestore_client(),
                business_id,
                payhere_configured=bool(
                    settings["merchant_id"] and settings["merchant_secret"]
                ),
                sandbox=settings["sandbox"],
            ),
        },
    )


@billing_blueprint.post("/businesses/<business_id>/billing/checkout")
@require_firebase_user
@require_business_member("owner")
def start_billing_checkout(business_id):
    checkout = create_checkout(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        get_json_object(),
        _payhere_settings(),
    )
    return jsonify({"checkout": checkout}), 201


@billing_blueprint.post("/billing/payhere/notify")
def receive_payhere_notification():
    settings = _payhere_settings()
    if not settings["merchant_id"] or not settings["merchant_secret"]:
        raise ApiError("payhere_not_configured", "PayHere is not configured.", 503)

    status = process_payhere_notification(
        get_firestore_client(),
        request.form,
        settings["merchant_id"],
        settings["merchant_secret"],
    )
    return jsonify({"received": True, "status": status})
