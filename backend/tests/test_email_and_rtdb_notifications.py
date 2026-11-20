import json
from html import escape
from unittest.mock import MagicMock, patch
import pytest

from app.core.errors import ApiError
from app.services.email_service import (
    send_brevo_email,
    send_notification_email,
    send_order_confirmation_email,
    send_customer_order_status_email,
)
from app.services.customer_portal_service import update_order_guest_email


def test_send_brevo_email_disabled_by_default(monkeypatch):
    monkeypatch.setattr(
        "app.services.email_service._get_brevo_config",
        lambda: (False, "mock-key", "sender@vendly.lk", "Vendly", "http://localhost:5173"),
    )

    with patch("httpx.post") as mock_post:
        result = send_brevo_email("test@example.com", "Test User", "Subject", "<p>Hi</p>")
        assert result is False
        mock_post.assert_not_called()


def test_send_brevo_email_enabled_success(monkeypatch):
    monkeypatch.setattr(
        "app.services.email_service._get_brevo_config",
        lambda: (True, "test-api-key-123", "orders@vendly.lk", "Vendly Notifications", "http://localhost:5173"),
    )

    mock_response = MagicMock()
    mock_response.status_code = 201

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = send_brevo_email(
            to_email="buyer@example.com",
            to_name="Buyer",
            subject="Order Placed",
            html_content="<p>Details</p>",
        )
        assert result is True
        assert mock_post.call_count == 1
        args, kwargs = mock_post.call_args
        assert kwargs["headers"]["api-key"] == "test-api-key-123"
        assert kwargs["json"]["to"][0]["email"] == "buyer@example.com"
        assert kwargs["json"]["sender"]["email"] == "orders@vendly.lk"
        assert kwargs["json"]["subject"] == "Order Placed"


def test_send_order_confirmation_email_requires_recipient():
    order = {"customerSnapshot": {}}
    business = {"name": "Fashion Hub"}
    assert send_order_confirmation_email(order, business) is False


@pytest.mark.parametrize("status,diagnostic", [(201, "HTTP 201"), (400, "HTTP 400"), (None, "RuntimeError")])
def test_email_logs_exclude_customer_details_and_provider_messages(monkeypatch, caplog, status, diagnostic):
    monkeypatch.setattr("app.services.email_service._get_brevo_config", lambda: (
        True, "synthetic-key", "sender@example.test", "Vendly", "https://example.test",
    ))
    # Capture logs from synthetic provider outcomes without sending real mail.
    response = MagicMock(status_code=status, text="synthetic-private-provider-detail")
    failure = RuntimeError(response.text) if status is None else None
    with patch("httpx.post", return_value=response, side_effect=failure), caplog.at_level("INFO"):
        assert send_brevo_email("buyer@example.test", "Buyer", "Private order subject", "<p>Hi</p>") is (status == 201)
    assert diagnostic in caplog.text
    for value in ("buyer@example.test", "Private order subject", "synthetic-private-provider-detail"):
        assert value not in caplog.text


def test_send_order_confirmation_email_formats_items():
    order = {
        "orderNumber": "VD-1002",
        "customerSnapshot": {"name": "Nimal", "email": "nimal@example.com"},
        "deliveryAddress": {"line1": "45 Galle Road", "city": "Colombo"},
        "items": [
            {"name": "Linen Shirt", "size": "L", "quantity": 2, "lineTotalMinor": 700000}
        ],
        "totalAmountMinor": 750000,
    }
    business = {"name": "Lanka Threads", "shortCode": "threads"}

    with patch("app.services.email_service.send_brevo_email", return_value=True) as mock_send:
        res = send_order_confirmation_email(order, business)
        assert res is True
        assert mock_send.call_count == 1
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to_email"] == "nimal@example.com"
        assert "VD-1002" in call_kwargs["subject"]
        assert "Linen Shirt" in call_kwargs["html_content"]
        assert "LKR 7,500.00" in call_kwargs["html_content"]


def test_send_customer_order_status_email():
    order = {
        "orderNumber": "VD-8899",
        "customerSnapshot": {"name": "Sara", "email": "sara@example.com"},
    }
    business = {"name": "Sara Studio", "shortCode": "sarastudio"}

    with patch("app.services.email_service.send_brevo_email", return_value=True) as mock_send:
        res = send_customer_order_status_email(order, business, "shipped", note="Handed to prompt courier")
        assert res is True
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to_email"] == "sara@example.com"
        assert "Shipped" in call_kwargs["subject"]
        assert "Handed to prompt courier" in call_kwargs["html_content"]


def test_notification_html_escapes_text_and_quoted_link_attributes():
    title = "Shipping & <delivery>"
    message = "Customer entered <b>gift</b>"
    url = 'https://example.test/orders?name="test"&page=1'
    # Capture the provider payload offline and check both HTML and plain text.
    with patch("app.services.email_service.send_brevo_email", return_value=True) as send:
        assert send_notification_email("seller@example.test", "Seller", "<alert>", title, message, url)
    payload = send.call_args.kwargs
    assert payload["subject"] == f"[Vendly] {title}"
    assert payload["text_content"] == f"{title}\n\n{message}"
    body = payload["html_content"]
    for value in (title, message, "<alert>"):
        assert value not in body and escape(value) in body
    assert f'href="{escape(url)}"' in body


@pytest.mark.parametrize("status_update", [False, True])
def test_customer_emails_render_order_fields_as_literal_text(status_update):
    customer = "Nimal & <company>"
    store = "<store> & Co."
    number = "VD-<123>"
    address = "<address> Main Road"
    product = "<product> & Co."
    size = "<large>"
    note = "Leave at <entrance>"
    order = {
        "orderNumber": number,
        "customerSnapshot": {"name": customer, "email": "buyer@example.test"},
        "deliveryAddress": {"line1": address},
        "items": [{"name": product, "size": size, "quantity": 2}],
    }
    with patch("app.services.email_service.send_brevo_email", return_value=True) as send:
        if status_update:
            assert send_customer_order_status_email(order, {"name": store}, "shipped", note=note)
        else:
            assert send_order_confirmation_email(order, {"name": store})
    payload = send.call_args.kwargs
    assert payload["to_name"] == customer
    assert number in payload["subject"]
    body = payload["html_content"]
    fields = [customer, store, number] + ([note] if status_update else [product, size, address])
    for value in fields:
        assert value not in body and escape(value) in body


def test_update_order_guest_email_validation():
    mock_db = MagicMock()
    with pytest.raises(ApiError) as exc:
        update_order_guest_email(mock_db, "mystore", "ord-123", "invalid-email")
    assert exc.value.status_code == 422

