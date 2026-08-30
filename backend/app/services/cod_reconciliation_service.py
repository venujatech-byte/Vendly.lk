from datetime import datetime, timedelta, timezone

from firebase_admin import firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.analytics_service import as_datetime


def _minor(value):
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _cod_balance(order):
    total = _minor(order.get("totalAmountMinor"))
    paid = _minor(order.get("paidAmountMinor"))
    saved_balance = order.get("balanceAmountMinor")
    return _minor(saved_balance) if saved_balance is not None else max(total - paid, 0)


def build_cod_reconciliation(orders, settlements=None, now=None, overdue_days=7):
    """Combine delivered COD orders with their independently saved settlements."""
    now = now or datetime.now(timezone.utc)
    settlements = settlements or []
    settlements_by_order = {
        item.get("orderId") or item.get("id"): item for item in settlements
    }
    rows = []

    for order in orders:
        balance = _cod_balance(order)
        if (
            order.get("fulfilmentStatus") != "delivered"
            or order.get("paymentMethod") not in {"cod", "deposit"}
            or balance <= 0
        ):
            continue

        order_id = order.get("id", "")
        settlement = settlements_by_order.get(order_id, {})
        collected = (
            _minor(settlement.get("amountCollectedMinor"))
            if "amountCollectedMinor" in settlement
            else balance
        )
        courier_charge = _minor(settlement.get("courierChargeMinor"))
        received = _minor(settlement.get("receivedSettlementMinor"))
        expected = max(collected - courier_charge, 0)
        delivered_at = (
            as_datetime(order.get("deliveredAt"))
            or as_datetime(order.get("updatedAt"))
            or as_datetime(order.get("createdAt"))
        )
        is_disputed = bool(settlement.get("isDisputed"))
        if is_disputed:
            status = "disputed"
        elif not settlement:
            status = "unreconciled"
        elif received == 0:
            status = "pending"
        elif received < expected:
            status = "partial"
        else:
            status = "reconciled"
        overdue = bool(
            delivered_at
            and delivered_at < now - timedelta(days=overdue_days)
            and status not in {"reconciled", "disputed"}
        )
        customer = order.get("customerSnapshot") or {}
        courier = order.get("courierSnapshot") or {}
        rows.append({
            "orderId": order_id,
            "orderNumber": order.get("orderNumber") or order_id,
            "customerName": customer.get("name") or order.get("customerName") or "Customer",
            "courierId": order.get("courierId") or courier.get("id") or "",
            "courierName": courier.get("name") or order.get("courierName") or "Unassigned",
            "deliveredAt": delivered_at.isoformat() if delivered_at else None,
            "expectedCollectionMinor": balance,
            "amountCollectedMinor": collected,
            "courierChargeMinor": courier_charge,
            "expectedSettlementMinor": expected,
            "receivedSettlementMinor": received,
            "varianceMinor": received - expected,
            "settlementDate": settlement.get("settlementDate"),
            "settlementReference": settlement.get("settlementReference", ""),
            "note": settlement.get("note", ""),
            "isDisputed": is_disputed,
            "status": status,
            "isOverdue": overdue,
        })

    rows.sort(key=lambda item: (item["isOverdue"], item["deliveredAt"] or ""), reverse=True)
    return {
        "summary": {
            "orderCount": len(rows),
            "expectedCollectionMinor": sum(item["expectedCollectionMinor"] for item in rows),
            "courierChargesMinor": sum(item["courierChargeMinor"] for item in rows),
            "expectedSettlementMinor": sum(item["expectedSettlementMinor"] for item in rows),
            "receivedSettlementMinor": sum(item["receivedSettlementMinor"] for item in rows),
            "varianceMinor": sum(item["varianceMinor"] for item in rows),
            "unreconciledCount": sum(item["status"] == "unreconciled" for item in rows),
            "overdueCount": sum(item["isOverdue"] for item in rows),
        },
        "entries": rows,
    }


def get_cod_reconciliation(database, business_id):
    reference = database.collection("businesses").document(business_id)
    orders = [serialize_snapshot(item) for item in reference.collection("orders").limit(2000).stream()]
    settlements = [serialize_snapshot(item) for item in reference.collection("codSettlements").limit(2000).stream()]
    return build_cod_reconciliation(orders, settlements)


def update_cod_settlement(database, business_id, order_id, payload, user_id):
    reference = database.collection("businesses").document(business_id)
    order_snapshot = reference.collection("orders").document(order_id).get()
    if not order_snapshot.exists:
        raise ApiError("order_not_found", "Order not found.", 404)
    order = {"id": order_snapshot.id, **order_snapshot.to_dict()}
    if order.get("fulfilmentStatus") != "delivered" or _cod_balance(order) <= 0:
        raise ApiError("invalid_cod_settlement", "Only a delivered order with a COD balance can be reconciled.", 422)

    changes = {}
    for field in ("amountCollectedMinor", "courierChargeMinor", "receivedSettlementMinor"):
        if field in payload:
            try:
                value = int(payload[field])
            except (TypeError, ValueError) as error:
                raise ApiError("validation_error", "Enter valid settlement amounts.", 422) from error
            if value < 0:
                raise ApiError("validation_error", "Settlement amounts cannot be negative.", 422)
            changes[field] = value
    for field, limit in (("settlementDate", 20), ("settlementReference", 120), ("note", 500)):
        if field in payload:
            changes[field] = str(payload[field] or "").strip()[:limit]
    if "isDisputed" in payload:
        changes["isDisputed"] = bool(payload["isDisputed"])
    changes.update({
        "orderId": order_id,
        "updatedAt": firestore.SERVER_TIMESTAMP,
        "updatedBy": user_id,
    })
    settlement_reference = reference.collection("codSettlements").document(order_id)
    if not settlement_reference.get().exists:
        changes["createdAt"] = firestore.SERVER_TIMESTAMP
    settlement_reference.set(changes, merge=True)
    return get_cod_reconciliation(database, business_id)
