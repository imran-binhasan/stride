"""Notifications and Audit Log models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TenantScopedModel, generate_uuid, utc_now

if TYPE_CHECKING:
    from src.models.auth import User


class Notification(Base):
    """In-app notification for task assignments, mentions, sprint events, etc."""

    __tablename__ = "notifications"

    id            : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id       : Mapped[str]      = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    org_id        : Mapped[str]      = mapped_column(String(36), index=True, nullable=False)
    type          : Mapped[str]      = mapped_column(String(100), nullable=False)  # e.g. "task.assigned"
    title         : Mapped[str]      = mapped_column(String(255), nullable=False)
    body          : Mapped[str|None] = mapped_column(Text, nullable=True)
    resource_type : Mapped[str|None] = mapped_column(String(50),  nullable=True)
    resource_id   : Mapped[str|None] = mapped_column(String(36),  nullable=True)
    actor_id      : Mapped[str|None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_read       : Mapped[bool]     = mapped_column(Boolean, default=False, nullable=False)
    read_at       : Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at    : Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user : Mapped[User]      = relationship("User", foreign_keys=[user_id])
    actor: Mapped[User|None] = relationship("User", foreign_keys=[actor_id])


class AuditLog(Base):
    """Immutable audit trail — records every significant mutation in the system."""

    __tablename__ = "audit_logs"

    id            : Mapped[str]           = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id        : Mapped[str]           = mapped_column(String(36), index=True, nullable=False)
    actor_id      : Mapped[str|None]      = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action        : Mapped[str]           = mapped_column(String(100), nullable=False)  # e.g. "task.created"
    resource_type : Mapped[str|None]      = mapped_column(String(50),  nullable=True)
    resource_id   : Mapped[str|None]      = mapped_column(String(36),  nullable=True)
    old_values    : Mapped[dict[str,Any]|None] = mapped_column(JSON, nullable=True)
    new_values    : Mapped[dict[str,Any]|None] = mapped_column(JSON, nullable=True)
    ip_address    : Mapped[str|None]      = mapped_column(String(45), nullable=True)
    user_agent    : Mapped[str|None]      = mapped_column(String(512), nullable=True)
    created_at    : Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    actor: Mapped[User|None] = relationship("User", foreign_keys=[actor_id])
