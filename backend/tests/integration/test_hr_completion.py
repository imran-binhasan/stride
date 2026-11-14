from datetime import UTC, datetime, timedelta

import pytest


async def employee(client, tenant, user_id, code, rate=25):
    result = await client.post(
        "/api/v1/hr/employees",
        headers=tenant["headers"],
        json={
            "user_id": user_id,
            "employee_id": code,
            "job_title": "Engineer",
            "hire_date": "2026-01-01",
            "hourly_rate": rate,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


@pytest.mark.asyncio
async def test_payroll_uses_approved_time_and_decimal_rounding(client, make_tenant):
    owner = await make_tenant("payroll-owner@example.com")
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "payroll-member@example.com",
            "password": "Password12345!",
            "full_name": "Payroll Member",
        },
    )
    user = reg.json()["data"]["user"]
    tokens = reg.json()["data"]["tokens"]
    await client.post(
        f"/api/v1/organizations/{owner['org_id']}/members",
        headers=owner["headers"],
        json={"email": user["email"], "role": "MEMBER"},
    )
    headers = {"Authorization": "Bearer " + tokens["access_token"], "X-Org-ID": owner["org_id"]}
    profile = await employee(client, owner, user["id"], "E001", rate=25.75)
    await employee(client, owner, owner["user_id"], "E002")
    # Ordinary employees can only see their own salary and leave records.
    profiles = await client.get("/api/v1/hr/employees", headers=headers)
    assert [p["id"] for p in profiles.json()] == [profile["id"]]
    assert (await client.get("/api/v1/hr/payroll/runs", headers=headers)).status_code == 403
    now = datetime.now(UTC)
    start = now - timedelta(hours=2)
    end = start + timedelta(hours=1)
    created = await client.post(
        "/api/v1/time-tracking/entries",
        headers=headers,
        json={
            "task_id": owner["task"]["id"],
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )
    entry = created.json()["id"]
    await client.post(f"/api/v1/time-tracking/entries/{entry}/submit", headers=headers)
    await client.post(
        f"/api/v1/time-tracking/entries/{entry}/review",
        headers=owner["headers"],
        json={"status": "APPROVED"},
    )
    payload = {"period_start": start.date().isoformat(), "period_end": now.date().isoformat()}
    result = await client.post("/api/v1/hr/payroll/runs", headers=owner["headers"], json=payload)
    assert result.status_code == 201, result.text
    assert result.json()["total_amount"] == 25.75
    item = next(i for i in result.json()["items"] if i["employee_id"] == profile["id"])
    assert item["regular_hours"] == 1
    assert item["net_amount"] == 25.75
    assert (
        await client.post("/api/v1/hr/payroll/runs", headers=owner["headers"], json=payload)
    ).status_code == 409


@pytest.mark.asyncio
async def test_foreign_employee_and_self_leave_review_rejected(client, make_tenant):
    a = await make_tenant("hr-a@example.com")
    b = await make_tenant("hr-b@example.com")
    bad = await client.post(
        "/api/v1/hr/employees",
        headers=a["headers"],
        json={
            "user_id": b["user_id"],
            "employee_id": "BAD",
            "job_title": "Engineer",
            "hire_date": "2026-01-01",
        },
    )
    assert bad.status_code == 422
    await employee(client, a, a["user_id"], "OWNER")
    leave = await client.post(
        "/api/v1/hr/leaves",
        headers=a["headers"],
        json={
            "type": "VACATION",
            "start_date": "2026-12-01",
            "end_date": "2026-12-02",
            "days_count": 2,
        },
    )
    assert leave.status_code == 201, leave.text
    reviewed = await client.patch(
        "/api/v1/hr/leaves/" + leave.json()["id"], headers=a["headers"], json={"status": "APPROVED"}
    )
    assert reviewed.status_code == 422
