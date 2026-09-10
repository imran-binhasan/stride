"""Notification and Audit Log service."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.notifications import AuditLog, Notification
from src.schemas.notifications import AuditLogResponse, NotificationResponse


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_notifications(
        self, user_id: str, org_id: str, unread_only: bool = False, limit: int = 50
    ) -> list[NotificationResponse]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id, Notification.org_id == org_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        result = await self.db.execute(stmt)
        return [NotificationResponse.model_validate(n) for n in result.scalars().all()]

    async def mark_read(self, user_id: str, notification_ids: list[str]) -> dict:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.id.in_(notification_ids))
            .values(is_read=True, read_at=datetime.now(UTC))
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return {"marked": len(notification_ids)}

    async def create_notification(
        self,
        user_id: str,
        org_id: str,
        type: str,
        title: str,
        body: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        actor_id: str | None = None,
    ) -> Notification:
        n = Notification(
            user_id=user_id,
            org_id=org_id,
            type=type,
            title=title,
            body=body,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
        )
        self.db.add(n)
        await self.db.flush()
        return n

    async def list_audit_logs(
        self, org_id: str, limit: int = 100, offset: int = 0
    ) -> list[AuditLogResponse]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.org_id == org_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return [AuditLogResponse.model_validate(a) for a in result.scalars().all()]

    async def log_audit(
        self,
        org_id: str,
        action: str,
        actor_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        entry = AuditLog(
            org_id=org_id,
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(entry)
        await self.db.flush()
