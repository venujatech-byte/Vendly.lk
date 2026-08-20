import hashlib

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def public_chat_key():
    """Limit an active chat by its secret token without storing the raw token."""
    token = request.headers.get("X-Chat-Session-Token", "").strip()

    if token:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"chat:{digest}"

    return f"ip:{get_remote_address()}"


limiter = Limiter(key_func=get_remote_address)
