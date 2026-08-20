from flask import Blueprint, g, jsonify

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.member_service import add_member, list_members, update_member


members_blueprint = Blueprint("members", __name__, url_prefix="/api/v1")


@members_blueprint.get("/businesses/<business_id>/members")
@require_firebase_user
@require_business_member("owner", "admin", permission="staff:manage")
def get_members(business_id):
    return jsonify(
        {"members": list_members(get_firestore_client(), business_id)},
    )


@members_blueprint.post("/businesses/<business_id>/members")
@require_firebase_user
@require_business_member("owner", "admin", permission="staff:manage")
def create_member(business_id):
    member = add_member(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"member": member}), 201


@members_blueprint.patch("/businesses/<business_id>/members/<member_uid>")
@require_firebase_user
@require_business_member("owner", "admin", permission="staff:manage")
def edit_member(business_id, member_uid):
    member = update_member(
        get_firestore_client(),
        business_id,
        member_uid,
        get_json_object(),
    )
    return jsonify({"member": member})
