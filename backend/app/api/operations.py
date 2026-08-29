from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request, send_file

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.operations_service import (
    create_fraud_report,
    export_orders,
    generate_waybill,
    list_notifications,
    mark_notification_read,
    record_courier_issue,
)
from app.services.courier_service import get_courier


operations_blueprint = Blueprint("operations", __name__, url_prefix="/api/v1")


@operations_blueprint.post(
    "/businesses/<business_id>/orders/<order_id>/fraud-report",
)
@require_firebase_user
@require_business_member(permission="orders:manage")
def add_fraud_report(business_id, order_id):
    report = create_fraud_report(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"fraudReport": report}), 201


@operations_blueprint.post(
    "/businesses/<business_id>/orders/<order_id>/courier-issues",
)
@require_firebase_user
@require_business_member(permission="orders:manage")
def add_courier_issue(business_id, order_id):
    issue = record_courier_issue(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"courierIssue": issue}), 201


@operations_blueprint.post(
    "/businesses/<business_id>/orders/<order_id>/waybill",
)
@require_firebase_user
@require_business_member(permission="orders:manage")
def create_waybill(business_id, order_id):
    order = generate_waybill(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
    )
    return jsonify({"order": order})


@operations_blueprint.get("/businesses/<business_id>/orders-export.xlsx")
@require_firebase_user
@require_business_member(permission="orders:read")
def download_orders(business_id):
    courier_id = request.args.get("courierId")
    workbook = export_orders(
        get_firestore_client(),
        business_id,
        status=request.args.get("status"),
        search=request.args.get("search"),
        date_from=request.args.get("dateFrom"),
        date_to=request.args.get("dateTo"),
        courier_id=courier_id,
        order_ids=request.args.getlist("orderId"),
    )
    courier = get_courier(get_firestore_client(), business_id, courier_id)
    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return send_file(
        workbook,
        as_attachment=True,
        download_name=f"{courier.get('code', 'courier')}-orders-{date_stamp}.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )


@operations_blueprint.get("/businesses/<business_id>/notifications")
@require_firebase_user
@require_business_member()
def get_notifications(business_id):
    notifications = list_notifications(
        get_firestore_client(),
        business_id,
        unread_only=request.args.get("unread") == "true",
    )
    return jsonify({"notifications": notifications})


@operations_blueprint.patch(
    "/businesses/<business_id>/notifications/<notification_id>/read",
)
@require_firebase_user
@require_business_member()
def read_notification(business_id, notification_id):
    notification = mark_notification_read(
        get_firestore_client(),
        business_id,
        notification_id,
    )
    return jsonify({"notification": notification})
