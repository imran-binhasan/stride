"""Integration tests for Time Tracking, Active Timers, Telemetry, Screenshots, and Daily Reports."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_time_tracking_full_lifecycle_and_daily_report(client: AsyncClient):
    # 1. Register user & setup project/task
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tracker@agency.io",
            "password": "Password12345!",
            "full_name": "Dev Tracker",
        },
    )
    access_token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Tracker Agency", "slug": "tracker-agency"},
        headers=headers,
    )
    org_id = org_res.json()["id"]
    headers["X-Org-ID"] = org_id

    ws_res = await client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "Operations", "slug": "ops"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    proj_res = await client.post(
        "/api/v1/projects",
        json={"workspace_id": ws_id, "name": "Client Portal", "key": "CP"},
        headers=headers,
    )
    proj_id = proj_res.json()["id"]

    task_res = await client.post(
        "/api/v1/tasks",
        json={"project_id": proj_id, "title": "Implement Payment Webhook"},
        headers=headers,
    )
    task_id = task_res.json()["id"]

    # 2. Start Active Timer on Task
    start_res = await client.post(
        "/api/v1/time-tracking/timer/start",
        json={"task_id": task_id, "is_billable": True, "notes": "Working on stripe hook"},
        headers=headers,
    )
    assert start_res.status_code == 201
    timer_data = start_res.json()
    time_entry_id = timer_data["id"]

    # 3. Ingest 30s Telemetry Heartbeats
    now = datetime.now(UTC).isoformat()
    telem_res = await client.post(
        "/api/v1/time-tracking/telemetry/heartbeat",
        json={
            "time_entry_id": time_entry_id,
            "period_start": now,
            "period_end": now,
            "keystroke_count": 35,
            "mouse_distance_px": 550,
            "active_window_title": "VS Code",
            "is_idle": False,
        },
        headers=headers,
    )
    assert telem_res.status_code == 200
    assert telem_res.json()["activity_score"] > 0.0

    # 4. Request Presigned S3 Screenshot URL & Confirm
    pre_res = await client.post(
        "/api/v1/time-tracking/screenshots/presigned-url",
        json={"time_entry_id": time_entry_id, "file_extension": "jpg"},
        headers=headers,
    )
    screenshot_id = pre_res.json()["screenshot_id"]
    s3_key = pre_res.json()["s3_key"]

    await client.post(
        "/api/v1/time-tracking/screenshots/confirm",
        json={
            "screenshot_id": screenshot_id,
            "time_entry_id": time_entry_id,
            "s3_key": s3_key,
            "activity_score": 85.0,
            "is_blurred": False,
        },
        headers=headers,
    )

    # 5. Stop Timer
    await client.post(
        "/api/v1/time-tracking/timer/stop",
        json={"time_entry_id": time_entry_id, "notes": "Completed initial draft"},
        headers=headers,
    )

    # 6. Fetch Daily Activity Summary Report
    today_str = datetime.now(UTC).date().isoformat()
    report_res = await client.get(
        f"/api/v1/time-tracking/reports/daily?date={today_str}", headers=headers
    )
    assert report_res.status_code == 200
    report = report_res.json()
    assert report["total_sessions_count"] == 1
    assert report["day_first_start_time"] is not None
    assert report["day_last_end_time"] is not None
    assert len(report["ten_minute_blocks"]) >= 1
    first_block = report["ten_minute_blocks"][0]
    assert first_block["activity_percent"] > 0.0
    assert first_block["screenshot_url"] == s3_key
