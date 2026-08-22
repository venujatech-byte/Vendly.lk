from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.customer_service import normalize_sri_lankan_phone
from app.services.numbers import non_negative_integer
from app.services.public_catalog_service import resolve_short_link
from app.services.text import optional_text, required_text


REVIEW_STATUSES = {"pending", "approved", "rejected"}


def validate_review_payload(payload):
    try:
        order_number = required_text(payload.get("orderNumber"), "Order number", 40).upper()
        phone_value = payload.get("phoneNumber")
        normalized_phone = normalize_sri_lankan_phone(phone_value) if phone_value else ""
        product_id = optional_text(payload.get("productId"), 120)
        review_text = required_text(payload.get("reviewText"), "Review", 2000)
        rating = non_negative_integer(payload.get("rating"), "Rating")
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if rating < 1 or rating > 5:
        raise ApiError("validation_error", "Rating must be between 1 and 5.", 422)

    return {
        "orderNumber": order_number,
        "normalizedPhone": normalized_phone,
        "productId": product_id,
        "reviewText": review_text,
        "rating": rating,
        "media": [
            {
                "type": str(item.get("type", "image")),
                "url": str(item.get("url", "")),
            }
            for item in (payload.get("media") or [])[:4]
            if isinstance(item, dict) and item.get("url")
        ],
    }


def create_verified_review(database, store_code, payload, customer_uid=None):
    review = validate_review_payload(payload)
    link = resolve_short_link(database, store_code, "store")
    business_id = link["businessId"]
    business_reference = database.collection("businesses").document(business_id)
    order_snapshots = list(
        business_reference.collection("orders")
        .where(filter=FieldFilter("orderNumber", "==", review["orderNumber"]))
        .limit(1)
        .stream(),
    )

    if not order_snapshots:
        raise ApiError(
            "review_order_not_found",
            "The order number and phone number could not be verified.",
            404,
        )

    order_snapshot = order_snapshots[0]
    order = order_snapshot.to_dict()

    order_customer_uid = order.get("customerUid") or ""
    if customer_uid and order_customer_uid:
        is_verified_customer = order_customer_uid == customer_uid
    else:
        is_verified_customer = (
            bool(review["normalizedPhone"])
            and order.get("customerSnapshot", {}).get("normalizedPhone")
            == review["normalizedPhone"]
        )
    if not is_verified_customer:
        raise ApiError(
            "review_order_not_found",
            "The order number and phone number could not be verified.",
            404,
        )
    if order.get("fulfilmentStatus") != "delivered":
        raise ApiError(
            "review_order_not_delivered",
            "A review can be submitted after the order is delivered.",
            409,
        )

    product_id = review["productId"]

    if product_id and not any(
        item.get("productId") == product_id for item in order.get("items", [])
    ):
        raise ApiError(
            "review_product_not_in_order",
            "The selected product was not included in this order.",
            403,
        )

    review_type = "product" if product_id else "seller"
    review_id = f"{order_snapshot.id}_{product_id or 'seller'}"
    reference = business_reference.collection("reviews").document(review_id)

    if reference.get().exists:
        raise ApiError(
            "review_already_submitted",
            "A review for this order has already been submitted.",
            409,
        )

    reference.set(
        {
            "type": review_type,
            "orderId": order_snapshot.id,
            "orderNumber": order.get("orderNumber", ""),
            "productId": product_id,
            "customerId": order.get("customerId", ""),
            "customerName": order.get("customerSnapshot", {}).get("name", "Customer"),
            "customerPhone": order.get("customerSnapshot", {}).get(
                "normalizedPhone",
                "",
            ),
            "customerEmail": order.get("customerSnapshot", {}).get("email", ""),
            "rating": review["rating"],
            "reviewText": review["reviewText"],
            "media": review["media"],
            "status": "pending",
            "verifiedPurchase": True,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    return serialize_snapshot(reference.get())


def list_reviews(database, business_id, status=None, product_id=None):
    business_reference = database.collection("businesses").document(business_id)
    snapshots = (
        business_reference
        .collection("reviews")
        .order_by("createdAt", direction="DESCENDING")
        .limit(200)
        .stream()
    )
    reviews = [serialize_snapshot(snapshot) for snapshot in snapshots]

    customer_cache = {}
    product_cache = {}
    enriched_reviews = []
    for review in reviews:
        customer_id = review.get("customerId")
        if customer_id and customer_id not in customer_cache:
            snapshot = business_reference.collection("customers").document(customer_id).get()
            customer_cache[customer_id] = snapshot.to_dict() if snapshot.exists else {}
        customer = customer_cache.get(customer_id, {})

        current_product_id = review.get("productId")
        if current_product_id and current_product_id not in product_cache:
            snapshot = business_reference.collection("products").document(
                current_product_id,
            ).get()
            product_cache[current_product_id] = snapshot.to_dict() if snapshot.exists else {}
        product = product_cache.get(current_product_id, {})
        media = product.get("media") or []
        variants = product.get("variantSummaries") or []
        enriched_reviews.append(
            {
                **review,
                "customerName": review.get("customerName")
                or customer.get("name")
                or "Customer",
                "customerPhone": review.get("customerPhone")
                or customer.get("normalizedPhone", ""),
                "customerEmail": review.get("customerEmail")
                or customer.get("email", ""),
                "productName": product.get("name")
                if current_product_id
                else "Seller review",
                "productImageUrl": media[0].get("url", "") if media else "",
                "productSku": variants[0].get("sku", "") if variants else "",
            }
        )
    reviews = enriched_reviews

    if status:
        reviews = [review for review in reviews if review.get("status") == status]
    if product_id:
        reviews = [review for review in reviews if review.get("productId") == product_id]

    return reviews


def list_public_product_reviews(database, business_id, product_id):
    return [
        {
            "id": review["id"],
            "customerName": review.get("customerName", "Customer"),
            "rating": review.get("rating", 0),
            "reviewText": review.get("reviewText", ""),
            "verifiedPurchase": review.get("verifiedPurchase", False),
            "createdAt": review.get("createdAt"),
        }
        for review in list_reviews(
            database,
            business_id,
            status="approved",
            product_id=product_id,
        )
    ]


def moderate_review(database, business_id, review_id, uid, payload):
    status = str(payload.get("status", "")).strip().lower()

    if status not in {"approved", "rejected"}:
        raise ApiError(
            "validation_error",
            "Review status must be approved or rejected.",
            422,
        )

    business_reference = database.collection("businesses").document(business_id)
    review_reference = business_reference.collection("reviews").document(review_id)
    transaction = database.transaction()

    @google_firestore.transactional
    def update_in_transaction(current_transaction):
        review_snapshot = review_reference.get(transaction=current_transaction)

        if not review_snapshot.exists:
            raise ApiError("review_not_found", "Review not found.", 404)

        review = review_snapshot.to_dict()

        if review.get("status") != "pending":
            raise ApiError(
                "review_already_moderated",
                "This review has already been moderated.",
                409,
            )

        target_reference = business_reference
        if review.get("type") == "product":
            target_reference = business_reference.collection("products").document(
                review.get("productId", ""),
            )

        target_snapshot = target_reference.get(transaction=current_transaction)
        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.update(
            review_reference,
            {
                "status": status,
                "moderatedBy": uid,
                "moderatedAt": timestamp,
                "updatedAt": timestamp,
            },
        )

        if status == "approved" and target_snapshot.exists:
            target = target_snapshot.to_dict()
            count = target.get("approvedReviewCount", 0) + 1
            rating_total = target.get("approvedReviewRatingTotal", 0) + review.get(
                "rating",
                0,
            )
            current_transaction.update(
                target_reference,
                {
                    "approvedReviewCount": count,
                    "approvedReviewRatingTotal": rating_total,
                    "averageRating": round(rating_total / count, 2),
                    "updatedAt": timestamp,
                },
            )

    update_in_transaction(transaction)
    return serialize_snapshot(review_reference.get())
