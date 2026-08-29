"""What the model is told about the turns before this one.

Every prompt used to be stateless. Entity memory - the selected product, the
last category, the last shown ids - carried some follow-ups, but the model
itself never saw a word of what had been said. So "and the warranty?" or "is
that one waterproof?" arrived with nothing to attach to.
"""

from app.services.ai_service import conversation_block


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


def test_the_history_becomes_real_chat_turns():
    from app.services.ai_service import history_messages

    messages = history_messages(turns())

    # Not a paragraph describing a conversation - the turns themselves, with
    # the roles a chat model expects. This is the difference between telling a
    # model about a conversation and letting it read one.
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[0]["content"] == "show me power banks"
    assert messages[2]["content"] == "the 20000mah one"


def test_blank_and_missing_history_produce_no_turns():
    from app.services.ai_service import history_messages

    assert history_messages(None) == []
    assert history_messages([]) == []
    assert history_messages([{"role": "customer", "text": "  "}]) == []


def test_the_turns_are_sent_before_the_question():
    from flask import Flask

    from app.services import ai_service

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["messages"] = json["messages"]

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        return Response()

    monkeypatch_target = ai_service.httpx
    original_post = monkeypatch_target.post
    monkeypatch_target.post = fake_post
    app = Flask(__name__)
    app.config.update({
        "AI_PROVIDER": "groq", "AI_API_KEY": "k", "AI_MODEL": "m",
        "AI_API_BASE_URL": "", "AI_TIMEOUT_SECONDS": 5,
    })

    try:
        with app.app_context():
            ai_service.request_ai_text("What is the warranty?", history=turns())
    finally:
        monkeypatch_target.post = original_post

    roles = [m["role"] for m in captured["messages"]]

    # system, the conversation, then the working context and the question.
    assert roles == ["system", "user", "assistant", "user", "user"]
    assert captured["messages"][-1]["content"] == "What is the warranty?"


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

    def fake_provider(
        prompt,
        provider,
        settings,
        max_tokens=1200,
        credentials=None,
        history=None,
    ):
        captured["prompt"] = prompt
        captured["history"] = list(history or [])
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
    # The turns have to reach the request, not just be accepted and dropped.
    assert [turn["text"] for turn in captured["history"]] == [
        "show me power banks",
        "Here is what we have in PowerBanks.",
        "the 20000mah one",
    ]
    assert "CUSTOMER MESSAGE:\nand the warranty?" in captured["prompt"]
