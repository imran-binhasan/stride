"""Coverage for previously-untested endpoints and the M1 screenshot-confirm guard."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_patch_task_updates_fields(client: AsyncClient, make_tenant):
    t = await make_tenant("cov-patch@test.io", key="CVP")
    r = await client.patch(
        f"/api/v1/tasks/{t['task']['id']}",
        json={"title": "Renamed", "priority": "URGENT", "custom_fields": {"team": "core"}},
        headers=t["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Renamed"
    assert body["priority"] == "URGENT"
    assert body["custom_fields"]["team"] == "core"


@pytest.mark.asyncio
async def test_project_get_and_workspace_list_with_pagination(client: AsyncClient, make_tenant):
    t = await make_tenant("cov-proj@test.io", key="CVJ")

    got = await client.get(f"/api/v1/projects/{t['project']['id']}", headers=t["headers"])
    assert got.status_code == 200
    assert got.json()["id"] == t["project"]["id"]

    listed = await client.get(
        f"/api/v1/projects/workspace/{t['ws_id']}?limit=1&offset=0", headers=t["headers"]
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_task_list_pagination(client: AsyncClient, make_tenant):
    t = await make_tenant("cov-page@test.io", key="CVG")
    # Create extra tasks (make_tenant already created one).
    for i in range(4):
        await client.post(
            "/api/v1/tasks",
            json={"project_id": t["project"]["id"], "title": f"T{i}"},
            headers=t["headers"],
        )
    page = await client.get(
        f"/api/v1/tasks/project/{t['project']['id']}?limit=2&offset=0", headers=t["headers"]
    )
    assert page.status_code == 200
    assert len(page.json()) == 2


@pytest.mark.asyncio
async def test_custom_status_add_and_delete(client: AsyncClient, make_tenant):
    t = await make_tenant("cov-status@test.io", key="CVS")
    add = await client.post(
        f"/api/v1/projects/{t['project']['id']}/statuses",
        json={"name": "QA Testing", "category": "IN_PROGRESS", "color": "#123456", "position": 9},
        headers=t["headers"],
    )
    assert add.status_code == 201
    status_id = add.json()["id"]

    delete = await client.delete(f"/api/v1/projects/statuses/{status_id}", headers=t["headers"])
    assert delete.status_code == 200
    assert delete.json()["success"] is True


@pytest.mark.asyncio
async def test_active_timer_and_screenshot_deletion(client: AsyncClient, make_tenant):
    t = await make_tenant("cov-timer@test.io", key="CVT")
    start = await client.post(
        "/api/v1/time-tracking/timer/start",
        json={"task_id": t["task"]["id"], "is_billable": True},
        headers=t["headers"],
    )
    entry_id = start.json()["id"]

    active = await client.get("/api/v1/time-tracking/timer/active", headers=t["headers"])
    assert active.status_code == 200
    assert active.json()["id"] == entry_id

    pre = await client.post(
        "/api/v1/time-tracking/screenshots/presigned-url",
        json={"time_entry_id": entry_id, "file_extension": "jpg"},
        headers=t["headers"],
    )
    screenshot_id = pre.json()["screenshot_id"]
    s3_key = pre.json()["s3_key"]
    await client.post(
        "/api/v1/time-tracking/screenshots/confirm",
        json={
            "screenshot_id": screenshot_id,
            "time_entry_id": entry_id,
            "s3_key": s3_key,
            "activity_score": 80.0,
            "is_blurred": False,
        },
        headers=t["headers"],
    )

    deleted = await client.delete(
        f"/api/v1/time-tracking/screenshots/{screenshot_id}", headers=t["headers"]
    )
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True


@pytest.mark.asyncio
async def test_screenshot_confirm_rejects_foreign_namespace(client: AsyncClient, make_tenant):
    """M1: a confirmed s3_key outside the caller's org namespace is rejected."""
    t = await make_tenant("cov-m1@test.io", key="CVM")
    start = await client.post(
        "/api/v1/time-tracking/timer/start",
        json={"task_id": t["task"]["id"]},
        headers=t["headers"],
    )
    entry_id = start.json()["id"]
    r = await client.post(
        "/api/v1/time-tracking/screenshots/confirm",
        json={
            "screenshot_id": "forged",
            "time_entry_id": entry_id,
            "s3_key": "screenshots/some-other-org/2026/01/forged.jpg",
            "activity_score": 50.0,
        },
        headers=t["headers"],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_ai_gate1_individual_endpoint(client: AsyncClient, make_tenant):
    t = await make_tenant("cov-ai@test.io", key="CVA")
    r = await client.post(
        "/api/v1/ai/pipeline/gate1-intent",
        json={
            "project_id": t["project"]["id"],
            "feature_prompt": "Add an urgent CSV export button to the reports page",
        },
        headers=t["headers"],
    )
    assert r.status_code == 200
    assert "passed" in r.json()
