"""Org/workspace discovery endpoints used by the frontend bootstrap."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_my_orgs_and_workspaces(client: AsyncClient, make_tenant):
    t = await make_tenant("disco@test.io", key="DIS")

    orgs = await client.get("/api/v1/organizations", headers=t["headers"])
    assert orgs.status_code == 200
    ids = [o["id"] for o in orgs.json()]
    assert t["org_id"] in ids
    mine = next(o for o in orgs.json() if o["id"] == t["org_id"])
    assert mine["role"] == "ORG_OWNER"

    ws = await client.get(
        f"/api/v1/organizations/{t['org_id']}/workspaces", headers=t["headers"]
    )
    assert ws.status_code == 200
    assert t["ws_id"] in [w["id"] for w in ws.json()]


@pytest.mark.asyncio
async def test_cannot_list_other_orgs_workspaces(client: AsyncClient, make_tenant):
    a = await make_tenant("disco-a@test.io", key="DSA")
    b = await make_tenant("disco-b@test.io", key="DSB")
    r = await client.get(
        f"/api/v1/organizations/{b['org_id']}/workspaces", headers=a["headers"]
    )
    assert r.status_code == 403
