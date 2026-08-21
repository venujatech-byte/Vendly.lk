import hashlib

from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.core.serialization import serialize_value
from app.services.customer_service import normalize_sri_lankan_phone
from app.services.text import optional_text


def fraud_phone_hash(phone_number):
    """Return a non-reversible registry key for a normalized phone number."""
    normalized_phone = normalize_sri_lankan_phone(phone_number)
    return hashlib.sha256(normalized_phone.encode("utf-8")).hexdigest()


def global_fraud_reference(database, phone_number):
    return database.collection("globalFraudRegistry").document(
        fraud_phone_hash(phone_number),
    )


def fraud_score(registry_data):
    report_count = max(0, int(registry_data.get("reportCount") or 0))
    returned_count = max(0, int(registry_data.get("returnedOrderCount") or 0))
    return min(100, report_count * 45 + returned_count * 20)


def fraud_risk(registry_data):
    score = fraud_score(registry_data)
    if score >= 60:
        return "high"
    if score >= 20:
        return "medium"
    return "low"


def global_fraud_summary(registry_data):
    data = registry_data or {}
    return {
        "reportCount": max(0, int(data.get("reportCount") or 0)),
        "returnedOrderCount": max(0, int(data.get("returnedOrderCount") or 0)),
        "score": fraud_score(data),
        "riskLevel": fraud_risk(data),
    }


def global_registry_increment(report_count=0, returned_count=0):
    """Build an atomic, privacy-safe update for the shared registry."""
    return {
        "reportCount": firestore.Increment(report_count),
        "returnedOrderCount": firestore.Increment(returned_count),
        "status": "active",
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }


def report_customer(database, business_id, customer_id, uid, payload):
    """Report a customer directly while keeping the shared registry anonymous."""
    business_reference = database.collection("businesses").document(business_id)
    customer_reference = business_reference.collection("customers").document(customer_id)
    report_reference = business_reference.collection("fraudReports").document(
        f"customer-{customer_id}",
    )
    transaction = database.transaction()

    try:
        reason = optional_text(payload.get("reason"), 80) or "seller-reported"
        note = optional_text(payload.get("note"), 1000)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    @google_firestore.transactional
    def report_in_transaction(current_transaction):
        customer_snapshot = customer_reference.get(transaction=current_transaction)
        report_snapshot = report_reference.get(transaction=current_transaction)

        if not customer_snapshot.exists:
            raise ApiError("customer_not_found", "Customer not found.", 404)
        if report_snapshot.exists:
            raise ApiError(
                "fraud_report_exists",
                "This customer has already been reported by your business.",
                409,
            )

        customer = customer_snapshot.to_dict()
        phone = customer.get("normalizedPhone", "")
        registry_reference = global_fraud_reference(database, phone) if phone else None
        timestamp = firestore.SERVER_TIMESTAMP
        report = {
            "customerId": customer_id,
            "customerSnapshot": {
                "name": customer.get("name", ""),
                "normalizedPhone": phone,
                "email": customer.get("email", ""),
            },
            "reason": reason,
            "note": note,
            "source": "customer-management",
            "status": "active",
            "reportedBy": uid,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        current_transaction.set(report_reference, report)
        if registry_reference:
            current_transaction.set(
                registry_reference,
                global_registry_increment(report_count=1),
                merge=True,
            )
        current_transaction.update(
            customer_reference,
            {
                "fraudReportCount": int(customer.get("fraudReportCount") or 0) + 1,
                "riskLevel": "high",
                "fraudListStatus": "active",
                "tags": firestore.ArrayUnion(["fraud-reported"]),
                "updatedAt": timestamp,
            },
        )

    report_in_transaction(transaction)
    return serialize_snapshot(report_reference.get())


def change_customer_fraud_risk(database, business_id, customer_id, payload):
    """Set the risk level used by this seller's fraud-management screen."""
    risk_level = str(payload.get("riskLevel") or "").strip().lower()
    if risk_level not in {"low", "medium", "high"}:
        raise ApiError(
            "validation_error",
            "Risk level must be low, medium or high.",
            422,
        )

    customer_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("customers")
        .document(customer_id)
    )
    if not customer_reference.get().exists:
        raise ApiError("customer_not_found", "Customer not found.", 404)

    customer_reference.update(
        {
            "manualFraudRiskLevel": risk_level,
            "riskLevel": risk_level,
            "fraudListStatus": "active",
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    return serialize_snapshot(customer_reference.get())


def remove_customer_from_fraud_list(database, business_id, customer_id):
    """Remove this seller's reports without deleting shared evidence from others."""
    business_reference = database.collection("businesses").document(business_id)
    customer_reference = business_reference.collection("customers").document(customer_id)
    customer_snapshot = customer_reference.get()
    if not customer_snapshot.exists:
        raise ApiError("customer_not_found", "Customer not found.", 404)

    reports = list(
        business_reference.collection("fraudReports")
        .where(filter=FieldFilter("customerId", "==", customer_id))
        .stream()
    )
    customer = customer_snapshot.to_dict()
    phone = customer.get("normalizedPhone", "")
    batch = database.batch()
    for report in reports:
        batch.delete(report.reference)

    batch.update(
        customer_reference,
        {
            "fraudReportCount": 0,
            "fraudListStatus": "removed",
            "manualFraudRiskLevel": firestore.DELETE_FIELD,
            "tags": firestore.ArrayRemove(["fraud-reported"]),
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    if phone and reports:
        batch.set(
            global_fraud_reference(database, phone),
            global_registry_increment(report_count=-len(reports)),
            merge=True,
        )
    batch.commit()
    return {"customerId": customer_id, "removed": True}


def list_seller_fraud_customers(database, business_id):
    """Expose only customers and reports owned by the requested business."""
    business_reference = database.collection("businesses").document(business_id)
    customers = {
        snapshot.id: {"id": snapshot.id, **snapshot.to_dict()}
        for snapshot in business_reference.collection("customers").stream()
    }
    reports_by_customer = {}
    for snapshot in business_reference.collection("fraudReports").stream():
        report = {"id": snapshot.id, **snapshot.to_dict()}
        customer_id = report.get("customerId")
        if customer_id:
            reports_by_customer.setdefault(customer_id, []).append(report)

    rows = []
    for customer_id, customer in customers.items():
        if customer.get("fraudListStatus") == "removed":
            continue
        reports = reports_by_customer.get(customer_id, [])
        returned_count = int(customer.get("returnedOrderCount") or 0)
        global_warning = customer.get("globalFraudWarning") or {}
        if not reports and returned_count == 0 and not global_warning.get("matched"):
            continue

        total_orders = int(
            customer.get("totalOrderCount")
            or customer.get("completedOrderCount")
            or returned_count
        )
        local_report_count = len(reports)
        score = max(
            int(customer.get("fraudScore") or 0),
            min(100, local_report_count * 45 + returned_count * 20),
            int(global_warning.get("score") or 0),
        )
        risk_level = customer.get("manualFraudRiskLevel") or (
            "high" if score >= 60 else "medium" if score >= 20 else "low"
        )
        latest_report = max(
            reports,
            key=lambda item: str(item.get("createdAt") or ""),
            default={},
        )
        rows.append(
            {
                **customer,
                "id": customer_id,
                "reports": reports,
                "fraudReportCount": local_report_count,
                "returnedOrderCount": returned_count,
                "totalOrderCount": total_orders,
                "returnRate": round(returned_count / total_orders * 100)
                if total_orders
                else 0,
                "fraudScore": score,
                "riskLevel": risk_level,
                "lastReturnedOrderDate": customer.get("lastReturnedOrderDate"),
                "returnReason": latest_report.get("reason")
                or customer.get("lastReturnReason")
                or "Unspecified",
                "globalMatch": bool(global_warning.get("matched")),
            }
        )

    return serialize_value(
        sorted(rows, key=lambda item: item.get("fraudScore", 0), reverse=True),
    )
