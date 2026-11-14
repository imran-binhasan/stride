"""Time Tracking, Telemetry Ingestion, and Screenshot upload service."""

import asyncio
import json
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.exceptions import (
    ConflictException,
    EntityNotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from src.core.redis import get_redis
from src.core.storage import (
    delete_object,
    generate_presigned_get_url,
    generate_presigned_put_url,
    guess_content_type,
    head_object,
)
from src.models.auth import User
from src.models.base import utc_now
from src.models.time_tracking import ActivityTelemetry, TimeEntry, TimeEntryStatus
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
from src.services.notification_service import NotificationService


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
        # Serialize starts per user so concurrent requests cannot create two active timers.
        await self.db.execute(select(User.id).where(User.id == user_id).with_for_update())
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
            entry = await self.repo.get_active_timer(user_id, org_id=org_id)

        if (
            not entry
            or entry.user_id != user_id
            or entry.org_id != org_id
            or entry.end_time is not None
        ):
            raise ValidationException("No active running timer found to stop")

        if payload.notes:
            entry.notes = payload.notes

        await self._finalize_timer(entry)
        return TimeEntryResponse.model_validate(entry)

    async def get_active_timer(
        self, user_id: str, org_id: str | None = None
    ) -> TimeEntryResponse | None:
        entry = await self.repo.get_active_timer(user_id, org_id=org_id)
        if not entry:
            return None
        return TimeEntryResponse.model_validate(entry)

    async def _finalize_timer(self, entry: TimeEntry) -> None:
        now = utc_now()
        entry.end_time = now
        start_time_utc = ensure_utc(entry.start_time)
        delta_sec = int((now - start_time_utc).total_seconds())
        deleted_seconds = 600 * sum(1 for shot in entry.screenshots if shot.is_deleted)
        entry.total_seconds = max(0, delta_sec - deleted_seconds)

        # Calculate average activity score from telemetries
        if entry.telemetries:
            avg_score = sum(t.activity_score for t in entry.telemetries) / len(entry.telemetries)
            entry.idle_seconds = min(
                entry.total_seconds,
                sum(
                    max(
                        0,
                        int(
                            (ensure_utc(t.period_end) - ensure_utc(t.period_start)).total_seconds()
                        ),
                    )
                    for t in entry.telemetries
                    if t.is_idle
                ),
            )
            entry.activity_percent = round(avg_score, 2)
        else:
            entry.activity_percent = 100.0
            entry.idle_seconds = 0

        await self.db.flush()

    async def ingest_telemetry(
        self, user_id: str, payload: TelemetryHeartbeatRequest, org_id: str | None = None
    ) -> TelemetryHeartbeatResponse:
        entry = await self.repo.get_entry_basic(payload.time_entry_id, org_id=org_id)
        if not entry or entry.user_id != user_id or entry.end_time is not None:
            raise ValidationException("Invalid or already stopped time entry")

        start, end = ensure_utc(payload.period_start), ensure_utc(payload.period_end)
        if end <= start or (end - start).total_seconds() > 120:
            raise ValidationException("Telemetry interval must be between 0 and 120 seconds")
        overlap = await self.db.scalar(
            select(ActivityTelemetry.id)
            .where(
                ActivityTelemetry.time_entry_id == entry.id,
                ActivityTelemetry.period_start < end,
                ActivityTelemetry.period_end > start,
            )
            .limit(1)
        )
        if overlap:
            raise ConflictException("Telemetry interval overlaps a previously recorded sample")

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

        redis = await get_redis()
        await redis.set(
            f"upload:screenshot:{screenshot_id}",
            json.dumps(
                {
                    "user_id": user_id,
                    "org_id": org_id,
                    "entry_id": entry.id,
                    "key": s3_key,
                    "is_blurred": payload.is_blurred,
                }
            ),
            ex=600,
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

        existing = await self.repo.get_screenshot(payload.screenshot_id)
        if existing:
            if existing.user_id != user_id or existing.time_entry_id != entry.id:
                raise ValidationException("Screenshot is already linked to another session")
            return ScreenshotResponse.model_validate(existing)
        redis = await get_redis()
        raw = await redis.get(f"upload:screenshot:{payload.screenshot_id}")
        reservation = json.loads(raw) if raw else {}
        if (
            reservation.get("user_id") != user_id
            or reservation.get("org_id") != org_id
            or reservation.get("entry_id") != entry.id
            or reservation.get("key") != payload.s3_key
        ):
            raise ValidationException(
                "Screenshot upload reservation is missing, expired, or mismatched"
            )
        if settings.ENVIRONMENT != "test":
            try:
                meta = await asyncio.to_thread(head_object, payload.s3_key)
            except Exception:
                raise ValidationException("Uploaded screenshot could not be verified") from None
            if meta.get("ContentLength", 0) < 1 or meta["ContentLength"] > 25 * 1024 * 1024:
                raise ValidationException("Screenshot file size is invalid")
        log = await self.repo.add_screenshot_log(
            screenshot_id=payload.screenshot_id,
            time_entry_id=payload.time_entry_id,
            user_id=user_id,
            s3_key=payload.s3_key,
            activity_score=payload.activity_score,
            is_blurred=payload.is_blurred,
        )
        return ScreenshotResponse.model_validate(log)

    async def delete_screenshot(
        self, screenshot_id: str, user_id: str, org_id: str | None = None
    ) -> dict:
        log = await self.repo.get_screenshot(screenshot_id)
        if not log or log.user_id != user_id:
            raise EntityNotFoundException("Screenshot", screenshot_id)

        entry = await self.repo.get_by_id(log.time_entry_id, org_id=org_id)
        if not entry:
            raise EntityNotFoundException("Screenshot", screenshot_id)
        if log.is_deleted:
            return {"success": True, "message": "Screenshot already deleted"}
        if entry.status in {TimeEntryStatus.SUBMITTED, TimeEntryStatus.APPROVED}:
            raise ConflictException(
                "Recall or reject the timesheet before deleting its screenshots"
            )
        log.is_deleted = True

        # Best-effort removal from object storage (skipped in tests to stay offline).
        # boto3 is a synchronous network call — run it off the event loop.
        if settings.ENVIRONMENT != "test":
            await asyncio.to_thread(delete_object, log.s3_key)

        entry = await self.repo.get_by_id(log.time_entry_id)
        if entry:
            entry.total_seconds = max(0, entry.total_seconds - 600)
            await self.db.flush()

        await NotificationService(self.db).log_audit(
            org_id=entry.org_id,
            actor_id=user_id,
            action="screenshot.deleted",
            resource_type="screenshot",
            resource_id=screenshot_id,
            new_values={"deducted_seconds": 600},
        )
        return {"success": True, "message": "Screenshot deleted and up to 10 minutes deducted"}

    async def get_daily_activity_summary(
        self, user_id: str, target_date: date, org_id: str | None = None
    ) -> DailyActivitySummaryResponse:
        """Aggregate employee work sessions, 10-min interval blocks, and daily screen time metrics."""
        entries = await self.repo.get_user_entries_for_day(
            user_id=user_id, target_date=target_date, org_id=org_id
        )

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

        day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        spans = [
            max(
                0,
                int(
                    (
                        min(ensure_utc(e.end_time) if e.end_time else utc_now(), day_end)
                        - max(ensure_utc(e.start_time), day_start)
                    ).total_seconds()
                ),
            )
            for e in entries
        ]
        durations = [
            min(span, e.total_seconds) if e.end_time else span
            for e, span in zip(entries, spans, strict=True)
        ]
        total_screen_sec = sum(durations)
        total_idle_sec = sum(
            min(d, e.idle_seconds) for e, d in zip(entries, durations, strict=True)
        )
        total_work_sec = max(0, total_screen_sec - total_idle_sec)

        # Collect all telemetries and screenshots across sessions
        all_telemetries = []
        all_screenshots = []
        for e in entries:
            all_telemetries.extend(
                t for t in e.telemetries if day_start <= ensure_utc(t.period_start) < day_end
            )
            all_screenshots.extend(
                [
                    s
                    for s in e.screenshots
                    if not s.is_deleted and day_start <= ensure_utc(s.recorded_at) < day_end
                ]
            )

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

            screen_url = generate_presigned_get_url(screens[0].s3_key) if screens else None
            screen_thumb = (
                generate_presigned_get_url(screens[0].thumbnail_s3_key)
                if screens and screens[0].thumbnail_s3_key
                else None
            )

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
        if total_screen_sec > 0:
            weighted_act = (
                sum(e.activity_percent * d for e, d in zip(entries, durations, strict=True))
                / total_screen_sec
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

    async def list_entries(self, org_id, user_id=None, status=None, limit=50, offset=0):
        stmt = select(TimeEntry).where(TimeEntry.org_id == org_id)
        if user_id:
            stmt = stmt.where(TimeEntry.user_id == user_id)
        if status:
            stmt = stmt.where(TimeEntry.status == status)
        rows = await self.db.scalars(
            stmt.order_by(TimeEntry.start_time.desc()).limit(limit).offset(offset)
        )
        return [TimeEntryResponse.model_validate(e) for e in rows]

    async def manual_entry(self, org_id, user_id, payload):
        task = await self.task_repo.get_by_id(payload.task_id, org_id=org_id)
        if not task:
            raise EntityNotFoundException("Task", payload.task_id)
        start, end = ensure_utc(payload.start_time), ensure_utc(payload.end_time)
        if end <= start or end > utc_now():
            raise ValidationException("End must be after start and cannot be in the future")
        await self.db.execute(select(User.id).where(User.id == user_id).with_for_update())
        overlap = await self.db.scalar(
            select(TimeEntry.id)
            .where(
                TimeEntry.user_id == user_id,
                TimeEntry.start_time < end,
                (TimeEntry.end_time > start) | TimeEntry.end_time.is_(None),
            )
            .limit(1)
        )
        if overlap:
            raise ConflictException("Time entry overlaps another session")
        entry = TimeEntry(
            org_id=org_id,
            user_id=user_id,
            task_id=task.id,
            start_time=start,
            end_time=end,
            total_seconds=int((end - start).total_seconds()),
            notes=payload.notes,
            is_billable=payload.is_billable,
            activity_percent=0,
        )
        self.db.add(entry)
        await self.db.flush()
        await NotificationService(self.db).log_audit(
            org_id, "time.created", user_id, "time_entry", entry.id
        )
        return TimeEntryResponse.model_validate(entry)

    async def transition_entry(self, entry_id, org_id, actor_id, action, reason=None):
        entry = await self.repo.get_by_id(entry_id, org_id=org_id)
        if not entry:
            raise EntityNotFoundException("TimeEntry", entry_id)
        if entry.end_time is None:
            raise ConflictException("Stop the timer before submitting it")
        if action in {"submit", "recall"} and entry.user_id != actor_id:
            raise PermissionDeniedException("Only the entry owner can submit or recall it")
        old = entry.status
        if action == "submit" and old in {TimeEntryStatus.DRAFT, TimeEntryStatus.REJECTED}:
            entry.status = TimeEntryStatus.SUBMITTED
        elif action == "recall" and old == TimeEntryStatus.SUBMITTED:
            entry.status = TimeEntryStatus.DRAFT
        elif action in {"APPROVED", "REJECTED"} and old == TimeEntryStatus.SUBMITTED:
            if actor_id == entry.user_id:
                raise PermissionDeniedException("You cannot approve or reject your own timesheet")
            if action == "REJECTED" and not (reason and reason.strip()):
                raise ValidationException("A reason is required for rejection")
            entry.status = TimeEntryStatus(action)
        else:
            raise ConflictException("Invalid timesheet status transition")
        await NotificationService(self.db).log_audit(
            org_id,
            "time." + action.lower(),
            actor_id,
            "time_entry",
            entry.id,
            {"status": old.value},
            {"status": entry.status.value, "reason": reason},
        )
        await self.db.flush()
        return TimeEntryResponse.model_validate(entry)

    async def delete_entry(self, entry_id, org_id, user_id):
        entry = await self.repo.get_by_id(entry_id, org_id=org_id)
        if not entry or entry.user_id != user_id:
            raise EntityNotFoundException("TimeEntry", entry_id)
        if entry.end_time is None or entry.status not in {
            TimeEntryStatus.DRAFT,
            TimeEntryStatus.REJECTED,
        }:
            raise ConflictException("Only stopped draft or rejected entries can be deleted")
        await self.db.delete(entry)
        await NotificationService(self.db).log_audit(
            org_id, "time.deleted", user_id, "time_entry", entry_id
        )
