import json
import re

import httpx
from flask import current_app


OPENAI_COMPATIBLE_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
}


CHAT_LANGUAGES = {"en", "si", "ta"}

# The model replies in the customer's language, so the chat service cannot spot
# "I don't know" by matching English phrases. It appends this marker instead,
# which survives translation and is stripped before the customer sees the reply.
MISSING_FACT_MARKER = "[NO_DATA]"

LANGUAGE_NAMES = {"en": "English", "si": "Sinhala", "ta": "Tamil"}


def language_instruction(language):
    """Tell the model which single language the customer is speaking."""
    name = LANGUAGE_NAMES.get(language, "English")
    return (
        f"The customer is writing in {name}. Reply only in {name}, and keep "
        "using it for the whole conversation. Do not add an English translation "
        f"unless {name} is English."
    )


def product_prompt(question, product, language="en"):
    context = {
        "name": product.get("name"),
        "brand": product.get("brand"),
        "colour": product.get("colourName"),
        "category": product.get("categoryName"),
        "description": product.get("description"),
        "sellerAiDescription": product.get("aiDescription"),
        "priceLkr": product.get("sellingPriceMinor", 0) / 100,
        "availableSizes": [
            variant.get("size")
            for variant in product.get("variants", [])
            if variant.get("size")
        ],
        "approvedReviewCount": product.get("approvedReviewCount", 0),
        "approvedReviewSnippets": product.get("approvedReviewSnippets", []),
    }
    return (
        "You are Vendly's friendly order-taking product assistant for a small "
        "Sri Lankan online business. Chat naturally and briefly, like a real seller "
        f"replying on Messenger. {language_instruction(language)} "
        "Use no more than three short sentences in total. "
        "Only discuss the product supplied in PRODUCT FACTS. Do not claim that the "
        "seller carries another product unless it is supplied by the Vendly catalogue. "
        "Use only the seller-provided JSON facts below. Never invent features, "
        "warranties, waterproof ratings, SIM support, video support, reviews, or "
        "availability. If the facts do not answer the question, say the seller has "
        f"not provided that information yet and end your reply with {MISSING_FACT_MARKER}. "
        f"Never write {MISSING_FACT_MARKER} when the facts do answer the question. "
        "Do not claim to have searched or verified "
        "information on the internet because no web-search tool is connected. Mention "
        "that delivery is calculated from district and total order weight when relevant.\n\n"
        f"PRODUCT FACTS:\n{json.dumps(context, ensure_ascii=False)}\n\n"
        f"CUSTOMER QUESTION:\n{question}"
    )


def generate_openai_compatible_answer(prompt, provider, settings, max_tokens=350):
    base_url = settings.get("AI_API_BASE_URL") or OPENAI_COMPATIBLE_BASE_URLS.get(
        provider,
    )

    if not base_url:
        return None

    response = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings['AI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings["AI_MODEL"],
            "messages": [
                {"role": "system", "content": "Follow the supplied product facts exactly."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        },
        timeout=settings["AI_TIMEOUT_SECONDS"],
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def generate_gemini_answer(prompt, settings):
    from google import genai

    client = genai.Client(api_key=settings["AI_API_KEY"])
    interaction = client.interactions.create(
        model=settings["AI_MODEL"],
        input=prompt,
    )
    return interaction.output_text.strip()


def generate_product_answer(question, product, language="en"):
    """Return an optional AI answer; failures safely fall back to deterministic chat."""
    settings = current_app.config
    provider = settings.get("AI_PROVIDER", "none")

    if provider == "none" or not settings.get("AI_API_KEY") or not settings.get("AI_MODEL"):
        return None

    prompt = product_prompt(question, product, language)

    try:
        if provider == "gemini":
            return generate_gemini_answer(prompt, settings)
        if provider in {"groq", "cerebras", "openai-compatible"}:
            return generate_openai_compatible_answer(prompt, provider, settings)
    except Exception:  # External SDKs use provider-specific exception classes.
        current_app.logger.exception("The configured AI provider request failed.")
        return None

    current_app.logger.warning("Unsupported AI_PROVIDER value: %s", provider)
    return None


def request_ai_text(prompt, max_tokens=350):
    """Send one prompt to the configured provider, or None when unavailable."""
    settings = current_app.config
    provider = settings.get("AI_PROVIDER", "none")

    if provider == "none" or not settings.get("AI_API_KEY") or not settings.get("AI_MODEL"):
        return None

    try:
        if provider == "gemini":
            return generate_gemini_answer(prompt, settings)
        if provider in {"groq", "cerebras", "openai-compatible"}:
            return generate_openai_compatible_answer(
                prompt,
                provider,
                settings,
                max_tokens=max_tokens,
            )
    except Exception:  # External SDKs use provider-specific exception classes.
        current_app.logger.exception("The configured AI provider request failed.")
        return None

    current_app.logger.warning("Unsupported AI_PROVIDER value: %s", provider)
    return None


def detect_chat_language(message):
    """Identify the language a storefront customer is writing in.

    This exists for romanised input. Sri Lankan customers routinely type
    Sinhala and Tamil in Latin letters ("mata bag ekak ona", "enakku venum"),
    which no character-range check can tell apart from English. Returns None
    when the provider is unavailable so the caller keeps its current language.
    """
    prompt = (
        "Identify the language of one online-shopping message from a Sri Lankan "
        "customer. Answer with exactly one code and nothing else: "
        "en for English, si for Sinhala, ta for Tamil. "
        "Sinhala and Tamil are often typed in Latin letters rather than their "
        "own script - classify those as si or ta, not en. Examples: "
        "'mata meka ganna ona' is si, 'enakku idhu venum' is ta, "
        "'is this available' is en. "
        "A message that is only a name, a phone number, an address or a number "
        "carries no language signal, so answer en for it.\n\n"
        f"CUSTOMER MESSAGE:\n{message}"
    )
    answer = request_ai_text(prompt, max_tokens=8)

    if not answer:
        return None

    code = re.sub(r"[^a-z]", "", str(answer).casefold())[:2]
    return code if code in CHAT_LANGUAGES else None


# ponytail: plain dict, cleared wholesale when it grows. The chat prompts repeat
# constantly across sessions, so this removes almost every translation call.
# Swap for a TTL cache only if a single process starts holding too much.
_TRANSLATION_CACHE = {}
_TRANSLATION_CACHE_LIMIT = 1000


def translate_chat_message(text, language):
    """Translate one deterministic chat reply, keeping every value verbatim.

    Only the wording is translated. Prices, order numbers, product names,
    districts and the quoted commands the customer has to type back must
    survive unchanged, or the reply stops matching what the code expects.
    """
    clean_text = str(text or "").strip()

    if not clean_text or language not in CHAT_LANGUAGES or language == "en":
        return text

    cache_key = (language, clean_text)

    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    prompt = (
        f"Translate the shop assistant message below into "
        f"{LANGUAGE_NAMES[language]}. Return only the translation, with no "
        "explanation, no quotes around the whole reply and no English version.\n"
        "Keep these unchanged, exactly as written: numbers, prices, currency "
        "codes such as LKR, weights, order numbers, waybill numbers, product "
        "names, courier names, district names and email addresses.\n"
        "Any word or phrase inside single quotes is a command the customer must "
        "type back to the system. Keep those in English inside their quotes, and "
        "translate only the words around them.\n"
        "Keep the tone of a polite Sri Lankan shop assistant.\n\n"
        f"MESSAGE:\n{clean_text}"
    )
    translation = request_ai_text(prompt, max_tokens=600)

    if not translation:
        # A provider failure must never blank the reply. English is degraded,
        # but it still moves the order forward.
        return text

    translation = translation.strip()

    if len(_TRANSLATION_CACHE) >= _TRANSLATION_CACHE_LIMIT:
        _TRANSLATION_CACHE.clear()

    _TRANSLATION_CACHE[cache_key] = translation
    return translation


STOREFRONT_INTENTS = {
    "product_question",
    "show_catalog",
    "show_category",
    "similar_products",
    "reviews",
    "delivery_quote",
    "start_order",
    "finished_selecting",
    "confirm_order",
    "change_order",
    "order_status",
    "new_order",
    "greeting",
    "unknown",
}


def generate_storefront_intent(message, product_names, category_names, state):
    """Classify one storefront message and identify its language in one call.

    Sri Lankan customers mix languages inside a single sentence: Sinhala
    grammar with English product and commerce words, in either script. A
    keyword list cannot cover that, because any English noun can sit anywhere
    inside a Sinhala sentence. The model reads the whole sentence instead.

    The result is untrusted input. The caller allowlists the intent, resolves
    every product and district against its own catalogue, and keeps all
    validation, pricing and order writing in deterministic code.
    """
    prompt = (
        "Classify one message from a customer shopping on a Sri Lankan online "
        "store, and identify the language it is written in. Return one JSON "
        "object only, with no Markdown and no explanation.\n"
        "Sri Lankan customers mix languages inside one sentence. Sinhala or "
        "Tamil grammar is regularly combined with English product words, in "
        "either script: 'මට black bag එකක් order කරන්න ඕන', 'mata delivery fee "
        "eka kiyada', 'watch එකේ warranty තියෙනවද'. Classify the intent of the "
        "whole sentence, not of the English words in it.\n"
        "Set language to the language the customer is writing in, not the "
        "language of the individual words: si when the sentence is Sinhala "
        "(including Sinhala typed in Latin letters, and Sinhala mixed with "
        "English words), ta for Tamil the same way, en only when the sentence "
        "is genuinely English.\n"
        f"Allowed intents: {', '.join(sorted(STOREFRONT_INTENTS))}.\n"
        "Use product_question for any question about a product's features, "
        "price, stock, sizes, colours or warranty. Use show_catalog when the "
        "customer wants to see what is available, show_category for one named "
        "category, similar_products when they want alternatives to something, "
        "reviews for ratings or customer feedback, delivery_quote for delivery "
        "or courier cost, start_order when they want to buy, finished_selecting "
        "when they say they have added everything they want, confirm_order to "
        "submit a summarised order, change_order to correct details, "
        "order_status for an existing order's progress, new_order to start a "
        "fresh order after one was placed, greeting for a bare greeting, and "
        "unknown when nothing fits.\n"
        "Copy productQuery, categoryQuery and district verbatim from the "
        "customer's own words when they name one, otherwise leave them empty. "
        "Never invent a product, category or district that is not named in the "
        "message.\n"
        f"CONVERSATION STATE: {state}\n"
        f"PRODUCTS IN THIS STORE: {json.dumps(product_names, ensure_ascii=False)}\n"
        f"CATEGORIES: {json.dumps(category_names, ensure_ascii=False)}\n"
        'Example shape: {"intent":"product_question","productQuery":"black bag",'
        '"categoryQuery":"","district":"","language":"si"}\n\n'
        f"CUSTOMER MESSAGE:\n{message}"
    )
    result = parse_json_object(request_ai_text(prompt, max_tokens=200))

    if not result or result.get("intent") not in STOREFRONT_INTENTS:
        return None

    language = result.get("language")

    return {
        "intent": result["intent"],
        "productQuery": str(result.get("productQuery") or "").strip(),
        "categoryQuery": str(result.get("categoryQuery") or "").strip(),
        "district": str(result.get("district") or "").strip(),
        "language": language if language in CHAT_LANGUAGES else None,
    }


def generate_product_description(product_details):
    """Generate seller-editable catalogue copy from the supplied product facts."""
    settings = current_app.config
    provider = settings.get("AI_PROVIDER", "none")
    name = str(product_details.get("name", "")).strip()

    if not name:
        return None

    facts = {
        "name": name,
        "brand": product_details.get("brand"),
        "colour": product_details.get("colourName"),
        "category": product_details.get("categoryName"),
        "size": product_details.get("productSize"),
        "warrantyMonths": product_details.get("warrantyPeriodMonths"),
        "weightKg": product_details.get("weightKg"),
        "costPriceLkr": product_details.get("costPrice"),
        "sellingPriceLkr": product_details.get("sellingPrice"),
        "variants": product_details.get("variants", []),
    }
    prompt = (
        "Write a clear e-commerce product description using every non-empty specification "
        "in the supplied facts, including brand, colour, size, weight, warranty and variant "
        "options when provided. Use only the supplied facts; do not invent specifications, materials, "
        "compatibility, waterproof ratings, warranty terms, or benefits. Do not "
        "Include prices only when supplied. Do not include a heading. Return only the description.\n\n"
        f"PRODUCT FACTS:\n{json.dumps(facts, ensure_ascii=False)}"
    )

    if provider == "none" or not settings.get("AI_API_KEY") or not settings.get("AI_MODEL"):
        return None

    try:
        if provider == "gemini":
            return generate_gemini_answer(prompt, settings)
        if provider in {"groq", "cerebras", "openai-compatible"}:
            return generate_openai_compatible_answer(prompt, provider, settings)
    except Exception:
        current_app.logger.exception("Product description generation failed.")
        return None

    return None


BUSINESS_ASSISTANT_INTENTS = {
    "navigate",
    "business_summary",
    "pending_orders",
    "low_stock",
    "search_order",
    "search_product",
    "update_order_status",
    "adjust_stock",
    "export_orders",
    "export_inventory",
    "export_customers",
    "open_add_order",
    "open_add_product",
    "open_shop_sale",
    "open_add_courier",
    "open_section",
    "open_settings",
    "order_view",
    "customer_view",
    "edit_product",
    "inventory_view",
    "shop_sale_view",
    "sales_metric",
    "export_sales",
    "print_waybills",
    "print_receipts",
    "scan_waybill",
    "scan_barcode",
    "set_theme",
    "bulk_update_order_status",
    "help",
    "unknown",
}


def parse_json_object(value):
    """Extract one JSON object from an AI response, including fenced responses."""
    if not value:
        return None

    match = re.search(r"\{.*\}", value, flags=re.DOTALL)
    if not match:
        return None

    try:
        result = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None

    return result if isinstance(result, dict) else None


def generate_business_assistant_intent(message):
    """Use the configured provider only to classify a seller command.

    The returned object is treated as untrusted input. The business assistant
    service allowlists every intent, checks permissions, resolves records inside
    the current business, validates arguments and asks for confirmation before a
    write is performed.
    """
    settings = current_app.config
    provider = settings.get("AI_PROVIDER", "none")

    if provider == "none" or not settings.get("AI_API_KEY") or not settings.get("AI_MODEL"):
        return None

    prompt = (
        "Classify a Vendly seller dashboard command. The seller may write in English, Sinhala, "
        "or a natural Sinhala-English mix. Return one JSON object only; "
        "do not add Markdown or explanations. Allowed intents: business_summary, "
        "navigate, pending_orders, low_stock, search_order, search_product, "
        "update_order_status, adjust_stock, export_orders, export_inventory, "
        "open_add_order, open_add_product, open_shop_sale, open_add_courier, "
        "open_section, open_settings, order_view, customer_view, edit_product, "
        "inventory_view, export_customers, shop_sale_view, sales_metric, export_sales, "
        "print_waybills, print_receipts, scan_waybill, scan_barcode, set_theme, "
        "bulk_update_order_status, help, unknown. "
        "For navigation include page, which must be one of overview, orders, "
        "inventory, couriers, customers or analytics. "
        "Use open_add_order for a new online/delivery order, open_shop_sale for "
        "a physical-shop/counter sale, open_add_product for a new product, and "
        "open_add_courier for a new courier. Use open_section with section set to "
        "shop_sales, warranty_claims, categories, customer_messages, "
        "customer_reviews or fraud_reports. Use open_settings with section set "
        "to general, staff or billing. Use order_view for filtered/searchable "
        "order lists, customer_view for customer searches, and export_customers "
        "for a customer CSV export. "
        "For order_view, shop_sale_view, export_orders, export_sales, sales_metric, print_waybills "
        "and print_receipts include dateFrom/dateTo in YYYY-MM-DD when the seller names a date. "
        "Interpret today/yesterday using the current calendar year 2026 when no year is stated. "
        "For sales_metric set metric to revenue, total_sales, sold_items, or top_item. "
        "For set_theme use theme dark or light. For edit_product include productQuery. For inventory_view include "
        "productQuery plus optional stockStatus (in-stock, low-stock, or "
        "out-of-stock), sortBy (name, price, or stock), and sortDirection "
        "(asc or desc). "
        "Allowed order-view statuses: pending, confirmed, packed, shipped, delivered, "
        "returned, cancelled. For an order command include orderQuery, status, and courierName "
        "only when the seller explicitly names a courier. For an "
        "bulk_update_order_status must include sourceStatus, status, and optional dateFrom/dateTo. "
        "For inventory adjustment include productQuery, optional variantQuery, and a "
        "signed integer quantityChange. Never invent an ID or value that is not in "
        "the seller's message. Example shape: "
        '{"intent":"search_order","page":"","orderQuery":"VD-000012","status":"",'
        '"productQuery":"","variantQuery":"","quantityChange":0}.\n\n'
        f"SELLER MESSAGE:\n{message}"
    )

    try:
        if provider == "gemini":
            answer = generate_gemini_answer(prompt, settings)
        elif provider in {"groq", "cerebras", "openai-compatible"}:
            answer = generate_openai_compatible_answer(prompt, provider, settings)
        else:
            return None
    except Exception:
        current_app.logger.exception("Business assistant intent classification failed.")
        return None

    result = parse_json_object(answer)
    if not result or result.get("intent") not in BUSINESS_ASSISTANT_INTENTS:
        return None

    return result
