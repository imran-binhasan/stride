"""Unit tests for the S3 presigned-URL storage helper."""

from src.core.storage import generate_presigned_put_url, guess_content_type


def test_guess_content_type_maps_common_extensions():
    assert guess_content_type("jpg") == "image/jpeg"
    assert guess_content_type(".PNG") == "image/png"
    assert guess_content_type("webp") == "image/webp"
    assert guess_content_type("bin") == "application/octet-stream"


def test_generate_presigned_put_url_is_signed():
    s3_key = "screenshots/org-1/2026/09/abc123.jpg"
    url = generate_presigned_put_url(s3_key, "image/jpeg", expires_in=300)

    # A genuine SigV4 presigned URL (offline-signed, no network call).
    assert url.startswith("http")
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=300" in url
    assert "abc123.jpg" in url
