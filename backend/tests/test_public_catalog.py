from app.services.public_catalog_service import public_product
from app.services.public_chat_service import (
    find_category_request,
    find_product_in_message,
    is_catalog_number_choice,
    is_finished_selecting_items,
    normalize_chat_cart,
    parse_delivery_address,
    public_order_confirmation,
    related_products,
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


def test_finished_selecting_items_recognises_short_checkout_replies():
    assert is_finished_selecting_items("no") is True
    assert is_finished_selecting_items("No thanks") is True
    assert is_finished_selecting_items("That's all") is True
    assert is_finished_selecting_items("done") is True
    assert is_finished_selecting_items("නැහැ") is True
    assert is_finished_selecting_items("No, show another product") is False


def test_chat_category_request_finds_all_matching_products():
    products = [
        {"id": "watch-1", "name": "Alpha Watch", "categoryName": "Smartwatches"},
        {"id": "watch-2", "name": "Beta Watch", "categoryName": "Smartwatches"},
        {"id": "buds", "name": "Earbuds", "categoryName": "Audio"},
    ]

    assert find_category_request("show all smartwatches", products) == "Smartwatches"
    assert find_category_request("smartwatch", products) == "Smartwatches"


def test_related_products_prioritize_the_selected_products_category():
    products = [
        {"id": "watch-1", "name": "Alpha Watch", "categoryName": "Smartwatches"},
        {"id": "buds", "name": "Earbuds", "categoryName": "Audio"},
        {"id": "watch-2", "name": "Beta Watch", "categoryName": "Smartwatches"},
    ]

    recommendations = related_products(products, products[0])

    assert [product["id"] for product in recommendations] == ["watch-2", "buds"]


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


def test_sinhala_and_tamil_words_survive_tokenisation():
    from app.services.public_chat_service import message_tokens, word_characters

    # Combining vowel signs are part of the word. Dropping them, as \w does,
    # turns one Sinhala word into unrelated fragments.
    assert word_characters("නැහැ").strip() == "නැහැ"
    assert word_characters("யாழ்ப்பாணம்").strip() == "யாழ்ப்பாணம்"
    assert "බෑග්" in message_tokens("මට බෑග් එකක් ඕන")
    assert message_tokens("hello, world!") == {"hello", "world"}


def test_products_are_matched_by_a_sinhala_product_name():
    products = [
        {"id": "bag", "name": "ලෙදර් බෑග්", "shortCode": "B1a2Cd"},
        {"id": "watch", "name": "ස්මාට් වොච්", "shortCode": "W3e4Fg"},
    ]

    assert find_product_in_message("ලෙදර් බෑග් ගැන කියන්න", products)["id"] == "bag"
    assert find_product_in_message("ස්මාට් වොච් තියෙනවද", products)["id"] == "watch"


def test_ambiguous_matches_are_returned_for_a_follow_up_question():
    from app.services.public_chat_service import find_matching_products

    products = [
        {"id": "pink", "name": "Daisy Running Shoes Pink"},
        {"id": "black", "name": "Daisy Running Shoes Black"},
    ]
    matches = find_matching_products("Tell me about Daisy shoes", products)

    # The chat asks which one instead of falling through to a dead end.
    assert {product["id"] for product in matches} == {"pink", "black"}
    assert find_product_in_message("Tell me about Daisy shoes", products) is None


def test_related_products_prefer_the_same_category_and_nearest_price():
    products = [
        {"id": "target", "name": "Bag A", "categoryName": "Bags", "sellingPriceMinor": 300000},
        {"id": "far", "name": "Bag B", "categoryName": "Bags", "sellingPriceMinor": 2500000},
        {"id": "near", "name": "Bag C", "categoryName": "Bags", "sellingPriceMinor": 350000},
        {"id": "other", "name": "Watch", "categoryName": "Watches", "sellingPriceMinor": 310000},
    ]
    suggestions = related_products(products, products[0])

    assert [product["id"] for product in suggestions] == ["near", "far", "other"]


def test_script_decides_the_language_without_calling_the_ai(monkeypatch):
    from app.services import public_chat_service

    def fail(_message):
        raise AssertionError("script is unambiguous, the AI must not be called")

    monkeypatch.setattr(public_chat_service, "detect_chat_language", fail)

    assert public_chat_service.conversation_language("මට බෑග් එකක් ඕන", "en") == "si"
    assert public_chat_service.conversation_language("எனக்கு வேண்டும்", "en") == "ta"


def test_ai_is_asked_only_about_romanised_latin_text(monkeypatch):
    from app.services import public_chat_service

    calls = []

    def fake_detect(message):
        calls.append(message)
        return "si"

    monkeypatch.setattr(public_chat_service, "detect_chat_language", fake_detect)

    # Latin letters cannot be told apart by character range, so the AI decides.
    assert public_chat_service.conversation_language("mata meka ganna ona", "en") == "si"
    assert calls == ["mata meka ganna ona"]


def test_an_established_language_survives_a_plain_data_reply(monkeypatch):
    from app.services import public_chat_service

    def fail(_message):
        raise AssertionError("a settled language must not be re-detected")

    monkeypatch.setattr(public_chat_service, "detect_chat_language", fail)

    # Names, phone numbers and addresses carry no language signal. Re-detecting
    # them would switch a Sinhala customer back to English mid-order.
    assert public_chat_service.conversation_language("0771234567", "si") == "si"
    assert public_chat_service.conversation_language("No. 45 Park Road", "si") == "si"


def test_a_failed_detection_keeps_the_current_language(monkeypatch):
    from app.services import public_chat_service

    monkeypatch.setattr(
        public_chat_service,
        "detect_chat_language",
        lambda _message: None,
    )

    assert public_chat_service.conversation_language("hello there", "en") == "en"


def test_an_explicit_language_request_overrides_detection(monkeypatch):
    from app.services import public_chat_service

    monkeypatch.setattr(
        public_chat_service,
        "detect_chat_language",
        lambda _message: "si",
    )

    assert public_chat_service.conversation_language("reply in english", "si") == "en"
    assert public_chat_service.conversation_language("in tamil please", "en") == "ta"
