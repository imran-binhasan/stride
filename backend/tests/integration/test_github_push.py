"""Integration test for GitHub push-event commit linking."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_github_push_links_tasks_from_commit_messages(client: AsyncClient):
    # 1. Setup user, org, workspace, project (key GH), and a task -> GH-1
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "push@dev.io", "password": "Password12345!", "full_name": "Push Dev"},
    )
    access_token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    org_id = (
        await client.post(
            "/api/v1/organizations",
            json={"name": "Push Lab", "slug": "push-lab"},
            headers=headers,
        )
    ).json()["id"]
    headers["X-Org-ID"] = org_id

    ws_id = (
        await client.post(
            f"/api/v1/organizations/{org_id}/workspaces",
            json={"name": "Push WS", "slug": "push-ws"},
            headers=headers,
        )
    ).json()["id"]

    proj_id = (
        await client.post(
            "/api/v1/projects",
            json={"workspace_id": ws_id, "name": "Push Service", "key": "GH"},
            headers=headers,
        )
    ).json()["id"]

    task_res = await client.post(
        "/api/v1/tasks",
        json={"project_id": proj_id, "title": "Wire commit linking"},
        headers=headers,
    )
    task_id = task_res.json()["id"]
    assert task_res.json()["short_id"] == "GH-1"

    # 2. Connect the repository
    await client.post(
        f"/api/v1/integrations/projects/{proj_id}/github",
        json={"repo_owner": "a3zen-org", "repo_name": "push-service"},
        headers=headers,
    )

    # 3. Send a push webhook whose commit message references GH-1
    push_payload = {
        "repository": {"name": "push-service", "owner": {"login": "a3zen-org"}},
        "commits": [
            {"message": "fix: resolve GH-1 race condition"},
            {"message": "chore: unrelated cleanup"},
        ],
    }
    hook_res = await client.post(
        "/api/v1/integrations/github/webhook",
        json=push_payload,
        headers={"X-GitHub-Event": "push"},
    )
    assert hook_res.status_code == 200
    result = hook_res.json()["result"]
    assert result["status"] == "processed"
    assert any(t["task_id"] == task_id for t in result["affected_tasks"])
