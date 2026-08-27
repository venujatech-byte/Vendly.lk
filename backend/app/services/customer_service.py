import re

from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import optional_text, required_text


def normalize_sri_lankan_phone(value):
    """Accept any Sri Lankan number, stored as 94 plus its nine national digits.

    Every Sri Lankan number is nine digits after the leading zero, whether it
    is a mobile (071, 077) or a landline (011 Colombo, 081 Kandy, 056, 046).
    Requiring a 7 rejected every landline a customer might give for delivery -
    and the customer had no way to know why their own number was "invalid".

    Accepted, all the same number: 0712345678, 712345678, 94712345678,
    +94 71 234 5678, 0094712345678.
    """
    digits = re.sub(r"\D", "", str(value or ""))

    if digits.startswith("00"):
        digits = digits[2:]

    if digits.startswith("94") and len(digits) == 11:
        national = digits[2:]
    elif digits.startswith("0") and len(digits) == 10:
        national = digits[1:]
    else:
        national = digits

    # A leading 0 never survives to here, so a national number that starts with
    # one is a typo - 10 digits, or 8 with a digit dropped.
    if not re.fullmatch(r"[1-9]\d{8}", national):
        raise ValueError(
            "Phone number must be a Sri Lankan number with 9 digits after the "
            "leading 0, for example 0712345678 or 0112345678.",
        )

    return f"94{national}"


def validate_address(value):
    if not isinstance(value, dict):
        raise ValueError("Delivery address must be an object.")

    return {
        "line1": required_text(value.get("line1"), "Address line", 200),
        "line2": optional_text(value.get("line2"), 200),
        "city": required_text(value.get("city"), "City", 100),
        "district": required_text(value.get("district"), "District", 100),
        "postalCode": optional_text(value.get("postalCode"), 20),
        "country": "Sri Lanka",
    }


def validate_customer(payload):
    try:
        name = required_text(payload.get("name"), "Customer name", 160)
        normalized_phone = normalize_sri_lankan_phone(payload.get("phoneNumber"))
        secondary_phone_value = optional_text(payload.get("secondaryPhoneNumber"), 30)
        normalized_secondary_phone = (
            normalize_sri_lankan_phone(secondary_phone_value)
            if secondary_phone_value
            else ""
        )
        email = optional_text(payload.get("email"), 254).lower()
        address = validate_address(payload.get("address"))
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    return {
        "name": name,
        "normalizedPhone": normalized_phone,
        "normalizedSecondaryPhone": normalized_secondary_phone,
        "email": email,
        "address": address,
    }


def list_customers(database, business_id, phone=None, search=None):
    collection = (
        database.collection("businesses")
        .document(business_id)
        .collection("customers")
    )

    if phone:
        try:
            normalized_phone = normalize_sri_lankan_phone(phone)
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

        query = collection.where(
            filter=FieldFilter("normalizedPhone", "==", normalized_phone),
        ).limit(1)
        return [serialize_snapshot(snapshot) for snapshot in query.stream()]

    customers = [
        serialize_snapshot(snapshot)
        for snapshot in collection.order_by("name").limit(200).stream()
    ]
    customers = [
        customer
        for customer in customers
        if customer.get("status", "active") != "archived"
    ]

    if search:
        search_text = search.strip().casefold()
        customers = [
            customer
            for customer in customers
            if search_text in customer.get("name", "").casefold()
            or search_text in customer.get("normalizedPhone", "")
        ]

    return customers


def get_customer(database, business_id, customer_id):
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("customers")
        .document(customer_id)
        .get()
    )

    if not snapshot.exists:
        raise ApiError("customer_not_found", "Customer not found.", 404)

    return serialize_snapshot(snapshot)


def create_customer(database, business_id, payload):
    customer = validate_customer(payload)
    business_reference = database.collection("businesses").document(business_id)
    customer_reference = business_reference.collection("customers").document()
    phone_reference = business_reference.collection("phoneRegistry").document(
        customer["normalizedPhone"],
    )
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        phone_snapshot = phone_reference.get(transaction=current_transaction)

        if phone_snapshot.exists:
            raise ApiError(
                "customer_phone_already_exists",
                "A customer with this phone number already exists.",
                409,
                {"customerId": phone_snapshot.to_dict().get("customerId")},
            )

        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.set(
            customer_reference,
            {
                "name": customer["name"],
                "normalizedPhone": customer["normalizedPhone"],
                "normalizedSecondaryPhone": customer["normalizedSecondaryPhone"],
                "email": customer["email"],
                "addresses": [customer["address"]],
                "defaultAddress": customer["address"],
                "tags": ["new-customer"],
                "privateNotes": "",
                "completedOrderCount": 0,
                "returnedOrderCount": 0,
                "totalSpentMinor": 0,
                "riskLevel": "low",
                "status": "active",
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )
        current_transaction.set(
            phone_reference,
            {
                "customerId": customer_reference.id,
                "normalizedPhone": customer["normalizedPhone"],
                "createdAt": timestamp,
            },
        )

    create_in_transaction(transaction)
    return get_customer(database, business_id, customer_reference.id)


def update_customer(database, business_id, customer_id, payload):
    customer_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("customers")
        .document(customer_id)
    )
    snapshot = customer_reference.get()

    if not snapshot.exists:
        raise ApiError("customer_not_found", "Customer not found.", 404)

    changes = {"updatedAt": firestore.SERVER_TIMESTAMP}

    try:
        if "name" in payload:
            changes["name"] = required_text(payload.get("name"), "Customer name", 160)
        if "email" in payload:
            changes["email"] = optional_text(payload.get("email"), 254).lower()
        if "address" in payload:
            address = validate_address(payload.get("address"))
            changes["defaultAddress"] = address
            changes["addresses"] = firestore.ArrayUnion([address])
        if "privateNotes" in payload:
            changes["privateNotes"] = optional_text(
                payload.get("privateNotes"),
                2000,
            )
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if "status" in payload:
        if payload.get("status") not in {"active", "blocked", "archived"}:
            raise ApiError(
                "validation_error",
                "Customer status must be active, blocked or archived.",
                422,
            )
        changes["status"] = payload["status"]

    customer_reference.update(changes)
    return get_customer(database, business_id, customer_id)
