"""Which cards go under an AI answer.

The words and the pictures have to agree. Naming one product and showing two
others reads as a bot that does not know its own catalogue, and it was the
single most reported problem in real use.
"""

from app.services.public_chat_service import products_named_in


def catalogue():
    """Real seller names: trailing category words, punctuation, a leading The."""
    return [
        {"id": "anker", "name": "Anker Soundcore R60i NC Earbuds"},
        {"id": "baseus", "name": "Baseus Bowei EZ10"},
        {"id": "redmi", "name": "Redmi buds 6 play"},
        {"id": "wiwu", "name": "The WIWU Essen Wi-P078 10000mAh Power Bank (Black)"},
        {"id": "xiaomi", "name": "Xiaomi 20,000mAh 18W Fast Charge Power Bank"},
        {"id": "aspor", "name": "ASPOR A337 Power Bank"},
        {"id": "shoes", "name": "Runner Shoes"},
    ]


def named(answer):
    return [product["id"] for product in products_named_in(answer, catalogue())]


def test_a_shortened_name_still_matches():
    # The reported bug. The answer recommended the Anker; the cards showed a
    # Baseus and a Redmi, because "Earbuds" was missing from the model's
    # phrasing and the whole name had to appear verbatim.
    assert named(
        "The Anker Soundcore R60i NC (LKR 9,999.00) has the strongest Adaptive "
        "ANC, making it the top choice.",
    ) == ["anker"]


def test_a_dropped_trailing_category_word_still_matches():
    assert named("I would pick the ASPOR A337 for the price.") == ["aspor"]


def test_every_product_in_a_comparison_is_matched():
    assert named(
        "Between the Baseus Bowei EZ10 and the Redmi buds 6 play, the Baseus "
        "is cheaper.",
    ) == ["baseus", "redmi"]


def test_a_generic_answer_names_nothing():
    # Better to show the scoped list than to invent a match.
    assert named("We have several earbuds in different price ranges.") == []


def test_a_bare_number_is_not_a_model_code():
    # "Redmi buds 6 play" would otherwise match on "6" alone, which appears in
    # a large share of answers that have nothing to do with it.
    assert named("We have 6 earbuds in stock and 10000 happy customers.") == []


def test_a_model_code_alone_is_not_enough():
    # A code quoted out of context - a warranty period, a spec - must not pull
    # up a product card on its own.
    assert named("Every order over 10000 rupees ships free.") == []


def test_a_name_with_no_model_code_matches_on_its_words():
    assert named("The Runner Shoes are on offer.") == ["shoes"]


def test_a_sibling_model_is_not_matched():
    # The most damaging failure: two products of one brand differing only by
    # code. Matching the wrong one shows the customer a different product from
    # the one the answer recommends.
    products = [
        {"id": "a337", "name": "ASPOR A337 Power Bank"},
        {"id": "a389", "name": "ASPOR A389 Power Bank"},
    ]
    matched = products_named_in("The ASPOR A337 is the better buy.", products)

    assert [product["id"] for product in matched] == ["a337"]


def test_an_empty_answer_names_nothing():
    assert products_named_in("", catalogue()) == []
    assert products_named_in(None, catalogue()) == []


def test_a_model_rewriting_the_punctuation_still_matches():
    # The model writes "P-08B" with a non-breaking hyphen and "10000mAh" as
    # "10,000 mAh", so not one token of the catalogue name survives intact.
    # The answer named two products and the cards showed neither.
    answer = (
        "The cheapest options are the WIWU Essen P‑08B 10,000 mAh 4‑Cable "
        "Power Bank and the WIWU Essen Wi‑P078 10,000 mAh powerbank, each "
        "priced at LKR 3,990.00."
    )
    products = [
        {"id": "p08b", "name": "WIWU Essen P-08B 10000mAh 4-Cable Power Bank"},
        {"id": "wip078", "name": "WIWU Essen Wi-P078 10000mAh Power Bank"},
        {"id": "xiaomi", "name": "Xiaomi 20000mAh Power Bank"},
    ]

    assert [item["id"] for item in products_named_in(answer, products)] == [
        "p08b",
        "wip078",
    ]


def test_the_punctuation_blind_match_needs_a_long_name():
    # Squashing removes word boundaries, so a short name could appear inside an
    # unrelated word. Only names long enough to be unmistakable qualify.
    products = [{"id": "x", "name": "Pro"}]

    assert products_named_in("This is a professional grade cable.", products) == []


def test_a_customer_naming_two_products_gets_both():
    from app.services.public_chat_service import products_the_customer_named

    # "zeblace" is one word of five in "Zeblace Gts 3 Smart Watch", so every
    # strict rule missed it - while being the only thing anyone would type.
    # The comparison then had one product and asked which to put beside it.
    products = [
        {"id": "t800", "name": "T800 Ultra Smart Watch", "categoryName": "Smart watch"},
        {"id": "zeb", "name": "Zeblace Gts 3 Smart Watch", "categoryName": "Smart watch"},
        {"id": "xiaomi", "name": "Xiaomi 20000mAh Power Bank", "categoryName": "PowerBanks"},
    ]
    matched = products_the_customer_named(
        "sorry I meant compare t800 ultra and zeblace", products,
    )

    assert sorted(item["id"] for item in matched) == ["t800", "zeb"]


def test_the_generous_reading_is_not_used_for_answers():
    from app.services.public_chat_service import products_the_customer_named

    products = [
        {"id": "t800", "name": "T800 Ultra Smart Watch", "categoryName": "Smart watch"},
        {"id": "zeb", "name": "Zeblace Gts 3 Smart Watch", "categoryName": "Smart watch"},
    ]

    # A category word names a kind of product, not a particular one - even when
    # only one product happens to carry it.
    assert products_the_customer_named("show me smart watches", products) == []
    # And the strict reading, which decides which cards sit under an answer the
    # model wrote, is unchanged.
    assert products_named_in("We have several smart watches.", products) == []
