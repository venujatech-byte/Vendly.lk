import json
import re
from datetime import datetime, timezone

import httpx
from flask import current_app


OPENAI_COMPATIBLE_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


CHAT_LANGUAGES = {"en", "si", "ta"}

# The model replies in the customer's language, so the chat service cannot spot
# "I don't know" by matching English phrases. It ends every answer with one of
# these markers instead, and the marker is stripped before the customer sees it.
#
# It is a forced choice between two markers rather than "append this one when
# unsure", because an optional marker gets over-applied: the model appended it
# to answers it had fully answered, which paged the seller for nothing.
MISSING_FACT_MARKER = "[NO_DATA]"
ANSWERED_MARKER = "[ANSWERED]"

LANGUAGE_NAMES = {"en": "English", "si": "Sinhala", "ta": "Tamil"}


def language_instruction(language):
    """Tell the model which single language the customer is speaking."""
    name = LANGUAGE_NAMES.get(language, "English")
    return (
        f"The customer is writing in {name}. Reply only in {name}, and keep "
        "using it for the whole conversation. Do not add an English translation "
        f"unless {name} is English. "
        "Write the way Sri Lankan shoppers actually text: keep common "
        "English product, tech and commerce words in English rather than "
        "translating them - items, delivery, order, battery, warranty, "
        "Bluetooth, charging, stock, size. A heavily formal translation "
        "reads as machine output and is harder to follow than the mixed "
        "wording people use themselves."
    )


def money_text(minor_units):
    """Format minor units the way the customer should read them back."""
    return f"LKR {(minor_units or 0) / 100:,.2f}"


def product_facts(product):
    """Every seller-entered fact about one product, in one JSON-ready shape."""
    return {
        "name": product.get("name"),
        "brand": product.get("brand"),
        "colour": product.get("colourName"),
        "category": product.get("categoryName"),
        "description": product.get("description"),
        "sellerAiDescription": product.get("aiDescription"),
        # priceLkr is the number to compare with; priceText is the string to
        # quote back. Without the formatted form the model echoes the raw float
        # and the customer reads "LKR 1900.0".
        "priceLkr": product.get("sellingPriceMinor", 0) / 100,
        "priceText": money_text(product.get("sellingPriceMinor", 0)),
        "wasPriceLkr": (product.get("compareAtPriceMinor") or 0) / 100 or None,
        "warrantyMonths": product.get("warrantyPeriodMonths") or None,
        "size": product.get("productSize") or None,
        "weightKg": (product.get("weightGrams") or 0) / 1000 or None,
        "inStock": product.get("availableStock", 0) > 0,
        "variants": [
            {
                "size": variant.get("size"),
                "priceLkr": (variant.get("sellingPriceMinor") or 0) / 100 or None,
                "inStock": variant.get("availableStock", 0) > 0,
            }
            for variant in product.get("variants", [])
        ],
        "approvedReviewCount": product.get("approvedReviewCount", 0),
        "approvedReviewSnippets": product.get("approvedReviewSnippets", []),
    }


def catalogue_entry(product):
    """A compact row for comparison questions.

    The description is included, trimmed. Without it the model cannot answer
    "which of these supports a SIM?" across products - it would only see names
    and prices, so it either guessed or listed everything regardless.
    """
    description = " ".join(
        str(
            product.get("description") or product.get("aiDescription") or "",
        ).split(),
    )
    return {
        "name": product.get("name"),
        "category": product.get("categoryName"),
        "brand": product.get("brand"),
        "colour": product.get("colourName") or None,
        "size": product.get("productSize") or None,
        "description": description[:400] or None,
        "priceLkr": product.get("sellingPriceMinor", 0) / 100,
        "priceText": money_text(product.get("sellingPriceMinor", 0)),
        "warrantyMonths": product.get("warrantyPeriodMonths") or None,
        "inStock": product.get("availableStock", 0) > 0,
    }


def product_prompt(question, product, language="en", other_products=None):
    context = product_facts(product)
    # Questions like "which is cheaper", "what is the difference between these
    # two" and "anything under 3000" cannot be answered from a single product.
    # These rows are named and priced so the model can compare against real
    # catalogue items instead of guessing at ones it half-remembers.
    catalogue = [catalogue_entry(item) for item in (other_products or [])]
    catalogue_block = (
        "OTHER PRODUCTS THIS SELLER HAS (compare against these, and recommend "
        "them by name when the customer asks for an alternative, a cheaper "
        "option or a comparison. Never mention a product that is not listed "
        f"here or in PRODUCT FACTS):\n{json.dumps(catalogue, ensure_ascii=False)}\n\n"
        if catalogue
        else ""
    )
    return (
        "You are Vendly's friendly order-taking product assistant for a small "
        "Sri Lankan online business. Chat naturally and briefly, like a real seller "
        f"replying on Messenger. {language_instruction(language)} "
        "Use no more than three short sentences in total. "
        "Use only the seller-provided JSON facts below. Never invent features, "
        "warranties, waterproof ratings, SIM support, video support, reviews, or "
        "availability. If the facts do not answer the question, say the seller has "
        "not provided that information yet.\n"
        "Always write prices back to the customer exactly as they appear in "
        "priceText, never as a bare decimal.\n"
        "End every reply with exactly one status marker on the same line, and "
        "nothing after it. Use "
        f"{ANSWERED_MARKER} when the facts above answered the customer's "
        f"question. Use {MISSING_FACT_MARKER} only when they did not. Choose one; "
        "never both and never neither.\n"
        "Do not claim to have searched or verified "
        "information on the internet because no web-search tool is connected. Mention "
        "that delivery is calculated from district and total order weight when relevant.\n\n"
        f"PRODUCT FACTS:\n{json.dumps(context, ensure_ascii=False)}\n\n"
        f"{catalogue_block}"
        f"CUSTOMER QUESTION:\n{question}"
    )


def generate_openai_compatible_answer(
    prompt,
    provider,
    settings,
    max_tokens=1200,
    credentials=None,
):
    """Call any OpenAI-compatible chat endpoint.

    `credentials` lets a second provider reuse this exact code path: the
    fallback differs only in its key, model and base URL, and giving it its own
    copy of the request would be two places to fix the day a header changes.
    """
    api_key = (credentials or {}).get("api_key") or settings.get("AI_API_KEY")
    model = (credentials or {}).get("model") or settings.get("AI_MODEL")
    base_url = (
        (credentials or {}).get("base_url")
        or settings.get("AI_API_BASE_URL")
        or OPENAI_COMPATIBLE_BASE_URLS.get(provider)
    )

    if not base_url:
        return None

    response = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
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


def generate_product_answer(question, product, language="en", other_products=None):
    """Return an optional AI answer; failures safely fall back to deterministic chat."""
    return request_ai_text(
        product_prompt(question, product, language, other_products),
    )


def catalogue_prompt(question, products, language="en", store_policies=""):
    catalogue = [catalogue_entry(product) for product in products]
    # The seller's own policy text. Without it the model has nothing to answer
    # "do you accept cash on delivery" from, and inventing a returns policy on
    # a shop's behalf is worse than admitting it is not written down.
    policy_block = (
        "STORE POLICIES, in the seller's own words. Answer questions about "
        "returns, refunds, exchanges, payment, cash on delivery and opening "
        "hours only from this text. If it does not cover what was asked, say "
        f"the seller has not stated it:\n{store_policies.strip()}\n\n"
        if str(store_policies or "").strip()
        else ""
    )
    return (
        "You are Vendly's friendly order-taking assistant for a small Sri "
        f"Lankan online business. {language_instruction(language)} "
        "Use no more than three short sentences.\n"
        f"Answer using only the {'CATALOGUE and STORE POLICIES' if policy_block else 'CATALOGUE'} "
        "below. The catalogue is the seller's complete list of available "
        "products. Never mention a product that is not in it, and never invent "
        "a price, a warranty, a feature or a shop policy.\n"
        "Check the description of each product before answering a question "
        "about a feature. If none of them has it, say so plainly and do not "
        "list products that do not match - naming products under a question "
        "they fail to answer reads as though they qualify.\n"
        "When the customer asks which of several products is better, "
        "compare their specifications and name one, with a short reason "
        "drawn from those specifications. If the descriptions do not "
        "separate them, do not pick arbitrarily - lay the differences out "
        "as a short markdown table, one row per specification, and let the "
        "customer choose.\n"
        "Name the specific products that answer the question, with their "
        "prices. Compare using priceLkr, but always write prices back to the "
        "customer exactly as they appear in priceText, never as a bare "
        "decimal. For a cheapest, dearest or budget question, name the ones "
        "that actually match.\n"
        "End every reply with exactly one status marker on the same line, and "
        f"nothing after it. Use {ANSWERED_MARKER} when the catalogue answered "
        f"the question, or {MISSING_FACT_MARKER} when nothing in it matches. "
        "Choose one; never both and never neither.\n\n"
        f"CATALOGUE:\n{json.dumps(catalogue, ensure_ascii=False)}\n\n"
        f"{policy_block}"
        f"CUSTOMER QUESTION:\n{question}"
    )


def generate_catalogue_answer(question, products, language="en", store_policies=""):
    """Answer a question that spans the catalogue, or asks how the shop works.

    "What is your cheapest earbud", "anything under 3000", "do you accept cash
    on delivery" and "can I return it" name no single product, so the
    single-product path used to fall through to a generic prompt.
    """
    if not products and not str(store_policies or "").strip():
        return None

    return request_ai_text(
        catalogue_prompt(question, products, language, store_policies),
    )



def comparison_prompt(products, language="en"):
    """Ask for a comparison table and nothing else.

    The catalogue prompt treats a table as the fallback for when it cannot
    pick a winner. An explicit "compare these" is the opposite: the table IS
    the answer, and a recommendation the customer did not ask for buries the
    differences they wanted to read.
    """
    catalogue = [catalogue_entry(product) for product in products]
    names = ", ".join(product.get("name", "") for product in products)
    return (
        "You are Vendly's assistant for a small Sri Lankan online business. "
        f"{language_instruction(language)}\n"
        "The customer asked to compare these products: "
        f"{names}.\n"
        "Reply with ONE markdown table and no other text - no introduction, "
        "no summary, no recommendation. They asked to compare, not to be told "
        "what to buy.\n"
        "Layout: the first column is the feature name, then one column per "
        "product, in the order listed above. The first row of the table must "
        "be the header naming each product.\n"
        "Choose the rows yourself by reading every description below and "
        "pulling out the features they actually discuss - battery capacity, "
        "charging speed, driver size, noise cancelling, water resistance, "
        "connectivity, whatever the seller wrote about. Always include Price, "
        "and include Warranty and Availability when the data has them.\n"
        "Use a feature only if at least one product states it. Where a product "
        "does not state it, put a dash. Never invent a value, and never carry "
        "a value across from another product.\n"
        "Write prices exactly as they appear in priceText, never as a bare "
        "decimal. Keep every cell short - a few words, not a sentence.\n\n"
        f"PRODUCTS:\n{json.dumps(catalogue, ensure_ascii=False)}"
    )


def generate_comparison_answer(products, language="en"):
    """A feature table for an explicit comparison request."""
    if len(products or []) < 2:
        return None

    return request_ai_text(
        comparison_prompt(products, language),
        max_tokens=1500,
    )
# The last provider failure, so the dashboard can show that the chatbot has
# quietly dropped back to simplified English replies. A log line is only read
# by someone already looking; a seller has no other way to find out.
# ponytail: process-local. A dead model fails on every worker within seconds,
# so any one of them has the answer. Move to Firestore only if that stops
# holding.
_LAST_AI_FAILURE = {"failure": None}


def record_ai_failure(kind, provider, model):
    _LAST_AI_FAILURE["failure"] = {
        "kind": kind,
        "provider": provider,
        "model": model,
        "at": datetime.now(timezone.utc).isoformat(),
    }


def ai_status():
    """Report whether AI is configured and working. Never exposes the API key."""
    settings = current_app.config
    provider = settings.get("AI_PROVIDER", "none")
    is_configured = (
        provider != "none"
        and bool(settings.get("AI_API_KEY"))
        and bool(settings.get("AI_MODEL"))
    )

    return {
        "configured": is_configured,
        "provider": provider if is_configured else "none",
        "model": settings.get("AI_MODEL", "") if is_configured else "",
        # An intentionally disabled provider is not a fault worth alarming over.
        "failure": _LAST_AI_FAILURE["failure"] if is_configured else None,
    }


def fallback_ai_text(prompt, max_tokens):
    """Ask the second provider, when the first one is rate limited.

    Only for 429. A wrong model name or a revoked key is a fault to fix, and
    quietly answering from somewhere else would hide it - the first provider
    would stay broken and nobody would know why the bill moved.

    Returns None when no fallback is configured, so a shop that has not set one
    behaves exactly as before.
    """
    settings = current_app.config
    provider = settings.get("AI_FALLBACK_PROVIDER", "none")
    api_key = settings.get("AI_FALLBACK_API_KEY")
    model = settings.get("AI_FALLBACK_MODEL")

    if provider in {"none", "", None} or not api_key or not model:
        return None

    try:
        answer = generate_openai_compatible_answer(
            prompt,
            provider,
            settings,
            max_tokens=max_tokens,
            credentials={
                "api_key": api_key,
                "model": model,
                "base_url": settings.get("AI_FALLBACK_API_BASE_URL"),
            },
        )
    except Exception:
        # The fallback failing is not news: the customer is already getting the
        # deterministic reply, and the rate limit that caused this is logged by
        # the caller. Raising here would replace one provider's problem with
        # another's.
        current_app.logger.warning(
            "AI FALLBACK FAILED - provider %r model %r could not answer either.",
            provider,
            model,
        )
        return None

    if answer:
        current_app.logger.info(
            "AI FALLBACK USED - the primary provider was rate limited, so %r "
            "answered with %r.",
            provider,
            model,
        )

    return answer


def request_ai_text(prompt, max_tokens=1200, task="answer"):
    """Send one prompt to the configured provider, or None when unavailable.

    `task="classify"` marks the mechanical work - reading an intent, naming a
    language, translating a sentence the code already wrote. Those run on
    every single message and do not need the model that reasons about a
    catalogue, so they go to `AI_FAST_MODEL` when one is set. Classification is
    the bulk of the traffic, so this is most of the token bill.
    """
    settings = current_app.config
    provider = settings.get("AI_PROVIDER", "none")
    fast_model = settings.get("AI_FAST_MODEL")
    model = fast_model if task == "classify" and fast_model else settings.get("AI_MODEL")

    if provider == "none" or not settings.get("AI_API_KEY") or not settings.get("AI_MODEL"):
        return None

    try:
        if provider == "gemini":
            answer = generate_gemini_answer(prompt, settings)
        elif provider in {"groq", "cerebras", "openai-compatible"}:
            answer = generate_openai_compatible_answer(
                prompt,
                provider,
                settings,
                max_tokens=max_tokens,
                credentials={"model": model},
            )
        else:
            current_app.logger.warning("Unsupported AI_PROVIDER value: %s", provider)
            return None
    except httpx.HTTPStatusError as error:
        # 429 is a quota or rate limit. It clears on its own, so it must not be
        # reported as a broken configuration - that sends someone editing a
        # model name that was never wrong.
        if error.response.status_code == 429:
            # Try the second provider before giving up. A rate limit is the one
            # failure another provider can actually answer through.
            answer = fallback_ai_text(prompt, max_tokens)

            if answer:
                return answer

            record_ai_failure("rate_limit", provider, model)
            current_app.logger.warning(
                "AI RATE LIMITED - provider %r throttled model %r. This reply "
                "fell back to English; it should recover without any change. "
                "Details: %s",
                provider,
                model,
                error.response.text[:200],
            )
            return None

        # Any other 4xx is a configuration fault, not a blip: a wrong model
        # name, a revoked key or an unavailable model. It never recovers on its
        # own, and until it is fixed every reply silently drops back to
        # English. It is logged as one actionable line rather than a stack
        # trace so it is not lost among transient failures.
        if 400 <= error.response.status_code < 500:
            record_ai_failure("configuration", provider, model)
            current_app.logger.error(
                "AI DISABLED - provider %r rejected model %r with HTTP %s: %s. "
                "The chatbot is falling back to English deterministic replies "
                "until AI_MODEL or AI_API_KEY is corrected.",
                provider,
                model,
                error.response.status_code,
                error.response.text[:200],
            )
            return None

        record_ai_failure("unavailable", provider, model)
        current_app.logger.exception("The configured AI provider request failed.")
        return None
    except Exception:  # External SDKs use provider-specific exception classes.
        record_ai_failure("unavailable", provider, settings.get("AI_MODEL"))
        current_app.logger.exception("The configured AI provider request failed.")
        return None

    # A success means whatever was wrong is over. Leaving a stale warning up is
    # how a banner becomes something people learn to ignore.
    _LAST_AI_FAILURE["failure"] = None
    return answer


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
    answer = request_ai_text(prompt, max_tokens=600, task="classify")

    if not answer:
        return None

    codes = re.findall(r"(en|si|ta)", str(answer).casefold())
    return codes[-1] if codes else None


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
        "Leave every proper noun in Latin script exactly as written: product "
        "names, brand names, courier names, district and city names, order "
        "numbers, waybill numbers and email addresses. Do NOT transliterate "
        "them into another script and do NOT translate their meaning. A "
        "transliterated district name stops matching the delivery price list.\n"
        "Leave all numbers, prices, currency codes such as LKR, weights and "
        "units exactly as written.\n"
        "Any word or phrase inside single quotes is a command the customer must "
        "type back to the system. Keep those in English inside their quotes, and "
        "translate only the words around them.\n"
        "Keep the tone of a polite Sri Lankan shop assistant.\n\n"
        f"MESSAGE:\n{clean_text}"
    )
    translation = request_ai_text(prompt, max_tokens=1500, task="classify")

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
    "show_cart",
    "show_catalog",
    "show_category",
    "similar_products",
    "reviews",
    "delivery_quote",
    "cancel_order",
    "location_question",
    "payment_question",
    "policy_question",
    "set_quantity",
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
        "customer wants to see what is available, show_cart when they ask what "
        "is in their cart, basket or order so far, show_category for one named "
        "category, similar_products when they want alternatives to something, "
        "location_question when they ask where the shop is, for its address, "
        "or whether they can visit in person, "
        "reviews for ratings or customer feedback, payment_question when they "
        "ask how to pay or about a bank transfer, deposit or advance, "
        "delivery_quote for delivery "
        "cost or delivery time, policy_question for how the shop operates rather than "
        "what it sells - returns, refunds, exchanges, warranty claims, cash on "
        "delivery, payment methods, opening hours and contact - start_order "
        "when they want to buy, finished_selecting "
        "when they say they have added everything they want, confirm_order to "
        "submit a summarised order, change_order to correct details, "
        "order_status for an existing order's progress, cancel_order when they ""want to call off an order they already placed, new_order to start a "
        "fresh order after one was placed, greeting for a bare greeting, and "
        "unknown when nothing fits.\n"
        "Copy productQuery, categoryQuery, sizeQuery and district verbatim from "
        "the customer's own words when they name one, otherwise leave them "
        "empty. Never invent a product, category, size or district that is not "
        "named in the message.\n"
        "Set quantity to how many units the customer asked for, as a whole "
        "number. Sinhala and Tamil attach the count to the noun - 'dekak' and "
        "'2ak' are 2, 'thunak' is 3, 'ekak' is 1. Use 0 when no quantity is "
        "stated; never guess one.\n"
        "Set quantityMode to say what that number means. Use \"total\" when the "
        "customer states how many they want altogether - 'mata 3k ona' (I want "
        "3), 'okkoma 3k' (3 in all), 'make it 3'. Use \"add\" only when they ask "
        "for that many MORE on top of what is already in the order - 'thawa "
        "dekak' (2 more), 'another one', 'add 2 more'. When in doubt use "
        "\"total\": adding when the customer meant a total silently overcharges "
        "them.\n"
        "Use set_quantity when the customer is correcting or changing how many "
        "of something they already added, rather than choosing a new product. "
        "'thawa 3k neme, okkoma 3k' (not 3 more - 3 in total), 'make it 2', "
        "'I only want 1' and 'remove it' are all set_quantity. Use quantity 0 "
        "for removing an item.\n"
        f"CONVERSATION STATE: {state}\n"
        f"PRODUCTS IN THIS STORE: {json.dumps(product_names, ensure_ascii=False)}\n"
        f"CATEGORIES: {json.dumps(category_names, ensure_ascii=False)}\n"
        'Example shape: {"intent":"start_order","productQuery":"black bag",'
        '"categoryQuery":"","sizeQuery":"XL","quantity":2,'
        '"quantityMode":"total","district":"","language":"si"}\n\n'
        f"CUSTOMER MESSAGE:\n{message}"
    )
    result = parse_json_object(
        request_ai_text(prompt, max_tokens=1200, task="classify"),
    )

    if not result or result.get("intent") not in STOREFRONT_INTENTS:
        return None

    language = result.get("language")

    try:
        quantity = int(result.get("quantity") or 0)
    except (TypeError, ValueError):
        quantity = 0

    return {
        "intent": result["intent"],
        "productQuery": str(result.get("productQuery") or "").strip(),
        "categoryQuery": str(result.get("categoryQuery") or "").strip(),
        "sizeQuery": str(result.get("sizeQuery") or "").strip(),
        # Clamped here so a hallucinated 9999 cannot reach the cart.
        "quantity": max(0, min(quantity, 99)),
        # "total" is the safe default: treating a stated total as an addition
        # silently puts more in the customer's order than they asked for.
        "quantityMode": (
            "add" if str(result.get("quantityMode") or "").strip().casefold() == "add"
            else "total"
        ),
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

    return request_ai_text(prompt)


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

    result = parse_json_object(request_ai_text(prompt, task="classify"))
    if not result or result.get("intent") not in BUSINESS_ASSISTANT_INTENTS:
        return None

    return result
