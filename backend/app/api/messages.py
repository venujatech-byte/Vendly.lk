from flask import Blueprint, g, jsonify

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.message_service import (
    get_chat_messages,
    list_chat_sessions,
    mark_chat_read,
    set_chat_ai_paused,
    send_seller_message,
)


messages_blueprint = Blueprint("messages", __name__, url_prefix="/api/v1")


@messages_blueprint.get("/businesses/<business_id>/chat-sessions")
@require_firebase_user
@require_business_member(permission="customers:read")
def get_business_chat_sessions(business_id):
    sessions = list_chat_sessions(get_firestore_client(), business_id)
    return jsonify({"sessions": sessions})


@messages_blueprint.get("/businesses/<business_id>/chat-sessions/<session_id>/messages")
@require_firebase_user
@require_business_member(permission="customers:read")
def get_business_chat_messages(business_id, session_id):
    return jsonify(get_chat_messages(get_firestore_client(), business_id, session_id))


@messages_blueprint.post("/businesses/<business_id>/chat-sessions/<session_id>/messages")
@require_firebase_user
@require_business_member(permission="customers:manage")
def add_business_chat_message(business_id, session_id):
    message = send_seller_message(
        get_firestore_client(),
        business_id,
        session_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"message": message}), 201


@messages_blueprint.patch("/businesses/<business_id>/chat-sessions/<session_id>/read")
@require_firebase_user
@require_business_member(permission="customers:read")
def read_business_chat(business_id, session_id):
    return jsonify(mark_chat_read(get_firestore_client(), business_id, session_id))


@messages_blueprint.patch(
    "/businesses/<business_id>/chat-sessions/<session_id>/ai",
)
@require_firebase_user
@require_business_member(permission="customers:manage")
def update_business_chat_ai(business_id, session_id):
    payload = get_json_object()
    if not isinstance(payload.get("paused"), bool):
        return jsonify(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Paused must be true or false.",
                }
            }
        ), 422
    return jsonify(
        set_chat_ai_paused(
            get_firestore_client(),
            business_id,
            session_id,
            payload["paused"],
        )
    )
