"""Recurring task schedules and one-time generation guard."""

import sqlalchemy as sa
from alembic import op

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("recurrence", sa.JSON(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("recurrence_generated", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade():
    op.drop_column("tasks", "recurrence_generated")
    op.drop_column("tasks", "recurrence")
