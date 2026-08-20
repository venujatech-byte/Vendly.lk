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
