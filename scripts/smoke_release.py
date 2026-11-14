"""End-to-end checks against a disposable Stride Compose stack (creates test data)."""

import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode

import httpx
import websockets


async def smoke(base):
    api = base.rstrip("/") + "/api/v1"
    async with httpx.AsyncClient(timeout=30) as client:
        page = await client.get(base)
        assert page.status_code == 200 and "root" in page.text

        async def request(method, path, headers=None, body=None):
            response = await client.request(method, api + path, headers=headers, json=body)
            assert response.status_code < 300, (
                method,
                path,
                response.status_code,
                response.text[:1000],
            )
            return response.json() if response.content else None

        reg = await request(
            "POST",
            "/auth/register",
            body={
                "email": f"smoke-{uuid.uuid4().hex}@example.com",
                "password": "SmokeTest12345!",
                "full_name": "Release Smoke",
            },
        )
        token = reg["data"]["tokens"]["access_token"]
        headers = {"Authorization": "Bearer " + token}
        org = (await request("GET", "/organizations", headers))[0]
        headers["X-Org-ID"] = org["id"]
        ws = (await request("GET", f"/organizations/{org['id']}/workspaces", headers))[0]
        project = await request(
            "POST",
            "/projects",
            headers,
            {"workspace_id": ws["id"], "name": "Release checks", "key": "SMK"},
        )
        await request(
            "PUT",
            f"/projects/{project['id']}/fields",
            headers,
            {
                "fields": [
                    {"key": "rate", "name": "Rate", "type": "NUMBER"},
                    {
                        "key": "cost",
                        "name": "Cost",
                        "type": "FORMULA",
                        "formula": "estimated_hours * rate",
                    },
                ]
            },
        )
        task = await request(
            "POST",
            "/tasks",
            headers,
            {
                "project_id": project["id"],
                "title": "Ship tested release",
                "estimated_hours": 2,
                "custom_fields": {"rate": 25},
                "due_date": "2026-12-01",
                "recurrence": {"frequency": "WEEKLY"},
            },
        )
        await request(
            "POST",
            f"/tasks/{task['id']}/comments",
            headers,
            {"content": "Deployed API and web proxy are working."},
        )
        await request(
            "POST", f"/tasks/{task['id']}/checklist", headers, {"title": "Verify deployment"}
        )
        table = await request(
            "GET",
            f"/views/table/{project['id']}?sort_by=title,-created_at&group_by=status_id",
            headers,
        )
        assert table["items"][0]["custom_fields"]["cost"] == 50
        schedule = await request(
            "POST",
            f"/views/gantt/{project['id']}/schedule",
            headers,
            {"start_date": "2026-12-01", "preview": True},
        )
        assert schedule["preview"] is True
        await request(
            "POST",
            f"/views/gantt/{project['id']}/schedule",
            headers,
            {"start_date": "2026-12-01", "preview": False},
        )
        timer = await request(
            "POST", "/time-tracking/timer/start", headers, {"task_id": task["id"]}
        )
        png = (
            Path(__file__).resolve().parents[1] / "desktop/src-tauri/icons/icon.png"
        ).read_bytes()
        reservation = await request(
            "POST",
            "/time-tracking/screenshots/presigned-url",
            headers,
            {"time_entry_id": timer["id"], "file_extension": "png", "is_blurred": False},
        )
        uploaded = await client.put(
            reservation["upload_url"], content=png, headers={"Content-Type": "image/png"}
        )
        assert uploaded.status_code == 200, uploaded.text[:200]
        shot = await request(
            "POST",
            "/time-tracking/screenshots/confirm",
            headers,
            {
                "time_entry_id": timer["id"],
                "screenshot_id": reservation["screenshot_id"],
                "s3_key": reservation["s3_key"],
            },
        )
        shots = await request(
            "GET", "/time-tracking/screenshots?time_entry_id=" + timer["id"], headers
        )
        assert len(shots) == 1
        assert (await client.get(shots[0]["download_url"])).content == png
        await request("DELETE", "/time-tracking/screenshots/" + shot["id"], headers)
        await request("POST", "/time-tracking/timer/stop", headers, {"time_entry_id": timer["id"]})
        feed = await request("POST", f"/views/calendar/{project['id']}/feed", headers)
        # Preserve the actual proxy host in this local smoke check.
        from urllib.parse import urlparse

        assert (await client.get(base.rstrip("/") + urlparse(feed["url"]).path)).status_code == 200
        await request("DELETE", f"/views/calendar/{project['id']}/feed", headers)
        wsbase = api.replace("http://", "ws://").replace("https://", "wss://")
        url = wsbase + "/ws/realtime?" + urlencode({"token": token, "org_id": org["id"]})
        room = f"room:org:{org['id']}:project:{project['id']}"
        async with (
            websockets.connect(url, open_timeout=15) as first,
            websockets.connect(url, open_timeout=15) as second,
        ):
            for connection in (first, second):
                await connection.send(json.dumps({"action": "join_room", "room": room}))
                assert (
                    json.loads(await asyncio.wait_for(connection.recv(), 10))["type"]
                    == "ROOM_JOINED"
                )
            await first.send(
                json.dumps(
                    {
                        "action": "broadcast",
                        "room": room,
                        "event": "USER_PRESENCE",
                        "data": {"user_id": "forged", "full_name": "Fake"},
                    }
                )
            )
            presence = json.loads(await asyncio.wait_for(second.recv(), 10))
            assert presence["data"]["user_id"] == reg["data"]["user"]["id"]
            started = time.perf_counter()
            await request(
                "PATCH", "/tasks/" + task["id"], headers, {"title": "Release smoke passed"}
            )
            while True:
                message = json.loads(await asyncio.wait_for(second.recv(), 10))
                if message.get("event") == "TASK_UPDATED":
                    break
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
        billing = await request("GET", "/billing", headers)
        assert billing["tier"] == "FREE"
        await request(
            "POST",
            "/auth/logout",
            headers,
            {"refresh_token": reg["data"]["tokens"]["refresh_token"]},
        )
        print(
            json.dumps(
                {
                    "web": True,
                    "restricted_api": True,
                    "tasks_and_formulas": True,
                    "gantt": True,
                    "real_storage_upload_download_delete": True,
                    "timers": True,
                    "calendar_feed": True,
                    "realtime_and_presence": True,
                    "billing": True,
                    "write_plus_realtime_ms": latency_ms,
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:58080")
    asyncio.run(smoke(parser.parse_args().base))
