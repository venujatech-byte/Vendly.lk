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


def send_order_status_chat_message(database, business_id, order_id, order, status, note=""):
    """Append an automated order update to its originating storefront chat."""
    # Two queries, because a session holds a list of every order it produced
    # AND a single `orderId` for its most recent one. The list is the correct
    # source; the single field is how sessions written before the list exists
    # are still reachable. Deduplicated by document id, since a recent order
    # matches both.
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

    sessions = list(snapshots.values())
    label = ORDER_STATUS_LABELS.get(status, status.replace("-", " "))
    order_number = order.get("orderNumber", "Your order")
    message = f"Order {order_number} status update: {label}."
    if note:
        message = f"{message} Note: {note}"

    for snapshot in sessions:
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
                "metadata": {
                    "automated": True,
                    "action": "order-status-update",
                    "orderId": order_id,
                    "status": status,
                },
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
        )
        snapshot.reference.set(
            {
                "lastMessage": session_message,
                "lastMessageRole": "seller",
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

