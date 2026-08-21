from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.business_service import generate_short_code
from app.services.numbers import (
    kilograms_to_grams,
    integer_value,
    money_to_minor_units,
    non_negative_integer,
)
from app.services.text import optional_text, required_text, slugify


def stock_status(stock, threshold):
    if stock == 0:
        return "out-of-stock"
    if stock <= threshold:
        return "low-stock"
    return "in-stock"


def normalize_registry_key(value):
    return value.strip().upper()


def validate_product(payload):
    """Validate an Add Product request and return normalized server values."""
    try:
        name = required_text(payload.get("name"), "Product name", 160)
        colour_name = optional_text(payload.get("colourName"), 80)
        product_type = optional_text(payload.get("productType"), 100)
        product_size = optional_text(payload.get("productSize"), 80)
        brand = optional_text(payload.get("brand"), 100)
        supplier_id = optional_text(payload.get("supplierId"), 120)
        description = optional_text(payload.get("description"), 4000)
        ai_description = optional_text(payload.get("aiDescription"), 4000)
        sku_prefix = optional_text(payload.get("skuPrefix"), 60).upper()
        colour_hex = optional_text(payload.get("colourHex"), 20)
        # Category is optional when a product is first created. Sellers can
        # assign an uncategorized product later from the inventory page.
        category_id = optional_text(payload.get("categoryId"), 120)
        cost_price_minor = money_to_minor_units(
            payload.get("costPrice"),
            "Cost price",
        )
        selling_price_minor = money_to_minor_units(
            payload.get("sellingPrice"),
            "Selling price",
            allow_zero=False,
        )
        compare_at_price_minor = money_to_minor_units(
            payload.get("compareAtPrice", 0),
            "Compare-at price",
        )
        weight_grams = kilograms_to_grams(payload.get("weightKg"))
        low_stock_threshold = non_negative_integer(
            payload.get("lowStockThreshold", 5),
            "Low-stock threshold",
        )
        warranty_period_months = non_negative_integer(
            payload.get("warrantyPeriodMonths", 0),
            "Warranty period",
        )
        warranty_notes = optional_text(payload.get("warrantyNotes"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    has_sizes = payload.get("hasSizes") is True
    raw_variants = payload.get("variants")

    if not isinstance(raw_variants, list) or not raw_variants:
        raise ApiError(
            "validation_error",
            "At least one stock row is required.",
            422,
        )

    if len(raw_variants) > 100:
        raise ApiError(
            "too_many_variants",
            "A product can contain no more than 100 size rows.",
            422,
        )

    variants = []
    seen_sizes = set()
    seen_skus = set()
    seen_barcodes = set()

    for index, raw_variant in enumerate(raw_variants, start=1):
        try:
            size = optional_text(raw_variant.get("size"), 40)
            sku = required_text(raw_variant.get("sku"), f"SKU in row {index}", 80).upper()
            barcode = required_text(
                raw_variant.get("barcode"),
                f"Barcode in row {index}",
                80,
            )
            initial_stock = non_negative_integer(
                raw_variant.get("stock", 0),
                f"Stock in row {index}",
            )
            variant_cost_price_minor = money_to_minor_units(
                raw_variant.get("costPrice", payload.get("costPrice")),
                f"Cost price in row {index}",
            )
            variant_selling_price_minor = money_to_minor_units(
                raw_variant.get("sellingPrice", payload.get("sellingPrice")),
                f"Selling price in row {index}",
                allow_zero=False,
            )
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

        if has_sizes and not size:
            raise ApiError(
                "validation_error",
                f"Size is required in row {index}.",
                422,
            )

        if not has_sizes and len(raw_variants) != 1:
            raise ApiError(
                "validation_error",
                "A product without sizes must have exactly one stock row.",
                422,
            )

        normalized_size = size.casefold()
        normalized_sku = normalize_registry_key(sku)
        normalized_barcode = normalize_registry_key(barcode)

        if has_sizes and normalized_size in seen_sizes:
            raise ApiError("duplicate_size", f"Size {size} is repeated.", 422)
        if normalized_sku in seen_skus:
            raise ApiError("duplicate_sku", f"SKU {sku} is repeated.", 422)
        if normalized_barcode in seen_barcodes:
            raise ApiError(
                "duplicate_barcode",
                f"Barcode {barcode} is repeated.",
                422,
            )

        seen_sizes.add(normalized_size)
        seen_skus.add(normalized_sku)
        seen_barcodes.add(normalized_barcode)
        variants.append(
            {
                "size": size,
                "sku": sku,
                "barcode": barcode,
                "initialStock": initial_stock,
                "costPriceMinor": variant_cost_price_minor,
                "sellingPriceMinor": variant_selling_price_minor,
            },
        )

    raw_media = payload.get("media", [])

    if not isinstance(raw_media, list):
        raise ApiError("validation_error", "Media must be a list.", 422)

    media = []

    for media_item in raw_media[:12]:
        if not isinstance(media_item, dict):
            raise ApiError(
                "validation_error",
                "Each media item must be an object.",
                422,
            )

        try:
            path = optional_text(media_item.get("path"), 500)
            url = optional_text(media_item.get("url"), 2000)
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error
        media_type = media_item.get("type", "image")

        if media_type not in {"image", "video"}:
            raise ApiError(
                "validation_error",
                "Media type must be image or video.",
                422,
            )

        if not path and not url:
            raise ApiError(
                "validation_error",
                "Each media item requires a storage path or URL.",
                422,
            )

        media.append({"path": path, "url": url, "type": media_type})

    return {
        "name": name,
        "colourName": colour_name,
        "colourHex": colour_hex,
        "productType": product_type,
        "productSize": product_size,
        "categoryId": category_id,
        "brand": brand,
        "supplierId": supplier_id,
        "description": description,
        "aiDescription": ai_description,
        "taxCategory": optional_text(payload.get("taxCategory"), 60) or "standard",
        "hasSizes": has_sizes,
        "skuPrefix": sku_prefix,
        "costPriceMinor": cost_price_minor,
        "sellingPriceMinor": selling_price_minor,
        "compareAtPriceMinor": compare_at_price_minor,
        "weightGrams": weight_grams,
        "lowStockThreshold": low_stock_threshold,
        "warrantyPeriodMonths": warranty_period_months,
        "warrantyNotes": warranty_notes,
        "media": media,
        "variants": variants,
    }


def list_products(database, business_id, category_id=None, status=None):
    query = (
        database.collection("businesses")
        .document(business_id)
        .collection("products")
    )

    if category_id:
        query = query.where(filter=FieldFilter("categoryId", "==", category_id))
    if status:
        query = query.where(filter=FieldFilter("status", "==", status))

    return [serialize_snapshot(snapshot) for snapshot in query.limit(200).stream()]


def get_product(database, business_id, product_id):
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("products")
        .document(product_id)
        .get()
    )

    if not snapshot.exists:
        raise ApiError("product_not_found", "Product not found.", 404)

    return serialize_snapshot(snapshot)


def create_product(database, business_id, uid, payload):
    product = validate_product(payload)
    business_reference = database.collection("businesses").document(business_id)
    category_name = "Uncategorized"
    if product["categoryId"]:
        category_snapshot = business_reference.collection("categories").document(
            product["categoryId"],
        ).get()

        if (
            not category_snapshot.exists
            or category_snapshot.to_dict().get("status") != "active"
        ):
            raise ApiError(
                "invalid_category",
                "Choose an active product category.",
                422,
            )
        category_name = category_snapshot.to_dict().get("name", "")

    product_reference = business_reference.collection("products").document()
    variant_collection = business_reference.collection("productVariants")
    inventory_collection = business_reference.collection("inventoryTransactions")
    variant_entries = []
    registry_references = []

    for variant in product["variants"]:
        variant_reference = variant_collection.document()
        sku_registry = business_reference.collection("skuRegistry").document(
            normalize_registry_key(variant["sku"]),
        )
        barcode_registry = business_reference.collection("barcodeRegistry").document(
            normalize_registry_key(variant["barcode"]),
        )
        registry_references.extend(
            [
                (sku_registry, "sku", variant["sku"]),
                (barcode_registry, "barcode", variant["barcode"]),
            ],
        )
        variant_entries.append((variant_reference, variant))

    short_code = generate_short_code()
    short_link_reference = database.collection("shortLinks").document(short_code)
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        for registry_reference, registry_type, registry_value in registry_references:
            if registry_reference.get(transaction=current_transaction).exists:
                raise ApiError(
                    f"{registry_type}_already_exists",
                    f"{registry_type.upper()} {registry_value} is already in use.",
                    409,
                )

        if short_link_reference.get(transaction=current_transaction).exists:
            raise ApiError(
                "short_code_conflict",
                "A public code conflict occurred. Please try again.",
                409,
            )

        timestamp = firestore.SERVER_TIMESTAMP
        total_stock = sum(item["initialStock"] for item in product["variants"])
        overall_status = stock_status(total_stock, product["lowStockThreshold"])
        variant_summaries = []

        for variant_reference, variant in variant_entries:
            initial_stock = variant["initialStock"]
            variant_status = stock_status(initial_stock, product["lowStockThreshold"])
            variant_data = {
                "productId": product_reference.id,
                "size": variant["size"],
                "sku": variant["sku"],
                "barcode": variant["barcode"],
                "costPriceMinor": variant["costPriceMinor"],
                "sellingPriceMinor": variant["sellingPriceMinor"],
                "weightGrams": product["weightGrams"],
                "stockOnHand": initial_stock,
                "stockReserved": 0,
                "stockAvailable": initial_stock,
                "stockStatus": variant_status,
                "status": "active",
                "createdAt": timestamp,
                "updatedAt": timestamp,
            }
            current_transaction.set(variant_reference, variant_data)
            variant_summaries.append(
                {
                    "id": variant_reference.id,
                    "size": variant["size"],
                    "sku": variant["sku"],
                    "barcode": variant["barcode"],
                    "stockOnHand": initial_stock,
                    "stockReserved": 0,
                    "stockAvailable": initial_stock,
                    "stockStatus": variant_status,
                    "costPriceMinor": variant["costPriceMinor"],
                    "sellingPriceMinor": variant["sellingPriceMinor"],
                    "imageUrl": "",
                },
            )

            if initial_stock > 0:
                current_transaction.set(
                    inventory_collection.document(),
                    {
                        "productId": product_reference.id,
                        "variantId": variant_reference.id,
                        "type": "receive",
                        "quantity": initial_stock,
                        "stockBefore": 0,
                        "stockAfter": initial_stock,
                        "orderId": None,
                        "reference": "Initial product stock",
                        "reason": "Product created",
                        "performedBy": uid,
                        "createdAt": timestamp,
                    },
                )

        current_transaction.set(
            product_reference,
            {
                "name": product["name"],
                "slug": slugify(product["name"]) or product_reference.id.lower(),
                "colourName": product["colourName"],
                "colourHex": product["colourHex"],
                "productType": product["productType"],
                "productSize": product["productSize"],
                "categoryId": product["categoryId"],
                "categoryName": category_name,
                "brand": product["brand"],
                "supplierId": product["supplierId"],
                "description": product["description"],
                "aiDescription": product["aiDescription"],
                "taxCategory": product["taxCategory"],
                "hasSizes": product["hasSizes"],
                "skuPrefix": product["skuPrefix"],
                "costPriceMinor": product["costPriceMinor"],
                "sellingPriceMinor": product["sellingPriceMinor"],
                "compareAtPriceMinor": product["compareAtPriceMinor"],
                "weightGrams": product["weightGrams"],
                "lowStockThreshold": product["lowStockThreshold"],
                "warrantyPeriodMonths": product["warrantyPeriodMonths"],
                "warrantyNotes": product["warrantyNotes"],
                "totalStock": total_stock,
                "reservedStock": 0,
                "availableStock": total_stock,
                "stockStatus": overall_status,
                "approvedReviewCount": 0,
                "media": product["media"],
                "primaryMediaPath": (
                    product["media"][0].get("path", "") if product["media"] else ""
                ),
                "variantSummaries": variant_summaries,
                "status": "active",
                "shortCode": short_code,
                "createdBy": uid,
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )

        for registry_reference, registry_type, registry_value in registry_references:
            current_transaction.set(
                registry_reference,
                {
                    "type": registry_type,
                    "value": registry_value,
                    "productId": product_reference.id,
                    "createdAt": timestamp,
                },
            )

        current_transaction.set(
            short_link_reference,
            {
                "type": "product",
                "businessId": business_id,
                "productId": product_reference.id,
                "status": "active",
                "createdAt": timestamp,
            },
        )

    create_in_transaction(transaction)
    return get_product(database, business_id, product_reference.id)


def update_product(database, business_id, product_id, payload):
    """Update shared product information without changing SKU or stock history."""
    business_reference = database.collection("businesses").document(business_id)
    product_reference = business_reference.collection("products").document(product_id)
    product_snapshot = product_reference.get()

    if not product_snapshot.exists:
        raise ApiError("product_not_found", "Product not found.", 404)

    current_product = product_snapshot.to_dict()
    changes = {"updatedAt": firestore.SERVER_TIMESTAMP}

    try:
        if "name" in payload:
            changes["name"] = required_text(payload.get("name"), "Product name", 160)
            changes["slug"] = slugify(changes["name"]) or product_id.lower()
        if "colourName" in payload:
            changes["colourName"] = optional_text(payload.get("colourName"), 80)
        if "colourHex" in payload:
            changes["colourHex"] = optional_text(payload.get("colourHex"), 20)
        if "productType" in payload:
            changes["productType"] = optional_text(payload.get("productType"), 100)
        if "productSize" in payload:
            changes["productSize"] = optional_text(payload.get("productSize"), 80)
        if "brand" in payload:
            changes["brand"] = optional_text(payload.get("brand"), 100)
        if "supplierId" in payload:
            changes["supplierId"] = optional_text(payload.get("supplierId"), 120)
        if "description" in payload:
            changes["description"] = optional_text(payload.get("description"), 4000)
        if "aiDescription" in payload:
            changes["aiDescription"] = optional_text(payload.get("aiDescription"), 4000)
        if "taxCategory" in payload:
            changes["taxCategory"] = optional_text(payload.get("taxCategory"), 60)
        if "costPrice" in payload:
            changes["costPriceMinor"] = money_to_minor_units(
                payload.get("costPrice"),
                "Cost price",
            )
        if "sellingPrice" in payload:
            changes["sellingPriceMinor"] = money_to_minor_units(
                payload.get("sellingPrice"),
                "Selling price",
                allow_zero=False,
            )
        if "compareAtPrice" in payload:
            changes["compareAtPriceMinor"] = money_to_minor_units(
                payload.get("compareAtPrice"),
                "Compare-at price",
            )
        if "weightKg" in payload:
            changes["weightGrams"] = kilograms_to_grams(payload.get("weightKg"))
        if "lowStockThreshold" in payload:
            changes["lowStockThreshold"] = non_negative_integer(
                payload.get("lowStockThreshold"),
                "Low-stock threshold",
            )
        if "warrantyPeriodMonths" in payload:
            changes["warrantyPeriodMonths"] = non_negative_integer(payload.get("warrantyPeriodMonths"), "Warranty period")
        if "warrantyNotes" in payload:
            changes["warrantyNotes"] = optional_text(payload.get("warrantyNotes"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if "status" in payload:
        if payload.get("status") not in {"active", "archived", "draft"}:
            raise ApiError(
                "validation_error",
                "Product status must be active, draft or archived.",
                422,
            )
        changes["status"] = payload["status"]

    if "categoryId" in payload:
        try:
            category_id = optional_text(payload.get("categoryId"), 120)
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error
        if category_id:
            category_snapshot = business_reference.collection("categories").document(
                category_id,
            ).get()

            if (
                not category_snapshot.exists
                or category_snapshot.to_dict().get("status") != "active"
            ):
                raise ApiError("invalid_category", "Choose an active category.", 422)

            changes["categoryId"] = category_id
            changes["categoryName"] = category_snapshot.to_dict().get("name", "")
        else:
            changes["categoryId"] = ""
            changes["categoryName"] = "Uncategorized"

    variants = list(
        business_reference.collection("productVariants")
        .where(filter=FieldFilter("productId", "==", product_id))
        .stream(),
    )
    batch = database.batch()

    if "variants" in payload:
        raw_variants = payload.get("variants")
        if not isinstance(raw_variants, list) or not raw_variants:
            raise ApiError("validation_error", "At least one variant is required.", 422)
        existing_by_id = {snapshot.id: snapshot for snapshot in variants}
        retained_ids = set()
        seen_skus = set()
        seen_barcodes = set()
        summaries = []
        total_stock = 0
        total_reserved = 0
        for index, raw_variant in enumerate(raw_variants, start=1):
            try:
                variant_id = optional_text(raw_variant.get("id"), 120)
                size = optional_text(raw_variant.get("size"), 40)
                sku = required_text(raw_variant.get("sku"), f"SKU in row {index}", 80).upper()
                barcode = required_text(raw_variant.get("barcode"), f"Barcode in row {index}", 80)
                stock_on_hand = non_negative_integer(raw_variant.get("stock", 0), f"Stock in row {index}")
                cost_minor = money_to_minor_units(raw_variant.get("costPrice", payload.get("costPrice")), f"Cost price in row {index}")
                selling_minor = money_to_minor_units(raw_variant.get("sellingPrice", payload.get("sellingPrice")), f"Selling price in row {index}", allow_zero=False)
            except ValueError as error:
                raise ApiError("validation_error", str(error), 422) from error
            normalized_sku = normalize_registry_key(sku)
            normalized_barcode = normalize_registry_key(barcode)
            if normalized_sku in seen_skus or normalized_barcode in seen_barcodes:
                raise ApiError("duplicate_variant_identifier", "Variant SKUs and barcodes must be unique.", 422)
            seen_skus.add(normalized_sku)
            seen_barcodes.add(normalized_barcode)

            snapshot = existing_by_id.get(variant_id)
            if snapshot:
                current = snapshot.to_dict()
                reserved = current.get("stockReserved", 0)
                if stock_on_hand < reserved:
                    raise ApiError("insufficient_adjustable_stock", "Variant stock cannot be below reserved stock.", 409)
                reference = snapshot.reference
                retained_ids.add(snapshot.id)
                image_url = current.get("imageUrl", "")
                created_at = current.get("createdAt")
            else:
                current = {}
                reserved = 0
                reference = business_reference.collection("productVariants").document()
                variant_id = reference.id
                image_url = raw_variant.get("imageUrl", "")
                created_at = firestore.SERVER_TIMESTAMP
            sku_registry = business_reference.collection("skuRegistry").document(normalize_registry_key(sku))
            barcode_registry = business_reference.collection("barcodeRegistry").document(normalize_registry_key(barcode))
            for registry, registry_type, value in ((sku_registry, "sku", sku), (barcode_registry, "barcode", barcode)):
                registry_snapshot = registry.get()
                if registry_snapshot.exists and registry_snapshot.to_dict().get("productId") != product_id:
                    raise ApiError(f"{registry_type}_already_exists", f"{registry_type.upper()} {value} is already in use.", 409)
                batch.set(registry, {"type": registry_type, "value": value, "productId": product_id, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
            if current.get("sku") and normalize_registry_key(current["sku"]) != normalize_registry_key(sku):
                batch.delete(business_reference.collection("skuRegistry").document(normalize_registry_key(current["sku"])))
            if current.get("barcode") and normalize_registry_key(current["barcode"]) != normalize_registry_key(barcode):
                batch.delete(business_reference.collection("barcodeRegistry").document(normalize_registry_key(current["barcode"])))
            available = stock_on_hand - reserved
            status = stock_status(available, changes.get("lowStockThreshold", current_product.get("lowStockThreshold", 5)))
            variant_data = {"productId": product_id, "size": size, "sku": sku, "barcode": barcode, "costPriceMinor": cost_minor, "sellingPriceMinor": selling_minor, "weightGrams": changes.get("weightGrams", current_product.get("weightGrams", 0)), "stockOnHand": stock_on_hand, "stockReserved": reserved, "stockAvailable": available, "stockStatus": status, "status": "active", "imageUrl": image_url, "createdAt": created_at, "updatedAt": firestore.SERVER_TIMESTAMP}
            batch.set(reference, variant_data, merge=True)
            summaries.append({"id": variant_id, "size": size, "sku": sku, "barcode": barcode, "stockOnHand": stock_on_hand, "stockReserved": reserved, "stockAvailable": available, "stockStatus": status, "costPriceMinor": cost_minor, "sellingPriceMinor": selling_minor, "imageUrl": image_url})
            total_stock += stock_on_hand
            total_reserved += reserved

        for variant_id, snapshot in existing_by_id.items():
            if variant_id not in retained_ids and snapshot.to_dict().get("stockReserved", 0) > 0:
                raise ApiError("variant_in_use", "A variant reserved by an order cannot be removed.", 409)
            if variant_id not in retained_ids:
                old = snapshot.to_dict()
                if old.get("sku"):
                    batch.delete(business_reference.collection("skuRegistry").document(normalize_registry_key(old["sku"])))
                if old.get("barcode"):
                    batch.delete(business_reference.collection("barcodeRegistry").document(normalize_registry_key(old["barcode"])))
                batch.delete(snapshot.reference)
        available_stock = total_stock - total_reserved
        changes.update({"hasSizes": payload.get("hasSizes") is True, "variantSummaries": summaries, "totalStock": total_stock, "reservedStock": total_reserved, "availableStock": available_stock, "stockStatus": stock_status(available_stock, changes.get("lowStockThreshold", current_product.get("lowStockThreshold", 5)))})
    shared_variant_changes = {
        field: changes[field]
        for field in ("costPriceMinor", "sellingPriceMinor", "weightGrams")
        if field in changes and (field == "weightGrams" or "variants" not in payload)
    }

    if "lowStockThreshold" in changes:
        threshold = changes["lowStockThreshold"]
        changes["stockStatus"] = stock_status(
            current_product.get("availableStock", 0),
            threshold,
        )
        if "variants" not in payload:
            changes["variantSummaries"] = [
            {
                **summary,
                "stockStatus": stock_status(
                    summary.get("stockAvailable", 0),
                    threshold,
                ),
            }
            for summary in current_product.get("variantSummaries", [])
            ]

    batch.update(product_reference, changes)

    if shared_variant_changes or "lowStockThreshold" in changes:
        timestamp = firestore.SERVER_TIMESTAMP

        for variant in variants:
            variant_changes = {
                **shared_variant_changes,
                "updatedAt": timestamp,
            }

            if "lowStockThreshold" in changes:
                variant_changes["stockStatus"] = stock_status(
                    variant.to_dict().get("stockAvailable", 0),
                    changes["lowStockThreshold"],
                )

            batch.update(variant.reference, variant_changes)

    batch.commit()
    return get_product(database, business_id, product_id)


def adjust_variant_stock(
    database,
    business_id,
    product_id,
    variant_id,
    uid,
    payload,
):
    """Adjust one variant's stock and record the complete audit transaction."""
    try:
        quantity_change = integer_value(payload.get("quantityChange"), "Quantity change")
        reason = required_text(payload.get("reason"), "Adjustment reason", 300)
        reference = optional_text(payload.get("reference"), 200)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if quantity_change == 0:
        raise ApiError(
            "validation_error",
            "Quantity change cannot be zero.",
            422,
        )

    business_reference = database.collection("businesses").document(business_id)
    product_reference = business_reference.collection("products").document(product_id)
    variant_reference = business_reference.collection("productVariants").document(
        variant_id,
    )
    transaction_reference = business_reference.collection(
        "inventoryTransactions",
    ).document()
    transaction = database.transaction()

    @google_firestore.transactional
    def adjust_in_transaction(current_transaction):
        product_snapshot = product_reference.get(transaction=current_transaction)
        variant_snapshot = variant_reference.get(transaction=current_transaction)

        if not product_snapshot.exists:
            raise ApiError("product_not_found", "Product not found.", 404)
        if not variant_snapshot.exists:
            raise ApiError("variant_not_found", "Product size/SKU not found.", 404)

        product = product_snapshot.to_dict()
        variant = variant_snapshot.to_dict()

        if variant.get("productId") != product_id:
            raise ApiError("variant_not_found", "Product size/SKU not found.", 404)

        stock_before = variant.get("stockOnHand", 0)
        stock_after = stock_before + quantity_change
        reserved = variant.get("stockReserved", 0)

        if stock_after < reserved:
            raise ApiError(
                "insufficient_adjustable_stock",
                "Stock cannot be reduced below the quantity reserved by orders.",
                409,
            )

        available_after = stock_after - reserved
        threshold = product.get("lowStockThreshold", 0)
        new_variant_status = stock_status(available_after, threshold)
        product_stock_after = product.get("totalStock", 0) + quantity_change
        product_available_after = product.get("availableStock", 0) + quantity_change
        summaries = []

        for summary in product.get("variantSummaries", []):
            if summary.get("id") == variant_id:
                summaries.append(
                    {
                        **summary,
                        "stockOnHand": stock_after,
                        "stockAvailable": available_after,
                        "stockStatus": new_variant_status,
                    },
                )
            else:
                summaries.append(summary)

        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.update(
            variant_reference,
            {
                "stockOnHand": stock_after,
                "stockAvailable": available_after,
                "stockStatus": new_variant_status,
                "updatedAt": timestamp,
            },
        )
        current_transaction.update(
            product_reference,
            {
                "totalStock": product_stock_after,
                "availableStock": product_available_after,
                "stockStatus": stock_status(product_available_after, threshold),
                "variantSummaries": summaries,
                "updatedAt": timestamp,
            },
        )
        current_transaction.set(
            transaction_reference,
            {
                "productId": product_id,
                "variantId": variant_id,
                "type": "adjust",
                "quantity": quantity_change,
                "stockBefore": stock_before,
                "stockAfter": stock_after,
                "orderId": None,
                "reference": reference,
                "reason": reason,
                "performedBy": uid,
                "createdAt": timestamp,
            },
        )

    adjust_in_transaction(transaction)
    return get_product(database, business_id, product_id)
