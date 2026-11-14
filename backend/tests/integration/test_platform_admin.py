import pytest
from sqlalchemy import select
from src.models.auth import User


@pytest.mark.asyncio
async def test_operator_directory_and_account_state_are_privileged(client, make_tenant, db_session):
    operator = await make_tenant("platform-operator@example.com")
    employee = await make_tenant("platform-employee@example.com")
    assert (
        await client.get("/api/v1/platform/summary", headers=employee["headers"])
    ).status_code == 403
    user = await db_session.scalar(select(User).where(User.id == operator["user_id"]))
    user.is_superadmin = True
    await db_session.commit()
    summary = await client.get("/api/v1/platform/summary", headers=operator["headers"])
    assert summary.status_code == 200, summary.text
    assert summary.json()["users"] == 2
    users = await client.get("/api/v1/platform/users", headers=operator["headers"])
    assert users.status_code == 200
    assert all("hashed_password" not in u for u in users.json())
    result = await client.patch(
        "/api/v1/platform/users/" + employee["user_id"],
        headers=operator["headers"],
        json={"is_active": False, "reason": "Disabled for verification"},
    )
    assert result.status_code == 200, result.text
    assert (await client.get("/api/v1/auth/me", headers=employee["headers"])).status_code == 401
    assert (
        await client.patch(
            "/api/v1/platform/users/" + operator["user_id"],
            headers=operator["headers"],
            json={"is_active": False, "reason": "Must be rejected"},
        )
    ).status_code == 403
