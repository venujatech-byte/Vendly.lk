from decimal import Decimal, ROUND_CEILING

from firebase_admin import firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.numbers import money_to_minor_units, non_negative_integer
from app.services.text import optional_text, required_text, slugify


def normalize_district(value):
    district = required_text(value, "District", 100)
    return slugify(district)


def calculate_delivery_fee(courier, total_weight_grams, district):
    if total_weight_grams <= 0:
        raise ValueError("Order weight must be greater than zero.")

    first_kg_price = courier.get("firstKgPriceMinor", 0)
    extra_kg_price = courier.get("extraKgPriceMinor", 0)
    extra_grams = max(total_weight_grams - 1000, 0)
    extra_kilograms = int(
        (Decimal(extra_grams) / Decimal(1000)).to_integral_value(
            rounding=ROUND_CEILING,
        ),
    )
    district_key = normalize_district(district)
    district_surcharge = courier.get("districtSurchargesMinor", {}).get(
        district_key,
        0,
    )

    return first_kg_price + (extra_kilograms * extra_kg_price) + district_surcharge


def courier_recommendation_score(courier, delivery_fee_minor, district):
    """Score active couriers using price and recorded delivery quality."""
    success_rate = float(courier.get("successRate", 0.8))
    return_rate = float(courier.get("returnRate", 0))
    district_key = normalize_district(district)
    district_issue_count = courier.get("districtIssueCounts", {}).get(district_key, 0)
    price_penalty = delivery_fee_minor / 100000

    return (success_rate * 100) - (return_rate * 60) - (district_issue_count * 4) - price_penalty


def validate_courier(payload):
    try:
        name = required_text(payload.get("name"), "Courier name", 160)
        code = required_text(payload.get("code"), "Courier code", 40).upper()
        first_kg_price_minor = money_to_minor_units(
            payload.get("firstKgPrice"),
            "First-kilogram price",
            allow_zero=False,
        )
        extra_kg_price_minor = money_to_minor_units(
            payload.get("extraKgPrice"),
            "Extra-kilogram price",
        )
        average_delivery_days = non_negative_integer(
            payload.get("averageDeliveryDays", 3),
            "Average delivery days",
        )
        tracking_url_template = optional_text(
            payload.get("trackingUrlTemplate"),
            1000,
        )
        waybill_prefix = optional_text(payload.get("waybillPrefix", "VWB"), 40) or "VWB"
        waybill_start = non_negative_integer(payload.get("waybillStart", 1), "Waybill range start")
        waybill_end = non_negative_integer(payload.get("waybillEnd", 999999), "Waybill range end")
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    raw_surcharges = payload.get("districtSurcharges", {})

    if waybill_end < waybill_start:
        raise ApiError("validation_error", "Waybill range end must be greater than or equal to its start.", 422)

    if not isinstance(raw_surcharges, dict):
        raise ApiError(
            "validation_error",
            "District surcharges must be an object.",
            422,
        )

    district_surcharges_minor = {}

    for district, amount in raw_surcharges.items():
        try:
            district_key = normalize_district(district)
            district_surcharges_minor[district_key] = money_to_minor_units(
                amount,
                f"Surcharge for {district}",
            )
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

    return {
        "name": name,
        "code": code,
        "firstKgPriceMinor": first_kg_price_minor,
        "extraKgPriceMinor": extra_kg_price_minor,
        "averageDeliveryDays": average_delivery_days,
        "trackingUrlTemplate": tracking_url_template,
        "districtSurchargesMinor": district_surcharges_minor,
        "waybillPrefix": waybill_prefix,
        "waybillStart": waybill_start,
        "waybillEnd": waybill_end,
    }


def list_couriers(database, business_id, active_only=False):
    snapshots = (
        database.collection("businesses")
        .document(business_id)
        .collection("couriers")
        .order_by("name")
        .stream()
    )
    couriers = [serialize_snapshot(snapshot) for snapshot in snapshots]

    if active_only:
        couriers = [courier for courier in couriers if courier.get("status") == "active"]

    return couriers


def get_courier(database, business_id, courier_id):
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("couriers")
        .document(courier_id)
        .get()
    )

    if not snapshot.exists:
        raise ApiError("courier_not_found", "Courier not found.", 404)

    return serialize_snapshot(snapshot)


def create_courier(database, business_id, payload):
    courier = validate_courier(payload)
    reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("couriers")
        .document()
    )
    timestamp = firestore.SERVER_TIMESTAMP
    reference.set(
        {
            **courier,
            "successRate": 0.8,
            "returnRate": 0,
            "deliveredOrderCount": 0,
            "returnedOrderCount": 0,
            "districtIssueCounts": {},
            "status": "active",
            "nextWaybillSequence": courier.get("waybillStart", 1),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    return get_courier(database, business_id, reference.id)


def update_courier(database, business_id, courier_id, payload):
    reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("couriers")
        .document(courier_id)
    )

    snapshot = reference.get()

    if not snapshot.exists:
        raise ApiError("courier_not_found", "Courier not found.", 404)

    current = snapshot.to_dict()
    merged_payload = {
        "name": current.get("name"),
        "code": current.get("code"),
        "firstKgPrice": current.get("firstKgPriceMinor", 0) / 100,
        "extraKgPrice": current.get("extraKgPriceMinor", 0) / 100,
        "averageDeliveryDays": current.get("averageDeliveryDays", 3),
        "trackingUrlTemplate": current.get("trackingUrlTemplate", ""),
        "waybillPrefix": current.get("waybillPrefix", "VWB"),
        "waybillStart": current.get("waybillStart", 1),
        "waybillEnd": current.get("waybillEnd", 999999),
        "districtSurcharges": {
            district: amount / 100
            for district, amount in current.get("districtSurchargesMinor", {}).items()
        },
        **payload,
    }
    changes = validate_courier(merged_payload)

    if "status" in payload:
        if payload.get("status") not in {"active", "inactive"}:
            raise ApiError(
                "validation_error",
                "Courier status must be active or inactive.",
                422,
            )
        changes["status"] = payload["status"]

    changes["updatedAt"] = firestore.SERVER_TIMESTAMP
    reference.update(changes)
    return get_courier(database, business_id, courier_id)


def recommend_couriers(database, business_id, total_weight_grams, district):
    recommendations = []

    for courier in list_couriers(database, business_id, active_only=True):
        delivery_fee = calculate_delivery_fee(courier, total_weight_grams, district)
        recommendations.append(
            {
                "courier": courier,
                "deliveryFeeMinor": delivery_fee,
                "score": round(
                    courier_recommendation_score(courier, delivery_fee, district),
                    3,
                ),
            },
        )

    return sorted(recommendations, key=lambda item: item["score"], reverse=True)
