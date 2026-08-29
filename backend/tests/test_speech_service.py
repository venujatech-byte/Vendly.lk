import pytest
from flask import Flask

from app.core.errors import ApiError
from app.services import speech_service


class FakeResponse:
    status_code = 200
    is_success = True

    def json(self):
        return {
            "text": "Show packed orders",
            "language": "en",
            "duration": 2.4,
        }


def speech_app(**overrides):
    app = Flask(__name__)
    config = {
        "GROQ_API_KEY": "test-key",
        "GROQ_TRANSCRIPTION_MODEL": "whisper-large-v3",
        "GROQ_TRANSCRIPTION_URL": "https://example.test/transcriptions",
        "GROQ_TRANSCRIPTION_TIMEOUT_SECONDS": 12,
    }
    config.update(overrides)
    app.config.update(config)
    return app


def test_transcription_uses_automatic_language_detection(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(speech_service.httpx, "post", fake_post)

    with speech_app().app_context():
        result = speech_service.transcribe_business_assistant_audio(
            b"browser-opus-audio",
            filename="command.webm",
            content_type="audio/webm;codecs=opus",
        )

    assert result["text"] == "Show packed orders"
    assert result["model"] == "whisper-large-v3"
    assert "language" not in captured["data"]
    assert "prompt" not in captured["data"]
    assert captured["data"]["model"] == "whisper-large-v3"
    assert captured["files"]["file"] == (
        "command.webm",
        b"browser-opus-audio",
        "audio/webm",
    )


def test_transcription_can_still_use_an_explicit_language(monkeypatch):
    captured = {}

    def fake_post(_url, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(speech_service.httpx, "post", fake_post)

    with speech_app().app_context():
        speech_service.transcribe_business_assistant_audio(
            b"browser-opus-audio",
            language="si-LK",
        )

    assert captured["data"]["language"] == "si"


def test_transcription_requires_server_side_groq_key():
    with speech_app(GROQ_API_KEY=None).app_context():
        with pytest.raises(ApiError) as captured:
            speech_service.transcribe_business_assistant_audio(b"audio")

    assert captured.value.code == "speech_not_configured"
    assert captured.value.status_code == 503


def test_transcription_rejects_unsupported_files_before_network_call(monkeypatch):
    def unexpected_post(*_args, **_kwargs):
        raise AssertionError("The network must not be called for an invalid file.")

    monkeypatch.setattr(speech_service.httpx, "post", unexpected_post)

    with speech_app().app_context():
        with pytest.raises(ApiError) as captured:
            speech_service.transcribe_business_assistant_audio(
                b"not-audio",
                filename="command.txt",
                content_type="text/plain",
            )

    assert captured.value.code == "unsupported_audio_type"
    assert captured.value.status_code == 415
