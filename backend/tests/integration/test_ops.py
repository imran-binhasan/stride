"""Observability, health probes, rate limiting, and input-validation coverage."""

import pytest
from httpx import AsyncClient
from src import config as config_module


@pytest.mark.asyncio
async def test_liveness_and_readiness(client: AsyncClient):
    live = await client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"

    ready = await client.get("/health")
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "healthy"
    assert body["checks"] == {"database": True, "redis": True}


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    # Generate at least one measured request.
    await client.get("/health/live")
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text


@pytest.mark.asyncio
async def test_request_id_header_present(client: AsyncClient):
    r = await client.get("/health/live")
    assert r.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_rate_limit_blocks_excess_logins(client: AsyncClient, monkeypatch):
    # Enable the limiter (it is disabled under ENVIRONMENT=test).
    monkeypatch.setattr(config_module.settings, "ENVIRONMENT", "development")

    statuses = []
    for _ in range(12):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.io", "password": "wrong-password"},
        )
        statuses.append(resp.status_code)

    # Limit is 10/min for the login scope; later attempts must be throttled.
    assert 429 in statuses


@pytest.mark.asyncio
async def test_screenshot_presigned_rejects_bad_extension(client: AsyncClient, make_tenant):
    t = await make_tenant("ops-ext@test.io", key="OPX")
    start = await client.post(
        "/api/v1/time-tracking/timer/start",
        json={"task_id": t["task"]["id"]},
        headers=t["headers"],
    )
    entry_id = start.json()["id"]
    r = await client.post(
        "/api/v1/time-tracking/screenshots/presigned-url",
        json={"time_entry_id": entry_id, "file_extension": "exe"},
        headers=t["headers"],
    )
    assert r.status_code == 422
