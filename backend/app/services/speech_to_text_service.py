"""Shared Groq Whisper transcription for seller and storefront assistants."""

import httpx
from flask import current_app

from app.core.errors import ApiError


MAX_AUDIO_BYTES = 25 * 1024 * 1024
SUPPORTED_EXTENSIONS = {"flac", "m4a", "mp3", "mp4", "mpeg", "mpga", "ogg", "wav", "webm"}


def _language_code(language):
    normalized = str(language or "").strip().lower()
    if normalized.startswith("si"):
        return "si"
    if normalized.startswith("en"):
        return "en"
    return None


def transcribe_audio(upload, language=None):
    """Transcribe one browser-recorded audio file with Groq Whisper."""
    if upload is None or not upload.filename:
        raise ApiError("audio_required", "Please record an audio message first.", 400)

    extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise ApiError(
            "unsupported_audio_format",
            "Use a WebM, WAV, MP3, M4A, OGG, FLAC, MPEG or MP4 audio recording.",
            400,
        )

    audio_bytes = upload.stream.read(MAX_AUDIO_BYTES + 1)
    if not audio_bytes:
        raise ApiError("empty_audio", "The audio recording is empty.", 400)
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ApiError("audio_too_large", "The audio recording must be smaller than 25 MB.", 413)

    api_key = current_app.config.get("GROQ_API_KEY")
    if not api_key and current_app.config.get("AI_PROVIDER") == "groq":
        api_key = current_app.config.get("AI_API_KEY")
    if not api_key:
        raise ApiError(
            "speech_to_text_unavailable",
            "Voice transcription is not configured yet.",
            503,
        )

    form_data = {
        "model": current_app.config["GROQ_TRANSCRIPTION_MODEL"],
        "response_format": "json",
        "temperature": "0",
    }
    detected_language = _language_code(language)
    if detected_language:
        form_data["language"] = detected_language

    try:
        response = httpx.post(
            current_app.config["GROQ_TRANSCRIPTION_URL"],
            headers={"Authorization": f"Bearer {api_key}"},
            data=form_data,
            files={
                "file": (
                    upload.filename,
                    audio_bytes,
                    upload.mimetype or "application/octet-stream",
                ),
            },
            timeout=current_app.config["GROQ_TRANSCRIPTION_TIMEOUT_SECONDS"],
        )
    except httpx.TimeoutException as error:
        raise ApiError(
            "transcription_timeout",
            "Voice transcription took too long. Please try again.",
            504,
        ) from error
    except httpx.HTTPError as error:
        raise ApiError(
            "transcription_unavailable",
            "Voice transcription is temporarily unavailable.",
            503,
        ) from error

    if response.status_code == 429:
        raise ApiError(
            "transcription_rate_limited",
            "Voice transcription is busy. Please wait a moment and try again.",
            429,
        )
    if response.status_code in {401, 403}:
        raise ApiError(
            "transcription_configuration_error",
            "Voice transcription credentials are invalid.",
            503,
        )
    if not response.is_success:
        raise ApiError(
            "transcription_failed",
            "The audio could not be transcribed. Please try again.",
            502,
        )

    try:
        transcript = str(response.json().get("text") or "").strip()
    except (ValueError, AttributeError) as error:
        raise ApiError(
            "invalid_transcription_response",
            "The transcription service returned an invalid response.",
            502,
        ) from error

    if not transcript:
        raise ApiError(
            "speech_not_detected",
            "I could not hear any speech. Please try again closer to the microphone.",
            422,
        )

    return transcript
