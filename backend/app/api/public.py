from flask import Blueprint, g, jsonify, request
from firebase_admin import auth as firebase_auth

from app.core.auth import optional_firebase_user, require_firebase_user
from app.core.errors import ApiError
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.core.rate_limit import guest_chat_ip_key, guest_chat_ip_limit_exempt, limiter, public_chat_key
from app.services.public_catalog_service import get_public_product, get_public_store
from app.services.public_chat_service import (
    answer_public_message,
    attach_public_chat_image,
    create_public_chat_order,
    create_public_chat_session,
    claim_public_chat_session,
    get_public_chat_messages,
    resume_public_chat_session,
)
from app.services.customer_portal_service import (
    get_customer_order,
    list_customer_chats,
    list_customer_orders,
    update_order_guest_email,
    claim_guest_customer_orders,
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
        # Only verified registered accounts share a store-wide conversation.
        share_customer_chat=bool(g.current_user) and g.current_user.get("firebase", {}).get("sign_in_provider") != "anonymous",
    )
    return jsonify(session), 201


@public_blueprint.post("/chat/sessions/<session_id>/messages")
@optional_firebase_user
@limiter.limit("60 per minute", key_func=public_chat_key)
@limiter.limit("120 per minute", key_func=guest_chat_ip_key, exempt_when=guest_chat_ip_limit_exempt)
def public_chat_message(session_id):
    session_token = request.headers.get("X-Chat-Session-Token", "")
    if g.current_user:
        claim_public_chat_session(
            get_firestore_client(),
            session_id,
            session_token,
            g.current_user["uid"],
            customer_email=g.current_user.get("email", ""),
        )
    response = answer_public_message(
        get_firestore_client(),
        session_id,
        session_token,
        get_json_object(),
    )
    return jsonify(response)


@public_blueprint.post("/chat/sessions/<session_id>/images")
# Uploading costs storage and an outbound request, so it is limited far more
# tightly than sending text.
@optional_firebase_user
@limiter.limit("10 per minute", key_func=public_chat_key)
@limiter.limit("20 per minute", key_func=guest_chat_ip_key, exempt_when=guest_chat_ip_limit_exempt)
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
@optional_firebase_user
def public_chat_messages(session_id):
    messages = get_public_chat_messages(
        get_firestore_client(),
        session_id,
        request.headers.get("X-Chat-Session-Token", ""),
        limit=min(max(request.args.get("limit", 20, type=int), 1), 50),
        before=request.args.get("before"),
        since=request.args.get("since"),
    )
    return jsonify(messages)


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
            customer_email=g.current_user.get("email", ""),
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
    # Validate the optional claim data before reading any client-supplied fields.
    payload = get_json_object()
    user_email = g.current_user.get("email") or payload.get("email") or ""
    result = claim_public_chat_session(
        get_firestore_client(),
        session_id,
        request.headers.get("X-Chat-Session-Token", ""),
        g.current_user["uid"],
        customer_email=user_email,
    )
    return jsonify(result)


@public_blueprint.post("/chat/sessions/<session_id>/resume")
@require_firebase_user
def resume_public_chat(session_id):
    result = resume_public_chat_session(
        get_firestore_client(),
        session_id,
        g.current_user["uid"],
        customer_email=g.current_user.get("email", ""),
    )
    return jsonify(result)


@public_blueprint.get("/stores/<store_code>/customer/orders")
@require_firebase_user
def customer_orders(store_code):
    return jsonify(
        {"orders": list_customer_orders(get_firestore_client(), store_code, g.current_user["uid"])}
    )


@public_blueprint.post("/stores/<store_code>/customer/claim-guest-orders")
@limiter.limit("10 per minute")
@require_firebase_user
def claim_guest_orders(store_code):
    # Both accounts need verified tokens; caller-supplied UIDs and phone numbers prove nothing.
    if g.current_user.get("firebase", {}).get("sign_in_provider") == "anonymous":
        raise ApiError("account_required", "Sign in to save guest orders.", 403)
    payload = get_json_object()
    try:
        guest = firebase_auth.verify_id_token(payload.get("guestIdToken") or "", check_revoked=True)
    except (
        firebase_auth.InvalidIdTokenError, firebase_auth.ExpiredIdTokenError,
        firebase_auth.RevokedIdTokenError, firebase_auth.UserDisabledError,
        firebase_auth.UserNotFoundError, ValueError,
    ):
        raise ApiError("invalid_guest_token", "Guest ownership could not be verified.", 401) from None
    if guest.get("firebase", {}).get("sign_in_provider") != "anonymous":
        raise ApiError("invalid_guest_token", "A guest session is required.", 403)
    return jsonify(claim_guest_customer_orders(
        get_firestore_client(), store_code, guest["uid"], g.current_user["uid"],
    ))


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


@public_blueprint.post("/stores/<store_code>/orders/<order_id>/email")
@limiter.limit("10 per minute")
@optional_firebase_user
def submit_guest_order_email(store_code, order_id):
    payload = get_json_object()
    email = payload.get("email")
    result = update_order_guest_email(
        get_firestore_client(),
        store_code,
        order_id,
        email,
        # Use verified identity and the original chat secret, never a caller-supplied UID.
        customer_uid=(g.current_user or {}).get("uid"),
        session_id=payload.get("sessionId"),
        session_token=request.headers.get("X-Chat-Session-Token"),
    )
    return jsonify(result), 200
