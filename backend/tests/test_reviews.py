import pytest

from app.core.errors import ApiError
from app.services.review_service import validate_review_payload


def test_review_requires_rating_between_one_and_five():
    with pytest.raises(ApiError):
        validate_review_payload(
            {
                "orderNumber": "VD-000001",
                "phoneNumber": "0771234567",
                "rating": 6,
                "reviewText": "Good",
            },
        )


def test_review_normalizes_phone_and_order_number():
    review = validate_review_payload(
        {
            "orderNumber": "vd-000001",
            "phoneNumber": "077 123 4567",
            "rating": 5,
            "reviewText": "Excellent product.",
        },
    )

    assert review["orderNumber"] == "VD-000001"
    assert review["normalizedPhone"] == "94771234567"
