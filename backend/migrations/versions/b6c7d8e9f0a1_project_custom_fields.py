"""Typed project custom-column definitions."""

import sqlalchemy as sa
from alembic import op

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "projects",
        sa.Column("custom_field_definitions", sa.JSON(), server_default="[]", nullable=False),
    )


def downgrade():
    op.drop_column("projects", "custom_field_definitions")
