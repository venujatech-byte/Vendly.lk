import pytest

from app.services.text import optional_text, required_text, slugify


def test_required_text_trims_value():
    assert required_text("  Smart Watches  ", "Name") == "Smart Watches"


def test_required_text_rejects_blank_value():
    with pytest.raises(ValueError, match="Name is required"):
        required_text("   ", "Name")


def test_optional_text_allows_blank_value():
    assert optional_text(None) == ""


def test_slugify_creates_url_safe_slug():
    assert slugify("Smart Watches & Wearables") == "smart-watches-wearables"
