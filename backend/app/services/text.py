import re
import unicodedata


def required_text(value, field_name, maximum_length=120):
    text = str(value or "").strip()

    if not text:
        raise ValueError(f"{field_name} is required.")

    if len(text) > maximum_length:
        raise ValueError(
            f"{field_name} must be {maximum_length} characters or fewer.",
        )

    return text


def optional_text(value, maximum_length=500):
    text = str(value or "").strip()

    if len(text) > maximum_length:
        raise ValueError(f"Text must be {maximum_length} characters or fewer.")

    return text


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
