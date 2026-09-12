from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.public_catalog_service import resolve_short_link
from app.services.public_chat_service import public_order_confirmation


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


def update_order_guest_email(database, store_code, order_id, email):
    email = str(email or "").strip().lower()
    if not email or "@" not in email or "." not in email:
        raise ApiError("validation_error", "Please provide a valid email address.", 422)

    business_id = resolve_store_business_id(database, store_code)
    business_ref = database.collection("businesses").document(business_id)
    order_ref = business_ref.collection("orders").document(order_id)
    order_snap = order_ref.get()
    if not order_snap.exists:
        raise ApiError("order_not_found", "Order not found.", 404)

    order_data = order_snap.to_dict()
    customer_snapshot = dict(order_data.get("customerSnapshot") or {})
    customer_snapshot["email"] = email

    order_ref.update({"customerSnapshot": customer_snapshot})

    # If customerId exists on order, also update customer doc if email is empty
    customer_id = order_data.get("customerId")
    if customer_id:
        cust_ref = business_ref.collection("customers").document(customer_id)
        cust_snap = cust_ref.get()
        if cust_snap.exists and not cust_snap.to_dict().get("email"):
            cust_ref.update({"email": email})

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

