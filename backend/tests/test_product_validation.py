import pytest

from app.core.errors import ApiError
from app.services.product_service import validate_product


def valid_product_payload():
    return {
        "name": "Daisy Running Shoes - Pink",
        "colourName": "Pink",
        "categoryId": "footwear",
        "costPrice": 1200,
        "sellingPrice": 1899,
        "weightKg": 0.45,
        "lowStockThreshold": 2,
        "hasSizes": True,
        "variants": [
            {
                "size": "36",
                "sku": "DFS-PNK-36",
                "barcode": "890123456001",
                "stock": 5,
            },
            {
                "size": "37",
                "sku": "DFS-PNK-37",
                "barcode": "890123456002",
                "stock": 1,
            },
        ],
    }


def test_product_validation_normalizes_prices_and_skus():
    product = validate_product(valid_product_payload())

    assert product["sellingPriceMinor"] == 189900
    assert product["weightGrams"] == 450
    assert product["variants"][0]["sku"] == "DFS-PNK-36"


def test_product_validation_rejects_duplicate_sizes():
    payload = valid_product_payload()
    payload["variants"][1]["size"] = "36"

    with pytest.raises(ApiError) as error:
        validate_product(payload)

    assert error.value.code == "duplicate_size"


def test_product_without_sizes_requires_one_stock_row():
    payload = valid_product_payload()
    payload["hasSizes"] = False

    with pytest.raises(ApiError) as error:
        validate_product(payload)

    assert error.value.code == "validation_error"
