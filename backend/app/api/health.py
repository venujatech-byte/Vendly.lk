from flask import Blueprint, jsonify


health_blueprint = Blueprint("health", __name__, url_prefix="/api/v1")


@health_blueprint.get("/health")
def health_check():
    """Public liveness endpoint used by local development and hosting."""
    return jsonify({"status": "ok", "service": "vendly-api"})
