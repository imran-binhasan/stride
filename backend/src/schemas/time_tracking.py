"""Pydantic v2 schemas for Time Tracking, Telemetry, Screenshots, and Daily Rollups."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from src.models.time_tracking import TimeEntryStatus


class StartTimerRequest(BaseModel):
    task_id: str
    is_billable: bool = True
    notes: str | None = None


class StopTimerRequest(BaseModel):
    time_entry_id: str | None = None  # If omitted, stops any active timer for user
    notes: str | None = None


class TimeEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    user_id: str
    task_id: str
    start_time: datetime
    end_time: datetime | None
    total_seconds: int
    idle_seconds: int
    activity_percent: float
    is_billable: bool
    status: TimeEntryStatus
    notes: str | None
    created_at: datetime


class TelemetryHeartbeatRequest(BaseModel):
    time_entry_id: str
    period_start: datetime
    period_end: datetime
    keystroke_count: int = Field(ge=0)
    mouse_distance_px: int = Field(ge=0)
    active_window_title: str | None = None
    is_idle: bool = False


class TelemetryHeartbeatResponse(BaseModel):
    id: str
    time_entry_id: str
    activity_score: float
    is_idle: bool
    recorded: bool = True


class ScreenshotPresignedRequest(BaseModel):
    time_entry_id: str
    file_extension: str = Field(default="jpg", pattern="^(jpg|jpeg|png|webp)$")
    is_blurred: bool = False


class ScreenshotPresignedResponse(BaseModel):
    screenshot_id: str
    upload_url: str
    s3_key: str
    expires_in_seconds: int


class ScreenshotConfirmRequest(BaseModel):
    screenshot_id: str
    time_entry_id: str
    s3_key: str
    activity_score: float = 0.0
    is_blurred: bool = False


class ScreenshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    time_entry_id: str
    user_id: str
    s3_key: str
    activity_score: float
    is_blurred: bool
    is_deleted: bool
    recorded_at: datetime


class TenMinuteBlockSummary(BaseModel):
    """10-minute timesheet interval block (TimeDoctor / Hubstaff standard)."""

    block_start: datetime
    block_end: datetime
    activity_percent: float
    is_idle: bool
    keystroke_count: int
    mouse_distance_px: int
    screenshot_url: str | None = None
    screenshot_thumbnail: str | None = None


class DailyActivitySummaryResponse(BaseModel):
    """Full-day employee workforce & screen time monitoring summary."""

    user_id: str
    date: date
    day_first_start_time: datetime | None
    day_last_end_time: datetime | None
    total_screen_time_seconds: int
    total_work_seconds: int
    total_idle_seconds: int
    overall_day_activity_percent: float
    total_sessions_count: int
    total_screenshots_count: int
    ten_minute_blocks: list[TenMinuteBlockSummary] = []
