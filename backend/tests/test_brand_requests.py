from app.services.public_chat_service import (
    brand_products,
    find_brand_request,
    implied_brands,
)


def catalogue():
    """Shaped like a real seller's: the brand field left empty."""
    return [
        {"id": "le209", "name": "Lenovo LE209", "brand": ""},
        {"id": "gm2", "name": "Lenovo GM 2 pro", "brand": ""},
        {"id": "pb", "name": "Fast Charge Power Bank", "brand": ""},
        {"id": "cable", "name": "Fast Charge Cable", "brand": ""},
        {"id": "mi", "name": "Xiaomi Range Extender", "brand": "Xiaomi"},
    ]


def test_a_brand_is_read_off_product_names_when_the_field_is_empty():
    # The brand field is optional and most sellers skip it, so "Lenovo" lived
    # only inside the product names. Brand requests matched nothing and the
    # customer was handed the whole catalogue instead.
    assert find_brand_request("lenovo", catalogue()) == "Lenovo"


def test_cue_words_do_not_hide_the_brand():
    # "show me lenovo" has three tokens, so name matching needed two of them to
    # overlap a product name. Only one did, and the request fell through.
    for message in ("show me lenovo", "send me lenovo", "lenovo products please"):
        assert find_brand_request(message, catalogue()) == "Lenovo", message


def test_a_recorded_brand_still_wins():
    assert find_brand_request("xiaomi", catalogue()) == "Xiaomi"


def test_a_descriptive_opening_phrase_is_not_a_brand():
    # "Fast Charge Power Bank" and "Fast Charge Cable" share their second word,
    # which marks a description rather than a brand. Without this, "is delivery
    # fast?" answered with a product list.
    assert "Fast" not in implied_brands(catalogue())
    assert find_brand_request("is delivery fast?", catalogue()) is None


def test_one_product_alone_does_not_invent_a_brand():
    # A lone product resolves by its own name, so there is nothing to gain and
    # a wrong brand to lose.
    assert implied_brands([{"id": "x", "name": "Solo Widget Pro"}]) == set()


def test_brand_products_finds_them_by_name_as_well_as_by_field():
    # Recognising the brand and then returning an empty list is worse than not
    # recognising it: the customer gets a confident answer with no products.
    assert [item["id"] for item in brand_products(catalogue(), "Lenovo")] == [
        "le209",
        "gm2",
    ]
    assert [item["id"] for item in brand_products(catalogue(), "Xiaomi")] == ["mi"]


def test_a_generic_opening_word_is_never_a_brand():
    # A catalogue of "Product 1", "Product 2" would otherwise answer the
    # request "show products" with "here is what we have from Product".
    catalogue = [
        {"id": f"p{index}", "name": f"Product {index}", "brand": ""}
        for index in range(4)
    ]

    assert implied_brands(catalogue) == set()
    assert find_brand_request("show products", catalogue) is None
