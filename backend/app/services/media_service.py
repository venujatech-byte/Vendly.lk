import hashlib
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx
from firebase_admin import firestore
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.core.errors import ApiError
from app.services.product_service import get_product


ALLOWED_MEDIA_TYPES = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
CLOUDINARY_UPLOAD_URL = "https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload"


def file_size(upload: FileStorage):
    current_position = upload.stream.tell()
    upload.stream.seek(0, 2)
    size = upload.stream.tell()
    upload.stream.seek(current_position)
    return size


def validate_media(upload: FileStorage):
    media_type = ALLOWED_MEDIA_TYPES.get(upload.mimetype)

    if not media_type:
        raise ApiError(
            "unsupported_media_type",
            f"{upload.filename or 'File'} is not a supported image or video.",
            422,
        )

    size = file_size(upload)
    maximum_size = MAX_IMAGE_BYTES if media_type == "image" else MAX_VIDEO_BYTES

    if size == 0:
        raise ApiError("empty_media_file", "An uploaded media file is empty.", 422)

    if size > maximum_size:
        maximum_megabytes = maximum_size // (1024 * 1024)
        raise ApiError(
            "media_file_too_large",
            f"{upload.filename} must be {maximum_megabytes} MB or smaller.",
            413,
        )

    return media_type, size


def firebase_download_url(bucket_name, object_path, download_token):
    encoded_path = quote(object_path, safe="")
    return (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/"
        f"{encoded_path}?alt=media&token={download_token}"
    )


def cloudinary_signature(parameters, api_secret):
    """Create Cloudinary's SHA-1 signature without exposing the API secret."""
    signed_values = "&".join(
        f"{key}={parameters[key]}" for key in sorted(parameters) if parameters[key] is not None
    )
    return hashlib.sha1(f"{signed_values}{api_secret}".encode("utf-8")).hexdigest()


def upload_to_cloudinary(upload, business_id, product_id, cloudinary_config):
    """Upload one file to Cloudinary and return safe metadata for Firestore."""
    cloud_name = cloudinary_config.get("cloud_name")
    api_key = cloudinary_config.get("api_key")
    api_secret = cloudinary_config.get("api_secret")

    if not all((cloud_name, api_key, api_secret)):
        raise ApiError(
            "media_storage_not_configured",
            "Media storage is not configured. Add the Cloudinary credentials to the backend .env file.",
            503,
        )

    media_type, size = validate_media(upload)
    resource_type = "video" if media_type == "video" else "image"
    safe_name = secure_filename(upload.filename or "media")
    public_id = (
        f"businesses/{business_id}/products/{product_id}/"
        f"{uuid4().hex}_{Path(safe_name).stem}"
    )
    timestamp = int(time.time())
    parameters = {"public_id": public_id, "timestamp": timestamp}
    signature = cloudinary_signature(parameters, api_secret)

    upload.stream.seek(0)
    try:
        response = httpx.post(
            CLOUDINARY_UPLOAD_URL.format(
                cloud_name=cloud_name,
                resource_type=resource_type,
            ),
            data={
                "api_key": api_key,
                "public_id": public_id,
                "timestamp": timestamp,
                "signature": signature,
            },
            files={
                "file": (
                    safe_name,
                    upload.stream,
                    upload.mimetype,
                ),
            },
            timeout=60.0,
        )
        response_data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ApiError(
            "cloudinary_upload_failed",
            "The media upload service could not be reached. Please try again.",
            502,
        ) from error

    if response.status_code >= 400:
        message = response_data.get("error", {}).get("message")
        raise ApiError(
            "cloudinary_upload_failed",
            message or "Cloudinary rejected this media file.",
            422 if response.status_code < 500 else 502,
        )

    return {
        "id": response_data.get("asset_id") or response_data.get("public_id"),
        "type": media_type,
        "path": response_data.get("public_id", public_id),
        "url": response_data.get("secure_url") or response_data.get("url", ""),
        "fileName": safe_name,
        "contentType": upload.mimetype,
        "sizeBytes": size,
        "provider": "cloudinary",
    }


def upload_product_media(
    database,
    business_id,
    product_id,
    uid,
    uploads,
    cloudinary_config=None,
):
    """Upload product media and append safe Cloudinary metadata to Firestore."""
    if not uploads:
        raise ApiError("media_required", "Choose at least one image or video.", 422)
    if len(uploads) > 12:
        raise ApiError("too_many_media_files", "Upload no more than 12 files.", 422)

    product = get_product(database, business_id, product_id)
    existing_media = product.get("media", [])

    if len(existing_media) + len(uploads) > 12:
        raise ApiError(
            "too_many_media_files",
            "A product can contain no more than 12 media files.",
            422,
        )

    uploaded_media = []

    for upload in uploads:
        uploaded_media.append(
            upload_to_cloudinary(
                upload,
                business_id,
                product_id,
                cloudinary_config or {},
            ),
        )

    product_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("products")
        .document(product_id)
    )
    changes = {
        "media": firestore.ArrayUnion(uploaded_media),
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }

    if not existing_media and uploaded_media:
        changes["primaryMediaPath"] = uploaded_media[0]["path"]

    product_reference.update(changes)
    return get_product(database, business_id, product_id)


def upload_variant_image(database, business_id, product_id, variant_id, upload, cloudinary_config=None):
    """Upload one variant image and keep its product summary in sync."""
    product = get_product(database, business_id, product_id)
    variant_reference = database.collection("businesses").document(business_id).collection("productVariants").document(variant_id)
    variant_snapshot = variant_reference.get()
    if not variant_snapshot.exists or variant_snapshot.to_dict().get("productId") != product_id:
        raise ApiError("variant_not_found", "Product variant not found.", 404)
    media = upload_to_cloudinary(upload, business_id, product_id, cloudinary_config or {})
    variant_reference.update({"imageUrl": media["url"], "imagePath": media["path"], "updatedAt": firestore.SERVER_TIMESTAMP})
    summaries = [{**summary, "imageUrl": media["url"]} if summary.get("id") == variant_id else summary for summary in product.get("variantSummaries", [])]
    database.collection("businesses").document(business_id).collection("products").document(product_id).update({"variantSummaries": summaries, "updatedAt": firestore.SERVER_TIMESTAMP})
    return get_product(database, business_id, product_id)
