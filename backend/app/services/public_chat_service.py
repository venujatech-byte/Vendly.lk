import hashlib
import hmac
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

from firebase_admin import firestore
from flask import current_app
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.customer_service import (
    create_customer,
    list_customers,
    normalize_sri_lankan_phone,
)
from app.services.ai_service import (
    ANSWERED_MARKER,
    money_text,
    MISSING_FACT_MARKER,
    ai_status,
    detect_chat_language,
    generate_catalogue_answer,
    generate_comparison_answer,
    generate_product_answer,
    generate_storefront_intent,
    translate_chat_message,
)
from app.services.chat_event_service import notify_seller_attention
from app.services.media_service import upload_chat_data_url
from app.services.courier_service import (
    district_display_name,
    district_first_kg_price,
    find_district_in_text,
    is_known_district,
    normalize_district,
    recommend_couriers,
)
from app.services.operations_service import sync_ai_failure_notification
from app.services.order_service import (
    add_items_to_order,
    create_order,
    order_accepts_more_items,
    update_order_status,
)
from app.services.public_catalog_service import (
    get_public_product,
    get_public_store,
    public_product,
)
from app.services.text import optional_text, required_text
from app.services.review_service import (
    list_public_product_reviews,
    list_public_seller_reviews,
    write_order_review,
)


# The review flow. Named `collecting-*` on purpose: those states are excluded
# from intent classification, and here too the message IS the data - a rating,
# a sentence, a photo.
REVIEW_STATES = {
    "collecting-review-product",
    "collecting-review-rating",
    "collecting-review-text",
    "collecting-review-photo",
    "collecting-review-seller-rating",
}

MAX_REVIEW_PHOTOS = 4

RATING_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "terrible": 1, "bad": 2, "ok": 3, "okay": 3, "good": 4, "great": 5,
    "excellent": 5, "perfect": 5,
}

SKIP_WORDS = {"skip", "no", "nope", "done", "finish", "nathi", "epa", "නැහැ", "එපා", "වෙන්න"}


def parse_star_rating(message):
    """Read 1-5 from "4", "4/5", "four stars", four star emoji, or "good"."""
    text = str(message).strip().casefold()
    stars = text.count("⭐") + text.count("★")

    if 1 <= stars <= 5:
        return stars

    digits = re.search(r"\b([1-5])\b", text)
    if digits:
        return int(digits.group(1))

    for word, value in RATING_WORDS.items():
        if word in text.split():
            return value

    return None


def wants_to_skip(message):
    return bool(set(str(message).casefold().split()) & SKIP_WORDS)


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

# "show my cart" carries no product name, so without this it fell through to
# product resolution and the customer was asked which product they meant.
CART_PHRASES = (
    "my cart",
    "the cart",
    "in cart",
    "my basket",
    "my order so far",
    "what did i add",
    "what have i added",
    "cart eke",
    "cart එකේ",
    "mage cart",
    "මගේ cart",
    "බඩු ලැයිස්තුව",
)

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


MERGE_ORDER_PHRASES = (
    "add to my order",
    "add to that order",
    "add to the order",
    "add to my existing",
    "add to existing",
    "same order",
    "one order",
    "together",
    "add it to",
    "add them to",
    "ekathu karanna",
    "එකතු කරන්න",
    "එකම order",
)

SEPARATE_ORDER_PHRASES = (
    "separate order",
    "separately",
    "new order",
    "another order",
    "different order",
    "wenama",
    "වෙනම",
)


def wants_to_merge_orders(message):
    lowered = str(message or "").casefold()
    return any(phrase in lowered for phrase in MERGE_ORDER_PHRASES)


def wants_separate_order(message):
    lowered = str(message or "").casefold()
    return any(phrase in lowered for phrase in SEPARATE_ORDER_PHRASES)


PAYMENT_CHOICE_PHRASES = (
    ("bank-half", (
        "half bank", "half transfer", "half payment", "part payment",
        "partial", "advance", "deposit", "half deposit",
        "aduma", "baagayak", "බාගයක්", "අඩක්", "පාதி",
    )),
    ("bank-full", (
        "full bank", "full transfer", "full payment", "bank transfer",
        "transfer full", "pay full", "full amount", "online payment",
        "sampurna", "සම්පූර්ණ", "முழு",
    )),
    ("cod", (
        "cash on delivery", "cod", "cash", "on delivery", "pay on delivery",
        "courier ekata", "බඩුව ලැබෙන විට", "මුදලින්", "delivery ekata",
    )),
)


def chat_payment_method(customer_draft):
    """Map the chat's payment answer onto the order's payment method."""
    choice = customer_draft.get("paymentChoice")

    if choice == "bank-full":
        return "paid"

    if choice == "bank-half":
        return "deposit"

    if choice == "cod":
        return "cod"

    # No explicit answer - an older draft, or a route that skipped the
    # question. Fall back to whatever the conversation inferred.
    return customer_draft.get("paymentMethod", "cod")


def payment_summary_text(choice):
    """One line for the confirmation summary, so the terms are on screen."""
    if choice == "bank-full":
        return (
            "Payment: full bank transfer - I will send our bank details once "
            "you confirm, and the seller holds the order until it arrives. "
        )

    if choice == "bank-half":
        return (
            "Payment: part bank transfer - I will send our bank details once "
            "you confirm, and the courier collects the balance on delivery. "
        )

    return "Payment: cash on delivery. "


def payment_choice_from_message(message, ai_intent=None):
    """Read the payment method from a reply, longest-meaning phrases first.

    "half bank transfer" contains "bank transfer", so the half phrases are
    checked before the full ones - otherwise every half payment would be
    recorded as a promise to send the whole amount.
    """
    lowered = str(message or "").casefold()

    for choice, phrases in PAYMENT_CHOICE_PHRASES:
        if any(phrase in lowered for phrase in phrases):
            return choice

    # The classifier already reads "I will send part only" as a deposit
    # question, so its answer stands in when the wording is unusual.
    intent = (ai_intent or {}).get("intent")

    if intent == "payment_question":
        return "bank-full"

    return None


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


def session_order_by_number(database, session, order_number):
    """An order this session already owns, looked up by its number.

    The session records every order it produced in `orderIds`, so ownership is
    already proven for those - naming one is not a guess and must not send the
    customer back through the phone check.
    """
    orders_reference = (
        database.collection("businesses")
        .document(session["businessId"])
        .collection("orders")
    )
    owned = list(session.get("orderIds") or [])
    if session.get("orderId"):
        owned.append(session["orderId"])

    for order_id in dict.fromkeys(owned):
        snapshot = orders_reference.document(order_id).get()
        if snapshot.exists and str(
            snapshot.to_dict().get("orderNumber", ""),
        ).casefold() == str(order_number).casefold():
            return {"id": snapshot.id, **snapshot.to_dict()}

    return None


ORDER_NUMBER_PATTERN = re.compile(r"\b((?:vd|vwb)[- ]?\d+)\b", re.IGNORECASE)

# A guessed order number plus repeated phone guesses is the only way in, so the
# attempts are capped per session.
MAX_ORDER_VERIFICATION_ATTEMPTS = 5

# How many products a reply may carry, how many a comparison may cover, and how
# many stay remembered as "these". Comparison used to reuse the reply cap, so
# "compare these" over six shown products silently dropped two of them.
MAX_RESPONSE_PRODUCTS = 12
MAX_COMPARE_PRODUCTS = 10
MAX_REMEMBERED_PRODUCTS = 12
MAX_SEEN_PRODUCTS = 100


def order_number_in_message(message):
    """Return an order or waybill number the customer typed, normalised."""
    match = ORDER_NUMBER_PATTERN.search(str(message))

    if not match:
        return ""

    return match.group(1).replace(" ", "-").upper()


def find_order_by_number(database, business_id, order_number, phone_number):
    """Look up one order for a customer who has no session link to it.

    A guest who ordered, closed the tab and came back has neither `orderId` on
    the session nor a `customerUid`, so `latest_order_for_session` finds
    nothing and they have to phone the seller - the exact outcome the storefront
    exists to avoid.

    The order number alone is guessable, so the phone on the order must match
    too. This mirrors the check `review_service` already makes.
    """
    try:
        normalized_phone = normalize_sri_lankan_phone(phone_number)
    except ValueError:
        return None

    snapshots = list(
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
        .where(filter=FieldFilter("orderNumber", "==", order_number))
        .limit(1)
        .stream(),
    )

    if not snapshots:
        return None

    order = snapshots[0].to_dict()

    if (order.get("customerSnapshot") or {}).get("normalizedPhone") != normalized_phone:
        return None

    return {"id": snapshots[0].id, **order}


def order_information_message(order):
    status = str(order.get("fulfilmentStatus") or "needs-confirmation").replace(
        "-", " "
    )
    parts = [
        f"Your order {order.get('orderNumber', '')} is currently {status}.",
        f"Order total: LKR {order.get('totalAmountMinor', 0) / 100:,.2f}.",
    ]
    courier = order.get("courierSnapshot") or {}
    courier_name = courier.get("name")
    if courier_name:
        parts.append(f"Courier: {courier_name}.")
    if order.get("waybillNumber"):
        parts.append(f"Waybill number: {order['waybillNumber']}.")

    # Frozen onto the order at checkout, so it stays accurate even if the
    # seller later changes the courier's configured estimate.
    days = courier.get("averageDeliveryDays") or 0
    if days and order.get("fulfilmentStatus") not in {"delivered", "returned", "cancelled"}:
        parts.append(
            f"Expected delivery is about {days} working "
            f"{'day' if days == 1 else 'days'} from dispatch.",
        )
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


# Below this, a Latin-script message is an answer, not a sentence.
MINIMUM_WORDS_TO_SWITCH_LANGUAGE = 3

GREETING_LANGUAGES = {"en", "si", "ta"}

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

    # A short Latin-script reply is nearly always an answer rather than a
    # sentence: a district, a name, a phone number, "yes". There is no language
    # in it to detect, and the model will guess - "Gampaha" was read as Sinhala
    # and switched an English conversation over. Too little signal to act on.
    if len(word_characters(message).split()) < MINIMUM_WORDS_TO_SWITCH_LANGUAGE:
        return language

    # The intent classifier already read this message and reported its
    # language, so reuse that instead of paying for a second call. This runs
    # in both directions: the old order returned the settled language before
    # ever reaching here, so a Sinhala conversation could never switch back to
    # English however plainly the customer wrote in it.
    if detected_language in {"en", "si", "ta"}:
        return detected_language

    if language != "en":
        return language

    return detect_chat_language(message) or language


# Intent classification is worth an AI call only where the customer is steering
# the conversation. In the collecting-* states the message IS the data - a name,
# a phone number, an address - so it is read literally and never classified.
# States where the customer is part-way through building or checking out an
# order that has not been placed yet.
DRAFT_IN_PROGRESS_STATES = {
    "choosing-payment",
    "choosing-order-merge",
    "awaiting-variant",
    "awaiting-item-quantity",
    "collecting-name",
    "collecting-phone",
    "collecting-secondary-phone",
    "collecting-address",
    "collecting-district",
    "collecting-nearest-city",
    "collecting-delivery-note",
    "awaiting-confirmation",
}

INTENT_CLASSIFIED_STATES = {
    "browsing",
    "choosing-order-merge",
    "awaiting-variant",
    "awaiting-item-quantity",
    "awaiting-confirmation",
    "completed",
}


def storefront_intent(message, products, state, history=None):
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
        history,
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
    return f"{name} ({size})" if size else name


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


def variant_labels(product):
    """The choices a customer picks between, in the order the seller set them."""
    return [
        option.get("size")
        for option in product.get("variants", [])
        if option.get("size")
    ]


def match_variant_in_message(product, message):
    """Find the variant a bare reply names: "orange", "the black one", "42mm".

    `choose_variant` reads the model's `sizeQuery`, which is empty for a
    one-word reply the classifier saw no order intent in. That left the
    customer answering the question correctly and being asked it again.
    """
    variants = product.get("variants", []) if product else []

    if not variants:
        return None

    whole = normalized_phrase(message)
    words = message_word_alias_set(message) | message_phrase_aliases(message)

    for variant in variants:
        label = normalized_phrase(variant.get("size", ""))

        if not label:
            continue

        # Whole-word only. A substring match would let "large" claim a
        # variant named "XL" inside some other word.
        if label == whole or label in words:
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


# Below this many products, asking the customer to narrow down is friction:
# they can just look. Above it, a full dump buries the conversation on a phone.
BROWSABLE_CATALOGUE_SIZE = 6


def catalogue_categories(products):
    """Category names that actually have products, in a stable order."""
    seen = []
    for product in products:
        name = product.get("categoryName", "").strip()
        if name and name not in seen:
            seen.append(name)
    return seen


CANCEL_ORDER_PHRASES = (
    "cancel my order",
    "cancel the order",
    "cancel order",
    "cancel this order",
    "i want to cancel",
    "dont want it anymore",
    "don't want it anymore",
    "order eka cancel",
    "cancel karanna",
    "epa cancel",
    "අවලංගු",
    "අවලංගු කරන්න",
    "ଇரத்து",
    "ரத்து செய்",
)

# Deliberately narrower than the seller's own STATUS_TRANSITIONS, which also
# permit packed -> cancelled. A packed order is work the seller has already
# done: picked, boxed and often labelled. They should decide whether to undo it,
# so the bot escalates instead of cancelling. Add "packed" here if you would
# rather let customers cancel right up to dispatch.
CUSTOMER_CANCELLABLE_STATUSES = {"needs-confirmation", "confirmed"}


def is_cancel_order_request(message):
    text = str(message).casefold()
    return any(phrase in text for phrase in CANCEL_ORDER_PHRASES)


DEPOSIT_REQUEST_PHRASES = (
    "bank transfer",
    "bank deposit",
    "deposit",
    "advance payment",
    "pay online",
    "pay in advance",
    "prepay",
    "account number",
    "bank details",
    "bank account",
    "කරුව",
    "බැංකු",
    "ගිණුම",
    "வங்கி",
    "முன்பணம்",
    "கணக்கு",
)


def is_deposit_request(message):
    """Recognise a customer asking to pay by transfer rather than on delivery."""
    return any(phrase in str(message).casefold() for phrase in DEPOSIT_REQUEST_PHRASES)


def catalog_business_name(database, business_id):
    """The shop's own name, for a message written outside a catalogue load."""
    snapshot = database.collection("businesses").document(business_id).get()

    if not snapshot.exists:
        return "the seller"

    return (snapshot.to_dict() or {}).get("name") or "the seller"


def bank_details_message(bank, business_name):
    """Lay out the seller's account so a customer can actually transfer to it."""
    lines = [
        line
        for line in (
            f"Bank: {bank.get('bankName', '')}" if bank.get("bankName") else "",
            f"Branch: {bank.get('branch', '')}" if bank.get("branch") else "",
            f"Account name: {bank.get('accountName', '')}" if bank.get("accountName") else "",
            f"Account number: {bank.get('accountNumber', '')}" if bank.get("accountNumber") else "",
        )
        if line
    ]

    if not lines:
        return ""

    parts = [
        f"You can pay {business_name} by bank transfer.",
        " ".join(lines) + ".",
    ]

    if bank.get("instructions"):
        parts.append(bank["instructions"])

    parts.append(
        "Tell me whether you are sending the full amount or only a part - the "
        "balance is collected as cash on delivery. I will note it on your order "
        "so the seller can check for your transfer.",
    )
    return " ".join(parts)


FULL_DEPOSIT_PHRASES = (
    "full", "whole", "entire", "all of it", "complete payment", "full amount",
    "sampurna", "සම්පූර්ණ", "මුළු", "முழு", "முற்றிலும்",
)

PART_DEPOSIT_PHRASES = (
    "half", "part", "partial", "advance", "deposit only",
    # Not a bare "delivery fee" - that is the wording of a price question and
    # would be misread as a payment amount during the transfer flow.
    "delivery fee only", "only the delivery", "delivery only", "just the delivery",
    "baagayak", "බාගයක්", "කොටසක්", "பாதி", "ஒரு பகுதி",
)


def deposit_choice(message):
    """Read whether the customer is transferring everything or only a part.

    Returned as a label rather than an amount: the customer says "half" or
    "just the delivery", and turning that into money is the seller's call once
    the transfer actually lands.
    """
    text = str(message).casefold()

    # Checked first - "not the full amount" is a part payment.
    if any(phrase in text for phrase in PART_DEPOSIT_PHRASES):
        return "part"

    if any(phrase in text for phrase in FULL_DEPOSIT_PHRASES):
        return "full"

    return ""


def chat_suggestions(action, state, has_items, has_order, shown_count=0):
    """Pick the next things worth offering, given where the conversation is.

    Ids only. The storefront turns them into localised labels from its own
    table and sends a fixed English command back, so these cost no AI call and
    still work when the provider is down.

    `shown_count` is how many products this reply is putting on screen, so a
    list of several can offer to compare them.
    """
    if state == "awaiting-item-quantity":
        return ["qty-1", "qty-2", "qty-3"]

    if state == "choosing-payment":
        return ["pay-cod", "pay-bank-full", "pay-bank-half"]

    if state == "choosing-order-merge":
        return ["merge-order", "separate-order"]

    if state == "awaiting-confirmation":
        return ["confirm-order", "change-order"]

    if state == "quoting-district":
        return []

    # Mid-checkout the answer is a name or a phone number; a chip would only
    # get in the way of typing it.
    if state in DRAFT_IN_PROGRESS_STATES:
        return ["skip"] if action in {
            "collect-secondary-phone",
            "collect-delivery-note",
        } else []

    if state == "completed" or has_order and action == "show-order-info":
        return ["order-status", "another-order", "cancel-order"]

    if action == "show-bank-details":
        return ["pay-full", "pay-part"]

    if action in {"show-product", "product-answer"}:
        return ["order-this", "similar-products", "reviews", "delivery-fee"]

    # Several products on screen. Comparing them is the next thing a customer
    # wants and the hardest thing to ask for by typing, so it leads.
    if shown_count > 1:
        return ["compare-these", "show-products", "delivery-fee"]

    if has_items:
        return ["checkout", "show-products", "delivery-fee"]

    return ["show-products", "delivery-fee", "reviews"]


LOCATION_QUESTION_PHRASES = (
    "where are you", "where is your shop", "where is the shop", "your address",
    "shop address", "physical shop", "physical store", "have a shop",
    "have a store", "can i come", "can i visit", "come to the shop",
    "walk in", "showroom", "located", "location",
    "kohedha", "koheda", "thiyenne kohe",
    "කොහේද", "කොහෙද", "සාප්පුව", "ලිපිනය",
    "எங்கே", "கடை", "முகவரி",
)


def is_location_question(message):
    """Recognise "where are you", "do you have a shop", "can I come there"."""
    return any(
        phrase in str(message).casefold() for phrase in LOCATION_QUESTION_PHRASES
    )


def store_location_message(location, business_name):
    """Answer where the shop is, or say plainly that there is nowhere to visit.

    A customer planning to travel needs a straight answer either way. Silence
    or a vague reply is what makes them phone the seller.
    """
    location = location or {}
    parts = [
        piece
        for piece in (
            location.get("addressLine", ""),
            location.get("city", ""),
            location.get("district", ""),
        )
        if piece
    ]

    if location.get("isOnlineOnly") or not parts:
        return (
            f"{business_name} is an online store, so there is no shop to visit. "
            "Everything is ordered here and delivered to your address by courier."
        )

    lines = [f"You can visit {business_name} at {', '.join(parts)}."]

    if location.get("openingHours"):
        lines.append(f"Open {location['openingHours']}.")
    if location.get("mapUrl"):
        lines.append(f"Map: {location['mapUrl']}")

    lines.append("You can also order here and have it delivered.")
    return " ".join(lines)


SUPERLATIVE_PHRASES = (
    "best", "which one", "recommend", "suggest", "top ", "good one",
    "cheapest", "most popular", "worth", "should i",
    "hoodama", "hondama", "හොඳම", "වරේම", "சிறந்த", "எது",
)


COMPARISON_PHRASES = (
    "compare",
    "comparison",
    "difference between",
    "differences",
    "what is the difference",
    "side by side",
    " vs ",
    " vs.",
    "versus",
    "sasandanna",
    "sasadanna",
    "සසඳන්න",
    "වෙනස මොකක්ද",
    "වෙනස්කම්",
    "ஒப்பிடு",
    "வித்தியாசம்",
)


def wants_a_comparison(message):
    """True when the customer asked to see the differences, not for a verdict.

    "Which is best" and "compare these" read alike but want opposite answers:
    one picks a winner, the other lays the specifications out and lets the
    customer decide. Answering a comparison with a verdict hides the very
    differences that were asked for.
    """
    return any(phrase in str(message).casefold() for phrase in COMPARISON_PHRASES)


def wants_a_recommendation(message):
    """"Which is the best one?" wants an answer, not the whole shelf."""
    return any(phrase in str(message).casefold() for phrase in SUPERLATIVE_PHRASES)


MORE_PRODUCTS_PHRASES = (
    "show more",
    "more products",
    "more items",
    "any more",
    "anything else",
    "other products",
    "others",
    "next",
    "thawa",
    "thava",
    "තව",
    "වෙන",
    "wena",
)


def wants_more_products(message):
    """"Show me more" asks for the ones that were left out, not a repeat."""
    lowered = str(message).casefold()
    return any(phrase in lowered for phrase in MORE_PRODUCTS_PHRASES)


def products_named_in(answer, products):
    """The catalogue items an answer actually mentions, in catalogue order.

    A recommendation names specific products; showing the first few items of
    the whole catalogue underneath it contradicts the words directly - the text
    said "WIWU P-08B and ASPOR A337" while the cards showed a Xiaomi power
    bank, some earbuds and a smart watch.

    The whole name had to appear verbatim, which almost never survives the
    model writing naturally: the answer said "Anker Soundcore R60i NC" while
    the catalogue read "Anker Soundcore R60i NC Earbuds". Nothing matched, so
    the reply fell back to the previously shown items and recommended one
    product while picturing two others.
    """
    text = " ".join(word_characters(str(answer or "")).split())

    if not text:
        return []

    answer_words = set(text.split())

    matched = [
        product
        for product in products
        if name_appears_in(product.get("name", ""), text, answer_words)
    ]

    return matched


def products_the_customer_named(message, products):
    """Products a customer's own message points at, read generously.

    Deliberately looser than `products_named_in`, because the two do different
    jobs. That one decides which cards sit under an answer the model wrote, so
    a wrong match shows the customer a product the text never mentioned. This
    one reads what a person typed, where "compare t800 ultra and zeblace" names
    two products and only one survives a strict reading.
    """
    text = " ".join(word_characters(str(message or "")).split())
    matched = products_named_in(message, products)
    identified = {product.get("id") for product in matched}

    return matched + [
        product
        for product in unique_products_for(set(text.split()), products)
        if product.get("id") not in identified
    ]


def unique_products_for(message_words, products):
    """Products identified by a word that belongs to no other product.

    Used alongside the full-name match, never instead of it: "zeblace" is one
    word of five in "Zeblace Gts 3 Smart Watch", so it fails every full-name
    rule while being the only thing anyone would actually type.

    Self-tuning against the seller's own catalogue: "smart" and "watch" sit in
    several names so they identify nothing, while "zeblace" and "aspor" sit in
    one. No word list to maintain - the catalogue decides.
    """
    # Words that name a category identify a kind of product, not a particular
    # one. In a shop with a single earbud, "earbuds" is unique to it - so "we
    # have several earbuds" would have pulled up its card as though the
    # sentence had named it.
    category_words = set()

    for product in products:
        category_words |= message_word_alias_set(product.get("categoryName", ""))

    owners = {}

    for product in products:
        for word in message_word_alias_set(product.get("name", "")):
            if len(word) > 2 and word not in category_words:
                owners.setdefault(word, set()).add(product.get("id"))

    named = {
        next(iter(owners[word]))
        for word in message_words
        if len(owners.get(word, ())) == 1
    }

    return [product for product in products if product.get("id") in named]


# Words that carry no identity in a product name, so their absence from an
# answer says nothing about whether that product was meant.
NAME_FILLER_WORDS = {"the", "a", "an", "and", "with", "for", "of", "in", "new"}


def squashed(value):
    """Letters and digits only, lowercased - punctuation and spacing removed.

    Long enough to be safe: an eight-character run of a product's own name is
    not going to appear inside an unrelated answer by chance.
    """
    return "".join(
        character
        for character in str(value or "").casefold()
        if character.isalnum()
    )


def name_appears_in(name, text, answer_words):
    """True when an answer names this product, allowing for natural phrasing.

    Every part bearing a digit - "R60i", "EZ10", "A337", "20000mah" - must be
    present: those are what separate one model from the next, and matching
    without them would put a sibling product's card under the answer. The rest
    only needs a majority, which absorbs a dropped trailing word like
    "Earbuds" or a "The" the seller typed and the model did not.
    """
    # Punctuation-blind first. A model writes "P-08B" with a non-breaking
    # hyphen and "10000mAh" as "10,000 mAh", so no token of the catalogue name
    # survives intact - the whole name is there, spelled the way a person
    # would. Squashing both sides to letters and digits sees it.
    squashed_name = squashed(name)

    if len(squashed_name) > 7 and squashed_name in squashed(text):
        return True

    words = [
        word
        for word in word_characters(str(name)).casefold().split()
        if word not in NAME_FILLER_WORDS
    ]

    if not words:
        return False

    # The exact name still counts, however it is worded around. Padded so the
    # comparison lands on whole words: as a bare substring test, a product
    # called "Pro" matched inside "professional".
    if f" {' '.join(words)} " in f" {text} ":
        return True

    # A model code mixes letters and digits - "R60i", "EZ10", "A337",
    # "10000mah". A bare number does not: the "6" in "Redmi buds 6 play"
    # identifies nothing on its own and appears in half the answers written.
    model_words = [
        word
        for word in words
        if any(letter.isdigit() for letter in word)
        and any(letter.isalpha() for letter in word)
    ]
    matched = [word for word in words if word in answer_words]

    if model_words:
        # The code pins the model; one more word confirms it is this seller's
        # product and not a number quoted from somewhere else in the sentence.
        return all(word in answer_words for word in model_words) and len(
            matched,
        ) > len(model_words)

    # No code to rely on, so the name itself has to be mostly present. Two
    # thirds absorbs a dropped trailing word without letting "buds" alone
    # claim every earbud in the catalogue.
    return len(matched) * 3 >= len(words) * 2


def message_word_alias_set(message):
    """Words the customer typed, with singular and plural forms of each.

    Matching a name against these keeps it a whole-word match. Substring
    matching once made "show" resolve to the "Shoes" category.
    """
    words = message_tokens(message)
    aliases = set(words)

    for word in words:
        if word.endswith("s"):
            aliases.add(word[:-1])
        if word.endswith("es"):
            aliases.add(word[:-2])

    return aliases


def message_phrase_aliases(message, sizes=(2, 3)):
    """Joined runs of consecutive words, so "power bank" matches "Powerbanks"."""
    words = word_characters(message).split()
    joined = {
        "".join(words[start:start + size])
        for size in sizes
        for start in range(len(words) - size + 1)
    }

    # Singular forms too: "smart watches" joins to "smartwatches", which must
    # still match a category stored as "Smart watch".
    aliases = set(joined)
    for phrase in joined:
        if phrase.endswith("es"):
            aliases.add(phrase[:-2])
        if phrase.endswith("s"):
            aliases.add(phrase[:-1])

    return aliases


# Words that lead a product name often enough to look like a brand, but that a
# customer types when asking to see the shop rather than naming a maker. A
# catalogue of "Product 1", "Product 2" would otherwise answer "show products"
# with "here is what we have from Product".
NEVER_A_BRAND = {"product", "products", "item", "items", "new", "the"}


def find_brand_request(message, products):
    """Return the brand named in a message, if this seller carries it.

    Customers shop by brand as readily as by category - "show me Lenovo
    products", "any Baseus earbuds". Without this the message matched no
    product name and no category, so it fell through to the category picker
    and the brand was ignored entirely.
    """
    words = message_word_alias_set(message)
    phrases = message_phrase_aliases(message)
    brands = {
        product.get("brand", "").strip()
        for product in products
        if product.get("brand", "").strip()
    } | implied_brands(products)

    for brand in sorted(brands, key=len, reverse=True):
        aliases = {normalized_phrase(brand)}
        if aliases & (words | phrases):
            return brand

    return None


def implied_brands(products):
    """Brands sellers never typed into the brand field, read off the names.

    The field is optional and most sellers skip it, so "Lenovo" existed only
    inside "Lenovo GM 2 pro". Brand requests then matched nothing and the
    customer got the whole catalogue instead of that brand.

    A leading word counts only when two or more products share it. One product
    already resolves by its own name, so nothing is lost by requiring two.

    Products sharing the second word too are a descriptive phrase, not a
    brand: "Fast Charge Power Bank" and "Fast Charge Cable" would otherwise
    make "Fast" a brand, and "is delivery fast?" would answer with a product
    list. Real brands are followed by different model names.
    """
    leading_words = {}

    for product in products:
        words = str(product.get("name", "")).split()

        if not words:
            continue

        entry = leading_words.setdefault(words[0].strip(), {"ids": set(), "seconds": set()})
        entry["ids"].add(product.get("id"))
        entry["seconds"].add(words[1].casefold() if len(words) > 1 else "")

    return {
        word
        for word, entry in leading_words.items()
        if word
        and word.casefold() not in NEVER_A_BRAND
        and len(entry["ids"]) > 1
        and len(entry["seconds"]) > 1
    }


def brand_products(products, brand, excluded_product_id=None):
    """Every product of a brand, whether the seller recorded it or not.

    Matching the brand field alone returned nothing for the brands read off
    product names, so the request was recognised and then answered with an
    empty list.
    """
    wanted = str(brand).strip().casefold()

    return [
        product
        for product in products
        if (
            product.get("brand", "").strip().casefold() == wanted
            or str(product.get("name", "")).strip().casefold().startswith(
                f"{wanted} ",
            )
        )
        and product.get("id") != excluded_product_id
    ]


def message_is_only_a_product_name(message, product):
    """True when the customer typed a product name and nothing else.

    "lenovo gm2 pro" is a request to see that product, not an instruction to
    order it. The classifier reads a bare product name as start_order, which
    sent the customer straight to "how many would you like?" before they had
    seen the price, the specs or a photo.
    """
    if not product:
        return False

    words = message_tokens(message)

    if not words:
        return False

    return words <= message_tokens(product.get("name", ""))


def seller_contact_message(business):
    """The handoff line for a question the catalogue cannot answer.

    "We don't have that information" is a dead end, and a dead end is what
    sends a customer to a competitor. The seller has already been notified, so
    tell the customer that, and give them a way to reach a person now if they
    do not want to wait.

    The WhatsApp link is derived from the published phone number rather than
    being a second field to keep in step.
    """
    phone = str(business.get("phone") or "").strip()

    if not phone:
        return "One of our agents will contact you shortly about this."

    try:
        whatsapp = normalize_sri_lankan_phone(phone)
    except ValueError:
        whatsapp = ""

    parts = [
        "One of our agents will contact you shortly about this.",
        f"If you are in a hurry you can call {phone}",
    ]

    if whatsapp:
        parts[-1] += f" or message us on WhatsApp: https://wa.me/{whatsapp}"

    return " ".join(parts) + "."


PRICE_CONSTRAINT_PATTERN = re.compile(
    r"(?:below|under|less than|cheaper than|up to|within|max|maximum|"
    r"above|over|more than|between|"
    r"හා|අතර|අඩු|කුඩා|ගත|"
    r"rs\.?|lkr|රු\.?)\s*[\d,]{3,}|[\d,]{3,}\s*(?:rs\.?|lkr|රු\.?|කින්)",
    re.IGNORECASE,
)


def has_price_constraint(message):
    """Spot "below Rs 2000", "under 5000", "anything up to 3000".

    A price filter is not a browse request, even though it usually starts with
    "show me". Left to the catalogue branch it produced the category picker
    instead of the products that actually fit the budget.
    """
    return bool(PRICE_CONSTRAINT_PATTERN.search(str(message)))


REFERS_TO_SHOWN_PHRASES = (
    "these", "those", "both", "among them", "of them", "any of these",
    "meken", "මේවා", "මේකෙන්", "දෙකම", "இவை", "இரண்டும்",
    # Sinhala points at a list by counting it: "me hatharen" is "out of these
    # four", "me deken" is "out of these two". Without these the question was
    # scoped by whatever category happened to be remembered instead of by what
    # the customer was actually looking at.
    "me hatharen", "mehatharen", "hatharen", "me deken", "medeken", "deken",
    "me tunen", "tunen", "me paheN", "pahen", "meyin", "meva", "mewa",
    "mekenma", "me okkoma", "okkoma",
    "මේ හතරෙන්", "හතරෙන්", "මේ දෙකෙන්", "දෙකෙන්", "තුනෙන්", "මේයින්",
    "ඔක්කොම", "මේ ඔක්කොම",
    "இவற்றில்", "ivatril", "ivarril", "இதில்",
)


def refers_to_shown_products(message):
    """True when the question is about the products currently on screen."""
    return any(
        phrase in str(message).casefold() for phrase in REFERS_TO_SHOWN_PHRASES
    )


def products_by_ids(products, ids):
    wanted = list(ids or [])
    return [product for product in products if product.get("id") in wanted]



# Words that carry no feature meaning, so what remains after removing them and
# the category name is what the customer is actually filtering on.
FEATURE_STOP_WORDS = {
    "send", "show", "give", "me", "us", "my", "i", "want", "need", "looking",
    "for", "with", "have", "having", "has", "that", "which", "the", "a", "an",
    "any", "some", "all", "of", "and", "or", "is", "are", "do", "you", "your",
    "please", "product", "products", "item", "items", "one", "ones", "thing",
    "get", "find", "see", "list", "under", "in", "on", "at", "to", "can",
    # Words that frame a question rather than describe a product. "I meant are
    # there watches with sim support" filtered on "meant" and "support" as
    # though they were features, so the reply read "Smart watch with meant sim
    # support" and matched nothing.
    "meant", "mean", "means", "actually", "sorry", "want", "wanted", "need",
    "needed", "asking", "ask", "tell", "know", "support", "supports",
    "supported", "feature", "features", "facility", "wondering", "maybe",
    "there", "it", "this", "these", "those", "only", "also", "like", "good",
    # Sinhala and Tamil carry the request in words the customer types in Latin
    # letters. Left in, "sim danna puluwan" filtered on "danna" and "puluwan"
    # as though they were features, so nothing could ever match.
    "ekak", "ona", "oni", "one", "mata", "mage", "api", "oyage",
    "thiyenawada", "thiyenawa", "thiyenne", "tiyenawada", "nadda", "natha",
    "nathi", "naha", "danna", "denna", "puluwan", "puluwanda", "ewa", "eka",
    "ewanna", "evanna", "pennanna", "balanna", "hoyanna", "karanna", "tikak",
    "wage", "saha", "harida", "kiyanna", "monawada", "mokakda", "kohomada",
    "irukka", "irukku", "anuppu", "venum", "kaattu", "enna",
    "තියෙනවද", "තියෙනවා", "නැද්ද", "නැහැ", "දාන්න", "දෙන්න", "පුළුවන්",
    "එවන්න", "පෙන්නන්න", "බලන්න", "ඕන", "ඕනේ", "මට", "එකක්", "මොනවද",
    "இருக்கா", "அனுப்பு", "காட்டு", "வேண்டும்", "எனக்கு",
}

# A customer says "waterproof"; the seller writes "IP68" or "water resistant".
# Matching the exact word alone found nothing and reported that no product had
# a feature the seller had described in different words.
FEATURE_SYNONYMS = {
    "waterproof": ("waterproof", "water resistant", "water-resistant", "ip67", "ip68", "ipx7", "ipx8", "splash"),
    "water": ("waterproof", "water resistant", "water-resistant", "ip67", "ip68", "ipx", "splash"),
    "resistant": ("resistant", "resistance", "proof"),
    "bluetooth": ("bluetooth", "wireless"),
    "wireless": ("wireless", "bluetooth"),
    "calling": ("calling", "call", "bluetooth calling", "phone call"),
    "gaming": ("gaming", "game", "low latency"),
    "noise": ("noise", "anc", "noise cancelling", "noise cancellation"),
    "anc": ("anc", "noise cancelling", "noise cancellation"),
    "fast": ("fast", "quick", "rapid"),
    "charging": ("charging", "charge", "charger"),
    "amoled": ("amoled", "oled"),
    "sim": ("sim", "sim slot", "sim card"),
    "battery": ("battery", "mah"),
    "warranty": ("warranty", "guarantee"),
}


def feature_terms(message, category_name):
    """The feature words left once the request and the category are removed.

    "send me smart watches with water resistant" is a category request AND a
    filter. Reading only the category answered it with every smart watch,
    including the ones without the feature the customer asked for.
    """
    # Plural and singular both, so the "watches" of "smart watches" is
    # recognised as part of the category "Smart watch" rather than surviving as
    # a feature the customer never asked for.
    category_words = message_word_alias_set(str(category_name or ""))
    # Sellers write compounds as one word ("PowerBanks") and customers type
    # them as two ("power banks"). Word matching alone left both halves behind
    # as features nothing could satisfy.
    category_collapsed = normalized_phrase(str(category_name or ""))

    def belongs_to_category(word):
        if message_word_alias_set(word) & category_words:
            return True

        # Only for words that could be part of a name. A capacity like
        # "20000mah" must never be absorbed into the category.
        if any(letter.isdigit() for letter in word):
            return False

        return bool(category_collapsed) and (
            word.rstrip("s") in category_collapsed
            or category_collapsed in word
        )

    return [
        word
        for word in word_characters(str(message or "")).casefold().split()
        if word not in FEATURE_STOP_WORDS
        and len(word) > 1
        and not belongs_to_category(word)
    ]


# A description that says "No SIM slot" contains the word "sim". Reading that
# as support is the worst kind of wrong answer - the customer buys the wrong
# product on the strength of it.
FEATURE_NEGATIONS = (
    "no ", "not ", "non ", "without ", "lacks ", "does not ", "doesn't ",
    "unsupported", "unavailable",
)


def mention_is_negated(haystack, position):
    """True when the text just before a mention denies it."""
    window = haystack[max(0, position - 24):position]
    return any(negation in window for negation in FEATURE_NEGATIONS)


def product_mentions_feature(product, term):
    """True when this product's own text describes the feature asked for."""
    haystack = " ".join(
        str(product.get(field, "") or "")
        for field in ("name", "description", "aiDescription", "productSize", "brand")
    ).casefold()

    for candidate in FEATURE_SYNONYMS.get(term, (term,)):
        position = haystack.find(candidate)

        while position != -1:
            if not mention_is_negated(haystack, position):
                return True

            position = haystack.find(candidate, position + 1)

    return False


def shared_category_name(products):
    """The category these products have in common, if they share one."""
    names = {
        product.get("categoryName", "")
        for product in products
        if product.get("categoryName")
    }
    return names.pop() if len(names) == 1 else ""


def products_with_features(products, terms):
    """Products whose descriptions cover every feature word the customer used.

    Deterministic on purpose: the seller's text either contains the feature or
    it does not, and reading it here costs nothing and cannot hallucinate. The
    model is only worth calling when this finds nothing, in case the seller
    described the feature in words this does not know.
    """
    if not terms:
        return []

    return [
        product
        for product in products
        if all(product_mentions_feature(product, term) for term in terms)
    ]


def comparison_table(products):
    """Build a spec table from stored facts, with no AI call.

    The model is the better comparer, but it is not always available - the free
    provider tier runs out of tokens per minute. Falling through left the
    customer with no answer at all, when the seller's own data already covers
    price, warranty and stock.
    """
    if len(products) < 2:
        return ""

    rows = [
        ("Price", [money_text(item.get("sellingPriceMinor", 0)) for item in products]),
        (
            "Warranty",
            [
                f"{item['warrantyPeriodMonths']} months"
                if item.get("warrantyPeriodMonths")
                else "-"
                for item in products
            ],
        ),
        (
            "Availability",
            [
                f"{item.get('availableStock', 0)} in stock"
                if item.get("availableStock", 0) > 0
                else "Out of stock"
                for item in products
            ],
        ),
        ("Brand", [item.get("brand") or "-" for item in products]),
    ]
    rows = [(label, values) for label, values in rows if any(v != "-" for v in values)]
    names = [item.get("name", "") for item in products]
    lines = [
        "| Spec | " + " | ".join(names) + " |",
        "|" + "---|" * (len(names) + 1),
    ]
    lines += ["| " + label + " | " + " | ".join(values) + " |" for label, values in rows]

    cheapest = min(products, key=lambda item: item.get("sellingPriceMinor", 0))
    return (
        "Here is how they compare:\n\n"
        + "\n".join(lines)
        + f"\n\n{cheapest.get('name', '')} is the lowest priced. "
        "Tell me which one you would like, or ask about any spec."
    )


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

    # One shared word is not an identification. "How long does it take to
    # charge" overlaps "Fast Charge Power Bank" on "charge" alone, which
    # selected the wrong product and made a feature question look like a
    # request for that product's full details. A single-word match only counts
    # when the message is essentially just that word.
    if highest_score < 2 and len(customer_tokens) > 2:
        return []

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


def find_category_request(message, products, require_cue=True):
    """Resolve an explicit request for a whole product category."""
    clean_message = str(message).strip().casefold()
    compact_message = normalized_phrase(clean_message)
    category_cues = {"show", "list", "all", "category", "categories", "have"}
    message_words = message_tokens(clean_message)
    # Singular and plural forms of what the customer actually typed, so a
    # category alias has to match a whole word rather than any run of letters.
    message_word_aliases = message_word_alias_set(clean_message)
    categories = {
        product.get("categoryName", "").strip()
        for product in products
        if product.get("categoryName", "").strip()
    }

    phrase_aliases = message_phrase_aliases(clean_message)

    for category in categories:
        compact_category = normalized_phrase(category)
        category_aliases = {compact_category}
        if compact_category.endswith("s"):
            category_aliases.add(compact_category[:-1])
        if compact_category.endswith("es"):
            category_aliases.add(compact_category[:-2])
        category_words = message_tokens(category)
        exact_category = compact_message in category_aliases
        # Match whole words, not substrings of the squashed message. Stripping
        # "es" off "Shoes" leaves the stub "sho", which is inside "show" - so
        # "show products" resolved to the Shoes category.
        # A category written as one token ("Powerbanks") is often typed as two
        # ("power bank"), so joined runs of consecutive words are compared too.
        # This keeps whole-word matching - unlike substring matching, which
        # made "show" resolve to the Shoes category.
        category_is_named = bool(category_aliases & message_word_aliases) or bool(
            category_aliases & phrase_aliases
        ) or (
            bool(category_words) and category_words.issubset(message_words)
        ) or (
            # A distinctive word is enough when it points at one category and
            # one only. Requiring every word meant "routers" could not reach
            # "Routers and modems" and "watches" could not reach "Smart watch"
            # - the customer has to type the seller's exact wording or get
            # nothing. Uniqueness is what keeps this from guessing.
            category == unique_category_for(message, products)
        )
        has_category_cue = bool(category_cues & message_words)

        # On the ordering path the intent is already known, so naming the
        # category is enough - "I want to order a powerbank" carries no
        # "show"/"list" cue and used to fall through to the whole catalogue.
        if exact_category or (category_is_named and (has_category_cue or not require_cue)):
            return category

    return None


# Words that appear in so many category names they identify nothing on their
# own. "smart" matches Smart watch and a smart bulb; "power" matches PowerBanks
# and a power cable.
WEAK_CATEGORY_WORDS = {"smart", "power", "wireless", "mini", "pro", "new", "and"}


def unique_category_for(message, products):
    """The single category a distinctive word in the message points at.

    Shared by the matcher and the "did you mean" fallback, so a word that is
    good enough to ask about is good enough to act on when nothing else
    matched.
    """
    message_words = message_word_alias_set(message)
    candidates = set()

    for product in products:
        category = product.get("categoryName", "").strip()

        if not category:
            continue

        distinctive = {
            word
            for word in message_word_alias_set(category)
            if word not in WEAK_CATEGORY_WORDS and len(word) > 2
        }

        if distinctive & message_words:
            candidates.add(category)

    return candidates.pop() if len(candidates) == 1 else None


def closest_category(message, products):
    """The one category a half-named request is probably reaching for.

    "watches" does not match "Smart watch": the matcher needs every word of the
    category, and rightly so - a partial match is a guess. But a guess offered
    as a question costs nothing, while "I did not catch which product you
    meant" ends the conversation.

    Returns a category only when exactly one is a candidate. Two candidates
    means the guess would be a coin flip, and the customer is better served by
    the category list.
    """
    return unique_category_for(message, products)


def closest_product(message, products):
    """The one product a half-remembered name is probably reaching for.

    Model codes carry the identity - "aspor a337", "gm2" - so a message sharing
    one with exactly one product is almost certainly about it, even when the
    rest of the name is wrong or missing.
    """
    message_words = message_word_alias_set(message)
    candidates = [
        product
        for product in products
        if any(
            any(letter.isdigit() for letter in word)
            and any(letter.isalpha() for letter in word)
            and word in message_words
            for word in message_word_alias_set(product.get("name", ""))
        )
    ]

    return candidates[0] if len(candidates) == 1 else None


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
    # A cross-sell should reach beyond the shelf they are already looking at,
    # so at least a third of the strip comes from other categories when they
    # exist. All same-category made it a duplicate of the listing above it.
    # A cross-sell should reach past the shelf they are already looking at, so
    # a slot or two is reserved for other categories when any exist. All
    # same-category made the strip a duplicate of the listing above it.
    reserved = min(len(other_products), max(1, limit // 3)) if other_products else 0
    picked = same_category[: limit - reserved] + other_products[:reserved]

    # Backfill if either side ran short, without repeating anything.
    for product in same_category + other_products:
        if len(picked) >= limit:
            break
        if product not in picked:
            picked.append(product)

    return picked[:limit]


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


DELIVERY_TIME_PHRASES = (
    "how long",
    "how many days",
    "how soon",
    "delivery time",
    "delivery days",
    "when will i get",
    "when will it",
    "kochchara kalak",
    "koccara kalak",
    "kiyaa dawasak",
    "kiya dawasak",
    "කොනතරු",
    "දවස්",
    "කාලයක්",
    "எத்தனை நாட்",
    "எவ்வளவு நாள்",
)


def is_delivery_time_question(message):
    """Recognise "how long will it take", the other half of every delivery ask.

    Sellers configure averageDeliveryDays per courier and it is snapshotted
    onto every order, but it was never shown to a customer - so the most common
    pre-purchase question after price had no answer at all.
    """
    text = str(message).casefold()

    if not any(phrase in text for phrase in DELIVERY_TIME_PHRASES):
        return False

    return any(
        word in text
        for word in (
            "deliver",
            "delivery",
            "shipping",
            "courier",
            "arrive",
            "order",
            "ලැබෙ",
            "යව",
            "ඩෙලිවරි",
            "டெலிவரி",
            "வர",
        )
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


def cart_contents_message(cart_summary):
    """List what is in the cart, priced, so "show my cart" has a real answer."""
    if not cart_summary:
        return (
            "Your cart is empty at the moment. Tell me what you are looking "
            "for and I will show you what we have."
        )

    lines = [
        f"- {item['quantity']} x {item['productName']}"
        + (f" ({item['size']})" if item["size"] else "")
        + f" - LKR {item['lineTotalMinor'] / 100:,.2f}"
        for item in cart_summary
    ]
    subtotal = sum(item["lineTotalMinor"] for item in cart_summary)

    return (
        "Here is what is in your cart:\n"
        + "\n".join(lines)
        + f"\nItems total: LKR {subtotal / 100:,.2f} (delivery is added once "
        "I know your district). Anything else, or shall we continue?"
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
        "averageDeliveryDays": courier.get("averageDeliveryDays", 0),
        "firstKgPriceMinor": district_first_kg_price(
            courier,
            normalize_district(district),
        ),
        "extraKgPriceMinor": courier.get("extraKgPriceMinor", 0),
        "weightGrams": quoted_weight,
        "isEstimate": not weight_grams,
        "deliveryFeeMinor": best["deliveryFeeMinor"],
    }


def delivery_quote_message(quote, asked_about_time=False):
    """Explain the district price and the extra-kilogram rate that built it.

    `asked_about_time` puts the days first. The customer who asked how long it
    takes should not have to read a price breakdown to reach their answer.
    """
    courier_text = f" with {quote['courierName']}" if quote.get("courierName") else ""
    days = quote.get("averageDeliveryDays") or 0

    if asked_about_time:
        lead = (
            f"{quote['courierName'] or 'The courier'} usually delivers to "
            f"{quote['district']} in about {days} working "
            f"{'day' if days == 1 else 'days'}."
            if days
            else f"The seller has not recorded a delivery time for "
            f"{quote['district']} yet, so I do not want to guess at one."
        )
        price = (
            f"Delivery there is LKR {quote['firstKgPriceMinor'] / 100:,.2f} for "
            f"the first 1 kg, plus LKR {quote['extraKgPriceMinor'] / 100:,.2f} "
            "for each extra 1 kg."
        )
        return f"{lead} {price}"

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

    # "When will it come?" is the question that follows "how much?" every time.
    if days:
        parts.append(
            f"{quote['courierName'] or 'The courier'} usually delivers to "
            f"{quote['district']} in about {days} working "
            f"{'day' if days == 1 else 'days'}.",
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

    # The greeting is written before the customer has said anything, so there is
    # nothing to detect a language from. A returning visitor's browser sends the
    # language it settled on last time; a first-time visitor gets a short
    # trilingual line, which is what Sri Lankan shops actually do, rather than
    # an English wall.
    requested = str(payload.get("language") or "").strip().casefold()
    greeting_language = requested if requested in GREETING_LANGUAGES else ""
    english_greeting = (
        f"Welcome to {business['name']}. What would you like to know about "
        f"{product['name']}?"
        if product
        else f"Welcome to {business['name']}. What product would you like to know about?"
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
            # A returning visitor's browser supplies this; otherwise the first
            # customer message settles it.
            "language": greeting_language or "en",
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

    if greeting_language in {"si", "ta"}:
        greeting = translate_chat_message(english_greeting, greeting_language)
    elif greeting_language == "en":
        greeting = english_greeting
    else:
        greeting = (
            f"Welcome to {business['name']}. How can I help you today? "
            "සිංහලෙන් හෝ தமிழில் கேட்கலாம්."
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


# How much of the conversation the model is shown. Sent as real chat turns, so
# this is the same thing ChatGPT does - twelve covers a browse, a couple of
# questions and a follow-up without the oldest topic outweighing the current
# one. Roughly 700 tokens at the cap, which the small classification model
# absorbs cheaply.
CONVERSATION_MEMORY_TURNS = 12

# Long enough for a real question or a short answer. A full product answer is
# truncated rather than dropped: what it referred to survives, which is all the
# next turn needs.
CONVERSATION_MEMORY_CHARS = 400


def remembered_turns(session):
    """The recent conversation, oldest first, for the model to read."""
    return list(session.get("recentTurns") or [])[-CONVERSATION_MEMORY_TURNS:]


def save_chat_message(session_reference, role, message, metadata=None, session=None):
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

    # A rolling window of the conversation, kept on the session so a follow-up
    # can be answered without reading the whole message subcollection back on
    # every turn. Written as a whole list rather than appended: ArrayUnion
    # deduplicates, and a conversation is full of repeated turns - "skip",
    # "2", "yes" - which would silently vanish from the history.
    if session is not None:
        turns = list(session.get("recentTurns") or [])
        turns.append(
            {"role": role, "text": str(message or "")[:CONVERSATION_MEMORY_CHARS]},
        )
        turns = turns[-CONVERSATION_MEMORY_TURNS:]
        # The in-memory session is read again later in the same request, so it
        # has to agree with what was just written.
        session["recentTurns"] = turns
        session_changes["recentTurns"] = turns
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

    # Captured before this message joins the window: the model is given the
    # turns BEFORE the one it is answering, and the current message separately.
    # Including it twice makes the prompt read as though it was asked twice.
    conversation_history = remembered_turns(session)
    save_chat_message(
        session_snapshot.reference,
        "customer",
        message,
        session=session,
    )

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
    ai_intent = storefront_intent(
        message,
        products,
        current_state,
        conversation_history,
    )
    # The seller finds out here. This is the only place that knows both that a
    # provider call was just attempted and which business it was for.
    sync_ai_failure_notification(database, session["businessId"], ai_status())
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
        response_categories=None,
        review_summary=None,
        seller_rating=None,
        selected_product_id="unchanged",
        pending_variant_id="unchanged",
        is_translated=False,
        accumulate_seen=False,
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
            session=session,
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

        # "What is the best one?" names nothing. Without this the catalogue
        # answer saw every product and replied about a router while the
        # customer was looking at smart watches.
        shown_category = next(
            (
                item.get("categoryName")
                for item in (response_products or [])
                if item.get("categoryName")
            ),
            None,
        )
        if shown_category:
            changes["lastCategoryShown"] = shown_category

        # "Which of these two is better?" refers to what is on screen. Only
        # the category was remembered, so the question reached the generic
        # fallback and the customer was asked what they were looking for.
        if response_products:
            changes["lastShownProductIds"] = [
                item["id"] for item in response_products if item.get("id")
            ][:MAX_REMEMBERED_PRODUCTS]

            # "Show me more" must return what was left out. A fresh listing
            # restarts the page; only the more-branch adds to it.
            shown_ids = [item["id"] for item in response_products if item.get("id")]
            changes["seenProductIds"] = (
                (session.get("seenProductIds") or []) + shown_ids
                if accumulate_seen
                else shown_ids
            )[:MAX_SEEN_PRODUCTS]
        elif product and product.get("categoryName"):
            changes["lastCategoryShown"] = product["categoryName"]

        if pending_variant_id != "unchanged":
            changes["pendingVariantId"] = pending_variant_id or ""

        session_snapshot.reference.update(changes)
        return {
            "message": localized_message,
            "language": language,
            "action": action,
            "state": state,
            "suggestions": chat_suggestions(
                action,
                state,
                bool(cart_summary),
                bool(session.get("orderId")),
                len(response_products or []),
            ),
            "product": product,
            "products": response_products or [],
            "reviews": response_reviews or [],
            "categories": response_categories or [],
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
            + (f" ({variant["size"]})" if variant.get("size") else "")
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
            response_products=(
                products[:MAX_RESPONSE_PRODUCTS] if not cart_summary else []
            ),
        )

    if current_state == "clarifying-scope":
        pending = session.get("pendingBudgetQuestion", "")
        wants_everything = any(
            phrase in lowered_message
            for phrase in ("any", "all", "everything", "whole", "සියලු", "எல்லா")
        )
        chosen = None if wants_everything else (
            find_category_request(message, products, require_cue=False)
            or session.get("lastCategoryShown")
        )
        scope = category_products(products, chosen) if chosen else products
        answer = generate_catalogue_answer(
            f"{pending} {message}".strip(),
            scope or products,
            language,
            catalog["business"].get("storefrontFaq", ""),
            conversation_history,
        )
        session_snapshot.reference.set({"pendingBudgetQuestion": ""}, merge=True)

        if answer:
            for marker in (MISSING_FACT_MARKER, ANSWERED_MARKER):
                answer = answer.replace(marker, "")
            named = products_named_in(answer, scope or products)
            return respond(
                answer.strip(),
                "show-category",
                next_state="browsing",
                response_products=named[:MAX_RESPONSE_PRODUCTS],
                is_translated=True,
            )

        current_state = "browsing"


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
        or is_delivery_time_question(message)
        or intent_is("delivery_quote")
    ):
        draft_address = customer_draft.get("address") or {}
        district = named_district or draft_address.get("district", "")

        # Which of the two they actually asked, remembered across the district
        # question. Answering "how long does delivery take" with a price, twice
        # in a row, reads as not listening - the question was never registered.
        if is_delivery_time_question(message) and not is_delivery_fee_question(
            message,
        ):
            customer_draft["deliveryQuestion"] = "time"
        elif is_delivery_fee_question(message) or intent_is("delivery_quote"):
            customer_draft.setdefault("deliveryQuestion", "fee")

        asked_about_time = customer_draft.get("deliveryQuestion") == "time"

        if not district:
            return respond(
                "Which district should we deliver to? I will check "
                + (
                    "how long delivery takes to that district."
                    if asked_about_time
                    else "the exact delivery fee for that district."
                ),
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
            delivery_quote_message(quote, asked_about_time),
            "show-delivery-quote",
            next_state="browsing",
        )

    # Once an order is submitted, normal conversation stays attached to that
    # order. Do not treat "ok", "thanks" or a status question as a brand-new
    # shopping session. A new catalogue is shown only when the customer clearly
    # asks to place another order.
    # A guest who ordered and came back later has no session link to that order.
    # Naming its number starts a phone check, which is the only thing standing
    # between a guessed order number and someone else's delivery address.
    named_order_number = order_number_in_message(message)

    if current_state == "verifying-order":
        pending_order_number = session.get("pendingOrderNumber", "")
        attempts = int(session.get("orderVerificationAttempts", 0)) + 1

        if named_order_number and named_order_number != pending_order_number:
            # They corrected the number rather than answering with a phone.
            pending_order_number = named_order_number
            attempts = 0

        verified_order = find_order_by_number(
            database,
            session["businessId"],
            pending_order_number,
            message,
        )

        if verified_order:
            session_snapshot.reference.set(
                {
                    "orderId": verified_order["id"],
                    # Without this the order leaves the notification list as
                    # soon as a newer one replaces `orderId`, and its status
                    # updates stop reaching the chat.
                    "orderIds": firestore.ArrayUnion([verified_order["id"]]),
                    "pendingOrderNumber": "",
                    "orderVerificationAttempts": 0,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            return respond(
                order_information_message(verified_order),
                "show-order-info",
                next_state="completed",
            )

        if attempts >= MAX_ORDER_VERIFICATION_ATTEMPTS:
            session_snapshot.reference.set(
                {"pendingOrderNumber": "", "orderVerificationAttempts": 0},
                merge=True,
            )
            return respond(
                "I could not verify that order. Please contact the seller "
                "directly so they can check it for you.",
                "show-order-info",
                next_state="browsing",
            )

        session_snapshot.reference.set(
            {
                "pendingOrderNumber": pending_order_number,
                "orderVerificationAttempts": attempts,
            },
            merge=True,
        )
        # One message for "no such order" and for "wrong phone", so the reply
        # cannot be used to discover which order numbers exist.
        return respond(
            f"I could not match that to order {pending_order_number}. Please "
            "send the mobile number used to place it, for example 077 123 4567.",
            "collect-order-phone",
            next_state="verifying-order",
        )

    if named_order_number:
        # An order this session placed needs no re-verification. Without this
        # the customer could only ever ask about their newest order.
        owned_order = session_order_by_number(database, session, named_order_number)

        # Sessions written before `orderIds` existed carry only the single
        # linked order, and it is not in the list to be found.
        if not owned_order and session.get("orderId"):
            linked_order = latest_order_for_session(database, session)

            if linked_order and str(
                linked_order.get("orderNumber", ""),
            ).casefold() == named_order_number.casefold():
                owned_order = linked_order

        if owned_order:
            return respond(
                order_information_message(owned_order),
                "show-order-info",
                next_state="completed",
            )

        # Anything else is someone else's number until the phone matches.
        session_snapshot.reference.set(
            {
                "pendingOrderNumber": named_order_number,
                "orderVerificationAttempts": 0,
            },
            merge=True,
        )
        return respond(
            f"I can check order {named_order_number} for you. Which mobile "
            "number was used to place it?",
            "collect-order-phone",
            next_state="verifying-order",
        )

    # Cancelling is irreversible and releases stock, so it needs the customer's
    # own order, an explicit confirmation, and a status the seller's own rules
    # still allow. Only a session that already proved ownership - by placing the
    # order or by passing the phone check - can reach this.
    if current_state == "confirming-cancel":
        cancel_order = latest_order_for_session(database, session)
        confirms_cancel = intent_is("confirm_order") or bool(
            set(word_characters(lowered_message).split())
            & {"yes", "confirm", "cancel", "ow", "ඔව්", "හරි", "ஆம்", "சரி"}
        )

        if not cancel_order:
            return respond(
                "I could not find that order any more. Please contact the "
                "seller so they can check it.",
                "show-order-info",
                next_state="completed",
            )

        if not confirms_cancel:
            return respond(
                f"Order {cancel_order.get('orderNumber', '')} has not been "
                "cancelled. Tell me if there is anything else I can help with.",
                "show-order-info",
                next_state="completed",
            )

        try:
            update_order_status(
                database,
                session["businessId"],
                cancel_order["id"],
                f"public-chat:{session_id}",
                {
                    "status": "cancelled",
                    "note": "Cancelled by the customer in the storefront chat.",
                },
            )
        except ApiError:
            # Most likely it was dispatched between the question and the answer.
            notify_seller_attention(
                database,
                session_snapshot.reference,
                session["businessId"],
                f"Customer asked to cancel {cancel_order.get('orderNumber', '')}",
            )
            return respond(
                f"I could not cancel order {cancel_order.get('orderNumber', '')} "
                "because it has already moved on. I have told the seller, and "
                "they will contact you.",
                "show-order-info",
                next_state="completed",
            )

        # The seller has stock to put back on the shelf and may want to follow
        # up, so this is never a silent change.
        notify_seller_attention(
            database,
            session_snapshot.reference,
            session["businessId"],
            f"Customer cancelled {cancel_order.get('orderNumber', '')} in chat",
        )
        return respond(
            f"Order {cancel_order.get('orderNumber', '')} has been cancelled "
            "and the items are back in stock. Would you like to order something "
            "else?",
            "show-order-info",
            next_state="completed",
        )

    # A customer who wants out must not be trapped by the question. Cancelling
    # falls through to the handler below rather than being re-asked how they
    # would like to pay for an order they are trying to abandon.
    wants_to_cancel = is_cancel_order_request(message) or intent_is("cancel_order")

    # "Cancel my order" while a draft is open means "do not place this one".
    # `orderId` stays set forever after a customer's first order, so keying off
    # it alone offered to cancel a delivered order while they were still
    # choosing items - the opposite of what was asked.
    has_open_draft = bool(cart_summary) or current_state in DRAFT_IN_PROGRESS_STATES

    if wants_to_cancel and has_open_draft:
        cart = []
        cart_summary = []
        customer_draft = {}
        placed_order_hint = (
            " Your earlier order is not affected - tell me its number if you "
            "want to change that one."
            if session.get("orderId")
            else ""
        )
        return respond(
            "I have cleared the items you were choosing, so nothing has been "
            f"ordered.{placed_order_hint} Would you like to start again?",
            "start-order",
            next_state="browsing",
            response_products=products[:MAX_RESPONSE_PRODUCTS],
        )

    # Above the collecting-* states as well as product resolution. Those states
    # read the message literally - it is meant to BE the name or the phone
    # number - so "show my cart" was being saved as the customer's name. It is
    # matched by phrase because no intent is classified there.
    if any(phrase in lowered_message for phrase in CART_PHRASES) or intent_is(
        "show_cart",
    ):
        # Reading the cart back is not a step in the conversation, so the state
        # is left exactly where it was.
        return respond(
            cart_contents_message(cart_summary),
            "show-cart",
            next_state=current_state,
        )

    if current_state == "choosing-payment" and not is_cancel_order_request(message):
        chosen = payment_choice_from_message(message, ai_intent)

        if not chosen:
            return respond(
                "Sorry, I did not catch that. Reply 'cash on delivery', 'full "
                "bank transfer', or 'half bank transfer'.",
                "choose-payment",
                next_state="choosing-payment",
            )

        customer_draft["paymentChoice"] = chosen

        item_text = ", ".join(
            f"{item['quantity']} × {item['productName']}"
            + (f" ({item["size"]})" if item["size"] else "")
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
            + payment_summary_text(customer_draft.get("paymentChoice", "cod"))
            + "Reply 'confirm order' to submit, or 'change order' to edit the details."
        )
        return respond(
            response_message,
            "confirm-order",
            next_state="awaiting-confirmation",
        )


    # ---- Review collection, after delivery -------------------------------
    # The seller marking an order delivered invites the customer to review it
    # (see `chat_event_service`). Ownership was proved by placing the order, so
    # no phone check is repeated here - `write_order_review` still enforces the
    # delivered gate and the one-review-per-order rule.
    if current_state in REVIEW_STATES:
        review_draft = dict(session.get("reviewDraft") or {})
        order_reference = (
            database.collection("businesses")
            .document(session["businessId"])
            .collection("orders")
            .document(review_draft.get("orderId") or "__missing__")
        )
        order_snapshot = order_reference.get()

        def end_review(text):
            session_snapshot.reference.set(
                {"reviewDraft": {}},
                merge=True,
            )
            return respond(text, "prompt", next_state="completed")

        def save_draft(changes, text, action, next_state):
            review_draft.update(changes)
            session_snapshot.reference.set(
                {"reviewDraft": review_draft},
                merge=True,
            )
            return respond(text, action, next_state=next_state)

        def submit(product_id, rating, review_text):
            """Write one review, and turn a rejection into a plain sentence."""
            try:
                write_order_review(
                    database,
                    session["businessId"],
                    order_snapshot,
                    {
                        "orderNumber": order_snapshot.to_dict().get("orderNumber", ""),
                        "normalizedPhone": order_snapshot.to_dict()
                        .get("customerSnapshot", {})
                        .get("normalizedPhone", ""),
                        "productId": product_id,
                        "reviewText": review_text,
                        "rating": rating,
                        "media": [
                            {"type": "image", "url": url}
                            for url in (review_draft.get("media") or [])
                        ],
                    },
                    # Chat photos are already uploaded, so no Cloudinary
                    # credentials are needed on this path.
                    {},
                )
                return ""
            except ApiError as error:
                return error.message

        if not order_snapshot.exists:
            return end_review(
                "I could not find that order any more, so I cannot record a "
                "review for it. Is there anything else I can help with?",
            )

        order_items = order_snapshot.to_dict().get("items", [])

        # "Skip" has to work at every step. A review nobody wants to write must
        # not trap the customer in a loop of questions.
        if wants_to_skip(message) and current_state != "collecting-review-photo":
            return end_review(
                "No problem, thank you for shopping with us. Tell me if you "
                "need anything else.",
            )

        if current_state == "collecting-review-product":
            chosen = next(
                (
                    item
                    for item in order_items
                    if str(item.get("productName", "")).casefold()
                    in message.casefold()
                ),
                None,
            )
            index = re.search(r"\b([1-9])\b", message)

            if not chosen and index and int(index.group(1)) <= len(order_items):
                chosen = order_items[int(index.group(1)) - 1]

            if not chosen:
                return respond(
                    "Which item shall I record the review for? "
                    + ", ".join(
                        f"{position}. {item.get('productName', 'item')}"
                        for position, item in enumerate(order_items, start=1)
                    ),
                    "collect-review-product",
                    next_state="collecting-review-product",
                )

            return save_draft(
                {"productId": chosen.get("productId", "")},
                f"How would you rate the {chosen.get('productName', 'item')} "
                "out of 5?",
                "collect-review-rating",
                "collecting-review-rating",
            )

        if current_state == "collecting-review-rating":
            rating = parse_star_rating(message)

            if not rating:
                return respond(
                    "Please send a number from 1 to 5, where 5 is excellent.",
                    "collect-review-rating",
                    next_state="collecting-review-rating",
                )

            return save_draft(
                {"rating": rating},
                f"Thank you, {rating} out of 5. What did you think of it? "
                "A sentence is plenty, or say skip.",
                "collect-review-text",
                "collecting-review-text",
            )

        if current_state == "collecting-review-text":
            return save_draft(
                {"reviewText": message.strip()[:2000]},
                "Would you like to add a photo of it? Send the picture, or "
                "say done.",
                "collect-review-photo",
                "collecting-review-photo",
            )

        if current_state == "collecting-review-photo":
            # Photos arrive through the image endpoint, not as text. Any text
            # here means the customer is finished adding them.
            failure = submit(
                review_draft.get("productId", ""),
                review_draft.get("rating", 5),
                review_draft.get("reviewText") or "No comment.",
            )

            if failure:
                return end_review(failure)

            return save_draft(
                {"media": [], "reviewText": "", "productId": ""},
                "Thank you, your review has been sent to the seller. One last "
                "thing - how would you rate the service overall, out of 5?",
                "collect-seller-rating",
                "collecting-review-seller-rating",
            )

        if current_state == "collecting-review-seller-rating":
            rating = parse_star_rating(message)

            if not rating:
                return respond(
                    "Please send a number from 1 to 5 for the service.",
                    "collect-seller-rating",
                    next_state="collecting-review-seller-rating",
                )

            failure = submit("", rating, f"Rated {rating} out of 5 for service.")
            return end_review(
                failure
                or "Thank you. Both reviews are with the seller and will "
                "appear on the store once approved.",
            )

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

        # Payment is settled before the summary, so the order the customer
        # approves states how they intend to pay. Asked after it, they would be
        # confirming terms that were not yet decided.
        return respond(
            "Last thing - how would you like to pay? Reply 'cash on delivery', "
            "'full bank transfer' to send the whole amount now, or 'half bank "
            "transfer' to send part now and pay the rest to the courier.",
            "choose-payment",
            next_state="choosing-payment",
        )

    if (
        customer_draft.get("paymentMethod") == "deposit"
        and not customer_draft.get("depositChoice")
        and deposit_choice(message)
        and not is_deposit_request(message)
    ):
        customer_draft["depositChoice"] = deposit_choice(message)
        amount_text = (
            "the full amount"
            if customer_draft["depositChoice"] == "full"
            else "part of the total, with the balance on delivery"
        )
        return respond(
            f"Noted - you are sending {amount_text}. I have put that on your "
            "order so the seller can check for your transfer. Send a photo of "
            "the bank slip here once you have paid.",
            "show-bank-details",
            next_state=current_state,
        )

    if is_location_question(message) or intent_is("location_question"):
        return respond(
            store_location_message(
                catalog["business"].get("storeLocation"),
                catalog["business"].get("name", "This store"),
            ),
            "show-store-location",
            next_state=current_state,
        )

    if is_deposit_request(message) or intent_is("payment_question"):
        business_document = (
            database.collection("businesses").document(session["businessId"]).get()
        )
        bank = (business_document.to_dict() or {}).get("bankDetails") or {}
        details = bank_details_message(bank, catalog["business"].get("name", "the seller"))

        if details:
            # Remember the choice so the order records it and the seller knows
            # to watch for a transfer.
            customer_draft["paymentMethod"] = "deposit"
            stated = deposit_choice(message)
            if stated:
                customer_draft["depositChoice"] = stated
            return respond(details, "show-bank-details", next_state=current_state)

        return respond(
            "This seller takes cash on delivery only, so there is nothing to "
            "pay in advance. You pay the courier when your order arrives.",
            "show-order-info",
            next_state=current_state,
        )

    if wants_to_cancel and session.get("orderId"):
        order_to_cancel = latest_order_for_session(database, session)
        current_order_status = (order_to_cancel or {}).get(
            "fulfilmentStatus",
            "",
        )

        if not order_to_cancel:
            return respond(
                "I could not find an order on this conversation to cancel.",
                "show-order-info",
                next_state="completed",
            )

        if current_order_status not in CUSTOMER_CANCELLABLE_STATUSES:
            notify_seller_attention(
                database,
                session_snapshot.reference,
                session["businessId"],
                f"Customer asked to cancel {order_to_cancel.get('orderNumber', '')}",
            )
            return respond(
                f"Order {order_to_cancel.get('orderNumber', '')} is already "
                f"{current_order_status.replace('-', ' ')}, so I cannot cancel "
                "it here. I have told the seller and they will contact you.",
                "show-order-info",
                next_state="completed",
            )

        return respond(
            f"Just to confirm - you want to cancel order "
            f"{order_to_cancel.get('orderNumber', '')}? This cannot be undone. "
            "Reply 'yes cancel' to go ahead.",
            "confirm-cancel-order",
            next_state="confirming-cancel",
        )

    # The keyword list matches broad words like "deliver" and "shipping", so on
    # its own it hijacks browsing questions ("how long is delivery?") into an
    # order-status reply whenever the customer has any past order. It is trusted
    # only once an order exists in this conversation, or when the customer names
    # an order number. The classifier's verdict is trusted anywhere.
    # Naming an order number is a status enquiry on its own - "VD-000001
    # kohomada?" carries no keyword from the list. Anything vaguer is trusted
    # only once this conversation actually has an order attached to it.
    keyword_status_enquiry = bool(named_order_number) or (
        is_order_enquiry(lowered_message)
        and (
            current_state == "completed"
            or session.get("status") == "completed"
            or session.get("orderId")
        )
    )

    latest_order = None
    if keyword_status_enquiry or intent_is("order_status"):
        latest_order = latest_order_for_session(database, session)
        if latest_order:
            session_snapshot.reference.set(
                {
                    "orderId": latest_order["id"],
                    "orderIds": firestore.ArrayUnion([latest_order["id"]]),
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
            # Same rule as any other catalogue request: on a large catalogue,
            # ask what they need instead of dumping every product and making
            # the customer scroll it on a phone.
            new_order_categories = catalogue_categories(products)

            if len(products) > BROWSABLE_CATALOGUE_SIZE and new_order_categories:
                return respond(
                    "Of course. What kind of product are you looking for this "
                    "time? Choose one of these, or tell me what you need: "
                    f"{', '.join(new_order_categories)}.",
                    "show-categories",
                    next_state="browsing",
                    response_categories=new_order_categories,
                    selected_product_id=(
                        None if not session.get("productId") else "unchanged"
                    ),
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

    # The customer was asked which variant of a named product they want.
    if current_state == "awaiting-variant":
        pending_product = next(
            (
                item
                for item in products
                if item.get("id") == session.get("selectedProductId")
            ),
            None,
        )
        chosen_variant = (
            match_variant_in_message(pending_product, message)
            or choose_variant(pending_product, ai_intent.get("sizeQuery", ""))
            if pending_product
            else None
        )

        if chosen_variant:
            wanted_quantity = quantity_from_message(
                message,
                ai_intent.get("quantity"),
            )
            label = (
                f" ({chosen_variant['size']})" if chosen_variant.get("size") else ""
            )

            # Never assume one. The quantity question is the same one every
            # other route through the order asks.
            if wanted_quantity <= 0:
                return respond(
                    f"How many {pending_product['name']}{label} would you "
                    "like? Send a number, for example 2.",
                    "collect-item-quantity",
                    next_state="awaiting-item-quantity",
                    product=pending_product,
                    pending_variant_id=chosen_variant["id"],
                )

            cart, line_quantity = set_variant_quantity(
                cart,
                chosen_variant["id"],
                wanted_quantity,
                chosen_variant.get("availableStock", 0),
            )
            cart_summary = summarize_chat_cart(cart, products)
            return respond(
                f"Added {line_quantity} x {pending_product['name']}{label} to "
                "your order. Anything else, or shall we continue?",
                "cart-updated",
                next_state="browsing",
                product=pending_product,
                pending_variant_id=None,
            )

        # Not a variant name. Only ask again when they have not moved on -
        # otherwise a customer who changed their mind is stuck in a loop.
        if pending_product and (
            not ai_intent.get("intent")
            or intent_is("start_order", "set_quantity", "unknown")
        ):
            return respond(
                f"Which option of {pending_product['name']} would you like? "
                f"Available: {', '.join(variant_labels(pending_product))}.",
                "select-variant",
                next_state="awaiting-variant",
                product=pending_product,
            )

        current_state = "browsing"

    # The customer was asked how many of a named product they want.
    if current_state == "awaiting-item-quantity":
        pending_product, pending_variant = find_variant(
            products,
            session.get("pendingVariantId", ""),
        )
        wanted_quantity = quantity_from_message(message, ai_intent.get("quantity"))

        # "actually the T800, two of those" names a different product. Applying
        # the quantity to the item we happened to be holding would put the wrong
        # thing in a real order, so the named product wins.
        renamed_matches = (
            find_matching_products(ai_intent["productQuery"], products)
            if ai_intent.get("productQuery")
            else []
        )

        if len(renamed_matches) == 1 and (
            not pending_product or renamed_matches[0]["id"] != pending_product["id"]
        ):
            renamed_product = renamed_matches[0]
            renamed_variant = choose_variant(
                renamed_product,
                ai_intent.get("sizeQuery", ""),
            )

            if renamed_variant:
                pending_product, pending_variant = renamed_product, renamed_variant
            else:
                sizes = variant_labels(renamed_product)
                return respond(
                    f"Which option of {renamed_product['name']} would you "
                    f"like? Available: {', '.join(sizes)}.",
                    "select-variant",
                    next_state="awaiting-variant",
                    product=renamed_product,
                    selected_product_id=renamed_product["id"],
                    pending_variant_id=None,
                )

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
                f" ({pending_variant["size"]})"
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

    # The customer was offered the choice between adding to an unconfirmed
    # order and placing a separate one. Handled here, above the collecting-*
    # states, because "add to my order" must not be read as a name.
    if current_state == "choosing-order-merge":
        open_order = latest_order_for_session(database, session)

        if wants_to_merge_orders(message) or intent_is("confirm_order"):
            if not order_accepts_more_items(open_order):
                # The seller confirmed it while the customer was deciding.
                return respond(
                    "The seller has just started preparing that order, so I "
                    "cannot add to it now. Let us place this as a separate "
                    "order. What is your full name?",
                    "collect-name",
                    next_state="collecting-name",
                )

            try:
                updated = add_items_to_order(
                    database,
                    session["businessId"],
                    open_order["id"],
                    f"public-chat:{session_id}",
                    [
                        {"variantId": line["variantId"], "quantity": line["quantity"]}
                        for line in cart_summary
                    ],
                )
            except ApiError as error:
                # Stock can sell out between the offer and the choice. Say so
                # and fall back to a separate order rather than losing the cart.
                return respond(
                    f"{error.message} Shall I place this as a separate order "
                    "instead? Tell me your full name to continue.",
                    "collect-name",
                    next_state="collecting-name",
                )

            cart = []
            cart_summary = []
            session_snapshot.reference.update(
                {
                    "orderId": updated["id"],
                    "orderIds": firestore.ArrayUnion([updated["id"]]),
                    "status": "completed",
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                },
            )
            return respond(
                f"Done. Your order {updated.get('orderNumber', '')} now has "
                f"{updated.get('itemCount', 0)} item(s), with delivery "
                "recalculated for the new weight. "
                + order_information_message(updated),
                "show-order-info",
                next_state="completed",
            )

        if wants_separate_order(message) or intent_is("new_order", "start_order"):
            return respond(
                "No problem, I will place this as a separate order. What is "
                "your full name?",
                "collect-name",
                next_state="collecting-name",
            )

        return respond(
            "Sorry, I did not catch that. Reply 'add to my order' to put these "
            "items on your existing order, or 'separate order' to place a new "
            "one.",
            "choose-order-merge",
            next_state="choosing-order-merge",
        )

    # Contact collection is deterministic so invalid details never reach orders.
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
                        # The answer to "how would you like to pay?" outranks
                        # anything inferred earlier from a question about bank
                        # transfers - it is the one the customer was asked
                        # directly and saw in the summary they confirmed.
                        "paymentMethod": chat_payment_method(customer_draft),
                        "paymentPending": customer_draft.get("paymentChoice", "cod")
                        != "cod",
                        "depositChoice": customer_draft.get("depositChoice", ""),
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
                "suggestions": ["order-status", "another-order", "cancel-order"],
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
        # An order the seller has not started on can still take these items,
        # and one delivery costs the customer one delivery fee. Ask rather than
        # decide: they may want them sent separately.
        open_order = latest_order_for_session(database, session)

        if order_accepts_more_items(open_order):
            return respond(
                f"You already have order {open_order.get('orderNumber', '')}, "
                "which the seller has not confirmed yet. Shall I add these "
                f"{item_count} item(s) to it, so everything arrives together "
                "and you pay one delivery fee? Reply 'add to my order', or "
                "'separate order' to place a new one.",
                "choose-order-merge",
                next_state="choosing-order-merge",
                response_products=[],
            )

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
    # A comparison of what is on screen must be answered before the remembered
    # single product claims the message - "what is best among them" was being
    # answered about one item instead of comparing the two that were listed.
    # An explicit "compare these" is answered with the table itself. It sits
    # above the recommendation branch because "compare" and "which is best"
    # want different answers: one lays the differences out, the other picks a
    # winner. Sharing a branch meant a comparison request got a verdict.
    if wants_a_comparison(message):
        # Most specific scope first. Naming the products outright has to beat
        # a category word, because the category word is usually inside one of
        # those names - "GM2 Pro Earbuds vs Runner Shoes" was being read as
        # "the Earbuds category" and compared one product with itself.
        # `find_matching_products` returns the first exact name match and
        # stops - it exists to resolve one product. A comparison names two, so
        # it uses the matcher built for finding every product named in a piece
        # of text.
        matched_by_name = products_the_customer_named(message, products)
        named_scope = find_category_request(message, products, require_cue=False)
        on_screen = products_by_ids(products, session.get("lastShownProductIds"))

        if len(matched_by_name) > 1:
            to_compare = matched_by_name
        elif named_scope:
            # "compare the power banks" carries its own scope, so it does not
            # depend on what happens to be on screen.
            to_compare = category_products(products, named_scope)
        elif on_screen:
            to_compare = on_screen
        elif session.get("lastCategoryShown"):
            to_compare = category_products(products, session["lastCategoryShown"])
        else:
            to_compare = []

        # A listing renders MAX_RESPONSE_PRODUCTS cards, so "compare these"
        # could never see more than four however many the shelf holds. Top the
        # on-screen set up from its own category before truncating.
        if to_compare and len(to_compare) < MAX_COMPARE_PRODUCTS:
            picked = {item.get("id") for item in to_compare}
            to_compare = to_compare + [
                item
                for item in category_products(
                    products,
                    to_compare[0].get("categoryName", ""),
                )
                if item.get("id") not in picked
            ]

        to_compare = to_compare[:MAX_COMPARE_PRODUCTS]

        if len(to_compare) > 1:
            table = generate_comparison_answer(to_compare, language)

            # The model reads the descriptions and compares whatever features
            # the seller wrote about. Without it, the stored fields still make
            # a usable table - worse, but not nothing.
            table = table or comparison_table(to_compare)

            if table:
                for marker in (MISSING_FACT_MARKER, ANSWERED_MARKER):
                    table = table.replace(marker, "")

                return respond(
                    table.strip(),
                    "show-category",
                    next_state="browsing",
                    response_products=to_compare,
                    is_translated=True,
                )

        if len(to_compare) == 1:
            # Alternatives from the same category, not the first four items in
            # the catalogue. Asking which watch to compare against and showing
            # power banks answers a question nobody asked.
            alternatives = [
                item
                for item in category_products(
                    products,
                    to_compare[0].get("categoryName", ""),
                )
                if item.get("id") != to_compare[0].get("id")
            ]
            return respond(
                "I need at least two products to compare. Which shall I put "
                f"beside the {to_compare[0]['name']}?",
                "show-category",
                next_state="browsing",
                response_products=(alternatives or products)[:MAX_RESPONSE_PRODUCTS],
            )

    if refers_to_shown_products(message) and wants_a_recommendation(message):
        on_screen = products_by_ids(products, session.get("lastShownProductIds"))

        if len(on_screen) > 1:
            comparison = generate_catalogue_answer(
                message,
                on_screen,
                language,
                catalog["business"].get("storefrontFaq", ""),
            )

            # The provider may be rate limited. A table built from stored
            # facts is worse than the model's reasoning but far better than
            # no answer.
            fell_back = not comparison
            comparison = comparison or comparison_table(on_screen)

            if comparison:
                for marker in (MISSING_FACT_MARKER, ANSWERED_MARKER):
                    comparison = comparison.replace(marker, "")
                named = [] if fell_back else products_named_in(comparison, on_screen)
                return respond(
                    comparison.strip(),
                    "show-category",
                    next_state="browsing",
                    response_products=(named or on_screen)[:MAX_COMPARE_PRODUCTS],
                    selected_product_id=(
                        named[0]["id"] if len(named) == 1 else "unchanged"
                    ),
                    is_translated=True,
                )

    # "Show me more" used to fall through to the generic prompt, or re-list the
    # same first four. The scope is whatever was last listed; the page is
    # everything in it that has not been shown yet.
    # "thawa dekak" is two *more of this item*, not more products - a digit or
    # a quantity intent means the cart branch below owns the message.
    if (
        wants_more_products(message)
        and session.get("seenProductIds")
        and not intent_is("set_quantity", "add_to_cart", "place_order")
        and not any(character.isdigit() for character in message)
    ):
        scope = (
            category_products(products, session["lastCategoryShown"])
            if session.get("lastCategoryShown")
            else products
        )
        seen = set(session.get("seenProductIds") or [])
        remaining = [item for item in scope if item.get("id") not in seen]

        if remaining:
            return respond(
                "Here are more.",
                "show-category",
                next_state="browsing",
                response_products=remaining[:MAX_RESPONSE_PRODUCTS],
                accumulate_seen=True,
            )

        if not find_matching_products(message, products):
            return respond(
                "That is everything I have"
                + (
                    f" in {session['lastCategoryShown']}"
                    if session.get("lastCategoryShown")
                    else ""
                )
                + ". Tell me what you are looking for and I will help you find it.",
                "prompt",
                next_state="browsing",
            )

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

    # A stated quantity is an order however terse the rest is. message_tokens
    # drops one- and two-character words, so "2 GM2 Pro" looked like a bare
    # product name until the quantity was checked separately.
    if (
        wants_to_order
        and not ai_intent.get("quantity")
        and not quantity_from_message(message)
        and message_is_only_a_product_name(message, explicitly_selected_product)
    ):
        # They named a product and nothing else. Show it; the "Order this" chip
        # and any explicit order wording still lead straight to the quantity.
        wants_to_order = False

    # A category named in this message outranks a product remembered from an
    # earlier one: "send me smartwatch" after asking about a power bank must
    # not order the power bank.
    named_category = find_category_request(message, products, require_cue=False)

    if named_category and not explicitly_selected_product:
        selected_product = None

    # Resolved here, above its first use. It was assigned further down, after
    # the ordering block that reads it, so "I want to order <brand>" with no
    # matching category crashed on an unbound name instead of listing the
    # brand. Nothing between here and there changes the message it reads.
    requested_brand = find_brand_request(message, products)

    def category_response(category_name, matches, heading):
        """Answer a category request, honouring any feature named alongside it.

        Two branches list a category - one for a cued request ("show me smart
        watches"), one for a bare category name. Both must apply the filter, so
        it lives here rather than being written twice and drifting apart.
        """
        requested_features = feature_terms(message, category_name)

        if not requested_features:
            return respond(
                heading,
                "show-category",
                next_state="browsing",
                response_products=matches,
                selected_product_id=(
                    None if not session.get("productId") else "unchanged"
                ),
            )

        # Read the seller's own text first. It cannot hallucinate, costs
        # nothing, and works while the provider is rate limited.
        feature_matches = products_with_features(matches, requested_features)
        feature_text = " ".join(requested_features)

        if feature_matches:
            return respond(
                f"Here is what we have in {category_name} with {feature_text}.",
                "show-category",
                next_state="browsing",
                response_products=feature_matches,
            )

        # Nothing matched by reading. The seller may have described the feature
        # in words the matcher does not know, so the model gets a look before
        # the customer is told it does not exist.
        feature_answer = generate_catalogue_answer(
            message,
            matches,
            language,
            catalog["business"].get("storefrontFaq", ""),
            conversation_history,
        )

        if feature_answer and MISSING_FACT_MARKER not in feature_answer:
            for marker in (MISSING_FACT_MARKER, ANSWERED_MARKER):
                feature_answer = feature_answer.replace(marker, "")

            named = products_named_in(feature_answer, matches)

            if named:
                return respond(
                    feature_answer.strip(),
                    "show-category",
                    next_state="browsing",
                    response_products=named[:MAX_RESPONSE_PRODUCTS],
                    is_translated=True,
                )

        # Said plainly, then alternatives - the customer came for something
        # and an outright "no" with nothing beside it ends the conversation.
        # The alternatives are labelled as alternatives, because listing them
        # under the feature reads as though they have it.
        alternatives = matches or products
        return respond(
            f"We do not have any {category_name} with {feature_text} - none of "
            "their descriptions mentions it, and I will not guess on something "
            "you are paying for. The closest we have are below. Tell me what "
            "matters most to you and I will help you choose, or ask me and one "
            "of our agents can check for you.",
            "show-category",
            next_state="browsing",
            response_products=alternatives[:MAX_RESPONSE_PRODUCTS],
        )


    # One gate for every branch that lists a group. A feature named alongside
    # a category is a filter wherever it appears - "send me 20000mah power
    # banks" was reaching the ordering branch, which asked which power bank
    # they wanted and listed all of them. Patching each listing branch in turn
    # is what let this recur; this runs before all of them.
    feature_scope = named_category or category_request
    feature_group = (
        category_products(products, feature_scope) if feature_scope else []
    )

    if not feature_group and len(matching_products) > 1:
        feature_group = matching_products
        feature_scope = shared_category_name(matching_products) or "products"

    # A message naming one product is a question about that product, not a
    # filter over a group - "is the T800 waterproof" must keep its own answer.
    if (
        feature_scope
        and len(feature_group) > 1
        and len(matching_products) != 1
        and feature_terms(message, feature_scope)
    ):
        return category_response(
            feature_scope,
            feature_group,
            f"Here is what we have in {feature_scope}.",
        )

    if wants_to_order:
        # A customer who says "mata GM2 pro dekak ona" has already chosen. Being
        # told to click Add is a dead end for anyone typing Sinhala or speaking,
        # which is exactly who needs to order without calling the seller.
        if selected_product:
            variant = choose_variant(selected_product, ai_intent.get("sizeQuery", ""))
            available_sizes = variant_labels(selected_product)

            if not variant and available_sizes:
                # awaiting-variant, not browsing: the reply is a bare word like
                # "orange", which browsing would try to resolve as a product and
                # then ask this same question again.
                return respond(
                    f"Which option of {selected_product['name']} would you "
                    f"like? Available: {', '.join(available_sizes)}.",
                    "select-variant",
                    next_state="awaiting-variant",
                    product=selected_product,
                    selected_product_id=selected_product["id"],
                )

            if variant:
                asked_quantity = ai_intent.get("quantity") or 0
                size_label = (
                    f" ({variant["size"]})" if variant.get("size") else ""
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
                size_text = f" ({variant["size"]})" if variant.get("size") else ""
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

        # No single product resolved. Before dumping the catalogue, see whether
        # they named a category - "a powerbank", "a smart watch".
        ordering_category = category_request or find_category_request(
            message,
            products,
            require_cue=False,
        )
        category_matches = (
            category_products(products, ordering_category) if ordering_category else []
        )

        if not category_matches and requested_brand:
            ordering_category = requested_brand
            category_matches = brand_products(products, requested_brand)

        if category_matches:
            return respond(
                f"Which {ordering_category} would you like to order? Tell me "
                "the name and how many, or choose one below.",
                "start-order",
                next_state="browsing",
                response_products=category_matches,
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

    if category_request and wants_a_recommendation(message):
        # "Best smart watch" wants one picked and justified, not a listing.
        scoped = category_products(products, category_request)
        recommendation = generate_catalogue_answer(
            message,
            scoped or products,
            language,
            catalog["business"].get("storefrontFaq", ""),
            conversation_history,
        )

        if recommendation and MISSING_FACT_MARKER not in recommendation:
            for marker in (MISSING_FACT_MARKER, ANSWERED_MARKER):
                recommendation = recommendation.replace(marker, "")
            named = products_named_in(recommendation, scoped or products)
            return respond(
                recommendation.strip(),
                "show-category",
                next_state="browsing",
                response_products=(named or scoped)[:MAX_RESPONSE_PRODUCTS],
                # "More info" after a recommendation must be about the product
                # that was recommended, not whatever was selected before it.
                selected_product_id=(
                    named[0]["id"] if len(named) == 1 else "unchanged"
                ),
                is_translated=True,
            )

    if category_request:
        return category_response(
            category_request,
            category_products(products, category_request),
            f"Here are all available products in {category_request}.",
        )

    if requested_brand and not selected_product:
        brand_matches = brand_products(products, requested_brand)

        if brand_matches:
            return respond(
                f"Here is what we have from {requested_brand}.",
                "show-category",
                next_state="browsing",
                response_products=brand_matches,
            )

    if wants_catalog:
        category_names = catalogue_categories(products)

        # Dumping the whole catalogue makes the customer do the filtering, and
        # on a phone it buries the conversation. Ask what they are after and
        # offer the categories instead - unless the shop is small enough that
        # narrowing would be pointless friction.
        if len(products) > BROWSABLE_CATALOGUE_SIZE and category_names:
            return respond(
                "What kind of product are you looking for? Choose one of these, "
                "or tell me what you need and I will find the closest matches: "
                f"{', '.join(category_names)}.",
                "show-categories",
                next_state="browsing",
                response_categories=category_names,
                selected_product_id=None if not session.get("productId") else "unchanged",
            )

        return respond(
            "Here is everything we have. Choose a product to see its image, "
            "description, price, available sizes and stock.",
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

        # Naming the product in this message - "lenovo gm2 pro" - is a request
        # to see it, so it earns the full card. Only a follow-up about a
        # product already on screen returns a bare answer.
        is_product_overview_request = bool(explicitly_selected_product) or is_catalog_number_choice(message) or any(
            phrase in lowered_message
            for phrase in (
                "tell me about",
                "product details",
                "view details",
                "know more",
                "more about",
                "more info",
                "more detail",
                "full detail",
                "full info",
                "specs",
                "specification",
                "තව තොරතුරු",
                "மேலோம் தகவல்",
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
            # The card below carries the name, price, warranty, stock and
            # description in a readable layout. Repeating them here printed
            # everything twice and pushed the card off a phone screen.
            response_message = (
                f"Here are the details for {selected_product['name']}."
                f"{size_text} Ask about a feature, compare similar products, or "
                "choose Order this product when you are ready."
            )
        else:
            generated_answer = generate_product_answer(
                message,
                selected_product,
                language,
                related_products(products, selected_product, limit=6),
                conversation_history,
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
                handoff = seller_contact_message(catalog["business"])
                response_message = (
                    f"{response_message} "
                    f"{translate_chat_message(handoff, language)}"
                    if answer_in_customer_language
                    else f"{response_message} {handoff}"
                )

                notify_seller_attention(
                    database,
                    session_snapshot.reference,
                    session["businessId"],
                    message,
                )

        return respond(
            response_message,
            # A full overview earns the product card - gallery, reviews and
            # the similar-products strip. A follow-up question ("does it have
            # ANC?") wants the answer and nothing else; repeating the whole
            # card under every reply buries it. "Show similar" is one chip away.
            "show-product" if is_product_overview_request else "product-answer",
            next_state="browsing",
            product=selected_product,
            response_reviews=(product_reviews[:4] if is_product_overview_request else []),
            review_summary=product_review_summary,
            response_products=(
                related_products(products, selected_product)
                if is_product_overview_request
                else []
            ),
            selected_product_id=selected_product["id"],
            is_translated=answer_in_customer_language,
        )

    # The message named several products equally well. Asking which one is a
    # real answer; falling through to the generic prompt is a dead end that
    # also pages the seller for a question the catalogue can settle.
    if len(matching_products) > 1:
        # A feature named alongside the products is a filter, not noise. "sim
        # danna puluwan smart watch nadda" matched both watches on "smart
        # watch" and asked which one they meant - about two products that
        # neither support SIM.
        if feature_terms(message, shared_category_name(matching_products)):
            return category_response(
                shared_category_name(matching_products) or "products",
                matching_products,
                "I found more than one product matching that. Which one would "
                "you like to know about?",
            )

        return respond(
            "I found more than one product matching that. Which one would you "
            "like to know about?",
            "show-catalog",
            next_state="browsing",
            response_products=matching_products[:MAX_RESPONSE_PRODUCTS],
        )

    is_simple_greeting = intent_is("greeting") or normalized_phrase(message) in {
        normalized_phrase(phrase) for phrase in GREETING_PHRASES
    }

    # "What is your cheapest earbud", "anything under 3000", "can I return it"
    # and "do you accept cash on delivery" name no single product, so nothing
    # above matched. Only the catalogue and the seller's own policy text are
    # offered as facts.
    # Ambiguous scope: they are looking at one category and asked for a budget
    # without saying whether they mean that category or the whole shop.
    # Guessing either way is wrong half the time, so ask.
    if (
        has_price_constraint(message)
        and not named_category
        and session.get("lastCategoryShown")
        and current_state != "clarifying-scope"
    ):
        session_snapshot.reference.set(
            {"pendingBudgetQuestion": message},
            merge=True,
        )
        return respond(
            f"Just to be sure - are you asking about "
            f"{session['lastCategoryShown']} in that price range, or any "
            "product in the shop? Reply with the category name, or say "
            "'any product'.",
            "confirm-scope",
            next_state="clarifying-scope",
        )

    if has_price_constraint(message):
        budget_scope = category_products(
            products,
            named_category or session.get("lastCategoryShown"),
        ) if (named_category or session.get("lastCategoryShown")) else []
        budget_answer = generate_catalogue_answer(
            message,
            budget_scope or products,
            language,
            catalog["business"].get("storefrontFaq", ""),
            conversation_history,
        )

        if budget_answer:
            for marker in (MISSING_FACT_MARKER, ANSWERED_MARKER):
                budget_answer = budget_answer.replace(marker, "")
            named = products_named_in(budget_answer, budget_scope or products)
            return respond(
                budget_answer.strip(),
                "show-category",
                next_state="browsing",
                response_products=named[:MAX_RESPONSE_PRODUCTS],
                is_translated=True,
            )

    if named_category:
        matches = category_products(products, named_category)

        if matches:
            return category_response(
                named_category,
                matches,
                f"Here is what we have in {named_category}.",
            )

    if not is_simple_greeting and intent_is(
        "product_question",
        "policy_question",
        "unknown",
    ):
        # Scope to what they were just shown when the question names nothing.
        recent_category = None if named_category else session.get("lastCategoryShown")
        scoped_products = (
            category_products(products, recent_category) if recent_category else []
        )

        if refers_to_shown_products(message):
            on_screen = products_by_ids(products, session.get("lastShownProductIds"))
            if on_screen:
                scoped_products = on_screen
        catalogue_answer = generate_catalogue_answer(
            message,
            scoped_products or products,
            language,
            catalog["business"].get("storefrontFaq", ""),
            conversation_history,
        )

        if catalogue_answer and MISSING_FACT_MARKER not in catalogue_answer:
            for marker in (MISSING_FACT_MARKER, ANSWERED_MARKER):
                catalogue_answer = catalogue_answer.replace(marker, "")

            named = products_named_in(catalogue_answer, products)
            return respond(
                catalogue_answer.strip(),
                "show-catalog",
                next_state="browsing",
                response_products=(named or scoped_products or products)[:MAX_RESPONSE_PRODUCTS],
                selected_product_id=(
                    named[0]["id"] if len(named) == 1 else "unchanged"
                ),
                is_translated=True,
            )

    if not is_simple_greeting:
        notify_seller_attention(
            database,
            session_snapshot.reference,
            session["businessId"],
            message,
        )

    fallback_categories = catalogue_categories(products)

    # Before giving up: a half-named request usually reaches for one obvious
    # thing. "watches" is not "Smart watch" to the matcher, which is right -
    # a partial match is a guess - but a guess offered as a question costs
    # nothing, and "I did not catch which product you meant" ends the
    # conversation for a customer who was one word away.
    suggested_product = closest_product(message, products)

    if suggested_product:
        return respond(
            f"Did you mean the {suggested_product['name']}? Tell me yes and I "
            "will pull up its details, or say what you are looking for.",
            "show-catalog",
            next_state="browsing",
            response_products=[suggested_product],
        )

    suggested_category = closest_category(message, products)

    if suggested_category:
        return respond(
            f"Did you mean {suggested_category}? I can show you what we have "
            "there, or tell me more about what you are looking for.",
            "show-categories",
            next_state="browsing",
            response_categories=[suggested_category] + [
                name for name in fallback_categories if name != suggested_category
            ],
        )

    # Nothing matched. Offering the categories is a smaller ask than scrolling
    # a whole catalogue to work out what the shop even sells.
    if len(products) > BROWSABLE_CATALOGUE_SIZE and fallback_categories:
        return respond(
            "I did not catch which product you meant. What kind of item are "
            "you looking for? We have: "
            f"{', '.join(fallback_categories)}.",
            "show-categories",
            next_state="browsing",
            response_categories=fallback_categories,
        )

    return respond(
        "Please choose a product or category. I can show product photos and "
        "descriptions, answer feature questions, suggest alternatives and take "
        "a complete order. "
        + seller_contact_message(catalog["business"]),
        "show-catalog",
        next_state="browsing",
        response_products=products,
    )


def attach_public_chat_image(database, session_id, provided_token, payload):
    """Store one customer-sent image, such as a bank transfer slip.

    The image is uploaded to Cloudinary and recorded as a customer message, so
    it lands in the seller inbox next to the conversation it belongs to. The
    seller is notified because a slip is something they have to act on.
    """
    session_snapshot, session = authorize_public_chat_session(
        database,
        session_id,
        provided_token,
    )
    data_url = str(payload.get("image") or "").strip()

    if not data_url:
        raise ApiError("validation_error", "An image is required.", 422)

    try:
        caption = optional_text(payload.get("caption"), 300)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    uploaded = upload_chat_data_url(
        data_url,
        session["businessId"],
        session_id,
        {
            "cloud_name": current_app.config.get("CLOUDINARY_CLOUD_NAME"),
            "api_key": current_app.config.get("CLOUDINARY_API_KEY"),
            "api_secret": current_app.config.get("CLOUDINARY_API_SECRET"),
        },
    )
    save_chat_message(
        session_snapshot.reference,
        "customer",
        caption or "Sent an image.",
        {"imageUrl": uploaded["url"], "kind": "image"},
    )

    # A photo sent while reviewing belongs to the review, not to the seller's
    # attention queue - nothing needs acting on, and the review is submitted
    # when the customer says they are done.
    if session.get("state") == "collecting-review-photo":
        review_draft = dict(session.get("reviewDraft") or {})
        review_draft["media"] = (review_draft.get("media") or [])[
            : MAX_REVIEW_PHOTOS - 1
        ] + [uploaded["url"]]
        session_snapshot.reference.set(
            {"reviewDraft": review_draft, "updatedAt": firestore.SERVER_TIMESTAMP},
            merge=True,
        )
        return {
            "imageUrl": uploaded["url"],
            "message": translate_chat_message(
                "Added to your review. Send another photo, or say done."
                if len(review_draft["media"]) < MAX_REVIEW_PHOTOS
                else "That is the last photo I can attach. Say done to send "
                "your review.",
                session.get("language", "en"),
            ),
        }

    # A bank slip needs a human to look at it and confirm the money.
    notify_seller_attention(
        database,
        session_snapshot.reference,
        session["businessId"],
        caption or "Customer sent an image",
    )
    return {
        "imageUrl": uploaded["url"],
        "message": "Thank you. I have sent the image to the seller, and they "
                   "will confirm it shortly.",
    }


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

    # The customer said "half" or "full" in the chat. Converting that to money
    # is the seller's call once the transfer lands, so it is recorded as words
    # on the order rather than as a deposit amount nobody has received.
    deposit_intent = payload.get("depositChoice")
    if deposit_intent:
        stated = (
            "the full amount" if deposit_intent == "full"
            else "part of the total, balance on delivery"
        )
        private_note = (
            f"{private_note} Customer said they will bank transfer {stated}."
        )

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
        # "deposit" records that the customer intends to transfer. The amount
        # is deliberately left at zero: nothing has actually been received yet,
        # and marking money as paid before it arrives is a far worse error than
        # a seller having to confirm it.
        "paymentMethod": payload.get("paymentMethod") or "cod",
        # A transfer the customer has promised but not sent. Recorded as an
        # intention so the seller knows to expect it, never as money received.
        "paymentPending": payload.get("paymentPending") is True,
        "source": "chatbot",
        "discountAmount": 0,
        "privateNote": private_note,
        "customerNote": delivery_note,
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
            # Every order this chat has produced, not just the newest. The
            # status notifier looks a session up by order, and `orderId` is
            # overwritten by each new order - so a status change on the earlier
            # one reached nobody.
            "orderIds": firestore.ArrayUnion([order["id"]]),
            "customerDraft": customer_summary,
            "customerSummary": customer_summary,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    confirmation = public_order_confirmation(order)

    # Bank details travel with the order that needs them, never with the
    # catalogue: published there they would be readable by anyone who loads the
    # storefront. This customer has just placed the order they apply to.
    if order_payload.get("paymentPending"):
        business_snapshot = (
            database.collection("businesses")
            .document(session["businessId"])
            .get()
        )
        bank_details = (
            (business_snapshot.to_dict() or {}).get("bankDetails") or {}
            if business_snapshot.exists
            else {}
        )
        confirmation["bankDetails"] = bank_details
        confirmation["paymentPending"] = True

        # Also written into the conversation. The confirmation page is closed
        # once; the chat is where the customer goes back to find the account
        # number when they are actually at their banking app.
        details = bank_details_message(
            bank_details,
            catalog_business_name(database, session["businessId"]),
        )

        if details:
            balance_line = (
                f" Please transfer LKR {order.get('totalAmountMinor', 0) / 100:,.2f} "
                f"for order {order.get('orderNumber', '')}, then send me a photo "
                "of the receipt here."
                if order_payload.get("paymentMethod") != "deposit"
                else f" Please transfer the part you agreed for order "
                f"{order.get('orderNumber', '')}, then send me a photo of the "
                "receipt here. The courier collects the balance on delivery."
            )
            save_chat_message(
                session_snapshot.reference,
                "assistant",
                translate_chat_message(
                    details + balance_line,
                    session.get("language", "en"),
                ),
                {"action": "show-bank-details", "orderId": order["id"]},
            )

    return confirmation
