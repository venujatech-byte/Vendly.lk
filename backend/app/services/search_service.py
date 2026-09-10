import re

from app.services.customer_service import list_customers
from app.services.order_service import list_orders
from app.services.product_service import list_products

MAX_SEARCH_QUERY_LENGTH = 80
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")
HTML_TAG_PATTERN = re.compile(r"<[^>]*>")


def sanitize_search_query(query: str) -> str:
    """Sanitize search input: strip control characters, HTML tags, and clamp length."""
    if not query:
        return ""

    # Strip control characters & null bytes
    cleaned = CONTROL_CHARS_PATTERN.sub("", str(query))

    # Strip HTML / script tags
    cleaned = HTML_TAG_PATTERN.sub("", cleaned)

    # Normalize spaces
    cleaned = " ".join(cleaned.split())

    # Enforce max length
    if len(cleaned) > MAX_SEARCH_QUERY_LENGTH:
        cleaned = cleaned[:MAX_SEARCH_QUERY_LENGTH].strip()

    return cleaned


def contains_query(values, query):
    return any(query in str(value or "").casefold() for value in values)


def search_records(orders, products, customers, query, limit_per_type=8):
    sanitized_query = sanitize_search_query(query)
    query_text = sanitized_query.casefold()

    if len(query_text) < 2:
        return {"orders": [], "products": [], "customers": []}

    order_results = []
    for order in orders:
        item_values = [
            value
            for item in order.get("items", [])
            for value in (item.get("name"), item.get("sku"), item.get("barcode"))
        ]
        if contains_query(
            [
                order.get("orderNumber"),
                order.get("waybillNumber"),
                order.get("customerSnapshot", {}).get("name"),
                order.get("customerSnapshot", {}).get("normalizedPhone"),
                *item_values,
            ],
            query_text,
        ):
            order_results.append(
                {
                    "id": order.get("id"),
                    "orderNumber": order.get("orderNumber", ""),
                    "customerName": order.get("customerSnapshot", {}).get("name", ""),
                    "status": order.get("fulfilmentStatus", ""),
                    "waybillNumber": order.get("waybillNumber", ""),
                },
            )

    product_results = []
    for product in products:
        variant_values = [
            value
            for variant in product.get("variantSummaries", [])
            for value in (variant.get("sku"), variant.get("barcode"), variant.get("size"))
        ]
        if contains_query(
            [
                product.get("name"),
                product.get("skuPrefix"),
                product.get("brand"),
                product.get("categoryName"),
                *variant_values,
            ],
            query_text,
        ):
            product_results.append(
                {
                    "id": product.get("id"),
                    "name": product.get("name", ""),
                    "sku": product.get("skuPrefix", ""),
                    "availableStock": product.get("availableStock", 0),
                    "status": product.get("stockStatus", ""),
                },
            )

    customer_results = []
    for customer in customers:
        if contains_query(
            [
                customer.get("name"),
                customer.get("normalizedPhone"),
                customer.get("email"),
            ],
            query_text,
        ):
            customer_results.append(
                {
                    "id": customer.get("id"),
                    "name": customer.get("name", ""),
                    "phone": customer.get("normalizedPhone", ""),
                    "riskLevel": customer.get("riskLevel", "low"),
                },
            )

    return {
        "orders": order_results[:limit_per_type],
        "products": product_results[:limit_per_type],
        "customers": customer_results[:limit_per_type],
    }


def global_search(database, business_id, query):
    return search_records(
        list_orders(database, business_id),
        list_products(database, business_id),
        list_customers(database, business_id),
        query,
    )
