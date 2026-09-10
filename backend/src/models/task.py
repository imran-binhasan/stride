"""Task, Dependency, Label, Comment, Attachment, and Watcher models."""

from __future__ import annotations

import enum
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON, Boolean, Date, Enum, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TenantScopedModel, TimestampedModel, generate_uuid

if TYPE_CHECKING:
    from src.models.auth import User
    from src.models.project import Label, Project, Sprint, WorkflowStatus


class TaskPriority(enum.StrEnum):
    URGENT = "URGENT"
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


class TaskType(enum.StrEnum):
    TASK    = "TASK"
    BUG     = "BUG"
    STORY   = "STORY"
    EPIC    = "EPIC"


class DependencyType(enum.StrEnum):
    BLOCKS     = "BLOCKS"
    BLOCKED_BY = "BLOCKED_BY"
    RELATES_TO = "RELATES_TO"


# ── Task ───────────────────────────────────────────────────────────────────────

class Task(Base, TimestampedModel, TenantScopedModel):
    __tablename__ = "tasks"

    id              : Mapped[str]          = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id      : Mapped[str]          = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    sprint_id       : Mapped[str|None]     = mapped_column(String(36), ForeignKey("sprints.id", ondelete="SET NULL"), index=True, nullable=True)
    status_id       : Mapped[str]          = mapped_column(String(36), ForeignKey("workflow_statuses.id", ondelete="RESTRICT"), index=True, nullable=False)
    parent_task_id  : Mapped[str|None]     = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=True)
    short_id        : Mapped[str]          = mapped_column(String(20), index=True, nullable=False)
    title           : Mapped[str]          = mapped_column(String(255), nullable=False)
    description     : Mapped[str|None]     = mapped_column(Text, nullable=True)
    type            : Mapped[TaskType]     = mapped_column(Enum(TaskType, native_enum=False, length=20), default=TaskType.TASK, nullable=False)
    priority        : Mapped[TaskPriority] = mapped_column(Enum(TaskPriority, native_enum=False, length=20), default=TaskPriority.MEDIUM, nullable=False)
    story_points    : Mapped[float|None]   = mapped_column(Float, nullable=True)
    estimated_hours : Mapped[float|None]   = mapped_column(Float, nullable=True)
    start_date      : Mapped[date|None]    = mapped_column(Date, nullable=True)
    due_date        : Mapped[date|None]    = mapped_column(Date, nullable=True)
    position        : Mapped[int]          = mapped_column(Integer, default=1000, nullable=False)
    custom_fields   : Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_client_ticket: Mapped[bool]         = mapped_column(Boolean, default=False, nullable=False)
    creator_id      : Mapped[str]          = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    assignee_id     : Mapped[str|None]     = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)

    __table_args__ = (UniqueConstraint("project_id", "short_id", name="uq_task_project_short_id"),)

    project    : Mapped[Project]           = relationship("Project", back_populates="tasks")
    status     : Mapped[WorkflowStatus]    = relationship("WorkflowStatus", back_populates="tasks")
    sprint     : Mapped[Sprint|None]       = relationship("Sprint", back_populates="tasks")
    creator    : Mapped[User]              = relationship("User", foreign_keys=[creator_id])
    assignee   : Mapped[User|None]         = relationship("User", foreign_keys=[assignee_id])

    # Self-referencing for parent/child (replaces subtasks table)
    parent      : Mapped[Task|None]       = relationship("Task", remote_side="Task.id", back_populates="children", foreign_keys=[parent_task_id])
    children    : Mapped[list[Task]]      = relationship("Task", back_populates="parent", foreign_keys=[parent_task_id], cascade="all, delete-orphan")

    assignees   : Mapped[list[TaskAssignee]]  = relationship("TaskAssignee",  back_populates="task", cascade="all, delete-orphan")
    watchers    : Mapped[list[TaskWatcher]]   = relationship("TaskWatcher",   back_populates="task", cascade="all, delete-orphan")
    labels      : Mapped[list[TaskLabel]]     = relationship("TaskLabel",     back_populates="task", cascade="all, delete-orphan")
    comments    : Mapped[list[Comment]]       = relationship("Comment",       back_populates="task", cascade="all, delete-orphan", order_by="Comment.created_at")
    attachments : Mapped[list[Attachment]]    = relationship("Attachment",    back_populates="task", cascade="all, delete-orphan")
    dependencies_out: Mapped[list[TaskDependency]] = relationship("TaskDependency", foreign_keys="TaskDependency.predecessor_id", back_populates="predecessor", cascade="all, delete-orphan")
    dependencies_in : Mapped[list[TaskDependency]] = relationship("TaskDependency", foreign_keys="TaskDependency.successor_id",   back_populates="successor",   cascade="all, delete-orphan")


# ── Multi-assignee ─────────────────────────────────────────────────────────────

class TaskAssignee(Base, TimestampedModel):
    __tablename__ = "task_assignees"

    id      : Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id : Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id : Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_assignee"),)

    task: Mapped[Task] = relationship("Task", back_populates="assignees")
    user: Mapped[User] = relationship("User")


# ── Watchers ───────────────────────────────────────────────────────────────────

class TaskWatcher(Base, TimestampedModel):
    __tablename__ = "task_watchers"

    id      : Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id : Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id : Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_watcher"),)

    task: Mapped[Task] = relationship("Task", back_populates="watchers")
    user: Mapped[User] = relationship("User")


# ── Labels (join) ──────────────────────────────────────────────────────────────

class TaskLabel(Base):
    __tablename__ = "task_labels"

    task_id  : Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id",   ondelete="CASCADE"), primary_key=True)
    label_id : Mapped[str] = mapped_column(String(36), ForeignKey("labels.id",  ondelete="CASCADE"), primary_key=True)

    task : Mapped[Task]  = relationship("Task",  back_populates="labels")
    label: Mapped[Label] = relationship("Label")


# ── Dependencies ───────────────────────────────────────────────────────────────

class TaskDependency(Base, TimestampedModel):
    __tablename__ = "task_dependencies"

    id              : Mapped[str]            = mapped_column(String(36), primary_key=True, default=generate_uuid)
    predecessor_id  : Mapped[str]            = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    successor_id    : Mapped[str]            = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    dependency_type : Mapped[DependencyType] = mapped_column(Enum(DependencyType, native_enum=False, length=20), default=DependencyType.BLOCKS, nullable=False)
    lag_days        : Mapped[int]            = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (UniqueConstraint("predecessor_id", "successor_id", name="uq_task_dependency_pair"),)

    predecessor: Mapped[Task] = relationship("Task", foreign_keys=[predecessor_id], back_populates="dependencies_out")
    successor  : Mapped[Task] = relationship("Task", foreign_keys=[successor_id],   back_populates="dependencies_in")


# ── Comments ───────────────────────────────────────────────────────────────────

class Comment(Base, TimestampedModel):
    __tablename__ = "comments"

    id               : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id          : Mapped[str]      = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    author_id        : Mapped[str]      = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    content          : Mapped[str]      = mapped_column(Text, nullable=False)
    is_internal      : Mapped[bool]     = mapped_column(Boolean, default=False, nullable=False)  # hidden from CLIENT portal
    parent_comment_id: Mapped[str|None] = mapped_column(String(36), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)

    task    : Mapped[Task]           = relationship("Task", back_populates="comments")
    author  : Mapped[User]           = relationship("User", foreign_keys=[author_id])
    replies : Mapped[list[Comment]]  = relationship("Comment", back_populates="parent_comment", foreign_keys=[parent_comment_id])
    parent_comment: Mapped[Comment|None] = relationship("Comment", remote_side="Comment.id", back_populates="replies", foreign_keys=[parent_comment_id])
    attachments: Mapped[list[Attachment]] = relationship("Attachment", back_populates="comment", cascade="all, delete-orphan")


# ── Attachments ────────────────────────────────────────────────────────────────

class Attachment(Base, TimestampedModel):
    __tablename__ = "attachments"

    id             : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id        : Mapped[str]      = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    comment_id     : Mapped[str|None] = mapped_column(String(36), ForeignKey("comments.id", ondelete="SET NULL"), nullable=True)
    uploaded_by_id : Mapped[str]      = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_name      : Mapped[str]      = mapped_column(String(255), nullable=False)
    file_size      : Mapped[int]      = mapped_column(nullable=False)
    mime_type      : Mapped[str]      = mapped_column(String(100), nullable=False)
    storage_key    : Mapped[str]      = mapped_column(String(512), nullable=False)

    task       : Mapped[Task]         = relationship("Task", back_populates="attachments")
    comment    : Mapped[Comment|None] = relationship("Comment", back_populates="attachments")
    uploaded_by: Mapped[User]         = relationship("User", foreign_keys=[uploaded_by_id])
