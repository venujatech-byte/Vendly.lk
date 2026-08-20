import pytest

from app.services.customer_service import (
    normalize_sri_lankan_phone,
    validate_address,
)


@pytest.mark.parametrize(
    ("provided", "expected"),
    [
        ("077 123 4567", "94771234567"),
        ("+94 77 123 4567", "94771234567"),
        ("771234567", "94771234567"),
    ],
)
def test_phone_numbers_are_normalized(provided, expected):
    assert normalize_sri_lankan_phone(provided) == expected


def test_invalid_phone_is_rejected():
    with pytest.raises(ValueError, match="valid Sri Lankan"):
        normalize_sri_lankan_phone("12345")


def test_address_requires_district_and_city():
    with pytest.raises(ValueError, match="City is required"):
        validate_address({"line1": "45 Park Road", "district": "Colombo"})
