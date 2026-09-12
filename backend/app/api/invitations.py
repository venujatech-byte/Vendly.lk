from flask import Blueprint, jsonify

from app.core.firebase import get_firestore_client
from app.services.member_service import get_invitation_by_token


invitations_blueprint = Blueprint("invitations", __name__, url_prefix="/api/v1")


@invitations_blueprint.get("/invitations/<token>")
def get_invitation(token):
    invitation = get_invitation_by_token(get_firestore_client(), token)
    return jsonify({"invitation": invitation})
