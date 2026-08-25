from flask import Blueprint, g, jsonify

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.rate_limit import limiter
from app.core.requests import get_json_object
from app.services.business_assistant_service import handle_business_assistant_message


business_assistant_blueprint = Blueprint(
    "business_assistant",
    __name__,
    url_prefix="/api/v1",
)


@business_assistant_blueprint.post(
    "/businesses/<business_id>/assistant/messages",
)
@limiter.limit("30 per minute")
@require_firebase_user
@require_business_member()
def business_assistant_message(business_id):
    response = handle_business_assistant_message(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        g.membership,
        get_json_object(),
    )
    return jsonify({"assistant": response})
