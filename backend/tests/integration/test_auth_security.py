"""Refresh-token lifecycle and privilege-ceiling security regressions."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.security import hash_token
from src.models.auth import RefreshToken


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "sec-logout@test.io", "password": "Password12345!", "full_name": "Sec"},
    )
    refresh = reg.json()["data"]["tokens"]["refresh_token"]

    out = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert out.status_code == 200

    # Refresh with a revoked token must fail.
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotation_invalidates_old_token(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "sec-rot@test.io", "password": "Password12345!", "full_name": "Sec"},
    )
    refresh = reg.json()["data"]["tokens"]["refresh_token"]

    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert first.status_code == 200
    # Old token is now revoked (rotation).
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_is_hashed_at_rest(client: AsyncClient, db_session: AsyncSession):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "sec-hash@test.io", "password": "Password12345!", "full_name": "Sec"},
    )
    refresh = reg.json()["data"]["tokens"]["refresh_token"]

    stored = (await db_session.execute(select(RefreshToken.token))).scalars().all()
    assert refresh not in stored  # raw token never persisted
    assert hash_token(refresh) in stored  # only the hash is stored


@pytest.mark.asyncio
async def test_admin_cannot_grant_role_above_own(client: AsyncClient, make_tenant):
    owner = await make_tenant("sec-owner@test.io", key="SEO")

    # Two existing users to invite.
    for email in ("sec-admin@test.io", "sec-target@test.io"):
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password12345!", "full_name": "Test User"},
        )

    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "sec-admin@test.io", "password": "Password12345!"},
    )
    assert admin_login.status_code == 200
    # Owner promotes admin to ORG_ADMIN.
    await client.post(
        f"/api/v1/organizations/{owner['org_id']}/members",
        json={"email": "sec-admin@test.io", "role": "ORG_ADMIN"},
        headers=owner["headers"],
    )
    admin_headers = {
        "Authorization": f"Bearer {admin_login.json()['access_token']}",
        "X-Org-ID": owner["org_id"],
    }

    # Admin granting ORG_OWNER (above own rank) -> 403.
    r = await client.post(
        f"/api/v1/organizations/{owner['org_id']}/members",
        json={"email": "sec-target@test.io", "role": "ORG_OWNER"},
        headers=admin_headers,
    )
    assert r.status_code == 403

    # Admin granting MEMBER (<= own rank) -> allowed.
    r = await client.post(
        f"/api/v1/organizations/{owner['org_id']}/members",
        json={"email": "sec-target@test.io", "role": "MEMBER"},
        headers=admin_headers,
    )
    assert r.status_code == 201
