"""Warranty snapshots and eligibility checks shared by online and shop sales."""

from calendar import monthrange
from datetime import datetime, timezone


def add_calendar_months(start, months):
    """Add months without treating every warranty month as 30 days."""
    target_month = start.month - 1 + months
    year = start.year + target_month // 12
    month = target_month % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def warranty_snapshot(product, start=None):
    """Copy editable inventory warranty terms into an immutable sold-item record."""
    start = start or datetime.now(timezone.utc)
    months = int(product.get("warrantyPeriodMonths", product.get("warrantyMonths", 0)) or 0)
    return {
        "warrantyPeriodMonths": months,
        "warrantyNotes": product.get("warrantyNotes", ""),
        "warrantyStartAt": start if months else None,
        "warrantyExpiresAt": add_calendar_months(start, months) if months else None,
    }


def warranty_is_active(item, now=None):
    """Return False when an item has no warranty or its saved expiry passed."""
    months = int(item.get("warrantyPeriodMonths", item.get("warrantyMonths", 0)) or 0)
    if months < 1:
        return False
    expires_at = item.get("warrantyExpiresAt")
    if not expires_at:
        return False
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at >= (now or datetime.now(timezone.utc))
