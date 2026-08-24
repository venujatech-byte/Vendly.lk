from app.services.ai_service import product_prompt


def test_product_prompt_contains_guardrails_and_seller_facts():
    prompt = product_prompt(
        "Is it waterproof?",
        {
            "name": "Watch",
            "description": "IP67 water resistance",
            "sellingPriceMinor": 200000,
            "variants": [],
        },
    )

    assert "IP67 water resistance" in prompt
    assert "Never invent features" in prompt
    assert "Is it waterproof?" in prompt
    assert "real seller" in prompt
    assert "English and Sinhala" in prompt
    assert "three short sentences" in prompt
    assert "no web-search tool is connected" in prompt
