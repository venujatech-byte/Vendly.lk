from app.services.public_catalog_service import public_product
from app.services.public_chat_service import (
    find_category_request,
    find_product_in_message,
    is_catalog_number_choice,
    normalize_chat_cart,
    parse_delivery_address,
    public_order_confirmation,
    summarize_chat_cart,
    token_hash,
)


def test_public_product_hides_cost_and_supplier_fields():
    product = public_product(
        {
            "id": "product-1",
            "name": "Watch",
            "costPriceMinor": 10000,
            "sellingPriceMinor": 20000,
            "supplierId": "private-supplier",
            "variantSummaries": [],
        },
    )

    assert product["sellingPriceMinor"] == 20000
    assert "costPriceMinor" not in product
    assert "supplierId" not in product


def test_chat_session_token_is_stored_as_a_hash():
    assert token_hash("secret-token") != "secret-token"
    assert token_hash("secret-token") == token_hash("secret-token")


def test_public_order_confirmation_hides_internal_costs_and_notes():
    confirmation = public_order_confirmation(
        {
            "id": "order-1",
            "orderNumber": "VD-000001",
            "items": [
                {
                    "productId": "product-1",
                    "variantId": "variant-1",
                    "name": "Watch",
                    "quantity": 1,
                    "unitPriceMinor": 20000,
                    "unitCostMinor": 10000,
                    "lineTotalMinor": 20000,
                },
            ],
            "subtotalMinor": 20000,
            "deliveryFeeMinor": 45000,
            "totalAmountMinor": 65000,
            "privateNote": "Seller-only information",
            "createdBy": "private-user-id",
        },
    )

    assert confirmation["orderNumber"] == "VD-000001"
    assert confirmation["totalAmountMinor"] == 65000
    assert "unitCostMinor" not in confirmation["items"][0]
    assert "privateNote" not in confirmation
    assert "createdBy" not in confirmation


def test_chat_product_selection_accepts_catalogue_number_and_partial_name():
    products = [
        {"id": "watch", "name": "T800 Ultra Smart Watch", "shortCode": "P8x43K"},
        {"id": "earbuds", "name": "Wireless Earbuds", "shortCode": "A2b9Lm"},
    ]

    assert find_product_in_message("2", products)["id"] == "earbuds"
    assert find_product_in_message("Tell me about the smart watch", products)["id"] == "watch"
    assert find_product_in_message("P8x43K", products)["id"] == "watch"


def test_chat_product_selection_does_not_guess_when_names_are_ambiguous():
    products = [
        {"id": "pink", "name": "Daisy Running Shoes Pink"},
        {"id": "black", "name": "Daisy Running Shoes Black"},
    ]

    assert find_product_in_message("Tell me about Daisy shoes", products) is None


def test_catalog_number_choice_only_matches_a_direct_selection():
    assert is_catalog_number_choice("2") is True
    assert is_catalog_number_choice("Product #2") is True
    assert is_catalog_number_choice("Does product 2 have Bluetooth?") is False


def test_chat_category_request_finds_all_matching_products():
    products = [
        {"id": "watch-1", "name": "Alpha Watch", "categoryName": "Smartwatches"},
        {"id": "watch-2", "name": "Beta Watch", "categoryName": "Smartwatches"},
        {"id": "buds", "name": "Earbuds", "categoryName": "Audio"},
    ]

    assert find_category_request("show all smartwatches", products) == "Smartwatches"
    assert find_category_request("smartwatch", products) == "Smartwatches"


def test_chat_cart_is_normalized_and_summarized_for_confirmation():
    cart = normalize_chat_cart(
        [
            {"variantId": "black-42", "quantity": 1},
            {"variantId": "black-42", "quantity": 2},
        ],
    )
    products = [
        {
            "id": "shoe",
            "name": "Running Shoe",
            "sellingPriceMinor": 189900,
            "media": [{"url": "https://example.test/shoe.jpg"}],
            "variants": [
                {"id": "black-42", "size": "42", "sku": "SHOE-BLK-42"},
            ],
        },
    ]

    assert cart == [{"variantId": "black-42", "quantity": 3}]
    assert summarize_chat_cart(cart, products)[0]["lineTotalMinor"] == 569700


def test_chat_delivery_address_requires_street_city_and_district():
    address = parse_delivery_address("No. 45 Park Road, Dehiwala, Colombo")

    assert address["line1"] == "No. 45 Park Road"
    assert address["city"] == "Dehiwala"
    assert address["district"] == "Colombo"
