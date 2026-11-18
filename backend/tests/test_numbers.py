import pytest
from decimal import Decimal

from app.services.numbers import (
    kilograms_to_grams,
    integer_value,
    money_to_minor_units,
    non_negative_integer,
)


def test_money_is_stored_as_integer_minor_units():
    assert money_to_minor_units("1899.50", "Price") == 189950


def test_weight_is_stored_as_integer_grams():
    assert kilograms_to_grams("0.45") == 450


def test_stock_rejects_fractional_values():
    with pytest.raises(ValueError, match="whole number"):
        non_negative_integer("2.5", "Stock")


def test_stock_adjustment_allows_negative_whole_numbers():
    assert integer_value("-3", "Quantity change") == -3


# Reject non-finite values consistently rather than leaking Decimal/overflow errors to API callers.
@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity", float("inf"), float("nan"), Decimal("Infinity")])
@pytest.mark.parametrize("convert", [money_to_minor_units, kilograms_to_grams, non_negative_integer, integer_value])
def test_numeric_helpers_reject_non_finite_values(convert, value):
    with pytest.raises(ValueError):
        convert(value, "Value")


# Values beyond Firestore's signed 64-bit integer range must fail before a database write.
@pytest.mark.parametrize("convert, value", [
    (money_to_minor_units, "92233720368547758.08"),
    (kilograms_to_grams, "9223372036854775.808"),
    (non_negative_integer, 2**63),
    (integer_value, 2**63),
    (integer_value, -(2**63) - 1),
    (money_to_minor_units, "1e1000000"),
    (kilograms_to_grams, "1e1000000"),
])
def test_numeric_helpers_reject_unstorable_values(convert, value):
    with pytest.raises(ValueError):
        convert(value, "Value")


# Retain the current half-up conversion and signed quantity boundaries for valid inputs.
@pytest.mark.parametrize("value, expected", [("1.005", 101), ("0.004", 0), ("1e2", 10000), ("92233720368547758.074", 2**63 - 1)])
def test_money_keeps_existing_rounding(value, expected):
    assert money_to_minor_units(value, "Price") == expected


def test_valid_weight_and_integer_boundaries_remain_accepted():
    assert kilograms_to_grams("0.0015") == 2
    assert kilograms_to_grams("9223372036854775.8074") == 2**63 - 1
    assert non_negative_integer(2**63 - 1, "Stock") == 2**63 - 1
    assert integer_value(-(2**63), "Adjustment") == -(2**63)
