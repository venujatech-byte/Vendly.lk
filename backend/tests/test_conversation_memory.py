"""What the model is told about the turns before this one.

Every prompt used to be stateless. Entity memory - the selected product, the
last category, the last shown ids - carried some follow-ups, but the model
itself never saw a word of what had been said. So "and the warranty?" or "is
that one waterproof?" arrived with nothing to attach to.
"""

from app.services.ai_service import conversation_block, product_prompt


def turns():
    return [
        {"role": "customer", "text": "show me power banks"},
        {"role": "assistant", "text": "Here is what we have in PowerBanks."},
        {"role": "customer", "text": "the 20000mah one"},
    ]


def test_the_turns_are_labelled_by_who_said_them():
    block = conversation_block(turns())

    assert "Customer: show me power banks" in block
    assert "You: Here is what we have in PowerBanks." in block


def test_the_history_is_subordinate_to_the_current_message():
    # The failure this guards against is the one §23 records four times over
    # for the stored product and category: memory outranking what was just
    # asked, so the bot answers the question before last.
    block = conversation_block(turns())

    assert "never answer an earlier one instead" in block
    assert "only to work out what the customer's latest message refers to" in block


def test_an_empty_history_adds_nothing():
    # A first message must not carry an empty heading that invites the model to
    # invent context for it.
    assert conversation_block([]) == ""
    assert conversation_block(None) == ""


def test_blank_turns_are_dropped():
    block = conversation_block(
        [{"role": "customer", "text": "  "}, {"role": "customer", "text": "hello"}],
    )

    assert block.count("Customer:") == 1


def test_the_history_reaches_the_product_prompt():
    prompt = product_prompt(
        "is it waterproof?",
        {"name": "T800", "sellingPriceMinor": 130000},
        "en",
        None,
        turns(),
    )

    assert "the 20000mah one" in prompt
    # Still clearly separated from the question being answered.
    assert "CUSTOMER QUESTION:" in prompt
    assert prompt.index("CONVERSATION SO FAR") < prompt.index("CUSTOMER QUESTION:")


def test_a_prompt_without_history_is_unchanged():
    prompt = product_prompt(
        "is it waterproof?",
        {"name": "T800", "sellingPriceMinor": 130000},
        "en",
    )

    assert "CONVERSATION SO FAR" not in prompt


def test_the_real_classifier_accepts_history_and_puts_it_in_the_prompt(monkeypatch):
    """The signature bug this file failed to catch the first time.

    Every other test stubs `generate_storefront_intent`, so a caller passing an
    argument the real function does not accept passed the whole suite and threw
    a 500 on the first live message - which the browser reported as a CORS
    error, because an unhandled 500 never gets the headers.

    This calls the real function with only the HTTP boundary faked, so the
    signature and the prompt are both exercised.
    """
    from flask import Flask

    from app.services import ai_service

    captured = {}

    def fake_provider(prompt, provider, settings, max_tokens=1200, credentials=None):
        captured["prompt"] = prompt
        return '{"intent":"product_question","language":"en"}'

    monkeypatch.setattr(
        ai_service, "generate_openai_compatible_answer", fake_provider,
    )
    app = Flask(__name__)
    app.config.update({
        "AI_PROVIDER": "groq",
        "AI_API_KEY": "key",
        "AI_MODEL": "big-model",
        "AI_FAST_MODEL": "small-model",
        "AI_API_BASE_URL": "",
        "AI_TIMEOUT_SECONDS": 5,
    })

    with app.app_context():
        result = ai_service.generate_storefront_intent(
            "and the warranty?",
            ["T800 Ultra Smart Watch"],
            ["Smart watch"],
            "browsing",
            turns(),
        )

    assert result["intent"] == "product_question"
    # The history has to reach the prompt, not just be accepted and dropped.
    assert "CONVERSATION SO FAR" in captured["prompt"]
    assert "show me power banks" in captured["prompt"]
    assert "CUSTOMER MESSAGE:\nand the warranty?" in captured["prompt"]
