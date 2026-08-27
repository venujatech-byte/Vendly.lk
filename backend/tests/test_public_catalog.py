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


def test_order_numbers_are_recognised_in_a_sentence():
    from app.services.public_chat_service import order_number_in_message

    assert order_number_in_message("VD-000012 kohomada?") == "VD-000012"
    assert order_number_in_message("where is vd 000012") == "VD-000012"
    assert order_number_in_message("check VWB-4471 please") == "VWB-4471"
    # A bare number is a quantity or a catalogue choice, not an order.
    assert order_number_in_message("2") == ""
    assert order_number_in_message("I want 3 of the GM2 pro") == ""


class OrderQuery:
    """Minimal stand-in for the orders collection query chain."""

    def __init__(self, orders):
        self.orders = orders

    def where(self, filter=None):  # noqa: A002 - matches the Firestore keyword
        wanted = filter.value if hasattr(filter, "value") else filter
        self.orders = [o for o in self.orders if o[1].get("orderNumber") == wanted]
        return self

    def limit(self, _count):
        return self

    def stream(self):
        return [FakeOrderSnapshot(i, d) for i, d in self.orders]


class FakeOrderSnapshot:
    def __init__(self, snapshot_id, data):
        self.id = snapshot_id
        self._data = data

    def to_dict(self):
        return self._data


class OrderDatabase:
    def __init__(self, orders):
        self.orders = orders

    def collection(self, _name):
        return self

    def document(self, _name):
        return self

    def stream(self):
        return OrderQuery(self.orders).stream()

    def where(self, filter=None):  # noqa: A002
        return OrderQuery(self.orders).where(filter=filter)


def order_database():
    return OrderDatabase([
        ("o1", {
            "orderNumber": "VD-000012",
            "fulfilmentStatus": "packed",
            # The stored form is what normalize_sri_lankan_phone produces.
            "customerSnapshot": {"normalizedPhone": "94771234567"},
        }),
    ])


def test_an_order_is_returned_only_for_the_phone_that_placed_it():
    from app.services.public_chat_service import find_order_by_number

    found = find_order_by_number(order_database(), "biz", "VD-000012", "0771234567")
    assert found["id"] == "o1"


def test_a_wrong_phone_never_returns_the_order():
    from app.services.public_chat_service import find_order_by_number

    # The order number alone is guessable, so this comparison is the only thing
    # protecting a stranger's delivery address and order history.
    assert find_order_by_number(order_database(), "biz", "VD-000012", "0770000000") is None


def test_an_unknown_order_number_returns_nothing():
    from app.services.public_chat_service import find_order_by_number

    assert find_order_by_number(order_database(), "biz", "VD-999999", "0771234567") is None


def test_an_unparseable_phone_is_rejected_before_any_lookup():
    from app.services.public_chat_service import find_order_by_number

    def fail(*_a, **_k):
        raise AssertionError("must not query orders for an invalid phone")

    class Guard:
        collection = fail

    assert find_order_by_number(Guard(), "biz", "VD-000012", "not a phone") is None
    assert find_order_by_number(Guard(), "biz", "VD-000012", "") is None


def category_catalogue():
    return [
        {"categoryName": "Earbuds"},
        {"categoryName": "Shoes"},
        {"categoryName": "Watches"},
    ]


def test_a_catalogue_request_is_not_mistaken_for_a_category():
    # Stripping "es" off "Shoes" leaves "sho", which sits inside "show". As a
    # substring match that turned "show products" into the Shoes category.
    assert find_category_request("show products", category_catalogue()) is None
    assert find_category_request("show catalogue", category_catalogue()) is None
    assert find_category_request("what do you have", category_catalogue()) is None


def test_a_named_category_still_resolves_in_singular_or_plural():
    assert find_category_request("show me shoes", category_catalogue()) == "Shoes"
    assert find_category_request("shoe", category_catalogue()) == "Shoes"
    assert find_category_request("do you have earbuds", category_catalogue()) == "Earbuds"
    assert find_category_request("show all watches", category_catalogue()) == "Watches"


def test_categories_are_listed_once_in_catalogue_order():
    from app.services.public_chat_service import catalogue_categories

    products = [
        {"categoryName": "Shoes"},
        {"categoryName": "Earbuds"},
        {"categoryName": "Shoes"},
        {"categoryName": ""},
        {},
    ]

    assert catalogue_categories(products) == ["Shoes", "Earbuds"]


def test_a_request_to_pay_by_transfer_is_recognised():
    from app.services.public_chat_service import is_deposit_request

    assert is_deposit_request("can I do a bank transfer?") is True
    assert is_deposit_request("deposit karanna puluwanda") is True
    assert is_deposit_request("send me your account number") is True
    assert is_deposit_request("බැංකු ගිණුම") is True
    assert is_deposit_request("just cash on delivery please") is False


def test_bank_details_are_laid_out_so_a_transfer_is_possible():
    from app.services.public_chat_service import bank_details_message

    message = bank_details_message(
        {
            "bankName": "Commercial Bank",
            "branch": "Nugegoda",
            "accountName": "VS Tech Store",
            "accountNumber": "8001234567",
            "instructions": "Send the slip on WhatsApp.",
        },
        "VS Tech Store",
    )

    assert "Commercial Bank" in message
    assert "8001234567" in message
    assert "Send the slip on WhatsApp." in message
    # The customer has to be told what happens to the rest of the money.
    assert "cash on delivery" in message


def test_a_seller_with_no_bank_details_produces_nothing():
    from app.services.public_chat_service import bank_details_message

    # The caller falls back to a "cash on delivery only" reply rather than
    # sending a half-empty account block.
    assert bank_details_message({}, "VS Tech Store") == ""
    assert bank_details_message({"instructions": "hi"}, "VS Tech Store") == ""


def test_half_and_full_transfers_are_told_apart():
    from app.services.public_chat_service import deposit_choice

    assert deposit_choice("I will send the full amount") == "full"
    assert deposit_choice("just half") == "part"
    assert deposit_choice("only the delivery fee") == "part"
    assert deposit_choice("සම්පූර්ණ") == "full"
    # "Not the full amount" is a part payment, so "part" wins a tie.
    assert deposit_choice("not the full amount, only part") == "part"
    assert deposit_choice("ok") == ""


def test_a_district_name_never_switches_the_conversation_language(monkeypatch):
    from app.services import public_chat_service

    def fail(_message):
        raise AssertionError("a one-word answer must not be language-detected")

    monkeypatch.setattr(public_chat_service, "detect_chat_language", fail)

    # A Sri Lankan place name looks Sinhala to a model, and answering "Gampaha"
    # in an English chat used to flip every later reply to Sinhala.
    assert public_chat_service.conversation_language("Gampaha", "en", "si") == "en"
    assert public_chat_service.conversation_language("Colombo", "en", "si") == "en"


def test_short_data_answers_never_switch_the_language(monkeypatch):
    from app.services import public_chat_service

    monkeypatch.setattr(
        public_chat_service, "detect_chat_language", lambda _m: "si",
    )

    for answer in ("Nimal Perera", "0771234567", "2", "yes", "skip", "XL"):
        assert public_chat_service.conversation_language(answer, "en", "si") == "en", answer


def test_a_real_sentence_can_still_switch_the_language(monkeypatch):
    from app.services import public_chat_service

    monkeypatch.setattr(public_chat_service, "detect_chat_language", lambda _m: None)

    # Long enough to carry actual language, so romanised Sinhala still works.
    assert public_chat_service.conversation_language(
        "mata meka ganna ona", "en", "si",
    ) == "si"


def test_sinhala_script_switches_however_short_it_is(monkeypatch):
    from app.services import public_chat_service

    def fail(_message):
        raise AssertionError("script is unambiguous; no AI call needed")

    monkeypatch.setattr(public_chat_service, "detect_chat_language", fail)

    # The word-count guard applies to Latin text only - script is proof.
    assert public_chat_service.conversation_language("නෑ", "en", None) == "si"
    assert public_chat_service.conversation_language("இல்லை", "en", None) == "ta"


def test_location_questions_are_recognised():
    from app.services.public_chat_service import is_location_question

    assert is_location_question("where are you located?") is True
    assert is_location_question("do you have a physical shop?") is True
    assert is_location_question("can I come to the shop") is True
    assert is_location_question("shop eka kohedha") is True
    assert is_location_question("කඩේ කොහෙද") is True
    assert is_location_question("where is my order") is False


def test_a_physical_shop_is_given_with_its_address():
    from app.services.public_chat_service import store_location_message

    message = store_location_message(
        {
            "isOnlineOnly": False,
            "addressLine": "No. 45 Galle Road",
            "city": "Nugegoda",
            "district": "Colombo",
            "openingHours": "Mon-Sat, 9am to 6pm",
            "mapUrl": "https://maps.app.goo.gl/x",
        },
        "VS Tech Store",
    )

    assert "No. 45 Galle Road, Nugegoda, Colombo" in message
    assert "Mon-Sat, 9am to 6pm" in message
    assert "maps.app.goo.gl" in message


def test_an_online_only_shop_says_so_plainly():
    from app.services.public_chat_service import store_location_message

    # A customer planning to travel needs a straight answer. Saying nothing is
    # what makes them phone the seller.
    message = store_location_message({"isOnlineOnly": True}, "VS Tech Store")

    assert "online store" in message
    assert "no shop to visit" in message


def test_an_unconfigured_location_is_treated_as_online_only():
    from app.services.public_chat_service import store_location_message

    # Better a correct default than an empty address block.
    for location in ({}, None, {"isOnlineOnly": False}):
        assert "online store" in store_location_message(location, "VS Tech Store")


def mixed_catalogue():
    return [
        {"id": "w1", "name": "T800 Watch", "categoryName": "Smart watch", "sellingPriceMinor": 130000},
        {"id": "w2", "name": "T900 Watch", "categoryName": "Smart watch", "sellingPriceMinor": 140000},
        {"id": "w3", "name": "Zeblace Watch", "categoryName": "Smart watch", "sellingPriceMinor": 500000},
        {"id": "p1", "name": "Aspor Power Bank", "categoryName": "Power banks", "sellingPriceMinor": 800000},
        {"id": "p2", "name": "Xiaomi Power Bank", "categoryName": "Power banks", "sellingPriceMinor": 1000000},
    ]


def test_related_products_reach_beyond_the_same_category():
    categories = {
        product["categoryName"]
        for product in related_products(mixed_catalogue(), mixed_catalogue()[0], limit=4)
    }

    # All-same-category made the strip a duplicate of the listing above it.
    assert len(categories) > 1


def test_a_category_is_matched_without_a_show_or_list_cue():
    from app.services.public_chat_service import find_category_request

    products = mixed_catalogue()

    # "I want to order a powerbank" carries no cue word, and used to fall
    # through to the entire catalogue.
    assert find_category_request("I want to order a powerbank", products, require_cue=False) == "Power banks"
    assert find_category_request("I want to order a power bank", products, require_cue=False) == "Power banks"
    assert find_category_request("I wan to order a smartwatch", products, require_cue=False) == "Smart watch"


def test_browsing_still_needs_a_cue_so_a_stray_word_does_not_list_a_category():
    from app.services.public_chat_service import find_category_request

    products = mixed_catalogue()

    assert find_category_request("show me power banks", products) == "Power banks"
    # Without require_cue=False this stays None, so ordinary chatter about a
    # product does not dump a whole category.
    assert find_category_request("my power bank broke last year", products) is None


def test_superlatives_are_recognised():
    from app.services.public_chat_service import wants_a_recommendation

    assert wants_a_recommendation("what is best one") is True
    assert wants_a_recommendation("which one do you recommend") is True
    assert wants_a_recommendation("what is the cheapest") is True
    assert wants_a_recommendation("show me smart watches") is False


def test_cards_follow_the_products_the_answer_named():
    from app.services.public_chat_service import products_named_in

    products = [
        {"id": "p1", "name": "WIWU Essen P-08B 10000mAh 4-Cable Power Bank"},
        {"id": "p2", "name": "ASPOR A337 30,000mAh 22.5W Fast Charging Power Bank"},
        {"id": "x", "name": "Xiaomi 20,000mAh 18W Fast Power Bank"},
        {"id": "w", "name": "T800 Ultra Smart Watch"},
    ]
    answer = (
        "The cheapest is WIWU Essen P-08B 10000mAh 4-Cable Power Bank at LKR "
        "3,990.00. The best value is ASPOR A337 30,000mAh 22.5W Fast Charging "
        "Power Bank at LKR 8,000.00."
    )

    # The cards used to be the first few of the whole catalogue, contradicting
    # the words directly - a smart watch under an answer about power banks.
    assert [p["id"] for p in products_named_in(answer, products)] == ["p1", "p2"]


def test_an_answer_naming_nothing_matches_nothing():
    from app.services.public_chat_service import products_named_in

    products = [{"id": "p1", "name": "WIWU Power Bank"}]

    # The caller falls back to the scoped category rather than guessing.
    assert products_named_in("We do not stock laptops.", products) == []
    assert products_named_in("", products) == []
    assert products_named_in(None, products) == []


def branded_catalogue():
    return [
        {"id": "1", "name": "Lenovo GM2 Pro", "brand": "Lenovo", "categoryName": "Earbuds"},
        {"id": "2", "name": "Lenovo LP40", "brand": "Lenovo", "categoryName": "Earbuds"},
        {"id": "3", "name": "Baseus Bowei EZ10", "brand": "Baseus", "categoryName": "Earbuds"},
        {"id": "4", "name": "ASPOR A337", "brand": "ASPOR", "categoryName": "Power banks"},
    ]


def test_a_named_brand_is_recognised():
    from app.services.public_chat_service import brand_products, find_brand_request

    products = branded_catalogue()

    # Customers shop by brand as readily as by category. Without this the
    # message matched no product and no category, so it fell through to the
    # category picker and the brand was ignored.
    assert find_brand_request("show me lenovo products", products) == "Lenovo"
    assert find_brand_request("show me baseus products", products) == "Baseus"
    assert [p["id"] for p in brand_products(products, "Lenovo")] == ["1", "2"]


def test_a_message_with_no_brand_matches_none():
    from app.services.public_chat_service import find_brand_request

    products = branded_catalogue()

    assert find_brand_request("show me products", products) is None
    assert find_brand_request("I want a smart watch", products) is None


def test_brand_matching_is_whole_word():
    from app.services.public_chat_service import find_brand_request

    # "asp" must not match ASPOR, the same guarantee category matching has.
    products = [{"id": "1", "name": "A337", "brand": "ASPOR"}]
    assert find_brand_request("do you have asp cables", products) is None


def test_an_unanswerable_question_offers_a_way_to_reach_a_person():
    from app.services.public_chat_service import seller_contact_message

    message = seller_contact_message({"phone": "0771234567"})

    # "We don't have that information" alone is a dead end, and a dead end is
    # what sends the customer to a competitor.
    assert "contact you shortly" in message
    assert "0771234567" in message
    assert "https://wa.me/94771234567" in message


def test_the_whatsapp_link_is_derived_from_the_published_number():
    from app.services.public_chat_service import seller_contact_message

    # Any format the seller typed resolves to the same wa.me link, so it is
    # not a second field to keep in step.
    for typed in ("0771234567", "+94 77 123 4567", "94771234567"):
        assert "https://wa.me/94771234567" in seller_contact_message({"phone": typed})


def test_a_seller_with_no_published_phone_still_gets_a_handoff():
    from app.services.public_chat_service import seller_contact_message

    for business in ({}, {"phone": ""}, {"phone": "not a phone"}):
        message = seller_contact_message(business)
        assert "contact you shortly" in message
        assert "wa.me" not in message


def charging_catalogue():
    return [
        {"id": "x", "name": "Xiaomi 20,000mAh 18W Fast Charge Power Bank"},
        {"id": "a", "name": "ASPOR A337 30,000mAh 22.5W Fast Charging Power Bank"},
        {"id": "l", "name": "Lenovo GM2 Pro Earbuds"},
    ]


def test_one_shared_word_does_not_identify_a_product():
    from app.services.public_chat_service import find_matching_products

    # "charge" is a word in "Fast Charge Power Bank". Matching on it alone
    # selected the wrong product and turned a feature question into a request
    # for that product's full spec sheet.
    assert find_matching_products("how long does it take to charge", charging_catalogue()) == []
    assert find_matching_products("is it waterproof", charging_catalogue()) == []


def test_a_real_product_name_still_matches():
    from app.services.public_chat_service import find_matching_products

    products = charging_catalogue()

    assert [p["id"] for p in find_matching_products("lenovo gm2 pro", products)] == ["l"]
    assert [p["id"] for p in find_matching_products("ASPOR A337", products)] == ["a"]
    # A short message is allowed a single-word match: it is all they typed.
    assert [p["id"] for p in find_matching_products("earbuds", products)] == ["l"]


def test_every_spelling_of_a_category_resolves():
    from app.services.public_chat_service import find_category_request

    products = [{"categoryName": "Smart watch"}, {"categoryName": "Power banks"}]

    # One word, two words, singular and plural must all reach the same
    # category. "smart watches" joins to "smartwatches" and needs singularising
    # before it matches a category stored as "Smart watch".
    for message in ("send me smartwatches", "send me smart watches",
                    "send me smartwatch", "send me smart watch"):
        assert find_category_request(message, products, require_cue=False) == "Smart watch", message

    for message in ("I want a power bank", "powerbanks please"):
        assert find_category_request(message, products, require_cue=False) == "Power banks", message


def test_an_ordinary_question_is_not_read_as_a_category():
    from app.services.public_chat_service import find_category_request

    products = [{"categoryName": "Smart watch"}, {"categoryName": "Power banks"}]

    for message in ("how long does it take to charge", "more info", "is it waterproof"):
        assert find_category_request(message, products, require_cue=False) is None, message


def test_a_price_filter_is_not_a_browse_request():
    from app.services.public_chat_service import has_price_constraint

    # "show me below Rs 2000" starts like a browse request, so the catalogue
    # branch claimed it and returned the category picker instead of the
    # products that fit the budget.
    for message in ("show me below Rs 2000", "under 5000", "anything up to 3000",
                    "less than 1500", "Rs 2000 ට අඩු"):
        assert has_price_constraint(message) is True, message


def test_ordinary_messages_carry_no_price_constraint():
    from app.services.public_chat_service import has_price_constraint

    # A bare quantity must not read as a budget.
    for message in ("show me smart watches", "more info", "I want 2 of them",
                    "how long does it take to charge"):
        assert has_price_constraint(message) is False, message


def test_a_question_about_the_products_on_screen_is_recognised():
    from app.services.public_chat_service import refers_to_shown_products

    assert refers_to_shown_products("what is best among these two") is True
    assert refers_to_shown_products("which of both is better") is True
    assert refers_to_shown_products("මේවා අතරින් හොඳම එක") is True
    assert refers_to_shown_products("show me smart watches") is False
