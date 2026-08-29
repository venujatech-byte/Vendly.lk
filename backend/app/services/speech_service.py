import logging

import httpx
from flask import current_app

from app.core.errors import ApiError


logger = logging.getLogger(__name__)

ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
}
MAX_AUDIO_BYTES = 24 * 1024 * 1024


def _base_content_type(content_type):
    return str(content_type or "").split(";", 1)[0].strip().lower()


def transcribe_business_assistant_audio(
    audio_bytes,
    *,
    filename="business-assistant.webm",
    content_type="audio/webm",
    language=None,
):
    """Transcribe one browser recording with Groq Whisper."""
    api_key = current_app.config.get("GROQ_API_KEY")
    if not api_key:
        raise ApiError(
            "speech_not_configured",
            "Speech-to-text is not configured on the server.",
            status_code=503,
        )

    normalized_content_type = _base_content_type(content_type)
    if normalized_content_type not in ALLOWED_AUDIO_TYPES:
        raise ApiError(
            "unsupported_audio_type",
            "This audio format is not supported.",
            status_code=415,
        )

    if not audio_bytes:
        raise ApiError(
            "empty_audio",
            "The recording is empty. Please record your request again.",
            status_code=400,
        )

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ApiError(
            "audio_too_large",
            "The recording is too large. Keep voice commands under one minute.",
            status_code=413,
        )

    model = current_app.config.get(
        "GROQ_TRANSCRIPTION_MODEL",
        "whisper-large-v3",
    )
    data = {
        "model": model,
        "response_format": "verbose_json",
        "temperature": "0",
    }
    normalized_language = str(language or "").split("-", 1)[0].lower()
    if normalized_language in {"en", "si", "ta"}:
        data["language"] = normalized_language

    try:
        response = httpx.post(
            current_app.config.get(
                "GROQ_TRANSCRIPTION_URL",
                "https://api.groq.com/openai/v1/audio/transcriptions",
            ),
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files={
                "file": (
                    filename,
                    audio_bytes,
                    normalized_content_type,
                ),
            },
            timeout=current_app.config.get(
                "GROQ_TRANSCRIPTION_TIMEOUT_SECONDS",
                45.0,
            ),
        )
    except httpx.TimeoutException as error:
        raise ApiError(
            "speech_timeout",
            "Speech transcription timed out. Please try a shorter command.",
            status_code=504,
        ) from error
    except httpx.HTTPError as error:
        logger.warning("Groq speech request failed: %s", error)
        raise ApiError(
            "speech_service_unavailable",
            "The speech service could not be reached. Please try again.",
            status_code=502,
        ) from error

    if not response.is_success:
        if response.status_code == 429:
            message = "The speech service is busy. Please wait and try again."
            code = "speech_rate_limited"
            status_code = 429
        elif response.status_code in {401, 403}:
            message = "The speech service credentials are invalid."
            code = "speech_authentication_failed"
            status_code = 503
        else:
            message = "The speech service could not transcribe this recording."
            code = "speech_transcription_failed"
            status_code = 502

        logger.warning(
            "Groq transcription returned status %s",
            response.status_code,
        )
        raise ApiError(code, message, status_code=status_code)

    try:
        payload = response.json()
    except ValueError as error:
        raise ApiError(
            "invalid_speech_response",
            "The speech service returned an invalid response.",
            status_code=502,
        ) from error

    text = str(payload.get("text") or "").strip()
    if not text:
        raise ApiError(
            "speech_not_detected",
            "No speech was detected. Please speak closer to the microphone.",
            status_code=422,
        )

    return {
        "text": text,
        "language": payload.get("language") or normalized_language or None,
        "duration": payload.get("duration"),
        "model": model,
    }
