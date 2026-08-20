from io import BytesIO

from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.order_service import get_order, list_orders
from app.services.text import optional_text, required_text


FRAUD_REASONS = {
    "fake-details",
    "invalid-address",
    "no-contact",
    "refused-order",
    "repeat-return",
    "other",
}
COURIER_ISSUE_TYPES = {
    "branch-problem",
    "delayed",
    "damaged",
    "lost",
    "other",
}
WAYBILL_ALLOWED_STATUSES = {"confirmed", "packed", "shipped", "delivered"}


def validate_report_payload(payload, allowed_values, field_label):
    try:
        report_type = required_text(payload.get("type"), field_label, 60).lower()
        note = optional_text(payload.get("note"), 1000)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if report_type not in allowed_values:
        raise ApiError(
            "validation_error",
            f"Choose a valid {field_label.lower()}.",
            422,
            {"allowedValues": sorted(allowed_values)},
        )

    return report_type, note


def create_fraud_report(database, business_id, order_id, uid, payload):
    reason, note = validate_report_payload(payload, FRAUD_REASONS, "Fraud reason")
    business_reference = database.collection("businesses").document(business_id)
    order_reference = business_reference.collection("orders").document(order_id)
    report_reference = business_reference.collection("fraudReports").document(order_id)
    notification_reference = business_reference.collection("notifications").document()
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        order_snapshot = order_reference.get(transaction=current_transaction)
        report_snapshot = report_reference.get(transaction=current_transaction)

        if not order_snapshot.exists:
            raise ApiError("order_not_found", "Order not found.", 404)
        if report_snapshot.exists:
            raise ApiError(
                "fraud_report_exists",
                "This order has already been reported.",
                409,
            )

        order = order_snapshot.to_dict()
        customer_reference = business_reference.collection("customers").document(
            order.get("customerId", ""),
        )
        customer_snapshot = customer_reference.get(transaction=current_transaction)
        timestamp = firestore.SERVER_TIMESTAMP
        report = {
            "orderId": order_id,
            "orderNumber": order.get("orderNumber", ""),
            "customerId": order.get("customerId", ""),
            "customerSnapshot": order.get("customerSnapshot", {}),
            "reason": reason,
            "note": note,
            "status": "active",
            "reportedBy": uid,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        current_transaction.set(report_reference, report)
        current_transaction.update(
            order_reference,
            {
                "fraudReport": {
                    "reason": reason,
                    "status": "active",
                    "reportedBy": uid,
                },
                "updatedAt": timestamp,
            },
        )

        if customer_snapshot.exists:
            customer = customer_snapshot.to_dict()
            current_transaction.update(
                customer_reference,
                {
                    "fraudReportCount": customer.get("fraudReportCount", 0) + 1,
                    "riskLevel": "high",
                    "tags": firestore.ArrayUnion(["fraud-reported"]),
                    "updatedAt": timestamp,
                },
            )

        current_transaction.set(
            notification_reference,
            {
                "type": "fraud-report",
                "title": f"Fraud report for {order.get('orderNumber', 'order')}",
                "message": f"Reason: {reason.replace('-', ' ')}.",
                "orderId": order_id,
                "orderNumber": order.get("orderNumber", ""),
                "isRead": False,
                "createdAt": timestamp,
            },
        )

    create_in_transaction(transaction)
    return serialize_snapshot(report_reference.get())


def record_courier_issue(database, business_id, order_id, uid, payload):
    issue_type, note = validate_report_payload(
        payload,
        COURIER_ISSUE_TYPES,
        "Courier issue type",
    )
    business_reference = database.collection("businesses").document(business_id)
    order_reference = business_reference.collection("orders").document(order_id)
    issue_reference = business_reference.collection("courierIssues").document()
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        order_snapshot = order_reference.get(transaction=current_transaction)

        if not order_snapshot.exists:
            raise ApiError("order_not_found", "Order not found.", 404)

        order = order_snapshot.to_dict()
        courier_id = order.get("courierId")

        if not courier_id:
            raise ApiError(
                "courier_not_assigned",
                "Assign a courier before reporting a courier issue.",
                409,
            )

        courier_reference = business_reference.collection("couriers").document(
            courier_id,
        )
        courier_snapshot = courier_reference.get(transaction=current_transaction)

        if not courier_snapshot.exists:
            raise ApiError("courier_not_found", "Courier not found.", 404)

        courier = courier_snapshot.to_dict()
        district = order.get("district", "unknown")
        district_counts = dict(courier.get("districtIssueCounts", {}))
        district_counts[district] = district_counts.get(district, 0) + 1
        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.set(
            issue_reference,
            {
                "orderId": order_id,
                "orderNumber": order.get("orderNumber", ""),
                "courierId": courier_id,
                "courierName": courier.get("name", ""),
                "district": district,
                "type": issue_type,
                "note": note,
                "reportedBy": uid,
                "createdAt": timestamp,
            },
        )
        current_transaction.update(
            courier_reference,
            {
                "districtIssueCounts": district_counts,
                "issueCount": courier.get("issueCount", 0) + 1,
                "updatedAt": timestamp,
            },
        )
        current_transaction.update(
            order_reference,
            {
                "courierIssueCount": order.get("courierIssueCount", 0) + 1,
                "updatedAt": timestamp,
            },
        )

    create_in_transaction(transaction)
    return serialize_snapshot(issue_reference.get())


def generate_waybill(database, business_id, order_id, uid):
    business_reference = database.collection("businesses").document(business_id)
    order_reference = business_reference.collection("orders").document(order_id)
    waybill_reference = business_reference.collection("waybills").document(order_id)
    transaction = database.transaction()

    @google_firestore.transactional
    def generate_in_transaction(current_transaction):
        business_snapshot = business_reference.get(transaction=current_transaction)
        order_snapshot = order_reference.get(transaction=current_transaction)

        if not order_snapshot.exists:
            raise ApiError("order_not_found", "Order not found.", 404)

        order = order_snapshot.to_dict()

        if order.get("waybillNumber"):
            return
        if order.get("fulfilmentStatus") not in WAYBILL_ALLOWED_STATUSES:
            raise ApiError(
                "order_not_ready_for_waybill",
                "Confirm the order before generating a waybill.",
                409,
            )

        business = business_snapshot.to_dict() if business_snapshot.exists else {}
        courier_reference = business_reference.collection("couriers").document(order.get("courierId", ""))
        courier_snapshot = courier_reference.get(transaction=current_transaction) if order.get("courierId") else None
        courier = courier_snapshot.to_dict() if courier_snapshot and courier_snapshot.exists else {}
        sequence = courier.get("nextWaybillSequence", courier.get("waybillStart", business.get("nextWaybillSequence", 1)))
        waybill_end = courier.get("waybillEnd", 999999)
        if sequence > waybill_end:
            raise ApiError("waybill_range_exhausted", "This courier's waybill range is exhausted.", 409)
        waybill_number = f"{courier.get('waybillPrefix', 'VWB')}-{sequence:08d}"
        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.set(
            waybill_reference,
            {
                "waybillNumber": waybill_number,
                "orderId": order_id,
                "orderNumber": order.get("orderNumber", ""),
                "courierId": order.get("courierId", ""),
                "courierSnapshot": order.get("courierSnapshot", {}),
                "customerSnapshot": order.get("customerSnapshot", {}),
                "deliveryAddress": order.get("deliveryAddress", {}),
                "totalWeightGrams": order.get("totalWeightGrams", 0),
                "generatedBy": uid,
                "createdAt": timestamp,
            },
        )
        current_transaction.update(
            order_reference,
            {"waybillNumber": waybill_number, "updatedAt": timestamp},
        )
        current_transaction.update(
            business_reference,
            {"nextWaybillSequence": sequence + 1, "updatedAt": timestamp},
        )
        if courier_snapshot and courier_snapshot.exists:
            current_transaction.update(
                courier_reference,
                {"nextWaybillSequence": sequence + 1, "updatedAt": timestamp},
            )

    generate_in_transaction(transaction)
    return get_order(database, business_id, order_id)


def format_address(address):
    return ", ".join(
        str(address.get(field, "")).strip()
        for field in ("line1", "line2", "city", "district", "postalCode", "country")
        if str(address.get(field, "")).strip()
    )


def build_orders_workbook(orders):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Orders"
    headers = [
        "Order No",
        "Created At",
        "Customer",
        "Phone",
        "Delivery Address",
        "Items",
        "Quantity",
        "Subtotal (LKR)",
        "Discount (LKR)",
        "Delivery Fee (LKR)",
        "Total (LKR)",
        "Courier",
        "Waybill No",
        "Payment",
        "Status",
    ]
    sheet.append(headers)
    header_fill = PatternFill("solid", fgColor="0B3B6E")

    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = header_fill

    for order in orders:
        items = order.get("items", [])
        sheet.append(
            [
                order.get("orderNumber", ""),
                str(order.get("createdAt", "")),
                order.get("customerSnapshot", {}).get("name", ""),
                order.get("customerSnapshot", {}).get("normalizedPhone", ""),
                format_address(order.get("deliveryAddress", {})),
                "; ".join(
                    f"{item.get('name', '')} {item.get('size', '')}".strip()
                    for item in items
                ),
                order.get("itemCount", 0),
                order.get("subtotalMinor", 0) / 100,
                order.get("discountTotalMinor", 0) / 100,
                order.get("deliveryFeeMinor", 0) / 100,
                order.get("totalAmountMinor", 0) / 100,
                order.get("courierSnapshot", {}).get("name", ""),
                order.get("waybillNumber", ""),
                order.get("paymentStatus", ""),
                order.get("fulfilmentStatus", ""),
            ],
        )

    for column in sheet.columns:
        maximum_length = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(
            maximum_length + 2,
            45,
        )

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


def export_orders(database, business_id, status=None, search=None):
    return build_orders_workbook(
        list_orders(database, business_id, status=status, search=search),
    )


def list_notifications(database, business_id, unread_only=False):
    snapshots = (
        database.collection("businesses")
        .document(business_id)
        .collection("notifications")
        .order_by("createdAt", direction="DESCENDING")
        .limit(50)
        .stream()
    )
    notifications = [serialize_snapshot(snapshot) for snapshot in snapshots]

    if unread_only:
        notifications = [item for item in notifications if not item.get("isRead")]

    return notifications


def mark_notification_read(database, business_id, notification_id):
    reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("notifications")
        .document(notification_id)
    )

    if not reference.get().exists:
        raise ApiError("notification_not_found", "Notification not found.", 404)

    reference.update({"isRead": True, "readAt": firestore.SERVER_TIMESTAMP})
    return serialize_snapshot(reference.get())
