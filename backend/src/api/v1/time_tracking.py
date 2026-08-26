"""Time Tracking, Telemetry Ingestion, and Screenshot API endpoints."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.exceptions import PermissionDeniedException
from src.core.rbac import AuthContext, require_role
from src.models.auth import OrgRole
from src.repositories.user_repo import UserRepository
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
    TimeEntryResponse,
)
from src.services.time_service import TimeService

router = APIRouter(prefix="/time-tracking", tags=["Time Tracking"])


@router.post("/timer/start", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
async def start_timer(
    payload: StartTimerRequest,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TimeEntryResponse:
    """Start an active timer on a task."""
    service = TimeService(db)
    return await service.start_timer(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        payload=payload,
    )


@router.post("/timer/stop", response_model=TimeEntryResponse)
async def stop_timer(
    payload: StopTimerRequest,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TimeEntryResponse:
    """Stop the active timer and finalize duration/activity percent."""
    service = TimeService(db)
    return await service.stop_timer(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        payload=payload,
    )


@router.get("/timer/active", response_model=TimeEntryResponse | None)
async def get_active_timer(
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TimeEntryResponse | None:
    """Get the currently running timer for the user."""
    service = TimeService(db)
    return await service.get_active_timer(user_id=ctx.user.id)


@router.post("/telemetry/heartbeat", response_model=TelemetryHeartbeatResponse)
async def send_telemetry_heartbeat(
    payload: TelemetryHeartbeatRequest,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TelemetryHeartbeatResponse:
    """Ingest 30-second activity telemetry from desktop companion daemon."""
    service = TimeService(db)
    return await service.ingest_telemetry(user_id=ctx.user.id, payload=payload)


@router.post("/screenshots/presigned-url", response_model=ScreenshotPresignedResponse)
async def get_screenshot_presigned_url(
    payload: ScreenshotPresignedRequest,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScreenshotPresignedResponse:
    """Obtain a secure presigned S3 upload URL for desktop screenshot capture."""
    service = TimeService(db)
    return await service.generate_screenshot_upload_url(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        payload=payload,
    )


@router.post(
    "/screenshots/confirm", response_model=ScreenshotResponse, status_code=status.HTTP_201_CREATED
)
async def confirm_screenshot_upload(
    payload: ScreenshotConfirmRequest,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScreenshotResponse:
    """Confirm screenshot upload completion and persist log metadata."""
    service = TimeService(db)
    return await service.confirm_screenshot(
        org_id=ctx.org_id, user_id=ctx.user.id, payload=payload
    )


@router.delete("/screenshots/{screenshot_id}")
async def delete_screenshot(
    screenshot_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Employee self-service deletion of screenshot with time deduction."""
    service = TimeService(db)
    return await service.delete_screenshot(screenshot_id=screenshot_id, user_id=ctx.user.id)


@router.get("/reports/daily", response_model=DailyActivitySummaryResponse)
async def get_daily_activity_report(
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    target_date: Annotated[date | None, Query(alias="date")] = None,
    target_user_id: Annotated[str | None, Query(alias="user_id")] = None,
) -> DailyActivitySummaryResponse:
    """Retrieve day start/end, total screen time, worked hours, idle hours, and 10-minute block timeline."""
    service = TimeService(db)
    chosen_date = target_date or datetime.now(UTC).date()
    # Users can view their own summary; Managers/Admins can view a team member's summary,
    # but only for members of the *same* organization (no cross-tenant access).
    uid = ctx.user.id
    if target_user_id and target_user_id != ctx.user.id:
        if not ctx.has_min_role(OrgRole.PROJECT_MANAGER):
            raise PermissionDeniedException(
                "Requires at least 'PROJECT_MANAGER' role to view another user's report"
            )
        membership = await UserRepository(db).get_org_membership(
            org_id=ctx.org_id, user_id=target_user_id
        )
        if not membership:
            raise PermissionDeniedException(
                "Target user is not a member of this organization"
            )
        uid = target_user_id
    return await service.get_daily_activity_summary(user_id=uid, target_date=chosen_date)
