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


@pytest.mark.parametrize(
    "provided",
    [
        "0112345678",  # Colombo landline
        "0812345678",  # Kandy landline
        "0562345678",
        "0462345678",
        "+94 567589478",
        "567589478",
    ],
)
def test_landlines_are_accepted_as_well_as_mobiles(provided):
    # Requiring a 7 after the country code accepted mobiles only, so a customer
    # giving a landline for delivery was told their own number was invalid,
    # with nothing on screen explaining why.
    assert normalize_sri_lankan_phone(provided).startswith("94")
    assert len(normalize_sri_lankan_phone(provided)) == 11


@pytest.mark.parametrize(
    "provided",
    ["12345", "", "07123456789", "071234567", "abcdefghij"],
)
def test_a_number_of_the_wrong_length_is_still_rejected(provided):
    # Nine national digits, no more and no fewer. Loosening the mobile rule
    # must not turn this into "any digits at all" - a wrong phone number means
    # an undeliverable order.
    with pytest.raises(ValueError, match="9 digits"):
        normalize_sri_lankan_phone(provided)


def test_address_requires_district_and_city():
    with pytest.raises(ValueError, match="City is required"):
        validate_address({"line1": "45 Park Road", "district": "Colombo"})
