"""Time Tracking, Telemetry Ingestion, and Screenshot upload service."""

import asyncio
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.exceptions import EntityNotFoundException, ValidationException
from src.core.storage import delete_object, generate_presigned_put_url, guess_content_type
from src.models.base import utc_now
from src.models.time_tracking import TimeEntry
from src.repositories.task_repo import TaskRepository
from src.repositories.time_repo import TimeRepository
from src.schemas.time_tracking import (
    DailyActivitySummaryResponse,
    ScreenshotConfirmRequest,
    ScreenshotPresignedRequest,
    ScreenshotPresignedResponse,
    ScreenshotResponse,
    StartTimerRequest,
    StopTimerRequest,
    TelemetryHeartbeatRequest,
    TelemetryHeartbeatResponse,
    TenMinuteBlockSummary,
    TimeEntryResponse,
)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def calculate_activity_score(keystrokes: int, mouse_px: int, is_idle: bool) -> float:
    """Calculate activity intensity percentage (0-100%) based on 30-second telemetry."""
    if is_idle:
        return 0.0

    key_score = min(100.0, (keystrokes / 40.0) * 100.0)
    mouse_score = min(100.0, (mouse_px / 800.0) * 100.0)

    combined = (key_score * 0.6) + (mouse_score * 0.4)
    return round(min(100.0, max(0.0, combined)), 2)


class TimeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TimeRepository(db)
        self.task_repo = TaskRepository(db)

    async def start_timer(
        self, org_id: str, user_id: str, payload: StartTimerRequest
    ) -> TimeEntryResponse:
        task = await self.task_repo.get_by_id(payload.task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", payload.task_id)

        # 1. Stop any currently active timer for this user
        active = await self.repo.get_active_timer(user_id)
        if active:
            await self._finalize_timer(active)

        # 2. Create new running timer
        entry = await self.repo.create_time_entry(
            org_id=org_id,
            user_id=user_id,
            task_id=task.id,
            is_billable=payload.is_billable,
            notes=payload.notes,
        )
        return TimeEntryResponse.model_validate(entry)

    async def stop_timer(
        self, org_id: str, user_id: str, payload: StopTimerRequest
    ) -> TimeEntryResponse:
        if payload.time_entry_id:
            entry = await self.repo.get_by_id(payload.time_entry_id, org_id=org_id)
        else:
            entry = await self.repo.get_active_timer(user_id)

        if not entry or entry.end_time is not None:
            raise ValidationException("No active running timer found to stop")

        if payload.notes:
            entry.notes = payload.notes

        await self._finalize_timer(entry)
        return TimeEntryResponse.model_validate(entry)

    async def get_active_timer(self, user_id: str) -> TimeEntryResponse | None:
        entry = await self.repo.get_active_timer(user_id)
        if not entry:
            return None
        return TimeEntryResponse.model_validate(entry)

    async def _finalize_timer(self, entry: TimeEntry) -> None:
        now = utc_now()
        entry.end_time = now
        start_time_utc = ensure_utc(entry.start_time)
        delta_sec = int((now - start_time_utc).total_seconds())
        entry.total_seconds = max(0, delta_sec)

        # Calculate average activity score from telemetries
        if entry.telemetries:
            avg_score = sum(t.activity_score for t in entry.telemetries) / len(entry.telemetries)
            idle_count = sum(1 for t in entry.telemetries if t.is_idle)
            entry.idle_seconds = idle_count * 30
            entry.activity_percent = round(avg_score, 2)
        else:
            entry.activity_percent = 100.0
            entry.idle_seconds = 0

        await self.db.flush()

    async def ingest_telemetry(
        self, user_id: str, payload: TelemetryHeartbeatRequest
    ) -> TelemetryHeartbeatResponse:
        entry = await self.repo.get_entry_basic(payload.time_entry_id)
        if not entry or entry.user_id != user_id or entry.end_time is not None:
            raise ValidationException("Invalid or already stopped time entry")

        score = calculate_activity_score(
            keystrokes=payload.keystroke_count,
            mouse_px=payload.mouse_distance_px,
            is_idle=payload.is_idle,
        )

        telemetry = await self.repo.add_telemetry(
            time_entry_id=entry.id,
            user_id=user_id,
            period_start=ensure_utc(payload.period_start),
            period_end=ensure_utc(payload.period_end),
            keystroke_count=payload.keystroke_count,
            mouse_distance_px=payload.mouse_distance_px,
            active_window_title=payload.active_window_title,
            is_idle=payload.is_idle,
            activity_score=score,
        )
        return TelemetryHeartbeatResponse(
            id=telemetry.id,
            time_entry_id=entry.id,
            activity_score=score,
            is_idle=payload.is_idle,
            recorded=True,
        )

    async def generate_screenshot_upload_url(
        self,
        org_id: str,
        user_id: str,
        payload: ScreenshotPresignedRequest,
    ) -> ScreenshotPresignedResponse:
        entry = await self.repo.get_by_id(payload.time_entry_id, org_id=org_id)
        if not entry or entry.user_id != user_id:
            raise ValidationException("Invalid time entry for screenshot upload")

        screenshot_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        s3_key = f"screenshots/{org_id}/{now.year}/{now.month:02d}/{screenshot_id}.{payload.file_extension}"

        expires_in = 300
        upload_url = generate_presigned_put_url(
            s3_key=s3_key,
            content_type=guess_content_type(payload.file_extension),
            expires_in=expires_in,
        )

        return ScreenshotPresignedResponse(
            screenshot_id=screenshot_id,
            upload_url=upload_url,
            s3_key=s3_key,
            expires_in_seconds=expires_in,
        )

    async def confirm_screenshot(
        self, org_id: str, user_id: str, payload: ScreenshotConfirmRequest
    ) -> ScreenshotResponse:
        entry = await self.repo.get_by_id(payload.time_entry_id, org_id=org_id)
        if not entry or entry.user_id != user_id:
            raise ValidationException("Invalid time entry for screenshot confirmation")
        # The s3_key must live in this organization's namespace (prevents cross-tenant pointers).
        if not payload.s3_key.startswith(f"screenshots/{org_id}/"):
            raise ValidationException("Screenshot key does not belong to this organization")

        log = await self.repo.add_screenshot_log(
            screenshot_id=payload.screenshot_id,
            time_entry_id=payload.time_entry_id,
            user_id=user_id,
            s3_key=payload.s3_key,
            activity_score=payload.activity_score,
            is_blurred=payload.is_blurred,
        )
        return ScreenshotResponse.model_validate(log)

    async def delete_screenshot(self, screenshot_id: str, user_id: str) -> dict:
        log = await self.repo.get_screenshot(screenshot_id)
        if not log or log.user_id != user_id:
            raise EntityNotFoundException("Screenshot", screenshot_id)

        log.is_deleted = True

        # Best-effort removal from object storage (skipped in tests to stay offline).
        # boto3 is a synchronous network call — run it off the event loop.
        if settings.ENVIRONMENT != "test":
            await asyncio.to_thread(delete_object, log.s3_key)

        entry = await self.repo.get_by_id(log.time_entry_id)
        if entry:
            entry.total_seconds = max(0, entry.total_seconds - 600)
            await self.db.flush()

        return {"success": True, "message": "Screenshot deleted and 10 minutes deducted"}

    async def get_daily_activity_summary(
        self, user_id: str, target_date: date
    ) -> DailyActivitySummaryResponse:
        """Aggregate employee work sessions, 10-min interval blocks, and daily screen time metrics."""
        entries = await self.repo.get_user_entries_for_day(user_id=user_id, target_date=target_date)

        if not entries:
            return DailyActivitySummaryResponse(
                user_id=user_id,
                date=target_date,
                day_first_start_time=None,
                day_last_end_time=None,
                total_screen_time_seconds=0,
                total_work_seconds=0,
                total_idle_seconds=0,
                overall_day_activity_percent=0.0,
                total_sessions_count=0,
                total_screenshots_count=0,
                ten_minute_blocks=[],
            )

        day_first_start = ensure_utc(entries[0].start_time)
        valid_end_times = [ensure_utc(e.end_time) for e in entries if e.end_time is not None]
        day_last_end = (
            max(valid_end_times) if valid_end_times else ensure_utc(entries[-1].start_time)
        )

        total_work_sec = sum(e.total_seconds for e in entries)
        total_idle_sec = sum(e.idle_seconds for e in entries)
        total_screen_sec = total_work_sec + total_idle_sec

        # Collect all telemetries and screenshots across sessions
        all_telemetries = []
        all_screenshots = []
        for e in entries:
            all_telemetries.extend(e.telemetries)
            all_screenshots.extend([s for s in e.screenshots if not s.is_deleted])

        # Group into 10-Minute interval blocks
        # Bucket key: floor timestamp to nearest 10-minute interval
        blocks_dict = defaultdict(lambda: {"telemetries": [], "screenshots": []})

        for t in all_telemetries:
            t_start = ensure_utc(t.period_start)
            # Floor to 10-min block
            minute = (t_start.minute // 10) * 10
            block_start = t_start.replace(minute=minute, second=0, microsecond=0)
            blocks_dict[block_start]["telemetries"].append(t)

        for s in all_screenshots:
            s_rec = ensure_utc(s.recorded_at)
            minute = (s_rec.minute // 10) * 10
            block_start = s_rec.replace(minute=minute, second=0, microsecond=0)
            blocks_dict[block_start]["screenshots"].append(s)

        ten_min_blocks: list[TenMinuteBlockSummary] = []
        for block_start, data in sorted(blocks_dict.items(), key=lambda x: x[0]):
            block_end = block_start + timedelta(minutes=10)
            telems = data["telemetries"]
            screens = data["screenshots"]

            if telems:
                avg_act = sum(t.activity_score for t in telems) / len(telems)
                is_idle = all(t.is_idle for t in telems)
                keys = sum(t.keystroke_count for t in telems)
                mouse = sum(t.mouse_distance_px for t in telems)
            else:
                avg_act = 0.0
                is_idle = True
                keys = 0
                mouse = 0

            screen_url = screens[0].s3_key if screens else None
            screen_thumb = screens[0].thumbnail_s3_key if screens else None

            ten_min_blocks.append(
                TenMinuteBlockSummary(
                    block_start=block_start,
                    block_end=block_end,
                    activity_percent=round(avg_act, 2),
                    is_idle=is_idle,
                    keystroke_count=keys,
                    mouse_distance_px=mouse,
                    screenshot_url=screen_url,
                    screenshot_thumbnail=screen_thumb,
                )
            )

        # Overall weighted daily activity percentage
        if total_work_sec > 0:
            weighted_act = (
                sum(e.activity_percent * e.total_seconds for e in entries) / total_work_sec
            )
        else:
            weighted_act = 0.0

        return DailyActivitySummaryResponse(
            user_id=user_id,
            date=target_date,
            day_first_start_time=day_first_start,
            day_last_end_time=day_last_end,
            total_screen_time_seconds=total_screen_sec,
            total_work_seconds=total_work_sec,
            total_idle_seconds=total_idle_sec,
            overall_day_activity_percent=round(weighted_act, 2),
            total_sessions_count=len(entries),
            total_screenshots_count=len(all_screenshots),
            ten_minute_blocks=ten_min_blocks,
        )
