"""Client Portal — ClientContact and per-project access grants."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TenantScopedModel, TimestampedModel, generate_uuid

if TYPE_CHECKING:
    from src.models.auth import User
    from src.models.project import Project


class ClientStatus(str):
    ACTIVE   = "ACTIVE"
    INACTIVE = "INACTIVE"


class ClientContact(Base, TimestampedModel, TenantScopedModel):
    """An external client who can access specific projects via the client portal."""

    __tablename__ = "client_contacts"

    id           : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id      : Mapped[str]      = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    company_name : Mapped[str|None] = mapped_column(String(255), nullable=True)
    phone        : Mapped[str|None] = mapped_column(String(50),  nullable=True)
    address      : Mapped[str|None] = mapped_column(Text, nullable=True)
    notes        : Mapped[str|None] = mapped_column(Text, nullable=True)
    is_active    : Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)

    user           : Mapped[User]                    = relationship("User", foreign_keys=[user_id])
    project_access : Mapped[list[ClientProjectAccess]] = relationship("ClientProjectAccess", back_populates="client_contact", cascade="all, delete-orphan")


class ClientProjectAccess(Base, TimestampedModel):
    """Fine-grained per-project permissions for a client contact."""

    __tablename__ = "client_project_access"

    id                  : Mapped[str]  = mapped_column(String(36), primary_key=True, default=generate_uuid)
    client_contact_id   : Mapped[str]  = mapped_column(String(36), ForeignKey("client_contacts.id", ondelete="CASCADE"), index=True, nullable=False)
    project_id          : Mapped[str]  = mapped_column(String(36), ForeignKey("projects.id",        ondelete="CASCADE"), index=True, nullable=False)
    can_create_tickets  : Mapped[bool] = mapped_column(Boolean, default=True,  nullable=False)
    can_comment         : Mapped[bool] = mapped_column(Boolean, default=True,  nullable=False)
    can_view_timesheets : Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    granted_by_id       : Mapped[str|None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (UniqueConstraint("client_contact_id", "project_id", name="uq_client_project_access"),)

    client_contact: Mapped[ClientContact] = relationship("ClientContact", back_populates="project_access")
    project       : Mapped[Project]       = relationship("Project", foreign_keys=[project_id])
    granted_by    : Mapped[User|None]     = relationship("User", foreign_keys=[granted_by_id])
