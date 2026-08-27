"""Authentication/authorization failure matrix — 401/403/404 across protected routes."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_token_is_401(client: AsyncClient):
    r = await client.get("/api/v1/tasks/some-id")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_is_401(client: AsyncClient):
    r = await client.get(
        "/api/v1/tasks/some-id", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_nonexistent_task_is_404(client: AsyncClient, make_tenant):
    a = await make_tenant("authz-a@test.io", key="AZA")
    r = await client.get("/api/v1/tasks/does-not-exist", headers=a["headers"])
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_insufficient_role_is_403(client: AsyncClient, make_tenant):
    owner = await make_tenant("authz-owner@test.io", key="AZO")
    # Register a guest user (gets their own default org), then invite into owner's org as GUEST.
    guest_reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "authz-guest@test.io", "password": "Password12345!", "full_name": "Guest"},
    )
    guest_token = guest_reg.json()["data"]["tokens"]["access_token"]

    invite = await client.post(
        f"/api/v1/organizations/{owner['org_id']}/members",
        json={"email": "authz-guest@test.io", "role": "GUEST"},
        headers=owner["headers"],
    )
    assert invite.status_code == 201

    guest_headers = {"Authorization": f"Bearer {guest_token}", "X-Org-ID": owner["org_id"]}

    # GUEST creating a project requires MEMBER -> 403
    r = await client.post(
        "/api/v1/projects",
        json={"workspace_id": owner["ws_id"], "name": "Nope", "key": "NOP"},
        headers=guest_headers,
    )
    assert r.status_code == 403

    # GUEST adding a workflow status requires PROJECT_MANAGER -> 403
    r = await client.post(
        f"/api/v1/projects/{owner['project']['id']}/statuses",
        json={"name": "QA", "category": "IN_PROGRESS", "color": "#111111", "position": 9},
        headers=guest_headers,
    )
    assert r.status_code == 403
