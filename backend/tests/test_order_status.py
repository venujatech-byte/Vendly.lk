from app.services.order_service import STATUS_TRANSITIONS, returned_customer_risk


def test_order_status_follows_fulfilment_sequence():
    assert "confirmed" in STATUS_TRANSITIONS["needs-confirmation"]
    assert "packed" in STATUS_TRANSITIONS["confirmed"]
    assert "shipped" in STATUS_TRANSITIONS["packed"]
    assert "delivered" in STATUS_TRANSITIONS["shipped"]


def test_completed_order_cannot_move_backwards():
    assert STATUS_TRANSITIONS["delivered"] == set()


def test_returned_customer_risk_increases_after_three_returns():
    assert returned_customer_risk(1) == ("medium", "returned-order")
    assert returned_customer_risk(2) == ("medium", "returned-order")
    assert returned_customer_risk(3) == ("high", "high-return-rate")
