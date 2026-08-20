import pytest
from openpyxl import load_workbook

from app.core.errors import ApiError
from app.services.operations_service import (
    build_orders_workbook,
    validate_report_payload,
)


def test_report_payload_rejects_unknown_type():
    with pytest.raises(ApiError) as error:
        validate_report_payload(
            {"type": "unknown"},
            {"delayed", "lost"},
            "Courier issue type",
        )

    assert error.value.status_code == 422


def test_order_export_creates_real_excel_workbook():
    stream = build_orders_workbook(
        [
            {
                "orderNumber": "VD-000001",
                "customerSnapshot": {
                    "name": "Kamal",
                    "normalizedPhone": "94771234567",
                },
                "deliveryAddress": {"line1": "10 Main Road", "district": "Colombo"},
                "items": [{"name": "Watch", "size": "", "quantity": 1}],
                "itemCount": 1,
                "subtotalMinor": 200000,
                "deliveryFeeMinor": 45000,
                "totalAmountMinor": 245000,
                "courierSnapshot": {"name": "Courier One"},
                "fulfilmentStatus": "confirmed",
            },
        ],
    )
    workbook = load_workbook(stream)
    sheet = workbook["Orders"]

    assert sheet["A2"].value == "VD-000001"
    assert sheet["C2"].value == "Kamal"
    assert sheet["K2"].value == 2450
