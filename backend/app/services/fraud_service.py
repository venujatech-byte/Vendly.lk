import hashlib

from firebase_admin import firestore

from app.core.serialization import serialize_value
from app.services.customer_service import normalize_sri_lankan_phone


def fraud_phone_hash(phone_number):
    """Return a non-reversible registry key for a normalized phone number."""
    normalized_phone = normalize_sri_lankan_phone(phone_number)
    return hashlib.sha256(normalized_phone.encode("utf-8")).hexdigest()


def global_fraud_reference(database, phone_number):
    return database.collection("globalFraudRegistry").document(
        fraud_phone_hash(phone_number),
    )


def fraud_score(registry_data):
    report_count = int(registry_data.get("reportCount") or 0)
    returned_count = int(registry_data.get("returnedOrderCount") or 0)
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
        "reportCount": int(data.get("reportCount") or 0),
        "returnedOrderCount": int(data.get("returnedOrderCount") or 0),
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
        risk_level = (
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
