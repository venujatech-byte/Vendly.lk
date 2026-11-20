"""Verify guest quota behavior through Flask with mocked chat providers."""

from unittest.mock import Mock

import pytest
from flask import Flask

from app import create_app
from app.core.rate_limit import guest_chat_ip_key


@pytest.fixture
def chat_client(monkeypatch):
    # Verify both route decorators and provider call counts without network access.
    answer = Mock(return_value={"message": "Synthetic reply"})
    upload = Mock(return_value={"message": "Synthetic upload"})
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.api.public.get_firestore_client", Mock())
    monkeypatch.setattr("app.api.public.claim_public_chat_session", Mock())
    monkeypatch.setattr("app.api.public.answer_public_message", answer)
    monkeypatch.setattr("app.api.public.attach_public_chat_image", upload)
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", lambda token, **_kwargs: {
        "uid": token, "firebase": {"sign_in_provider": token},
    })

    def start(enabled):
        app = create_app({"TESTING": False, "GUEST_CHAT_IP_LIMIT_ENABLED": enabled, "RATELIMIT_STORAGE_URI": "memory://"})
        return app.test_client(), {"messages": answer, "images": upload}

    return start


def send(client, endpoint, index, *, ip="192.0.2.4", identity=None):
    headers = {"X-Chat-Session-Token": f"synthetic-token-{index}", "X-Vendly-Client-IP": ip}
    if identity:
        headers["Authorization"] = f"Bearer {identity}"
    return client.post(f"/api/v1/public/chat/sessions/chat-a/{endpoint}", json={}, headers=headers)


@pytest.mark.parametrize("endpoint,status,quota", [("messages", 200, 120), ("images", 201, 20)])
def test_guest_quota_spans_sessions_and_keeps_verified_accounts_separate(chat_client, endpoint, status, quota):
    client, providers = chat_client(True)
    for index in range(quota):
        identity = "anonymous" if index % 2 else None
        assert send(client, endpoint, index, identity=identity).status_code == status
    blocked = send(client, endpoint, quota)
    assert blocked.status_code == 429
    assert providers[endpoint].call_count == quota
    assert send(client, endpoint, quota, ip="192.0.2.5").status_code == status
    assert send(client, endpoint, quota + 1, identity="password").status_code == status


@pytest.mark.parametrize("enabled", [False, True])
def test_session_limit_applies_and_ip_limit_is_optional(chat_client, enabled):
    client, providers = chat_client(enabled)
    for _ in range(10):
        assert send(client, "images", 0).status_code == 201
    assert send(client, "images", 0).status_code == 429
    assert providers["images"].call_count == 10
    for index in range(1, 24):
        expected = 429 if enabled and index >= 10 else 201
        assert send(client, "images", index).status_code == expected


@pytest.mark.parametrize("peer,header,expected", [
    ("127.0.0.1", "192.0.2.4", "192.0.2.4"),
    ("::1", "::ffff:192.0.2.4", "192.0.2.4"),
    ("192.0.2.5", "192.0.2.4", "192.0.2.5"),
    ("127.0.0.1", "192.0.2.4, 192.0.2.5", "127.0.0.1"),
    ("127.0.0.1", "", "127.0.0.1"),
])
def test_guest_ip_key_accepts_only_single_addresses_from_loopback(peer, header, expected):
    app = Flask(__name__)
    with app.test_request_context(headers={"X-Vendly-Client-IP": header}, environ_overrides={"REMOTE_ADDR": peer}):
        assert guest_chat_ip_key() == f"guest-ip:{expected}"
