import hashlib
import json
import re

from app.core.authorization import membership_has_permission
from app.services.cache_revision_service import get_cache_revision
from app.services.customer_service import stream_customers
from app.services.order_service import stream_orders
from app.services.product_service import stream_products

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
            # Later records cannot change the existing first-match result limit.
            if len(order_results) == limit_per_type:
                break

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
            # Later records cannot change the existing first-match result limit.
            if len(product_results) == limit_per_type:
                break

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
            # Later records cannot change the existing first-match result limit.
            if len(customer_results) == limit_per_type:
                break

    return {
        "orders": order_results[:limit_per_type],
        "products": product_results[:limit_per_type],
        "customers": customer_results[:limit_per_type],
    }


def search_scope(membership):
    # Include only server-granted modules so permission changes cannot reuse broader cached results.
    return ",".join(
        collection for collection, permission in (
            ("orders", "orders:read"), ("products", "inventory:read"), ("customers", "customers:read"),
        )
        if membership_has_permission(membership, permission)
    )


def get_search_revision(database, business_id, membership):
    # Reuse existing atomic markers; search caching needs no extra writes or collection scans.
    scope = search_scope(membership)
    revisions = {
        collection: get_cache_revision(database, business_id, collection)
        for collection in scope.split(",") if collection
    }
    revision = hashlib.sha256(json.dumps(revisions, sort_keys=True).encode()).hexdigest()
    return {"revision": revision, "scope": scope}


def global_search(database, business_id, query, membership):
    # Invalid/short searches return the same empty result without reading business collections.
    if len(sanitize_search_query(query).casefold()) < 2:
        return {"orders": [], "products": [], "customers": []}
    # Exclude forbidden modules before constructing lazy scans; each stops after eight matches.
    return search_records(
        stream_orders(database, business_id) if membership_has_permission(membership, "orders:read") else [],
        stream_products(database, business_id) if membership_has_permission(membership, "inventory:read") else [],
        stream_customers(database, business_id) if membership_has_permission(membership, "customers:read") else [],
        query,
    )
