from datetime import datetime, timezone

from app.services.warranty import warranty_is_active, warranty_snapshot


def test_sold_item_keeps_its_original_warranty_terms_and_expiry():
    sold_at = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    sold_item_terms = warranty_snapshot({"warrantyPeriodMonths": 3, "warrantyNotes": "Supplier cover"}, sold_at)

    assert sold_item_terms["warrantyPeriodMonths"] == 3
    assert sold_item_terms["warrantyExpiresAt"] == datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
    assert warranty_is_active(sold_item_terms, datetime(2026, 11, 25, 12, tzinfo=timezone.utc))
    assert not warranty_is_active(sold_item_terms, datetime(2026, 11, 27, 12, tzinfo=timezone.utc))
