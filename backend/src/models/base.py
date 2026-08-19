"""Base models and mixins for SQLAlchemy declarative models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


def generate_uuid() -> str:
    """Generate a UUID4 hex string."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative Base class for all ORM models."""

    pass


class TimestampedModel:
    """Mixin for models requiring created_at and updated_at audit timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class TenantScopedModel:
    """Mixin for multi-tenant models requiring strict organization isolation."""

    org_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
    )
