from app.services.search_service import search_records


def test_global_search_finds_sku_barcode_waybill_and_phone():
    results = search_records(
        [
            {
                "id": "o1",
                "orderNumber": "VD-000001",
                "waybillNumber": "VWB-1234",
                "customerSnapshot": {"name": "Kamal", "normalizedPhone": "94771234567"},
                "items": [],
            },
        ],
        [
            {
                "id": "p1",
                "name": "Smart Watch",
                "variantSummaries": [{"sku": "WATCH-BLK", "barcode": "890123"}],
            },
        ],
        [{"id": "c1", "name": "Kamal", "normalizedPhone": "94771234567"}],
        "890123",
    )
    assert results["products"][0]["id"] == "p1"

    results = search_records([], [], [{"id": "c1", "name": "Kamal"}], "kam")
    assert results["customers"][0]["name"] == "Kamal"


def test_global_search_waits_for_two_characters():
    assert search_records([], [], [], "a") == {
        "orders": [],
        "products": [],
        "customers": [],
    }
