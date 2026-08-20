from app.core.errors import ApiError
from app.services.product_service import get_product, list_products


def resolve_short_link(database, short_code, expected_type=None):
    snapshot = database.collection("shortLinks").document(short_code).get()

    if not snapshot.exists:
        raise ApiError("public_link_not_found", "This Vendly link is invalid.", 404)

    link = {"shortCode": snapshot.id, **snapshot.to_dict()}

    if link.get("status") != "active":
        raise ApiError("public_link_inactive", "This Vendly link is inactive.", 404)
    if expected_type and link.get("type") != expected_type:
        raise ApiError("public_link_not_found", "This Vendly link is invalid.", 404)

    return link


def public_variant(variant):
    return {
        "id": variant.get("id"),
        "size": variant.get("size", ""),
        "sku": variant.get("sku", ""),
        "availableStock": variant.get("stockAvailable", 0),
        "stockStatus": variant.get("stockStatus", "out-of-stock"),
    }


def public_product(product):
    return {
        "id": product["id"],
        "shortCode": product.get("shortCode", ""),
        "name": product.get("name", ""),
        "colourName": product.get("colourName", ""),
        "colourHex": product.get("colourHex", ""),
        "productType": product.get("productType", ""),
        "categoryId": product.get("categoryId", ""),
        "categoryName": product.get("categoryName", ""),
        "brand": product.get("brand", ""),
        "description": product.get("description", ""),
        "aiDescription": product.get("aiDescription", ""),
        "sellingPriceMinor": product.get("sellingPriceMinor", 0),
        "compareAtPriceMinor": product.get("compareAtPriceMinor", 0),
        "weightGrams": product.get("weightGrams", 0),
        "availableStock": product.get("availableStock", 0),
        "stockStatus": product.get("stockStatus", "out-of-stock"),
        "approvedReviewCount": product.get("approvedReviewCount", 0),
        "media": [
            {
                "type": item.get("type", "image"),
                "url": item.get("url", ""),
            }
            for item in product.get("media", [])
            if item.get("url")
        ],
        "hasSizes": product.get("hasSizes", False),
        "variants": [
            public_variant(variant)
            for variant in product.get("variantSummaries", [])
            if variant.get("stockAvailable", 0) > 0
        ],
    }


def public_business(snapshot):
    business = snapshot.to_dict()
    return {
        "id": snapshot.id,
        "name": business.get("name", ""),
        "shortCode": business.get("shortCode", ""),
        "logoUrl": business.get("logoUrl", ""),
        "phone": business.get("publicPhone", ""),
        "email": business.get("publicEmail", ""),
        "currency": business.get("currency", "LKR"),
        "status": business.get("status", "inactive"),
    }


def get_public_store(database, short_code):
    link = resolve_short_link(database, short_code, "store")
    business_snapshot = database.collection("businesses").document(
        link["businessId"],
    ).get()

    if not business_snapshot.exists or business_snapshot.to_dict().get("status") != "active":
        raise ApiError("store_not_found", "This Vendly store is unavailable.", 404)

    products = list_products(database, business_snapshot.id, status="active")
    return {
        "business": public_business(business_snapshot),
        "products": [public_product(product) for product in products],
    }


def get_public_product(database, short_code):
    link = resolve_short_link(database, short_code, "product")
    business_snapshot = database.collection("businesses").document(
        link["businessId"],
    ).get()

    if not business_snapshot.exists or business_snapshot.to_dict().get("status") != "active":
        raise ApiError("store_not_found", "This Vendly store is unavailable.", 404)

    product = get_product(database, link["businessId"], link["productId"])

    if product.get("status") != "active":
        raise ApiError("product_not_found", "This product is unavailable.", 404)

    return {
        "business": public_business(business_snapshot),
        "product": public_product(product),
    }
