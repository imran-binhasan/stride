"""Project, Sprint, and Workflow Status database models."""

from __future__ import annotations

import enum
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, TenantScopedModel, TimestampedModel, generate_uuid

if TYPE_CHECKING:
    from src.models.task import Task


class StatusCategory(enum.StrEnum):
    """Workflow state categories."""

    BACKLOG = "BACKLOG"
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"


class Project(Base, TimestampedModel, TenantScopedModel):
    """Project domain entity."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    key: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_view: Mapped[str] = mapped_column(String(50), default="kanban", nullable=False)
    task_counter: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (UniqueConstraint("org_id", "key", name="uq_project_org_key"),)

    # Relationships
    statuses: Mapped[list[WorkflowStatus]] = relationship(
        "WorkflowStatus",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="WorkflowStatus.position",
    )
    sprints: Mapped[list[Sprint]] = relationship(
        "Sprint", back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[Task]] = relationship(
        "Task", back_populates="project", cascade="all, delete-orphan"
    )


class WorkflowStatus(Base, TimestampedModel):
    """Customizable workflow status columns for projects."""

    __tablename__ = "workflow_statuses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[StatusCategory] = mapped_column(
        Enum(StatusCategory, native_enum=False, length=50),
        default=StatusCategory.TODO,
        nullable=False,
    )
    color: Mapped[str] = mapped_column(String(20), default="#6B7280", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="statuses")
    tasks: Mapped[list[Task]] = relationship("Task", back_populates="status")


class Sprint(Base, TimestampedModel):
    """Sprint iteration model for agile cycles."""

    __tablename__ = "sprints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="sprints")
    tasks: Mapped[list[Task]] = relationship("Task", back_populates="sprint")
