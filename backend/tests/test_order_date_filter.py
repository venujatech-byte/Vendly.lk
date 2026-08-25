from app.services.order_service import filter_orders


def test_order_date_filter_uses_sri_lanka_calendar_day():
    # 00:30 on 23 August in Sri Lanka is still 19:00 UTC on 22 August.
    # It must nevertheless appear when the seller filters for 2026-08-23.
    early_colombo_order = {
        "id": "early-order",
        "createdAt": "2026-08-22T19:00:00+00:00",
    }
    later_colombo_order = {
        "id": "later-order",
        "createdAt": "2026-08-23T12:00:00+00:00",
    }

    matching_orders = filter_orders(
        [early_colombo_order, later_colombo_order],
        date_from="2026-08-23",
        date_to="2026-08-23",
    )

    assert [order["id"] for order in matching_orders] == ["early-order", "later-order"]
