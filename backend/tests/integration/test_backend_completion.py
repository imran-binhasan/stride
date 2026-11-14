"""Behavior and security regressions for backend completion work."""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from src.models.task import TaskAssignee


async def member_in(client, owner, email):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password12345!", "full_name": "Team Member"},
    )
    assert reg.status_code == 201
    added = await client.post(
        f"/api/v1/organizations/{owner['org_id']}/members",
        headers=owner["headers"],
        json={"email": email, "role": "MEMBER"},
    )
    assert added.status_code == 201, added.text
    return {
        "Authorization": "Bearer " + reg.json()["data"]["tokens"]["access_token"],
        "X-Org-ID": owner["org_id"],
    }


@pytest.mark.asyncio
async def test_nested_tasks_clear_fields_and_cycles(client, make_tenant):
    a = await make_tenant("completion-task@test.io", key="CTA")
    base = "/api/v1/tasks/" + a["task"]["id"]
    child = await client.post(
        base + "/subtasks", headers=a["headers"], json={"title": "Child", "position": 2}
    )
    assert child.status_code == 201, child.text
    task = await client.get(base, headers=a["headers"])
    assert task.json()["children"][0]["id"] == child.json()["id"]
    assert task.json()["subtasks"][0]["is_completed"] is False
    cycle = await client.patch(
        base, headers=a["headers"], json={"parent_task_id": child.json()["id"]}
    )
    assert cycle.status_code == 409
    assert (
        await client.patch(base, headers=a["headers"], json={"due_date": "2026-11-01"})
    ).status_code == 200
    cleared = await client.patch(base, headers=a["headers"], json={"due_date": None})
    assert cleared.json()["due_date"] is None
    assert (
        await client.patch(base, headers=a["headers"], json={"title": "   "})
    ).status_code == 422
    assert (await client.delete(base, headers=a["headers"])).status_code == 204
    assert (
        await client.get("/api/v1/tasks/" + child.json()["id"], headers=a["headers"])
    ).status_code == 404


@pytest.mark.asyncio
async def test_reject_foreign_task_links_and_comments(client, make_tenant):
    a = await make_tenant("completion-links-a@test.io", key="CLA")
    b = await make_tenant("completion-links-b@test.io", key="CLB")
    result = await client.post(
        "/api/v1/tasks",
        headers=a["headers"],
        json={
            "project_id": a["project"]["id"],
            "title": "Bad parent",
            "parent_task_id": b["task"]["id"],
        },
    )
    assert result.status_code == 422
    comment = await client.post(
        f"/api/v1/tasks/{b['task']['id']}/comments",
        headers=b["headers"],
        json={"content": "Private"},
    )
    assert comment.status_code == 201, comment.text
    cid = comment.json()["id"]
    assert (
        await client.delete("/api/v1/tasks/comments/" + cid, headers=a["headers"])
    ).status_code == 404
    bad_reply = await client.post(
        f"/api/v1/tasks/{a['task']['id']}/comments",
        headers=a["headers"],
        json={"content": "Reply", "parent_comment_id": cid},
    )
    assert bad_reply.status_code == 422


@pytest.mark.asyncio
async def test_checklists_labels_assignees_and_watchers(client, make_tenant, db_session):
    a = await make_tenant("completion-resources@test.io", key="CRA")
    base = "/api/v1/tasks/" + a["task"]["id"]
    item = await client.post(
        base + "/checklist", headers=a["headers"], json={"title": "Acceptance check"}
    )
    assert item.status_code == 201, item.text
    done = await client.patch(
        base + "/checklist/" + item.json()["id"], headers=a["headers"], json={"is_completed": True}
    )
    assert done.json()["is_completed"] is True
    assert len((await client.get(base + "/checklist", headers=a["headers"])).json()) == 1
    label = await client.post(
        "/api/v1/projects/labels", headers=a["headers"], json={"name": "backend"}
    )
    assert label.status_code == 201
    assert (await client.get("/api/v1/projects/labels", headers=a["headers"])).status_code == 200
    assert (
        await client.put(base + "/labels/" + label.json()["id"], headers=a["headers"])
    ).status_code == 204
    data = (await client.get(base, headers=a["headers"])).json()
    assert data["labels"][0]["label"]["name"] == "backend"
    for _ in range(2):
        assert (
            await client.put(base + "/assignees/" + a["user_id"], headers=a["headers"])
        ).status_code == 204
        assert (await client.put(base + "/watch", headers=a["headers"])).status_code == 204
    rows = list(
        await db_session.scalars(
            select(TaskAssignee).where(TaskAssignee.task_id == a["task"]["id"])
        )
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_manual_time_approval_ownership_and_overlap(client, make_tenant):
    owner = await make_tenant("completion-time-owner@test.io", key="CTO")
    headers = await member_in(client, owner, "completion-time-member@test.io")
    now = datetime.now(UTC)
    payload = {
        "task_id": owner["task"]["id"],
        "start_time": (now - timedelta(hours=2)).isoformat(),
        "end_time": (now - timedelta(hours=1)).isoformat(),
    }
    created = await client.post("/api/v1/time-tracking/entries", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["total_seconds"] == 3600
    eid = created.json()["id"]
    base = "/api/v1/time-tracking/entries/" + eid
    assert (
        await client.post("/api/v1/time-tracking/entries", headers=headers, json=payload)
    ).status_code == 409
    assert (await client.post(base + "/submit", headers=owner["headers"])).status_code == 403
    assert (await client.post(base + "/submit", headers=headers)).json()["status"] == "SUBMITTED"
    assert (
        await client.post(base + "/review", headers=headers, json={"status": "APPROVED"})
    ).status_code == 403
    reviewed = await client.post(
        base + "/review", headers=owner["headers"], json={"status": "APPROVED"}
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "APPROVED"
    assert (await client.delete(base, headers=headers)).status_code == 409


@pytest.mark.asyncio
async def test_timer_cannot_be_stopped_by_another_member(client, make_tenant):
    owner = await make_tenant("completion-timer-owner@test.io", key="CTR")
    headers = await member_in(client, owner, "completion-timer-member@test.io")
    timer = await client.post(
        "/api/v1/time-tracking/timer/start", headers=headers, json={"task_id": owner["task"]["id"]}
    )
    assert timer.status_code == 201
    result = await client.post(
        "/api/v1/time-tracking/timer/stop",
        headers=owner["headers"],
        json={"time_entry_id": timer.json()["id"]},
    )
    assert result.status_code == 422
    active = await client.get("/api/v1/time-tracking/timer/active", headers=headers)
    assert active.json()["id"] == timer.json()["id"]
    stopped = await client.post("/api/v1/time-tracking/timer/stop", headers=headers, json={})
    assert stopped.status_code == 200, stopped.text


@pytest.mark.asyncio
async def test_table_and_calendar_export(client, make_tenant):
    a = await make_tenant("completion-views@test.io", key="CVA")
    pid = a["project"]["id"]
    await client.patch(
        "/api/v1/tasks/" + a["task"]["id"],
        headers=a["headers"],
        json={"title": "Due, task", "due_date": "2026-11-02"},
    )
    table = await client.get(
        f"/api/v1/views/table/{pid}?search=Due&sort_by=title", headers=a["headers"]
    )
    assert table.status_code == 200, table.text
    assert table.json()["total"] == 1
    assert table.json()["items"][0]["title"] == "Due, task"
    calendar = await client.get(f"/api/v1/views/calendar/{pid}/export.ics", headers=a["headers"])
    assert calendar.status_code == 200, calendar.text
    assert "BEGIN:VCALENDAR" in calendar.text
    assert "DTSTART;VALUE=DATE:20261102" in calendar.text
    assert "SUMMARY:Due\\, task" in calendar.text


@pytest.mark.asyncio
async def test_attachment_upload_reservation_and_retry(client, make_tenant):
    a = await make_tenant("completion-upload@test.io", key="CUA")
    base = "/api/v1/tasks/" + a["task"]["id"] + "/attachments"
    upload = await client.post(
        base + "/upload-url",
        headers=a["headers"],
        json={"file_name": "spec.txt", "file_size": 10, "mime_type": "text/plain"},
    )
    assert upload.status_code == 200, upload.text
    aid = upload.json()["attachment_id"]
    for _ in range(2):
        result = await client.post(
            base + "/confirm", headers=a["headers"], json={"attachment_id": aid}
        )
        assert result.status_code == 201, result.text
        assert result.json()["id"] == aid
    url = await client.get(base + "/" + aid + "/download-url", headers=a["headers"])
    assert url.status_code == 200
    assert "X-Amz-Signature" in url.json()["download_url"]


@pytest.mark.asyncio
async def test_client_requires_project_grant_and_hides_internal_comments(client, make_tenant):
    owner = await make_tenant("completion-client-owner@test.io", key="CCO")
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "completion-client@test.io",
            "password": "Password12345!",
            "full_name": "Client User",
        },
    )
    user = reg.json()["data"]["user"]
    await client.post(
        f"/api/v1/organizations/{owner['org_id']}/members",
        headers=owner["headers"],
        json={"email": user["email"], "role": "CLIENT"},
    )
    headers = {
        "Authorization": "Bearer " + reg.json()["data"]["tokens"]["access_token"],
        "X-Org-ID": owner["org_id"],
    }
    base = "/api/v1/tasks/" + owner["task"]["id"]
    assert (await client.get(base, headers=headers)).status_code == 403
    contact = await client.post(
        "/api/v1/clients",
        headers=owner["headers"],
        json={"user_id": user["id"], "company_name": "Client"},
    )
    assert contact.status_code == 201, contact.text
    grant = await client.post(
        "/api/v1/clients/" + contact.json()["id"] + "/project-access",
        headers=owner["headers"],
        json={"project_id": owner["project"]["id"]},
    )
    assert grant.status_code == 201, grant.text
    await client.post(
        base + "/comments",
        headers=owner["headers"],
        json={"content": "Internal only", "is_internal": True},
    )
    task = await client.get(base, headers=headers)
    assert task.status_code == 200, task.text
    assert task.json()["comments"] == []


def test_fresh_migration_chain(tmp_path):
    backend = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DATABASE_URL": "sqlite+aiosqlite:///" + str(tmp_path / "migration.db")}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
async def test_last_owner_cannot_be_removed(client, make_tenant):
    owner = await make_tenant("completion-last-owner@test.io", key="CLO")
    members = await client.get(
        f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"]
    )
    member = next(m for m in members.json() if m["email"] == owner["email"])
    result = await client.patch(
        f"/api/v1/organizations/{owner['org_id']}/members/{member['id']}",
        headers=owner["headers"],
        json={"status": "SUSPENDED"},
    )
    assert result.status_code == 409
    still_active = await client.get(
        f"/api/v1/organizations/{owner['org_id']}", headers=owner["headers"]
    )
    assert still_active.status_code == 200


@pytest.mark.asyncio
async def test_screenshot_reservation_and_delete_idempotency(client, make_tenant):
    a = await make_tenant("completion-shots@test.io", key="CSH")
    start = await client.post(
        "/api/v1/time-tracking/timer/start", headers=a["headers"], json={"task_id": a["task"]["id"]}
    )
    entry = start.json()["id"]
    issue = await client.post(
        "/api/v1/time-tracking/screenshots/presigned-url",
        headers=a["headers"],
        json={"time_entry_id": entry},
    )
    data = issue.json()
    payload = {
        "screenshot_id": data["screenshot_id"],
        "s3_key": data["s3_key"],
        "time_entry_id": entry,
    }
    forged = {**payload, "s3_key": data["s3_key"] + ".forged"}
    assert (
        await client.post(
            "/api/v1/time-tracking/screenshots/confirm", headers=a["headers"], json=forged
        )
    ).status_code == 422
    for _ in range(2):
        assert (
            await client.post(
                "/api/v1/time-tracking/screenshots/confirm", headers=a["headers"], json=payload
            )
        ).status_code == 201
    for _ in range(2):
        assert (
            await client.delete(
                "/api/v1/time-tracking/screenshots/" + data["screenshot_id"], headers=a["headers"]
            )
        ).status_code == 200
    assert (
        await client.post("/api/v1/time-tracking/timer/stop", headers=a["headers"], json={})
    ).status_code == 200


@pytest.mark.asyncio
async def test_timer_restart_stops_previous_entry(client, make_tenant):
    a = await make_tenant("completion-restart@test.io", key="CRT")
    ids = []
    for _ in range(2):
        result = await client.post(
            "/api/v1/time-tracking/timer/start",
            headers=a["headers"],
            json={"task_id": a["task"]["id"]},
        )
        assert result.status_code == 201, result.text
        ids.append(result.json()["id"])
    entries = await client.get("/api/v1/time-tracking/entries", headers=a["headers"])
    assert len([e for e in entries.json() if e["end_time"] is None]) == 1
    assert ids[0] != ids[1]


@pytest.mark.asyncio
async def test_wip_warning_and_sprint_metrics(client, make_tenant):
    a = await make_tenant("completion-wip@test.io", key="CWP")
    pid = a["project"]["id"]
    state = a["task"]["status_id"]
    patch = await client.patch(
        f"/api/v1/projects/{pid}/statuses/{state}", headers=a["headers"], json={"wip_limit": 1}
    )
    assert patch.status_code == 200, patch.text
    await client.post(
        "/api/v1/tasks", headers=a["headers"], json={"project_id": pid, "title": "Second"}
    )
    board = await client.get(f"/api/v1/views/kanban/{pid}", headers=a["headers"])
    assert (
        next(c for c in board.json()["columns"] if c["status"]["id"] == state)["wip_exceeded"]
        is True
    )
    sprint = await client.post(
        f"/api/v1/projects/{pid}/sprints", headers=a["headers"], json={"name": "Sprint 1"}
    )
    assert sprint.status_code == 201
    sid = sprint.json()["id"]
    await client.patch(
        "/api/v1/tasks/" + a["task"]["id"],
        headers=a["headers"],
        json={"sprint_id": sid, "story_points": 5},
    )
    metrics = await client.get(
        f"/api/v1/projects/{pid}/sprints/{sid}/metrics", headers=a["headers"]
    )
    assert metrics.json()["total_points"] == 5


@pytest.mark.asyncio
async def test_invitation_reissue_revokes_previous_token(client, make_tenant):
    owner = await make_tenant("renew-owner@test.io", key="RNO")
    endpoint = f"/api/v1/organizations/{owner['org_id']}/members/invite"
    payload = {"email": "renew-invite@example.com", "role": "MEMBER"}
    first = await client.post(endpoint, headers=owner["headers"], json=payload)
    second = await client.post(endpoint, headers=owner["headers"], json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()["invite_token"] != second.json()["invite_token"]
    accept = {
        "token": first.json()["invite_token"],
        "full_name": "Invite User",
        "password": "Password12345!",
    }
    assert (
        await client.post("/api/v1/organizations/invites/accept", json=accept)
    ).status_code == 401
    accept["token"] = second.json()["invite_token"]
    assert (
        await client.post("/api/v1/organizations/invites/accept", json=accept)
    ).status_code == 200


@pytest.mark.asyncio
async def test_explicit_client_project_grant_is_read_only(client, make_tenant):
    owner = await make_tenant("grant-owner@test.io", key="GRO")
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "granted-client@example.com",
            "password": "Password12345!",
            "full_name": "Read Only Client",
        },
    )
    user = reg.json()["data"]["user"]
    added = await client.post(
        f"/api/v1/organizations/{owner['org_id']}/members",
        headers=owner["headers"],
        json={"email": user["email"], "role": "CLIENT"},
    )
    assert added.status_code == 201
    headers = {
        "Authorization": "Bearer " + reg.json()["data"]["tokens"]["access_token"],
        "X-Org-ID": owner["org_id"],
    }
    path = "/api/v1/tasks/" + owner["task"]["id"]
    assert (await client.get(path, headers=headers)).status_code == 403
    granted = await client.post(
        f"/api/v1/projects/{owner['project']['id']}/access",
        headers=owner["headers"],
        json={"grantee_type": "USER", "grantee_id": user["id"]},
    )
    assert granted.status_code == 201, granted.text
    assert (await client.get(path, headers=headers)).status_code == 200
    assert (
        await client.post(path + "/comments", headers=headers, json={"content": "Not permitted"})
    ).status_code == 403
