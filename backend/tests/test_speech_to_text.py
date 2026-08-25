from io import BytesIO

import httpx
import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

from app.core.errors import ApiError
from app.services import speech_to_text_service


def test_transcribe_audio_sends_recording_to_groq(monkeypatch):
    app = Flask(__name__)
    app.config.update(
        GROQ_API_KEY="test-key",
        GROQ_TRANSCRIPTION_MODEL="whisper-large-v3-turbo",
        GROQ_TRANSCRIPTION_URL="https://api.groq.com/openai/v1/audio/transcriptions",
        GROQ_TRANSCRIPTION_TIMEOUT_SECONDS=30,
    )
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json={"text": "add two watches"})

    monkeypatch.setattr(speech_to_text_service.httpx, "post", fake_post)
    upload = FileStorage(
        stream=BytesIO(b"recorded audio"),
        filename="voice-message.webm",
        content_type="audio/webm",
    )

    with app.app_context():
        transcript = speech_to_text_service.transcribe_audio(upload, "en-LK")

    assert transcript == "add two watches"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["data"]["model"] == "whisper-large-v3-turbo"
    assert captured["data"]["language"] == "en"
    assert captured["files"]["file"][0] == "voice-message.webm"


def test_transcribe_audio_rejects_unsupported_file():
    app = Flask(__name__)
    upload = FileStorage(
        stream=BytesIO(b"not audio"),
        filename="voice-message.txt",
        content_type="text/plain",
    )

    with app.app_context(), pytest.raises(ApiError) as error:
        speech_to_text_service.transcribe_audio(upload)

    assert error.value.code == "unsupported_audio_format"


def test_transcribe_audio_can_reuse_groq_chat_key(monkeypatch):
    app = Flask(__name__)
    app.config.update(
        GROQ_API_KEY=None,
        AI_PROVIDER="groq",
        AI_API_KEY="shared-groq-key",
        GROQ_TRANSCRIPTION_MODEL="whisper-large-v3-turbo",
        GROQ_TRANSCRIPTION_URL="https://api.groq.com/openai/v1/audio/transcriptions",
        GROQ_TRANSCRIPTION_TIMEOUT_SECONDS=30,
    )

    def fake_post(_url, **kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer shared-groq-key"
        return httpx.Response(200, json={"text": "සිංහල පණිවිඩයක්"})

    monkeypatch.setattr(speech_to_text_service.httpx, "post", fake_post)
    upload = FileStorage(
        stream=BytesIO(b"recorded audio"),
        filename="voice-message.ogg",
        content_type="audio/ogg",
    )

    with app.app_context():
        transcript = speech_to_text_service.transcribe_audio(upload, "si-LK")

    assert transcript == "සිංහල පණිවිඩයක්"
