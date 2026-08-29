"""A second provider, for the one failure another provider can answer.

The free tier runs out of tokens per minute several times a day. Every AI path
degrades to a deterministic English reply when that happens, which is a worse
answer than the model would have given - so it is worth asking somewhere else
before settling for it.
"""

import httpx
import pytest
from flask import Flask

from app.services import ai_service


def app_with(**overrides):
    app = Flask(__name__)
    app.config.update({
        "AI_PROVIDER": "groq",
        "AI_API_KEY": "primary-key",
        "AI_MODEL": "primary-model",
        "AI_API_BASE_URL": "",
        "AI_TIMEOUT_SECONDS": 5,
        "AI_FALLBACK_PROVIDER": "openrouter",
        "AI_FALLBACK_API_KEY": None,
        "AI_FALLBACK_MODEL": None,
        "AI_FALLBACK_API_BASE_URL": None,
        **overrides,
    })
    return app


def raise_status(status, body="{}"):
    def raiser(*arguments, **keywords):
        request = httpx.Request("POST", "https://example.test/chat/completions")
        response = httpx.Response(status, text=body, request=request)
        raise httpx.HTTPStatusError(str(status), request=request, response=response)

    return raiser


def test_a_rate_limit_is_answered_by_the_fallback(monkeypatch):
    calls = []

    def provider(prompt, name, settings, max_tokens=1200, credentials=None, history=None):
        calls.append((name, (credentials or {}).get("model")))

        # Both calls now carry full credentials, so the model is what tells
        # them apart.
        if (credentials or {}).get("model") == "primary-model":
            raise_status(429)()

        return "answered by the fallback"

    monkeypatch.setattr(ai_service, "generate_openai_compatible_answer", provider)
    app = app_with(
        AI_FALLBACK_API_KEY="second-key",
        AI_FALLBACK_MODEL="second-model",
    )

    with app.app_context():
        assert ai_service.request_ai_text("hello") == "answered by the fallback"

    # The primary was tried first, then the fallback with its own model.
    assert calls == [("groq", "primary-model"), ("openrouter", "second-model")]


def test_without_a_fallback_configured_nothing_changes(monkeypatch):
    monkeypatch.setattr(
        ai_service, "generate_openai_compatible_answer", raise_status(429),
    )

    with app_with().app_context():
        assert ai_service.request_ai_text("hello") is None


def test_a_broken_configuration_is_not_papered_over(monkeypatch, caplog):
    import logging

    attempts = []

    def provider(prompt, name, settings, max_tokens=1200, credentials=None, history=None):
        attempts.append(name)
        raise_status(404, '{"error":{"code":"model_not_found"}}')()

    monkeypatch.setattr(ai_service, "generate_openai_compatible_answer", provider)
    app = app_with(
        AI_FALLBACK_API_KEY="second-key",
        AI_FALLBACK_MODEL="second-model",
    )

    with app.app_context(), caplog.at_level(logging.ERROR):
        assert ai_service.request_ai_text("hello") is None

    # A retired model name is a fault to fix. Answering from somewhere else
    # would leave the primary broken with nobody the wiser and the bill moving.
    assert attempts == ["groq"]
    assert "AI DISABLED" in caplog.text


def test_a_failing_fallback_does_not_replace_one_problem_with_another(monkeypatch):
    def provider(prompt, name, settings, max_tokens=1200, credentials=None, history=None):
        if (credentials or {}).get("model") == "second-model":
            raise httpx.ConnectError("the second provider is down")

        raise_status(429)()

    monkeypatch.setattr(ai_service, "generate_openai_compatible_answer", provider)
    app = app_with(
        AI_FALLBACK_API_KEY="second-key",
        AI_FALLBACK_MODEL="second-model",
    )

    with app.app_context():
        # The customer still gets the deterministic reply rather than an error.
        assert ai_service.request_ai_text("hello") is None


def test_openrouter_has_a_known_base_url():
    # Without it the fallback silently returns None, which looks exactly like
    # having no fallback configured at all.
    assert ai_service.PROVIDER_PROFILES["openrouter"]["base_url"]


def test_the_fallback_sends_its_own_key_and_model(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["auth"] = headers["Authorization"]
        captured["model"] = json["model"]

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        return Response()

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)
    app = app_with(
        AI_FALLBACK_API_KEY="second-key",
        AI_FALLBACK_MODEL="second-model",
    )

    with app.app_context():
        assert ai_service.fallback_ai_text("hello", 500) == "ok"

    # Its own credentials, not the primary's - sending the primary key to the
    # second provider would fail in a way that reads as the fallback being
    # broken.
    assert captured["auth"] == "Bearer second-key"
    assert captured["model"] == "second-model"
    assert "openrouter.ai" in captured["url"]


def models_used(monkeypatch, call, **config):
    """Record which model each AI call actually asks for."""
    used = []

    def provider(prompt, name, settings, max_tokens=1200, credentials=None, history=None):
        used.append((credentials or {}).get("model"))
        return '{"intent":"greeting","language":"en"}'

    monkeypatch.setattr(ai_service, "generate_openai_compatible_answer", provider)

    with app_with(**config).app_context():
        call()

    return used


def test_classification_uses_the_cheap_model(monkeypatch):
    # Intent runs on every single message. It reads a sentence into a label and
    # needs none of the reasoning a catalogue answer does, so it is most of the
    # token bill and the cheapest thing to move.
    used = models_used(
        monkeypatch,
        lambda: ai_service.generate_storefront_intent("hello", [], [], "browsing"),
        AI_FAST_MODEL="small-model",
    )

    assert used == ["small-model"]


def test_language_detection_and_translation_use_the_cheap_model(monkeypatch):
    for call in (
        lambda: ai_service.detect_chat_language("mata ekak ona"),
        lambda: ai_service.translate_chat_message("Your order is confirmed.", "si"),
    ):
        assert models_used(monkeypatch, call, AI_FAST_MODEL="small-model") == [
            "small-model",
        ]


def test_a_catalogue_answer_keeps_the_full_model(monkeypatch):
    # The reasoning calls are the reason a good model is configured at all.
    # Sending these to the cheap one would save tokens by making the product
    # worse, which is not the trade being made here.
    used = models_used(
        monkeypatch,
        lambda: ai_service.generate_catalogue_answer(
            "which is cheapest?", [{"name": "A", "sellingPriceMinor": 100}], "en",
        ),
        AI_FAST_MODEL="small-model",
    )

    assert used == ["primary-model"]


def test_without_a_fast_model_everything_uses_the_main_one(monkeypatch):
    # Unset, the behaviour is exactly what it was before the split.
    used = models_used(
        monkeypatch,
        lambda: ai_service.generate_storefront_intent("hello", [], [], "browsing"),
    )

    assert used == ["primary-model"]


def test_a_full_completions_url_in_the_base_setting_still_works(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        return Response()

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)
    app = app_with(**{
        "AI_FALLBACK_API_KEY": "second-key",
        "AI_FALLBACK_MODEL": "second-model",
        # What a provider's documentation shows, and therefore what gets
        # pasted in. Appending the path to it produced a doubled URL and a 404
        # that surfaced only as "fallback failed".
        "AI_FALLBACK_API_BASE_URL": "https://openrouter.ai/api/v1/chat/completions",
    })

    with app.app_context():
        assert ai_service.fallback_ai_text("hello", 100) == "ok"

    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert "chat/completions/chat/completions" not in captured["url"]


def test_a_server_error_falls_back(monkeypatch):
    # Free tiers return 502 and 503 often enough that treating them as fatal
    # would answer in English for no reason. Seen live on a free model.
    def provider(prompt, name, settings, max_tokens=1200, credentials=None, history=None):
        if (credentials or {}).get("model") == "primary-model":
            raise_status(502, "bad gateway")()

        return "answered by the fallback"

    monkeypatch.setattr(ai_service, "generate_openai_compatible_answer", provider)
    app = app_with(**{
        "AI_FALLBACK_API_KEY": "second-key",
        "AI_FALLBACK_MODEL": "second-model",
    })

    with app.app_context():
        assert ai_service.request_ai_text("hello") == "answered by the fallback"


def test_a_timeout_falls_back(monkeypatch):
    import httpx as httpx_module

    def provider(prompt, name, settings, max_tokens=1200, credentials=None, history=None):
        if (credentials or {}).get("model") == "primary-model":
            raise httpx_module.ReadTimeout("the primary took too long")

        return "answered by the fallback"

    monkeypatch.setattr(ai_service, "generate_openai_compatible_answer", provider)
    app = app_with(**{
        "AI_FALLBACK_API_KEY": "second-key",
        "AI_FALLBACK_MODEL": "second-model",
    })

    with app.app_context():
        assert ai_service.request_ai_text("hello") == "answered by the fallback"


def test_openrouter_works_as_the_primary_provider(monkeypatch):
    # It was only ever reachable as a fallback: the primary path checked a
    # hardcoded set of provider names that did not include it, so making it
    # primary turned the AI off entirely with one warning line.
    seen = {}

    def provider(prompt, name, settings, max_tokens=1200, credentials=None, history=None):
        seen["provider"] = name
        return "ok"

    monkeypatch.setattr(ai_service, "generate_openai_compatible_answer", provider)
    app = app_with(**{"AI_PROVIDER": "openrouter"})

    with app.app_context():
        assert ai_service.request_ai_text("hello") == "ok"

    assert seen["provider"] == "openrouter"


def test_openrouter_requests_suppress_reasoning(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["body"] = json

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        return Response()

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)
    app = app_with(**{"AI_PROVIDER": "openrouter"})

    with app.app_context():
        ai_service.request_ai_text("hello")

    # A reasoning model thinks inside the completion budget. On a long
    # catalogue prompt that thinking came back AS the reply, so the customer
    # read "We need to decide which is best..." instead of an answer.
    assert captured["body"]["reasoning"] == {"exclude": True}


def test_other_providers_are_not_sent_the_reasoning_flag(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["body"] = json

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        return Response()

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)

    with app_with().app_context():
        ai_service.request_ai_text("hello")

    # It is an OpenRouter parameter. Sending it to a provider that does not
    # know it risks a 400 on every single call.
    assert "reasoning" not in captured["body"]


def resolved_for(provider, **overrides):
    from app.services.ai_service import provider_credentials

    config = {
        "AI_PROVIDER": provider,
        "AI_API_KEY": "key",
        "AI_MODEL": "",
        "AI_FAST_MODEL": "",
        "AI_API_BASE_URL": "",
        "AI_TIMEOUT_SECONDS": None,
        **overrides,
    }
    return provider_credentials(config)


def test_switching_provider_switches_the_endpoint_and_the_quirks():
    # The whole point: one line in .env, and the base URL, the timeout and the
    # provider's quirks follow. Four providers, four correct configurations,
    # without four more settings the reader has to know about.
    groq = resolved_for("groq")
    router = resolved_for("openrouter")
    gemini = resolved_for("gemini")
    cerebras = resolved_for("cerebras")

    assert "groq.com" in groq["base_url"]
    assert "openrouter.ai" in router["base_url"]
    assert "googleapis.com" in gemini["base_url"]
    assert "cerebras.ai" in cerebras["base_url"]

    # Only OpenRouter's models narrate their reasoning into the reply.
    assert router["exclude_reasoning"] is True
    assert groq["exclude_reasoning"] is False
    assert gemini["exclude_reasoning"] is False

    # A free tier is slower, so it gets longer before a timeout is called.
    assert router["timeout"] > groq["timeout"]


def test_an_explicit_model_always_beats_the_suggestion():
    # A suggestion filling in over a name the seller typed would hide which of
    # the two was wrong when the call 404s.
    assert resolved_for("groq", AI_MODEL="my-own-model")["model"] == "my-own-model"
    assert resolved_for("openrouter", AI_MODEL="mine:free")["model"] == "mine:free"


def test_a_provider_with_no_suggested_model_needs_one_configured():
    # Inventing a model name for a provider whose catalogue changes weekly is
    # how every message becomes a 404.
    assert resolved_for("cerebras")["model"] == ""
    assert resolved_for("gemini")["model"] == ""


def test_the_fallback_resolves_the_same_way():
    from app.services.ai_service import provider_credentials

    resolved = provider_credentials(
        {
            "AI_PROVIDER": "openrouter",
            "AI_FALLBACK_PROVIDER": "groq",
            "AI_FALLBACK_API_KEY": "groq-key",
            "AI_FALLBACK_MODEL": "",
            "AI_FALLBACK_API_BASE_URL": "",
            "AI_TIMEOUT_SECONDS": None,
        },
        fallback=True,
    )

    # Either provider can hold either role, with the same defaults applied.
    assert "groq.com" in resolved["base_url"]
    assert resolved["model"] == "openai/gpt-oss-120b"
    assert resolved["exclude_reasoning"] is False
