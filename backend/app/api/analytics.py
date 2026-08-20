from flask import Blueprint, jsonify

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.services.analytics_service import get_business_analytics


analytics_blueprint = Blueprint("analytics", __name__, url_prefix="/api/v1")


@analytics_blueprint.get("/businesses/<business_id>/analytics/overview")
@require_firebase_user
@require_business_member(permission="analytics:read")
def analytics_overview(business_id):
    return jsonify(
        {"analytics": get_business_analytics(get_firestore_client(), business_id)},
    )
