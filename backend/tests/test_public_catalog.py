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


def sample_catalogue():
    return [
        {"id": "bag", "name": "Black Leather Bag", "categoryName": "Bags"},
        {"id": "watch", "name": "T800 Smart Watch", "categoryName": "Watches"},
    ]


def test_intent_is_not_classified_while_collecting_customer_details(monkeypatch):
    from app.services import public_chat_service

    def fail(*arguments):
        raise AssertionError("a name or phone number must be read literally")

    monkeypatch.setattr(public_chat_service, "generate_storefront_intent", fail)

    for state in ("collecting-name", "collecting-phone", "collecting-address"):
        assert public_chat_service.storefront_intent(
            "Nimal Perera",
            sample_catalogue(),
            state,
        ) == {}


def test_intent_is_classified_while_browsing(monkeypatch):
    from app.services import public_chat_service

    captured = {}

    def fake_intent(message, product_names, category_names, state):
        captured["names"] = product_names
        captured["categories"] = category_names
        return {"intent": "start_order", "productQuery": "black bag", "language": "si"}

    monkeypatch.setattr(
        public_chat_service,
        "generate_storefront_intent",
        fake_intent,
    )

    result = public_chat_service.storefront_intent(
        "මට black bag එකක් order කරන්න ඕන",
        sample_catalogue(),
        "browsing",
    )

    assert result["intent"] == "start_order"
    assert captured["names"] == ["Black Leather Bag", "T800 Smart Watch"]
    assert captured["categories"] == ["Bags", "Watches"]


def test_a_failed_classification_falls_back_to_the_keyword_ladder(monkeypatch):
    from app.services import public_chat_service

    monkeypatch.setattr(
        public_chat_service,
        "generate_storefront_intent",
        lambda *arguments: None,
    )

    # An empty result means every downstream `intent_is(...)` is False and the
    # deterministic phrase lists decide, exactly as before the classifier.
    assert public_chat_service.storefront_intent("hello", sample_catalogue(), "browsing") == {}


def test_an_english_product_name_inside_a_sinhala_sentence_still_matches():
    from app.services.public_chat_service import find_matching_products

    matches = find_matching_products("මට black leather bag එකක් ඕන", sample_catalogue())

    assert [product["id"] for product in matches] == ["bag"]


def test_change_words_are_matched_as_whole_words():
    from app.services.public_chat_service import word_characters

    # "now" contains "no". Substring matching read "yes, confirm now" as a
    # rejection and wiped the collected customer details.
    words = set(word_characters("yes, confirm now").split())

    assert "no" not in words
    assert "now" in words
    assert "no" in set(word_characters("no, change it").split())


def test_chat_cart_prices_and_weighs_from_the_variant():
    # create_order bills the variant's own price and weight. Using the parent
    # product's values showed one subtotal and charged another whenever a size
    # was priced differently.
    products = [
        {
            "id": "shoe",
            "name": "Runner",
            "sellingPriceMinor": 500000,
            "weightGrams": 900,
            "media": [],
            "variants": [
                {"id": "v-large", "size": "XL", "sellingPriceMinor": 650000, "weightGrams": 1100},
                {"id": "v-small", "size": "S"},
            ],
        },
    ]
    summary = summarize_chat_cart(
        [{"variantId": "v-large", "quantity": 2}, {"variantId": "v-small", "quantity": 1}],
        products,
    )
    by_variant = {line["variantId"]: line for line in summary}

    assert by_variant["v-large"]["unitPriceMinor"] == 650000
    assert by_variant["v-large"]["lineTotalMinor"] == 1300000
    assert by_variant["v-large"]["lineWeightGrams"] == 2200
    # A variant without its own price falls back to the product's.
    assert by_variant["v-small"]["unitPriceMinor"] == 500000
    assert by_variant["v-small"]["lineWeightGrams"] == 900


def test_public_variant_exposes_price_and_weight():
    from app.services.public_catalog_service import public_variant

    variant = public_variant(
        {"id": "v1", "size": "M", "sellingPriceMinor": 320000, "weightGrams": 400, "stockAvailable": 3},
    )

    assert variant["sellingPriceMinor"] == 320000
    assert variant["weightGrams"] == 400


def variant_product():
    return {
        "id": "shoe",
        "name": "Runner",
        "variants": [
            {"id": "v-s", "size": "S", "availableStock": 4},
            {"id": "v-xl", "size": "XL", "availableStock": 2},
        ],
    }


def test_a_single_variant_product_needs_no_size_question():
    from app.services.public_chat_service import choose_variant

    product = {"variants": [{"id": "only", "size": ""}]}

    assert choose_variant(product, "")["id"] == "only"


def test_a_named_size_selects_its_variant():
    from app.services.public_chat_service import choose_variant

    assert choose_variant(variant_product(), "XL")["id"] == "v-xl"
    assert choose_variant(variant_product(), "xl")["id"] == "v-xl"


def test_an_unstated_size_stays_ambiguous_so_the_bot_asks():
    from app.services.public_chat_service import choose_variant

    # Guessing a size would put the wrong item in a real order.
    assert choose_variant(variant_product(), "") is None
    assert choose_variant(variant_product(), "XXL") is None


def test_a_stated_quantity_is_a_total_not_an_addition():
    from app.services.public_chat_service import set_variant_quantity

    # "mata 3k ona" means "I want 3", not "add 3 more". Adding to the existing
    # line put 4 in the order when the customer asked for 3.
    cart, quantity = set_variant_quantity([{"variantId": "v-s", "quantity": 1}], "v-s", 3, 9)

    assert quantity == 3
    assert cart == [{"variantId": "v-s", "quantity": 3}]


def test_add_mode_accumulates_for_thawa_dekak():
    from app.services.public_chat_service import set_variant_quantity

    # "thawa dekak" / "2 more" is the one case that adds to what is there.
    cart, quantity = set_variant_quantity(
        [{"variantId": "v-s", "quantity": 1}], "v-s", 2, 9, "add",
    )

    assert quantity == 3
    assert cart == [{"variantId": "v-s", "quantity": 3}]


def test_a_first_item_with_no_quantity_defaults_to_one():
    from app.services.public_chat_service import set_variant_quantity

    cart, quantity = set_variant_quantity([], "v-s", 0, 9)

    assert quantity == 1
    assert cart == [{"variantId": "v-s", "quantity": 1}]


def test_zero_in_total_mode_removes_the_line():
    from app.services.public_chat_service import set_variant_quantity

    cart, quantity = set_variant_quantity(
        [{"variantId": "v-s", "quantity": 2}, {"variantId": "v-xl", "quantity": 1}],
        "v-s",
        0,
        9,
    )

    assert quantity == 0
    assert cart == [{"variantId": "v-xl", "quantity": 1}]


def test_the_cart_line_is_capped_at_available_stock():
    from app.services.public_chat_service import set_variant_quantity

    # "give me 10" when 2 are left must not build an unfulfillable draft.
    cart, quantity = set_variant_quantity([], "v-xl", 10, 2)

    assert quantity == 2
    assert cart == [{"variantId": "v-xl", "quantity": 2}]


def test_setting_a_quantity_never_mutates_the_caller_s_cart():
    from app.services.public_chat_service import set_variant_quantity

    original = [{"variantId": "v-s", "quantity": 1}]
    set_variant_quantity(original, "v-s", 5, 9)

    assert original == [{"variantId": "v-s", "quantity": 1}]


def stocked_catalogue():
    return [
        {
            "id": "buds",
            "name": "GM2 Pro Earbuds",
            "sellingPriceMinor": 450000,
            "media": [],
            "variants": [{"id": "v-buds", "size": "", "availableStock": 2}],
        },
    ]


def test_a_line_within_stock_is_left_alone():
    from app.services.public_chat_service import reconcile_cart_stock

    cart, sold_out, reduced = reconcile_cart_stock(
        [{"variantId": "v-buds", "quantity": 2}],
        stocked_catalogue(),
    )

    assert cart == [{"variantId": "v-buds", "quantity": 2}]
    assert sold_out == []
    assert reduced == []


def test_a_partly_depleted_line_is_reduced_and_reported():
    from app.services.public_chat_service import reconcile_cart_stock

    # Previously this survived to the order transaction and failed there with
    # "Only 2 unit(s) are available for SKU ..." at the moment of confirmation.
    cart, sold_out, reduced = reconcile_cart_stock(
        [{"variantId": "v-buds", "quantity": 5}],
        stocked_catalogue(),
    )

    assert cart == [{"variantId": "v-buds", "quantity": 2}]
    assert sold_out == []
    assert [available for _product, _variant, available in reduced] == [2]


def test_a_sold_out_line_is_reported_not_silently_dropped():
    from app.services.public_chat_service import reconcile_cart_stock

    # A sold-out variant disappears from the public catalogue, so the old code
    # filtered the line out of the cart without telling anyone.
    cart, sold_out, reduced = reconcile_cart_stock(
        [{"variantId": "v-gone", "quantity": 1}],
        stocked_catalogue(),
    )

    assert cart == []
    assert sold_out == ["v-gone"]
    assert reduced == []


def test_a_zero_stock_variant_still_in_the_payload_counts_as_sold_out():
    from app.services.public_chat_service import reconcile_cart_stock

    products = [
        {
            "id": "buds",
            "name": "GM2 Pro Earbuds",
            "variants": [{"id": "v-buds", "availableStock": 0}],
        },
    ]
    cart, sold_out, _reduced = reconcile_cart_stock(
        [{"variantId": "v-buds", "quantity": 1}],
        products,
    )

    assert cart == []
    assert sold_out == ["v-buds"]


def test_stock_conflict_codes_match_what_create_order_raises():
    from app.services.public_chat_service import STOCK_CONFLICT_CODES

    # These are the recoverable ones. A validation error must still surface.
    assert "insufficient_stock" in STOCK_CONFLICT_CODES
    assert "validation_error" not in STOCK_CONFLICT_CODES


def test_a_quantity_reply_is_read_from_digits_or_from_the_classifier():
    from app.services.public_chat_service import quantity_from_message

    assert quantity_from_message("2") == 2
    assert quantity_from_message("I'll take 3 please") == 3
    # Sinhala words carry no digits, so the classifier supplies the number.
    assert quantity_from_message("dekak", 2) == 2
    assert quantity_from_message("තුනක්", 3) == 3
    # No number anywhere means ask again rather than assume one.
    assert quantity_from_message("what colours do you have?") == 0
    assert quantity_from_message("", 0) == 0


def test_a_digit_inside_a_product_name_is_not_a_quantity():
    from app.services.public_chat_service import quantity_from_message

    # "GM2 pro" and "T800" carry digits that are part of the name. Reading them
    # as a quantity put the wrong number of items in the order.
    assert quantity_from_message("mata GM2 pro ona") == 0
    assert quantity_from_message("T800 watch") == 0
    assert quantity_from_message("GM2 pro 3") == 3


def test_a_quantity_reply_is_clamped():
    from app.services.public_chat_service import quantity_from_message

    assert quantity_from_message("500") == 99
    assert quantity_from_message("0") == 0


def resolve_greeting_language(payload):
    """Exercises the branch create_public_chat_session uses for the greeting."""
    from app.services.public_chat_service import GREETING_LANGUAGES

    requested = str(payload.get("language") or "").strip().casefold()
    return requested if requested in GREETING_LANGUAGES else ""


def test_an_unknown_or_missing_greeting_language_falls_back_to_trilingual():
    # There is no customer message yet to detect from, so a blank result is the
    # signal to greet in all three rather than defaulting everyone to English.
    assert resolve_greeting_language({}) == ""
    assert resolve_greeting_language({"language": ""}) == ""
    assert resolve_greeting_language({"language": "fr"}) == ""
    assert resolve_greeting_language({"language": None}) == ""


def test_a_remembered_greeting_language_is_accepted():
    assert resolve_greeting_language({"language": "si"}) == "si"
    assert resolve_greeting_language({"language": " TA "}) == "ta"
    assert resolve_greeting_language({"language": "en"}) == "en"
