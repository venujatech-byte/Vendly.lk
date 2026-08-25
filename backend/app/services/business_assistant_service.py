import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from firebase_admin import firestore

from app.core.authorization import membership_has_permission
from app.core.errors import ApiError
from app.services.ai_service import generate_business_assistant_intent
from app.services.analytics_service import get_business_analytics
from app.services.order_service import list_orders, update_order_status
from app.services.product_service import adjust_variant_stock, list_products


ORDER_NUMBER_PATTERN = re.compile(r"\bVD-\d+\b", re.IGNORECASE)
ALLOWED_ORDER_STATUSES = {
    "confirmed",
    "packed",
    "shipped",
    "delivered",
    "returned",
    "cancelled",
}
ORDER_VIEW_STATUSES = ALLOWED_ORDER_STATUSES | {"pending"}
ALLOWED_CONFIRMED_ACTIONS = {"update_order_status", "adjust_stock"}
PAGE_ROUTES = {
    "overview": "/",
    "orders": "/orders",
    "inventory": "/inventory",
    "couriers": "/couriers",
    "customers": "/customers",
    "analytics": "/analytics",
}


def format_money(minor_units):
    return f"LKR {minor_units / 100:,.0f}"


def require_permission(membership, permission):
    if not membership_has_permission(membership, permission):
        raise ApiError(
            "permission_denied",
            "Your staff role does not allow this assistant action.",
            403,
            {"requiredPermission": permission},
        )


def clean_product_query(message):
    query = message.casefold()
    query = re.sub(r"\b(increase|add|raise|decrease|reduce|remove|adjust|change)\b", " ", query)
    query = re.sub(r"\b(stock|inventory|quantity|of|for|to)\b", " ", query)
    query = re.sub(r"\bby\s+-?\d+\b", " ", query)
    query = re.sub(r"\s+", " ", query)
    return query.strip()


def clean_inventory_query(message):
    query = message.casefold()
    query = re.sub(
        r"\b(search|find|filter|show|list|sort|products?|items?|inventory|for|by|ascending|descending|asc|desc|highest|lowest|first)\b",
        " ",
        query,
    )
    query = re.sub(r"\b(in stock|low stock|out of stock)\b", " ", query)
    query = re.sub(r"\b(name|price|stock)\b", " ", query)
    return re.sub(r"\s+", " ", query).strip()


def clean_order_view_query(message):
    query = message.casefold()
    query = re.sub(
        r"\b(search|find|filter|show|list|orders?|for|by|status|with|matching|all)\b",
        " ",
        query,
    )
    query = re.sub(
        r"\b(pending|confirmed|packed|shipped|delivered|returned|cancelled)\b",
        " ",
        query,
    )
    return re.sub(r"\s+", " ", query).strip()


def deterministic_intent(message):
    """Handle common commands predictably when AI is unavailable or unnecessary."""
    text = message.strip()
    lowered = text.casefold()
    order_number_match = ORDER_NUMBER_PATTERN.search(text)

    if not text or lowered in {"help", "commands", "what can you do"}:
        return {"intent": "help"}

    # Reset commands must be handled before the general filter branch. Sending
    # them to the AI classifier can turn a follow-up such as "reset filters"
    # back into the previous filter request instead of clearing the page.
    if any(
        phrase in lowered
        for phrase in (
            "reset filter",
            "reset filters",
            "clear filter",
            "clear filters",
            "remove filter",
            "remove filters",
            "clear search",
            "show all records",
            "show everything",
        )
    ):
        return {"intent": "reset_filters"}

    if "export" in lowered and any(word in lowered for word in ("order", "orders")):
        return {"intent": "export_orders"}
    if "export" in lowered and any(word in lowered for word in ("inventory", "product", "products", "item", "items")):
        return {"intent": "export_inventory"}
    if "export" in lowered and any(word in lowered for word in ("customer", "customers")):
        return {"intent": "export_customers"}

    if any(phrase in lowered for phrase in ("shop sale", "physical sale", "counter sale", "sales order")) and any(
        word in lowered for word in ("add", "create", "new", "record", "make")
    ):
        return {"intent": "open_shop_sale"}
    if any(phrase in lowered for phrase in ("add order", "new order", "create order", "online order")):
        return {"intent": "open_add_order"}
    if any(phrase in lowered for phrase in ("add product", "new product", "create product")):
        return {"intent": "open_add_product"}
    if "courier" in lowered and any(word in lowered for word in ("add", "new", "create")):
        return {"intent": "open_add_courier"}
    if "edit" in lowered and any(word in lowered for word in ("product", "item")):
        product_query = re.sub(r"\b(edit|update|change|product|item|details?|information|for)\b", " ", lowered)
        return {
            "intent": "edit_product",
            "productQuery": re.sub(r"\s+", " ", product_query).strip(),
        }

    if any(word in lowered for word in ("open", "show", "view", "manage", "go to")):
        if "warranty" in lowered:
            return {"intent": "open_section", "section": "warranty_claims"}
        if any(phrase in lowered for phrase in ("shop sale", "shop order", "physical sale", "counter sale")):
            return {"intent": "open_section", "section": "shop_sales"}
        if "categor" in lowered:
            return {"intent": "open_section", "section": "categories"}
        if "message" in lowered or "chat" in lowered:
            return {"intent": "open_section", "section": "customer_messages"}
        if "review" in lowered:
            return {"intent": "open_section", "section": "customer_reviews"}
        if "fraud" in lowered:
            return {"intent": "open_section", "section": "fraud_reports"}

    if any(word in lowered for word in ("settings", "setting", "billing", "subscription", "plan", "permissions", "staff")):
        section = "general"
        if any(word in lowered for word in ("billing", "subscription", "plan", "payment")):
            section = "billing"
        elif any(word in lowered for word in ("permissions", "staff", "team")):
            section = "staff"
        return {"intent": "open_settings", "section": section}

    if (
        any(word in lowered for word in ("filter", "sort"))
        or re.search(r"\bsearch\s+(?:the\s+)?(?:inventory|products?|items?)\b", lowered)
    ) and any(
        word in lowered for word in ("inventory", "product", "products", "item", "items", "stock")
    ):
        stock_status = ""
        if "out of stock" in lowered:
            stock_status = "out-of-stock"
        elif "low stock" in lowered:
            stock_status = "low-stock"
        elif "in stock" in lowered:
            stock_status = "in-stock"

        sort_by = ""
        if "price" in lowered:
            sort_by = "price"
        elif "stock" in lowered and "sort" in lowered:
            sort_by = "stock"
        elif "name" in lowered:
            sort_by = "name"

        descending = any(word in lowered for word in ("descending", "desc", "highest", "most"))
        return {
            "intent": "inventory_view",
            "productQuery": clean_inventory_query(text),
            "stockStatus": stock_status,
            "sortBy": sort_by,
            "sortDirection": "desc" if descending else "asc",
        }
    if any(word in lowered for word in ("open", "go to", "navigate", "take me")):
        for page in PAGE_ROUTES:
            if page in lowered:
                return {"intent": "navigate", "page": page}
    if any(phrase in lowered for phrase in ("today's summary", "todays summary", "business summary", "dashboard summary", "how is business")):
        return {"intent": "business_summary"}
    if "low stock" in lowered or "restock" in lowered:
        return {"intent": "low_stock"}
    if (
        "pending order" in lowered or "orders need confirmation" in lowered
    ) and not any(word in lowered for word in ("filter", "search", "find", "list")):
        return {"intent": "pending_orders"}

    statuses = [status for status in ALLOWED_ORDER_STATUSES if status in lowered]
    if order_number_match and statuses and any(word in lowered for word in ("mark", "set", "update", "change", "move")):
        return {
            "intent": "update_order_status",
            "orderQuery": order_number_match.group(0).upper(),
            "status": statuses[0],
        }
    if order_number_match:
        return {
            "intent": "search_order",
            "orderQuery": order_number_match.group(0).upper(),
        }


    view_statuses = [status for status in ORDER_VIEW_STATUSES if status in lowered]
    if any(word in lowered for word in ("filter", "search", "find", "show", "list")) and any(
        word in lowered for word in ("order", "orders")
    ):
        return {
            "intent": "order_view",
            "orderQuery": clean_order_view_query(text),
            "status": view_statuses[0] if view_statuses else "",
        }

    if "stock" in lowered and any(word in lowered for word in ("increase", "add", "raise", "decrease", "reduce", "remove", "adjust")):
        quantity_match = re.search(r"\bby\s+(\d+)\b", lowered)
        quantity = int(quantity_match.group(1)) if quantity_match else 0
        if any(word in lowered for word in ("decrease", "reduce", "remove")):
            quantity *= -1
        return {
            "intent": "adjust_stock",
            "productQuery": clean_product_query(text),
            "variantQuery": "",
            "quantityChange": quantity,
        }

    if any(word in lowered for word in ("order", "orders")):
        return {"intent": "pending_orders"}
    if any(word in lowered for word in ("product", "sku", "barcode", "item")):
        query = re.sub(r"\b(find|show|search|product|item|sku|barcode|for|me)\b", " ", lowered)
        return {"intent": "search_product", "productQuery": re.sub(r"\s+", " ", query).strip()}

    if any(word in lowered for word in ("customer", "customers")):
        query = re.sub(r"\b(find|show|search|customer|customers|for|me)\b", " ", lowered)
        return {"intent": "customer_view", "customerQuery": re.sub(r"\s+", " ", query).strip()}

    return {"intent": "unknown"}


def classify_intent(message):
    deterministic = deterministic_intent(message)
    if deterministic["intent"] != "unknown":
        return deterministic
    return generate_business_assistant_intent(message) or deterministic


def product_matches(product, query):
    needle = str(query or "").strip().casefold()
    if not needle:
        return False
    searchable = [
        product.get("name", ""),
        product.get("brand", ""),
        product.get("categoryName", ""),
        product.get("skuPrefix", ""),
    ]
    for variant in product.get("variantSummaries", []):
        searchable.extend((variant.get("size", ""), variant.get("sku", ""), variant.get("barcode", "")))
    return any(needle in str(value).casefold() for value in searchable)


def product_card(product):
    return {
        "type": "product",
        "id": product.get("id"),
        "title": product.get("name", "Product"),
        "subtitle": product.get("categoryName") or "Uncategorized",
        "value": f"{product.get('availableStock', 0)} available",
        "status": product.get("stockStatus", "in-stock"),
        "navigateTo": "/inventory",
    }


def order_card(order):
    return {
        "type": "order",
        "id": order.get("id"),
        "title": order.get("orderNumber", "Order"),
        "subtitle": order.get("customerSnapshot", {}).get("name") or "Customer",
        "value": format_money(order.get("totalAmountMinor", 0)),
        "status": order.get("fulfilmentStatus", "needs-confirmation"),
        "navigateTo": "/orders",
    }


def find_order(database, business_id, query):
    matches = list_orders(database, business_id, search=str(query or "").strip())
    normalized = str(query or "").strip().casefold()
    exact = [item for item in matches if item.get("orderNumber", "").casefold() == normalized]
    return exact or matches


def resolve_variant(products, product_query, variant_query=""):
    product_matches_list = [product for product in products if product_matches(product, product_query)]
    if len(product_matches_list) != 1:
        return product_matches_list, None, None

    product = product_matches_list[0]
    variants = product.get("variantSummaries", [])
    variant_needle = str(variant_query or "").strip().casefold()
    if variant_needle:
        variants = [
            variant for variant in variants
            if variant_needle in str(variant.get("size", "")).casefold()
            or variant_needle in str(variant.get("sku", "")).casefold()
            or variant_needle in str(variant.get("barcode", "")).casefold()
        ]
    return product_matches_list, product, variants[0] if len(variants) == 1 else None


def help_response():
    return {
        "message": (
            "I can show today's summary, pending orders, low-stock products, find an order or product, "
            "open dashboard pages, settings and customer sections; export orders, inventory or customers; "
            "open order, shop-sale, product and courier forms; filter orders or inventory; update an order status; "
            "and adjust stock. Database changes always require "
            "confirmation or a validated dashboard form."
        ),
        "suggestions": ["Today's summary", "Filter packed orders", "Open customer messages", "Add a new order"],
    }


def process_read_intent(database, business_id, membership, intent):
    intent_name = intent.get("intent")

    if intent_name == "help" or intent_name == "unknown":
        return help_response()

    if intent_name == "navigate":
        page = str(intent.get("page") or "").strip().casefold()
        route = PAGE_ROUTES.get(page)
        if not route:
            return help_response()
        return {
            "message": f"Opening the {page} page.",
            "navigateTo": route,
        }

    if intent_name == "export_orders":
        require_permission(membership, "orders:read")
        return {
            "message": "Preparing your courier-compatible order export.",
            "clientAction": {"type": "export_orders"},
        }

    if intent_name == "export_inventory":
        require_permission(membership, "inventory:read")
        return {
            "message": "Preparing your inventory export.",
            "clientAction": {"type": "export_inventory"},
        }

    if intent_name == "export_customers":
        require_permission(membership, "customers:read")
        return {
            "message": "Preparing your customer export.",
            "clientAction": {"type": "export_customers"},
        }

    if intent_name == "reset_filters":
        return {
            "message": "Filters cleared. Showing all records again.",
            "clientAction": {"type": "reset_filters"},
        }

    if intent_name == "open_settings":
        section = str(intent.get("section") or "general").strip().casefold()
        if section not in {"general", "staff", "billing"}:
            section = "general"
        return {
            "message": f"Opening {section} settings.",
            "clientAction": {"type": "open_settings", "section": section},
        }

    if intent_name == "open_add_courier":
        require_permission(membership, "couriers:manage")
        return {
            "message": "Opening the add-courier form.",
            "navigateTo": "/couriers?assistantAction=add-courier",
        }

    if intent_name == "open_section":
        section = str(intent.get("section") or "").strip().casefold()
        sections = {
            "shop_sales": ("orders:read", "/orders?assistantAction=open-shop-sales", "shop sales"),
            "warranty_claims": ("orders:read", "/orders?assistantAction=open-warranty-claims", "warranty claims"),
            "categories": ("inventory:read", "/inventory?assistantAction=open-categories", "categories"),
            "customer_messages": ("customers:read", "/customers?tab=messages", "customer messages"),
            "customer_reviews": ("customers:read", "/customers?tab=reviews", "customer reviews"),
            "fraud_reports": ("customers:read", "/customers?tab=fraud", "fraud reports"),
        }
        section_config = sections.get(section)
        if not section_config:
            return help_response()
        permission, route, label = section_config
        require_permission(membership, permission)
        return {"message": f"Opening {label}.", "navigateTo": route}

    if intent_name == "order_view":
        require_permission(membership, "orders:read")
        query = str(intent.get("orderQuery") or "").strip()
        status = str(intent.get("status") or "").strip().casefold()
        if status not in ORDER_VIEW_STATUSES:
            status = ""
        parameters = {}
        if query:
            parameters["search"] = query
        if status:
            parameters["status"] = status
        route = "/orders" + (f"?{urlencode(parameters)}" if parameters else "")
        return {"message": "Opening the matching orders.", "navigateTo": route}

    if intent_name == "customer_view":
        require_permission(membership, "customers:read")
        query = str(intent.get("customerQuery") or "").strip()
        route = "/customers" + (f"?{urlencode({'search': query})}" if query else "")
        return {"message": "Opening the matching customers.", "navigateTo": route}

    if intent_name == "open_add_order":
        require_permission(membership, "orders:manage")
        return {
            "message": "Opening the new online-order form.",
            "navigateTo": "/orders?assistantAction=add-order",
        }

    if intent_name == "open_shop_sale":
        require_permission(membership, "orders:manage")
        return {
            "message": "Opening the physical-shop sales form.",
            "navigateTo": "/orders?assistantAction=add-shop-sale",
        }

    if intent_name == "open_add_product":
        require_permission(membership, "inventory:manage")
        return {
            "message": "Opening the add-product form.",
            "navigateTo": "/inventory?assistantAction=add-product",
        }

    if intent_name == "edit_product":
        require_permission(membership, "inventory:manage")
        products = [
            product for product in list_products(database, business_id)
            if product_matches(product, intent.get("productQuery"))
        ]
        if len(products) != 1:
            return {
                "message": "I need one exact product to edit. Use its full name, SKU or barcode.",
                "cards": [product_card(product) for product in products[:5]],
            }
        product = products[0]
        return {
            "message": f"Opening {product.get('name')} in the product editor.",
            "navigateTo": f"/inventory?assistantAction=edit-product&productId={product.get('id')}",
        }

    if intent_name == "inventory_view":
        require_permission(membership, "inventory:read")
        query = str(intent.get("productQuery") or "").strip()
        stock_status = str(intent.get("stockStatus") or "").strip()
        sort_by = str(intent.get("sortBy") or "").strip()
        sort_direction = "desc" if intent.get("sortDirection") == "desc" else "asc"
        if stock_status not in {"", "in-stock", "low-stock", "out-of-stock"}:
            stock_status = ""
        if sort_by not in {"", "name", "price", "stock"}:
            sort_by = ""
        parameters = {}
        if query:
            parameters["search"] = query
        if stock_status:
            parameters["stockStatus"] = stock_status
        if sort_by:
            parameters["sortBy"] = sort_by
            parameters["sortDirection"] = sort_direction
        route = "/inventory" + (f"?{urlencode(parameters)}" if parameters else "")
        return {
            "message": "Opening the matching inventory view.",
            "navigateTo": route,
        }

    if intent_name == "business_summary":
        require_permission(membership, "analytics:read")
        analytics = get_business_analytics(database, business_id)
        counts = analytics.get("orderCounts", {})
        financials = analytics.get("financials", {})
        work = analytics.get("workCentre", {})
        return {
            "message": (
                f"Today you have {analytics.get('performance', {}).get('ordersToday', 0)} new orders. "
                f"Delivered revenue is {format_money(financials.get('productRevenueMinor', 0))}; "
                f"{work.get('needsConfirmation', 0)} orders need confirmation and "
                f"{work.get('lowStockProducts', 0)} products need restocking."
            ),
            "cards": [
                {"type": "metric", "title": "All orders", "value": counts.get("all", 0), "navigateTo": "/orders"},
                {"type": "metric", "title": "Gross profit", "value": format_money(financials.get("grossProfitMinor", 0)), "navigateTo": "/analytics"},
            ],
        }

    if intent_name == "pending_orders":
        require_permission(membership, "orders:read")
        orders = list_orders(database, business_id, status="needs-confirmation")
        return {
            "message": f"You have {len(orders)} orders waiting for confirmation.",
            "cards": [order_card(order) for order in orders[:5]],
            "suggestions": ["Today's summary", "Show low stock"],
        }

    if intent_name == "low_stock":
        require_permission(membership, "inventory:read")
        products = list_products(database, business_id)
        products = [product for product in products if product.get("stockStatus") in {"low-stock", "out-of-stock"}]
        return {
            "message": f"{len(products)} products need stock attention.",
            "cards": [product_card(product) for product in products[:5]],
            "suggestions": ["Today's summary", "Show pending orders"],
        }

    if intent_name == "search_order":
        require_permission(membership, "orders:read")
        orders = find_order(database, business_id, intent.get("orderQuery"))
        if not orders:
            return {"message": "I could not find a matching order. Try the complete order number, such as VD-000024."}
        return {"message": f"I found {len(orders)} matching order(s).", "cards": [order_card(order) for order in orders[:5]]}

    if intent_name == "search_product":
        require_permission(membership, "inventory:read")
        products = [
            product for product in list_products(database, business_id)
            if product_matches(product, intent.get("productQuery"))
        ]
        if not products:
            return {"message": "I could not find that product. Try its complete name, SKU or barcode."}
        return {"message": f"I found {len(products)} matching product(s).", "cards": [product_card(product) for product in products[:5]]}

    return None


def prepare_write_intent(database, business_id, membership, intent):
    intent_name = intent.get("intent")

    if intent_name == "update_order_status":
        require_permission(membership, "orders:manage")
        status = str(intent.get("status") or "").strip().casefold()
        if status not in ALLOWED_ORDER_STATUSES:
            return {"message": "Tell me the valid next status you want to use."}
        orders = find_order(database, business_id, intent.get("orderQuery"))
        if len(orders) != 1:
            return {
                "message": "I need one exact order number before changing a status.",
                "cards": [order_card(order) for order in orders[:5]],
            }
        order = orders[0]
        return {
            "message": f"Please confirm: change {order.get('orderNumber')} from {order.get('fulfilmentStatus')} to {status}?",
            "pendingAction": {
                "type": "update_order_status",
                "label": f"Mark {order.get('orderNumber')} as {status}",
                "orderId": order.get("id"),
                "orderNumber": order.get("orderNumber"),
                "status": status,
            },
        }

    if intent_name == "adjust_stock":
        require_permission(membership, "inventory:manage")
        try:
            quantity_change = int(intent.get("quantityChange") or 0)
        except (TypeError, ValueError):
            quantity_change = 0
        if quantity_change == 0 or abs(quantity_change) > 100000:
            return {"message": "Tell me how many units to add or remove, for example: increase GM2 stock by 10."}
        products = list_products(database, business_id)
        matches, product, variant = resolve_variant(
            products,
            intent.get("productQuery"),
            intent.get("variantQuery"),
        )
        if not product:
            return {
                "message": "I need one exact product. Try its full name, SKU or barcode.",
                "cards": [product_card(item) for item in matches[:5]],
            }
        if not variant:
            return {
                "message": "That product has multiple size/SKU rows. Include the size, SKU or barcode in your request.",
                "cards": [product_card(product)],
            }
        direction = "increase" if quantity_change > 0 else "decrease"
        return {
            "message": f"Please confirm: {direction} {product.get('name')} ({variant.get('sku')}) stock by {abs(quantity_change)}?",
            "pendingAction": {
                "type": "adjust_stock",
                "label": f"{direction.title()} stock by {abs(quantity_change)}",
                "productId": product.get("id"),
                "productName": product.get("name"),
                "variantId": variant.get("id"),
                "variantSku": variant.get("sku"),
                "quantityChange": quantity_change,
            },
        }

    return None


def audit_action(database, business_id, uid, action, result):
    database.collection("businesses").document(business_id).collection(
        "assistantAuditLogs",
    ).document().set(
        {
            "uid": uid,
            "action": action,
            "resultId": result.get("id", "") if isinstance(result, dict) else "",
            "createdAt": firestore.SERVER_TIMESTAMP,
        },
    )


def confirm_action(database, business_id, uid, membership, action):
    if not isinstance(action, dict) or action.get("type") not in ALLOWED_CONFIRMED_ACTIONS:
        raise ApiError("invalid_assistant_action", "This assistant action is not allowed.", 422)

    if action["type"] == "update_order_status":
        require_permission(membership, "orders:manage")
        status = str(action.get("status") or "").strip().casefold()
        if status not in ALLOWED_ORDER_STATUSES:
            raise ApiError("invalid_assistant_action", "Choose a valid order status.", 422)
        order = update_order_status(
            database,
            business_id,
            str(action.get("orderId") or ""),
            uid,
            {"status": status, "note": "Updated through the Vendly business assistant"},
        )
        audit_action(database, business_id, uid, action, order)
        return {
            "message": f"Done — {order.get('orderNumber')} is now {status}.",
            "cards": [order_card(order)],
        }

    require_permission(membership, "inventory:manage")
    try:
        quantity_change = int(action.get("quantityChange") or 0)
    except (TypeError, ValueError) as error:
        raise ApiError("invalid_assistant_action", "Choose a valid stock quantity.", 422) from error
    if quantity_change == 0 or abs(quantity_change) > 100000:
        raise ApiError("invalid_assistant_action", "Choose a valid stock quantity.", 422)
    product = adjust_variant_stock(
        database,
        business_id,
        str(action.get("productId") or ""),
        str(action.get("variantId") or ""),
        uid,
        {
            "quantityChange": quantity_change,
            "reason": "Adjusted through the Vendly business assistant",
            "reference": "Business assistant",
        },
    )
    audit_action(database, business_id, uid, action, product)
    return {
        "message": f"Done — {product.get('name')} stock was updated by {quantity_change:+d}.",
        "cards": [product_card(product)],
    }


def handle_business_assistant_message(database, business_id, uid, membership, payload):
    confirmed_action = payload.get("confirmedAction")
    if confirmed_action:
        return confirm_action(database, business_id, uid, membership, confirmed_action)

    message = str(payload.get("message") or "").strip()
    if not message:
        raise ApiError("validation_error", "Enter a message for the business assistant.", 422)
    if len(message) > 1000:
        raise ApiError("validation_error", "The assistant message is too long.", 422)

    intent = classify_intent(message)
    response = process_read_intent(database, business_id, membership, intent)
    if response:
        return response
    response = prepare_write_intent(database, business_id, membership, intent)
    return response or help_response()
