from flask import Blueprint, g, jsonify

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.ai_service import ai_status
from app.services.business_service import create_or_get_business, update_public_contact


businesses_blueprint = Blueprint("businesses", __name__, url_prefix="/api/v1")


@businesses_blueprint.post("/businesses")
@require_firebase_user
def create_business():
    payload = get_json_object()

    business, was_created = create_or_get_business(
        get_firestore_client(),
        g.current_user,
        payload,
    )

    return jsonify({"business": business}), 201 if was_created else 200


@businesses_blueprint.patch("/businesses/<business_id>/public-contact")
@require_firebase_user
@require_business_member("owner", "admin")
def edit_public_contact(business_id):
    business = update_public_contact(
        get_firestore_client(),
        business_id,
        get_json_object(),
    )
    return jsonify({"business": business})


@businesses_blueprint.get("/businesses/<business_id>/ai-status")
@require_firebase_user
@require_business_member("owner", "admin")
def get_ai_status(business_id):
    """Report whether the chatbot's AI is working.

    A provider failure only reached the server log, so a seller whose bot had
    quietly dropped to simplified English had no way to find out. Restricted to
    owner/admin because the provider and model name are deployment details.
    """
    return jsonify({"aiStatus": ai_status()})
