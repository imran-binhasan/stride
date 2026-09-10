"""Full RBAC refactor: teams, departments, licenses, client portal, HR, billing, notifications, task types

Revision ID: c1a2b3d4e5f6
Revises: bf0d42eb4aa8
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "bf0d42eb4aa8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. organizations — add new columns ────────────────────────────────────
    with op.batch_alter_table("organizations") as batch:
        batch.add_column(sa.Column("logo_url", sa.String(512), nullable=True))
        batch.add_column(sa.Column("deployment_type", sa.String(20), server_default="SAAS", nullable=False))
        batch.add_column(sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("is_trial_used", sa.Boolean(), server_default=sa.text("0"), nullable=False))
        batch.add_column(sa.Column("max_members", sa.Integer(), server_default="5", nullable=False))
        batch.add_column(sa.Column("max_projects", sa.Integer(), server_default="3", nullable=False))
        batch.add_column(sa.Column("max_storage_gb", sa.Integer(), server_default="5", nullable=False))
        # Rename subscription_tier from varchar to enum-backed varchar (no-op for SQLite, fine for Postgres)
        batch.alter_column("subscription_tier", type_=sa.String(20), existing_type=sa.String(50))

    # ── 2. licenses ───────────────────────────────────────────────────────────
    op.create_table(
        "licenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("license_key", sa.String(255), unique=True, nullable=False),
        sa.Column("licensed_email", sa.String(255), nullable=False),
        sa.Column("max_seats", sa.Integer(), server_default="10", nullable=False),
        sa.Column("tier", sa.String(20), server_default="STARTER", nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── 3. users — add profile fields ─────────────────────────────────────────
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("phone", sa.String(50), nullable=True))
        batch.add_column(sa.Column("timezone", sa.String(60), server_default="UTC", nullable=False))
        batch.add_column(sa.Column("locale", sa.String(10), server_default="en", nullable=False))

    # ── 4. org_members — full lifecycle refactor ──────────────────────────────
    with op.batch_alter_table("org_members") as batch:
        batch.add_column(sa.Column("email", sa.String(255), nullable=True))  # backfilled below
        batch.add_column(sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False))
        batch.add_column(sa.Column("invite_token", sa.String(255), nullable=True))
        batch.add_column(sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("invited_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
        batch.add_column(sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("user_id", nullable=True)

    # Backfill email from users table
    op.execute(
        "UPDATE org_members SET email = (SELECT email FROM users WHERE users.id = org_members.user_id)"
        " WHERE email IS NULL"
    )

    with op.batch_alter_table("org_members") as batch:
        batch.alter_column("email", nullable=False)
        # Replace unique(org_id, user_id) with unique(org_id, email)
        batch.drop_constraint("uq_org_member", type_="unique")
        batch.create_unique_constraint("uq_org_member_email", ["org_id", "email"])

    # ── 5. departments ────────────────────────────────────────────────────────
    op.create_table(
        "departments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("head_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── 6. teams ──────────────────────────────────────────────────────────────
    op.create_table(
        "teams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("department_id", sa.String(36), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("identifier", sa.String(20), nullable=False),
        sa.Column("color", sa.String(20), server_default="#6B7280", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "team_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("role", sa.String(10), server_default="MEMBER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_member"),
    )

    # ── 7. client_contacts ────────────────────────────────────────────────────
    op.create_table(
        "client_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), index=True, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "client_project_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_contact_id", sa.String(36), sa.ForeignKey("client_contacts.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("can_create_tickets", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("can_comment", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("can_view_timesheets", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("granted_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("client_contact_id", "project_id", name="uq_client_project_access"),
    )

    # ── 8. projects — add new columns ─────────────────────────────────────────
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False))
        batch.add_column(sa.Column("color", sa.String(20), server_default="#6B7280", nullable=False))
        batch.add_column(sa.Column("icon", sa.String(50), nullable=True))
        batch.add_column(sa.Column("start_date", sa.Date, nullable=True))
        batch.add_column(sa.Column("target_date", sa.Date, nullable=True))
        batch.add_column(sa.Column("client_contact_id", sa.String(36), sa.ForeignKey("client_contacts.id", ondelete="SET NULL"), nullable=True))
        batch.add_column(sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    # ── 9. project_access_grants ──────────────────────────────────────────────
    op.create_table(
        "project_access_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("grantee_type", sa.String(10), nullable=False),
        sa.Column("grantee_id", sa.String(36), index=True, nullable=False),
        sa.Column("granted_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "grantee_type", "grantee_id", name="uq_project_grant"),
    )

    # ── 10. sprints — replace is_active/is_closed with status ─────────────────
    with op.batch_alter_table("sprints") as batch:
        batch.add_column(sa.Column("status", sa.String(20), server_default="PLANNED", nullable=False))

    # Migrate: is_active=True → ACTIVE, is_closed=True → COMPLETED, else PLANNED
    op.execute(
        "UPDATE sprints SET status = 'ACTIVE' WHERE is_active = 1 AND (is_closed IS NULL OR is_closed = 0)"
    )
    op.execute(
        "UPDATE sprints SET status = 'COMPLETED' WHERE is_closed = 1"
    )

    with op.batch_alter_table("sprints") as batch:
        batch.drop_column("is_active")
        batch.drop_column("is_closed")

    # ── 11. labels (org-level) ────────────────────────────────────────────────
    op.create_table(
        "labels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(20), server_default="#6B7280", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_label_org_name"),
    )

    # ── 12. tasks — add new columns, drop subtasks ────────────────────────────
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("type", sa.String(20), server_default="TASK", nullable=False))
        batch.add_column(sa.Column("parent_task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True))
        batch.add_column(sa.Column("start_date", sa.Date, nullable=True))
        batch.add_column(sa.Column("is_client_ticket", sa.Boolean(), server_default=sa.text("0"), nullable=False))
        batch.create_index("ix_tasks_parent_task_id", ["parent_task_id"])

    # Migrate subtasks → tasks with parent_task_id
    op.execute(
        "INSERT INTO tasks (id, org_id, project_id, short_id, title, status_id, creator_id, type, parent_task_id, priority, position, custom_fields, is_client_ticket, created_at, updated_at)"
        " SELECT id, (SELECT org_id FROM tasks t2 WHERE t2.id = subtasks.task_id), (SELECT project_id FROM tasks t2 WHERE t2.id = subtasks.task_id),"
        " 'SUB-' || id, title, (SELECT status_id FROM tasks t2 WHERE t2.id = subtasks.task_id),"
        " (SELECT creator_id FROM tasks t2 WHERE t2.id = subtasks.task_id),"
        " 'TASK', task_id, 'MEDIUM', position, '{}', 0, created_at, updated_at"
        " FROM subtasks"
    )

    op.drop_table("subtasks")

    # ── 13. task_assignees ────────────────────────────────────────────────────
    op.create_table(
        "task_assignees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_assignee"),
    )

    # Seed task_assignees from tasks.assignee_id
    op.execute(
        "INSERT INTO task_assignees (id, task_id, user_id, created_at, updated_at)"
        " SELECT hex(randomblob(16)), id, assignee_id, created_at, updated_at"
        " FROM tasks WHERE assignee_id IS NOT NULL"
    )

    # ── 14. task_watchers ─────────────────────────────────────────────────────
    op.create_table(
        "task_watchers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_watcher"),
    )

    # ── 15. task_labels ───────────────────────────────────────────────────────
    op.create_table(
        "task_labels",
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("label_id", sa.String(36), sa.ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
    )

    # ── 16. comments ─────────────────────────────────────────────────────────
    op.create_table(
        "comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_internal", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("parent_comment_id", sa.String(36), sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── 17. attachments ───────────────────────────────────────────────────────
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("comment_id", sa.String(36), sa.ForeignKey("comments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── 18. employee_profiles ─────────────────────────────────────────────────
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), index=True, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("department_id", sa.String(36), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("manager_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("employee_id", sa.String(50), nullable=False),
        sa.Column("job_title", sa.String(255), nullable=False),
        sa.Column("employment_type", sa.String(20), server_default="FULL_TIME", nullable=False),
        sa.Column("hire_date", sa.Date, nullable=False),
        sa.Column("termination_date", sa.Date, nullable=True),
        sa.Column("work_hours_per_week", sa.Float, server_default="40.0", nullable=False),
        sa.Column("hourly_rate", sa.Numeric(10, 2), server_default="0.0", nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "employee_id", name="uq_employee_id_per_org"),
        sa.UniqueConstraint("org_id", "user_id", name="uq_employee_profile_user"),
    )

    # ── 19. leave_requests ────────────────────────────────────────────────────
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), index=True, nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employee_profiles.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="PENDING", nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("days_count", sa.Float, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("approved_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── 20. payroll_runs & payroll_items ──────────────────────────────────────
    op.create_table(
        "payroll_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), index=True, nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), server_default="0.0", nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("processed_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "payroll_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payroll_run_id", sa.String(36), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employee_profiles.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("regular_hours", sa.Float, server_default="0.0", nullable=False),
        sa.Column("overtime_hours", sa.Float, server_default="0.0", nullable=False),
        sa.Column("gross_amount", sa.Numeric(10, 2), server_default="0.0", nullable=False),
        sa.Column("deductions", sa.Numeric(10, 2), server_default="0.0", nullable=False),
        sa.Column("net_amount", sa.Numeric(10, 2), server_default="0.0", nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("status", sa.String(20), server_default="PENDING", nullable=False),
        sa.Column("payment_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── 21. subscription_plans, subscriptions, invoices ───────────────────────
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("price_monthly", sa.Numeric(10, 2), server_default="0.0", nullable=False),
        sa.Column("price_yearly", sa.Numeric(10, 2), server_default="0.0", nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("max_members", sa.Integer, server_default="5", nullable=False),
        sa.Column("max_projects", sa.Integer, server_default="3", nullable=False),
        sa.Column("max_storage_gb", sa.Integer, server_default="5", nullable=False),
        sa.Column("feature_flags", sa.JSON, nullable=False),
        sa.Column("stripe_price_id_monthly", sa.String(255), nullable=True),
        sa.Column("stripe_price_id_yearly", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, index=True, nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), server_default="TRIALING", nullable=False),
        sa.Column("trial_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), unique=True, nullable=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_invoice_id", sa.String(255), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── 22. notifications & audit_logs ────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("org_id", sa.String(36), index=True, nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), index=True, nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("old_values", sa.JSON, nullable=True),
        sa.Column("new_values", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), index=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
    op.drop_table("subscription_plans")
    op.drop_table("payroll_items")
    op.drop_table("payroll_runs")
    op.drop_table("leave_requests")
    op.drop_table("employee_profiles")
    op.drop_table("attachments")
    op.drop_table("comments")
    op.drop_table("task_labels")
    op.drop_table("task_watchers")
    op.drop_table("task_assignees")
    op.drop_table("labels")
    op.drop_table("project_access_grants")
    op.drop_table("client_project_access")
    op.drop_table("client_contacts")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_table("departments")
    op.drop_table("licenses")
    # Note: column drops and constraint restores for the upgrade alterations are omitted
    # (downgrade to a pre-refactor state is destructive; handle via point-in-time restore)
