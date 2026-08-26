from app.services.ai_service import MISSING_FACT_MARKER, product_prompt


def sample_product():
    return {
        "name": "Watch",
        "description": "IP67 water resistance",
        "sellingPriceMinor": 200000,
        "variants": [],
    }


def test_product_prompt_contains_guardrails_and_seller_facts():
    prompt = product_prompt("Is it waterproof?", sample_product())

    assert "IP67 water resistance" in prompt
    assert "Never invent features" in prompt
    assert "Is it waterproof?" in prompt
    assert "real seller" in prompt
    assert "three short sentences" in prompt
    assert "no web-search tool is connected" in prompt


def test_product_prompt_asks_for_one_language_only():
    # Replying in two languages at once made every English customer read
    # Sinhala too. The customer's own language is now the only one used.
    english = product_prompt("Is it waterproof?", sample_product(), "en")
    sinhala = product_prompt("Is it waterproof?", sample_product(), "si")
    tamil = product_prompt("Is it waterproof?", sample_product(), "ta")

    assert "Reply only in English" in english
    assert "Reply only in Sinhala" in sinhala
    assert "Sinhala" not in english
    assert "Reply only in Tamil" in tamil
    assert "Sinhala" not in tamil


def test_product_prompt_defaults_to_english():
    assert "Reply only in English" in product_prompt("Size?", sample_product())


def test_product_prompt_requests_a_language_neutral_uncertainty_marker():
    # An English "I don't know" cannot be detected in a Sinhala reply, so the
    # model flags missing facts with a marker instead.
    prompt = product_prompt("Does it support SIM?", sample_product(), "si")

    assert MISSING_FACT_MARKER in prompt
    assert "not provided that information yet" in prompt
