from collections import Counter
from decimal import Decimal, ROUND_CEILING

from firebase_admin import firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.numbers import money_to_minor_units, non_negative_integer
from app.services.text import optional_text, required_text, slugify


# The 25 administrative districts of Sri Lanka as (English, Sinhala, Tamil).
# This is the single source of truth for the courier pricing form, the
# storefront address step and the chatbot delivery quote.
DISTRICT_NAMES = (
    ("Ampara", "අම්පාර", "அம்பாறை"),
    ("Anuradhapura", "අනුරාධපුර", "அனுராதபுரம்"),
    ("Badulla", "බදුල්ල", "பதுளை"),
    ("Batticaloa", "මඩකලපුව", "மட்டக்களப்பு"),
    ("Colombo", "කොළඹ", "கொழும்பு"),
    ("Galle", "ගාල්ල", "காலி"),
    ("Gampaha", "ගම්පහ", "கம்பஹா"),
    ("Hambantota", "හම්බන්තොට", "அம்பாந்தோட்டை"),
    ("Jaffna", "යාපනය", "யாழ்ப்பாணம்"),
    ("Kalutara", "කළුතර", "களுத்துறை"),
    ("Kandy", "මහනුවර", "கண்டி"),
    ("Kegalle", "කෑගල්ල", "கேகாலை"),
    ("Kilinochchi", "කිලිනොච්චිය", "கிளிநொச்சி"),
    ("Kurunegala", "කුරුණෑගල", "குருணாகல்"),
    ("Mannar", "මන්නාරම", "மன்னார்"),
    ("Matale", "මාතලේ", "மாத்தளை"),
    ("Matara", "මාතර", "மாத்தறை"),
    ("Monaragala", "මොණරාගල", "மொணராகலை"),
    ("Mullaitivu", "මුලතිව්", "முல்லைத்தீவு"),
    ("Nuwara Eliya", "නුවරඑළිය", "நுவரெலியா"),
    ("Polonnaruwa", "පොළොන්නරුව", "பொலன்னறுவை"),
    ("Puttalam", "පුත්තලම", "புத்தளம்"),
    ("Ratnapura", "රත්නපුර", "இரத்தினபுரி"),
    ("Trincomalee", "ත්‍රිකුණාමලය", "திருகோணமலை"),
    ("Vavuniya", "වවුනියාව", "வவுனியா"),
)

SRI_LANKA_DISTRICTS = tuple(english for english, _sinhala, _tamil in DISTRICT_NAMES)

DISTRICT_SLUGS = {slugify(district): district for district in SRI_LANKA_DISTRICTS}

# Customers write district names in Sinhala, Tamil, romanised Sinhala and with
# the usual English spelling variants. Every form must resolve to one key or the
# delivery quote silently falls back to the courier's common price.
DISTRICT_ALIASES = {
    name.casefold(): slugify(english)
    for english, sinhala, tamil in DISTRICT_NAMES
    for name in (sinhala, tamil)
}
DISTRICT_ALIASES.update(
    {
        "anuradapura": "anuradhapura",
        "baticaloa": "batticaloa",
        "gaalla": "galle",
        "gampha": "gampaha",
        "jaffina": "jaffna",
        "kaluthara": "kalutara",
        "kegalla": "kegalle",
        "killinochchi": "kilinochchi",
        "kolamba": "colombo",
        "kurunagala": "kurunegala",
        "mahanuwara": "kandy",
        "moneragala": "monaragala",
        "mulaitivu": "mullaitivu",
        "mullaithivu": "mullaitivu",
        "nuwaraeliya": "nuwara-eliya",
        "polonnaruva": "polonnaruwa",
        "puttalama": "puttalam",
        "rathnapura": "ratnapura",
        "thirukonamalai": "trincomalee",
        "trincomali": "trincomalee",
        "wavuniya": "vavuniya",
        "yapanaya": "jaffna",
    },
)


def normalize_district(value):
    """Resolve any spelling, script or alias of a district to one stable key."""
    district = required_text(value, "District", 100)
    raw_value = district.strip().casefold()

    if raw_value in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[raw_value]

    slug = slugify(district)
    return DISTRICT_ALIASES.get(slug, slug)


def district_display_name(value):
    """Return the seller-facing district name, or the customer's own wording."""
    try:
        return DISTRICT_SLUGS.get(normalize_district(value), str(value).strip())
    except ValueError:
        return str(value).strip()


def is_known_district(value):
    """True when the value resolves to one of the 25 Sri Lankan districts."""
    try:
        return normalize_district(value) in DISTRICT_SLUGS
    except ValueError:
        return False


def find_district_in_text(value):
    """Return the district key named anywhere in a free-text chat message."""
    text = str(value).casefold()

    for english, sinhala, tamil in DISTRICT_NAMES:
        if any(name.casefold() in text for name in (english, sinhala, tamil)):
            return slugify(english)

    for alias, district_key in DISTRICT_ALIASES.items():
        if alias in text:
            return district_key

    return None


def district_first_kg_price(courier, district_key):
    """The district's own first-kilogram price, or the courier's common price."""
    return courier.get("districtFirstKgPricesMinor", {}).get(
        district_key,
        courier.get("firstKgPriceMinor", 0),
    )


def calculate_delivery_fee(courier, total_weight_grams, district):
    """First-kilogram price for the district + (extra kilograms x extra price)."""
    if total_weight_grams <= 0:
        raise ValueError("Order weight must be greater than zero.")

    extra_grams = max(total_weight_grams - 1000, 0)
    extra_kilograms = int(
        (Decimal(extra_grams) / Decimal(1000)).to_integral_value(
            rounding=ROUND_CEILING,
        ),
    )
    first_kg_price = district_first_kg_price(courier, normalize_district(district))

    return first_kg_price + (extra_kilograms * courier.get("extraKgPriceMinor", 0))


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

    raw_district_prices = payload.get("districtFirstKgPrices", {})

    if waybill_end < waybill_start:
        raise ApiError("validation_error", "Waybill range end must be greater than or equal to its start.", 422)

    if not isinstance(raw_district_prices, dict):
        raise ApiError(
            "validation_error",
            "District first-kilogram prices must be an object.",
            422,
        )

    district_first_kg_prices_minor = {}

    for district, amount in raw_district_prices.items():
        try:
            district_key = normalize_district(district)
            district_first_kg_prices_minor[district_key] = money_to_minor_units(
                amount,
                f"First-kilogram price for {district}",
                allow_zero=False,
            )
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

    unknown_districts = sorted(
        DISTRICT_SLUGS.get(key, key)
        for key in district_first_kg_prices_minor
        if key not in DISTRICT_SLUGS
    )

    if unknown_districts:
        raise ApiError(
            "validation_error",
            f"Unknown district(s): {', '.join(unknown_districts)}.",
            422,
        )

    # The courier table shows one first-kilogram price. It is the price shared
    # by most districts, so it is derived here instead of being typed twice. It
    # also prices any district the seller has not configured yet.
    if district_first_kg_prices_minor:
        first_kg_price_minor = Counter(
            district_first_kg_prices_minor.values(),
        ).most_common(1)[0][0]
    else:
        try:
            first_kg_price_minor = money_to_minor_units(
                payload.get("firstKgPrice"),
                "First-kilogram price",
                allow_zero=False,
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
        "districtFirstKgPricesMinor": district_first_kg_prices_minor,
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
        "districtFirstKgPrices": {
            district: amount / 100
            for district, amount in current.get(
                "districtFirstKgPricesMinor",
                {},
            ).items()
        },
        **payload,
    }
    changes = validate_courier(merged_payload)

    if changes["districtFirstKgPricesMinor"] and "districtSurchargesMinor" in current:
        # The old surcharge map is replaced by per-district first-kilogram
        # prices. The previous form only ever stored one district, so nothing
        # of value is lost.
        changes["districtSurchargesMinor"] = firestore.DELETE_FIELD

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
