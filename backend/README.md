# Stride API

FastAPI, async SQLAlchemy, Redis, and S3-compatible storage for Stride’s core team workflow.

The implemented API includes organizations/workspaces/members; projects/statuses/sprints; tasks/subtasks/checklists/comments/dependencies/assignments/labels/watchers/attachments; board/calendar/table/Gantt views; timers/manual time/approval workflows; notifications/audit logs; and incoming GitHub/Figma integration support.

Authenticated REST requests use `Authorization: Bearer <access token>` and `X-Org-ID`. Realtime uses `/api/v1/ws/realtime?token=...&org_id=...` and verifies active membership and room access. The web app handles token rotation and organization selection.

Read [core scope and verification](../docs/CORE_WORKFLOW_STATUS.md) before deployment. Full SRS features are not all implemented. AI execution results remain unverified until an isolated `AI_RUNNER_URL` is configured; returned worker results must include `execution_status: completed`, actual test counts, and optional measured coverage. Submitted Python is never executed in the API process.

## Setup

```bash
uv sync --extra dev
uv run --extra dev uvicorn src.main:app --reload --port 8000
```

See [.env.example](.env.example). Run database upgrades using `uv run alembic upgrade head`. The historical refactor migration was repaired for portable SQL and named constraints; a new migration adds checklists, WIP limits, legacy-role normalization, and the one-running-timer constraint.

Configure `S3_PUBLIC_ENDPOINT_URL` for browser uploads/downloads and `S3_ENDPOINT_URL` for server storage access. Configure the GitHub repository webhook to POST to `/api/v1/integrations/github/webhook` using `GITHUB_WEBHOOK_SECRET`. Set `FIGMA_API_ACCESS_TOKEN` to resolve thumbnails through Figma’s API.
