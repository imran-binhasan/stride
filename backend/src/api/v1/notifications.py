"""Notifications and Audit Log API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.rbac import AuthContext, Permission, require_permission
from src.schemas.notifications import AuditLogResponse, MarkReadRequest, NotificationResponse
from src.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[NotificationResponse]:
    return await NotificationService(db).list_notifications(
        user_id=ctx.user.id, org_id=ctx.org_id, unread_only=unread_only, limit=limit
    )


@router.post("/mark-read")
async def mark_notifications_read(
    payload: MarkReadRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    return await NotificationService(db).mark_read(
        user_id=ctx.user.id, notification_ids=payload.notification_ids
    )


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLogResponse]:
    """Admin-only audit trail. Requires org:update (ORG_ADMIN+)."""
    return await NotificationService(db).list_audit_logs(
        org_id=ctx.org_id, limit=limit, offset=offset
    )
