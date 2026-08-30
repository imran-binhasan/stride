"""Integration tests for Kanban, Calendar, and Gantt View API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_view_engines_endpoints(client: AsyncClient):
    # 1. Register & setup project
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "views@team.io", "password": "Password12345!", "full_name": "Views Lead"},
    )
    tokens = reg_res.json()["data"]["tokens"]
    access_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "View Tech", "slug": "view-tech"},
        headers=headers,
    )
    org_id = org_res.json()["id"]
    headers["X-Org-ID"] = org_id

    ws_res = await client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "Product", "slug": "product"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    proj_res = await client.post(
        "/api/v1/projects",
        json={"workspace_id": ws_id, "name": "Web App", "key": "WEB"},
        headers=headers,
    )
    proj_id = proj_res.json()["id"]
    statuses = proj_res.json()["statuses"]
    todo_id = statuses[1]["id"]
    in_prog_id = statuses[2]["id"]

    # 2. Create tasks with due dates
    await client.post(
        "/api/v1/tasks",
        json={
            "project_id": proj_id,
            "title": "Design Database Schema",
            "status_id": todo_id,
            "due_date": "2026-09-15",
            "story_points": 3.0,
        },
        headers=headers,
    )
    await client.post(
        "/api/v1/tasks",
        json={
            "project_id": proj_id,
            "title": "Implement JWT Auth",
            "status_id": in_prog_id,
            "due_date": "2026-09-20",
            "story_points": 5.0,
        },
        headers=headers,
    )

    # 3. Test Kanban View Endpoint
    kanban_res = await client.get(f"/api/v1/views/kanban/{proj_id}", headers=headers)
    assert kanban_res.status_code == 200
    k_data = kanban_res.json()
    assert k_data["total_tasks"] == 2
    assert len(k_data["columns"]) == 5

    # 4. Test Calendar View Endpoint
    cal_res = await client.get(
        f"/api/v1/views/calendar/{proj_id}?month=9&year=2026", headers=headers
    )
    assert cal_res.status_code == 200
    cal_data = cal_res.json()
    assert len(cal_data["events"]) == 2

    # 5. Test Gantt CPM View Endpoint
    gantt_res = await client.get(f"/api/v1/views/gantt/{proj_id}", headers=headers)
    assert gantt_res.status_code == 200
    gantt_data = gantt_res.json()
    assert "project_duration_days" in gantt_data
    assert len(gantt_data["nodes"]) == 2
