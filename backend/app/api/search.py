from flask import Blueprint, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.services.search_service import get_search_revision, global_search, search_scope


search_blueprint = Blueprint("search", __name__, url_prefix="/api/v1")


@search_blueprint.get("/businesses/<business_id>/search")
@require_firebase_user
@require_business_member()
def search_business(business_id):
    response = {
        "results": global_search(
            get_firestore_client(),
            business_id,
            request.args.get("q", ""),
            # Use the membership verified by the server, never client-supplied permissions.
            g.membership,
        ),
    }
    # Bind opted-in cached responses to verified permissions while preserving existing client envelopes.
    if request.args.get("includeScope") == "1":
        response["scope"] = search_scope(g.membership)
    return jsonify(response)


# Verify current tenant membership before allowing reuse of browser-cached search results.
@search_blueprint.get("/businesses/<business_id>/search/cache/version")
@require_firebase_user
@require_business_member()
def search_version(business_id):
    response = jsonify(get_search_revision(get_firestore_client(), business_id, g.membership))
    # Fresh authorization/revision checks must not be reused by an HTTP cache.
    response.headers["Cache-Control"] = "no-store"
    return response
