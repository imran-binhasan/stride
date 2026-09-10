"""Project, Sprint, Workflow Status, Label, and Project Access models."""

from __future__ import annotations

import enum
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TenantScopedModel, TimestampedModel, generate_uuid

if TYPE_CHECKING:
    from src.models.auth import User
    from src.models.client import ClientContact
    from src.models.task import Task


class StatusCategory(enum.StrEnum):
    BACKLOG     = "BACKLOG"
    TODO        = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW   = "IN_REVIEW"
    DONE        = "DONE"


class ProjectStatus(enum.StrEnum):
    ACTIVE    = "ACTIVE"
    ARCHIVED  = "ARCHIVED"
    COMPLETED = "COMPLETED"


class SprintStatus(enum.StrEnum):
    PLANNED   = "PLANNED"
    ACTIVE    = "ACTIVE"
    COMPLETED = "COMPLETED"


class GranteeType(enum.StrEnum):
    USER = "USER"
    TEAM = "TEAM"


# ── Project ────────────────────────────────────────────────────────────────────

class Project(Base, TimestampedModel, TenantScopedModel):
    __tablename__ = "projects"

    id               : Mapped[str]           = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id     : Mapped[str]           = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    key              : Mapped[str]           = mapped_column(String(10), index=True, nullable=False)
    name             : Mapped[str]           = mapped_column(String(255), nullable=False)
    description      : Mapped[str|None]      = mapped_column(Text, nullable=True)
    status           : Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus, native_enum=False, length=20), default=ProjectStatus.ACTIVE, nullable=False)
    default_view     : Mapped[str]           = mapped_column(String(50), default="kanban", nullable=False)
    color            : Mapped[str]           = mapped_column(String(20), default="#6B7280", nullable=False)
    icon             : Mapped[str|None]      = mapped_column(String(50), nullable=True)
    task_counter     : Mapped[int]           = mapped_column(Integer, default=0, nullable=False)
    start_date       : Mapped[date|None]     = mapped_column(Date, nullable=True)
    target_date      : Mapped[date|None]     = mapped_column(Date, nullable=True)
    client_contact_id: Mapped[str|None]      = mapped_column(String(36), ForeignKey("client_contacts.id", ondelete="SET NULL"), index=True, nullable=True)
    created_by_id    : Mapped[str|None]      = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (UniqueConstraint("org_id", "key", name="uq_project_org_key"),)

    statuses      : Mapped[list[WorkflowStatus]]    = relationship("WorkflowStatus",    back_populates="project", cascade="all, delete-orphan", order_by="WorkflowStatus.position")
    sprints       : Mapped[list[Sprint]]            = relationship("Sprint",            back_populates="project", cascade="all, delete-orphan")
    tasks         : Mapped[list[Task]]              = relationship("Task",              back_populates="project", cascade="all, delete-orphan")
    access_grants : Mapped[list[ProjectAccessGrant]] = relationship("ProjectAccessGrant", back_populates="project", cascade="all, delete-orphan")
    client_contact: Mapped[ClientContact|None]      = relationship("ClientContact", foreign_keys=[client_contact_id])
    created_by    : Mapped[User|None]               = relationship("User", foreign_keys=[created_by_id])


# ── Project Access Grants (USER or TEAM) ──────────────────────────────────────

class ProjectAccessGrant(Base, TimestampedModel):
    """Explicit project access for CLIENT/GUEST users or entire teams.

    MEMBER+ roles access all org projects without a grant.
    """

    __tablename__ = "project_access_grants"

    id           : Mapped[str]         = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id   : Mapped[str]         = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    grantee_type : Mapped[GranteeType] = mapped_column(Enum(GranteeType, native_enum=False, length=10), nullable=False)
    grantee_id   : Mapped[str]         = mapped_column(String(36), nullable=False, index=True)
    granted_by_id: Mapped[str|None]    = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (UniqueConstraint("project_id", "grantee_type", "grantee_id", name="uq_project_grant"),)

    project   : Mapped[Project]  = relationship("Project", back_populates="access_grants")
    granted_by: Mapped[User|None] = relationship("User", foreign_keys=[granted_by_id])


# ── Workflow Status ────────────────────────────────────────────────────────────

class WorkflowStatus(Base, TimestampedModel):
    __tablename__ = "workflow_statuses"

    id        : Mapped[str]            = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str]            = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    name      : Mapped[str]            = mapped_column(String(100), nullable=False)
    category  : Mapped[StatusCategory] = mapped_column(Enum(StatusCategory, native_enum=False, length=50), default=StatusCategory.TODO, nullable=False)
    color     : Mapped[str]            = mapped_column(String(20), default="#6B7280", nullable=False)
    position  : Mapped[int]            = mapped_column(Integer, default=0, nullable=False)

    project: Mapped[Project]  = relationship("Project", back_populates="statuses")
    tasks  : Mapped[list[Task]] = relationship("Task", back_populates="status")


# ── Sprint ─────────────────────────────────────────────────────────────────────

class Sprint(Base, TimestampedModel):
    __tablename__ = "sprints"

    id         : Mapped[str]          = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id : Mapped[str]          = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    name       : Mapped[str]          = mapped_column(String(255), nullable=False)
    goal       : Mapped[str|None]     = mapped_column(Text, nullable=True)
    start_date : Mapped[date|None]    = mapped_column(Date, nullable=True)
    end_date   : Mapped[date|None]    = mapped_column(Date, nullable=True)
    status     : Mapped[SprintStatus] = mapped_column(Enum(SprintStatus, native_enum=False, length=20), default=SprintStatus.PLANNED, nullable=False)

    project: Mapped[Project]  = relationship("Project", back_populates="sprints")
    tasks  : Mapped[list[Task]] = relationship("Task", back_populates="sprint")


# ── Labels (org-level pool) ────────────────────────────────────────────────────

class Label(Base, TimestampedModel):
    __tablename__ = "labels"

    id    : Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    name  : Mapped[str] = mapped_column(String(100), nullable=False)
    color : Mapped[str] = mapped_column(String(20), default="#6B7280", nullable=False)

    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_label_org_name"),)
