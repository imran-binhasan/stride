# Core team workflow status

Scope confirmed on 22 October 2026: finish the core team workflow before enterprise features.

## Implemented

- Organizations and workspaces; member invitations, acceptance, suspension/reactivation, role ceilings, and last-owner protection.
- Projects, workflow statuses and WIP warnings; sprint creation, state changes, and metrics.
- Tasks, nested subtasks, editable dates/assignments/estimates, dependencies, checklists, comments, labels, watchers, attachments, and deletion.
- Kanban, filtered/paginated table, monthly calendar with rescheduling/export, and Gantt/critical-path calculations.
- Timers, manual time entries, overlap/ownership checks, submission/recall, approval/rejection, and audit records.
- Tenant and project access checks, restricted client access, authenticated realtime rooms, and post-commit notifications.
- GitHub incoming webhook automation and Figma links, with real thumbnails when a Figma token is configured.
- Web screens for project/workspace creation, team invitations, sprints, WIP limits, issue editing, time entry and manager review.
- AI responses report execution as unverified when no isolated execution worker is configured. They no longer fabricate test or coverage results.

## Validation

- Backend: **100 passed; 85% measured coverage**. Ruff passes. The Postgres migration/schema test also passes separately against disposable Postgres 16 (101 checks total).
- Frontend: **11 tests pass** and the production build passes.
- Fresh SQLite and Postgres 16 migrations validate, including all mapped Postgres tables and columns. Compose configuration validates.
- Desktop web bundle production build passes; native tracker validation remains a separate milestone.
- Real browser/API checks pass for registration, project/task creation and editing, subtasks, checklists, comments, timers, table view, manual timesheets, submission, invitation acceptance, manager approval, calendar rescheduling and export.
- Desktop (1440 px) and mobile (390 px) layouts inspected; no JavaScript exceptions in the browser checks.
- CI now runs backend/frontend checks and a migration smoke test against a disposable Postgres 16 service.

## Deployment checks still required

Validated again on 14 November 2026. The Postgres migration/schema test passed against a disposable Docker Postgres 16 database. CI runs the same schema check. To repeat against another disposable database:

```bash
cd backend
STRIDE_TEST_POSTGRES_URL='postgresql+asyncpg://user:password@localhost/test_database' \
  uv run --extra dev pytest tests/integration/test_postgres_migrations.py
```

Configure real storage credentials/public endpoint, GitHub webhook secret and repository delivery, and optional Figma credentials. Live provider delivery and real object-storage uploads were not exercised here. Apply migrations with `alembic upgrade head`; the new migration also normalizes legacy role values. The domain refactor cannot safely be downgraded automatically.

## Separate enterprise/desktop work

SSO, database-enforced RLS, recurring tasks, Google Calendar sync, advanced scheduling/reporting, billing/payroll completion, autonomous code execution infrastructure, and the native desktop tracker remain outside this milestone. Full SRS completion and production certification are not claimed.
