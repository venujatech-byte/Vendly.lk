from app.services.billing_service import (
    amount_string,
    payhere_checkout_hash,
    payhere_notification_signature,
    public_plans,
)


def test_amount_string_uses_two_decimal_places():
    assert amount_string(299000) == "2990.00"


def test_checkout_hash_matches_payhere_formula():
    result = payhere_checkout_hash(
        "1211149",
        "Order123",
        "1000.00",
        "LKR",
        "secret",
    )
    assert result == "1FF5ABC4ABB491EB8D4CF179A1A6A879"


def test_notification_signature_changes_with_status():
    success = payhere_notification_signature(
        "1211149", "Order123", "1000.00", "LKR", "2", "secret"
    )
    failed = payhere_notification_signature(
        "1211149", "Order123", "1000.00", "LKR", "-2", "secret"
    )
    assert success != failed


def test_public_plans_do_not_expose_payment_secrets():
    plans = public_plans()
    assert {plan["id"] for plan in plans} == {"early_access", "seller", "team"}
    assert all("merchantSecret" not in plan for plan in plans)
