import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from firebase_admin import firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import required_text


PLANS = {
    "early_access": {
        "id": "early_access",
        "name": "Early access",
        "amountMinor": 0,
        "billingPeriod": "free",
        "description": "Explore Vendly while the platform is in early access.",
        "features": [
            "Dashboard and storefront",
            "Orders and inventory",
            "Customer and courier tools",
        ],
    },
    "seller": {
        "id": "seller",
        "name": "Seller plan",
        "amountMinor": 299000,
        "billingPeriod": "month",
        "description": "For independent sellers managing daily online and shop orders.",
        "features": [
            "Chatbot and storefront",
            "Orders and inventory",
            "Customer and courier workflows",
            "Business reports and exports",
        ],
    },
    "team": {
        "id": "team",
        "name": "Team plan",
        "amountMinor": 799000,
        "billingPeriod": "month",
        "description": "For growing businesses that need staff access and advanced operations.",
        "features": [
            "Everything in Seller",
            "Staff roles and permissions",
            "Advanced reports and exports",
            "Priority support",
        ],
    },
}


PAYMENT_STATUS = {
    "2": "paid",
    "0": "pending",
    "-1": "cancelled",
    "-2": "failed",
    "-3": "chargedback",
}


def amount_string(amount_minor):
    return f"{int(amount_minor) / 100:.2f}"


def payhere_checkout_hash(merchant_id, order_id, amount, currency, merchant_secret):
    hashed_secret = hashlib.md5(merchant_secret.encode("utf-8")).hexdigest().upper()
    source = f"{merchant_id}{order_id}{amount}{currency}{hashed_secret}"
    return hashlib.md5(source.encode("utf-8")).hexdigest().upper()


def payhere_notification_signature(
    merchant_id,
    order_id,
    amount,
    currency,
    status_code,
    merchant_secret,
):
    hashed_secret = hashlib.md5(merchant_secret.encode("utf-8")).hexdigest().upper()
    source = (
        f"{merchant_id}{order_id}{amount}{currency}{status_code}{hashed_secret}"
    )
    return hashlib.md5(source.encode("utf-8")).hexdigest().upper()


def public_plans():
    return list(PLANS.values())


def get_billing_summary(database, business_id, payhere_configured=False, sandbox=True):
    business_snapshot = database.collection("businesses").document(business_id).get()
    if not business_snapshot.exists:
        raise ApiError("business_not_found", "Business not found.", 404)

    business = business_snapshot.to_dict() or {}
    billing = business.get("billing") or {}
    plan_id = billing.get("planId") or "early_access"
    current_plan = PLANS.get(plan_id, PLANS["early_access"])
    last_payment = None

    payment_id = billing.get("lastPaymentId") or billing.get("pendingPaymentId")
    if payment_id:
        payment_snapshot = database.collection("billingPayments").document(payment_id).get()
        if payment_snapshot.exists:
            last_payment = serialize_snapshot(payment_snapshot)

    return {
        "currentPlan": current_plan,
        "subscription": {
            "status": billing.get("status") or "active",
            "renewsAt": billing.get("renewsAt"),
            "activatedAt": billing.get("activatedAt"),
        },
        "lastPayment": last_payment,
        "plans": public_plans(),
        "payhere": {
            "configured": bool(payhere_configured),
            "sandbox": bool(sandbox),
        },
    }


def _customer_details(payload):
    try:
        full_name = required_text(payload.get("name"), "Billing name", 120)
        email = required_text(payload.get("email"), "Billing email", 254)
        phone = required_text(payload.get("phone"), "Billing phone", 30)
        address = required_text(payload.get("address"), "Billing address", 250)
        city = required_text(payload.get("city"), "Billing city", 100)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    name_parts = full_name.split(maxsplit=1)
    return {
        "first_name": name_parts[0],
        "last_name": name_parts[1] if len(name_parts) > 1 else "-",
        "email": email,
        "phone": phone,
        "address": address,
        "city": city,
        "country": "Sri Lanka",
    }


def create_checkout(database, business_id, user_uid, payload, settings):
    plan_id = str(payload.get("planId") or "").strip().lower()
    plan = PLANS.get(plan_id)
    if not plan or plan["amountMinor"] <= 0:
        raise ApiError("invalid_plan", "Choose a paid Vendly plan.", 422)

    merchant_id = settings.get("merchant_id")
    merchant_secret = settings.get("merchant_secret")
    if not merchant_id or not merchant_secret:
        raise ApiError(
            "payhere_not_configured",
            "PayHere sandbox is not configured yet. Add the merchant credentials to the backend environment.",
            503,
        )

    customer = _customer_details(payload)
    payment_id = secrets.token_urlsafe(12).replace("-", "").replace("_", "")
    order_id = f"VND-{payment_id.upper()}"
    amount = amount_string(plan["amountMinor"])
    currency = "LKR"
    payment_reference = database.collection("billingPayments").document(payment_id)
    timestamp = firestore.SERVER_TIMESTAMP

    payment_reference.set(
        {
            "businessId": business_id,
            "userUid": user_uid,
            "orderId": order_id,
            "planId": plan_id,
            "amountMinor": plan["amountMinor"],
            "currency": currency,
            "status": "initiated",
            "provider": "payhere",
            "sandbox": bool(settings.get("sandbox", True)),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    database.collection("businesses").document(business_id).update(
        {
            "billing.pendingPaymentId": payment_id,
            "billing.updatedAt": timestamp,
        },
    )

    fields = {
        "merchant_id": merchant_id,
        "return_url": f"{settings['frontend_url']}/?billing=return",
        "cancel_url": f"{settings['frontend_url']}/?billing=cancelled",
        "notify_url": f"{settings['backend_url']}/api/v1/billing/payhere/notify",
        **customer,
        "order_id": order_id,
        "items": f"Vendly {plan['name']} - one month",
        "currency": currency,
        "amount": amount,
        "custom_1": business_id,
        "custom_2": payment_id,
        "hash": payhere_checkout_hash(
            merchant_id,
            order_id,
            amount,
            currency,
            merchant_secret,
        ),
    }

    return {
        "paymentId": payment_id,
        "actionUrl": (
            "https://sandbox.payhere.lk/pay/checkout"
            if settings.get("sandbox", True)
            else "https://www.payhere.lk/pay/checkout"
        ),
        "fields": fields,
    }


def process_payhere_notification(database, form, merchant_id, merchant_secret):
    required_fields = [
        "merchant_id",
        "order_id",
        "payhere_amount",
        "payhere_currency",
        "status_code",
        "md5sig",
        "custom_2",
    ]
    if any(not form.get(field) for field in required_fields):
        raise ApiError("invalid_payment_notification", "Payment notification is incomplete.", 400)

    if form["merchant_id"] != merchant_id:
        raise ApiError("invalid_payment_notification", "Merchant ID does not match.", 400)

    expected_signature = payhere_notification_signature(
        form["merchant_id"],
        form["order_id"],
        form["payhere_amount"],
        form["payhere_currency"],
        form["status_code"],
        merchant_secret,
    )
    if not hmac.compare_digest(expected_signature, form["md5sig"].upper()):
        raise ApiError("invalid_payment_signature", "Payment signature is invalid.", 400)

    payment_reference = database.collection("billingPayments").document(form["custom_2"])
    payment_snapshot = payment_reference.get()
    if not payment_snapshot.exists:
        raise ApiError("payment_not_found", "Billing payment was not found.", 404)

    payment = payment_snapshot.to_dict() or {}
    if payment.get("orderId") != form["order_id"]:
        raise ApiError("invalid_payment_notification", "Payment order does not match.", 400)
    if form["payhere_currency"] != payment.get("currency"):
        raise ApiError(
            "invalid_payment_notification",
            "Payment currency does not match.",
            400,
        )
    if form["payhere_amount"] != amount_string(payment.get("amountMinor", 0)):
        raise ApiError(
            "invalid_payment_notification",
            "Payment amount does not match.",
            400,
        )

    status = PAYMENT_STATUS.get(form["status_code"], "unknown")
    timestamp = firestore.SERVER_TIMESTAMP
    payment_reference.set(
        {
            "status": status,
            "paymentId": form.get("payment_id") or "",
            "method": form.get("method") or "",
            "statusMessage": form.get("status_message") or "",
            "updatedAt": timestamp,
        },
        merge=True,
    )

    if status == "paid":
        now = datetime.now(timezone.utc)
        database.collection("businesses").document(payment["businessId"]).update(
            {
                "billing.planId": payment["planId"],
                "billing.status": "active",
                "billing.activatedAt": now,
                "billing.renewsAt": now + timedelta(days=30),
                "billing.lastPaymentId": payment_snapshot.id,
                "billing.pendingPaymentId": "",
                "billing.updatedAt": timestamp,
            },
        )

    return status
