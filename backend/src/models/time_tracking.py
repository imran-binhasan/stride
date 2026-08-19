"""Time Tracking, Desktop Telemetry, and Screenshot database models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, TenantScopedModel, TimestampedModel, generate_uuid, utc_now

if TYPE_CHECKING:
    from src.models.auth import User
    from src.models.task import Task


class TimeEntryStatus(enum.StrEnum):
    """Timesheet approval status."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TimeEntry(Base, TimestampedModel, TenantScopedModel):
    """Time entry log record for tasks."""

    __tablename__ = "time_entries"
    # Serves both the active-timer sort and the daily-report range scan.
    __table_args__ = (
        Index("ix_time_entries_user_start", "user_id", "start_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idle_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activity_percent: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[TimeEntryStatus] = mapped_column(
        Enum(TimeEntryStatus, native_enum=False, length=20),
        default=TimeEntryStatus.DRAFT,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User")
    task: Mapped[Task] = relationship("Task")
    telemetries: Mapped[list[ActivityTelemetry]] = relationship(
        "ActivityTelemetry", back_populates="time_entry", cascade="all, delete-orphan"
    )
    screenshots: Mapped[list[ScreenshotLog]] = relationship(
        "ScreenshotLog", back_populates="time_entry", cascade="all, delete-orphan"
    )


class ActivityTelemetry(Base):
    """30-second activity telemetry payload from desktop agent."""

    __tablename__ = "activity_telemetries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    time_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("time_entries.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    keystroke_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mouse_distance_px: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_window_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_idle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    time_entry: Mapped[TimeEntry] = relationship("TimeEntry", back_populates="telemetries")


class ScreenshotLog(Base):
    """Periodic screenshot capture metadata with S3 storage references."""

    __tablename__ = "screenshot_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    time_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("time_entries.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    activity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_blurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    time_entry: Mapped[TimeEntry] = relationship("TimeEntry", back_populates="screenshots")
