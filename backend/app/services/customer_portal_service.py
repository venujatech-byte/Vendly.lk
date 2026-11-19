from app.core.errors import ApiError
from app.services.cache_revision_service import mark_cache_changed
from app.core.serialization import serialize_snapshot
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import FailedPrecondition
from app.services.public_catalog_service import resolve_short_link
from app.services.public_chat_service import authorize_public_chat_session, public_order_confirmation


def resolve_store_business_id(database, store_code):
    try:
        return resolve_short_link(database, store_code, "store")["businessId"]
    except Exception:
        return resolve_short_link(database, store_code)["businessId"]


def list_customer_orders(database, store_code, customer_uid):
    try:
        business_id = resolve_store_business_id(database, store_code)
        snapshots = (
            database.collection("businesses")
            .document(business_id)
            .collection("orders")
            .where("customerUid", "==", customer_uid)
            .stream()
        )
        orders = [public_order_confirmation(serialize_snapshot(item)) for item in snapshots]
        return sorted(orders, key=lambda item: str(item.get("createdAt", "")), reverse=True)
    except Exception:
        return []


def claim_guest_customer_orders(database, store_code, guest_uid, customer_uid):
    """Link only orders owned by the separately verified guest identity in this store."""
    business_id = resolve_store_business_id(database, store_code)
    orders = database.collection("businesses").document(business_id).collection("orders")
    claimed = 0

    # Re-check ownership in each transaction so retries cannot steal an already reassigned order.
    @google_firestore.transactional
    def claim(current_transaction, reference):
        snapshot = reference.get(transaction=current_transaction)
        if not snapshot.exists or snapshot.to_dict().get("customerUid") != guest_uid:
            return False
        current_transaction.update(reference, {"customerUid": customer_uid})
        mark_cache_changed(database, business_id, "orders", current_transaction)
        return True

    if guest_uid != customer_uid:
        for snapshot in orders.where(filter=FieldFilter("customerUid", "==", guest_uid)).stream():
            claimed += claim(database.transaction(), snapshot.reference)
    return {"claimedOrders": claimed}


def get_customer_order(database, store_code, customer_uid, order_id):
    business_id = resolve_store_business_id(database, store_code)
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
        .document(order_id)
        .get()
    )
    if not snapshot.exists or snapshot.to_dict().get("customerUid") != customer_uid:
        raise ApiError("customer_order_not_found", "Order not found.", 404)
    return public_order_confirmation(serialize_snapshot(snapshot))


def list_customer_chats(database, store_code, customer_uid):
    try:
        business_id = resolve_store_business_id(database, store_code)
        snapshots = (
            database.collection("publicChatSessions")
            .where("customerUid", "==", customer_uid)
            .stream()
        )
        chats = []
        for snapshot in snapshots:
            session = serialize_snapshot(snapshot)
            if session.get("businessId") != business_id:
                continue
            last_message = session.get("lastMessage") or ""
            last_role = session.get("lastMessageRole") or "assistant"

            chats.append(
                {
                    "id": snapshot.id,
                    "status": session.get("status", "active"),
                    "state": session.get("state", "browsing"),
                    "orderId": session.get("orderId", ""),
                    "createdAt": session.get("createdAt"),
                    "updatedAt": session.get("updatedAt"),
                    "lastMessage": last_message,
                    "lastMessageRole": last_role,
                    "messages": [
                        {
                            "id": f"{snapshot.id}-msg",
                            "role": last_role,
                            "message": last_message,
                        }
                    ] if last_message else [],
                    "unreadCount": int(session.get("unreadByCustomer") or 0),
                }
            )
        return sorted(chats, key=lambda item: str(item.get("updatedAt", "")), reverse=True)
    except Exception:
        return []


def update_order_guest_email(
    database, store_code, order_id, email, *, customer_uid=None,
    session_id=None, session_token=None,
):
    email = str(email or "").strip().lower()
    if not email or "@" not in email or "." not in email:
        raise ApiError("validation_error", "Please provide a valid email address.", 422)

    # A public order ID is not proof of ownership; require identity or chat credentials.
    if not customer_uid and not (session_id and session_token):
        raise ApiError("authentication_required", "Order ownership is required.", 401)

    business_id = resolve_store_business_id(database, store_code)
    business_ref = database.collection("businesses").document(business_id)
    order_ref = business_ref.collection("orders").document(order_id)
    order_snap = order_ref.get()
    if not order_snap.exists:
        raise ApiError("order_not_found", "Order not found.", 404)

    order_data = order_snap.to_dict()
    # Bound orders belong only to their verified customer; legacy guests prove the original session.
    if order_data.get("customerUid"):
        if order_data["customerUid"] != customer_uid:
            raise ApiError("order_not_found", "Order not found.", 404)
    else:
        if not (session_id and session_token):
            raise ApiError("order_not_found", "Order not found.", 404)
        try:
            _, session = authorize_public_chat_session(
                database, session_id, session_token, allow_closed=True,
            )
        except ApiError:
            raise ApiError("order_not_found", "Order not found.", 404) from None
        owned_orders = list(session.get("orderIds") or [])
        if session.get("orderId"):
            owned_orders.append(session["orderId"])
        if (
            session.get("businessId") != business_id
            or order_id not in owned_orders
            or (session.get("customerUid") and session["customerUid"] != customer_uid)
        ):
            raise ApiError("order_not_found", "Order not found.", 404)

    # Only an authorized customer can change the receipt destination or trigger email.
    customer_snapshot = dict(order_data.get("customerSnapshot") or {})
    customer_snapshot["email"] = email

    # Ownership can change during guest sign-in; reject writes against an outdated authorization read.
    try:
        batch = database.batch()
        batch.update(
            order_ref,
            {"customerSnapshot": customer_snapshot},
            option=database.write_option(last_update_time=order_snap.update_time),
        )
        mark_cache_changed(database, business_id, "orders", batch)
        batch.commit()
    except FailedPrecondition:
        raise ApiError("order_changed", "Order changed. Please reload and try again.", 409) from None

    # Owning an order does not prove ownership of a customer matched by an unverified phone.
    # Send order confirmation and receipt email to the newly provided guest email
    try:
        from app.services.email_service import send_order_confirmation_email
        biz_snap = business_ref.get()
        biz_data = biz_snap.to_dict() if biz_snap.exists else {}
        order_data["customerSnapshot"] = customer_snapshot
        order_data["id"] = order_id
        send_order_confirmation_email(order_data, biz_data, recipient_email=email)
    except Exception:
        pass

    return {"success": True, "email": email}

