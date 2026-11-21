"""Check chat attachment visibility with offline Firebase and Cloudinary."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import httpx
import pytest

from app import create_app
from app.services import chat_payment_service, media_service, order_service, public_chat_service
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


@pytest.mark.parametrize("already_paid", [0, 200000])
def test_chat_report_records_one_transfer_once_after_seller_verification(attachments, monkeypatch, already_paid):
    client, store, upload, _ = attachments
    order_path = "businesses/business-a/orders/order-a"
    store.put(order_path, {
        "orderNumber": "VD-TEST", "paymentMethod": "deposit",
        "fulfilmentStatus": "confirmed" if already_paid else "needs-confirmation",
        "paymentStatus": "partially-paid" if already_paid else "pending-payment",
        "totalAmountMinor": 400000, "paidAmountMinor": already_paid,
    })
    store.put(CHAT, {**store.documents[CHAT], "orderId": "order-a", "state": "completed", "status": "completed"})
    owner = {"Authorization": "Bearer synthetic-owner"}
    store.put("businesses/business-a/members/synthetic-owner", {"role": "owner", "status": "active"})
    store.put("businesses/business-a/members/synthetic-order-only", {
        "role": "order_manager", "status": "active", "permissions": ["orders:manage"],
    })
    store.put("businesses/business-b/members/synthetic-owner", {"role": "owner", "status": "active"})
    monkeypatch.setattr("app.api.orders.get_firestore_client", lambda: store.client)
    notify = Mock()
    confirm = Mock()
    monkeypatch.setattr(order_service, "_notify_payment_recorded", notify)
    monkeypatch.setattr(order_service, "_publish_order_status_change", confirm)
    model = Mock(side_effect=AssertionError("Receipt amounts must be handled locally."))
    monkeypatch.setattr(public_chat_service, "storefront_intent", model)

    image = client.post(f"{PUBLIC}/images", headers=GUEST, json={"image": IMAGE})
    assert image.status_code == 201
    assert "How much did you transfer for order VD-TEST?" in image.json["message"]
    receipt = image.json["privateAttachment"]
    path = f"{SELLER}/payment-reports/{receipt['id']}"
    draft_retry = client.post(f"{PUBLIC}/images", headers=GUEST, json={"image": IMAGE})
    assert draft_retry.status_code == 409
    assert upload.call_count == 1
    replied = client.post(f"{PUBLIC}/messages", headers=GUEST, json={"message": "LKR 1,100.00"})
    assert replied.status_code == 200
    assert "for verification" in replied.json["message"]
    assert store.documents[order_path]["paidAmountMinor"] == already_paid
    model.assert_not_called()

    # A chat reader, an order manager without inbox access, and the wrong business cannot verify.
    for headers in (READER, {"Authorization": "Bearer synthetic-order-only"}):
        assert client.post(path, headers=headers, json={"amount": "1000"}).status_code == 403
    assert client.post(path.replace("business-a", "business-b"), headers=owner, json={"amount": "1000"}).status_code == 404
    review = client.get(path, headers=owner)
    assert review.json["report"]["reportedAmountMinor"] == 110000
    assert review.json["report"]["receipt"] == receipt
    overpayment = client.post(path, headers=owner, json={"amount": "5000"})
    assert overpayment.json["error"]["code"] == "invalid_payment"
    assert store.documents[order_path]["paidAmountMinor"] == already_paid

    # Interleave a second approval to prove the same receipt cannot be credited twice.
    reference = store.client.document(f"{CHAT}/paymentReports/{receipt['id']}")
    store.before_commit = lambda _: chat_payment_service.verify_chat_payment_report(
        store.client, "business-a", reference, "synthetic-owner", {"amount": "1000"},
    )
    verified = client.post(path, headers=owner, json={"amount": "1000"})
    assert verified.status_code == 200
    assert verified.json["report"]["verifiedAmountMinor"] == 100000
    order = store.documents[order_path]
    assert order["paidAmountMinor"] == already_paid + 100000
    assert order["balanceAmountMinor"] == 300000 - already_paid
    assert order["fulfilmentStatus"] == "confirmed"
    assert len(order["paymentReceipts"]) == 1
    assert order["paymentReceipts"][0]["amountMinor"] == 100000
    notify.assert_called_once()
    assert confirm.call_count == (0 if already_paid else 1)

    # The order page can open the original private receipt after verification.
    links = client.get("/api/v1/businesses/business-a/orders/order-a/payment-receipts/links", headers=owner)
    assert links.status_code == 200
    query = parse_qs(urlsplit(links.json["links"][receipt["id"]]).query)
    assert query["public_id"] == [upload.call_args.kwargs["data"]["public_id"]]
