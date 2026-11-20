"""Exercise seller AI quotas with the real Flask limiter and offline providers."""

from io import BytesIO
from unittest.mock import Mock

import pytest

from app import create_app
from firestore_memory import MemoryFirestore


@pytest.mark.parametrize("route,provider,quota", [
    ("assistant/messages", "business_assistant.handle_business_assistant_message", 30),
    ("assistant/transcriptions", "business_assistant.transcribe_business_assistant_audio", 12),
    ("products/generate-description", "products.generate_product_description", 12),
])
def test_seller_ai_quota_uses_verified_user_and_business(monkeypatch, route, provider, quota):
    # Mock identity verification, membership storage and providers while retaining real route gates.
    store = MemoryFirestore()
    for business in ("business-a", "business-b"):
        for uid in ("seller-a", "seller-b"):
            store.put(f"businesses/{business}/members/{uid}", {"role": "owner", "status": "active"})
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", lambda token, **kwargs: {"uid": token})
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.business_assistant.get_firestore_client", lambda: store.client)
    response = Mock(return_value={"description": "Synthetic description"})
    monkeypatch.setattr(f"app.api.{provider}", response)
    app = create_app({"TESTING": False, "RATELIMIT_STORAGE_URI": "memory://"})
    client = app.test_client()

    def send(uid, business="business-a", ip="192.0.2.10"):
        payload = {"data": {"audio": (BytesIO(b"synthetic"), "sample.webm")}} if route.endswith("transcriptions") else {"json": {"name": "Item"}}
        return client.post(
            f"/api/v1/businesses/{business}/{route}",
            headers={"Authorization": f"Bearer {uid}"} if uid else {},
            environ_overrides={"REMOTE_ADDR": ip},
            **payload,
        )

    # Authorization failures must not reach the provider or become quota errors.
    assert send(None).status_code == 401
    assert send("non-member").status_code == 403
    response.assert_not_called()

    for _ in range(quota):
        assert send("seller-a").status_code == 200
    for ip in ("192.0.2.10", "192.0.2.11"):
        blocked = send("seller-a", ip=ip)
        assert blocked.status_code == 429
        assert blocked.json["error"]["code"] == "rate_limit_exceeded"
    assert response.call_count == quota
    assert send("seller-b").status_code == 200
    assert send("seller-a", "business-b").status_code == 200
