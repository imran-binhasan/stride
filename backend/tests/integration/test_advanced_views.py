from datetime import UTC, datetime, timedelta

import pytest
from src.schemas.custom_fields import CustomFieldsRequest


def test_formula_rejects_code_and_unknown_references():
    for expression in ['__import__("os").system("id")', "x ** 1000000", "unknown + 1"]:
        with pytest.raises(ValueError):
            CustomFieldsRequest(
                fields=[{"key": "cost", "name": "Cost", "type": "FORMULA", "formula": expression}]
            )


@pytest.mark.asyncio
async def test_typed_custom_columns_and_formula(client, make_tenant):
    t = await make_tenant("fields@example.com")
    base = "/api/v1/projects/" + t["project"]["id"]
    fields = [
        {"key": "rate", "name": "Rate", "type": "NUMBER"},
        {"key": "cost", "name": "Cost", "type": "FORMULA", "formula": "estimated_hours * rate"},
        {"key": "stage", "name": "Stage", "type": "DROPDOWN", "options": ["Design", "Build"]},
    ]
    result = await client.put(base + "/fields", headers=t["headers"], json={"fields": fields})
    assert result.status_code == 200, result.text
    task = "/api/v1/tasks/" + t["task"]["id"]
    assert (
        await client.patch(task, headers=t["headers"], json={"custom_fields": {"rate": "twenty"}})
    ).status_code == 422
    valid = await client.patch(
        task,
        headers=t["headers"],
        json={"estimated_hours": 2.5, "custom_fields": {"rate": 20, "stage": "Build"}},
    )
    assert valid.status_code == 200, valid.text
    table = await client.get(
        "/api/v1/views/table/" + t["project"]["id"],
        headers=t["headers"],
        params={"sort_by": "title,-created_at", "group_by": "status_id"},
    )
    assert table.status_code == 200, table.text
    assert table.json()["items"][0]["custom_fields"]["cost"] == 50
    assert (
        await client.patch(task, headers=t["headers"], json={"custom_fields": {"cost": 1000}})
    ).status_code == 422


@pytest.mark.asyncio
async def test_gantt_schedule_preview_apply_and_milestone(client, make_tenant):
    t = await make_tenant("schedule@example.com")
    pid = t["project"]["id"]
    base = "/api/v1/tasks/" + t["task"]["id"]
    await client.patch(base, headers=t["headers"], json={"estimated_hours": 16})
    follow = await client.post(
        "/api/v1/tasks",
        headers=t["headers"],
        json={"project_id": pid, "title": "Release", "type": "MILESTONE"},
    )
    assert follow.status_code == 201, follow.text
    link = await client.post(
        base + "/dependencies",
        headers=t["headers"],
        json={"successor_id": follow.json()["id"], "dependency_type": "BLOCKS", "lag_days": 1},
    )
    assert link.status_code == 201, link.text
    endpoint = "/api/v1/views/gantt/" + pid + "/schedule"
    preview = await client.post(
        endpoint, headers=t["headers"], json={"start_date": "2026-12-01", "preview": True}
    )
    assert preview.status_code == 200, preview.text
    assert (await client.get(base, headers=t["headers"])).json()["start_date"] is None
    changes = {c["id"]: c for c in preview.json()["changes"]}
    assert changes[t["task"]["id"]]["due_date"] == "2026-12-02"
    assert changes[follow.json()["id"]]["start_date"] == "2026-12-04"
    applied = await client.post(
        endpoint, headers=t["headers"], json={"start_date": "2026-12-01", "preview": False}
    )
    assert applied.status_code == 200, applied.text
    assert (await client.get(base, headers=t["headers"])).json()["due_date"] == "2026-12-02"


@pytest.mark.asyncio
async def test_calendar_subscription_rotates_and_revokes(client, make_tenant):
    t = await make_tenant("calendar-feed@example.com")
    await client.patch(
        "/api/v1/tasks/" + t["task"]["id"], headers=t["headers"], json={"due_date": "2026-12-01"}
    )
    endpoint = "/api/v1/views/calendar/" + t["project"]["id"] + "/feed"
    created = await client.post(endpoint, headers=t["headers"])
    assert created.status_code == 200, created.text
    from urllib.parse import urlparse

    path = urlparse(created.json()["url"]).path
    feed = await client.get(path)
    assert feed.status_code == 200, feed.text
    assert "BEGIN:VEVENT" in feed.text
    await client.post(endpoint, headers=t["headers"])
    assert (await client.get(path)).status_code == 404
    await client.delete(endpoint, headers=t["headers"])


@pytest.mark.asyncio
async def test_idle_stop_clips_session_and_keeps_optional_draft(client, make_tenant):
    t = await make_tenant("idle-stop@example.com")
    started = await client.post(
        "/api/v1/time-tracking/timer/start", headers=t["headers"], json={"task_id": t["task"]["id"]}
    )
    start = datetime.fromisoformat(started.json()["start_time"])
    stopped = await client.post(
        "/api/v1/time-tracking/timer/stop",
        headers=t["headers"],
        json={"time_entry_id": started.json()["id"], "idle_since": start.isoformat()},
    )
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["total_seconds"] == 0
    assert stopped.json()["activity_percent"] == 0
    bad = await client.post(
        "/api/v1/time-tracking/timer/start", headers=t["headers"], json={"task_id": t["task"]["id"]}
    )
    future = datetime.now(UTC) + timedelta(hours=1)
    assert (
        await client.post(
            "/api/v1/time-tracking/timer/stop",
            headers=t["headers"],
            json={"time_entry_id": bad.json()["id"], "idle_since": future.isoformat()},
        )
    ).status_code == 422
