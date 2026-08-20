from app.services.courier_service import (
    calculate_delivery_fee,
    courier_recommendation_score,
)


def sample_courier():
    return {
        "firstKgPriceMinor": 45000,
        "extraKgPriceMinor": 10000,
        "districtSurchargesMinor": {"jaffna": 5000},
        "successRate": 0.9,
        "returnRate": 0.05,
        "districtIssueCounts": {},
    }


def test_first_kilogram_uses_base_price():
    assert calculate_delivery_fee(sample_courier(), 800, "Colombo") == 45000


def test_partial_extra_kilogram_rounds_up():
    assert calculate_delivery_fee(sample_courier(), 1100, "Colombo") == 55000


def test_district_surcharge_is_added():
    assert calculate_delivery_fee(sample_courier(), 1000, "Jaffna") == 50000


def test_more_branch_issues_reduce_recommendation_score():
    courier = sample_courier()
    normal_score = courier_recommendation_score(courier, 45000, "Kandy")
    courier["districtIssueCounts"] = {"kandy": 3}
    issue_score = courier_recommendation_score(courier, 45000, "Kandy")

    assert issue_score < normal_score
