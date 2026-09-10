"""Pydantic v2 schemas for Notifications and Audit Logs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    org_id: str
    type: str
    title: str
    body: str | None
    resource_type: str | None
    resource_id: str | None
    actor_id: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class MarkReadRequest(BaseModel):
    notification_ids: list[str]


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    actor_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime
