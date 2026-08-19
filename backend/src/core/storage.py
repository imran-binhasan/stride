"""S3-compatible object storage client for presigned screenshot uploads and lifecycle."""

import logging
from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from src.config import settings

logger = logging.getLogger("a3zen.storage")

_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}


def guess_content_type(file_extension: str) -> str:
    """Map a file extension to a MIME content type for presigned uploads."""
    return _CONTENT_TYPES.get(file_extension.lower().lstrip("."), "application/octet-stream")


@lru_cache
def get_s3_client():
    """Return a cached boto3 S3 client configured for AWS S3 or an S3-compatible endpoint (MinIO/R2)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )


def generate_presigned_put_url(s3_key: str, content_type: str, expires_in: int = 300) -> str:
    """Generate a presigned PUT URL for a direct client-to-S3 screenshot upload.

    This performs offline request signing (no network round-trip).
    """
    return get_s3_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


def delete_object(s3_key: str) -> bool:
    """Best-effort deletion of a stored object. Returns True on success, False on failure."""
    try:
        get_s3_client().delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        return True
    except (BotoCoreError, ClientError) as exc:
        logger.warning("Failed to delete S3 object %s: %s", s3_key, exc)
        return False
