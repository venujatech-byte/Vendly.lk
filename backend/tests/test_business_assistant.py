from app.services.business_assistant_service import (
    clean_product_query,
    deterministic_intent,
    process_read_intent,
)


def test_assistant_recognizes_read_only_dashboard_commands():
    assert deterministic_intent("Show today's summary")["intent"] == "business_summary"
    assert deterministic_intent("Show low stock products")["intent"] == "low_stock"
    assert deterministic_intent("Find order VD-000024") == {
        "intent": "search_order",
        "orderQuery": "VD-000024",
    }
    assert deterministic_intent("Open the inventory page") == {
        "intent": "navigate",
        "page": "inventory",
    }


def test_assistant_prepares_but_does_not_execute_status_command():
    intent = deterministic_intent("Mark order VD-000024 as packed")
    assert intent["intent"] == "update_order_status"
    assert intent["orderQuery"] == "VD-000024"
    assert intent["status"] == "packed"


def test_assistant_understands_signed_stock_adjustment():
    increase = deterministic_intent("Increase stock of Lenovo GM2 by 10")
    decrease = deterministic_intent("Reduce stock of Lenovo GM2 by 3")

    assert increase["intent"] == "adjust_stock"
    assert increase["quantityChange"] == 10
    assert decrease["quantityChange"] == -3
    assert clean_product_query("Increase stock of Lenovo GM2 by 10") == "lenovo gm2"


def test_assistant_recognizes_exports_and_existing_dashboard_forms():
    assert deterministic_intent("Export all orders")["intent"] == "export_orders"
    assert deterministic_intent("Export inventory items")["intent"] == "export_inventory"
    assert deterministic_intent("Add a new order")["intent"] == "open_add_order"
    assert deterministic_intent("Record a physical shop sale")["intent"] == "open_shop_sale"
    assert deterministic_intent("Add a new product")["intent"] == "open_add_product"
    assert deterministic_intent("Add a courier")["intent"] == "open_add_courier"
    assert deterministic_intent("Export customers")["intent"] == "export_customers"


def test_assistant_opens_online_orders_instead_of_the_add_order_form():
    assert deterministic_intent("Show me online orders") == {
        "intent": "order_view",
        "orderQuery": "",
        "status": "",
    }
    assert deterministic_intent("Add an online order")["intent"] == "open_add_order"


def test_assistant_does_not_use_conversational_me_as_a_filter_value():
    orders = deterministic_intent("Show me orders")
    assert orders["intent"] == "order_view"
    assert orders["orderQuery"] == ""

    inventory = deterministic_intent("Show me inventory")
    assert inventory["intent"] == "inventory_view"
    assert inventory["productQuery"] == ""


def test_assistant_prints_a_specific_shop_sale_receipt_from_short_sale_number():
    intent = deterministic_intent("Print receipt on sales no 2")
    assert intent["intent"] == "print_receipts"
    assert intent["saleQuery"] == "POS-000002"


def test_assistant_recognizes_product_edit_filter_and_sort_commands():
    edit = deterministic_intent("Edit product Lenovo GM2 pro")
    assert edit == {"intent": "edit_product", "productQuery": "lenovo gm2 pro"}

    filtered = deterministic_intent("Filter low stock items")
    assert filtered["intent"] == "inventory_view"
    assert filtered["stockStatus"] == "low-stock"

    sorted_items = deterministic_intent("Sort products by stock descending")
    assert sorted_items["intent"] == "inventory_view"
    assert sorted_items["sortBy"] == "stock"
    assert sorted_items["sortDirection"] == "desc"

    searched = deterministic_intent("Search inventory for Lenovo GM2")
    assert searched["intent"] == "inventory_view"
    assert searched["productQuery"] == "lenovo gm2"


def test_assistant_reset_filter_follow_up_has_its_own_action():
    assert deterministic_intent("Reset filters") == {"intent": "reset_filters"}
    assert deterministic_intent("clear search") == {"intent": "reset_filters"}

    owner = {"role": "owner", "permissions": ["*"]}
    response = process_read_intent(None, "business-1", owner, {"intent": "reset_filters"})
    assert response == {
        "message": "Filters cleared. Showing all records again.",
        "clientAction": {"type": "reset_filters"},
    }


def test_assistant_returns_safe_client_and_form_actions():
    owner = {"role": "owner", "permissions": ["*"]}

    order_export = process_read_intent(None, "business-1", owner, {"intent": "export_orders"})
    assert order_export["clientAction"] == {"type": "export_orders"}

    add_order = process_read_intent(None, "business-1", owner, {"intent": "open_add_order"})
    assert add_order["navigateTo"] == "/orders?assistantAction=add-order"

    inventory_view = process_read_intent(
        None,
        "business-1",
        owner,
        {
            "intent": "inventory_view",
            "productQuery": "Lenovo GM2",
            "stockStatus": "low-stock",
            "sortBy": "stock",
            "sortDirection": "desc",
        },
    )
    assert inventory_view["navigateTo"] == (
        "/inventory?search=Lenovo+GM2&stockStatus=low-stock&sortBy=stock&sortDirection=desc"
    )


def test_assistant_recognizes_dashboard_sections_and_filtered_views():
    assert deterministic_intent("Filter packed orders") == {
        "intent": "order_view",
        "orderQuery": "",
        "status": "packed",
    }
    assert deterministic_intent("Show warranty claims") == {
        "intent": "open_section",
        "section": "warranty_claims",
    }
    assert deterministic_intent("Open customer messages") == {
        "intent": "open_section",
        "section": "customer_messages",
    }
    assert deterministic_intent("Open billing settings") == {
        "intent": "open_settings",
        "section": "billing",
    }


def test_assistant_understands_month_first_calendar_dates():
    intent = deterministic_intent("Show me August 23rd orders")
    assert intent["intent"] == "order_view"
    assert intent["dateFrom"] == "2026-08-23"
    assert intent["dateTo"] == "2026-08-23"


def test_assistant_returns_routes_for_new_dashboard_features():
    owner = {"role": "owner", "permissions": ["*"]}

    packed_orders = process_read_intent(
        None,
        "business-1",
        owner,
        {"intent": "order_view", "orderQuery": "", "status": "packed"},
    )
    assert packed_orders["navigateTo"] == "/orders?assistantAction=open-online-orders&status=packed"

    messages = process_read_intent(
        None,
        "business-1",
        owner,
        {"intent": "open_section", "section": "customer_messages"},
    )
    assert messages["navigateTo"] == "/customers?tab=messages"

    billing = process_read_intent(
        None,
        "business-1",
        owner,
        {"intent": "open_settings", "section": "billing"},
    )
    assert billing["clientAction"] == {"type": "open_settings", "section": "billing"}

    customer_export = process_read_intent(
        None,
        "business-1",
        owner,
        {"intent": "export_customers"},
    )
    assert customer_export["clientAction"] == {"type": "export_customers"}
