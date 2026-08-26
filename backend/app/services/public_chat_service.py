import hashlib
import hmac
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

from firebase_admin import firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.customer_service import (
    create_customer,
    list_customers,
    normalize_sri_lankan_phone,
)
from app.services.ai_service import (
    ANSWERED_MARKER,
    MISSING_FACT_MARKER,
    detect_chat_language,
    generate_catalogue_answer,
    generate_product_answer,
    generate_storefront_intent,
    translate_chat_message,
)
from app.services.chat_event_service import notify_seller_attention
from app.services.courier_service import (
    district_display_name,
    district_first_kg_price,
    find_district_in_text,
    is_known_district,
    normalize_district,
    recommend_couriers,
)
from app.services.order_service import create_order
from app.services.public_catalog_service import (
    get_public_product,
    get_public_store,
    public_product,
)
from app.services.text import optional_text, required_text
from app.services.review_service import (
    list_public_product_reviews,
    list_public_seller_reviews,
)


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

# ponytail: these keyword sets are the deterministic intent ladder. They carry
# the Sinhala and Tamil wording customers actually use, plus the romanised
# Sinhala most people type on a phone. Replace the whole ladder with an AI
# intent classifier (see generate_business_assistant_intent) when the phrase
# lists start needing a new entry every week.
ORDER_INTENT_PHRASES = {
    "i want to order",
    "place order",
    "buy this",
    "order this",
    "ready to order",
    "checkout",
    "order karanna",
    "ganna one",
    "ganna ona",
    "mata one",
    "ඕඩර් කරන්න",
    "ගන්න ඕන",
    "ගන්න ඕනේ",
    "මට ඕන",
    "ஆர்டர் செய்ய",
    "வாங்க வேண்டும்",
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
    "ow",
    "ehenam",
    "හරි",
    "ඔව්",
    "ඔව්, තහවුරු කරන්න",
    "තහවුරු කරන්න",
    "ஆம்",
    "சரி",
    "உறுதிப்படுத்து",
}

NEW_ORDER_PHRASES = {
    "another order",
    "new order",
    "order again",
    "place another order",
    "make another order",
    "buy something else",
    "aluth order",
    "තව ඕඩර්",
    "අලුත් ඕඩර්",
    "නව ඇණවුම",
    "மற்றொரு ஆர்டர்",
    "புதிய ஆர்டர்",
}

ORDER_ENQUIRY_WORDS = {
    "status",
    "ship",
    "shipped",
    "shipping",
    "deliver",
    "delivered",
    "delivery",
    "track",
    "tracking",
    "waybill",
    "packed",
    "dispatch",
    "arrive",
    "arrival",
    "තත්ත්වය",
    "බෙදාහැරීම",
    "ලැබුණාද",
    "එවලාද",
    "ට්‍රැක්",
    "நிலை",
    "டெலிவரி",
    "கண்காணி",
    "வந்ததா",
}

CATALOG_PHRASES = {
    "show products",
    "show catalogue",
    "show catalog",
    "what do you have",
    "mokakda thiyenne",
    "monawada thiyenne",
    "නිෂ්පාදන",
    "මොනවද තියෙන්නේ",
    "බඩු පෙන්නන්න",
    "පෙන්නන්න",
    "பொருட்கள்",
    "என்ன இருக்கு",
    "காட்டுங்கள்",
}

ALTERNATIVE_PHRASES = {
    "not satisfied",
    "not interested",
    "don't like",
    "do not like",
    "something else",
    "similar product",
    "similar items",
    "other option",
    "other item",
    "another product",
    "wenna deyak",
    # Romanised Sinhala for "are there others like this one".
    "me vage",
    "meka wage",
    "mewa vage",
    "vage thawa",
    "wage thawa",
    "thawa ewa",
    "thava ewa",
    "wenath",
    "වගේ තව",
    "වෙන එකක්",
    "වෙනත්",
    "සමාන",
    "කැමති නෑ",
    "வேறு",
    "மாற்று",
    "பிடிக்கவில்லை",
}

GREETING_PHRASES = {
    "hi",
    "hello",
    "hey",
    "goodmorning",
    "goodafternoon",
    "goodevening",
    "ayubowan",
    "kohomada",
    "ආයුබෝවන්",
    "හලෝ",
    "කොහොමද",
    "වணක්කම්",
    "வணக்கம்",
    "ஹலோ",
    "எப்படிஇருக்கிறீர்கள்",
}


def is_explicit_new_order_request(message):
    """Only an unmistakable request may reset a completed order chat."""
    clean_message = str(message).strip().casefold()
    return any(phrase in clean_message for phrase in NEW_ORDER_PHRASES)


def is_order_enquiry(message):
    """Recognise delivery, tracking and existing-order questions."""
    clean_message = str(message).casefold()
    words = set(word_characters(clean_message).split())
    return bool(words & ORDER_ENQUIRY_WORDS) or "order info" in clean_message \
        or "order details" in clean_message


def latest_order_for_session(database, session):
    """Find the linked order, or the latest order owned by this customer."""
    orders_reference = (
        database.collection("businesses")
        .document(session["businessId"])
        .collection("orders")
    )
    order_id = session.get("orderId")
    if order_id:
        snapshot = orders_reference.document(order_id).get()
        if snapshot.exists:
            return {"id": snapshot.id, **snapshot.to_dict()}

    customer_uid = session.get("customerUid")
    if not customer_uid:
        return None

    snapshots = orders_reference.where("customerUid", "==", customer_uid).stream()
    orders = [{"id": item.id, **item.to_dict()} for item in snapshots]
    if not orders:
        return None
    return max(orders, key=lambda item: str(item.get("createdAt", "")))


def order_information_message(order):
    status = str(order.get("fulfilmentStatus") or "needs-confirmation").replace(
        "-", " "
    )
    parts = [
        f"Your order {order.get('orderNumber', '')} is currently {status}.",
        f"Order total: LKR {order.get('totalAmountMinor', 0) / 100:,.2f}.",
    ]
    courier_name = (order.get("courierSnapshot") or {}).get("name")
    if courier_name:
        parts.append(f"Courier: {courier_name}.")
    if order.get("waybillNumber"):
        parts.append(f"Waybill number: {order['waybillNumber']}.")
    parts.append("Ask me about this order, or say 'another order' to shop again.")
    return " ".join(parts)


def word_characters(value):
    """Keep letters, combining marks and digits; turn everything else to space.

    Neither `[a-z0-9]` nor `\\w` can tokenise Sinhala or Tamil. The ASCII class
    erases those scripts completely, and `\\w` silently drops the combining
    vowel signs their words are built from, so "නැහැ" would arrive as two
    unrelated fragments. Matching on the Unicode category keeps every script
    whole.
    """
    return "".join(
        character if unicodedata.category(character)[0] in {"L", "M", "N"} else " "
        for character in str(value).casefold()
    )


def message_tokens(value):
    return {
        token
        for token in word_characters(value).split()
        if len(token) > 2 and token not in PRODUCT_STOP_WORDS
    }


SINHALA_SCRIPT = re.compile(r"[඀-෿]")
TAMIL_SCRIPT = re.compile(r"[஀-௿]")

# An explicit request always wins over detection, in any of the three languages.
LANGUAGE_REQUESTS = {
    "en": ("in english", "english please", "reply in english", "ඉංග්‍රීසි", "ஆங்கில"),
    "si": ("in sinhala", "sinhala please", "සිංහලෙන්", "සිංහල", "சிங்கள"),
    "ta": ("in tamil", "tamil please", "தமிழில்", "தமிழ்", "දෙමළ"),
}


def requested_language(message):
    text = str(message).casefold()

    for language, phrases in LANGUAGE_REQUESTS.items():
        if any(phrase in text for phrase in phrases):
            return language

    return None


def conversation_language(message, current_language, detected_language=None):
    """Decide which language to answer one customer message in.

    Sinhala and Tamil script are certain, so they are matched directly and cost
    nothing. The AI is asked only about Latin text, which is the genuinely
    ambiguous case: romanised Sinhala and Tamil are indistinguishable from
    English by character range alone. Once a language is established it is kept,
    so a customer typing a phone number or an address does not get switched back
    to English mid-order.
    """
    language = current_language if current_language in {"en", "si", "ta"} else "en"
    explicit_request = requested_language(message)

    if explicit_request:
        return explicit_request

    if SINHALA_SCRIPT.search(str(message)):
        return "si"

    if TAMIL_SCRIPT.search(str(message)):
        return "ta"

    if language != "en":
        return language

    # The intent classifier already read this message and reported its
    # language, so reuse that instead of paying for a second call.
    if detected_language in {"en", "si", "ta"}:
        return detected_language

    return detect_chat_language(message) or language


# Intent classification is worth an AI call only where the customer is steering
# the conversation. In the collecting-* states the message IS the data - a name,
# a phone number, an address - so it is read literally and never classified.
INTENT_CLASSIFIED_STATES = {
    "browsing",
    "quoting-district",
    "awaiting-item-quantity",
    "awaiting-confirmation",
    "completed",
}


def storefront_intent(message, products, state):
    """Classify a code-mixed message, or return an empty result on failure."""
    if state not in INTENT_CLASSIFIED_STATES:
        return {}

    category_names = sorted(
        {
            product.get("categoryName", "").strip()
            for product in products
            if product.get("categoryName", "").strip()
        },
    )
    result = generate_storefront_intent(
        message,
        [product.get("name", "") for product in products][:60],
        category_names,
        state,
    )
    return result or {}


# Order-creation failures that mean "the shelf changed", not "the request was
# malformed". Only these are recoverable by re-checking stock and re-asking.
STOCK_CONFLICT_CODES = {
    "insufficient_stock",
    "inactive_variant",
    "variant_not_found",
}


def reconcile_cart_stock(cart, products):
    """Clamp a draft to what is still on the shelf, and report what changed.

    Stock moves while a customer is deciding. A variant that sells out drops
    out of the public catalogue entirely, so an unreported line simply vanished
    from the cart; a partly-depleted line survived and failed inside the order
    transaction with a raw "Only N unit(s) available for SKU ..." at the moment
    of confirmation. Both are caught here instead.

    Returns the corrected cart, the variant ids that are gone, and the lines
    that had to be reduced.
    """
    variants = {
        variant["id"]: (product, variant)
        for product in products
        for variant in product.get("variants", [])
    }
    updated = []
    sold_out_variant_ids = []
    reduced_lines = []

    for line in cart:
        match = variants.get(line["variantId"])

        if not match:
            sold_out_variant_ids.append(line["variantId"])
            continue

        product, variant = match
        available = variant.get("availableStock", 0)

        if available <= 0:
            sold_out_variant_ids.append(line["variantId"])
            continue

        if line["quantity"] > available:
            reduced_lines.append((product, variant, available))
            updated.append({**line, "quantity": available})
        else:
            updated.append(line)

    return updated, sold_out_variant_ids, reduced_lines


def describe_missing_variant(database, business_id, variant_id, products):
    """Name a cart line whose variant has dropped out of the public catalogue.

    Sold-out variants are filtered out of the public payload, so the only way
    to tell the customer *which* item went is to read the variant directly.
    This runs only when a line has actually vanished, which is rare.
    """
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("productVariants")
        .document(variant_id)
        .get()
    )

    if not snapshot.exists:
        return "An item in your order"

    variant = snapshot.to_dict()
    product = next(
        (item for item in products if item["id"] == variant.get("productId")),
        None,
    )
    name = product["name"] if product else "An item in your order"
    size = variant.get("size", "")
    return f"{name} (size {size})" if size else name


def quantity_from_message(message, ai_quantity=0):
    """Read a quantity sent as its own reply: "2", "two", "dekak".

    The number must stand alone. A bare `\\d+` matched the "2" inside "GM2 pro"
    and read a product name as a quantity. Suffixed Sinhala forms like "3k" and
    "2ak" deliberately fall through to the classifier, which reads them as
    numbers rather than guessing from the digits.
    """
    digits = re.search(r"(?<![0-9A-Za-z])\d+(?![0-9A-Za-z])", str(message))

    if digits:
        return max(0, min(int(digits.group()), 99))

    return max(0, min(int(ai_quantity or 0), 99))


def find_variant(products, variant_id):
    """Locate a cart line's product and variant in the loaded catalogue."""
    for product in products:
        for variant in product.get("variants", []):
            if variant.get("id") == variant_id:
                return product, variant

    return None, None


def choose_variant(product, size_query):
    """Pick the variant the customer meant, or None when it is ambiguous."""
    variants = product.get("variants", [])

    if not variants:
        return None

    if len(variants) == 1:
        return variants[0]

    wanted = normalized_phrase(size_query)

    if not wanted:
        return None

    for variant in variants:
        if normalized_phrase(variant.get("size", "")) == wanted:
            return variant

    return None


def set_variant_quantity(cart, variant_id, quantity, available_stock, mode="total"):
    """Put a line in the chat cart at the quantity the customer actually meant.

    `mode="total"` sets the line to `quantity`; `mode="add"` adds to whatever is
    already there. Total is the default because a stated quantity - "mata 3k
    ona", "I want 3" - is a total, and treating it as an addition silently puts
    more in the order than the customer asked for.

    A quantity of 0 in total mode removes the line, so "remove it" works.

    Returns the new cart and the quantity the line ended up at, which may be
    lower than asked. Stock is checked again inside the order transaction; this
    only stops the customer building a draft that cannot be fulfilled.
    """
    updated = [dict(line) for line in cart]
    existing = next(
        (line for line in updated if line["variantId"] == variant_id),
        None,
    )
    current_quantity = existing["quantity"] if existing else 0

    if mode == "add":
        requested = current_quantity + max(1, quantity)
    else:
        requested = quantity if quantity > 0 else (0 if existing else 1)

    if requested <= 0:
        return [line for line in updated if line["variantId"] != variant_id], 0

    capped = max(1, min(requested, available_stock or requested, 99))

    if existing:
        existing["quantity"] = capped
    else:
        updated.append({"variantId": variant_id, "quantity": capped})

    return updated, capped


def find_matching_products(message, products):
    """Every catalogue item that matches the customer's wording equally well.

    More than one result means the message is genuinely ambiguous, and the
    caller should ask which product was meant instead of giving up.
    """
    clean_message = str(message).strip().casefold()
    numbered_choice = re.fullmatch(
        r"(?:product|item)?\s*#?\s*(\d+)",
        clean_message,
    )

    if numbered_choice:
        product_index = int(numbered_choice.group(1)) - 1
        if 0 <= product_index < len(products):
            return [products[product_index]]

    for product in products:
        product_name = product.get("name", "").strip().casefold()
        short_code = product.get("shortCode", "").strip().casefold()

        if short_code and short_code in clean_message:
            return [product]
        if product_name and product_name in clean_message:
            return [product]

    customer_tokens = message_tokens(clean_message)
    scored_products = []

    for product in products:
        product_words = message_tokens(product.get("name", ""))
        matching_words = customer_tokens & product_words

        if matching_words:
            scored_products.append((len(matching_words), product))

    if not scored_products:
        return []

    scored_products.sort(key=lambda item: item[0], reverse=True)
    highest_score = scored_products[0][0]
    return [product for score, product in scored_products if score == highest_score]


def find_product_in_message(message, products):
    """Resolve a catalogue choice by number, name, short code or useful words."""
    matches = find_matching_products(message, products)
    return matches[0] if len(matches) == 1 else None


def is_catalog_number_choice(message):
    """Return True when the customer only selects a numbered catalogue item."""
    return bool(
        re.fullmatch(
            r"(?:product|item)?\s*#?\s*\d+",
            str(message).strip().casefold(),
        ),
    )


def normalized_phrase(value):
    return "".join(word_characters(value).split())


def is_finished_selecting_items(message):
    """Recognise a short reply that means the customer's cart is complete."""
    clean_message = str(message).strip().casefold()
    compact_message = normalized_phrase(clean_message)

    return compact_message in {
        "no",
        "nothanks",
        "nothingelse",
        "thatsall",
        "thatwillbeall",
        "done",
        "enough",
        "continue",
        "proceed",
        "checkout",
    } or compact_message in {
        "නැහැ",
        "නෑ",
        "එපා",
        "වෙනමොනවත්එපා",
        "ඇති",
        "ඉවරයි",
        "இல்லை",
        "வேண்டாம்",
        "போதும்",
        "முடிந்தது",
    }


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


def related_products(products, selected_product, limit=4):
    """Recommend catalogue items without allowing the AI to invent products.

    Same category first, then the rest of the catalogue. Within each group the
    closest price comes first, because a shopper looking at a LKR 3,000 bag is
    far more likely to want the LKR 3,500 one than the LKR 25,000 one.
    """
    if not selected_product:
        return []

    selected_id = selected_product.get("id")
    target_price = selected_product.get("sellingPriceMinor", 0)

    def price_distance(product):
        return abs(product.get("sellingPriceMinor", 0) - target_price)

    same_category = sorted(
        category_products(
            products,
            selected_product.get("categoryName"),
            selected_id,
        ),
        key=price_distance,
    )
    same_category_ids = {product.get("id") for product in same_category}
    other_products = sorted(
        (
            product
            for product in products
            if product.get("id") != selected_id
            and product.get("id") not in same_category_ids
        ),
        key=price_distance,
    )
    return (same_category + other_products)[:limit]


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
        # create_order prices and weighs each line from the variant. Using the
        # product's price here showed the customer one subtotal and charged
        # another whenever a size was priced differently.
        unit_price = variant.get("sellingPriceMinor") or product.get(
            "sellingPriceMinor",
            0,
        )
        unit_weight_grams = variant.get("weightGrams") or product.get(
            "weightGrams",
            0,
        )
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
                "unitWeightGrams": unit_weight_grams,
                "lineWeightGrams": unit_weight_grams * quantity,
                "imageUrl": (product.get("media") or [{}])[0].get("url", ""),
            },
        )

    return summary


DELIVERY_FEE_PHRASES = (
    "delivery fee",
    "delivery charge",
    "delivery cost",
    "delivery price",
    "delivery kiyada",
    "shipping fee",
    "shipping charge",
    "shipping cost",
    "courier fee",
    "courier charge",
    "courier cost",
    "postage",
    "gasthuwa",
    "gaasthuwa",
    "ගාස්තු",
    "බෙදාහැරීමේ",
    "කුරියර්",
    "கட்டணம்",
    "டெலிவரி",
)


def is_delivery_fee_question(message):
    """Recognise a delivery-price question in English, Sinhala or Tamil."""
    text = str(message).casefold()

    if any(phrase in text for phrase in DELIVERY_FEE_PHRASES):
        return True

    asks_price = any(
        word in text for word in ("how much", "kiyada", "how many", "එවනවද", "කීයද")
    )
    return asks_price and any(
        word in text for word in ("delivery", "shipping", "courier", "deliver")
    )


def cart_weight_grams(cart_summary):
    return sum(item.get("lineWeightGrams", 0) for item in cart_summary)


def session_catalog(database, session):
    """Load the seller's public catalogue for one chat session."""
    business_snapshot = (
        database.collection("businesses").document(session["businessId"]).get()
    )
    return get_public_store(database, business_snapshot.to_dict().get("shortCode"))


def cheapest_courier_quote(database, business_id, district, weight_grams):
    """The lowest delivery fee for one district across the seller's couriers.

    Customers are quoted, and orders are assigned, the cheapest courier for
    their district. Delivery quality only breaks a price tie, unlike the seller
    dashboard recommendation which weighs success rate first.
    """
    if not str(district or "").strip():
        return None

    quotes = recommend_couriers(
        database,
        business_id,
        max(int(weight_grams or 0), 1000),
        district,
    )

    if not quotes:
        return None

    return min(
        quotes,
        key=lambda quote: (quote["deliveryFeeMinor"], -quote["score"]),
    )


def delivery_quote(database, business_id, district, weight_grams):
    """Price one delivery with the courier the order would actually use."""
    quoted_weight = max(int(weight_grams or 0), 1000)
    best = cheapest_courier_quote(database, business_id, district, weight_grams)

    if not best:
        return None

    courier = best["courier"]

    return {
        "courierId": courier.get("id", ""),
        "district": district_display_name(district),
        "courierName": courier.get("name", ""),
        "firstKgPriceMinor": district_first_kg_price(
            courier,
            normalize_district(district),
        ),
        "extraKgPriceMinor": courier.get("extraKgPriceMinor", 0),
        "weightGrams": quoted_weight,
        "isEstimate": not weight_grams,
        "deliveryFeeMinor": best["deliveryFeeMinor"],
    }


def delivery_quote_message(quote):
    """Explain the district price and the extra-kilogram rate that built it."""
    courier_text = f" with {quote['courierName']}" if quote.get("courierName") else ""
    parts = [
        f"Delivery to {quote['district']}{courier_text} is LKR "
        f"{quote['firstKgPriceMinor'] / 100:,.2f} for the first 1 kg, plus LKR "
        f"{quote['extraKgPriceMinor'] / 100:,.2f} for each extra 1 kg.",
    ]

    if quote["isEstimate"]:
        parts.append(
            "That is the price for a 1 kg parcel. Add items to your order and I "
            "will confirm the exact delivery fee for their total weight.",
        )
    else:
        parts.append(
            f"Your selected items weigh {quote['weightGrams'] / 1000:,.2f} kg, so "
            f"delivery is LKR {quote['deliveryFeeMinor'] / 100:,.2f}.",
        )

    return " ".join(parts)


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


def is_optional_phone_skip(message):
    """Return True when the customer intentionally has no second number.

    The prompt asks them to type 'skip', and the translation keeps that command
    in English, but a Sinhala or Tamil speaker will often answer in their own
    words instead. Both are accepted.
    """
    return str(message).strip().lower() in {
        "skip", "no", "none", "n/a", "na", "no second number",
        "i don't have one", "i do not have one", "continue",
        "නෑ", "නැහැ", "එපා", "නැත", "අවශ්‍ය නැහැ", "දෙවෙනි නම්බර් නෑ",
        "இல்லை", "வேண்டாம்", "தவிர்", "கிடையாது",
    }


def parse_required_location(message, field_name):
    """Validate a single free-text location field collected by the chatbot."""
    value = str(message).strip()
    if len(value) < 2 or not any(character.isalpha() for character in value):
        raise ValueError(f"Please enter a valid {field_name}.")
    return required_text(value, field_name, 120)


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
            # Set from the customer's first message; the greeting cannot know it.
            "language": "en",
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
        "action": "show-product" if product else "prompt-product",
        # A normal storefront conversation starts with a short question. The
        # catalogue is returned only after the customer asks for products or a
        # category. A product-specific link still opens that product directly.
        "products": [product] if product else [],
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
    # A completed order does not end the customer conversation. Customers must
    # still be able to ask about delivery, tracking and their order status.
    # Only explicitly closed sessions are blocked from receiving messages.
    if not allow_closed and session.get("status") not in {"active", "completed"}:
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
    catalog = session_catalog(database, session)
    products = catalog["products"]
    supplied_cart = (
        normalize_chat_cart(payload.get("cart"))
        if "cart" in payload
        else None
    )
    cart = supplied_cart if supplied_cart is not None else session.get("cart", [])
    cart, sold_out_variant_ids, reduced_lines = reconcile_cart_stock(cart, products)
    cart_summary = summarize_chat_cart(cart, products)
    customer_draft = dict(session.get("customerDraft") or {})
    current_state = session.get("state", "browsing")
    lowered_message = message.strip().casefold()
    # One AI call reads the whole sentence for both intent and language, so a
    # code-mixed message like "මට black bag එකක් order කරන්න ඕන" is understood
    # even though no phrase list contains that combination. The keyword ladder
    # below stays as the fallback for when the provider is unavailable.
    ai_intent = storefront_intent(message, products, current_state)
    language = conversation_language(
        message,
        session.get("language", "en"),
        ai_intent.get("language"),
    )

    def intent_is(*names):
        return ai_intent.get("intent") in names

    def respond(
        response_message,
        action,
        *,
        next_state=None,
        product=None,
        response_products=None,
        response_reviews=None,
        review_summary=None,
        seller_rating=None,
        selected_product_id="unchanged",
        pending_variant_id="unchanged",
        is_translated=False,
    ):
        state = next_state or current_state
        # Every deterministic reply is written in English in this file, so this
        # is the one place that turns it into the customer's language. Answers
        # the model already wrote in that language skip it.
        localized_message = (
            response_message
            if is_translated
            else translate_chat_message(response_message, language)
        )
        save_chat_message(
            session_snapshot.reference,
            "assistant",
            localized_message,
            {
                "action": action,
                "productId": product.get("id") if product else None,
                "state": state,
                "language": language,
            },
        )
        changes = {
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "state": state,
            "cart": cart,
            "customerDraft": customer_draft,
            "language": language,
        }

        if selected_product_id != "unchanged":
            changes["selectedProductId"] = selected_product_id

        if pending_variant_id != "unchanged":
            changes["pendingVariantId"] = pending_variant_id or ""

        session_snapshot.reference.update(changes)
        return {
            "message": localized_message,
            "language": language,
            "action": action,
            "state": state,
            "product": product,
            "products": response_products or [],
            "reviews": response_reviews or [],
            "reviewSummary": review_summary,
            "sellerRating": seller_rating,
            "cart": cart,
            "cartSummary": cart_summary,
            "cartSubtotalMinor": sum(
                item["lineTotalMinor"] for item in cart_summary
            ),
            "customerDraft": customer_draft,
        }

    # Stock moved while the customer was deciding. Say so immediately, before
    # answering anything else: a changed order is more urgent than the question
    # they just asked, and silently shipping a different order is not an option.
    # The corrected cart is persisted by respond(), so this fires only once.
    if sold_out_variant_ids or reduced_lines:
        notes = [
            f"{describe_missing_variant(database, session['businessId'], variant_id, products)}"
            " has just sold out, so I removed it from your order."
            for variant_id in sold_out_variant_ids
        ]
        notes += [
            f"Only {available} of {product['name']}"
            + (f" (size {variant['size']})" if variant.get("size") else "")
            + f" are left, so I reduced that line to {available}."
            for product, variant, available in reduced_lines
        ]

        if cart_summary:
            notes.append(
                "The rest of your order is unchanged. Shall we continue?",
            )
            # Mid-checkout the collected details are still good, so stay put.
            next_stock_state = current_state
        else:
            notes.append("Your order is empty now. Would you like to choose something else?")
            next_stock_state = "browsing"
            customer_draft = {}

        return respond(
            " ".join(notes),
            "start-order",
            next_state=next_stock_state,
            response_products=products[:4] if not cart_summary else [],
        )

    # A delivery-price question is answered before the order-status check below,
    # because "delivery" is also a tracking word. Checkout and completed states
    # are excluded so a mid-checkout question cannot derail the collected draft.
    named_district = find_district_in_text(message) or (
        find_district_in_text(ai_intent["district"])
        if ai_intent.get("district")
        else None
    )

    if current_state == "quoting-district" and not named_district:
        # That reply was not a district after all. Handle it as a normal message.
        current_state = "browsing"

    if current_state in {"browsing", "quoting-district"} and session.get(
        "status",
    ) != "completed" and (
        current_state == "quoting-district"
        or is_delivery_fee_question(message)
        or intent_is("delivery_quote")
    ):
        draft_address = customer_draft.get("address") or {}
        district = named_district or draft_address.get("district", "")

        if not district:
            return respond(
                "Which district should we deliver to? I will check the exact "
                "delivery fee for that district.",
                "collect-quote-district",
                next_state="quoting-district",
            )

        quote = delivery_quote(
            database,
            session["businessId"],
            district,
            cart_weight_grams(cart_summary),
        )

        if not quote:
            return respond(
                "The seller has not set up a courier yet, so I cannot quote a "
                "delivery fee for that district.",
                "show-delivery-quote",
                next_state="browsing",
            )

        # Remember the district so checkout does not ask for it a second time.
        customer_draft["address"] = {
            "line1": "",
            "line2": "",
            "city": "",
            "postalCode": "",
            **draft_address,
            "district": quote["district"],
        }
        return respond(
            delivery_quote_message(quote),
            "show-delivery-quote",
            next_state="browsing",
        )

    # Once an order is submitted, normal conversation stays attached to that
    # order. Do not treat "ok", "thanks" or a status question as a brand-new
    # shopping session. A new catalogue is shown only when the customer clearly
    # asks to place another order.
    # The keyword list matches broad words like "deliver" and "shipping", so on
    # its own it hijacks browsing questions ("how long is delivery?") into an
    # order-status reply whenever the customer has any past order. It is trusted
    # only once an order exists in this conversation, or when the customer names
    # an order number. The classifier's verdict is trusted anywhere.
    keyword_status_enquiry = is_order_enquiry(lowered_message) and (
        current_state == "completed"
        or session.get("status") == "completed"
        or session.get("orderId")
        or re.search(r"\b(?:vd|vwb)[- ]?\d+", lowered_message)
    )

    latest_order = None
    if keyword_status_enquiry or intent_is("order_status"):
        latest_order = latest_order_for_session(database, session)
        if latest_order:
            session_snapshot.reference.set(
                {
                    "orderId": latest_order["id"],
                    "status": "completed",
                    "state": "completed",
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            return respond(
                order_information_message(latest_order),
                "show-order-info",
                next_state="completed",
                response_products=[],
            )

    if current_state == "completed" or session.get("status") == "completed":
        starts_new_order = is_explicit_new_order_request(lowered_message) or intent_is(
            "new_order",
        )

        if starts_new_order:
            cart = []
            cart_summary = []
            customer_draft = {}
            session_snapshot.reference.update(
                {
                    "status": "active",
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                },
            )
            return respond(
                "Of course. Here is the catalogue for your new order. Choose a "
                "product to see its details, sizes and available stock.",
                "start-another-order",
                next_state="browsing",
                response_products=products,
                selected_product_id=(
                    None if not session.get("productId") else "unchanged"
                ),
            )

        order = latest_order_for_session(database, session)

        if order:
            response_message = order_information_message(order)
        else:
            response_message = (
                "Your order has already been submitted. Ask me about that order, "
                "or say 'another order' to shop again."
            )

        return respond(
            response_message,
            "show-order-info",
            next_state="completed",
            response_products=[],
        )

    # The customer was asked how many of a named product they want.
    if current_state == "awaiting-item-quantity":
        pending_product, pending_variant = find_variant(
            products,
            session.get("pendingVariantId", ""),
        )
        wanted_quantity = quantity_from_message(message, ai_intent.get("quantity"))

        if not pending_variant:
            return respond(
                "Sorry, that item is no longer available. Which product would "
                "you like to order?",
                "show-catalog",
                next_state="browsing",
                response_products=products,
                pending_variant_id=None,
            )

        if wanted_quantity <= 0:
            # Not a number. If they clearly moved on to something else, let the
            # normal handling take over rather than asking again forever.
            if ai_intent.get("intent") and not intent_is(
                "start_order",
                "set_quantity",
                "unknown",
            ):
                current_state = "browsing"
            else:
                return respond(
                    f"How many {pending_product['name']} would you like? Send "
                    "a number, for example 2.",
                    "collect-item-quantity",
                    next_state="awaiting-item-quantity",
                    product=pending_product,
                )

        if wanted_quantity > 0:
            cart, line_quantity = set_variant_quantity(
                cart,
                pending_variant["id"],
                wanted_quantity,
                pending_variant.get("availableStock", 0),
            )
            cart_summary = summarize_chat_cart(cart, products)
            size_label = (
                f" (size {pending_variant['size']})"
                if pending_variant.get("size")
                else ""
            )
            line_total = next(
                (
                    item["lineTotalMinor"]
                    for item in cart_summary
                    if item["variantId"] == pending_variant["id"]
                ),
                0,
            )
            capped_text = (
                f" Only {line_quantity} left in stock, so that is what I have "
                "put in your order."
                if line_quantity < wanted_quantity
                else ""
            )
            return respond(
                f"Added {line_quantity} x {pending_product['name']}{size_label} "
                f"- LKR {line_total / 100:,.2f}.{capped_text} Would you like "
                "anything else, or shall we take your delivery details?",
                "start-order",
                next_state="browsing",
                product=pending_product,
                pending_variant_id=None,
            )

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
            "Do you have a second phone number? Send it, or type 'skip' if you "
            "only have one number.",
            "collect-secondary-phone",
            next_state="collecting-secondary-phone",
        )

    if current_state == "collecting-secondary-phone":
        if is_optional_phone_skip(message):
            customer_draft["secondaryPhoneNumber"] = ""
        else:
            try:
                normalize_sri_lankan_phone(message)
            except ValueError as error:
                return respond(
                    f"{error} Send a valid second number, or type 'skip' to "
                    "continue with one number.",
                    "collect-secondary-phone",
                    next_state="collecting-secondary-phone",
                )
            customer_draft["secondaryPhoneNumber"] = message.strip()

        return respond(
            "Please send your street address (for example: No. 45 Park Road).",
            "collect-address",
            next_state="collecting-address",
        )

    if current_state == "collecting-address":
        try:
            address_line = required_text(message.strip(), "Street address", 200)
        except ValueError as error:
            return respond(
                str(error),
                "collect-address",
                next_state="collecting-address",
            )

        # A district captured during a delivery quote is not asked for again.
        quoted_district = (customer_draft.get("address") or {}).get("district", "")
        customer_draft["address"] = {
            "line1": address_line,
            "line2": "",
            "city": "",
            "district": quoted_district,
            "postalCode": "",
        }

        if quoted_district:
            return respond(
                f"Thanks. I already have {quoted_district} as your delivery "
                "district. What is the nearest city?",
                "collect-nearest-city",
                next_state="collecting-nearest-city",
            )

        return respond(
            "Which district should we deliver to?",
            "collect-district",
            next_state="collecting-district",
        )

    if current_state == "collecting-district":
        # Only a recognised district can be accepted. An unknown spelling would
        # silently fall back to the courier's common price and misquote the fee.
        if not is_known_district(message):
            return respond(
                "I could not recognise that district. Please send one of Sri "
                "Lanka's 25 districts, for example Colombo, Gampaha or Jaffna.",
                "collect-district",
                next_state="collecting-district",
            )

        customer_draft["address"]["district"] = district_display_name(message)
        return respond(
            "What is the nearest city?",
            "collect-nearest-city",
            next_state="collecting-nearest-city",
        )

    if current_state == "collecting-nearest-city":
        try:
            customer_draft["address"]["city"] = parse_required_location(
                message, "nearest city"
            )
        except ValueError as error:
            return respond(
                str(error),
                "collect-nearest-city",
                next_state="collecting-nearest-city",
            )

        return respond(
            "Do you have any extra delivery note? Type it, or type 'skip' if "
            "there is no note.",
            "collect-delivery-note",
            next_state="collecting-delivery-note",
        )

    if current_state == "collecting-delivery-note":
        customer_draft["deliveryNote"] = "" if is_optional_phone_skip(message) else message.strip()

        item_text = ", ".join(
            f"{item['quantity']} × {item['productName']}"
            + (f" (size {item['size']})" if item["size"] else "")
            for item in cart_summary
        )
        address = customer_draft["address"]
        subtotal_minor = sum(item["lineTotalMinor"] for item in cart_summary)
        # Quote the same courier the order will use, so the customer confirms
        # the total they were shown instead of an unknown delivery fee.
        quote = delivery_quote(
            database,
            session["businessId"],
            address["district"],
            cart_weight_grams(cart_summary),
        )

        if quote:
            totals_text = (
                f"Items: LKR {subtotal_minor / 100:,.2f}. Delivery to "
                f"{quote['district']} ({quote['weightGrams'] / 1000:,.2f} kg) by "
                f"{quote['courierName']}: LKR {quote['deliveryFeeMinor'] / 100:,.2f}. "
                f"Total: LKR "
                f"{(subtotal_minor + quote['deliveryFeeMinor']) / 100:,.2f}. "
            )
        else:
            totals_text = (
                f"Items: LKR {subtotal_minor / 100:,.2f}. The delivery fee will "
                "be confirmed by the seller. "
            )

        response_message = (
            f"Please confirm your order: {item_text}. Customer: "
            f"{customer_draft['name']}, {customer_draft['phoneNumber']}"
            + (f" / {customer_draft['secondaryPhoneNumber']}" if customer_draft.get("secondaryPhoneNumber") else "")
            + ". Delivery: "
            f"{address['line1']}, {address['city']}, {address['district']}. "
            + (f"Note: {customer_draft['deliveryNote']}. " if customer_draft.get("deliveryNote") else "")
            + totals_text
            + "Reply 'confirm order' to submit, or 'change order' to edit the details."
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
            or intent_is("confirm_order")
        )
        # Whole words only. As a substring, "no" matches "now", so "yes,
        # confirm now" used to be read as a rejection and wiped the draft.
        changes_order = bool(
            set(word_characters(lowered_message).split())
            & {"change", "edit", "no", "cancel", "wrong", "වෙනස්", "නෑ", "නැහැ", "தவறு"}
        ) or intent_is("change_order")

        if confirms_order:
            try:
                order = create_public_chat_order(
                    database,
                    session_id,
                    provided_token,
                    {
                        "customer": {
                            "name": customer_draft.get("name"),
                            "phoneNumber": customer_draft.get("phoneNumber"),
                            "secondaryPhoneNumber": customer_draft.get("secondaryPhoneNumber", ""),
                            "email": customer_draft.get("email", ""),
                            "address": customer_draft.get("address"),
                        },
                        "items": cart,
                        "deliveryNote": customer_draft.get("deliveryNote", ""),
                    },
                )
            except ApiError as error:
                # Someone else can still take the last unit between the summary
                # and the transaction. The raw message names an SKU the customer
                # has never seen, so it must not be what they read at the very
                # moment they commit to buying.
                if error.code not in STOCK_CONFLICT_CODES:
                    raise

                cart, sold_out_variant_ids, reduced_lines = reconcile_cart_stock(
                    cart,
                    products,
                )
                cart_summary = summarize_chat_cart(cart, products)
                return respond(
                    "Sorry - one of your items sold out while we were "
                    "finishing the order, so I could not place it. I have "
                    "updated your order to what is still available. Reply "
                    "'confirm order' to place it, or tell me what to change.",
                    "confirm-order",
                    next_state="awaiting-confirmation",
                )
            response_message = translate_chat_message(
                f"Your order {order['orderNumber']} was placed successfully. "
                f"Items subtotal: LKR {order['subtotalMinor'] / 100:,.2f}, "
                f"delivery: LKR {order['deliveryFeeMinor'] / 100:,.2f}, total: "
                f"LKR {order['totalAmountMinor'] / 100:,.2f}.",
                language,
            )
            save_chat_message(
                session_snapshot.reference,
                "assistant",
                response_message,
                {
                    "action": "order-confirmed",
                    "orderId": order["id"],
                    "language": language,
                },
            )
            session_snapshot.reference.update(
                {
                    "state": "completed",
                    "status": "completed",
                    "cart": [],
                    "language": language,
                    "selectedProductId": firestore.DELETE_FIELD,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                },
            )
            return {
                "message": response_message,
                "language": language,
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

    # Product cards add items to the browser cart while the conversation stays
    # in browsing mode. When the customer answers "no" to "add any other
    # item?", continue checkout instead of treating that short reply as a new
    # catalogue request. The cart guard prevents an unrelated "no" from
    # starting contact collection.
    if (
        current_state == "browsing"
        and cart_summary
        and (is_finished_selecting_items(message) or intent_is("finished_selecting"))
    ):
        item_count = sum(item["quantity"] for item in cart_summary)
        return respond(
            f"Great. Your order draft has {item_count} item(s). What is your "
            "full name?",
            "collect-name",
            next_state="collecting-name",
            response_products=[],
        )

    wants_catalog = any(
        phrase in lowered_message for phrase in CATALOG_PHRASES
    ) or intent_is("show_catalog")
    wants_to_order = any(
        phrase in lowered_message for phrase in ORDER_INTENT_PHRASES
    ) or intent_is("start_order")
    wants_alternatives = any(
        phrase in lowered_message for phrase in ALTERNATIVE_PHRASES
    ) or intent_is("similar_products")
    category_request = find_category_request(message, products)
    matching_products = find_matching_products(message, products)

    # The classifier pulls the product out of a mixed sentence - "මට black bag
    # එකක් ඕන" yields "black bag" - which the catalogue matcher can then
    # resolve. Only the extracted words are trusted; the product itself is
    # always looked up in this seller's own catalogue.
    if not matching_products and ai_intent.get("productQuery"):
        matching_products = find_matching_products(
            ai_intent["productQuery"],
            products,
        )

    if not category_request and ai_intent.get("categoryQuery"):
        category_request = find_category_request(
            ai_intent["categoryQuery"],
            products,
        )

    explicitly_selected_product = (
        matching_products[0] if len(matching_products) == 1 else None
    )
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

    # Correcting a quantity that is already in the order - "make it 2", "thawa
    # 3k neme okkoma 3k" (not 3 more, 3 in total), "remove it". This runs before
    # the order branch so a correction is never read as a fresh product choice.
    if intent_is("set_quantity") and cart_summary:
        target_line = None

        if selected_product:
            target_line = next(
                (
                    line
                    for line in cart_summary
                    if line["productId"] == selected_product["id"]
                ),
                None,
            )

        # "okkoma 3k" names no product. With a single line there is no doubt
        # which one they mean; with several, guessing would edit the wrong item.
        if not target_line and len(cart_summary) == 1:
            target_line = cart_summary[0]

        if not target_line:
            return respond(
                "Which item should I change the quantity of? "
                + ", ".join(line["productName"] for line in cart_summary)
                + ".",
                "start-order",
                next_state="browsing",
            )

        _target_product, target_variant = find_variant(
            products,
            target_line["variantId"],
        )
        asked_quantity = ai_intent.get("quantity", 0)
        cart, line_quantity = set_variant_quantity(
            cart,
            target_line["variantId"],
            asked_quantity,
            (target_variant or {}).get("availableStock", 0),
            ai_intent.get("quantityMode", "total"),
        )
        cart_summary = summarize_chat_cart(cart, products)

        if line_quantity == 0:
            response_message = (
                f"Removed {target_line['productName']} from your order."
            )
        else:
            capped_text = (
                f" Only {line_quantity} left in stock, so that is what I have "
                "put in your order."
                if line_quantity < asked_quantity
                else ""
            )
            response_message = (
                f"Your order now has {line_quantity} x "
                f"{target_line['productName']}.{capped_text}"
            )

        return respond(
            f"{response_message} Would you like anything else, or shall we "
            "take your delivery details?",
            "start-order",
            next_state="browsing",
        )

    if wants_to_order:
        # A customer who says "mata GM2 pro dekak ona" has already chosen. Being
        # told to click Add is a dead end for anyone typing Sinhala or speaking,
        # which is exactly who needs to order without calling the seller.
        if selected_product:
            variant = choose_variant(selected_product, ai_intent.get("sizeQuery", ""))
            available_sizes = [
                option.get("size")
                for option in selected_product.get("variants", [])
                if option.get("size")
            ]

            if not variant and available_sizes:
                return respond(
                    f"Which size of {selected_product['name']} would you like? "
                    f"Available: {', '.join(available_sizes)}.",
                    "show-product",
                    next_state="browsing",
                    product=selected_product,
                    selected_product_id=selected_product["id"],
                )

            if variant:
                asked_quantity = ai_intent.get("quantity") or 0
                size_label = (
                    f" (size {variant['size']})" if variant.get("size") else ""
                )

                # Confirm which product, and how many, before putting anything
                # in the order. Silently assuming one is how a customer ends up
                # with a quantity they never asked for.
                if asked_quantity <= 0:
                    unit_price = variant.get("sellingPriceMinor") or selected_product.get(
                        "sellingPriceMinor",
                        0,
                    )
                    return respond(
                        f"{selected_product['name']}{size_label} - LKR "
                        f"{unit_price / 100:,.2f} each. How many would you "
                        "like to order?",
                        "collect-item-quantity",
                        next_state="awaiting-item-quantity",
                        product=selected_product,
                        selected_product_id=selected_product["id"],
                        pending_variant_id=variant["id"],
                    )

                cart, line_quantity = set_variant_quantity(
                    cart,
                    variant["id"],
                    asked_quantity,
                    variant.get("availableStock", 0),
                    ai_intent.get("quantityMode", "total"),
                )
                cart_summary = summarize_chat_cart(cart, products)
                size_text = f" (size {variant['size']})" if variant.get("size") else ""
                capped_text = (
                    f" Only {line_quantity} left in stock, so that is what I "
                    "have put in your order."
                    if line_quantity < asked_quantity
                    else ""
                )
                return respond(
                    f"Your order now has {line_quantity} x "
                    f"{selected_product['name']}{size_text}.{capped_text} Would "
                    "you like anything else, or shall we take your delivery "
                    "details?",
                    "start-order",
                    next_state="browsing",
                    product=selected_product,
                    selected_product_id=selected_product["id"],
                )

        if not cart_summary:
            response_message = (
                "Which product would you like to order? Tell me the name and "
                "how many, or choose one below and use Add to order."
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
            seller_reviews = list_public_seller_reviews(
                database,
                session["businessId"],
            )
            product_rating = round(
                sum(review["rating"] for review in reviews) / len(reviews), 1
            ) if reviews else 0
            seller_average = round(
                sum(review["rating"] for review in seller_reviews) / len(seller_reviews),
                1,
            ) if seller_reviews else 0

            return respond(
                (
                    f"Here are verified reviews for {selected_product['name']}."
                    if reviews
                    else f"{selected_product['name']} does not have approved reviews yet."
                ),
                "show-reviews",
                next_state="browsing",
                product=selected_product,
                response_reviews=reviews[:6],
                review_summary={
                    "averageRating": product_rating,
                    "reviewCount": len(reviews),
                },
                seller_rating={
                    "businessName": catalog["business"].get("name", "Seller"),
                    "averageRating": seller_average,
                    "reviewCount": len(seller_reviews),
                    "recentReviews": seller_reviews[:3],
                },
                selected_product_id=selected_product["id"],
            )

        deterministic_description = (
            selected_product.get("aiDescription")
            or selected_product.get("description")
            or "The seller has not added a detailed description yet."
        )

        is_product_overview_request = is_catalog_number_choice(message) or any(
            phrase in lowered_message
            for phrase in (
                "tell me about",
                "product details",
                "view details",
                "know more",
                "more about",
            )
        )

        product_reviews = []
        product_review_summary = None
        answer_in_customer_language = False

        if is_product_overview_request:
            product_reviews = list_public_product_reviews(
                database,
                session["businessId"],
                selected_product["id"],
            )
            product_rating = round(
                sum(review["rating"] for review in product_reviews)
                / len(product_reviews),
                1,
            ) if product_reviews else 0
            product_review_summary = {
                "averageRating": product_rating,
                "reviewCount": len(product_reviews),
            }
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
                f"{size_text} Ask about a feature, compare similar products, or choose "
                "Order this product when you are ready."
            )
        else:
            generated_answer = generate_product_answer(
                message,
                selected_product,
                language,
                related_products(products, selected_product, limit=6),
            )
            # The model answers in the customer's language, so an English
            # phrase list can no longer tell whether it knew the answer. It
            # ends the reply with a status marker instead, in any language.
            answer_is_uncertain = not generated_answer or MISSING_FACT_MARKER in (
                generated_answer
            )

            if generated_answer:
                for marker in (MISSING_FACT_MARKER, ANSWERED_MARKER):
                    generated_answer = generated_answer.replace(marker, "")
                generated_answer = generated_answer.strip()

            answer_in_customer_language = bool(generated_answer)
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
            response_reviews=(product_reviews[:4] if is_product_overview_request else []),
            review_summary=product_review_summary,
            # Similar products accompany every product answer, not only a full
            # overview. A shopper asking about one feature is exactly who wants
            # to see the nearest alternatives.
            response_products=related_products(products, selected_product),
            selected_product_id=selected_product["id"],
            is_translated=answer_in_customer_language,
        )

    # The message named several products equally well. Asking which one is a
    # real answer; falling through to the generic prompt is a dead end that
    # also pages the seller for a question the catalogue can settle.
    if len(matching_products) > 1:
        return respond(
            "I found more than one product matching that. Which one would you "
            "like to know about?",
            "show-catalog",
            next_state="browsing",
            response_products=matching_products[:4],
        )

    is_simple_greeting = intent_is("greeting") or normalized_phrase(message) in {
        normalized_phrase(phrase) for phrase in GREETING_PHRASES
    }

    # "What is your cheapest earbud", "anything under 3000", "can I return it"
    # and "do you accept cash on delivery" name no single product, so nothing
    # above matched. Only the catalogue and the seller's own policy text are
    # offered as facts.
    if not is_simple_greeting and intent_is(
        "product_question",
        "policy_question",
        "unknown",
    ):
        catalogue_answer = generate_catalogue_answer(
            message,
            products,
            language,
            catalog["business"].get("storefrontFaq", ""),
        )

        if catalogue_answer and MISSING_FACT_MARKER not in catalogue_answer:
            for marker in (MISSING_FACT_MARKER, ANSWERED_MARKER):
                catalogue_answer = catalogue_answer.replace(marker, "")

            return respond(
                catalogue_answer.strip(),
                "show-catalog",
                next_state="browsing",
                response_products=products[:4],
                is_translated=True,
            )

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

    # The customer was quoted the cheapest courier for their district, so the
    # order is assigned that same courier instead of the dashboard's
    # quality-weighted recommendation. Both callers of this function - the chat
    # state machine and the storefront checkout - are covered here.
    courier_id = payload.get("courierId", "")

    if not courier_id:
        district = (customer_payload.get("address") or {}).get("district", "")
        cart_summary = summarize_chat_cart(
            normalize_chat_cart(payload.get("items")) or [],
            session_catalog(database, session)["products"],
        )
        quote = cheapest_courier_quote(
            database,
            session["businessId"],
            district,
            cart_weight_grams(cart_summary),
        )
        courier_id = quote["courier"].get("id", "") if quote else ""

    order_payload = {
        "customerId": customer["id"],
        "items": payload.get("items"),
        "deliveryAddress": customer_payload.get("address"),
        "courierId": courier_id,
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
    customer_summary = {
        "customerId": customer["id"],
        "name": customer_payload.get("name") or customer.get("name") or "Customer",
        "phoneNumber": customer_payload.get("phoneNumber") or customer.get("normalizedPhone", ""),
        "secondaryPhoneNumber": customer_payload.get("secondaryPhoneNumber", "")
        or customer.get("normalizedSecondaryPhone", ""),
        "email": customer_payload.get("email", "") or customer.get("email", ""),
        "address": customer_payload.get("address") or customer.get("defaultAddress") or {},
    }
    session_snapshot.reference.update(
        {
            "status": "completed",
            "state": "completed",
            "cart": [],
            "orderId": order["id"],
            "customerDraft": customer_summary,
            "customerSummary": customer_summary,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    return public_order_confirmation(order)
