from firebase_admin import firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import required_text


def _session_reference(database, business_id, session_id):
    reference = database.collection("publicChatSessions").document(session_id)
    snapshot = reference.get()
    if not snapshot.exists or snapshot.to_dict().get("businessId") != business_id:
        raise ApiError("chat_session_not_found", "Chat conversation not found.", 404)
    return reference, snapshot.to_dict()


def _message_rows(reference):
    messages = [serialize_snapshot(item) for item in reference.collection("messages").stream()]
    return sorted(messages, key=lambda item: item.get("createdAt") or "")


def _customer_details(database, session):
    # Completed orders keep a stable customer summary on the conversation.
    # Prefer it over the in-progress draft so the seller inbox immediately
    # changes from "Guest customer" to the submitted customer name.
    summary = session.get("customerSummary") or {}
    draft = session.get("customerDraft") or {}
    details = {**draft, **summary}
    if not details.get("name") and session.get("orderId"):
        order_snapshot = (
            database.collection("businesses")
            .document(session.get("businessId", ""))
            .collection("orders")
            .document(session["orderId"])
            .get()
        )
        if order_snapshot.exists:
            order = order_snapshot.to_dict()
            customer = order.get("customerSnapshot") or {}
            details = {
                **details,
                "name": customer.get("name", ""),
                "phoneNumber": customer.get("normalizedPhone", ""),
                "secondaryPhoneNumber": customer.get("normalizedSecondaryPhone", ""),
                "email": customer.get("email", ""),
                "address": order.get("deliveryAddress") or {},
            }
    address = details.get("address") or {}
    account = {}
    if session.get("customerUid"):
        account_snapshot = (
            database.collection("users").document(session["customerUid"]).get()
        )
        account = account_snapshot.to_dict() if account_snapshot.exists else {}
    return {
        "uid": session.get("customerUid"),
        "name": details.get("name") or account.get("displayName") or "Guest customer",
        "phoneNumber": details.get("phoneNumber") or "",
        "secondaryPhoneNumber": details.get("secondaryPhoneNumber") or "",
        "email": details.get("email") or account.get("email") or "",
        "address": address,
    }


def list_chat_sessions(database, business_id):
    snapshots = (
        database.collection("publicChatSessions")
        .where("businessId", "==", business_id)
        .stream()
    )
    sessions = []
    for snapshot in snapshots:
        session = serialize_snapshot(snapshot)
        last_message = {}
        if not session.get("lastMessage"):
            # Compatibility for chats created before parent summaries existed.
            legacy_messages = _message_rows(snapshot.reference)
            if not legacy_messages:
                continue
            last_message = legacy_messages[-1]
        sessions.append(
            {
                "id": snapshot.id,
                "customer": _customer_details(database, session),
                "state": session.get("state", "browsing"),
                "status": session.get("status", "active"),
                "orderId": session.get("orderId"),
                "lastMessage": session.get("lastMessage") or last_message.get("message", ""),
                "lastMessageRole": session.get("lastMessageRole") or last_message.get("role", ""),
                "lastMessageAt": session.get("updatedAt") or last_message.get("createdAt"),
                "unreadCount": int(session.get("unreadBySeller") or 0),
                "aiPaused": bool(session.get("aiPaused", False)),
                "needsSellerAttention": bool(
                    session.get("needsSellerAttention", False)
                ),
            }
        )
    return sorted(sessions, key=lambda item: item.get("lastMessageAt") or "", reverse=True)


def get_chat_messages(database, business_id, session_id):
    reference, session = _session_reference(database, business_id, session_id)
    return {
        "session": {
            "id": session_id,
            "customer": _customer_details(database, session),
            "orderId": session.get("orderId"),
            "state": session.get("state", "browsing"),
            "status": session.get("status", "active"),
            "aiPaused": bool(session.get("aiPaused", False)),
            "needsSellerAttention": bool(
                session.get("needsSellerAttention", False)
            ),
        },
        "messages": _message_rows(reference),
    }


def send_seller_message(database, business_id, session_id, seller_uid, payload):
    try:
        message = required_text(payload.get("message"), "Message", 2000)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    reference, _session = _session_reference(database, business_id, session_id)
    message_reference = reference.collection("messages").document()
    message_reference.set(
        {
            "role": "seller",
            "message": message,
            "metadata": {"sellerUid": seller_uid},
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
    reference.set(
        {
            "lastMessage": message,
            "lastMessageRole": "seller",
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    return serialize_snapshot(message_reference.get())


def mark_chat_read(database, business_id, session_id):
    reference, _session = _session_reference(database, business_id, session_id)
    reference.set(
        {
            "unreadBySeller": 0,
            "needsSellerAttention": False,
            "sellerLastReadAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    return {"sessionId": session_id, "unreadCount": 0}


def set_chat_ai_paused(database, business_id, session_id, is_paused):
    """Enable or pause automated replies for one customer conversation."""
    reference, _session = _session_reference(database, business_id, session_id)
    reference.set(
        {
            "aiPaused": bool(is_paused),
            "aiPausedAt": (
                firestore.SERVER_TIMESTAMP if is_paused else None
            ),
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    return {"sessionId": session_id, "aiPaused": bool(is_paused)}
