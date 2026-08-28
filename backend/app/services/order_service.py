from collections import defaultdict
import logging
from datetime import datetime, timedelta, timezone

from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.courier_service import (
    calculate_delivery_fee,
    get_courier,
    recommend_couriers,
)
from app.services.customer_service import get_customer, validate_address
from app.services.fraud_service import (
    global_fraud_reference,
    global_fraud_summary,
    global_registry_increment,
)
from app.services.chat_event_service import send_order_status_chat_message
from app.services.numbers import money_to_minor_units, non_negative_integer
from app.services.product_service import stock_status
from app.services.text import optional_text, required_text
from app.services.warranty import warranty_snapshot


LOGGER = logging.getLogger(__name__)
# Sri Lanka (Asia/Colombo) is permanently UTC+05:30 and has no daylight-saving
# time. A fixed offset avoids requiring the optional `tzdata` package on
# Windows development machines.
SRI_LANKA_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Colombo")


ALLOWED_PAYMENT_METHODS = {"cod", "paid", "deposit"}
ALLOWED_ORDER_SOURCES = {
    "dashboard",
    "chatbot",
    "whatsapp",
    "facebook",
    "phone",
    "mini-store",
}

STATUS_TRANSITIONS = {
    "needs-confirmation": {"confirmed", "cancelled"},
    "confirmed": {"packed", "cancelled"},
    "packed": {"shipped", "cancelled"},
    "shipped": {"delivered", "returned"},
    "delivered": set(),
    "returned": set(),
    "cancelled": set(),
}


def returned_customer_risk(returned_order_count):
    """Choose the customer risk level and tag after a returned order."""
    if returned_order_count >= 3:
        return "high", "high-return-rate"

    return "medium", "returned-order"


def validate_order_request(payload):
    try:
        customer_id = required_text(payload.get("customerId"), "Customer", 120)
        private_note = optional_text(payload.get("privateNote"), 2000)
        # The customer's own words, kept as their own field. Buried inside the
        # seller's private note they could not be shown as the customer's
        # instruction, and the notification had nothing to quote.
        customer_note = optional_text(payload.get("customerNote"), 500)
        source = optional_text(payload.get("source"), 40) or "dashboard"
        payment_method = optional_text(payload.get("paymentMethod"), 40) or "cod"
        # The customer chose a bank transfer and has not sent it yet. Recorded
        # as an intention, never as money: an order marked paid on a promise is
        # a parcel shipped for free if the transfer never arrives.
        payment_pending = payload.get("paymentPending") is True
        discount_minor = money_to_minor_units(
            payload.get("discountAmount", 0),
            "Discount",
        )
        deposit_minor = money_to_minor_units(
            payload.get("depositAmount", 0),
            "Deposit amount",
        )
        secondary_phone = optional_text(payload.get("secondaryPhoneNumber"), 30)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if source not in ALLOWED_ORDER_SOURCES:
        raise ApiError("validation_error", "Choose a valid order source.", 422)
    if payment_method not in ALLOWED_PAYMENT_METHODS:
        raise ApiError("validation_error", "Choose a valid payment method.", 422)

    raw_items = payload.get("items")

    if not isinstance(raw_items, list) or not raw_items:
        raise ApiError("validation_error", "Add at least one order item.", 422)
    if len(raw_items) > 50:
        raise ApiError(
            "too_many_order_items",
            "An order can contain no more than 50 item rows.",
            422,
        )

    quantities_by_variant = defaultdict(int)

    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            raise ApiError(
                "validation_error",
                f"Order item {index} must be an object.",
                422,
            )

        try:
            variant_id = required_text(
                item.get("variantId"),
                f"Variant in item {index}",
                120,
            )
            quantity = non_negative_integer(
                item.get("quantity"),
                f"Quantity in item {index}",
            )
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

        if quantity == 0:
            raise ApiError(
                "validation_error",
                f"Quantity in item {index} must be greater than zero.",
                422,
            )

        quantities_by_variant[variant_id] += quantity

    return {
        "customerId": customer_id,
        "items": [
            {"variantId": variant_id, "quantity": quantity}
            for variant_id, quantity in quantities_by_variant.items()
        ],
        "courierId": optional_text(payload.get("courierId"), 120),
        "deliveryAddress": payload.get("deliveryAddress"),
        "discountMinor": discount_minor,
        "depositMinor": deposit_minor,
        "secondaryPhoneNumber": secondary_phone,
        "paymentMethod": payment_method,
        "paymentPending": payment_pending,
        "source": source,
        "privateNote": private_note,
        "customerNote": customer_note,
        "assignedStaffUid": optional_text(payload.get("assignedStaffUid"), 120),
        "customerUid": optional_text(payload.get("customerUid"), 128),
    }


def filter_orders(
    orders,
    status=None,
    search=None,
    date_from=None,
    date_to=None,
    courier_id=None,
):
    if status:
        orders = [order for order in orders if order.get("fulfilmentStatus") == status]
    if courier_id:
        orders = [order for order in orders if order.get("courierId") == courier_id]
    # Firestore timestamps are stored in UTC. Sellers choose dates in Sri
    # Lanka, so compare the calendar date after converting to Asia/Colombo.
    # Without this conversion, orders placed between midnight and 5:30 AM
    # local time appear under the previous UTC day.
    def local_order_date(order):
        value = order.get("createdAt")
        if isinstance(value, datetime):
            timestamp = value
        else:
            try:
                timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return str(value or "")[:10]

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(SRI_LANKA_TIMEZONE).date().isoformat()

    if date_from:
        orders = [
            order
            for order in orders
            if local_order_date(order) >= date_from
        ]
    if date_to:
        orders = [
            order
            for order in orders
            if local_order_date(order) <= date_to
        ]
    if search:
        search_text = search.strip().casefold()
        orders = [
            order
            for order in orders
            if search_text in order.get("orderNumber", "").casefold()
            or search_text
            in order.get("customerSnapshot", {}).get("name", "").casefold()
            or search_text
            in order.get("customerSnapshot", {}).get("normalizedPhone", "")
            or search_text in order.get("waybillNumber", "").casefold()
            or any(
                search_text in item.get("name", "").casefold()
                or search_text in item.get("sku", "").casefold()
                or search_text in item.get("barcode", "").casefold()
                for item in order.get("items", [])
            )
        ]

    return orders


def list_orders(
    database,
    business_id,
    status=None,
    search=None,
    date_from=None,
    date_to=None,
    courier_id=None,
):
    collection = (
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
    )
    orders = [
        serialize_snapshot(snapshot)
        for snapshot in collection.order_by("createdAt", direction="DESCENDING")
        .limit(200)
        .stream()
    ]

    return filter_orders(
        orders,
        status=status,
        search=search,
        date_from=date_from,
        date_to=date_to,
        courier_id=courier_id,
    )


def get_order(database, business_id, order_id):
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
        .document(order_id)
        .get()
    )

    if not snapshot.exists:
        raise ApiError("order_not_found", "Order not found.", 404)

    return serialize_snapshot(snapshot)


def choose_courier(database, business_id, courier_id, weight_grams, district):
    if courier_id:
        courier = get_courier(database, business_id, courier_id)

        if courier.get("status") != "active":
            raise ApiError("invalid_courier", "Choose an active courier.", 422)

        return courier

    recommendations = recommend_couriers(
        database,
        business_id,
        weight_grams,
        district,
    )

    if not recommendations:
        raise ApiError(
            "courier_required",
            "Add an active courier before creating an order.",
            422,
        )

    return recommendations[0]["courier"]


def create_order(database, business_id, uid, payload):
    request_data = validate_order_request(payload)
    business_reference = database.collection("businesses").document(business_id)
    customer_reference = business_reference.collection("customers").document(
        request_data["customerId"],
    )
    customer = get_customer(database, business_id, request_data["customerId"])

    try:
        delivery_address = validate_address(
            request_data["deliveryAddress"] or customer.get("defaultAddress"),
        )
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    variant_collection = business_reference.collection("productVariants")
    preliminary_variants = []
    preliminary_weight = 0

    for item in request_data["items"]:
        snapshot = variant_collection.document(item["variantId"]).get()

        if not snapshot.exists:
            raise ApiError("variant_not_found", "A selected product is unavailable.", 404)

        variant = snapshot.to_dict()
        preliminary_variants.append(variant)
        preliminary_weight += variant.get("weightGrams", 0) * item["quantity"]

    courier = choose_courier(
        database,
        business_id,
        request_data["courierId"],
        preliminary_weight,
        delivery_address["district"],
    )
    courier_reference = business_reference.collection("couriers").document(courier["id"])
    order_reference = business_reference.collection("orders").document()
    waybill_reference = business_reference.collection("waybills").document(order_reference.id)
    notification_reference = business_reference.collection("notifications").document()
    fraud_notification_reference = business_reference.collection("notifications").document()
    registry_reference = global_fraud_reference(
        database,
        customer.get("normalizedPhone", ""),
    )
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        business_snapshot = business_reference.get(transaction=current_transaction)
        customer_snapshot = customer_reference.get(transaction=current_transaction)
        courier_snapshot = courier_reference.get(transaction=current_transaction)
        registry_snapshot = registry_reference.get(transaction=current_transaction)

        if not business_snapshot.exists:
            raise ApiError("business_not_found", "Business not found.", 404)
        if not customer_snapshot.exists:
            raise ApiError("customer_not_found", "Customer not found.", 404)
        if customer_snapshot.to_dict().get("status") != "active":
            raise ApiError("customer_blocked", "This customer is not active.", 409)
        if not courier_snapshot.exists or courier_snapshot.to_dict().get("status") != "active":
            raise ApiError("invalid_courier", "Choose an active courier.", 422)

        variant_snapshots = {}
        product_snapshots = {}

        for item in request_data["items"]:
            variant_reference = variant_collection.document(item["variantId"])
            variant_snapshot = variant_reference.get(transaction=current_transaction)

            if not variant_snapshot.exists:
                raise ApiError(
                    "variant_not_found",
                    "A selected product is unavailable.",
                    404,
                )

            variant = variant_snapshot.to_dict()

            if variant.get("status") != "active":
                raise ApiError("inactive_variant", "A selected product is inactive.", 409)
            if variant.get("stockAvailable", 0) < item["quantity"]:
                raise ApiError(
                    "insufficient_stock",
                    f"Only {variant.get('stockAvailable', 0)} unit(s) are available for SKU {variant.get('sku')}.",
                    409,
                )

            variant_snapshots[item["variantId"]] = variant_snapshot
            product_id = variant.get("productId")

            if product_id not in product_snapshots:
                product_snapshot = business_reference.collection("products").document(
                    product_id,
                ).get(transaction=current_transaction)

                if not product_snapshot.exists or product_snapshot.to_dict().get("status") != "active":
                    raise ApiError(
                        "inactive_product",
                        "A selected product is unavailable.",
                        409,
                    )

                product_snapshots[product_id] = product_snapshot

        business = business_snapshot.to_dict()
        customer_data = customer_snapshot.to_dict()
        courier_data = courier_snapshot.to_dict()
        registry_summary = global_fraud_summary(
            registry_snapshot.to_dict() if registry_snapshot.exists else {},
        )
        has_global_fraud_warning = registry_summary["score"] > 0
        sequence = business.get("nextOrderSequence", 1)
        order_prefix = business.get("orderPrefix", "VD")
        order_number = f"{order_prefix}-{sequence:06d}"
        waybill_sequence = courier_data.get(
            "nextWaybillSequence",
            courier_data.get("waybillStart", 1),
        )
        waybill_end = courier_data.get("waybillEnd", 999999)
        if waybill_sequence > waybill_end:
            raise ApiError(
                "waybill_range_exhausted",
                "This courier's waybill range is exhausted. Add a new range before creating the order.",
                409,
            )
        waybill_number = (
            f"{courier_data.get('waybillPrefix', 'VWB')}-{waybill_sequence:08d}"
        )
        items = []
        warranty_started_at = datetime.now(timezone.utc)
        subtotal_minor = 0
        total_weight_grams = 0
        quantities_by_product = defaultdict(int)

        for requested_item in request_data["items"]:
            variant_snapshot = variant_snapshots[requested_item["variantId"]]
            variant = variant_snapshot.to_dict()
            product = product_snapshots[variant["productId"]].to_dict()
            quantity = requested_item["quantity"]
            unit_price_minor = variant.get("sellingPriceMinor", 0)
            line_total_minor = unit_price_minor * quantity
            line_weight_grams = variant.get("weightGrams", 0) * quantity
            media = product.get("media", [])
            items.append(
                {
                    "productId": variant["productId"],
                    "variantId": variant_snapshot.id,
                    "name": product.get("name", "Product"),
                    "size": variant.get("size", ""),
                    "sku": variant.get("sku", ""),
                    "barcode": variant.get("barcode", ""),
                    "quantity": quantity,
                    "unitPriceMinor": unit_price_minor,
                    "unitCostMinor": variant.get("costPriceMinor", 0),
                    "unitWeightGrams": variant.get("weightGrams", 0),
                    "lineTotalMinor": line_total_minor,
                    "mediaUrl": media[0].get("url", "") if media else "",
                    # These terms are frozen at the time of sale.
                    **warranty_snapshot(product, warranty_started_at),
                },
            )
            subtotal_minor += line_total_minor
            total_weight_grams += line_weight_grams
            quantities_by_product[variant["productId"]] += quantity

        if request_data["discountMinor"] > subtotal_minor:
            raise ApiError(
                "invalid_discount",
                "Discount cannot be greater than the item subtotal.",
                422,
            )

        delivery_fee_minor = calculate_delivery_fee(
            courier_data,
            total_weight_grams,
            delivery_address["district"],
        )
        tax_minor = 0
        total_minor = (
            subtotal_minor
            - request_data["discountMinor"]
            + delivery_fee_minor
            + tax_minor
        )
        timestamp = firestore.SERVER_TIMESTAMP

        for requested_item in request_data["items"]:
            variant_snapshot = variant_snapshots[requested_item["variantId"]]
            variant = variant_snapshot.to_dict()
            quantity = requested_item["quantity"]
            available_before = variant.get("stockAvailable", 0)
            available_after = available_before - quantity
            reserved_after = variant.get("stockReserved", 0) + quantity
            product = product_snapshots[variant["productId"]].to_dict()
            threshold = product.get("lowStockThreshold", 0)
            current_transaction.update(
                variant_snapshot.reference,
                {
                    "stockReserved": reserved_after,
                    "stockAvailable": available_after,
                    "stockStatus": stock_status(available_after, threshold),
                    "updatedAt": timestamp,
                },
            )
            current_transaction.set(
                business_reference.collection("inventoryTransactions").document(),
                {
                    "productId": variant["productId"],
                    "variantId": variant_snapshot.id,
                    "type": "reserve",
                    "quantity": quantity,
                    "stockBefore": available_before,
                    "stockAfter": available_after,
                    "orderId": order_reference.id,
                    "reference": order_number,
                    "reason": "Order created",
                    "performedBy": uid,
                    "createdAt": timestamp,
                },
            )

        for product_id, reserved_quantity in quantities_by_product.items():
            product_snapshot = product_snapshots[product_id]
            product = product_snapshot.to_dict()
            variant_updates = {
                item["variantId"]: item["quantity"]
                for item in request_data["items"]
                if variant_snapshots[item["variantId"]].to_dict().get("productId")
                == product_id
            }
            summaries = []

            for summary in product.get("variantSummaries", []):
                quantity = variant_updates.get(summary.get("id"), 0)

                if quantity:
                    available = summary.get("stockAvailable", 0) - quantity
                    summaries.append(
                        {
                            **summary,
                            "stockReserved": summary.get("stockReserved", 0) + quantity,
                            "stockAvailable": available,
                            "stockStatus": stock_status(
                                available,
                                product.get("lowStockThreshold", 0),
                            ),
                        },
                    )
                else:
                    summaries.append(summary)

            available_product_stock = product.get("availableStock", 0) - reserved_quantity
            current_transaction.update(
                product_snapshot.reference,
                {
                    "reservedStock": product.get("reservedStock", 0) + reserved_quantity,
                    "availableStock": available_product_stock,
                    "stockStatus": stock_status(
                        available_product_stock,
                        product.get("lowStockThreshold", 0),
                    ),
                    "variantSummaries": summaries,
                    "updatedAt": timestamp,
                },
            )

        if request_data["depositMinor"] > total_minor:
            raise ApiError("invalid_deposit", "Deposit cannot exceed the order total.", 422)

        paid_amount_minor = (
            0
            if request_data["paymentPending"]
            else total_minor
            if request_data["paymentMethod"] == "paid"
            else request_data["depositMinor"]
            if request_data["paymentMethod"] == "deposit"
            else 0
        )
        payment_status = (
            # Distinct from "unpaid", which is a cash-on-delivery order behaving
            # normally. This one is waiting on a transfer and must not ship.
            "pending-payment"
            if request_data["paymentPending"]
            else "paid" if paid_amount_minor == total_minor
            else "partially-paid" if paid_amount_minor > 0
            else "unpaid"
        )
        current_transaction.set(
            order_reference,
            {
                "orderNumber": order_number,
                "customerId": customer_snapshot.id,
                "customerSnapshot": {
                    "name": customer_data.get("name", ""),
                    "normalizedPhone": customer_data.get("normalizedPhone", ""),
                    "email": customer_data.get("email", ""),
                    "secondaryPhoneNumber": request_data["secondaryPhoneNumber"] or customer_data.get("normalizedSecondaryPhone", ""),
                    "riskLevel": customer_data.get("riskLevel", "low"),
                },
                "items": items,
                "itemCount": sum(item["quantity"] for item in items),
                "subtotalMinor": subtotal_minor,
                "discountTotalMinor": request_data["discountMinor"],
                "deliveryFeeMinor": delivery_fee_minor,
                "taxTotalMinor": tax_minor,
                "totalAmountMinor": total_minor,
                "paidAmountMinor": paid_amount_minor,
                "depositAmountMinor": request_data["depositMinor"],
                "balanceAmountMinor": total_minor - paid_amount_minor,
                "paymentMethod": request_data["paymentMethod"],
                "paymentStatus": payment_status,
                "fulfilmentStatus": "needs-confirmation",
                "deliveryAddress": delivery_address,
                "district": delivery_address["district"],
                "courierId": courier_snapshot.id,
                "courierSnapshot": {
                    "name": courier_data.get("name", ""),
                    "code": courier_data.get("code", ""),
                    "averageDeliveryDays": courier_data.get(
                        "averageDeliveryDays",
                        0,
                    ),
                },
                "totalWeightGrams": total_weight_grams,
                "source": request_data["source"],
                "privateNote": request_data["privateNote"],
                "customerNote": request_data["customerNote"],
                "assignedStaffUid": request_data["assignedStaffUid"] or uid,
                "waybillNumber": waybill_number,
                "stockReservationStatus": "reserved",
                "createdBy": uid,
                "customerUid": request_data["customerUid"],
                "fraudRiskSnapshot": {
                    **registry_summary,
                    "matched": has_global_fraud_warning,
                    "checkedAt": datetime.now(timezone.utc),
                },
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )
        current_transaction.update(
            business_reference,
            {
                "nextOrderSequence": sequence + 1,
                "updatedAt": timestamp,
            },
        )
        customer_changes = {
            "totalOrderCount": customer_data.get("totalOrderCount", 0) + 1,
            "lastOrderId": order_reference.id,
            "lastOrderNumber": order_number,
            "lastOrderDate": datetime.now(timezone.utc),
            "updatedAt": timestamp,
        }
        if has_global_fraud_warning:
            customer_changes.update(
                {
                    "globalFraudWarning": {
                        **registry_summary,
                        "matched": True,
                        "checkedAt": datetime.now(timezone.utc),
                    },
                    "fraudScore": max(
                        int(customer_data.get("fraudScore") or 0),
                        registry_summary["score"],
                    ),
                    "riskLevel": registry_summary["riskLevel"],
                    "tags": firestore.ArrayUnion(["global-fraud-warning"]),
                },
            )
        current_transaction.update(customer_reference, customer_changes)
        current_transaction.update(
            courier_reference,
            {
                "nextWaybillSequence": waybill_sequence + 1,
                "updatedAt": timestamp,
            },
        )
        current_transaction.set(
            waybill_reference,
            {
                "waybillNumber": waybill_number,
                "orderId": order_reference.id,
                "orderNumber": order_number,
                "courierId": courier_snapshot.id,
                "courierSnapshot": {
                    "name": courier_data.get("name", ""),
                    "code": courier_data.get("code", ""),
                },
                "customerSnapshot": {
                    "name": customer_data.get("name", ""),
                    "normalizedPhone": customer_data.get("normalizedPhone", ""),
                },
                "deliveryAddress": delivery_address,
                "totalWeightGrams": total_weight_grams,
                "generatedBy": uid,
                "createdAt": timestamp,
            },
        )
        current_transaction.set(
            notification_reference,
            {
                "type": "new-order",
                "title": f"New order {order_number}",
                # A note is an instruction about this delivery - a landmark, a
                # time to call, a gift wrap. It is worth nothing if the seller
                # only finds it after opening the order.
                "message": (
                    f"{customer_data.get('name', 'Customer')} placed an order."
                    + (
                        f' Note: "{request_data["customerNote"]}"'
                        if request_data["customerNote"]
                        else ""
                    )
                ),
                "hasCustomerNote": bool(request_data["customerNote"]),
                "orderId": order_reference.id,
                "orderNumber": order_number,
                "isRead": False,
                "createdAt": timestamp,
            },
        )
        if has_global_fraud_warning:
            current_transaction.set(
                fraud_notification_reference,
                {
                    "type": "fraud-warning",
                    "title": f"Fraud warning for {order_number}",
                    "message": (
                        f"{customer_data.get('name', 'Customer')} matches the global "
                        f"fraud registry ({registry_summary['reportCount']} report(s), "
                        f"{registry_summary['returnedOrderCount']} return(s))."
                    ),
                    "orderId": order_reference.id,
                    "orderNumber": order_number,
                    "customerId": customer_snapshot.id,
                    "riskLevel": registry_summary["riskLevel"],
                    "fraudScore": registry_summary["score"],
                    "isRead": False,
                    "createdAt": timestamp,
                },
            )

    create_in_transaction(transaction)
    return get_order(database, business_id, order_reference.id)


def update_order_status(database, business_id, order_id, uid, payload):
    try:
        new_status = required_text(payload.get("status"), "Order status", 40)
        note = optional_text(payload.get("note"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    order_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
        .document(order_id)
    )
    business_reference = database.collection("businesses").document(business_id)
    # Allocated outside the transaction, as create_order does: a document
    # reference must not be created during a retry.
    status_notification_reference = business_reference.collection(
        "notifications",
    ).document()
    transaction = database.transaction()

    @google_firestore.transactional
    def update_in_transaction(current_transaction):
        order_snapshot = order_reference.get(transaction=current_transaction)

        if not order_snapshot.exists:
            raise ApiError("order_not_found", "Order not found.", 404)

        order = order_snapshot.to_dict()
        current_status = order.get("fulfilmentStatus")
        allowed_next_statuses = STATUS_TRANSITIONS.get(current_status, set())

        if new_status not in allowed_next_statuses:
            raise ApiError(
                "invalid_status_transition",
                f"Order cannot move from {current_status} to {new_status}.",
                409,
                {"allowedStatuses": sorted(allowed_next_statuses)},
            )

        # A bank transfer that has not arrived yet. Confirming starts the shop
        # picking and packing against money nobody has received, which is the
        # whole risk the customer chose bank transfer to avoid for the seller.
        # Cancelling stays available - an order that never gets paid has to be
        # closable.
        if (
            new_status == "confirmed"
            and order.get("paymentStatus") == "pending-payment"
        ):
            raise ApiError(
                "payment_not_received",
                "This order is waiting on a bank transfer. Record the payment "
                "before confirming it.",
                409,
            )

        stock_action = None

        if new_status in {"cancelled", "returned"}:
            stock_action = "release"
        elif new_status == "delivered":
            stock_action = "sell"

        variant_snapshots = {}
        product_snapshots = {}
        customer_snapshot = None
        courier_snapshot = None

        if stock_action:
            customer_reference = business_reference.collection("customers").document(
                order["customerId"],
            )
            courier_reference = business_reference.collection("couriers").document(
                order["courierId"],
            )
            customer_snapshot = customer_reference.get(transaction=current_transaction)
            courier_snapshot = courier_reference.get(transaction=current_transaction)

            for item in order.get("items", []):
                variant_reference = business_reference.collection(
                    "productVariants",
                ).document(item["variantId"])
                variant_snapshot = variant_reference.get(transaction=current_transaction)

                if not variant_snapshot.exists:
                    raise ApiError(
                        "variant_not_found",
                        "A reserved product size/SKU no longer exists.",
                        409,
                    )

                variant_snapshots[item["variantId"]] = variant_snapshot
                product_id = item["productId"]

                if product_id not in product_snapshots:
                    product_snapshot = business_reference.collection("products").document(
                        product_id,
                    ).get(transaction=current_transaction)

                    if not product_snapshot.exists:
                        raise ApiError(
                            "product_not_found",
                            "A product in this order no longer exists.",
                            409,
                        )

                    product_snapshots[product_id] = product_snapshot

        timestamp = firestore.SERVER_TIMESTAMP

        if stock_action:
            quantities_by_product = defaultdict(int)

            for item in order.get("items", []):
                quantity = item["quantity"]
                variant_snapshot = variant_snapshots[item["variantId"]]
                variant = variant_snapshot.to_dict()
                product = product_snapshots[item["productId"]].to_dict()
                reserved_before = variant.get("stockReserved", 0)

                if reserved_before < quantity:
                    raise ApiError(
                        "invalid_stock_reservation",
                        "The order stock reservation is incomplete.",
                        409,
                    )

                reserved_after = reserved_before - quantity
                available_before = variant.get("stockAvailable", 0)
                on_hand_before = variant.get("stockOnHand", 0)

                if stock_action == "release":
                    available_after = available_before + quantity
                    on_hand_after = on_hand_before
                else:
                    available_after = available_before
                    on_hand_after = on_hand_before - quantity

                current_transaction.update(
                    variant_snapshot.reference,
                    {
                        "stockOnHand": on_hand_after,
                        "stockReserved": reserved_after,
                        "stockAvailable": available_after,
                        "stockStatus": stock_status(
                            available_after,
                            product.get("lowStockThreshold", 0),
                        ),
                        "updatedAt": timestamp,
                    },
                )
                current_transaction.set(
                    business_reference.collection("inventoryTransactions").document(),
                    {
                        "productId": item["productId"],
                        "variantId": item["variantId"],
                        "type": stock_action,
                        "quantity": quantity,
                        "stockBefore": (
                            available_before
                            if stock_action == "release"
                            else on_hand_before
                        ),
                        "stockAfter": (
                            available_after
                            if stock_action == "release"
                            else on_hand_after
                        ),
                        "orderId": order_id,
                        "reference": order.get("orderNumber", ""),
                        "reason": f"Order marked {new_status}",
                        "performedBy": uid,
                        "createdAt": timestamp,
                    },
                )
                quantities_by_product[item["productId"]] += quantity

            for product_id, quantity in quantities_by_product.items():
                product_snapshot = product_snapshots[product_id]
                product = product_snapshot.to_dict()
                item_quantities = {
                    item["variantId"]: item["quantity"]
                    for item in order.get("items", [])
                    if item["productId"] == product_id
                }
                summaries = []

                for summary in product.get("variantSummaries", []):
                    item_quantity = item_quantities.get(summary.get("id"), 0)

                    if not item_quantity:
                        summaries.append(summary)
                        continue

                    available = summary.get("stockAvailable", 0)
                    on_hand = summary.get("stockOnHand", 0)

                    if stock_action == "release":
                        available += item_quantity
                    else:
                        on_hand -= item_quantity

                    summaries.append(
                        {
                            **summary,
                            "stockOnHand": on_hand,
                            "stockReserved": summary.get("stockReserved", 0)
                            - item_quantity,
                            "stockAvailable": available,
                            "stockStatus": stock_status(
                                available,
                                product.get("lowStockThreshold", 0),
                            ),
                        },
                    )

                available_product_stock = product.get("availableStock", 0)
                total_product_stock = product.get("totalStock", 0)

                if stock_action == "release":
                    available_product_stock += quantity
                else:
                    total_product_stock -= quantity

                current_transaction.update(
                    product_snapshot.reference,
                    {
                        "totalStock": total_product_stock,
                        "reservedStock": product.get("reservedStock", 0) - quantity,
                        "availableStock": available_product_stock,
                        "stockStatus": stock_status(
                            available_product_stock,
                            product.get("lowStockThreshold", 0),
                        ),
                        "variantSummaries": summaries,
                        "updatedAt": timestamp,
                    },
                )

        order_changes = {
            "fulfilmentStatus": new_status,
            "updatedAt": timestamp,
            "statusHistory": firestore.ArrayUnion(
                [
                    {
                        "from": current_status,
                        "to": new_status,
                        "note": note,
                        "changedBy": uid,
                        "changedAt": datetime.now(timezone.utc),
                    },
                ],
            ),
        }

        if stock_action == "release":
            order_changes["stockReservationStatus"] = "released"
        elif stock_action == "sell":
            order_changes["stockReservationStatus"] = "sold"

        current_transaction.update(order_reference, order_changes)

        # A customer cancelling is news to the seller: stock has just been
        # released, anything already picked has to be put back, and a courier
        # may have been booked. A seller cancelling their own order is not -
        # they were the one who did it.
        if new_status == "cancelled" and str(uid).startswith("public-chat:"):
            customer_name = (order.get("customerSnapshot") or {}).get(
                "name",
                "The customer",
            )
            current_transaction.set(
                status_notification_reference,
                {
                    "type": "order-cancelled",
                    "title": f"Order {order.get('orderNumber', '')} cancelled",
                    "message": (
                        f"{customer_name} cancelled this order from the chat."
                        + (f" Reason: {note}" if note else "")
                        + " The reserved stock has been released."
                    ),
                    "orderId": order_reference.id,
                    "orderNumber": order.get("orderNumber", ""),
                    "isRead": False,
                    "createdAt": timestamp,
                },
            )

        if new_status == "delivered" and customer_snapshot and customer_snapshot.exists:
            customer = customer_snapshot.to_dict()
            current_transaction.update(
                customer_snapshot.reference,
                {
                    "completedOrderCount": customer.get("completedOrderCount", 0) + 1,
                    "totalSpentMinor": customer.get("totalSpentMinor", 0)
                    + order.get("totalAmountMinor", 0),
                    "tags": firestore.ArrayUnion(["repeat-customer"]),
                    "updatedAt": timestamp,
                },
            )

        if new_status == "returned" and customer_snapshot and customer_snapshot.exists:
            customer = customer_snapshot.to_dict()
            returned_count = customer.get("returnedOrderCount", 0) + 1
            risk_level, return_tag = returned_customer_risk(returned_count)
            customer_phone = order.get("customerSnapshot", {}).get(
                "normalizedPhone",
                "",
            )
            current_transaction.update(
                customer_snapshot.reference,
                {
                    "returnedOrderCount": returned_count,
                    "riskLevel": risk_level,
                    "lastReturnedOrderDate": datetime.now(timezone.utc),
                    "lastReturnReason": note or "returned-order",
                    "tags": firestore.ArrayUnion([return_tag]),
                    "updatedAt": timestamp,
                },
            )
            if customer_phone:
                current_transaction.set(
                    global_fraud_reference(database, customer_phone),
                    global_registry_increment(returned_count=1),
                    merge=True,
                )

        if courier_snapshot and courier_snapshot.exists and new_status in {"delivered", "returned"}:
            courier = courier_snapshot.to_dict()
            delivered_count = courier.get("deliveredOrderCount", 0)
            returned_count = courier.get("returnedOrderCount", 0)

            if new_status == "delivered":
                delivered_count += 1
            else:
                returned_count += 1

            completed_count = delivered_count + returned_count
            current_transaction.update(
                courier_snapshot.reference,
                {
                    "deliveredOrderCount": delivered_count,
                    "returnedOrderCount": returned_count,
                    "successRate": delivered_count / completed_count,
                    "returnRate": returned_count / completed_count,
                    "updatedAt": timestamp,
                },
            )

    update_in_transaction(transaction)
    # The order update is already committed; chat delivery is a separate
    # best-effort event so a temporary chat problem cannot roll back stock.
    try:
        send_order_status_chat_message(
            database,
            business_id,
            order_id,
            order_reference.get().to_dict() or {},
            new_status,
            note,
        )
    except Exception:
        # Status and inventory changes must remain successful even if the
        # optional customer chat channel is temporarily unavailable.
        LOGGER.exception("Order status chat update could not be delivered.")
    return get_order(database, business_id, order_id)


def update_order(database, business_id, order_id, uid, payload):
    """Update seller-editable order fields without changing reserved items."""
    order_reference = (
        database.collection("businesses").document(business_id)
        .collection("orders").document(order_id)
    )
    snapshot = order_reference.get()
    if not snapshot.exists:
        raise ApiError("order_not_found", "Order not found.", 404)

    changes = {"updatedAt": firestore.SERVER_TIMESTAMP, "updatedBy": uid}
    current_order = snapshot.to_dict()
    customer_snapshot = dict(current_order.get("customerSnapshot") or {})
    if "customerName" in payload:
        customer_snapshot["name"] = required_text(payload.get("customerName"), "Customer name", 160)
    if "phoneNumber" in payload:
        phone = required_text(payload.get("phoneNumber"), "Phone number", 40)
        customer_snapshot["normalizedPhone"] = phone
        customer_snapshot["phoneNumber"] = phone
    if "secondaryPhoneNumber" in payload:
        secondary_phone = optional_text(payload.get("secondaryPhoneNumber"), 40)
        customer_snapshot["secondaryPhoneNumber"] = secondary_phone
        customer_snapshot["normalizedSecondaryPhone"] = secondary_phone
    if "email" in payload:
        customer_snapshot["email"] = optional_text(payload.get("email"), 160)
    if any(
        field in payload
        for field in ("customerName", "phoneNumber", "secondaryPhoneNumber", "email")
    ):
        changes["customerSnapshot"] = customer_snapshot
    if "deliveryAddress" in payload:
        address = payload.get("deliveryAddress")
        if not isinstance(address, dict):
            raise ApiError("validation_error", "Delivery address must be an object.", 422)
        changes["deliveryAddress"] = address
    if "privateNote" in payload:
        changes["privateNote"] = optional_text(payload.get("privateNote"), 2000)
    if "assignedStaffUid" in payload:
        changes["assignedStaffUid"] = optional_text(payload.get("assignedStaffUid"), 120)
    if "paymentMethod" in payload:
        payment_method = optional_text(payload.get("paymentMethod"), 40)
        if payment_method not in ALLOWED_PAYMENT_METHODS:
            raise ApiError("validation_error", "Choose a valid payment method.", 422)
        changes["paymentMethod"] = payment_method

    if "waybillNumber" in payload:
        waybill_number = optional_text(payload.get("waybillNumber"), 120).upper()

        if waybill_number:
            duplicate_orders = (
                order_reference.parent
                .where(filter=FieldFilter("waybillNumber", "==", waybill_number))
                .limit(2)
                .stream()
            )
            if any(order.id != order_id for order in duplicate_orders):
                raise ApiError(
                    "duplicate_waybill_number",
                    "This waybill number is already assigned to another order.",
                    409,
                )

        changes["waybillNumber"] = waybill_number

    if "courierId" in payload:
        courier_id = optional_text(payload.get("courierId"), 120)
        if courier_id:
            courier_snapshot = (
                database.collection("businesses").document(business_id)
                .collection("couriers").document(courier_id).get()
            )
            if not courier_snapshot.exists:
                raise ApiError("courier_not_found", "Choose an active courier.", 422)
            changes["courierId"] = courier_id
            changes["courierSnapshot"] = {"id": courier_snapshot.id, **courier_snapshot.to_dict()}
        else:
            changes["courierId"] = ""
            changes["courierSnapshot"] = {}

    order_reference.update(changes)

    if "waybillNumber" in changes and changes["waybillNumber"]:
        waybill_reference = (
            database.collection("businesses").document(business_id)
            .collection("waybills").document(order_id)
        )
        waybill_reference.set(
            {
                "waybillNumber": changes["waybillNumber"],
                "orderId": order_id,
                "orderNumber": current_order.get("orderNumber", ""),
                "courierId": current_order.get("courierId", ""),
                "courierSnapshot": current_order.get("courierSnapshot", {}),
                "customerSnapshot": current_order.get("customerSnapshot", {}),
                "deliveryAddress": current_order.get("deliveryAddress", {}),
                "totalWeightGrams": current_order.get("totalWeightGrams", 0),
                "updatedBy": uid,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
    return get_order(database, business_id, order_id)


# Only an order the seller has not begun working on. Once it is confirmed,
# picked or dispatched, the packed contents no longer match the record, and a
# customer must not be able to change what is already on its way.
MERGEABLE_ORDER_STATUSES = {"needs-confirmation"}


def order_accepts_more_items(order):
    return (order or {}).get("fulfilmentStatus") in MERGEABLE_ORDER_STATUSES


def add_items_to_order(database, business_id, order_id, uid, items):
    """Append items to an order the seller has not confirmed yet.

    A customer who orders again minutes later usually means one delivery, not
    two. `update_order` deliberately never touches reserved items, so this is
    the one path that adds them: it reserves the new stock exactly as
    `create_order` does, then reprices the order - subtotal, weight, delivery
    for the new weight, and total.

    The order keeps its number, its customer and its courier. Only the lines,
    the weight and the money change.
    """
    if not items:
        raise ApiError("validation_error", "No items to add.", 422)

    business_reference = database.collection("businesses").document(business_id)
    order_reference = business_reference.collection("orders").document(order_id)

    @firestore.transactional
    def apply(current_transaction):
        order_snapshot = order_reference.get(transaction=current_transaction)

        if not order_snapshot.exists:
            raise ApiError("order_not_found", "Order not found.", 404)

        order = order_snapshot.to_dict()

        # Re-checked inside the transaction: the seller may have confirmed the
        # order in the seconds between the customer being offered this and
        # choosing it.
        if not order_accepts_more_items(order):
            raise ApiError(
                "order_not_editable",
                "That order is already being prepared, so it can no longer be "
                "changed.",
                409,
            )

        courier_snapshot = business_reference.collection("couriers").document(
            order.get("courierId", ""),
        ).get(transaction=current_transaction)

        if not courier_snapshot.exists:
            raise ApiError("courier_not_found", "Courier not found.", 404)

        variant_snapshots = {}
        product_snapshots = {}

        for item in items:
            variant_reference = business_reference.collection(
                "productVariants",
            ).document(item["variantId"])
            variant_snapshot = variant_reference.get(transaction=current_transaction)

            if not variant_snapshot.exists:
                raise ApiError(
                    "variant_not_found",
                    "A selected item no longer exists.",
                    404,
                )

            variant = variant_snapshot.to_dict()

            if variant.get("stockAvailable", 0) < item["quantity"]:
                raise ApiError(
                    "insufficient_stock",
                    "Only {0} unit(s) are available for SKU {1}.".format(
                        variant.get("stockAvailable", 0),
                        variant.get("sku"),
                    ),
                    409,
                )

            variant_snapshots[item["variantId"]] = variant_snapshot
            product_id = variant.get("productId")

            if product_id not in product_snapshots:
                product_snapshot = business_reference.collection("products").document(
                    product_id,
                ).get(transaction=current_transaction)

                if not product_snapshot.exists:
                    raise ApiError(
                        "inactive_product",
                        "A selected product is unavailable.",
                        409,
                    )

                product_snapshots[product_id] = product_snapshot

        timestamp = firestore.SERVER_TIMESTAMP
        existing_items = [dict(line) for line in (order.get("items") or [])]
        quantities_by_product = defaultdict(int)
        warranty_started_at = datetime.now(timezone.utc)

        for item in items:
            variant_snapshot = variant_snapshots[item["variantId"]]
            variant = variant_snapshot.to_dict()
            product = product_snapshots[variant["productId"]].to_dict()
            quantity = item["quantity"]
            unit_price_minor = variant.get("sellingPriceMinor", 0)
            media = product.get("media", [])
            existing_line = next(
                (
                    line
                    for line in existing_items
                    if line.get("variantId") == variant_snapshot.id
                ),
                None,
            )

            # Ordering the same item twice is one line of three, not two lines
            # the picker has to notice are the same product.
            if existing_line:
                existing_line["quantity"] += quantity
                existing_line["lineTotalMinor"] = (
                    existing_line["unitPriceMinor"] * existing_line["quantity"]
                )
            else:
                existing_items.append(
                    {
                        "productId": variant["productId"],
                        "variantId": variant_snapshot.id,
                        "name": product.get("name", "Product"),
                        "size": variant.get("size", ""),
                        "sku": variant.get("sku", ""),
                        "barcode": variant.get("barcode", ""),
                        "quantity": quantity,
                        "unitPriceMinor": unit_price_minor,
                        "unitCostMinor": variant.get("costPriceMinor", 0),
                        "unitWeightGrams": variant.get("weightGrams", 0),
                        "lineTotalMinor": unit_price_minor * quantity,
                        "mediaUrl": media[0].get("url", "") if media else "",
                        **warranty_snapshot(product, warranty_started_at),
                    },
                )

            quantities_by_product[variant["productId"]] += quantity
            available_before = variant.get("stockAvailable", 0)
            available_after = available_before - quantity
            current_transaction.update(
                variant_snapshot.reference,
                {
                    "stockReserved": variant.get("stockReserved", 0) + quantity,
                    "stockAvailable": available_after,
                    "stockStatus": stock_status(
                        available_after,
                        product.get("lowStockThreshold", 0),
                    ),
                    "updatedAt": timestamp,
                },
            )
            current_transaction.set(
                business_reference.collection("inventoryTransactions").document(),
                {
                    "productId": variant["productId"],
                    "variantId": variant_snapshot.id,
                    "type": "reserve",
                    "quantity": quantity,
                    "stockBefore": available_before,
                    "stockAfter": available_after,
                    "orderId": order_reference.id,
                    "reference": order.get("orderNumber", ""),
                    "reason": "Items added to existing order",
                    "performedBy": uid,
                    "createdAt": timestamp,
                },
            )

        for product_id, reserved_quantity in quantities_by_product.items():
            product_snapshot = product_snapshots[product_id]
            product = product_snapshot.to_dict()
            added_by_variant = defaultdict(int)

            for item in items:
                variant = variant_snapshots[item["variantId"]].to_dict()

                if variant.get("productId") == product_id:
                    added_by_variant[item["variantId"]] += item["quantity"]

            summaries = []

            for summary in product.get("variantSummaries", []):
                quantity = added_by_variant.get(summary.get("id"), 0)

                if quantity:
                    available = summary.get("stockAvailable", 0) - quantity
                    summaries.append(
                        {
                            **summary,
                            "stockReserved": summary.get("stockReserved", 0) + quantity,
                            "stockAvailable": available,
                            "stockStatus": stock_status(
                                available,
                                product.get("lowStockThreshold", 0),
                            ),
                        },
                    )
                else:
                    summaries.append(summary)

            available_product_stock = (
                product.get("availableStock", 0) - reserved_quantity
            )
            current_transaction.update(
                product_snapshot.reference,
                {
                    "reservedStock": product.get("reservedStock", 0) + reserved_quantity,
                    "availableStock": available_product_stock,
                    "stockStatus": stock_status(
                        available_product_stock,
                        product.get("lowStockThreshold", 0),
                    ),
                    "variantSummaries": summaries,
                    "updatedAt": timestamp,
                },
            )

        subtotal_minor = sum(line["lineTotalMinor"] for line in existing_items)
        total_weight_grams = sum(
            line.get("unitWeightGrams", 0) * line["quantity"]
            for line in existing_items
        )
        # Delivery is charged on the whole parcel. Keeping the old fee would
        # undercharge the seller on the extra weight.
        delivery_fee_minor = calculate_delivery_fee(
            courier_snapshot.to_dict(),
            total_weight_grams,
            order.get("district", ""),
        )
        discount_minor = order.get("discountTotalMinor", 0)
        total_minor = (
            subtotal_minor
            - discount_minor
            + delivery_fee_minor
            + order.get("taxTotalMinor", 0)
        )
        paid_amount_minor = order.get("paidAmountMinor", 0)
        added_quantity = sum(item["quantity"] for item in items)
        current_transaction.update(
            order_reference,
            {
                "items": existing_items,
                "itemCount": sum(line["quantity"] for line in existing_items),
                "subtotalMinor": subtotal_minor,
                "deliveryFeeMinor": delivery_fee_minor,
                "totalAmountMinor": total_minor,
                "balanceAmountMinor": total_minor - paid_amount_minor,
                # A deposit that covered the old total may not cover the new
                # one, so the status is recomputed rather than carried over.
                "paymentStatus": (
                    "paid" if paid_amount_minor >= total_minor
                    else "partially-paid" if paid_amount_minor > 0
                    else "unpaid"
                ),
                "totalWeightGrams": total_weight_grams,
                "updatedAt": timestamp,
                "updatedBy": uid,
            },
        )
        current_transaction.set(
            order_reference.collection("events").document(),
            {
                "status": order.get("fulfilmentStatus", "needs-confirmation"),
                "message": (
                    "Customer added {0} item(s) to this order before "
                    "confirmation.".format(added_quantity)
                ),
                "performedBy": uid,
                "createdAt": timestamp,
            },
        )

    apply(database.transaction())
    return get_order(database, business_id, order_id)


def record_order_payment(database, business_id, order_id, uid, payload):
    """Record money the seller has actually received against an order.

    The seller enters what landed in their account and attaches the receipt.
    Anything still outstanding becomes the cash-on-delivery amount, so a half
    transfer and a full transfer are the same operation with different numbers
    rather than two code paths that can disagree.
    """
    try:
        paid_amount_minor = int(payload.get("paidAmountMinor") or 0)
    except (TypeError, ValueError) as error:
        raise ApiError(
            "validation_error",
            "Paid amount must be a number.",
            422,
        ) from error

    if paid_amount_minor <= 0:
        raise ApiError(
            "validation_error",
            "Enter the amount you received.",
            422,
        )

    receipt_url = optional_text(payload.get("receiptUrl"), 2000)
    note = optional_text(payload.get("note"), 500)
    order_reference = (
        database.collection("businesses").document(business_id)
        .collection("orders").document(order_id)
    )
    snapshot = order_reference.get()

    if not snapshot.exists:
        raise ApiError("order_not_found", "Order not found.", 404)

    order = snapshot.to_dict()
    total_minor = order.get("totalAmountMinor", 0)

    # Overpayment is a data-entry slip, and silently accepting it would show a
    # negative balance to collect on the courier's sheet.
    if paid_amount_minor > total_minor:
        raise ApiError(
            "invalid_payment",
            "The amount received cannot be more than the order total.",
            422,
        )

    balance_minor = total_minor - paid_amount_minor
    payment_status = "paid" if balance_minor == 0 else "partially-paid"
    receipts = list(order.get("paymentReceipts") or [])

    if receipt_url:
        receipts.append(
            {
                "url": receipt_url,
                "amountMinor": paid_amount_minor,
                "recordedBy": uid,
                "recordedAt": datetime.now(timezone.utc),
            },
        )

    order_reference.update(
        {
            "paidAmountMinor": paid_amount_minor,
            "balanceAmountMinor": balance_minor,
            "paymentStatus": payment_status,
            # Settled either way: the rest is collected on delivery, so nothing
            # is still waiting on a transfer.
            "paymentPending": False,
            "paymentReceipts": receipts,
            "paymentVerifiedBy": uid,
            "paymentVerifiedAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    order_reference.collection("events").document().set(
        {
            "status": order.get("fulfilmentStatus", "needs-confirmation"),
            "message": (
                f"Payment of {paid_amount_minor / 100:,.2f} recorded."
                + (
                    f" Balance {balance_minor / 100:,.2f} to collect on delivery."
                    if balance_minor
                    else " Order fully paid."
                )
                + (f" {note}" if note else "")
            ),
            "performedBy": uid,
            "createdAt": firestore.SERVER_TIMESTAMP,
        },
    )
    return get_order(database, business_id, order_id)
