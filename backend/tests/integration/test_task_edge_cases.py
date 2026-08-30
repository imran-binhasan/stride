"""Negative and edge-path coverage for task update, move, and dependency rules."""

import pytest
from httpx import AsyncClient


async def _new_task(client, headers, project_id, title):
    r = await client.post(
        "/api/v1/tasks", json={"project_id": project_id, "title": title}, headers=headers
    )
    return r.json()["id"]


@pytest.mark.asyncio
async def test_update_all_task_fields(client: AsyncClient, make_tenant):
    t = await make_tenant("edge-upd@test.io", key="EUP")
    status_id = t["project"]["statuses"][2]["id"]
    r = await client.patch(
        f"/api/v1/tasks/{t['task']['id']}",
        json={
            "title": "Full",
            "description": "desc",
            "status_id": status_id,
            "priority": "HIGH",
            "story_points": 5,
            "estimated_hours": 16,
            "due_date": "2026-12-01",
            "custom_fields": {"k": "v"},
        },
        headers=t["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["description"] == "desc"
    assert body["status_id"] == status_id
    assert body["story_points"] == 5


@pytest.mark.asyncio
async def test_update_nonexistent_task_404(client: AsyncClient, make_tenant):
    t = await make_tenant("edge-upd404@test.io", key="E44")
    r = await client.patch(
        "/api/v1/tasks/nope", json={"title": "x"}, headers=t["headers"]
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_move_nonexistent_task_404(client: AsyncClient, make_tenant):
    t = await make_tenant("edge-move@test.io", key="EMV")
    status_id = t["project"]["statuses"][1]["id"]
    r = await client.patch(
        "/api/v1/tasks/nope/move",
        json={"status_id": status_id, "new_position": 100},
        headers=t["headers"],
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_dependency_self_reference_409(client: AsyncClient, make_tenant):
    t = await make_tenant("edge-dep-self@test.io", key="EDS")
    tid = t["task"]["id"]
    r = await client.post(
        f"/api/v1/tasks/{tid}/dependencies",
        json={"successor_id": tid},
        headers=t["headers"],
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_dependency_unknown_successor_404(client: AsyncClient, make_tenant):
    t = await make_tenant("edge-dep-404@test.io", key="ED4")
    r = await client.post(
        f"/api/v1/tasks/{t['task']['id']}/dependencies",
        json={"successor_id": "ghost"},
        headers=t["headers"],
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_dependency_cycle_rejected_409(client: AsyncClient, make_tenant):
    t = await make_tenant("edge-cycle@test.io", key="ECY")
    a = t["task"]["id"]
    b = await _new_task(client, t["headers"], t["project"]["id"], "B")

    # A -> B ok
    r = await client.post(
        f"/api/v1/tasks/{a}/dependencies", json={"successor_id": b}, headers=t["headers"]
    )
    assert r.status_code == 201
    # B -> A creates a cycle
    r = await client.post(
        f"/api/v1/tasks/{b}/dependencies", json={"successor_id": a}, headers=t["headers"]
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_update_rejects_foreign_project_status(client: AsyncClient, make_tenant):
    """A status id from another org's project cannot be assigned via PATCH."""
    a = await make_tenant("edge-fs-a@test.io", key="EFA")
    b = await make_tenant("edge-fs-b@test.io", key="EFB")
    foreign_status = b["project"]["statuses"][1]["id"]

    r = await client.patch(
        f"/api/v1/tasks/{a['task']['id']}",
        json={"status_id": foreign_status},
        headers=a["headers"],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_assign_to_non_member_rejected(client: AsyncClient, make_tenant):
    a = await make_tenant("edge-asg-a@test.io", key="EGA")
    b = await make_tenant("edge-asg-b@test.io", key="EGB")

    r = await client.patch(
        f"/api/v1/tasks/{a['task']['id']}",
        json={"assignee_id": b["user_id"]},
        headers=a["headers"],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_stop_timer_when_none_active_422(client: AsyncClient, make_tenant):
    t = await make_tenant("edge-timer@test.io", key="ETM")
    r = await client.post(
        "/api/v1/time-tracking/timer/stop", json={}, headers=t["headers"]
    )
    assert r.status_code == 422
