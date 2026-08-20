from flask import Blueprint, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.services.search_service import global_search


search_blueprint = Blueprint("search", __name__, url_prefix="/api/v1")


@search_blueprint.get("/businesses/<business_id>/search")
@require_firebase_user
@require_business_member()
def search_business(business_id):
    return jsonify(
        {
            "results": global_search(
                get_firestore_client(),
                business_id,
                request.args.get("q", ""),
            ),
        },
    )
