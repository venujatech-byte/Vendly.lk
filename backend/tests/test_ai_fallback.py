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

    def provider(prompt, name, settings, max_tokens=1200, credentials=None):
        calls.append((name, (credentials or {}).get("model")))

        if not credentials:
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
    assert calls == [("groq", None), ("openrouter", "second-model")]


def test_without_a_fallback_configured_nothing_changes(monkeypatch):
    monkeypatch.setattr(
        ai_service, "generate_openai_compatible_answer", raise_status(429),
    )

    with app_with().app_context():
        assert ai_service.request_ai_text("hello") is None


def test_a_broken_configuration_is_not_papered_over(monkeypatch, caplog):
    import logging

    attempts = []

    def provider(prompt, name, settings, max_tokens=1200, credentials=None):
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
    def provider(prompt, name, settings, max_tokens=1200, credentials=None):
        if credentials:
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
    assert "openrouter" in ai_service.OPENAI_COMPATIBLE_BASE_URLS


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
