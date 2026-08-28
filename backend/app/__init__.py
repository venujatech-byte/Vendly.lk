from flask import Flask, jsonify
from flask_cors import CORS

from app.api.businesses import businesses_blueprint
from app.api.business_assistant import business_assistant_blueprint
from app.api.billing import billing_blueprint
from app.api.analytics import analytics_blueprint
from app.api.categories import categories_blueprint
from app.api.customers import customers_blueprint
from app.api.couriers import couriers_blueprint
from app.api.health import health_blueprint
from app.api.me import me_blueprint
from app.api.members import members_blueprint
from app.api.messages import messages_blueprint
from app.api.orders import orders_blueprint
from app.api.operations import operations_blueprint
from app.api.products import products_blueprint
from app.api.public import public_blueprint
from app.api.reviews import reviews_blueprint
from app.api.search import search_blueprint
from app.api.shop_sales import shop_sales_blueprint
from app.core.config import Settings
from app.core.errors import ApiError, api_error_payload
from app.core.firebase import initialize_firebase
from app.core.rate_limit import limiter


def create_app(test_config=None):
    """Create and configure one Vendly Flask application instance."""
    settings = Settings.from_environment()

    app = Flask(__name__)
    app.config.from_mapping(
        DEBUG=settings.debug,
        JSON_SORT_KEYS=False,
        FIREBASE_PROJECT_ID=settings.firebase_project_id,
        FIREBASE_STORAGE_BUCKET=settings.firebase_storage_bucket,
        CLOUDINARY_CLOUD_NAME=settings.cloudinary_cloud_name,
        CLOUDINARY_API_KEY=settings.cloudinary_api_key,
        CLOUDINARY_API_SECRET=settings.cloudinary_api_secret,
        MAX_CONTENT_LENGTH=60 * 1024 * 1024,
        AI_PROVIDER=settings.ai_provider,
        AI_API_KEY=settings.ai_api_key,
        AI_MODEL=settings.ai_model,
        AI_API_BASE_URL=settings.ai_api_base_url,
        AI_FAST_MODEL=settings.ai_fast_model,
        AI_FALLBACK_PROVIDER=settings.ai_fallback_provider,
        AI_FALLBACK_API_KEY=settings.ai_fallback_api_key,
        AI_FALLBACK_MODEL=settings.ai_fallback_model,
        AI_FALLBACK_API_BASE_URL=settings.ai_fallback_api_base_url,
        AI_TIMEOUT_SECONDS=settings.ai_timeout_seconds,
        RATELIMIT_STORAGE_URI=settings.rate_limit_storage_uri,
        RATELIMIT_HEADERS_ENABLED=True,
        RATELIMIT_ENABLED=True,
        PAYHERE_SANDBOX=settings.payhere_sandbox,
        PAYHERE_MERCHANT_ID=settings.payhere_merchant_id,
        PAYHERE_MERCHANT_SECRET=settings.payhere_merchant_secret,
        FRONTEND_PUBLIC_URL=settings.frontend_public_url,
        BACKEND_PUBLIC_URL=settings.backend_public_url,
    )

    if test_config:
        app.config.update(test_config)

    if app.config.get("TESTING"):
        app.config["RATELIMIT_ENABLED"] = False

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": settings.frontend_origins,
                "allow_headers": [
                    "Authorization",
                    "Content-Type",
                    "X-Chat-Session-Token",
                ],
                "methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                "expose_headers": [
                    "Content-Disposition",
                    "X-RateLimit-Limit",
                    "X-RateLimit-Remaining",
                    "X-RateLimit-Reset",
                ],
            },
        },
    )

    initialize_firebase(settings)
    limiter.init_app(app)

    app.register_blueprint(health_blueprint)
    app.register_blueprint(analytics_blueprint)
    app.register_blueprint(me_blueprint)
    app.register_blueprint(members_blueprint)
    app.register_blueprint(messages_blueprint)
    app.register_blueprint(businesses_blueprint)
    app.register_blueprint(business_assistant_blueprint)
    app.register_blueprint(billing_blueprint)
    app.register_blueprint(categories_blueprint)
    app.register_blueprint(customers_blueprint)
    app.register_blueprint(couriers_blueprint)
    app.register_blueprint(products_blueprint)
    app.register_blueprint(orders_blueprint)
    app.register_blueprint(operations_blueprint)
    app.register_blueprint(public_blueprint)
    app.register_blueprint(reviews_blueprint)
    app.register_blueprint(search_blueprint)
    app.register_blueprint(shop_sales_blueprint)

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify(api_error_payload(error)), error.status_code

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": {"code": "not_found", "message": "Route not found."}}), 404

    @app.errorhandler(413)
    def handle_payload_too_large(_error):
        return jsonify(
            {
                "error": {
                    "code": "payload_too_large",
                    "message": "The uploaded request is too large.",
                },
            },
        ), 413

    @app.errorhandler(429)
    def handle_rate_limit(_error):
        return jsonify(
            {
                "error": {
                    "code": "rate_limit_exceeded",
                    "message": "Too many requests. Please wait and try again.",
                },
            },
        ), 429

    @app.errorhandler(500)
    def handle_server_error(_error):
        return jsonify(
            {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected server error occurred.",
                },
            },
        ), 500

    return app
