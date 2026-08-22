from flask import Blueprint, g, jsonify, request

from app.core.auth import optional_firebase_user, require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.rate_limit import limiter
from app.core.requests import get_json_object
from app.services.public_catalog_service import get_public_product
from app.services.review_service import (
    create_verified_review,
    list_public_product_reviews,
    list_reviews,
    moderate_review,
)


reviews_blueprint = Blueprint("reviews", __name__, url_prefix="/api/v1")


@reviews_blueprint.get("/public/products/<short_code>/reviews")
@limiter.limit("120 per minute")
def public_product_reviews(short_code):
    catalog = get_public_product(get_firestore_client(), short_code)
    reviews = list_public_product_reviews(
        get_firestore_client(),
        catalog["business"]["id"],
        catalog["product"]["id"],
    )
    return jsonify({"reviews": reviews})


@reviews_blueprint.post("/public/stores/<store_code>/reviews")
# Customers may retry after correcting an order/review, so keep protection
# against abuse without blocking normal testing and genuine submissions.
@limiter.limit("20 per hour")
@optional_firebase_user
def submit_public_review(store_code):
    review = create_verified_review(
        get_firestore_client(),
        store_code,
        get_json_object(),
        customer_uid=(g.current_user or {}).get("uid"),
    )
    return jsonify({"review": review}), 201


@reviews_blueprint.get("/businesses/<business_id>/reviews")
@require_firebase_user
@require_business_member(permission="inventory:read")
def get_reviews(business_id):
    reviews = list_reviews(
        get_firestore_client(),
        business_id,
        status=request.args.get("status"),
        product_id=request.args.get("productId"),
    )
    return jsonify({"reviews": reviews})


@reviews_blueprint.patch("/businesses/<business_id>/reviews/<review_id>")
@require_firebase_user
@require_business_member(permission="reviews:manage")
def update_review(business_id, review_id):
    review = moderate_review(
        get_firestore_client(),
        business_id,
        review_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"review": review})
