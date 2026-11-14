# Stride implementation and release readiness

Reviewed 14 November 2026. The current branch contains the web application, API, native desktop companion, and the supporting enterprise workflows described below. This is an implementation and local validation report, not a production deployment or third-party certification.

## Implemented

- Organizations, workspaces, membership roles, invitations, projects, statuses, sprints, task hierarchy, comments, checklists, labels, dependencies, attachments, watchers, and audit history.
- Kanban, searchable/filterable/sortable/groupable tables, custom typed project fields and safe numeric formulas, calendar and revocable calendar feeds, Gantt critical paths, milestones, dependencies, and schedule preview/apply.
- Timer tracking, manual time, approval workflows, activity screenshots, idle-time clipping, deletion, and team timesheets.
- HR profiles, leave requests, approved-timesheet payroll calculations, guarded billing and subscription entitlements, and platform administration with audited account actions.
- Google and GitHub OAuth with state/PKCE handling and verified-email checks; GitHub webhook automation and explicitly enabled issue publishing.
- Tenant-scoped PostgreSQL row security, restricted runtime DB role, transaction-pooler configuration, per-project/member quotas, and recurring tasks.
- Isolated AI job runner using resource-limited containers. AI reports only observed test and coverage results.
- Tauri desktop companion with native timer controls, background/tray operation, activity telemetry, screenshot capture/upload, idle recovery, and session handling.
- Compose web/API/database/Redis/object-storage stack, CI checks, Linux desktop package, and release smoke-test script.

## Local verification

Run the checks below from a clean checkout with the listed services available. The release smoke script writes test data, so use a disposable stack/database.

- Backend integration suite: run with disposable PostgreSQL and S3-compatible storage using `STRIDE_TEST_POSTGRES_URL` and `STRIDE_TEST_S3_ENDPOINT`.
- PostgreSQL RLS integration checks: exercised using the restricted runtime role against a disposable PostgreSQL instance.
- Frontend: `npm test -- --run` and `npm run build` from `frontend/`.
- Desktop UI: `npm test -- --run` from `desktop/`; native Rust tests and a Linux release build are run in the CI/container toolchain.
- AI runner: build `runner/Dockerfile.sandbox`, then run `STRIDE_TEST_RUNNER=1 STRIDE_TEST_RUNNER_IMAGE=stride-runner:test uv run --extra dev pytest ../runner/test_runner.py` from `backend/`.
- Full-stack smoke: `backend/.venv/bin/python scripts/smoke_release.py --base http://localhost:<web-port>`.

These checks validate local application behavior. They do not establish production load capacity or validate external OAuth, Stripe, GitHub, or mail-provider accounts.

## Before a production launch

1. Set unique production secrets from `backend/.env.example`; configure Google/GitHub OAuth redirect URIs and Stripe price IDs/webhook; provide scoped GitHub publishing credentials only if publishing is enabled.
2. Deploy PostgreSQL with backups and restore rehearsal, Redis, and private S3-compatible storage. Set browser-reachable `S3_PUBLIC_ENDPOINT_URL`, HTTPS public URLs, bucket lifecycle/encryption, and network access controls.
3. Terminate TLS at a reverse proxy, restrict API and database network exposure, configure allowed origins and OAuth/web base URLs, and verify health checks and log/alert collection.
4. Apply Alembic migrations and bootstrap the first platform operator with `backend/promote_operator.py`; verify that the API uses the restricted non-superuser DB role.
5. If AI execution is enabled, deploy the isolated runner on a dedicated host with Docker access and its own authentication token. Do not expose the Docker socket to the API container.
6. Build, sign, and test platform-specific desktop installers on Windows and macOS. The Linux `.deb` is unsigned; notarization/signing and end-user installation flows have not been verified here.
7. Complete a production-like restore, provider webhook, tenant-isolation, and load test at the deployment's chosen capacity before inviting users.

OAuth provider credentials, Stripe credentials, production infrastructure, signing identities, and load-test targets are environment-specific and were unavailable for this local validation. The source code and Linux build are ready to deploy after these operator steps; no external services or production environment have been provisioned by this change.
