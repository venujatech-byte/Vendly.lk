from app.services.courier_service import (
    calculate_delivery_fee,
    courier_recommendation_score,
    district_display_name,
    is_known_district,
    normalize_district,
)


def sample_courier():
    return {
        "firstKgPriceMinor": 45000,
        "extraKgPriceMinor": 10000,
        "districtFirstKgPricesMinor": {
            "colombo": 45000,
            "gampaha": 45000,
            "jaffna": 70000,
            "nuwara-eliya": 52000,
        },
        "successRate": 0.9,
        "returnRate": 0.05,
        "districtIssueCounts": {},
    }


def test_first_kilogram_uses_the_district_price():
    assert calculate_delivery_fee(sample_courier(), 800, "Colombo") == 45000
    assert calculate_delivery_fee(sample_courier(), 1000, "Jaffna") == 70000


def test_partial_extra_kilogram_rounds_up():
    # 1.1 kg to Colombo: 450.00 + (1 x 100.00)
    assert calculate_delivery_fee(sample_courier(), 1100, "Colombo") == 55000


def test_extra_kilogram_price_is_shared_by_every_district():
    # 3.0 kg to Jaffna: 700.00 + (2 x 100.00)
    assert calculate_delivery_fee(sample_courier(), 3000, "Jaffna") == 90000


def test_unconfigured_district_falls_back_to_the_common_price():
    assert calculate_delivery_fee(sample_courier(), 1000, "Matara") == 45000


def test_sinhala_and_tamil_district_names_resolve():
    assert normalize_district("යාපනය") == "jaffna"
    assert normalize_district("யாழ்ப்பாணம்") == "jaffna"
    assert calculate_delivery_fee(sample_courier(), 1000, "යාපනය") == 70000


def test_spelling_variants_resolve_to_one_key():
    assert normalize_district("Kaluthara") == "kalutara"
    assert normalize_district("nuwaraeliya") == "nuwara-eliya"
    assert normalize_district("Nuwara Eliya") == "nuwara-eliya"


def test_display_name_returns_the_seller_facing_spelling():
    assert district_display_name("යාපනය") == "Jaffna"
    assert district_display_name("kaluthara") == "Kalutara"
    assert district_display_name("Springfield") == "Springfield"


def test_unknown_district_is_reported():
    assert is_known_district("Colombo") is True
    assert is_known_district("Springfield") is False


def test_more_branch_issues_reduce_recommendation_score():
    courier = sample_courier()
    normal_score = courier_recommendation_score(courier, 45000, "Kandy")
    courier["districtIssueCounts"] = {"kandy": 3}
    issue_score = courier_recommendation_score(courier, 45000, "Kandy")

    assert issue_score < normal_score


def test_delivery_fee_questions_are_recognised_in_three_languages():
    from app.services.public_chat_service import is_delivery_fee_question

    assert is_delivery_fee_question("What is the delivery fee?") is True
    assert is_delivery_fee_question("delivery eka kiyada?") is True
    assert is_delivery_fee_question("ගාස්තුව කීයද?") is True
    assert is_delivery_fee_question("டெலிவரி கட்டணம் எவ்வளவு?") is True
    assert is_delivery_fee_question("How much is the courier charge") is True


def test_tracking_questions_are_not_treated_as_fee_questions():
    from app.services.public_chat_service import is_delivery_fee_question

    # "delivery" alone belongs to the order-status flow, not the quote flow.
    assert is_delivery_fee_question("where is my delivery") is False
    assert is_delivery_fee_question("has my order been delivered") is False


def test_cart_weight_is_summed_from_the_lines():
    from app.services.public_chat_service import cart_weight_grams

    assert cart_weight_grams([]) == 0
    assert cart_weight_grams(
        [{"lineWeightGrams": 700}, {"lineWeightGrams": 1500}],
    ) == 2200


def test_quote_message_explains_the_district_price_and_extra_rate():
    from app.services.public_chat_service import delivery_quote_message

    message = delivery_quote_message(
        {
            "district": "Jaffna",
            "courierName": "Koombiyo",
            "firstKgPriceMinor": 70000,
            "extraKgPriceMinor": 10000,
            "weightGrams": 2400,
            "isEstimate": False,
            "deliveryFeeMinor": 90000,
        },
    )

    assert "Jaffna" in message
    assert "700.00 for the first 1 kg" in message
    assert "100.00 for each extra 1 kg" in message
    assert "900.00" in message


def test_quote_message_says_when_it_is_a_one_kilogram_estimate():
    from app.services.public_chat_service import delivery_quote_message

    message = delivery_quote_message(
        {
            "district": "Colombo",
            "courierName": "Koombiyo",
            "firstKgPriceMinor": 45000,
            "extraKgPriceMinor": 10000,
            "weightGrams": 1000,
            "isEstimate": True,
            "deliveryFeeMinor": 45000,
        },
    )

    assert "1 kg parcel" in message


def sample_quotes():
    return [
        {
            "courier": {"id": "fast", "name": "Fast", "extraKgPriceMinor": 10000},
            "deliveryFeeMinor": 60000,
            "score": 95.0,
        },
        {
            "courier": {"id": "cheap-poor", "name": "Budget", "extraKgPriceMinor": 8000},
            "deliveryFeeMinor": 45000,
            "score": 70.0,
        },
        {
            "courier": {"id": "cheap-good", "name": "Value", "extraKgPriceMinor": 8000},
            "deliveryFeeMinor": 45000,
            "score": 88.0,
        },
    ]


def test_cheapest_courier_is_chosen_and_quality_breaks_a_price_tie(monkeypatch):
    from app.services import public_chat_service

    monkeypatch.setattr(
        public_chat_service,
        "recommend_couriers",
        lambda *arguments: sample_quotes(),
    )

    best = public_chat_service.cheapest_courier_quote(None, "biz", "Colombo", 1400)

    # The highest-scored courier costs more, so it must not win.
    assert best["courier"]["id"] == "cheap-good"
    assert best["deliveryFeeMinor"] == 45000


def test_no_courier_is_chosen_without_a_district(monkeypatch):
    from app.services import public_chat_service

    def fail(*arguments):
        raise AssertionError("couriers must not be priced without a district")

    monkeypatch.setattr(public_chat_service, "recommend_couriers", fail)

    assert public_chat_service.cheapest_courier_quote(None, "biz", "", 1400) is None


def test_seller_recommendation_still_prefers_delivery_quality():
    # The dashboard ranking is unchanged: a cheaper courier with a worse record
    # must still score below a pricier reliable one.
    reliable = {"successRate": 0.95, "returnRate": 0.02, "districtIssueCounts": {}}
    unreliable = {"successRate": 0.70, "returnRate": 0.20, "districtIssueCounts": {}}

    assert courier_recommendation_score(reliable, 60000, "Colombo") > (
        courier_recommendation_score(unreliable, 45000, "Colombo")
    )


def test_delivery_time_questions_are_recognised_in_three_languages():
    from app.services.public_chat_service import is_delivery_time_question

    assert is_delivery_time_question("how long will delivery take?") is True
    assert is_delivery_time_question("delivery how many days") is True
    assert is_delivery_time_question("kochchara kalak yanawada delivery") is True
    assert is_delivery_time_question("when will it arrive") is True


def test_a_time_question_about_something_else_is_not_a_delivery_question():
    from app.services.public_chat_service import is_delivery_time_question

    # "How long is the warranty" shares the wording but not the subject.
    assert is_delivery_time_question("how long is the warranty") is False
    assert is_delivery_time_question("how much is delivery") is False
    assert is_delivery_time_question("show products") is False


def quote_with_days(days):
    return {
        "district": "Colombo",
        "courierName": "Koombiyo",
        "firstKgPriceMinor": 45000,
        "extraKgPriceMinor": 10000,
        "weightGrams": 600,
        "isEstimate": False,
        "deliveryFeeMinor": 45000,
        "averageDeliveryDays": days,
    }


def test_the_quote_says_how_long_delivery_takes():
    from app.services.public_chat_service import delivery_quote_message

    # "When will it come?" follows "how much?" every single time, and the
    # seller already configured the answer per courier.
    message = delivery_quote_message(quote_with_days(3))

    assert "about 3 working days" in message
    assert "Koombiyo" in message


def test_a_one_day_courier_is_not_described_as_one_days():
    from app.services.public_chat_service import delivery_quote_message

    assert "about 1 working day." in delivery_quote_message(quote_with_days(1))


def test_a_courier_with_no_estimate_says_nothing_about_timing():
    from app.services.public_chat_service import delivery_quote_message

    message = delivery_quote_message(quote_with_days(0))

    assert "working day" not in message
    assert "450.00" in message


def order_with_status(status):
    return {
        "orderNumber": "VD-000012",
        "fulfilmentStatus": status,
        "totalAmountMinor": 945000,
        "courierSnapshot": {"name": "Koombiyo", "averageDeliveryDays": 3},
    }


def test_an_in_flight_order_shows_its_expected_delivery():
    from app.services.public_chat_service import order_information_message

    assert "about 3 working days" in order_information_message(order_with_status("packed"))


def test_a_finished_order_does_not_promise_a_future_delivery():
    from app.services.public_chat_service import order_information_message

    # Telling someone their delivered order will arrive in 3 days is worse
    # than saying nothing.
    for status in ("delivered", "returned", "cancelled"):
        assert "working days" not in order_information_message(order_with_status(status))
