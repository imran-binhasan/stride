"""Multi-tenant isolation tests — a user of org A must never reach org B's data."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cannot_read_or_mutate_another_orgs_project_and_task(
    client: AsyncClient, make_tenant
):
    a = await make_tenant("iso-a@test.io", key="AAA")
    b = await make_tenant("iso-b@test.io", key="BBB")

    # A reading B's project -> 404 (org filter hides it)
    r = await client.get(f"/api/v1/projects/{b['project']['id']}", headers=a["headers"])
    assert r.status_code == 404

    # A reading B's task -> 404
    r = await client.get(f"/api/v1/tasks/{b['task']['id']}", headers=a["headers"])
    assert r.status_code == 404

    # A patching B's task -> 404
    r = await client.patch(
        f"/api/v1/tasks/{b['task']['id']}",
        json={"title": "hijacked"},
        headers=a["headers"],
    )
    assert r.status_code == 404

    # A listing tasks in B's project -> empty (scoped by A's org)
    r = await client.get(
        f"/api/v1/tasks/project/{b['project']['id']}", headers=a["headers"]
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_cannot_invite_or_create_workspace_in_another_org(client: AsyncClient, make_tenant):
    a = await make_tenant("iso-c@test.io", key="CCC")
    b = await make_tenant("iso-d@test.io", key="DDD")

    # C1: A is ORG_OWNER of its own org but has no membership in B's org.
    r = await client.post(
        f"/api/v1/organizations/{b['org_id']}/members",
        json={"email": a["email"], "role": "MEMBER"},
        headers=a["headers"],  # header still carries A's own org id
    )
    assert r.status_code == 403

    r = await client.post(
        f"/api/v1/organizations/{b['org_id']}/workspaces",
        json={"name": "Intruder WS"},
        headers=a["headers"],
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_read_cross_org_activity_report(client: AsyncClient, make_tenant):
    a = await make_tenant("iso-e@test.io", key="EEE")
    b = await make_tenant("iso-f@test.io", key="FFF")

    # H1: A is ORG_OWNER (>= PROJECT_MANAGER) but B's user is not in A's org.
    r = await client.get(
        f"/api/v1/time-tracking/reports/daily?user_id={b['user_id']}",
        headers=a["headers"],
    )
    assert r.status_code == 403
