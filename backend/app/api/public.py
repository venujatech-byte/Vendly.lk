from flask import Blueprint, g, jsonify, request

from app.core.auth import optional_firebase_user, require_firebase_user
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.core.rate_limit import limiter, public_chat_key
from app.services.public_catalog_service import get_public_product, get_public_store
from app.services.public_chat_service import (
    answer_public_message,
    attach_public_chat_image,
    create_public_chat_order,
    create_public_chat_session,
    claim_public_chat_session,
    get_public_chat_messages,
)
from app.services.customer_portal_service import (
    get_customer_order,
    list_customer_chats,
    list_customer_orders,
)


public_blueprint = Blueprint("public", __name__, url_prefix="/api/v1/public")


@public_blueprint.get("/stores/<short_code>")
@limiter.limit("120 per minute")
def public_store(short_code):
    return jsonify(get_public_store(get_firestore_client(), short_code))


@public_blueprint.get("/products/<short_code>")
@limiter.limit("120 per minute")
def public_product(short_code):
    return jsonify(get_public_product(get_firestore_client(), short_code))


@public_blueprint.post("/chat/sessions")
@limiter.limit("20 per minute")
@optional_firebase_user
def start_public_chat():
    session = create_public_chat_session(
        get_firestore_client(),
        get_json_object(),
        (g.current_user or {}).get("uid"),
    )
    return jsonify(session), 201


@public_blueprint.post("/chat/sessions/<session_id>/messages")
@limiter.limit("60 per minute", key_func=public_chat_key)
def public_chat_message(session_id):
    response = answer_public_message(
        get_firestore_client(),
        session_id,
        request.headers.get("X-Chat-Session-Token", ""),
        get_json_object(),
    )
    return jsonify(response)


@public_blueprint.post("/chat/sessions/<session_id>/images")
# Uploading costs storage and an outbound request, so it is limited far more
# tightly than sending text.
@limiter.limit("10 per minute", key_func=public_chat_key)
def public_chat_image(session_id):
    response = attach_public_chat_image(
        get_firestore_client(),
        session_id,
        request.headers.get("X-Chat-Session-Token", ""),
        get_json_object(),
    )
    return jsonify(response), 201


@public_blueprint.get("/chat/sessions/<session_id>/messages")
@limiter.limit("120 per minute", key_func=public_chat_key)
def public_chat_messages(session_id):
    messages = get_public_chat_messages(
        get_firestore_client(),
        session_id,
        request.headers.get("X-Chat-Session-Token", ""),
    )
    return jsonify({"messages": messages})


@public_blueprint.post("/chat/sessions/<session_id>/orders")
@limiter.limit("6 per minute", key_func=public_chat_key)
@optional_firebase_user
def public_chat_order(session_id):
    session_token = request.headers.get("X-Chat-Session-Token", "")
    if g.current_user:
        claim_public_chat_session(
            get_firestore_client(),
            session_id,
            session_token,
            g.current_user["uid"],
        )
    order = create_public_chat_order(
        get_firestore_client(),
        session_id,
        session_token,
        get_json_object(),
    )
    return jsonify({"order": order}), 201


@public_blueprint.post("/chat/sessions/<session_id>/claim")
@require_firebase_user
def claim_public_chat(session_id):
    result = claim_public_chat_session(
        get_firestore_client(),
        session_id,
        request.headers.get("X-Chat-Session-Token", ""),
        g.current_user["uid"],
    )
    return jsonify(result)


@public_blueprint.get("/stores/<store_code>/customer/orders")
@require_firebase_user
def customer_orders(store_code):
    return jsonify(
        {"orders": list_customer_orders(get_firestore_client(), store_code, g.current_user["uid"])}
    )


@public_blueprint.get("/stores/<store_code>/customer/orders/<order_id>")
@require_firebase_user
def customer_order(store_code, order_id):
    return jsonify(
        {"order": get_customer_order(get_firestore_client(), store_code, g.current_user["uid"], order_id)}
    )


@public_blueprint.get("/stores/<store_code>/customer/chats")
@require_firebase_user
def customer_chats(store_code):
    return jsonify(
        {"chats": list_customer_chats(get_firestore_client(), store_code, g.current_user["uid"])}
    )
