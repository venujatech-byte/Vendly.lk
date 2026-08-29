from flask import Blueprint, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.errors import ApiError
from app.core.firebase import get_firestore_client
from app.core.rate_limit import limiter
from app.core.requests import get_json_object
from app.services.business_assistant_service import handle_business_assistant_message
from app.services.speech_service import transcribe_business_assistant_audio


business_assistant_blueprint = Blueprint(
    "business_assistant",
    __name__,
    url_prefix="/api/v1",
)


@business_assistant_blueprint.post(
    "/businesses/<business_id>/assistant/messages",
)
@limiter.limit("30 per minute")
@require_firebase_user
@require_business_member()
def business_assistant_message(business_id):
    response = handle_business_assistant_message(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        g.membership,
        get_json_object(),
    )
    return jsonify({"assistant": response})


@business_assistant_blueprint.post(
    "/businesses/<business_id>/assistant/transcriptions",
)
@limiter.limit("12 per minute")
@require_firebase_user
@require_business_member()
def business_assistant_transcription(business_id):
    # The authorization decorator already validates that this user belongs to
    # the business in the URL. The audio itself is not stored in Firestore.
    del business_id
    audio_file = request.files.get("audio")
    if audio_file is None:
        raise ApiError(
            "audio_required",
            "An audio recording is required.",
            status_code=400,
        )

    transcription = transcribe_business_assistant_audio(
        audio_file.read(),
        filename=audio_file.filename or "business-assistant.webm",
        content_type=audio_file.content_type or "audio/webm",
        language=request.form.get("language"),
    )
    return jsonify({"transcription": transcription})
