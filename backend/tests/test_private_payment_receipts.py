"""Exercise seller receipt upload, persistence, and link authorization offline."""

import base64
from hashlib import sha1
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import httpx
import pytest

from app import create_app
from app.services import media_service
from firestore_memory import MemoryFirestore


ORDER = "businesses/business-a/orders/order-a"
ORDERS_URL = "/api/v1/businesses/business-a/orders"
LINKS_URL = f"{ORDERS_URL}/order-a/payment-receipts/links"
HEADERS = {"Authorization": "Bearer synthetic-owner"}
SECRET = "synthetic-secret"
TIMESTAMP = 1700000000
IMAGE = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xffsynthetic").decode()


@pytest.fixture
def receipts(monkeypatch):
    # Use Firestore's real SDK with in-memory RPCs, and simulate only external services.
    store = MemoryFirestore()
    store.put(ORDER, {"totalAmountMinor": 2500, "paidAmountMinor": 0, "orderNumber": "ORDER-A"})
    store.put("businesses/business-a/members/synthetic-owner", {"role": "owner", "status": "active"})
    store.put("businesses/business-a/members/synthetic-no-orders", {"role": "custom", "status": "active", "permissions": ["customers:read"]})
    store.put("businesses/business-b/members/synthetic-outsider", {"role": "owner", "status": "active"})
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", lambda token, **_kwargs: {"uid": token})
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.orders.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.orders.bump_analytics_version", Mock())
    monkeypatch.setattr("app.api.orders.create_order", Mock(return_value={"id": "order-a", "paidAmountMinor": 500}))
    monkeypatch.setattr("app.services.order_service.send_payment_recorded_chat_message", Mock())
    monkeypatch.setattr(media_service, "time", Mock(time=lambda: TIMESTAMP))

    def cloudinary_response(_url, *, data, timeout):
        return httpx.Response(200, json={
            "type": data.get("type", "upload"), "public_id": data["public_id"], "format": "jpg",
            "secure_url": "https://example.test/synthetic-upload-url",
        })

    upload = Mock(side_effect=cloudinary_response)
    monkeypatch.setattr(media_service.httpx, "post", upload)
    app = create_app({"TESTING": True, "CLOUDINARY_CLOUD_NAME": "synthetic-cloud",
                      "CLOUDINARY_API_KEY": "synthetic-key", "CLOUDINARY_API_SECRET": SECRET})
    return app.test_client(), store, upload


def assert_signature(parameters, signed_keys):
    # Compare with the provider's canonical sorted-parameter signature independently.
    signature_input = "&".join(f"{key}={parameters[key]}" for key in sorted(signed_keys))
    assert parameters["signature"] == sha1(f"{signature_input}{SECRET}".encode()).hexdigest()


@pytest.mark.parametrize("method,url,status", [("POST", ORDERS_URL, 201), ("PATCH", f"{ORDERS_URL}/order-a/payment", 200)])
def test_seller_upload_stores_private_asset_and_signs_link_on_demand(receipts, method, url, status):
    client, store, upload = receipts
    result = client.open(url, method=method, headers=HEADERS, json={"receiptImage": IMAGE, "paidAmountMinor": 500})
    assert result.status_code == status
    upload_data = upload.call_args.kwargs["data"]
    assert upload_data["type"] == "authenticated"
    assert_signature(upload_data, ["public_id", "timestamp", "type"])
    receipt = store.documents[ORDER]["paymentReceipts"][0]
    asset = receipt["privateAsset"]
    assert receipt["amountMinor"] == 500
    assert "url" not in receipt
    assert "synthetic-upload-url" not in result.get_data(as_text=True)

    response = client.get(LINKS_URL, headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    url_parts = urlsplit(response.json["links"][asset["id"]])
    parameters = {key: values[0] for key, values in parse_qs(url_parts.query).items()}
    assert (url_parts.scheme, url_parts.netloc, url_parts.path) == (
        "https", "api.cloudinary.com", "/v1_1/synthetic-cloud/image/download",
    )
    assert parameters["type"] == "authenticated"
    assert parameters["format"] == "jpg"
    assert parameters["public_id"] == upload_data["public_id"]
    assert int(parameters["expires_at"]) == TIMESTAMP + 300
    assert_signature(parameters, ["public_id", "format", "type", "timestamp", "expires_at"])


def test_link_endpoint_requires_order_permission_and_ignores_legacy_urls(receipts):
    client, store, upload = receipts
    store.put(ORDER, {**store.documents[ORDER], "paymentReceipts": [{"url": "https://example.test/legacy"}]})
    assert client.get(LINKS_URL).status_code == 401
    for identity in ("synthetic-outsider", "synthetic-no-orders"):
        assert client.get(LINKS_URL, headers={"Authorization": f"Bearer {identity}"}).status_code == 403
    assert client.get(LINKS_URL, headers=HEADERS).json == {"links": {}}
    assert store.documents[ORDER]["paymentReceipts"] == [{"url": "https://example.test/legacy"}]
    upload.assert_not_called()


def test_unconfirmed_private_upload_is_not_attached_to_the_order(receipts):
    client, store, upload = receipts
    upload.side_effect = None
    upload.return_value = httpx.Response(200, json={"type": "upload", "secure_url": "https://example.test/public"})
    result = client.patch(f"{ORDERS_URL}/order-a/payment", headers=HEADERS, json={"receiptImage": IMAGE, "paidAmountMinor": 500})
    assert result.status_code == 502
    assert "paymentReceipts" not in store.documents[ORDER]
    assert store.documents[ORDER]["paidAmountMinor"] == 0
