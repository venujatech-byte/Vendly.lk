import hashlib
import json

from flask import g, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def public_chat_key():
    """Limit an active chat by its secret token without storing the raw token."""
    token = request.headers.get("X-Chat-Session-Token", "").strip()

    if token:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"chat:{digest}"

    return f"ip:{get_remote_address()}"


def business_user_key():
    """Split a seller quota by verified account and authorized business."""
    # Encode both parts without relying on a delimiter that could occur in an ID.
    return json.dumps([g.business_id, g.current_user["uid"]])


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute", "2000 per hour"],
)
