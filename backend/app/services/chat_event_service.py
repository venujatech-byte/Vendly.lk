from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.services.ai_service import translate_chat_message


ORDER_STATUS_LABELS = {
    "needs-confirmation": "needs confirmation",
    "confirmed": "confirmed",
    "packed": "packed and ready for dispatch",
    "shipped": "shipped",
    "delivered": "delivered",
    "returned": "returned",
    "cancelled": "cancelled",
}


def notify_seller_attention(
    database,
    session_reference,
    business_id,
    customer_message,
    reason="ai-unanswered",
):
    """Create one open seller-attention notification per conversation."""
    notification_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("notifications")
        .document()
    )
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        session_snapshot = session_reference.get(transaction=current_transaction)
        if not session_snapshot.exists:
            return False
        session = session_snapshot.to_dict()
        if session.get("needsSellerAttention"):
            return False

        draft = session.get("customerDraft") or {}
        customer_name = draft.get("name") or "A storefront customer"
        current_transaction.set(
            notification_reference,
            {
                "type": "chat-needs-attention",
                "title": "Customer question needs your help",
                "message": f"{customer_name}: {customer_message[:180]}",
                "chatSessionId": session_reference.id,
                "customerUid": session.get("customerUid"),
                "reason": reason,
                "isRead": False,
                "createdAt": firestore.SERVER_TIMESTAMP,
            },
        )
        current_transaction.set(
            session_reference,
            {
                "needsSellerAttention": True,
                "attentionReason": reason,
                "attentionRequestedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        return True

    return create_in_transaction(transaction)


def send_chat_message_to_order_sessions(
    database,
    business_id,
    order_id,
    message,
    metadata,
):
    """Write one automated message into every chat that produced this order.

    Two queries, because a session holds a list of every order it produced AND
    a single `orderId` for its most recent one. The list is the correct source;
    the single field is how sessions written before the list existed are still
    reachable. Deduplicated by document id, since a recent order matches both.
    """
    session_collection = database.collection("publicChatSessions")
    snapshots = {}

    for snapshot in session_collection.where(
        filter=FieldFilter("orderIds", "array_contains", order_id),
    ).stream():
        snapshots[snapshot.id] = snapshot

    for snapshot in session_collection.where(
        filter=FieldFilter("orderId", "==", order_id),
    ).stream():
        snapshots.setdefault(snapshot.id, snapshot)

    for snapshot in snapshots.values():
        session = snapshot.to_dict()

        if session.get("businessId") != business_id:
            continue

        # The customer reads this one, so it follows the language the rest of
        # the conversation settled on rather than always arriving in English.
        session_message = translate_chat_message(
            message,
            session.get("language", "en"),
        )
        snapshot.reference.collection("messages").document().set(
            {
                "role": "seller",
                "message": session_message,
                "metadata": {"automated": True, **metadata},
                "createdAt": firestore.SERVER_TIMESTAMP,
            },
        )
        snapshot.reference.set(
            {
                "lastMessage": session_message,
                "lastMessageRole": "seller",
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )


def send_payment_recorded_chat_message(
    database,
    business_id,
    order_id,
    order,
    paid_amount_minor,
    balance_minor,
):
    """Tell the customer their transfer was received, in their own chat.

    The customer sent a receipt and then heard nothing. Confirming it closes
    the loop they started, and tells them what the courier will still collect.
    """
    order_number = order.get("orderNumber", "your order")

    # Nothing was banked: the order moved to cash on delivery. Announcing a
    # payment of zero would read as a mistake, or worse as a refund.
    if not paid_amount_minor:
        message = (
            f"Order {order_number} has been changed to cash on delivery. "
            f"Please have LKR {balance_minor / 100:,.2f} ready for the courier."
        )
    else:
        message = (
            f"Payment received for order {order_number}: LKR "
            f"{paid_amount_minor / 100:,.2f}."
        )
        message += (
            f" The courier will collect the remaining LKR "
            f"{balance_minor / 100:,.2f} on delivery."
            if balance_minor
            else " Your order is paid in full and nothing is due on delivery."
        )
    send_chat_message_to_order_sessions(
        database,
        business_id,
        order_id,
        message,
        {"action": "payment-recorded", "orderId": order_id},
    )


def send_order_status_chat_message(database, business_id, order_id, order, status, note=""):
    """Append an automated order update to its originating storefront chat."""
    label = ORDER_STATUS_LABELS.get(status, status.replace("-", " "))
    order_number = order.get("orderNumber", "Your order")
    message = f"Order {order_number} status update: {label}."

    if note:
        message = f"{message} Note: {note}"

    send_chat_message_to_order_sessions(
        database,
        business_id,
        order_id,
        message,
        {"action": "order-status-update", "orderId": order_id, "status": status},
    )

