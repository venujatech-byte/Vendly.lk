from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def money_to_minor_units(value, field_name, allow_zero=True):
    """Convert a decimal money value to integer cents for safe storage."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid number.") from error

    minimum = Decimal("0") if allow_zero else Decimal("0.01")

    if amount < minimum:
        requirement = "zero or greater" if allow_zero else "greater than zero"
        raise ValueError(f"{field_name} must be {requirement}.")

    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def kilograms_to_grams(value, field_name="Product weight"):
    """Convert kilograms to integer grams so delivery calculations stay stable."""
    try:
        kilograms = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid number.") from error

    if kilograms <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return int((kilograms * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def non_negative_integer(value, field_name):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive whole number or zero.")

    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{field_name} must be a positive whole number or zero.",
        ) from error

    if number < 0 or str(value).strip() not in {str(number), f"{number}.0"}:
        raise ValueError(f"{field_name} must be a positive whole number or zero.")

    return number


def integer_value(value, field_name):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a whole number.")

    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a whole number.") from error

    if str(value).strip() not in {str(number), f"{number}.0"}:
        raise ValueError(f"{field_name} must be a whole number.")

    return number
