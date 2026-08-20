import pytest

from app.core.errors import ApiError
from app.services.order_service import filter_orders, validate_order_request


def valid_order_payload():
    return {
        "customerId": "customer-1",
        "items": [
            {"variantId": "variant-1", "quantity": 1},
            {"variantId": "variant-1", "quantity": 2},
        ],
        "paymentMethod": "cod",
        "source": "dashboard",
    }


def test_duplicate_item_rows_are_combined():
    order = validate_order_request(valid_order_payload())
    assert order["items"] == [{"variantId": "variant-1", "quantity": 3}]


def test_order_quantity_must_be_positive():
    payload = valid_order_payload()
    payload["items"][0]["quantity"] = 0

    with pytest.raises(ApiError, match="greater than zero"):
        validate_order_request(payload)


def test_invalid_order_source_is_rejected():
    payload = valid_order_payload()
    payload["source"] = "unknown"

    with pytest.raises(ApiError, match="valid order source"):
        validate_order_request(payload)


def test_order_filters_apply_date_courier_and_waybill_search():
    orders = [
        {
            "id": "one",
            "createdAt": "2026-08-17T10:00:00+00:00",
            "courierId": "courier-one",
            "waybillNumber": "VWB-123",
            "fulfilmentStatus": "confirmed",
            "customerSnapshot": {},
            "items": [],
        },
        {
            "id": "two",
            "createdAt": "2026-08-10T10:00:00+00:00",
            "courierId": "courier-two",
            "fulfilmentStatus": "confirmed",
            "customerSnapshot": {},
            "items": [],
        },
    ]

    assert filter_orders(
        orders,
        date_from="2026-08-15",
        courier_id="courier-one",
        search="vwb-123",
    ) == [orders[0]]
