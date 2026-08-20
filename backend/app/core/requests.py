from flask import request

from app.core.errors import ApiError


def get_json_object():
    """Return a JSON object request body or raise a consistent API error."""
    payload = request.get_json(silent=True)

    if payload is None:
        return {}

    if not isinstance(payload, dict):
        raise ApiError(
            "validation_error",
            "The request body must be a JSON object.",
            422,
        )

    return payload
