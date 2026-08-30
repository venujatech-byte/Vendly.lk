from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request, send_file

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.services.analytics_service import (
    get_business_analytics,
    get_business_ledger,
)
from app.services.cod_reconciliation_service import (
    get_cod_reconciliation,
    update_cod_settlement,
)
from app.services.spreadsheet_service import export_ledger_workbook


analytics_blueprint = Blueprint("analytics", __name__, url_prefix="/api/v1")


@analytics_blueprint.get("/businesses/<business_id>/analytics/overview")
@require_firebase_user
@require_business_member(permission="analytics:read")
def analytics_overview(business_id):
    return jsonify(
        {"analytics": get_business_analytics(get_firestore_client(), business_id)},
    )


@analytics_blueprint.get("/businesses/<business_id>/analytics/ledger")
@require_firebase_user
@require_business_member(permission="analytics:read")
def analytics_ledger(business_id):
    return jsonify(
        {"ledger": get_business_ledger(get_firestore_client(), business_id)},
    )


@analytics_blueprint.get("/businesses/<business_id>/analytics/cod-reconciliation")
@require_firebase_user
@require_business_member(permission="analytics:read")
def analytics_cod_reconciliation(business_id):
    return jsonify({
        "reconciliation": get_cod_reconciliation(get_firestore_client(), business_id),
    })


@analytics_blueprint.patch("/businesses/<business_id>/analytics/cod-reconciliation/<order_id>")
@require_firebase_user
@require_business_member(permission="orders:*")
def analytics_update_cod_reconciliation(business_id, order_id):
    return jsonify({
        "reconciliation": update_cod_settlement(
            get_firestore_client(),
            business_id,
            order_id,
            request.get_json(silent=True) or {},
            g.current_user["uid"],
        ),
    })


@analytics_blueprint.get("/businesses/<business_id>/analytics/ledger-export.xlsx")
@require_firebase_user
@require_business_member(permission="analytics:read")
def analytics_ledger_export(business_id):
    ledger = get_business_ledger(get_firestore_client(), business_id)
    search = request.args.get("search", "").strip().casefold()
    transaction_type = request.args.get("type", "").strip()
    date_from = request.args.get("dateFrom", "").strip()
    date_to = request.args.get("dateTo", "").strip()

    entries = []
    for entry in ledger.get("entries", []):
        entry_date = str(entry.get("createdAt", ""))[:10]
        searchable = " ".join(
            str(entry.get(field, ""))
            for field in (
                "reference",
                "customerName",
                "description",
                "label",
                "paymentMethod",
                "status",
            )
        ).casefold()
        if search and search not in searchable:
            continue
        if transaction_type and transaction_type != "all" and entry.get("transactionType") != transaction_type:
            continue
        if date_from and entry_date < date_from:
            continue
        if date_to and entry_date > date_to:
            continue
        entries.append(entry)

    workbook = export_ledger_workbook(entries)
    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return send_file(
        workbook,
        as_attachment=True,
        download_name=f"vendly-transaction-ledger-{date_stamp}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
