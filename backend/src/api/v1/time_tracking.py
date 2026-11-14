"""Time Tracking, Telemetry Ingestion, and Screenshot API endpoints."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.exceptions import PermissionDeniedException
from src.core.rbac import AuthContext, Permission, require_permission
from src.repositories.user_repo import UserRepository
from src.schemas.time_tracking import (
    DailyActivitySummaryResponse,
    ManualTimeEntryRequest,
    ScreenshotConfirmRequest,
    ScreenshotPresignedRequest,
    ScreenshotPresignedResponse,
    ScreenshotResponse,
    StartTimerRequest,
    StopTimerRequest,
    TelemetryHeartbeatRequest,
    TelemetryHeartbeatResponse,
    TimeEntryResponse,
    TimeEntryReviewRequest,
)
from src.services.time_service import TimeService

router = APIRouter(prefix="/time-tracking", tags=["Time Tracking"])


@router.post("/timer/start", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
async def start_timer(
    payload: StartTimerRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TimeEntryResponse:
    """Start an active timer on a task."""
    return await TimeService(db).start_timer(
        org_id=ctx.org_id, user_id=ctx.user.id, payload=payload
    )


@router.post("/timer/stop", response_model=TimeEntryResponse)
async def stop_timer(
    payload: StopTimerRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TimeEntryResponse:
    """Stop the active timer and finalize duration/activity percent."""
    return await TimeService(db).stop_timer(org_id=ctx.org_id, user_id=ctx.user.id, payload=payload)


@router.get("/timer/active", response_model=TimeEntryResponse | None)
async def get_active_timer(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_READ_OWN))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TimeEntryResponse | None:
    return await TimeService(db).get_active_timer(user_id=ctx.user.id, org_id=ctx.org_id)


@router.post("/telemetry/heartbeat", response_model=TelemetryHeartbeatResponse)
async def send_telemetry_heartbeat(
    payload: TelemetryHeartbeatRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TelemetryHeartbeatResponse:
    """Ingest 30-second activity telemetry from desktop companion daemon."""
    return await TimeService(db).ingest_telemetry(
        user_id=ctx.user.id, payload=payload, org_id=ctx.org_id
    )


@router.post("/screenshots/presigned-url", response_model=ScreenshotPresignedResponse)
async def get_screenshot_presigned_url(
    payload: ScreenshotPresignedRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScreenshotPresignedResponse:
    """Obtain a secure presigned S3 upload URL for desktop screenshot capture."""
    return await TimeService(db).generate_screenshot_upload_url(
        org_id=ctx.org_id, user_id=ctx.user.id, payload=payload
    )


@router.post(
    "/screenshots/confirm", response_model=ScreenshotResponse, status_code=status.HTTP_201_CREATED
)
async def confirm_screenshot_upload(
    payload: ScreenshotConfirmRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScreenshotResponse:
    return await TimeService(db).confirm_screenshot(
        org_id=ctx.org_id, user_id=ctx.user.id, payload=payload
    )


@router.delete("/screenshots/{screenshot_id}")
async def delete_screenshot(
    screenshot_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    return await TimeService(db).delete_screenshot(
        screenshot_id=screenshot_id, user_id=ctx.user.id, org_id=ctx.org_id
    )


@router.get("/reports/daily", response_model=DailyActivitySummaryResponse)
async def get_daily_activity_report(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_READ_OWN))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    target_date: Annotated[date | None, Query(alias="date")] = None,
    target_user_id: Annotated[str | None, Query(alias="user_id")] = None,
) -> DailyActivitySummaryResponse:
    """Retrieve daily activity summary. Managers can view any member's report."""
    chosen_date = target_date or datetime.now(UTC).date()
    uid = ctx.user.id
    if target_user_id and target_user_id != ctx.user.id:
        if not ctx.has_permission(Permission.TIME_READ_ALL):
            raise PermissionDeniedException(
                "Requires 'time:read_all' permission to view another user's report"
            )
        membership = await UserRepository(db).get_org_membership(
            org_id=ctx.org_id, user_id=target_user_id
        )
        if not membership:
            raise PermissionDeniedException("Target user is not a member of this organization")
        uid = target_user_id
    return await TimeService(db).get_daily_activity_summary(
        user_id=uid, target_date=chosen_date, org_id=ctx.org_id
    )


@router.get("/entries", response_model=list[TimeEntryResponse])
async def list_entries(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_READ_OWN))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_id: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    all_members: bool = False,
):
    if (all_members or user_id and user_id != ctx.user.id) and not ctx.has_permission(
        Permission.TIME_READ_ALL
    ):
        raise PermissionDeniedException("Requires time:read_all")
    return await TimeService(db).list_entries(
        ctx.org_id, user_id if all_members else user_id or ctx.user.id, status, limit, offset
    )


@router.post("/entries", response_model=TimeEntryResponse, status_code=201)
async def manual_entry(
    payload: ManualTimeEntryRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await TimeService(db).manual_entry(ctx.org_id, ctx.user.id, payload)


@router.post("/entries/{entry_id}/submit", response_model=TimeEntryResponse)
async def submit_entry(
    entry_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await TimeService(db).transition_entry(entry_id, ctx.org_id, ctx.user.id, "submit")


@router.post("/entries/{entry_id}/recall", response_model=TimeEntryResponse)
async def recall_entry(
    entry_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await TimeService(db).transition_entry(entry_id, ctx.org_id, ctx.user.id, "recall")


@router.post("/entries/{entry_id}/review", response_model=TimeEntryResponse)
async def review_entry(
    entry_id: str,
    payload: TimeEntryReviewRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_APPROVE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await TimeService(db).transition_entry(
        entry_id, ctx.org_id, ctx.user.id, payload.status.value, payload.reason
    )


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_LOG))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    await TimeService(db).delete_entry(entry_id, ctx.org_id, ctx.user.id)


@router.get("/screenshots")
async def list_screenshots(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TIME_READ_OWN))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    time_entry_id: str,
):
    from src.core.exceptions import EntityNotFoundException
    from src.core.storage import generate_presigned_get_url
    from src.repositories.time_repo import TimeRepository

    entry = await TimeRepository(db).get_by_id(time_entry_id, org_id=ctx.org_id)
    if not entry or (
        entry.user_id != ctx.user.id and not ctx.has_permission(Permission.TIME_READ_ALL)
    ):
        raise EntityNotFoundException("TimeEntry", time_entry_id)
    return [
        {
            **ScreenshotResponse.model_validate(shot).model_dump(),
            "download_url": generate_presigned_get_url(shot.s3_key),
        }
        for shot in entry.screenshots
        if not shot.is_deleted
    ]
