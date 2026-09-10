from unittest.mock import patch

from app import create_app


def test_me_requires_a_bearer_token():
    app = create_app({"TESTING": True})
    response = app.test_client().get("/api/v1/me")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"


@patch("app.core.auth.firebase_auth.verify_id_token")
def test_password_account_must_verify_email(verify_id_token):
    verify_id_token.return_value = {
        "uid": "seller-1",
        "email_verified": False,
        "firebase": {"sign_in_provider": "password"},
    }
    app = create_app({"TESTING": True})
    response = app.test_client().get(
        "/api/v1/me",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "email_not_verified"


@patch("app.core.auth.firebase_auth.verify_id_token")
def test_revoked_token_returns_revoked_error(verify_id_token):
    from firebase_admin.auth import RevokedIdTokenError

    verify_id_token.side_effect = RevokedIdTokenError("Token has been revoked")
    app = create_app({"TESTING": True})
    response = app.test_client().get(
        "/api/v1/me",
        headers={"Authorization": "Bearer revoked-token"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "revoked_authentication_token"


@patch("app.core.auth.firebase_auth.verify_id_token")
def test_disabled_user_returns_user_disabled(verify_id_token):
    from firebase_admin.auth import UserDisabledError

    verify_id_token.side_effect = UserDisabledError("User is disabled")
    app = create_app({"TESTING": True})
    response = app.test_client().get(
        "/api/v1/me",
        headers={"Authorization": "Bearer disabled-token"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "user_disabled"
