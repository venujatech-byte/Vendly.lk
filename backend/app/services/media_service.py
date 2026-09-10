import hashlib
import base64
import binascii
import re
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
REVIEW_DATA_URL = re.compile(
    r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\r\n]+)$",
)


DANGEROUS_SCRIPT_SIGNATURES = (
    b"<script",
    b"<?php",
    b"<% ",
    b"<html",
    b"<svg",
    b"javascript:",
    b"data:text/html",
    b"#!/",
)


def validate_magic_bytes(header: bytes, claimed_mimetype: str) -> bool:
    """Verify that binary header matches the claimed mimetype and is not a script."""
    if not header:
        return False

    sample = header[:1024].lower()
    if any(sig in sample for sig in DANGEROUS_SCRIPT_SIGNATURES):
        return False

    if claimed_mimetype == "image/jpeg":
        return header.startswith(b"\xff\xd8\xff")
    if claimed_mimetype == "image/png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if claimed_mimetype == "image/webp":
        return len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if claimed_mimetype == "image/gif":
        return header.startswith(b"GIF87a") or header.startswith(b"GIF89a")
    if claimed_mimetype == "video/mp4":
        return len(header) >= 8 and header[4:8] in (b"ftyp", b"moov", b"wide", b"mdat")
    if claimed_mimetype == "video/quicktime":
        return len(header) >= 8 and header[4:8] in (b"ftyp", b"moov", b"wide", b"mdat", b"free")
    if claimed_mimetype == "video/webm":
        return header.startswith(b"\x1a\x45\xdf\xa3")

    return False


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

    # Verify binary magic bytes to prevent spoofed MIME types or embedded scripts
    current_position = upload.stream.tell()
    upload.stream.seek(0)
    header = upload.stream.read(1024)
    upload.stream.seek(current_position)

    if not validate_magic_bytes(header, upload.mimetype):
        raise ApiError(
            "malicious_or_corrupted_file",
            f"{upload.filename or 'File'} contents do not match the expected format or contain invalid script signatures.",
            422,
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


def upload_chat_data_url(data_url, business_id, session_id, cloudinary_config):
    """Upload one customer-sent chat image, such as a bank slip.

    Shares the review uploader so there is a single Cloudinary path with one
    set of type and size limits; only the destination folder differs.
    """
    return upload_review_data_url(
        data_url,
        business_id,
        session_id,
        cloudinary_config,
        folder="chats",
    )


def upload_review_data_url(
    data_url,
    business_id,
    review_id,
    cloudinary_config,
    folder="reviews",
):
    """Upload one browser-compressed review image to Cloudinary."""
    cloud_name = cloudinary_config.get("cloud_name")
    api_key = cloudinary_config.get("api_key")
    api_secret = cloudinary_config.get("api_secret")
    if not all((cloud_name, api_key, api_secret)):
        raise ApiError(
            "media_storage_not_configured",
            "Review image storage is not configured. Add the Cloudinary credentials to the backend .env file.",
            503,
        )

    match = REVIEW_DATA_URL.fullmatch(str(data_url).strip())
    if not match:
        raise ApiError(
            "unsupported_review_image",
            "Review images must be JPEG, PNG or WebP files.",
            422,
        )
    try:
        image_bytes = base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error) as error:
        raise ApiError("invalid_review_image", "A review image is invalid.", 422) from error
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise ApiError(
            "review_image_too_large",
            "Each review image must be 10 MB or smaller.",
            413,
        )

    claimed_mimetype = match.group(1)
    if not validate_magic_bytes(image_bytes[:1024], claimed_mimetype):
        raise ApiError(
            "malicious_or_corrupted_file",
            "The review image contents do not match the expected image format.",
            422,
        )

    public_id = f"businesses/{business_id}/{folder}/{review_id}/{uuid4().hex}"
    timestamp = int(time.time())
    parameters = {"public_id": public_id, "timestamp": timestamp}
    signature = cloudinary_signature(parameters, api_secret)
    try:
        response = httpx.post(
            CLOUDINARY_UPLOAD_URL.format(
                cloud_name=cloud_name,
                resource_type="image",
            ),
            data={
                "api_key": api_key,
                "public_id": public_id,
                "timestamp": timestamp,
                "signature": signature,
                "file": data_url,
            },
            timeout=60.0,
        )
        response_data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ApiError(
            "cloudinary_upload_failed",
            "The review image upload service could not be reached.",
            502,
        ) from error
    if response.status_code >= 400:
        message = response_data.get("error", {}).get("message")
        raise ApiError(
            "cloudinary_upload_failed",
            message or "Cloudinary rejected the review image.",
            422 if response.status_code < 500 else 502,
        )

    return {
        "id": response_data.get("asset_id") or response_data.get("public_id"),
        "type": "image",
        "path": response_data.get("public_id", public_id),
        "url": response_data.get("secure_url") or response_data.get("url", ""),
        "contentType": match.group(1),
        "sizeBytes": len(image_bytes),
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
