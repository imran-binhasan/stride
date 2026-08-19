"""External Integrations (GitHub & Figma) database models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, TenantScopedModel, TimestampedModel, generate_uuid

if TYPE_CHECKING:
    from src.models.project import Project
    from src.models.task import Task


class GitHubIntegration(Base, TimestampedModel, TenantScopedModel):
    """GitHub repository connection mapping for a project."""

    __tablename__ = "github_integrations"
    # Inbound webhooks look up integrations by (repo_owner, repo_name) on every event.
    __table_args__ = (
        Index("ix_github_integrations_repo", "repo_owner", "repo_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    repo_owner: Mapped[str] = mapped_column(String(100), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(100), nullable=False)
    auto_transition_pr_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_transition_pr_merge: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    project: Mapped[Project] = relationship("Project")


class FigmaLink(Base, TimestampedModel):
    """Attached Figma design frame or file link on a task."""

    __tablename__ = "figma_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    figma_url: Mapped[str] = mapped_column(String(512), nullable=False)
    file_key: Mapped[str] = mapped_column(String(100), nullable=False)
    node_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationships
    task: Mapped[Task] = relationship("Task")


class WebhookEventLog(Base, TimestampedModel):
    """Audit log for incoming external webhook events."""

    __tablename__ = "webhook_event_logs"
    # Supports provider-filtered queries and time-based retention pruning.
    __table_args__ = (
        Index("ix_webhook_event_logs_provider_created", "provider", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "github", "figma"
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    processed_successfully: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
