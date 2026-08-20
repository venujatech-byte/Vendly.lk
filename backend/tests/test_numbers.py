import pytest

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
