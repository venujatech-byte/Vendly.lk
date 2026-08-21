import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from firebase_admin import firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.customer_service import (
    create_customer,
    list_customers,
    normalize_sri_lankan_phone,
)
from app.services.ai_service import generate_product_answer
from app.services.chat_event_service import notify_seller_attention
from app.services.order_service import create_order
from app.services.public_catalog_service import (
    get_public_product,
    get_public_store,
    public_product,
)
from app.services.text import optional_text, required_text
from app.services.review_service import list_public_product_reviews


PRODUCT_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "product",
    "item",
}

ORDER_INTENT_PHRASES = {
    "i want to order",
    "place order",
    "buy this",
    "order this",
    "ready to order",
    "checkout",
}

CONFIRMATION_PHRASES = {
    "yes",
    "yes confirm",
    "confirm",
    "confirm order",
    "submit order",
    "place it",
    "ok",
    "okay",
}


def message_tokens(value):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value).casefold())
        if len(token) > 2 and token not in PRODUCT_STOP_WORDS
    }


def find_product_in_message(message, products):
    """Resolve a catalogue choice by number, name, short code or useful words."""
    clean_message = str(message).strip().casefold()
    numbered_choice = re.fullmatch(
        r"(?:product|item)?\s*#?\s*(\d+)",
        clean_message,
    )

    if numbered_choice:
        product_index = int(numbered_choice.group(1)) - 1
        if 0 <= product_index < len(products):
            return products[product_index]

    for product in products:
        product_name = product.get("name", "").strip().casefold()
        short_code = product.get("shortCode", "").strip().casefold()

        if short_code and short_code in clean_message:
            return product
        if product_name and product_name in clean_message:
            return product

    customer_tokens = message_tokens(clean_message)
    scored_products = []

    for product in products:
        product_words = message_tokens(product.get("name", ""))
        matching_words = customer_tokens & product_words

        if matching_words:
            scored_products.append((len(matching_words), product))

    if not scored_products:
        return None

    scored_products.sort(key=lambda item: item[0], reverse=True)
    highest_score = scored_products[0][0]
    best_matches = [
        product for score, product in scored_products if score == highest_score
    ]
    return best_matches[0] if len(best_matches) == 1 else None


def is_catalog_number_choice(message):
    """Return True when the customer only selects a numbered catalogue item."""
    return bool(
        re.fullmatch(
            r"(?:product|item)?\s*#?\s*\d+",
            str(message).strip().casefold(),
        ),
    )


def normalized_phrase(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def find_category_request(message, products):
    """Resolve an explicit request for a whole product category."""
    clean_message = str(message).strip().casefold()
    compact_message = normalized_phrase(clean_message)
    category_cues = {"show", "list", "all", "category", "categories", "have"}
    message_words = message_tokens(clean_message)
    categories = {
        product.get("categoryName", "").strip()
        for product in products
        if product.get("categoryName", "").strip()
    }

    for category in categories:
        compact_category = normalized_phrase(category)
        category_aliases = {compact_category}
        if compact_category.endswith("s"):
            category_aliases.add(compact_category[:-1])
        if compact_category.endswith("es"):
            category_aliases.add(compact_category[:-2])
        category_words = message_tokens(category)
        exact_category = compact_message in category_aliases
        category_is_named = (
            any(alias and alias in compact_message for alias in category_aliases)
            or category_words.issubset(message_words)
        )
        has_category_cue = bool(category_cues & message_words)

        if exact_category or (category_is_named and has_category_cue):
            return category

    return None


def category_products(products, category_name, excluded_product_id=None):
    return [
        product
        for product in products
        if product.get("categoryName") == category_name
        and product.get("id") != excluded_product_id
    ]


def normalize_chat_cart(value):
    """Keep only variant identifiers and safe positive quantities in chat state."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise ApiError("validation_error", "The order draft must be a list.", 422)
    if len(value) > 50:
        raise ApiError(
            "too_many_order_items",
            "An order can contain no more than 50 item rows.",
            422,
        )

    quantities = {}

    for item in value:
        if not isinstance(item, dict):
            continue
        variant_id = str(item.get("variantId") or "").strip()

        try:
            quantity = int(item.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0

        if variant_id and 0 < quantity <= 999:
            quantities[variant_id] = min(
                999,
                quantities.get(variant_id, 0) + quantity,
            )

    return [
        {"variantId": variant_id, "quantity": quantity}
        for variant_id, quantity in quantities.items()
    ]


def summarize_chat_cart(cart, products):
    variants = {}

    for product in products:
        for variant in product.get("variants", []):
            variants[variant.get("id")] = (product, variant)

    summary = []

    for item in cart:
        match = variants.get(item.get("variantId"))

        if not match:
            continue

        product, variant = match
        quantity = item["quantity"]
        unit_price = product.get("sellingPriceMinor", 0)
        summary.append(
            {
                "variantId": variant.get("id"),
                "productId": product.get("id"),
                "productName": product.get("name", ""),
                "size": variant.get("size", ""),
                "sku": variant.get("sku", ""),
                "quantity": quantity,
                "unitPriceMinor": unit_price,
                "lineTotalMinor": unit_price * quantity,
                "imageUrl": (product.get("media") or [{}])[0].get("url", ""),
            },
        )

    return summary


def parse_customer_name(message):
    clean_name = re.sub(
        r"^(?:my name is|name is|i am|i'm)\s+",
        "",
        str(message).strip(),
        flags=re.IGNORECASE,
    ).strip()

    if len(clean_name) < 2 or not any(character.isalpha() for character in clean_name):
        raise ValueError("Please enter a valid full name.")

    return required_text(clean_name, "Customer name", 160)


def parse_delivery_address(message):
    clean_address = re.sub(
        r"^(?:my address is|deliver to|delivery address is)\s+",
        "",
        str(message).strip(),
        flags=re.IGNORECASE,
    ).strip()
    parts = [part.strip() for part in clean_address.split(",") if part.strip()]

    if len(parts) < 3:
        raise ValueError(
            "Please send the street address, nearest city and district separated "
            "by commas. Example: No. 45 Park Road, Dehiwala, Colombo.",
        )

    return {
        "line1": ", ".join(parts[:-2]),
        "line2": "",
        "city": parts[-2],
        "district": parts[-1],
        "postalCode": "",
    }


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_public_chat_session(database, payload, customer_uid=None):
    store_code = payload.get("storeCode")
    product_code = payload.get("productCode")

    if product_code:
        catalog = get_public_product(database, product_code)
        business = catalog["business"]
        product = catalog["product"]
    elif store_code:
        catalog = get_public_store(database, store_code)
        business = catalog["business"]
        product = None
    else:
        raise ApiError(
            "public_link_required",
            "A store or product code is required.",
            422,
        )

    session_reference = database.collection("publicChatSessions").document()
    session_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session_reference.set(
        {
            "businessId": business["id"],
            "productId": product["id"] if product else None,
            "selectedProductId": product["id"] if product else None,
            "tokenHash": token_hash(session_token),
            "state": "browsing",
            "cart": [],
            "customerDraft": {},
            "customerUid": customer_uid,
            "status": "active",
            "unreadBySeller": 0,
            "aiPaused": False,
            "needsSellerAttention": False,
            "createdAt": now,
            "updatedAt": now,
            "expiresAt": now + timedelta(hours=24),
        },
    )

    greeting = (
        f"Welcome to {business['name']}. What would you like to know about "
        f"{product['name']}?"
        if product
        else f"Welcome to {business['name']}. What product would you like to know about?"
    )

    return {
        "sessionId": session_reference.id,
        "sessionToken": session_token,
        "business": business,
        "product": product,
        "message": greeting,
        "action": "show-product" if product else "show-catalog",
        "products": [product] if product else catalog.get("products", []),
    }


def authorize_public_chat_session(
    database,
    session_id,
    provided_token,
    allow_closed=False,
):
    if not provided_token:
        raise ApiError(
            "chat_session_token_required",
            "A chat session token is required.",
            401,
        )

    snapshot = database.collection("publicChatSessions").document(session_id).get()

    if not snapshot.exists:
        raise ApiError("chat_session_not_found", "Chat session not found.", 404)

    session = snapshot.to_dict()

    if not hmac.compare_digest(
        session.get("tokenHash", ""),
        token_hash(provided_token),
    ):
        raise ApiError("invalid_chat_session", "Chat session is invalid.", 401)
    if not allow_closed and session.get("status") != "active":
        raise ApiError("chat_session_closed", "Chat session is closed.", 409)

    expires_at = session.get("expiresAt")

    if expires_at and expires_at < datetime.now(timezone.utc):
        raise ApiError("chat_session_expired", "Chat session has expired.", 401)

    return snapshot, session


def get_public_chat_messages(database, session_id, provided_token):
    """Return one customer's own chat messages after token verification."""
    snapshot, _session = authorize_public_chat_session(
        database,
        session_id,
        provided_token,
        allow_closed=True,
    )
    messages = [
        serialize_snapshot(item)
        for item in snapshot.reference.collection("messages").stream()
    ]
    return sorted(messages, key=lambda item: item.get("createdAt") or "")


def save_chat_message(session_reference, role, message, metadata=None):
    session_reference.collection("messages").document().set(
        {
            "role": role,
            "message": message,
            "metadata": metadata or {},
            "createdAt": firestore.SERVER_TIMESTAMP,
        },
    )
    # Keep a small conversation summary on the parent document. The seller
    # inbox can list chats without downloading every message in every session.
    session_changes = {
        "lastMessage": message,
        "lastMessageRole": role,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }
    if role == "customer":
        session_changes["unreadBySeller"] = firestore.Increment(1)
    session_reference.set(session_changes, merge=True)


def claim_public_chat_session(database, session_id, provided_token, customer_uid):
    """Attach an active guest chat to the customer who has just signed in."""
    snapshot, session = authorize_public_chat_session(
        database,
        session_id,
        provided_token,
        allow_closed=True,
    )
    existing_uid = session.get("customerUid")
    if existing_uid and existing_uid != customer_uid:
        raise ApiError(
            "chat_session_owner_mismatch",
            "This chat belongs to another customer account.",
            403,
        )
    snapshot.reference.update(
        {
            "customerUid": customer_uid,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    if session.get("orderId"):
        (
            database.collection("businesses")
            .document(session["businessId"])
            .collection("orders")
            .document(session["orderId"])
            .update({"customerUid": customer_uid})
        )
    return {"sessionId": snapshot.id, "claimed": True}


def public_order_confirmation(order):
    """Return only the order fields that the customer is allowed to see."""
    return {
        "id": order.get("id"),
        "orderNumber": order.get("orderNumber", ""),
        "items": [
            {
                "productId": item.get("productId"),
                "variantId": item.get("variantId"),
                "name": item.get("name", ""),
                "size": item.get("size", ""),
                "sku": item.get("sku", ""),
                "quantity": item.get("quantity", 0),
                "unitPriceMinor": item.get("unitPriceMinor", 0),
                "lineTotalMinor": item.get("lineTotalMinor", 0),
                "mediaUrl": item.get("mediaUrl", ""),
            }
            for item in order.get("items", [])
        ],
        "itemCount": order.get("itemCount", 0),
        "subtotalMinor": order.get("subtotalMinor", 0),
        "discountTotalMinor": order.get("discountTotalMinor", 0),
        "deliveryFeeMinor": order.get("deliveryFeeMinor", 0),
        "taxTotalMinor": order.get("taxTotalMinor", 0),
        "totalAmountMinor": order.get("totalAmountMinor", 0),
        "paymentMethod": order.get("paymentMethod", "cod"),
        "paymentStatus": order.get("paymentStatus", "unpaid"),
        "fulfilmentStatus": order.get("fulfilmentStatus", "needs-confirmation"),
        "deliveryAddress": order.get("deliveryAddress", {}),
        "courier": order.get("courierSnapshot", {}),
        "waybillNumber": order.get("waybillNumber", ""),
        "createdAt": order.get("createdAt"),
    }


def answer_public_message(database, session_id, provided_token, payload):
    session_snapshot, session = authorize_public_chat_session(
        database,
        session_id,
        provided_token,
    )

    try:
        message = required_text(payload.get("message"), "Message", 2000)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    save_chat_message(session_snapshot.reference, "customer", message)

    if session.get("aiPaused", False):
        notify_seller_attention(
            database,
            session_snapshot.reference,
            session["businessId"],
            message,
            reason="ai-paused",
        )
        return {
            "message": "",
            "action": "waiting-for-seller",
            "state": session.get("state", "browsing"),
            "aiPaused": True,
        }
    business_snapshot = (
        database.collection("businesses").document(session["businessId"]).get()
    )
    store_code = business_snapshot.to_dict().get("shortCode")
    catalog = get_public_store(database, store_code)
    products = catalog["products"]
    supplied_cart = (
        normalize_chat_cart(payload.get("cart"))
        if "cart" in payload
        else None
    )
    cart = supplied_cart if supplied_cart is not None else session.get("cart", [])
    cart_summary = summarize_chat_cart(cart, products)
    valid_variant_ids = {item["variantId"] for item in cart_summary}
    cart = [item for item in cart if item["variantId"] in valid_variant_ids]
    customer_draft = dict(session.get("customerDraft") or {})
    current_state = session.get("state", "browsing")
    lowered_message = message.strip().casefold()

    def respond(
        response_message,
        action,
        *,
        next_state=None,
        product=None,
        response_products=None,
        selected_product_id="unchanged",
    ):
        state = next_state or current_state
        save_chat_message(
            session_snapshot.reference,
            "assistant",
            response_message,
            {
                "action": action,
                "productId": product.get("id") if product else None,
                "state": state,
            },
        )
        changes = {
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "state": state,
            "cart": cart,
            "customerDraft": customer_draft,
        }

        if selected_product_id != "unchanged":
            changes["selectedProductId"] = selected_product_id

        session_snapshot.reference.update(changes)
        return {
            "message": response_message,
            "action": action,
            "state": state,
            "product": product,
            "products": response_products or [],
            "cart": cart,
            "cartSummary": cart_summary,
            "cartSubtotalMinor": sum(
                item["lineTotalMinor"] for item in cart_summary
            ),
            "customerDraft": customer_draft,
        }

    # Contact collection is deterministic so invalid details never reach orders.
    if current_state == "collecting-name":
        try:
            customer_draft["name"] = parse_customer_name(message)
        except ValueError as error:
            return respond(str(error), "collect-name", next_state="collecting-name")

        return respond(
            f"Thanks, {customer_draft['name']}. What is your Sri Lankan mobile "
            "number? Example: 077 123 4567.",
            "collect-phone",
            next_state="collecting-phone",
        )

    if current_state == "collecting-phone":
        try:
            normalize_sri_lankan_phone(message)
        except ValueError as error:
            return respond(str(error), "collect-phone", next_state="collecting-phone")

        customer_draft["phoneNumber"] = message.strip()
        return respond(
            "Please send the street address, nearest city and district separated "
            "by commas. Example: No. 45 Park Road, Dehiwala, Colombo.",
            "collect-address",
            next_state="collecting-address",
        )

    if current_state == "collecting-address":
        try:
            customer_draft["address"] = parse_delivery_address(message)
        except ValueError as error:
            return respond(
                str(error),
                "collect-address",
                next_state="collecting-address",
            )

        item_text = ", ".join(
            f"{item['quantity']} × {item['productName']}"
            + (f" (size {item['size']})" if item["size"] else "")
            for item in cart_summary
        )
        address = customer_draft["address"]
        response_message = (
            f"Please confirm your order: {item_text}. Customer: "
            f"{customer_draft['name']}, {customer_draft['phoneNumber']}. Delivery: "
            f"{address['line1']}, {address['city']}, {address['district']}. "
            "The delivery fee will be calculated from the district and total weight. "
            "Reply 'confirm order' to submit, or 'change order' to edit the details."
        )
        return respond(
            response_message,
            "confirm-order",
            next_state="awaiting-confirmation",
        )

    if current_state == "awaiting-confirmation":
        confirms_order = (
            lowered_message in CONFIRMATION_PHRASES
            or "confirm order" in lowered_message
        )
        changes_order = any(
            phrase in lowered_message
            for phrase in ("change", "edit", "no", "cancel")
        )

        if confirms_order:
            order = create_public_chat_order(
                database,
                session_id,
                provided_token,
                {
                    "customer": {
                        "name": customer_draft.get("name"),
                        "phoneNumber": customer_draft.get("phoneNumber"),
                        "email": customer_draft.get("email", ""),
                        "address": customer_draft.get("address"),
                    },
                    "items": cart,
                    "deliveryNote": customer_draft.get("deliveryNote", ""),
                },
            )
            response_message = (
                f"Your order {order['orderNumber']} was placed successfully. "
                f"Items subtotal: LKR {order['subtotalMinor'] / 100:,.2f}, "
                f"delivery: LKR {order['deliveryFeeMinor'] / 100:,.2f}, total: "
                f"LKR {order['totalAmountMinor'] / 100:,.2f}."
            )
            save_chat_message(
                session_snapshot.reference,
                "assistant",
                response_message,
                {"action": "order-confirmed", "orderId": order["id"]},
            )
            return {
                "message": response_message,
                "action": "order-confirmed",
                "state": "completed",
                "product": None,
                "products": [],
                "cart": [],
                "cartSummary": [],
                "cartSubtotalMinor": 0,
                "customerDraft": customer_draft,
                "order": order,
            }

        if changes_order:
            customer_draft = {}
            return respond(
                "No problem. Your selected products are still in the draft. "
                "Please enter the customer full name again.",
                "collect-name",
                next_state="collecting-name",
            )

        return respond(
            "Please reply 'confirm order' to submit this order, or 'change order' "
            "to correct the customer or delivery details.",
            "confirm-order",
            next_state="awaiting-confirmation",
        )

    wants_catalog = any(
        phrase in lowered_message
        for phrase in (
            "show products",
            "show catalogue",
            "show catalog",
            "what do you have",
        )
    )
    wants_to_order = any(phrase in lowered_message for phrase in ORDER_INTENT_PHRASES)
    wants_alternatives = any(
        phrase in lowered_message
        for phrase in (
            "not satisfied",
            "not interested",
            "don't like",
            "do not like",
            "something else",
            "similar product",
            "other option",
            "other item",
            "another product",
        )
    )
    category_request = find_category_request(message, products)
    explicitly_selected_product = find_product_in_message(message, products)
    remembered_product_id = session.get("productId") or session.get(
        "selectedProductId",
    )
    remembered_product = next(
        (
            product
            for product in products
            if product["id"] == remembered_product_id
        ),
        None,
    )
    selected_product = explicitly_selected_product or remembered_product

    if wants_to_order:
        if not cart_summary:
            response_message = (
                "First select the product and size, then use Add to order. "
                "Your selected items will appear in the Live Order Draft on the right."
            )
            return respond(
                response_message,
                "start-order",
                next_state="browsing",
                product=selected_product,
                response_products=[selected_product] if selected_product else products,
                selected_product_id=(
                    selected_product["id"] if selected_product else "unchanged"
                ),
            )

        return respond(
            f"Great. Your draft contains {sum(item['quantity'] for item in cart_summary)} "
            "item(s). What is the customer's full name?",
            "collect-name",
            next_state="collecting-name",
        )

    if wants_alternatives and selected_product:
        alternatives = category_products(
            products,
            selected_product.get("categoryName"),
            selected_product["id"],
        )
        if not alternatives:
            alternatives = [
                product for product in products if product["id"] != selected_product["id"]
            ]

        return respond(
            (
                f"Here are other {selected_product.get('categoryName') or 'product'} "
                "options you may prefer. Select one to see its photos and details."
                if alternatives
                else "There are no other available products in this category right now."
            ),
            "suggest-alternatives",
            next_state="browsing",
            response_products=alternatives,
        )

    if category_request:
        matches = category_products(products, category_request)
        return respond(
            f"Here are all available products in {category_request}.",
            "show-category",
            next_state="browsing",
            response_products=matches,
            selected_product_id=None if not session.get("productId") else "unchanged",
        )

    if wants_catalog:
        return respond(
            "Here is the catalogue. Choose a product to see its image, description, "
            "price, available sizes and stock.",
            "show-catalog",
            next_state="browsing",
            response_products=products,
            selected_product_id=None if not session.get("productId") else "unchanged",
        )

    if selected_product:
        if "review" in lowered_message:
            reviews = list_public_product_reviews(
                database,
                session["businessId"],
                selected_product["id"],
            )
            selected_product = {
                **selected_product,
                "approvedReviewSnippets": [
                    {
                        "rating": review["rating"],
                        "reviewText": review["reviewText"],
                    }
                    for review in reviews[:5]
                ],
            }

        deterministic_description = (
            selected_product.get("aiDescription")
            or selected_product.get("description")
            or "The seller has not added a detailed description yet."
        )

        if "review" in lowered_message and selected_product.get("approvedReviewSnippets"):
            review_text = "; ".join(
                f"{review['rating']}/5 - {review['reviewText']}"
                for review in selected_product["approvedReviewSnippets"]
            )
            response_message = f"Verified customer reviews: {review_text}"
        elif "review" in lowered_message:
            response_message = "This product does not have approved customer reviews yet."
        elif is_catalog_number_choice(message) or explicitly_selected_product:
            available_sizes = [
                variant.get("size")
                for variant in selected_product.get("variants", [])
                if variant.get("size")
            ]
            size_text = (
                f" Available sizes: {', '.join(available_sizes)}."
                if available_sizes
                else ""
            )
            response_message = (
                f"{selected_product['name']}: {deterministic_description} "
                f"Price: LKR {selected_product['sellingPriceMinor'] / 100:,.2f}."
                f"{size_text} Ask me about a specific feature, add it to your order, "
                "or ask for other options in this category."
            )
        else:
            generated_answer = generate_product_answer(message, selected_product)
            answer_is_uncertain = not generated_answer or any(
                phrase in generated_answer.casefold()
                for phrase in (
                    "i don't know",
                    "i do not know",
                    "not enough information",
                    "cannot answer",
                    "can't answer",
                    "seller has not provided",
                )
            )
            response_message = generated_answer or (
                f"Based on the seller's information: {deterministic_description} "
                "If that does not answer the specific feature you asked about, the "
                "seller has not provided that detail yet."
            )
            if answer_is_uncertain:
                notify_seller_attention(
                    database,
                    session_snapshot.reference,
                    session["businessId"],
                    message,
                )

        return respond(
            response_message,
            "show-product",
            next_state="browsing",
            product=selected_product,
            selected_product_id=selected_product["id"],
        )

    is_simple_greeting = normalized_phrase(message) in {
        "hi", "hello", "hey", "goodmorning", "goodafternoon", "goodevening"
    }
    if not is_simple_greeting:
        notify_seller_attention(
            database,
            session_snapshot.reference,
            session["businessId"],
            message,
        )

    return respond(
        "Please choose a product or category. I can show product photos and "
        "descriptions, answer feature questions, suggest alternatives and take "
        "a complete order.",
        "show-catalog",
        next_state="browsing",
        response_products=products,
    )


def create_public_chat_order(database, session_id, provided_token, payload):
    session_snapshot, session = authorize_public_chat_session(
        database,
        session_id,
        provided_token,
    )
    customer_payload = payload.get("customer")

    if not isinstance(customer_payload, dict):
        raise ApiError("validation_error", "Customer details are required.", 422)

    existing_customers = list_customers(
        database,
        session["businessId"],
        phone=customer_payload.get("phoneNumber"),
    )
    customer = (
        existing_customers[0]
        if existing_customers
        else create_customer(database, session["businessId"], customer_payload)
    )
    try:
        delivery_note = optional_text(payload.get("deliveryNote"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    private_note = "Created through the public Vendly chatbot."
    if delivery_note:
        private_note = f"{private_note} Customer delivery note: {delivery_note}"

    order_payload = {
        "customerId": customer["id"],
        "items": payload.get("items"),
        "deliveryAddress": customer_payload.get("address"),
        "courierId": payload.get("courierId", ""),
        "paymentMethod": "cod",
        "source": "chatbot",
        "discountAmount": 0,
        "privateNote": private_note,
        "customerUid": session.get("customerUid", ""),
    }

    if session.get("productId"):
        for item in order_payload.get("items") or []:
            variant_snapshot = (
                database.collection("businesses")
                .document(session["businessId"])
                .collection("productVariants")
                .document(item.get("variantId", ""))
                .get()
            )

            if (
                not variant_snapshot.exists
                or variant_snapshot.to_dict().get("productId") != session["productId"]
            ):
                raise ApiError(
                    "product_link_restriction",
                    "This product link can only order the linked product.",
                    403,
                )

    order = create_order(
        database,
        session["businessId"],
        f"public-chat:{session_id}",
        order_payload,
    )
    session_snapshot.reference.update(
        {
            "status": "completed",
            "orderId": order["id"],
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    return public_order_confirmation(order)
