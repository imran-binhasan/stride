"""Database repository for Time Entries, Telemetry, and Screenshots."""

from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.models.base import utc_now
from src.models.time_tracking import ActivityTelemetry, ScreenshotLog, TimeEntry


class TimeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active_timer(self, user_id: str) -> TimeEntry | None:
        stmt = (
            select(TimeEntry)
            .where(
                TimeEntry.user_id == user_id,
                TimeEntry.end_time.is_(None),
            )
            .order_by(TimeEntry.start_time.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_entry_basic(
        self, time_entry_id: str, org_id: str | None = None
    ) -> TimeEntry | None:
        """Fetch a time entry WITHOUT eager-loading telemetries/screenshots.

        Used on the high-frequency telemetry ingest path to avoid reloading the entire
        session's telemetry set on every 30s heartbeat (O(n^2) over a long session).
        """
        stmt = select(TimeEntry).where(TimeEntry.id == time_entry_id)
        if org_id:
            stmt = stmt.where(TimeEntry.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, time_entry_id: str, org_id: str | None = None) -> TimeEntry | None:
        stmt = (
            select(TimeEntry)
            .where(TimeEntry.id == time_entry_id)
            .options(
                selectinload(TimeEntry.telemetries),
                selectinload(TimeEntry.screenshots),
            )
        )
        if org_id:
            stmt = stmt.where(TimeEntry.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_entries_for_day(self, user_id: str, target_date: date) -> list[TimeEntry]:
        """Fetch all time entries for a user starting on target_date."""
        start_of_day = datetime.combine(target_date, time.min, tzinfo=UTC)
        end_of_day = datetime.combine(target_date, time.max, tzinfo=UTC)

        stmt = (
            select(TimeEntry)
            .where(
                TimeEntry.user_id == user_id,
                TimeEntry.start_time >= start_of_day,
                TimeEntry.start_time <= end_of_day,
            )
            .options(
                selectinload(TimeEntry.telemetries),
                selectinload(TimeEntry.screenshots),
            )
            .order_by(TimeEntry.start_time.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_time_entry(
        self,
        org_id: str,
        user_id: str,
        task_id: str,
        is_billable: bool = True,
        notes: str | None = None,
    ) -> TimeEntry:
        entry = TimeEntry(
            org_id=org_id,
            user_id=user_id,
            task_id=task_id,
            is_billable=is_billable,
            notes=notes,
            start_time=utc_now(),
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def add_telemetry(
        self,
        time_entry_id: str,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
        keystroke_count: int,
        mouse_distance_px: int,
        active_window_title: str | None,
        is_idle: bool,
        activity_score: float,
    ) -> ActivityTelemetry:
        telemetry = ActivityTelemetry(
            time_entry_id=time_entry_id,
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            keystroke_count=keystroke_count,
            mouse_distance_px=mouse_distance_px,
            active_window_title=active_window_title,
            is_idle=is_idle,
            activity_score=activity_score,
        )
        self.db.add(telemetry)
        await self.db.flush()
        return telemetry

    async def add_screenshot_log(
        self,
        time_entry_id: str,
        user_id: str,
        s3_key: str,
        activity_score: float = 0.0,
        is_blurred: bool = False,
        screenshot_id: str | None = None,
    ) -> ScreenshotLog:
        kwargs = {
            "time_entry_id": time_entry_id,
            "user_id": user_id,
            "s3_key": s3_key,
            "activity_score": activity_score,
            "is_blurred": is_blurred,
        }
        if screenshot_id:
            kwargs["id"] = screenshot_id

        log = ScreenshotLog(**kwargs)
        self.db.add(log)
        await self.db.flush()
        return log

    async def get_screenshot(self, screenshot_id: str) -> ScreenshotLog | None:
        stmt = select(ScreenshotLog).where(ScreenshotLog.id == screenshot_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
