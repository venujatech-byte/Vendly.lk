from flask import Blueprint, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_platform_admin
from app.core.firebase import get_firestore_client
from app.services.platform_admin_service import get_seller_dashboard
from app.services.aws_monitoring_service import get_aws_server_health


admin_blueprint = Blueprint("admin", __name__, url_prefix="/api/v1/admin")


@admin_blueprint.get("/server-health")
@require_firebase_user
@require_platform_admin
def get_server_health():
    return jsonify(get_aws_server_health())


@admin_blueprint.get("/sellers")
@require_firebase_user
@require_platform_admin
def list_sellers_for_platform_admin():
    return jsonify(
        get_seller_dashboard(
            get_firestore_client(),
            after=request.args.get("after", "").strip() or None,
        )
    )
