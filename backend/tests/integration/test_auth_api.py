"""Integration tests for Auth, Registration, Login, Token Refresh and Org creation."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_login_and_me_flow(client: AsyncClient):
    # 1. Register a new user
    reg_payload = {
        "email": "ceo@startup.io",
        "password": "Password12345!",
        "full_name": "Sarah Connor",
        "organization_name": "Cyberdyne Systems",
    }
    res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    assert data["data"]["user"]["email"] == "ceo@startup.io"
    access_token = data["data"]["tokens"]["access_token"]
    refresh_token = data["data"]["tokens"]["refresh_token"]
    assert access_token is not None
    assert refresh_token is not None

    # 2. Duplicate registration returns 409 Conflict
    dup_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 409

    # 3. Login with credentials
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "ceo@startup.io", "password": "Password12345!"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    new_access_token = login_data["access_token"]

    # 4. Access /auth/me with Bearer token
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "ceo@startup.io"
    assert me_data["full_name"] == "Sarah Connor"

    # 5. Rotate refresh token
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    refreshed_data = refresh_res.json()
    assert "access_token" in refreshed_data
    assert refreshed_data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_invalid_login(client: AsyncClient):
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@a3zen.io", "password": "wrongpassword"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_organization_and_workspace(client: AsyncClient):
    # Register user first
    reg_payload = {
        "email": "lead@tech.io",
        "password": "Password12345!",
        "full_name": "Alex Murphy",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    access_token = reg_res.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Create new Organization
    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Omni Consumer Products", "slug": "ocp-corp"},
        headers=headers,
    )
    assert org_res.status_code == 201
    org_data = org_res.json()
    assert org_data["slug"] == "ocp-corp"
    org_id = org_data["id"]

    # Create new Workspace in Organization
    ws_res = await client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "Delta City R&D", "slug": "delta-rd", "description": "Future city project"},
        headers={**headers, "X-Org-ID": org_id},
    )
    assert ws_res.status_code == 201
    ws_data = ws_res.json()
    assert ws_data["name"] == "Delta City R&D"
    assert ws_data["org_id"] == org_id
