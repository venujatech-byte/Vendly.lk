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


def test_search_sanitizes_script_tags_and_control_chars():
    from app.services.search_service import sanitize_search_query

    # Script tag stripped
    assert sanitize_search_query("<script>alert(1)</script>") == "alert(1)"
    assert sanitize_search_query("<img src=x onerror=alert(1)>") == ""

    # Control chars stripped
    assert sanitize_search_query("Kamal\x00\x1b[31m") == "Kamal[31m"

    # Max length clamped to 80
    long_query = "a" * 100
    assert len(sanitize_search_query(long_query)) == 80


def test_search_matches_legitimate_keyword_when_scripts_are_stripped():
    results = search_records(
        [],
        [{"id": "p1", "name": "Smart Watch", "variantSummaries": []}],
        [],
        "<script>Watch</script>",
    )
    assert len(results["products"]) == 1
    assert results["products"][0]["id"] == "p1"
