"""Integration tests for Task creation, short_id incrementing, subtasks, and move operations."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_task_full_crud_lifecycle(client: AsyncClient):
    # 1. Register & setup project
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": "eng@company.io", "password": "Password12345!", "full_name": "Dev Lead"},
    )
    tokens = res.json()["data"]["tokens"]
    access_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Dev Studio", "slug": "dev-studio"},
        headers=headers,
    )
    org_id = org_res.json()["id"]
    headers["X-Org-ID"] = org_id

    ws_res = await client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "App Dev", "slug": "app-dev"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    proj_res = await client.post(
        "/api/v1/projects",
        json={"workspace_id": ws_id, "name": "Mobile App", "key": "MOB"},
        headers=headers,
    )
    proj_id = proj_res.json()["id"]
    statuses = proj_res.json()["statuses"]
    todo_status_id = statuses[1]["id"]
    in_progress_status_id = statuses[2]["id"]

    # 2. Create Task 1 (should get MOB-1)
    task1_res = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": proj_id,
            "title": "Build Auth Screen",
            "priority": "HIGH",
            "story_points": 5.0,
            "status_id": todo_status_id,
        },
        headers=headers,
    )
    assert task1_res.status_code == 201
    task1_data = task1_res.json()
    assert task1_data["short_id"] == "MOB-1"
    assert task1_data["title"] == "Build Auth Screen"
    assert task1_data["priority"] == "HIGH"
    task1_id = task1_data["id"]

    # 3. Create Task 2 (should get MOB-2)
    task2_res = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": proj_id,
            "title": "Setup Push Notifications",
            "priority": "MEDIUM",
            "story_points": 3.0,
        },
        headers=headers,
    )
    assert task2_res.status_code == 201
    assert task2_res.json()["short_id"] == "MOB-2"
    task2_id = task2_res.json()["id"]

    # 4. Add Subtask to Task 1
    sub_res = await client.post(
        f"/api/v1/tasks/{task1_id}/subtasks",
        json={"title": "Design Figma inputs", "position": 0},
        headers=headers,
    )
    assert sub_res.status_code == 201
    sub_data = sub_res.json()
    assert sub_data["title"] == "Design Figma inputs"
    assert sub_data["is_completed"] is False

    # 5. Move Task 1 to In Progress with new position
    move_res = await client.patch(
        f"/api/v1/tasks/{task1_id}/move",
        json={"status_id": in_progress_status_id, "new_position": 2050},
        headers=headers,
    )
    assert move_res.status_code == 200
    moved_data = move_res.json()
    assert moved_data["status_id"] == in_progress_status_id
    assert moved_data["position"] == 2050

    # 6. Add Dependency: Task 1 blocks Task 2
    dep_res = await client.post(
        f"/api/v1/tasks/{task1_id}/dependencies",
        json={"successor_id": task2_id, "dependency_type": "BLOCKS"},
        headers=headers,
    )
    assert dep_res.status_code == 201
    dep_data = dep_res.json()
    assert dep_data["predecessor_id"] == task1_id
    assert dep_data["successor_id"] == task2_id

    # 7. List Tasks for project
    list_res = await client.get(f"/api/v1/tasks/project/{proj_id}", headers=headers)
    assert list_res.status_code == 200
    tasks_list = list_res.json()
    assert len(tasks_list) == 2
