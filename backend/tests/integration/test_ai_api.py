"""Integration tests for AI Engineering Pipeline API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_ai_pipeline_endpoint(client: AsyncClient):
    # 1. Setup User & Project
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ai-lead@pipeline.io",
            "password": "Password12345!",
            "full_name": "AI Pipeline Lead",
        },
    )
    access_token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Pipeline AI Corp", "slug": "pipeline-ai"},
        headers=headers,
    )
    org_id = org_res.json()["id"]
    headers["X-Org-ID"] = org_id

    ws_res = await client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "Intelligence", "slug": "intel"},
        headers=headers,
    )
    ws_id = ws_res.json()["id"]

    proj_res = await client.post(
        "/api/v1/projects",
        json={"workspace_id": ws_id, "name": "AI Platform", "key": "AIP"},
        headers=headers,
    )
    proj_id = proj_res.json()["id"]

    # 2. Trigger Full 5-Gate AI Pipeline
    pipe_res = await client.post(
        "/api/v1/ai/pipeline/run-all",
        json={
            "project_id": proj_id,
            "feature_prompt": "URGENT: Create a real-time cursor presence indicator for collaborative Kanban boards",
        },
        headers=headers,
    )
    assert pipe_res.status_code == 200
    data = pipe_res.json()
    assert data["pipeline_success"] is True
    assert data["gate1_intent"]["passed"] is True
    assert data["gate1_intent"]["suggested_priority"] == "URGENT"
    assert data["gate2_context"]["passed"] is True
    assert data["gate3_plan"]["is_acyclic"] is True
    assert data["gate4_tdd"]["passed"] is True
    assert data["gate5_execution"]["coverage_percent"] >= 90.0
