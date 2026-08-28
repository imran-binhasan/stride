"""Integration tests for Figma frame attachments and listing."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_figma_link_attachment_and_listing(client: AsyncClient):
    # 1. Setup User & Project & Task
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "design@studio.io",
            "password": "Password12345!",
            "full_name": "Figma Designer",
        },
    )
    access_token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Design Corp", "slug": "design-corp"},
        headers=headers,
    )
    org_id = org_res.json()["id"]
    headers["X-Org-ID"] = org_id

    ws_res = await client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "UI/UX", "slug": "ui-ux"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    proj_res = await client.post(
        "/api/v1/projects",
        json={"workspace_id": ws_id, "name": "Design System", "key": "DS"},
        headers=headers,
    )
    proj_id = proj_res.json()["id"]

    task_res = await client.post(
        "/api/v1/tasks",
        json={"project_id": proj_id, "title": "Design Navigation Bar"},
        headers=headers,
    )
    task_id = task_res.json()["id"]

    # 2. Attach Figma Frame to Task
    figma_url = "https://www.figma.com/file/aBc123XYZ/App-Design?node-id=10%3A20"
    attach_res = await client.post(
        f"/api/v1/integrations/tasks/{task_id}/figma",
        json={"figma_url": figma_url, "file_name": "Navbar Component"},
        headers=headers,
    )
    assert attach_res.status_code == 201
    link_data = attach_res.json()
    assert link_data["file_key"] == "aBc123XYZ"
    assert link_data["node_id"] == "10:20"
    assert link_data["file_name"] == "Navbar Component"
    assert "thumbnail_url" in link_data

    # 3. List Figma Links on Task
    list_res = await client.get(f"/api/v1/integrations/tasks/{task_id}/figma", headers=headers)
    assert list_res.status_code == 200
    links_list = list_res.json()
    assert len(links_list) == 1
    assert links_list[0]["id"] == link_data["id"]
