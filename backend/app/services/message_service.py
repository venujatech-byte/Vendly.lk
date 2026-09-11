from datetime import datetime, timezone

from firebase_admin import firestore
from flask import current_app

from app.core.errors import ApiError
from app.core.firebase import get_rtdb_reference
from app.core.serialization import serialize_snapshot
from app.services.ai_service import translate_chat_message
from app.services.text import required_text


def _session_reference(database, business_id, session_id):
    reference = database.collection("publicChatSessions").document(session_id)
    snapshot = reference.get()
    if not snapshot.exists or snapshot.to_dict().get("businessId") != business_id:
        raise ApiError("chat_session_not_found", "Chat conversation not found.", 404)
    return reference, snapshot.to_dict()


def _message_rows(reference, limit=10, before=None):
    session_id = reference.id
    rtdb_ref = get_rtdb_reference(f"chatMessages/{session_id}")
    rtdb_data = None
    if rtdb_ref is not None:
        try:
            rtdb_data = rtdb_ref.get()
        except Exception as err:
            current_app.logger.warning("Failed to fetch messages from RTDB: %s", err)

    if rtdb_data and isinstance(rtdb_data, dict):
        all_msgs = []
        for msg_id, val in rtdb_data.items():
            if isinstance(val, dict):
                all_msgs.append({"id": msg_id, **val})
        all_msgs.sort(key=lambda m: str(m.get("createdAt") or m.get("id") or ""))
        if before:
            idx = next((i for i, m in enumerate(all_msgs) if m.get("id") == before), None)
            if idx is not None:
                all_msgs = all_msgs[:idx]
        has_more = len(all_msgs) > limit
        rows = all_msgs[-limit:] if has_more else all_msgs
        next_cursor = rows[0].get("id") if has_more and rows else None
        return rows, has_more, next_cursor

    query = reference.collection("messages").order_by(
        "createdAt", direction="DESCENDING"
    )
    if before:
        cursor = reference.collection("messages").document(before).get()
        if cursor.exists:
            query = query.start_after(cursor)
    snapshots = list(query.limit(limit + 1).stream())
    has_more = len(snapshots) > limit
    rows = snapshots[:limit]
    next_cursor = rows[-1].id if has_more and rows else None
    rows.reverse()
    return [serialize_snapshot(item) for item in rows], has_more, next_cursor


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


def list_chat_sessions(database, business_id, limit=10, before=None):
    query = (
        database.collection("publicChatSessions")
        .where("businessId", "==", business_id)
        .order_by("updatedAt", direction="DESCENDING")
    )
    if before:
        cursor = database.collection("publicChatSessions").document(before).get()
        if cursor.exists:
            query = query.start_after(cursor)
    snapshots = list(query.limit(limit + 1).stream())
    has_more = len(snapshots) > limit
    snapshots = snapshots[:limit]
    sessions = []
    for snapshot in snapshots:
        session = serialize_snapshot(snapshot)
        last_message = {}
        if not session.get("lastMessage"):
            # Compatibility for chats created before parent summaries existed.
            legacy_messages, _, _ = _message_rows(snapshot.reference, limit=1)
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
    return {
        "sessions": sessions,
        "nextCursor": snapshots[-1].id if has_more and snapshots else None,
        "hasMore": has_more,
    }


def get_chat_messages(database, business_id, session_id, limit=20, before=None):
    reference, session = _session_reference(database, business_id, session_id)
    messages, has_more, next_cursor = _message_rows(reference, limit=limit, before=before)
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
        "messages": messages,
        "nextCursor": next_cursor,
        "hasMore": has_more,
    }


def delete_chat_session(database, business_id, session_id):
    """Permanently delete a seller-owned chat and its message subcollection."""
    reference, _session = _session_reference(database, business_id, session_id)
    database.recursive_delete(reference)
    rtdb_ref = get_rtdb_reference(f"chatMessages/{session_id}")
    if rtdb_ref is not None:
        try:
            rtdb_ref.delete()
        except Exception as err:
            current_app.logger.warning("Failed to delete RTDB messages for session %s: %s", session_id, err)
    return {"sessionId": session_id, "deleted": True}


def send_seller_message(database, business_id, session_id, seller_uid, payload):
    try:
        message = required_text(payload.get("message"), "Message", 2000)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    reference, session = _session_reference(database, business_id, session_id)

    # The whole conversation may have been in Sinhala or Tamil, and a human
    # steps in precisely when the question was hard. Handing that customer a
    # sudden English reply is where the language guarantee used to break.
    #
    # This runs whatever the seller typed: if they already wrote in the
    # customer's language it is close to a no-op, and if they typed English in
    # a hurry the customer still reads their own language.
    language = session.get("language", "en")
    customer_message = translate_chat_message(message, language)
    was_translated = customer_message != message

    now_iso = datetime.now(timezone.utc).isoformat()
    msg_data = {
        "role": "seller",
        # What the customer reads.
        "message": customer_message,
        # What the seller typed, so their own inbox shows their words back.
        "sellerMessage": message,
        "metadata": {
            "sellerUid": seller_uid,
            "language": language,
            "translated": was_translated,
        },
        "createdAt": now_iso,
    }

    message_id = None
    rtdb_ref = get_rtdb_reference(f"chatMessages/{session_id}")
    if rtdb_ref is not None:
        try:
            pushed = rtdb_ref.push(msg_data)
            message_id = pushed.key
        except Exception as err:
            current_app.logger.warning("Failed to write seller message to RTDB: %s", err)

    if not message_id:
        # Fallback to Firestore subcollection if RTDB is unavailable
        message_reference = reference.collection("messages").document()
        message_reference.set(
            {
                **msg_data,
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
        )
        message_id = getattr(message_reference, "id", None)
        if not message_id:
            try:
                message_id = message_reference.get().id
            except Exception:
                message_id = "message-id"

    reference.set(
        {
            "lastMessage": customer_message,
            "lastMessageRole": "seller",
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    return {
        "id": message_id,
        **msg_data,
    }


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
