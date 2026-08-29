"""Filtering a category by a feature the customer named.

"Send me smart watches with water resistant" is two requests in one: a
category and a filter. Reading only the category listed every smart watch,
including the ones without the feature - which reads as though they all have
it.

The filter is deterministic on purpose. The seller's text either contains the
feature or it does not; reading it here costs nothing, cannot hallucinate, and
works when the provider is rate limited.
"""

from app.services.public_chat_service import (
    feature_terms,
    product_mentions_feature,
    products_with_features,
)


def watches():
    return [
        {
            "id": "t800",
            "name": "T800 Ultra Smart Watch",
            "description": "1.99 inch display, Bluetooth calling, IP67 water resistant.",
        },
        {
            "id": "zeblace",
            "name": "Zeblace Gts 3 Smart Watch",
            "description": "AMOLED display, 30 days battery, heart rate monitor.",
        },
        {
            "id": "gt4",
            "name": "GT4 Smart Watch",
            "description": "Waterproof design, AMOLED screen, wireless charging.",
        },
    ]


def matching(message):
    terms = feature_terms(message, "Smart watch")
    return [item["id"] for item in products_with_features(watches(), terms)]


def test_the_category_words_are_not_read_as_features():
    # "watches" is the category in plural. Left in, it became a feature no
    # product could match and every request returned nothing.
    assert feature_terms("show me smart watches", "Smart watch") == []
    assert feature_terms("smart watch", "Smart watch") == []


def test_a_feature_filters_the_category():
    assert matching("send me smart watches with water resistant") == ["t800", "gt4"]


def test_the_sellers_wording_does_not_have_to_match_the_customers():
    # The customer says "waterproof"; the seller wrote "IP67 water resistant"
    # on one and "Waterproof" on the other. Exact matching found one of two and
    # would have implied the other lacks the feature.
    assert matching("waterproof smart watches") == ["t800", "gt4"]
    assert product_mentions_feature(watches()[0], "waterproof") is True


def test_every_named_feature_must_be_present():
    # "with bluetooth calling" is one requirement in two words, not two
    # alternatives. Matching either would return watches without calling.
    assert matching("show me smart watches with bluetooth calling") == ["t800"]


def test_a_feature_nobody_has_matches_nothing():
    # The caller reports this plainly. Returning the category unfiltered would
    # read as though these products have the feature.
    assert matching("smart watches with satellite gps") == []


def test_no_feature_named_means_no_filtering():
    # A plain category request must still list the category.
    assert products_with_features(watches(), []) == []
    assert feature_terms("send me smart watches", "Smart watch") == []


def test_the_request_words_are_not_features():
    # "send", "me", "with" and "products" describe the asking, not the product.
    assert feature_terms("send me the products with amoled", "Smart watch") == [
        "amoled",
    ]


def test_a_denied_feature_does_not_count_as_having_it():
    # "No SIM slot" contains the word "sim". Reading that as support is the
    # worst kind of wrong answer: the customer buys the wrong product on the
    # strength of it. This is what sent two watches back to someone asking in
    # Sinhala which ones take a SIM.
    assert product_mentions_feature(
        {"description": "Bluetooth calling, IP67. No SIM slot."}, "sim",
    ) is False
    assert product_mentions_feature(
        {"description": "Supports SIM card, 4G calling."}, "sim",
    ) is True


def test_other_denial_wordings_are_recognised():
    for description in (
        "AMOLED display, without ANC.",
        "Not waterproof.",
        "Does not have wireless charging.",
    ):
        term = (
            "anc" if "ANC" in description
            else "waterproof" if "waterproof" in description
            else "wireless"
        )
        assert product_mentions_feature({"description": description}, term) is False


def test_a_denial_elsewhere_does_not_hide_a_real_mention():
    # Two sentences: one denies a feature, the other confirms the one asked
    # about. Only the mention being looked at matters.
    product = {"description": "No SIM slot. Waterproof to IP68."}

    assert product_mentions_feature(product, "sim") is False
    assert product_mentions_feature(product, "waterproof") is True


def test_sinhala_request_words_are_not_read_as_features():
    # "sim danna puluwan" filtered on "danna" and "puluwan" as though they were
    # features, so no product could ever match a Sinhala question.
    assert feature_terms("sim danna puluwan smart watch nadda", "Smart watch") == [
        "sim",
    ]
    assert feature_terms("amoled ewa thiyenawada", "Smart watch") == ["amoled"]


def test_a_compound_category_typed_as_two_words_is_recognised():
    # The seller writes "PowerBanks", the customer types "power banks". Word
    # matching alone left both halves behind as features nothing could satisfy,
    # so every filtered request silently returned the whole category.
    assert feature_terms("send me 20000mah power banks", "PowerBanks") == ["20000mah"]
    assert feature_terms("send me power banks", "PowerBanks") == []


def test_a_capacity_is_never_absorbed_into_the_category_name():
    # The compound rule matches on substrings, which must never swallow a
    # number - that number is the whole request.
    assert "20000mah" in feature_terms("20000mah powerbank", "PowerBanks")
    assert "10000mah" in feature_terms("10000mah power bank", "PowerBanks")
