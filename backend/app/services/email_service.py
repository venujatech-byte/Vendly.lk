import logging
import httpx
from flask import current_app

LOGGER = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _get_brevo_config():
    """Safely obtain Brevo configuration and frontend URL from Flask app or settings."""
    try:
        from flask import has_app_context, current_app
        if has_app_context():
            settings = current_app.config
            use_brevo = bool(settings.get("USE_BREVO"))
            api_key = (settings.get("BREVO_API_KEY") or "").strip()
            sender_email = (settings.get("BREVO_SENDER_EMAIL") or "").strip()
            sender_name = (settings.get("BREVO_SENDER_NAME") or "Vendly").strip() or "Vendly"
            frontend_url = (settings.get("FRONTEND_PUBLIC_URL") or "http://localhost:5173").rstrip("/")
            return use_brevo, api_key, sender_email, sender_name, frontend_url
    except Exception:
        pass

    try:
        from app.core.config import Settings
        cfg = Settings.from_environment()
        return (
            bool(cfg.use_brevo),
            (cfg.brevo_api_key or "").strip(),
            (cfg.brevo_sender_email or "").strip(),
            (cfg.brevo_sender_name or "Vendly").strip() or "Vendly",
            (cfg.frontend_public_url or "http://localhost:5173").rstrip("/"),
        )
    except Exception:
        return False, "", "", "Vendly", "http://localhost:5173"


def is_brevo_enabled():
    """Return True only when USE_BREVO is True and a Brevo API key is configured."""
    use_brevo, api_key, sender_email, _, _ = _get_brevo_config()
    return use_brevo and bool(api_key) and bool(sender_email)


def send_brevo_email(to_email, to_name, subject, html_content, text_content=None):
    """Send one transactional email via Brevo's v3 API.

    Safely skips if USE_BREVO is false or unconfigured. Never throws an exception
    that could break an ongoing database transaction or business flow.
    """
    to_email = str(to_email or "").strip()
    if not to_email or "@" not in to_email:
        return False

    use_brevo, api_key, sender_email, sender_name, _ = _get_brevo_config()
    if not (use_brevo and api_key and sender_email):
        LOGGER.debug("Brevo email skipped: USE_BREVO is disabled or unconfigured.")
        return False

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email, "name": str(to_name or to_email).strip()}],
        "subject": str(subject or "Vendly Update").strip(),
        "htmlContent": html_content,
    }
    if text_content:
        payload["textContent"] = text_content

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = httpx.post(BREVO_API_URL, json=payload, headers=headers, timeout=10.0)
        if response.status_code in {200, 201, 202}:
            LOGGER.info("Brevo email sent successfully to %s: %s", to_email, subject)
            return True

        LOGGER.warning(
            "Brevo returned status %s for email to %s: %s",
            response.status_code,
            to_email,
            response.text[:300],
        )
        return False
    except Exception as error:
        LOGGER.warning("Could not send Brevo email to %s: %s", to_email, error)
        return False


def _base_email_template(title, body_content, button_text=None, button_url=None):
    """Wrap content in a clean, mobile-responsive HTML email template."""
    action_button = ""
    if button_text and button_url:
        action_button = f"""
        <div style="margin: 28px 0; text-align: center;">
            <a href="{button_url}" style="background-color: #168cf5; color: #ffffff; padding: 12px 26px; font-weight: bold; text-decoration: none; border-radius: 8px; display: inline-block;">
                {button_text}
            </a>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #0f172a;">
    <div style="max-width: 580px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
        <div style="background: linear-gradient(135deg, #0b3b6e 0%, #168cf5 100%); padding: 20px 24px; color: #ffffff;">
            <h1 style="margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">Vendly</h1>
        </div>
        <div style="padding: 24px 28px; line-height: 1.6;">
            <h2 style="margin-top: 0; margin-bottom: 16px; font-size: 18px; color: #0b3b6e;">{title}</h2>
            {body_content}
            {action_button}
        </div>
        <div style="background-color: #f1f5f9; padding: 16px 28px; font-size: 12px; color: #64748b; text-align: center; border-top: 1px solid #e2e8f0;">
            <p style="margin: 0;">Sent via Vendly E-Commerce Platform.</p>
        </div>
    </div>
</body>
</html>"""


def send_notification_email(recipient_email, recipient_name, notification_type, title, message, action_url=None):
    """Send an alert email for a newly created notification (seller or staff member)."""
    body = f"""
    <p style="font-size: 15px; color: #334155; margin-bottom: 12px;">{message}</p>
    <div style="background-color: #f8fafc; border-left: 4px solid #168cf5; padding: 12px 16px; border-radius: 4px; margin: 16px 0;">
        <span style="font-size: 12px; font-weight: 700; color: #168cf5; text-transform: uppercase;">{notification_type.replace('-', ' ')}</span>
    </div>
    """
    html = _base_email_template(
        title=title,
        body_content=body,
        button_text="Open Dashboard" if action_url else None,
        button_url=action_url,
    )
    return send_brevo_email(
        to_email=recipient_email,
        to_name=recipient_name,
        subject=f"[Vendly] {title}",
        html_content=html,
        text_content=f"{title}\n\n{message}",
    )


def send_order_confirmation_email(order, business, recipient_email=None):
    """Send a detailed order confirmation and receipt email to the customer."""
    customer = order.get("customerSnapshot") or {}
    email = recipient_email or customer.get("email") or customer.get("emailAddress")
    if not email:
        return False

    customer_name = customer.get("name") or "Customer"
    order_number = order.get("orderNumber") or order.get("id")
    total_lkr = (order.get("totalAmountMinor") or 0) / 100

    items_html = ""
    for item in order.get("items", []):
        name = item.get("name") or item.get("productName") or "Item"
        qty = item.get("quantity") or 1
        size = f" ({item['size']})" if item.get("size") else ""
        price = (item.get("lineTotalMinor") or 0) / 100
        items_html += f"""
        <tr>
            <td style="padding: 8px 0; border-bottom: 1px solid #f1f5f9;">{name}{size} &times; {qty}</td>
            <td style="padding: 8px 0; border-bottom: 1px solid #f1f5f9; text-align: right; font-weight: 600;">LKR {price:,.2f}</td>
        </tr>
        """

    address = order.get("deliveryAddress") or {}
    addr_line = ", ".join(filter(None, [
        address.get("line1"),
        address.get("city"),
        address.get("district"),
    ]))

    body = f"""
    <p>Hi {customer_name},</p>
    <p>Thank you for your order with <strong>{business.get('name', 'our store')}</strong>! We have received your order and are processing it.</p>
    
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 20px 0;">
        <h3 style="margin-top: 0; margin-bottom: 12px; font-size: 15px; color: #0b3b6e;">Order #{order_number}</h3>
        <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
            {items_html}
            <tr>
                <td style="padding: 10px 0 0; font-weight: 700;">Total:</td>
                <td style="padding: 10px 0 0; text-align: right; font-weight: 700; color: #0b3b6e; font-size: 16px;">LKR {total_lkr:,.2f}</td>
            </tr>
        </table>
    </div>

    <div style="font-size: 13px; color: #64748b; margin-top: 14px;">
        <strong>Delivery Address:</strong><br>
        {addr_line or 'Address as recorded during checkout'}
    </div>
    """

    short_code = business.get("shortCode", "")
    _, _, _, _, frontend_url = _get_brevo_config()
    tracking_url = f"{frontend_url}/stores/{short_code}" if short_code else None

    html = _base_email_template(
        title=f"Order Confirmed: #{order_number}",
        body_content=body,
        button_text="Track Order on Storefront" if tracking_url else None,
        button_url=tracking_url,
    )

    return send_brevo_email(
        to_email=email,
        to_name=customer_name,
        subject=f"Order #{order_number} Confirmed - {business.get('name', 'Vendly Store')}",
        html_content=html,
    )


def send_customer_order_status_email(order, business, new_status, note=None, recipient_email=None):
    """Send an order status tracking update (Confirmed, Packed, Dispatched, Delivered) to the customer."""
    customer = order.get("customerSnapshot") or {}
    email = recipient_email or customer.get("email") or customer.get("emailAddress")
    if not email:
        return False

    customer_name = customer.get("name") or "Customer"
    order_number = order.get("orderNumber") or order.get("id")
    friendly_status = str(new_status or "").replace("-", " ").title()

    body = f"""
    <p>Hi {customer_name},</p>
    <p>Your order <strong>#{order_number}</strong> with <strong>{business.get('name', 'our store')}</strong> has an update:</p>
    
    <div style="background-color: #eff6ff; border-left: 4px solid #168cf5; padding: 14px 18px; border-radius: 6px; margin: 18px 0;">
        <span style="font-size: 12px; font-weight: 700; color: #168cf5; text-transform: uppercase;">Current Status</span>
        <h3 style="margin: 4px 0 0; color: #0b3b6e; font-size: 18px;">{friendly_status}</h3>
        {f'<p style="margin: 8px 0 0; font-size: 13px; color: #475569;">Note: {note}</p>' if note else ''}
    </div>
    """

    short_code = business.get("shortCode", "")
    _, _, _, _, frontend_url = _get_brevo_config()
    tracking_url = f"{frontend_url}/stores/{short_code}" if short_code else None

    html = _base_email_template(
        title=f"Order Update: #{order_number} is {friendly_status}",
        body_content=body,
        button_text="View Order Status" if tracking_url else None,
        button_url=tracking_url,
    )

    return send_brevo_email(
        to_email=email,
        to_name=customer_name,
        subject=f"Update on Order #{order_number}: {friendly_status}",
        html_content=html,
    )
