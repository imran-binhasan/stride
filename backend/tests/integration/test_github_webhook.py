"""Integration tests for GitHub webhook processing and automated status transitions."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_github_webhook_pr_transition_flow(client: AsyncClient):
    # 1. Setup User & Project
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "gh@dev.io", "password": "Password12345!", "full_name": "GH Dev"},
    )
    access_token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "GitHub Lab", "slug": "gh-lab"},
        headers=headers,
    )
    org_id = org_res.json()["id"]
    headers["X-Org-ID"] = org_id

    ws_res = await client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "Git WS", "slug": "git-ws"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    proj_res = await client.post(
        "/api/v1/projects",
        json={"workspace_id": ws_id, "name": "API Service", "key": "GH"},
        headers=headers,
    )
    proj_id = proj_res.json()["id"]
    statuses = proj_res.json()["statuses"]
    todo_id = statuses[1]["id"]
    in_review_id = statuses[3]["id"]
    done_id = statuses[4]["id"]

    # 2. Connect GitHub Repository to Project
    connect_res = await client.post(
        f"/api/v1/integrations/projects/{proj_id}/github",
        json={
            "repo_owner": "a3zen-org",
            "repo_name": "api-service",
            "auto_transition_pr_open": True,
            "auto_transition_pr_merge": True,
        },
        headers=headers,
    )
    assert connect_res.status_code == 201

    # 3. Create a Task (should get GH-1)
    task_res = await client.post(
        "/api/v1/tasks",
        json={
            "project_id": proj_id,
            "title": "Implement Webhook Verification",
            "status_id": todo_id,
        },
        headers=headers,
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["id"]
    assert task_res.json()["short_id"] == "GH-1"
    assert task_res.json()["status_id"] == todo_id

    # 4. Trigger Webhook: PR Opened with branch `feature/GH-1-webhook`
    pr_opened_payload = {
        "action": "opened",
        "repository": {
            "name": "api-service",
            "owner": {"login": "a3zen-org"},
        },
        "pull_request": {
            "title": "feat: add webhook verification",
            "head": {"ref": "feature/GH-1-webhook"},
            "body": "Resolves GH-1 with full HMAC support",
            "merged": False,
        },
    }
    hook_res = await client.post(
        "/api/v1/integrations/github/webhook",
        json=pr_opened_payload,
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert hook_res.status_code == 200
    assert hook_res.json()["success"] is True

    # Verify task transitioned to In Review
    t_check1 = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert t_check1.json()["status_id"] == in_review_id

    # 5. Trigger Webhook: PR Merged
    pr_merged_payload = {
        "action": "closed",
        "repository": {
            "name": "api-service",
            "owner": {"login": "a3zen-org"},
        },
        "pull_request": {
            "title": "feat: add webhook verification",
            "head": {"ref": "feature/GH-1-webhook"},
            "body": "Resolves GH-1 with full HMAC support",
            "merged": True,
        },
    }
    hook_res2 = await client.post(
        "/api/v1/integrations/github/webhook",
        json=pr_merged_payload,
        headers={"X-GitHub-Event": "pull_request"},
    )
    assert hook_res2.status_code == 200

    # Verify task transitioned to Done
    t_check2 = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert t_check2.json()["status_id"] == done_id
