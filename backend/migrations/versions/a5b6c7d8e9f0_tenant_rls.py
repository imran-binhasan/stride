"""Enforce tenant isolation for domain data, including children without org_id.

Authentication/organization directory and inbound integration routing stay in the
application authorization layer. Domain data defaults to denied without context.
"""

from alembic import op
import sqlalchemy as sa

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None

DIRECT = [
    "workspaces",
    "departments",
    "teams",
    "projects",
    "labels",
    "tasks",
    "time_entries",
    "employee_profiles",
    "leave_requests",
    "payroll_runs",
    "client_contacts",
    "notifications",
    "audit_logs",
    "subscriptions",
    "invoices",
]
CHILDREN = {
    "sprints": ("projects", "project_id"),
    "workflow_statuses": ("projects", "project_id"),
    "project_access_grants": ("projects", "project_id"),
    "task_assignees": ("tasks", "task_id"),
    "task_labels": ("tasks", "task_id"),
    "task_watchers": ("tasks", "task_id"),
    "comments": ("tasks", "task_id"),
    "attachments": ("tasks", "task_id"),
    "checklist_items": ("tasks", "task_id"),
    "figma_links": ("tasks", "task_id"),
    "activity_telemetries": ("time_entries", "time_entry_id"),
    "screenshot_logs": ("time_entries", "time_entry_id"),
    "payroll_items": ("payroll_runs", "payroll_run_id"),
    "team_members": ("teams", "team_id"),
    "client_project_access": ("client_contacts", "client_contact_id"),
}


def policy(table, predicate):
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY tenant_scope ON "{table}" USING ({predicate}) WITH CHECK ({predicate})'
    )


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    inspector = sa.inspect(bind)
    names = set(inspector.get_table_names())
    for table in DIRECT:
        if table in names:
            policy(table, "org_id = nullif(current_setting('stride.org_id', true), '')")
    for table, (parent, key) in CHILDREN.items():
        if table in names:
            policy(table, f'EXISTS (SELECT 1 FROM "{parent}" p WHERE p.id = "{table}"."{key}")')
    policy(
        "task_dependencies",
        "EXISTS (SELECT 1 FROM tasks p WHERE p.id = task_dependencies.predecessor_id) AND EXISTS (SELECT 1 FROM tasks p WHERE p.id = task_dependencies.successor_id)",
    )

    op.execute(
        "CREATE POLICY audit_no_update ON audit_logs AS RESTRICTIVE FOR UPDATE USING (false)"
    )
    op.execute(
        "CREATE POLICY audit_no_delete ON audit_logs AS RESTRICTIVE FOR DELETE USING (false)"
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    names = set(sa.inspect(bind).get_table_names())
    op.execute("DROP POLICY IF EXISTS audit_no_update ON audit_logs")
    op.execute("DROP POLICY IF EXISTS audit_no_delete ON audit_logs")
    for table in [*DIRECT, *CHILDREN, "task_dependencies"]:
        if table in names:
            op.execute(f'DROP POLICY IF EXISTS tenant_scope ON "{table}"')
            op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
