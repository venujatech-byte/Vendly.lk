import hashlib
import json
from ipaddress import ip_address

from flask import current_app, g, request
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


def guest_chat_ip_limit_exempt():
    """Apply the opt-in network quota only to guests and anonymous accounts."""
    user = g.current_user or {}
    signed_in = user.get("uid") and user.get("firebase", {}).get("sign_in_provider") != "anonymous"
    return not current_app.config["GUEST_CHAT_IP_LIMIT_ENABLED"] or bool(signed_in)


def guest_chat_ip_key():
    """Use the direct peer or a single address set by local Nginx."""
    peer = get_remote_address()
    try:
        address = ip_address(peer)
    except ValueError:
        return f"guest-ip:{peer}"
    # Remote clients cannot supply this value directly. Nginx must overwrite it.
    if address.is_loopback:
        forwarded = request.headers.get("X-Vendly-Client-IP", "")
        if "%" not in forwarded:
            try:
                address = ip_address(forwarded)
            except ValueError:
                pass
    return f"guest-ip:{getattr(address, 'ipv4_mapped', None) or address}"


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute", "2000 per hour"],
)
