"""Real S3-compatible HTTP uploads; enabled only for an explicitly disposable store."""

import os
import uuid
from pathlib import Path

import httpx
import pytest
from src.config import settings
from src.core.storage import get_public_s3_client, get_s3_client


@pytest.mark.asyncio
async def test_real_attachment_and_screenshot_uploads(
    client, make_tenant, redis_client, monkeypatch
):
    endpoint = os.environ.get("STRIDE_TEST_S3_ENDPOINT")
    if not endpoint:
        pytest.skip("Requires an explicitly configured disposable S3-compatible store")
    bucket = "stride-test-" + uuid.uuid4().hex
    for key, value in {
        "S3_ENDPOINT_URL": endpoint,
        "S3_PUBLIC_ENDPOINT_URL": endpoint,
        "S3_ACCESS_KEY": "stride-test",
        "S3_SECRET_KEY": "stride-storage-test-secret",
        "S3_BUCKET_NAME": bucket,
    }.items():
        monkeypatch.setattr(settings, key, value)
    get_s3_client.cache_clear()
    get_public_s3_client.cache_clear()
    s3 = get_s3_client()
    s3.create_bucket(Bucket=bucket)
    tenant = await make_tenant("live-storage@example.com")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    try:
        base = "/api/v1/tasks/" + tenant["task"]["id"] + "/attachments"
        data = b"actual attachment payload"
        reservation = await client.post(
            base + "/upload-url",
            headers=tenant["headers"],
            json={"file_name": "proof.txt", "file_size": len(data), "mime_type": "text/plain"},
        )
        assert reservation.status_code == 200, reservation.text
        upload = reservation.json()
        async with httpx.AsyncClient() as external:
            assert (
                await external.put(
                    upload["upload_url"], content=data, headers={"Content-Type": "text/plain"}
                )
            ).status_code == 200
            confirmed = await client.post(
                base + "/confirm",
                headers=tenant["headers"],
                json={"attachment_id": upload["attachment_id"]},
            )
            assert confirmed.status_code == 201, confirmed.text
            download = await client.get(
                base + "/" + upload["attachment_id"] + "/download-url", headers=tenant["headers"]
            )
            assert (await external.get(download.json()["download_url"])).content == data
            timer = await client.post(
                "/api/v1/time-tracking/timer/start",
                headers=tenant["headers"],
                json={"task_id": tenant["task"]["id"]},
            )
            shot = await client.post(
                "/api/v1/time-tracking/screenshots/presigned-url",
                headers=tenant["headers"],
                json={"time_entry_id": timer.json()["id"], "file_extension": "png"},
            )
            signed = shot.json()
            assert (
                await external.put(
                    signed["upload_url"],
                    content=(
                        Path(__file__).resolve().parents[3] / "desktop/src-tauri/icons/icon.png"
                    ).read_bytes(),
                    headers={"Content-Type": "image/png"},
                )
            ).status_code == 200
            result = await client.post(
                "/api/v1/time-tracking/screenshots/confirm",
                headers=tenant["headers"],
                json={
                    "time_entry_id": timer.json()["id"],
                    "screenshot_id": signed["screenshot_id"],
                    "s3_key": signed["s3_key"],
                },
            )
            assert result.status_code == 201, result.text
    finally:
        objects = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
        if objects:
            s3.delete_objects(
                Bucket=bucket, Delete={"Objects": [{"Key": o["Key"]} for o in objects]}
            )
        s3.delete_bucket(Bucket=bucket)
        get_s3_client.cache_clear()
        get_public_s3_client.cache_clear()
