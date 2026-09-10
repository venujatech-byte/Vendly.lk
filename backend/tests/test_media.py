from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app.core.errors import ApiError
from app.services.media_service import firebase_download_url, validate_media


def test_image_media_is_accepted():
    valid_webp = b"RIFF\x14\x00\x00\x00WEBPVP8 \x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    upload = FileStorage(
        stream=BytesIO(valid_webp),
        filename="shoe.webp",
        content_type="image/webp",
    )

    media_type, size = validate_media(upload)

    assert media_type == "image"
    assert size == len(valid_webp)


def test_disguised_script_is_rejected():
    upload = FileStorage(
        stream=BytesIO(b"<script>alert('xss')</script>"),
        filename="malicious.png",
        content_type="image/png",
    )

    with pytest.raises(ApiError) as error:
        validate_media(upload)

    assert error.value.code == "malicious_or_corrupted_file"


def test_mismatched_magic_bytes_is_rejected():
    upload = FileStorage(
        stream=BytesIO(b"not-really-a-jpeg-file"),
        filename="fake.jpeg",
        content_type="image/jpeg",
    )

    with pytest.raises(ApiError) as error:
        validate_media(upload)

    assert error.value.code == "malicious_or_corrupted_file"


def test_unsupported_media_is_rejected():
    upload = FileStorage(
        stream=BytesIO(b"document"),
        filename="product.pdf",
        content_type="application/pdf",
    )

    with pytest.raises(ApiError) as error:
        validate_media(upload)

    assert error.value.code == "unsupported_media_type"


def test_download_url_encodes_storage_path():
    url = firebase_download_url("bucket", "businesses/one/image 1.png", "token")

    assert "businesses%2Fone%2Fimage%201.png" in url
