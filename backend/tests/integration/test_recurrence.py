from datetime import date

import pytest
from src.schemas.recurrence import RecurrenceRule
from src.services.recurrence_service import next_due


@pytest.mark.parametrize(
    ("rule", "current", "expected"),
    [
        ({"frequency": "MONTHLY"}, date(2026, 1, 31), date(2026, 2, 28)),
        ({"frequency": "WEEKLY", "weekdays": [0, 2]}, date(2026, 11, 16), date(2026, 11, 18)),
        (
            {"frequency": "WEEKLY", "weekdays": [0], "interval": 2},
            date(2026, 11, 16),
            date(2026, 11, 30),
        ),
        ({"frequency": "CRON", "cron": "0 9 * * 1"}, date(2026, 11, 16), date(2026, 11, 23)),
        ({"frequency": "DAILY", "until": "2026-11-16"}, date(2026, 11, 16), None),
    ],
)
def test_next_due(rule, current, expected):
    assert next_due(RecurrenceRule.model_validate(rule), current) == expected


@pytest.mark.asyncio
async def test_complete_recurring_task_creates_next_only_once(client, make_tenant):
    tenant = await make_tenant("recurring@example.com")
    task = tenant["task"]
    base = "/api/v1/tasks/" + task["id"]
    headers = tenant["headers"]
    configured = await client.patch(
        base, headers=headers, json={"due_date": "2026-11-16", "recurrence": {"frequency": "DAILY"}}
    )
    assert configured.status_code == 200, configured.text
    done = next(s["id"] for s in tenant["project"]["statuses"] if s["category"] == "DONE")
    for _ in range(2):
        response = await client.patch(
            base + "/move", headers=headers, json={"status_id": done, "new_position": 1000}
        )
        assert response.status_code == 200, response.text
    tasks = (
        await client.get("/api/v1/tasks/project/" + task["project_id"], headers=headers)
    ).json()
    assert len(tasks) == 2
    following = next(t for t in tasks if t["id"] != task["id"])
    assert following["due_date"] == "2026-11-17"
    assert following["recurrence"]["frequency"] == "DAILY"
    assert following["status_id"] != done
