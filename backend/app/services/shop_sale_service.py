from collections import defaultdict

from firebase_admin import firestore
from google.cloud import firestore as google_firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.numbers import money_to_minor_units, non_negative_integer
from app.services.product_service import stock_status
from app.services.text import optional_text, required_text


def _validate_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items:
        raise ApiError("validation_error", "Add at least one sale item.", 422)

    quantities = defaultdict(int)
    for index, item in enumerate(raw_items, start=1):
        try:
            variant_id = required_text(item.get("variantId"), f"Variant in item {index}", 120)
            quantity = non_negative_integer(item.get("quantity"), f"Quantity in item {index}")
        except (AttributeError, ValueError) as error:
            raise ApiError("validation_error", str(error), 422) from error
        if quantity < 1:
            raise ApiError("validation_error", "Sale quantities must be greater than zero.", 422)
        quantities[variant_id] += quantity
    return [{"variantId": key, "quantity": value} for key, value in quantities.items()]


def list_shop_sales(database, business_id, search=None, date_from=None, date_to=None):
    collection = database.collection("businesses").document(business_id).collection("shopSales")
    sales = [
        serialize_snapshot(snapshot)
        for snapshot in collection.order_by("createdAt", direction="DESCENDING").limit(300).stream()
    ]
    if date_from:
        sales = [sale for sale in sales if str(sale.get("createdAt", ""))[:10] >= date_from]
    if date_to:
        sales = [sale for sale in sales if str(sale.get("createdAt", ""))[:10] <= date_to]
    if search:
        needle = search.strip().casefold()
        sales = [
            sale for sale in sales
            if needle in sale.get("saleNumber", "").casefold()
            or needle in sale.get("customerName", "").casefold()
            or needle in sale.get("phoneNumber", "")
            or any(
                needle in item.get("name", "").casefold()
                or needle in item.get("sku", "").casefold()
                or needle in item.get("barcode", "").casefold()
                for item in sale.get("items", [])
            )
        ]
    return sales


def create_shop_sale(database, business_id, uid, payload):
    try:
        items_requested = _validate_items(payload.get("items"))
        discount_minor = money_to_minor_units(payload.get("discountAmount", 0), "Discount")
        customer_name = optional_text(payload.get("customerName"), 160)
        phone_number = optional_text(payload.get("phoneNumber"), 30)
        payment_method = optional_text(payload.get("paymentMethod"), 30) or "cash"
        note = optional_text(payload.get("note"), 1000)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if payment_method not in {"cash", "card", "bank-transfer"}:
        raise ApiError("validation_error", "Choose a valid shop payment method.", 422)

    business_ref = database.collection("businesses").document(business_id)
    sale_ref = business_ref.collection("shopSales").document()
    transaction = database.transaction()

    @google_firestore.transactional
    def save(current_transaction):
        business_snapshot = business_ref.get(transaction=current_transaction)
        if not business_snapshot.exists:
            raise ApiError("business_not_found", "Business not found.", 404)

        variant_snapshots = {}
        product_snapshots = {}
        for requested in items_requested:
            variant_ref = business_ref.collection("productVariants").document(requested["variantId"])
            variant_snapshot = variant_ref.get(transaction=current_transaction)
            if not variant_snapshot.exists:
                raise ApiError("variant_not_found", "A selected product option is unavailable.", 404)
            variant = variant_snapshot.to_dict()
            if variant.get("status") != "active":
                raise ApiError("inactive_variant", "A selected product option is inactive.", 409)
            if variant.get("stockAvailable", 0) < requested["quantity"]:
                raise ApiError(
                    "insufficient_stock",
                    f"Only {variant.get('stockAvailable', 0)} unit(s) are available for {variant.get('sku', 'this item')}.",
                    409,
                )
            variant_snapshots[requested["variantId"]] = variant_snapshot
            product_id = variant.get("productId")
            if product_id not in product_snapshots:
                product_snapshot = business_ref.collection("products").document(product_id).get(transaction=current_transaction)
                if not product_snapshot.exists:
                    raise ApiError("product_not_found", "A selected product is unavailable.", 404)
                product_snapshots[product_id] = product_snapshot

        business = business_snapshot.to_dict()
        sequence = business.get("nextShopSaleSequence", 1)
        sale_number = f"POS-{sequence:06d}"
        timestamp = firestore.SERVER_TIMESTAMP
        sale_items = []
        subtotal_minor = 0
        quantity_by_product = defaultdict(int)

        for requested in items_requested:
            variant_snapshot = variant_snapshots[requested["variantId"]]
            variant = variant_snapshot.to_dict()
            product_snapshot = product_snapshots[variant["productId"]]
            product = product_snapshot.to_dict()
            quantity = requested["quantity"]
            price_minor = variant.get("sellingPriceMinor", product.get("sellingPriceMinor", 0))
            line_total_minor = price_minor * quantity
            media = product.get("media", [])
            image_url = variant.get("imageUrl") or (media[0].get("url", "") if media else "")
            sale_items.append({
                "productId": variant["productId"],
                "variantId": variant_snapshot.id,
                "name": product.get("name", "Product"),
                "size": variant.get("size", ""),
                "sku": variant.get("sku", ""),
                "barcode": variant.get("barcode", ""),
                "quantity": quantity,
                "unitPriceMinor": price_minor,
                "unitCostMinor": variant.get("costPriceMinor", 0),
                "lineTotalMinor": line_total_minor,
                "mediaUrl": image_url,
                "warrantyMonths": product.get("warrantyMonths", 0),
            })
            subtotal_minor += line_total_minor
            quantity_by_product[variant["productId"]] += quantity

            on_hand_before = variant.get("stockOnHand", 0)
            available_before = variant.get("stockAvailable", 0)
            on_hand_after = on_hand_before - quantity
            available_after = available_before - quantity
            threshold = product.get("lowStockThreshold", 0)
            current_transaction.update(variant_snapshot.reference, {
                "stockOnHand": on_hand_after,
                "stockAvailable": available_after,
                "stockStatus": stock_status(available_after, threshold),
                "updatedAt": timestamp,
            })
            current_transaction.set(business_ref.collection("inventoryTransactions").document(), {
                "productId": variant["productId"], "variantId": variant_snapshot.id,
                "type": "shop-sale", "quantity": quantity,
                "stockBefore": on_hand_before, "stockAfter": on_hand_after,
                "shopSaleId": sale_ref.id, "reference": sale_number,
                "reason": "Physical shop sale", "performedBy": uid, "createdAt": timestamp,
            })

        if discount_minor > subtotal_minor:
            raise ApiError("invalid_discount", "Discount cannot exceed the subtotal.", 422)

        for product_id, quantity in quantity_by_product.items():
            product_snapshot = product_snapshots[product_id]
            product = product_snapshot.to_dict()
            sold_by_variant = {
                item["variantId"]: item["quantity"]
                for item in sale_items if item["productId"] == product_id
            }
            summaries = []
            for summary in product.get("variantSummaries", []):
                sold = sold_by_variant.get(summary.get("id"), 0)
                if not sold:
                    summaries.append(summary)
                    continue
                available = summary.get("stockAvailable", 0) - sold
                summaries.append({**summary, "stockOnHand": summary.get("stockOnHand", 0) - sold,
                                  "stockAvailable": available,
                                  "stockStatus": stock_status(available, product.get("lowStockThreshold", 0))})
            available_stock = product.get("availableStock", 0) - quantity
            current_transaction.update(product_snapshot.reference, {
                "totalStock": product.get("totalStock", 0) - quantity,
                "availableStock": available_stock,
                "variantSummaries": summaries,
                "stockStatus": stock_status(available_stock, product.get("lowStockThreshold", 0)),
                "updatedAt": timestamp,
            })

        total_minor = subtotal_minor - discount_minor
        current_transaction.set(sale_ref, {
            "saleNumber": sale_number, "source": "physical-shop", "status": "completed",
            "customerName": customer_name, "phoneNumber": phone_number,
            "items": sale_items, "itemCount": sum(item["quantity"] for item in sale_items),
            "subtotalMinor": subtotal_minor, "discountTotalMinor": discount_minor,
            "totalAmountMinor": total_minor, "paymentMethod": payment_method,
            "note": note, "createdBy": uid, "createdAt": timestamp, "updatedAt": timestamp,
        })
        current_transaction.update(business_ref, {"nextShopSaleSequence": sequence + 1, "updatedAt": timestamp})

    save(transaction)
    return serialize_snapshot(sale_ref.get())


def delete_shop_sale(database, business_id, sale_id, uid):
    business_ref = database.collection("businesses").document(business_id)
    sale_ref = business_ref.collection("shopSales").document(sale_id)
    transaction = database.transaction()

    @google_firestore.transactional
    def reverse(current_transaction):
        sale_snapshot = sale_ref.get(transaction=current_transaction)
        if not sale_snapshot.exists:
            raise ApiError("shop_sale_not_found", "Shop sale not found.", 404)
        sale = sale_snapshot.to_dict()
        if sale.get("status") == "voided":
            raise ApiError("shop_sale_already_voided", "This shop sale was already deleted.", 409)

        variant_snapshots = {}
        product_snapshots = {}
        for item in sale.get("items", []):
            variant_snapshot = business_ref.collection("productVariants").document(item["variantId"]).get(transaction=current_transaction)
            product_snapshot = business_ref.collection("products").document(item["productId"]).get(transaction=current_transaction)
            if not variant_snapshot.exists or not product_snapshot.exists:
                raise ApiError("stock_record_missing", "Stock cannot be restored because a product record is missing.", 409)
            variant_snapshots[item["variantId"]] = variant_snapshot
            product_snapshots[item["productId"]] = product_snapshot

        timestamp = firestore.SERVER_TIMESTAMP
        quantity_by_product = defaultdict(int)
        for item in sale.get("items", []):
            quantity = item["quantity"]
            variant_snapshot = variant_snapshots[item["variantId"]]
            variant = variant_snapshot.to_dict()
            product = product_snapshots[item["productId"]].to_dict()
            on_hand = variant.get("stockOnHand", 0) + quantity
            available = variant.get("stockAvailable", 0) + quantity
            current_transaction.update(variant_snapshot.reference, {
                "stockOnHand": on_hand, "stockAvailable": available,
                "stockStatus": stock_status(available, product.get("lowStockThreshold", 0)), "updatedAt": timestamp,
            })
            current_transaction.set(business_ref.collection("inventoryTransactions").document(), {
                "productId": item["productId"], "variantId": item["variantId"],
                "type": "shop-sale-reversal", "quantity": quantity,
                "stockBefore": on_hand - quantity, "stockAfter": on_hand,
                "shopSaleId": sale_id, "reference": sale.get("saleNumber", ""),
                "reason": "Physical shop sale deleted", "performedBy": uid, "createdAt": timestamp,
            })
            quantity_by_product[item["productId"]] += quantity

        for product_id, quantity in quantity_by_product.items():
            product_snapshot = product_snapshots[product_id]
            product = product_snapshot.to_dict()
            restored = {item["variantId"]: item["quantity"] for item in sale["items"] if item["productId"] == product_id}
            summaries = []
            for summary in product.get("variantSummaries", []):
                amount = restored.get(summary.get("id"), 0)
                available = summary.get("stockAvailable", 0) + amount
                summaries.append({**summary, "stockOnHand": summary.get("stockOnHand", 0) + amount,
                                  "stockAvailable": available,
                                  "stockStatus": stock_status(available, product.get("lowStockThreshold", 0))})
            available_stock = product.get("availableStock", 0) + quantity
            current_transaction.update(product_snapshot.reference, {
                "totalStock": product.get("totalStock", 0) + quantity,
                "availableStock": available_stock, "variantSummaries": summaries,
                "stockStatus": stock_status(available_stock, product.get("lowStockThreshold", 0)), "updatedAt": timestamp,
            })
        current_transaction.update(sale_ref, {"status": "voided", "voidedBy": uid, "voidedAt": timestamp, "updatedAt": timestamp})

    reverse(transaction)
    return serialize_snapshot(sale_ref.get())


def list_warranty_claims(database, business_id):
    collection = database.collection("businesses").document(business_id).collection("warrantyClaims")
    return [serialize_snapshot(snapshot) for snapshot in collection.order_by("createdAt", direction="DESCENDING").limit(300).stream()]


def create_warranty_claim(database, business_id, uid, payload):
    try:
        source_type = required_text(payload.get("sourceType"), "Sale type", 30)
        source_id = required_text(payload.get("sourceId"), "Order or sale", 120)
        variant_id = required_text(payload.get("variantId"), "Item", 120)
        reason = required_text(payload.get("reason"), "Warranty reason", 300)
        details = optional_text(payload.get("details"), 1500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error
    collection_name = "orders" if source_type == "online-order" else "shopSales" if source_type == "shop-sale" else None
    if not collection_name:
        raise ApiError("validation_error", "Choose a valid warranty sale type.", 422)
    business_ref = database.collection("businesses").document(business_id)
    source_snapshot = business_ref.collection(collection_name).document(source_id).get()
    if not source_snapshot.exists:
        raise ApiError("sale_not_found", "The original order or shop sale was not found.", 404)
    source = source_snapshot.to_dict()
    item = next((record for record in source.get("items", []) if record.get("variantId") == variant_id), None)
    if not item:
        raise ApiError("item_not_found", "The selected item is not part of this sale.", 422)
    business = business_ref.get().to_dict() or {}
    sequence = business.get("nextWarrantyClaimSequence", 1)
    claim_ref = business_ref.collection("warrantyClaims").document()
    timestamp = firestore.SERVER_TIMESTAMP
    claim_ref.set({
        "claimNumber": f"WC-{sequence:06d}", "sourceType": source_type, "sourceId": source_id,
        "sourceNumber": source.get("orderNumber") or source.get("saleNumber"),
        "customerName": source.get("customerSnapshot", {}).get("name") or source.get("customerName", "Walk-in customer"),
        "phoneNumber": source.get("customerSnapshot", {}).get("phoneNumber") or source.get("phoneNumber", ""),
        "item": item, "reason": reason, "details": details, "status": "open",
        "createdBy": uid, "createdAt": timestamp, "updatedAt": timestamp,
    })
    business_ref.update({"nextWarrantyClaimSequence": sequence + 1, "updatedAt": timestamp})
    return serialize_snapshot(claim_ref.get())
