from app.services.ai_service import (
    ANSWERED_MARKER,
    MISSING_FACT_MARKER,
    product_prompt,
)


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


def test_product_prompt_forces_a_choice_between_both_status_markers():
    # An English "I don't know" cannot be detected in a Sinhala reply, so the
    # model reports its own certainty with a marker. Both markers are offered
    # as a forced choice: asked to append only the "no data" one, the model
    # added it to answers it had fully answered and paged the seller for
    # nothing.
    prompt = product_prompt("Does it support SIM?", sample_product(), "si")

    assert MISSING_FACT_MARKER in prompt
    assert ANSWERED_MARKER in prompt
    assert "never both and never neither" in prompt
    assert "not provided that information yet" in prompt


def test_a_configuration_error_is_logged_as_one_actionable_line(caplog, monkeypatch):
    import logging

    import httpx
    from flask import Flask

    from app.services import ai_service

    app = Flask(__name__)
    app.config.update(
        AI_PROVIDER="groq",
        AI_API_KEY="key",
        AI_MODEL="retired-model",
        AI_API_BASE_URL="",
        AI_TIMEOUT_SECONDS=5,
    )

    def raise_model_not_found(*arguments, **keywords):
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        response = httpx.Response(404, text='{"error":{"code":"model_not_found"}}', request=request)
        raise httpx.HTTPStatusError("404", request=request, response=response)

    monkeypatch.setattr(
        ai_service,
        "generate_openai_compatible_answer",
        raise_model_not_found,
    )

    with app.app_context(), caplog.at_level(logging.ERROR):
        assert ai_service.request_ai_text("hello") is None

    # A retired model name never recovers on its own, and every chat reply
    # silently drops back to English until someone notices. It must not be
    # buried among transient stack traces.
    assert "AI DISABLED" in caplog.text
    assert "retired-model" in caplog.text


def test_catalogue_context_lets_the_model_compare_real_products():
    from app.services.ai_service import product_prompt

    others = [
        {"name": "LP40 Pro", "sellingPriceMinor": 280000, "categoryName": "Earbuds"},
    ]
    prompt = product_prompt("which is cheaper?", sample_product(), "en", others)

    # A single product cannot answer a comparison. The alternatives are named
    # and priced so the model compares against the real catalogue.
    assert "LP40 Pro" in prompt
    assert "LKR 2,800.00" in prompt
    assert "Never mention a product that is not listed" in prompt


def test_prices_are_supplied_both_to_compare_with_and_to_quote():
    from app.services.ai_service import catalogue_entry, money_text, product_facts

    facts = product_facts({"name": "Watch", "sellingPriceMinor": 190000})

    # priceLkr is numeric so "cheapest" comparisons are arithmetic, priceText
    # is formatted so the customer never reads back "LKR 1900.0".
    assert facts["priceLkr"] == 1900.0
    assert facts["priceText"] == "LKR 1,900.00"
    assert catalogue_entry({"sellingPriceMinor": 45000})["priceText"] == "LKR 450.00"
    assert money_text(0) == "LKR 0.00"
    assert money_text(None) == "LKR 0.00"


def test_structured_seller_fields_reach_the_prompt():
    from app.services.ai_service import product_facts

    # These live as structured fields, not prose. Before they were exposed the
    # bot could not answer "what is the warranty" whatever the model did.
    facts = product_facts(
        {
            "name": "Watch",
            "warrantyPeriodMonths": 12,
            "productSize": "42mm",
            "weightGrams": 300,
            "availableStock": 4,
        },
    )

    assert facts["warrantyMonths"] == 12
    assert facts["size"] == "42mm"
    assert facts["weightKg"] == 0.3
    assert facts["inStock"] is True


def test_catalogue_answer_needs_products():
    from app.services.ai_service import generate_catalogue_answer

    assert generate_catalogue_answer("anything cheap?", [], "en") is None


def provider_app():
    from flask import Flask

    app = Flask(__name__)
    app.config.update(
        AI_PROVIDER="groq",
        AI_API_KEY="key",
        AI_MODEL="a-model",
        AI_API_BASE_URL="",
        AI_TIMEOUT_SECONDS=5,
    )
    return app


def raise_status(status, body):
    import httpx

    def raiser(*arguments, **keywords):
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        response = httpx.Response(status, text=body, request=request)
        raise httpx.HTTPStatusError(str(status), request=request, response=response)

    return raiser


def test_a_rate_limit_is_not_reported_as_a_broken_configuration(caplog, monkeypatch):
    import logging

    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "generate_openai_compatible_answer",
        raise_status(429, '{"error":{"message":"tokens per minute"}}'),
    )

    with provider_app().app_context(), caplog.at_level(logging.WARNING):
        assert ai_service.request_ai_text("hello") is None

    # 429 clears on its own. Calling it a broken configuration sends someone
    # editing a model name that was never wrong.
    assert "AI RATE LIMITED" in caplog.text
    assert "AI DISABLED" not in caplog.text


def test_store_policies_are_the_only_source_for_policy_answers():
    from app.services.ai_service import catalogue_prompt

    prompt = catalogue_prompt(
        "do you accept cash on delivery?",
        [{"name": "Watch", "sellingPriceMinor": 190000}],
        "en",
        "Payment: Cash on delivery island-wide.",
    )

    assert "Cash on delivery island-wide" in prompt
    assert "only from this text" in prompt
    assert "never invent a price, a warranty, a feature or a shop policy" in prompt


def test_the_policy_block_is_omitted_when_the_seller_wrote_nothing():
    from app.services.ai_service import catalogue_prompt

    prompt = catalogue_prompt("do you accept cash on delivery?", [], "en", "   ")

    assert "STORE POLICIES" not in prompt


def test_a_policy_question_is_answerable_without_any_products():
    from app.services import ai_service

    calls = []
    original = ai_service.request_ai_text
    ai_service.request_ai_text = lambda prompt, **kw: calls.append(prompt) or "ok"
    try:
        # A shop with an empty catalogue can still answer "what are your hours".
        assert ai_service.generate_catalogue_answer("hours?", [], "en", "9am to 6pm") == "ok"
        assert ai_service.generate_catalogue_answer("hours?", [], "en", "") is None
    finally:
        ai_service.request_ai_text = original

    assert len(calls) == 1
