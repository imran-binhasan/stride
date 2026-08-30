"""Integration tests for Project creation, default statuses, and Sprints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_project_lifecycle(client: AsyncClient):
    # 1. Register user & get token
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "pm@enterprise.io",
            "password": "Password12345!",
            "full_name": "Project Lead",
        },
    )
    tokens = res.json()["data"]["tokens"]
    access_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Get workspace ID from user me/org
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200

    # Create dedicated workspace
    ws_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Acme Corp", "slug": "acme-corp"},
        headers=headers,
    )
    org_id = ws_res.json()["id"]
    headers["X-Org-ID"] = org_id

    ws_create_res = await client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "Engineering", "slug": "eng"},
        headers=headers,
    )
    ws_id = ws_create_res.json()["id"]

    # 3. Create Project
    proj_res = await client.post(
        "/api/v1/projects",
        json={
            "workspace_id": ws_id,
            "name": "Core Backend",
            "key": "A3Z",
            "description": "Backend API service",
        },
        headers=headers,
    )
    assert proj_res.status_code == 201
    proj_data = proj_res.json()
    assert proj_data["key"] == "A3Z"
    assert proj_data["name"] == "Core Backend"
    # Verify auto-initialized 5 workflow statuses
    assert len(proj_data["statuses"]) == 5
    status_names = [s["name"] for s in proj_data["statuses"]]
    assert status_names == ["Backlog", "To Do", "In Progress", "In Review", "Done"]

    proj_id = proj_data["id"]

    # 4. Duplicate project key in same org returns 409
    dup_res = await client.post(
        "/api/v1/projects",
        json={
            "workspace_id": ws_id,
            "name": "Duplicate Project",
            "key": "A3Z",
        },
        headers=headers,
    )
    assert dup_res.status_code == 409

    # 5. Create Sprint under Project
    sprint_res = await client.post(
        f"/api/v1/projects/{proj_id}/sprints",
        json={
            "name": "Sprint 1 - Foundation",
            "goal": "Ship MVP Backend APIs",
            "start_date": "2026-09-01",
            "end_date": "2026-09-14",
        },
        headers=headers,
    )
    assert sprint_res.status_code == 201
    sprint_data = sprint_res.json()
    assert sprint_data["name"] == "Sprint 1 - Foundation"
    assert sprint_data["project_id"] == proj_id
