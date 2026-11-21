import re

from google.cloud import firestore as google_firestore

from app.core.errors import ApiError
from app.services.numbers import money_to_minor_units
from app.services.order_service import can_report_chat_transfer, record_order_payment


def parse_chat_transfer_amount(value):
    """Read one LKR amount without interpreting prose or rounding extra decimals."""
    match = re.fullmatch(
        r"(?:LKR\s*|Rs\.?\s*)?([0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(\.[0-9]{1,2})?",
        str(value or "").strip(),
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("Enter the amount you transferred in LKR, for example 2,500.00.")
    return money_to_minor_units(
        match[1].replace(",", "") + (match[2] or ""), "Transfer amount", allow_zero=False,
    )


def stage_chat_receipt(database, session_reference, business_id, order_id, asset):
    order_reference = database.collection("businesses").document(business_id).collection("orders").document(order_id)

    @google_firestore.transactional
    def stage(transaction):
        # Hold the receipt against the order displayed in this conversation.
        session = session_reference.get(transaction=transaction).to_dict() or {}
        if session.get("orderId") != order_id or session.get("state") != "completed":
            return None
        if (session.get("paymentReceiptDraft") or {}).get("orderId") == order_id:
            raise ApiError("receipt_amount_pending", "Enter the amount for the previous receipt or type 'skip' first.", 409)
        order = order_reference.get(transaction=transaction).to_dict() or {}
        if not can_report_chat_transfer(order):
            return None

        draft = {"orderId": order_id, "orderNumber": order.get("orderNumber", ""), "receipt": asset}
        transaction.update(session_reference, {"paymentReceiptDraft": draft})
        return draft

    return stage(database.transaction())


def finish_chat_receipt(database, session_reference, draft, amount_minor):
    receipt = draft["receipt"]
    report_reference = session_reference.collection("paymentReports").document(receipt["id"])

    @google_firestore.transactional
    def finish(transaction):
        # Concurrent submissions must consume this receipt draft only once.
        session = session_reference.get(transaction=transaction).to_dict() or {}
        if (session.get("paymentReceiptDraft") != draft or session.get("orderId") != draft["orderId"]
                or session.get("state") != "completed"):
            raise ApiError("receipt_draft_changed", "This receipt has already been handled. Reload the chat.", 409)
        transaction.update(session_reference, {"paymentReceiptDraft": None})
        if amount_minor is None:
            return None
        report = {**draft, "reportedAmountMinor": amount_minor}
        transaction.set(report_reference, report)
        return {
            "id": report_reference.id, "orderNumber": draft["orderNumber"], "reportedAmountMinor": amount_minor,
        }

    return finish(database.transaction())


def chat_payment_report_reference(session_reference, report_id):
    if not re.fullmatch(r"[0-9a-f]{32}", report_id):
        raise ApiError("payment_report_not_found", "Payment report not found.", 404)
    return session_reference.collection("paymentReports").document(report_id)


def get_chat_payment_report(reference):
    report = reference.get().to_dict()
    if not report:
        raise ApiError("payment_report_not_found", "Payment report not found.", 404)
    return report


def verify_chat_payment_report(database, business_id, reference, uid, payload):
    report = get_chat_payment_report(reference)
    try:
        amount_minor = parse_chat_transfer_amount(payload.get("amount"))
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error
    return record_order_payment(
        database, business_id, report["orderId"], uid, {"paidAmountMinor": amount_minor},
        chat_report_reference=reference,
    )
