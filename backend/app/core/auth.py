from functools import wraps

from firebase_admin import auth as firebase_auth
from flask import g, jsonify, request


def authentication_error(
    message,
    status_code=401,
    code="authentication_required",
):
    return jsonify(
        {
            "error": {
                "code": code,
                "message": message,
            },
        },
    ), status_code


def require_firebase_user(view_function):
    """Verify a Firebase ID token from the Authorization header."""

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")

        if not authorization.startswith("Bearer "):
            return authentication_error("A Firebase bearer token is required.")

        id_token = authorization.removeprefix("Bearer ").strip()

        if not id_token:
            return authentication_error("A Firebase bearer token is required.")

        try:
            g.current_user = firebase_auth.verify_id_token(id_token)
        except (
            firebase_auth.InvalidIdTokenError,
            firebase_auth.ExpiredIdTokenError,
            firebase_auth.RevokedIdTokenError,
            firebase_auth.UserDisabledError,
            ValueError,
        ):
            return authentication_error(
                "The Firebase token is invalid or expired.",
                code="invalid_authentication_token",
            )

        sign_in_provider = g.current_user.get("firebase", {}).get(
            "sign_in_provider",
        )

        if (
            sign_in_provider == "password"
            and not g.current_user.get("email_verified", False)
        ):
            return authentication_error(
                "Verify your email address before using Vendly.",
                status_code=403,
                code="email_not_verified",
            )

        return view_function(*args, **kwargs)

    return wrapped_view


def optional_firebase_user(view_function):
    """Load a Firebase identity when supplied, while allowing public guests."""

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        g.current_user = None

        if authorization.startswith("Bearer "):
            id_token = authorization.removeprefix("Bearer ").strip()
            try:
                g.current_user = firebase_auth.verify_id_token(id_token)
            except (
                firebase_auth.InvalidIdTokenError,
                firebase_auth.ExpiredIdTokenError,
                firebase_auth.RevokedIdTokenError,
                firebase_auth.UserDisabledError,
                ValueError,
            ):
                return authentication_error(
                    "The Firebase token is invalid or expired.",
                    code="invalid_authentication_token",
                )

        return view_function(*args, **kwargs)

    return wrapped_view
