import json

import httpx
from flask import current_app


OPENAI_COMPATIBLE_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
}


def product_prompt(question, product):
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
        "replying on Messenger. Reply in both English and Sinhala when possible, "
        "using no more than three short sentences in total. "
        "Only discuss the product supplied in PRODUCT FACTS. Do not claim that the "
        "seller carries another product unless it is supplied by the Vendly catalogue. "
        "Use only the seller-provided JSON facts below. Never invent features, "
        "warranties, waterproof ratings, SIM support, video support, reviews, or "
        "availability. If the facts do not answer the question, say the seller has "
        "not provided that information yet. Do not claim to have searched or verified "
        "information on the internet because no web-search tool is connected. Mention "
        "that delivery is calculated from district and total order weight when relevant.\n\n"
        f"PRODUCT FACTS:\n{json.dumps(context, ensure_ascii=False)}\n\n"
        f"CUSTOMER QUESTION:\n{question}"
    )


def generate_openai_compatible_answer(prompt, provider, settings):
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
            "max_tokens": 350,
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


def generate_product_answer(question, product):
    """Return an optional AI answer; failures safely fall back to deterministic chat."""
    settings = current_app.config
    provider = settings.get("AI_PROVIDER", "none")

    if provider == "none" or not settings.get("AI_API_KEY") or not settings.get("AI_MODEL"):
        return None

    prompt = product_prompt(question, product)

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
