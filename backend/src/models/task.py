"""Task, Subtask, Dependency, and Tag database models."""

from __future__ import annotations

import enum
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, TenantScopedModel, TimestampedModel, generate_uuid

if TYPE_CHECKING:
    from src.models.auth import User
    from src.models.project import Project, Sprint, WorkflowStatus


class TaskPriority(enum.StrEnum):
    """Task priority levels."""

    URGENT = "URGENT"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DependencyType(enum.StrEnum):
    """Types of directional task dependency links."""

    BLOCKS = "BLOCKS"
    BLOCKED_BY = "BLOCKED_BY"
    RELATES_TO = "RELATES_TO"


class Task(Base, TimestampedModel, TenantScopedModel):
    """Core Task / Issue entity with dynamic custom fields."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sprint_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sprints.id", ondelete="SET NULL"), index=True, nullable=True
    )
    status_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_statuses.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    short_id: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, native_enum=False, length=20),
        default=TaskPriority.MEDIUM,
        nullable=False,
    )
    story_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    custom_fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    creator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assignee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    __table_args__ = (UniqueConstraint("project_id", "short_id", name="uq_task_project_short_id"),)

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="tasks")
    status: Mapped[WorkflowStatus] = relationship("WorkflowStatus", back_populates="tasks")
    sprint: Mapped[Sprint | None] = relationship("Sprint", back_populates="tasks")
    creator: Mapped[User] = relationship("User", foreign_keys=[creator_id])
    assignee: Mapped[User | None] = relationship("User", foreign_keys=[assignee_id])
    subtasks: Mapped[list[Subtask]] = relationship(
        "Subtask", back_populates="task", cascade="all, delete-orphan", order_by="Subtask.position"
    )
    dependencies_out: Mapped[list[TaskDependency]] = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.predecessor_id",
        back_populates="predecessor",
        cascade="all, delete-orphan",
    )
    dependencies_in: Mapped[list[TaskDependency]] = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.successor_id",
        back_populates="successor",
        cascade="all, delete-orphan",
    )


class Subtask(Base, TimestampedModel):
    """Subtask item under a parent task."""

    __tablename__ = "subtasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    task: Mapped[Task] = relationship("Task", back_populates="subtasks")


class TaskDependency(Base, TimestampedModel):
    """Predecessor-Successor dependency relation between tasks."""

    __tablename__ = "task_dependencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    predecessor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    successor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    dependency_type: Mapped[DependencyType] = mapped_column(
        Enum(DependencyType, native_enum=False, length=20),
        default=DependencyType.BLOCKS,
        nullable=False,
    )
    lag_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("predecessor_id", "successor_id", name="uq_task_dependency_pair"),
    )

    # Relationships
    predecessor: Mapped[Task] = relationship(
        "Task", foreign_keys=[predecessor_id], back_populates="dependencies_out"
    )
    successor: Mapped[Task] = relationship(
        "Task", foreign_keys=[successor_id], back_populates="dependencies_in"
    )
