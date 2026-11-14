"""Task checklists, WIP limits, and active timer constraint.

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
"""

import sqlalchemy as sa
from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c1a2b3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE org_members SET role = 'MANAGER' WHERE role = 'PROJECT_MANAGER'")
    op.execute("UPDATE org_members SET role = 'CLIENT' WHERE role = 'GUEST'")
    op.execute("UPDATE organizations SET subscription_tier = upper(subscription_tier)")
    op.add_column("workflow_statuses", sa.Column("wip_limit", sa.Integer(), nullable=True))
    op.create_table(
        "checklist_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_checklist_items_task_id", "checklist_items", ["task_id"])
    op.create_index(
        "uq_running_timer_user",
        "time_entries",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("end_time IS NULL"),
        postgresql_where=sa.text("end_time IS NULL"),
    )


def downgrade():
    op.drop_index("uq_running_timer_user", table_name="time_entries")
    op.drop_table("checklist_items")
    op.drop_column("workflow_statuses", "wip_limit")
