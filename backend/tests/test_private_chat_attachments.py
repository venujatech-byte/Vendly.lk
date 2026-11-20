"""Check chat attachment visibility with offline Firebase and Cloudinary."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import httpx
import pytest

from app import create_app
from app.services import media_service, public_chat_service
from firestore_memory import MemoryFirestore
from test_private_payment_receipts import IMAGE, SECRET, TIMESTAMP, assert_signature


CHAT = "publicChatSessions/chat-a"
PUBLIC = "/api/v1/public/chat/sessions/chat-a"
SELLER = "/api/v1/businesses/business-a/chat-sessions/chat-a"
GUEST = {"X-Chat-Session-Token": "synthetic-guest"}
READER = {"Authorization": "Bearer synthetic-reader"}


@pytest.fixture
def attachments(monkeypatch):
    # Real SDK calls run against the in-memory store so message history is exercised.
    store = MemoryFirestore()
    store.put(CHAT, {"businessId": "business-a", "status": "active", "state": "browsing",
                     "tokenHash": public_chat_service.token_hash(GUEST["X-Chat-Session-Token"])})
    for business, uid, permissions in (
        ("business-a", "synthetic-reader", ["customers:read"]),
        ("business-a", "synthetic-no-chat", ["orders:read"]),
        ("business-b", "synthetic-outsider", ["customers:read"]),
    ):
        store.put(f"businesses/{business}/members/{uid}",
                  {"role": "custom", "status": "active", "permissions": permissions})

    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", lambda token, **_: {"uid": token})
    for module in ("core.authorization", "api.public", "api.messages"):
        monkeypatch.setattr(f"app.{module}.get_firestore_client", lambda: store.client)
    for service in ("public_chat_service", "message_service"):
        monkeypatch.setattr(f"app.services.{service}.get_rtdb_reference", lambda _: None)
    sync_access = Mock()
    monkeypatch.setattr("app.services.realtime_access_service.sync_chat_access", sync_access)
    monkeypatch.setattr(public_chat_service, "notify_seller_attention", Mock())
    monkeypatch.setattr(media_service, "time", Mock(time=lambda: TIMESTAMP))

    # Include a provider URL to ensure it is discarded for authenticated uploads.
    def cloudinary_response(_url, *, data, timeout):
        return httpx.Response(200, json={
            "type": data.get("type", "upload"), "public_id": data["public_id"],
            "format": "jpg", "secure_url": "https://example.test/synthetic-image",
        })

    upload = Mock(side_effect=cloudinary_response)
    monkeypatch.setattr(media_service.httpx, "post", upload)
    app = create_app({"TESTING": True, "CLOUDINARY_CLOUD_NAME": "synthetic-cloud",
                      "CLOUDINARY_API_KEY": "synthetic-key", "CLOUDINARY_API_SECRET": SECRET})
    return app.test_client(), store, upload, sync_access


def test_private_image_is_saved_without_url_and_signed_for_both_chat_participants(attachments):
    client, store, upload, sync_access = attachments
    response = client.post(f"{PUBLIC}/images", headers=GUEST, json={"image": IMAGE, "caption": "Bank slip"})
    assert response.status_code == 201
    asset = response.json["privateAttachment"]
    assert "imageUrl" not in response.json
    data = upload.call_args.kwargs["data"]
    assert data["type"] == "authenticated"
    assert data["public_id"] == f"businesses/business-a/private-chat-images/chat-a/{asset['id']}"
    assert_signature(data, ["public_id", "timestamp", "type"])
    path, = [path for path in store.documents if path.startswith(f"{CHAT}/messages/")]
    metadata = {"privateAttachment": asset, "kind": "image"}
    assert store.documents[path]["metadata"] == metadata
    # The memory transport leaves server timestamp transforms unset.
    store.put(path, {**store.documents[path], "createdAt": datetime.now(timezone.utc)})
    history = client.get(f"{PUBLIC}/messages", headers=GUEST)
    assert history.json["messages"][0]["metadata"] == metadata

    for base, headers in ((PUBLIC, GUEST), (SELLER, READER)):
        signed = client.get(f"{base}/attachments/{asset['id']}/{asset['format']}", headers=headers)
        assert signed.status_code == 200
        assert signed.headers["Cache-Control"] == "no-store"
        parts = urlsplit(signed.json["url"])
        assert (parts.scheme, parts.netloc, parts.path) == (
            "https", "api.cloudinary.com", "/v1_1/synthetic-cloud/image/download",
        )
        parameters = {key: values[0] for key, values in parse_qs(parts.query).items()}
        assert parameters["public_id"] == data["public_id"]
        assert parameters["type"] == "authenticated"
        assert parameters["format"] == "jpg"
        assert int(parameters["expires_at"]) == TIMESTAMP + 300
        assert_signature(parameters, ["public_id", "format", "type", "timestamp", "expires_at"])
    sync_access.assert_not_called()


def test_attachment_links_use_existing_session_expiry_inbox_and_tenant_checks(attachments):
    client, store, upload, _ = attachments
    suffix = f"/attachments/{'a' * 32}/jpg"
    assert client.get(PUBLIC + suffix).status_code == 401
    assert client.get(PUBLIC + suffix, headers={"X-Chat-Session-Token": "synthetic-other"}).status_code == 401
    assert client.get(PUBLIC + "/attachments/invalid/jpg", headers=GUEST).status_code == 404
    assert client.get(SELLER + suffix).status_code == 401
    assert client.get(SELLER + suffix, headers={"Authorization": "Bearer synthetic-no-chat"}).status_code == 403
    assert client.get(SELLER.replace("business-a", "business-b") + suffix,
                      headers={"Authorization": "Bearer synthetic-outsider"}).status_code == 404
    store.put(CHAT, {**store.documents[CHAT], "hiddenFromSellerInbox": True})
    assert client.get(SELLER + suffix, headers=READER).status_code == 404
    assert client.get(PUBLIC + suffix, headers=GUEST).status_code == 200
    store.put(CHAT, {**store.documents[CHAT], "expiresAt": datetime.now(timezone.utc) - timedelta(days=1)})
    expired = client.get(PUBLIC + suffix, headers=GUEST)
    assert expired.json["error"]["code"] == "chat_session_expired"
    upload.assert_not_called()


def test_review_upload_keeps_public_url_for_review_publication(attachments):
    client, store, upload, _ = attachments
    store.put(CHAT, {**store.documents[CHAT], "state": "collecting-review-photo"})
    response = client.post(f"{PUBLIC}/images", headers=GUEST, json={"image": IMAGE})
    assert response.status_code == 201
    assert "privateAttachment" not in response.json
    assert store.documents[CHAT]["reviewDraft"]["media"] == [response.json["imageUrl"]]
    assert "type" not in upload.call_args.kwargs["data"]
    public_chat_service.notify_seller_attention.assert_not_called()
