"""Tenant-scoped task collaboration and storage endpoints."""

import asyncio
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.database import get_db_session
from src.core.events import record_change
from src.core.exceptions import EntityNotFoundException, ValidationException
from src.core.rbac import AuthContext, Permission, require_permission
from src.core.redis import get_redis
from src.core.storage import (
    delete_object,
    generate_presigned_get_url,
    generate_presigned_put_url,
    head_object,
)
from src.models.auth import MemberStatus
from src.models.task import Attachment, ChecklistItem, TaskAssignee, TaskLabel, TaskWatcher
from src.repositories.project_repo import ProjectRepository
from src.repositories.task_repo import TaskRepository
from src.repositories.user_repo import UserRepository
from src.schemas.task import AttachmentResponse

router = APIRouter(prefix="/tasks", tags=["Task collaboration"])
DB = Annotated[AsyncSession, Depends(get_db_session)]
Read = Annotated[AuthContext, Depends(require_permission(Permission.TASK_READ))]
Write = Annotated[AuthContext, Depends(require_permission(Permission.TASK_UPDATE))]
Assign = Annotated[AuthContext, Depends(require_permission(Permission.TASK_ASSIGN))]


async def task_or_404(db, task_id, org_id):
    task = await TaskRepository(db).get_by_id(task_id, org_id=org_id)
    if not task:
        raise EntityNotFoundException("Task", task_id)
    return task


@router.put("/{task_id}/assignees/{user_id}", status_code=204)
async def assign(task_id: str, user_id: str, ctx: Assign, db: DB):
    task = await task_or_404(db, task_id, ctx.org_id)
    member = await UserRepository(db).get_org_membership(ctx.org_id, user_id)
    if not member or member.status != MemberStatus.ACTIVE:
        raise ValidationException("Assignee must be active in this organization")
    exists = await db.scalar(
        select(TaskAssignee).where(TaskAssignee.task_id == task_id, TaskAssignee.user_id == user_id)
    )
    if not exists:
        db.add(TaskAssignee(task_id=task_id, user_id=user_id))
        record_change(db, ctx.org_id, task.project_id, "TASK_ASSIGNED", task_id, ctx.user.id)
        from src.services.notification_service import NotificationService

        await NotificationService(db).create_notification(
            user_id,
            ctx.org_id,
            "task.assigned",
            f"Assigned: {task.title}",
            resource_type="task",
            resource_id=task_id,
            actor_id=ctx.user.id,
        )


@router.delete("/{task_id}/assignees/{user_id}", status_code=204)
async def unassign(task_id: str, user_id: str, ctx: Assign, db: DB):
    task = await task_or_404(db, task_id, ctx.org_id)
    row = await db.scalar(
        select(TaskAssignee).where(TaskAssignee.task_id == task_id, TaskAssignee.user_id == user_id)
    )
    if row:
        await db.delete(row)
    if task.assignee_id == user_id:
        task.assignee_id = None
    record_change(db, ctx.org_id, task.project_id, "TASK_UPDATED", task_id, ctx.user.id)


@router.put("/{task_id}/labels/{label_id}", status_code=204)
async def add_label(task_id: str, label_id: str, ctx: Write, db: DB):
    task = await task_or_404(db, task_id, ctx.org_id)
    if not await ProjectRepository(db).get_label_by_id(label_id, ctx.org_id):
        raise EntityNotFoundException("Label", label_id)
    exists = await db.scalar(
        select(TaskLabel).where(TaskLabel.task_id == task_id, TaskLabel.label_id == label_id)
    )
    if not exists:
        db.add(TaskLabel(task_id=task_id, label_id=label_id))
        record_change(db, ctx.org_id, task.project_id, "TASK_UPDATED", task_id, ctx.user.id)


@router.delete("/{task_id}/labels/{label_id}", status_code=204)
async def remove_label(task_id: str, label_id: str, ctx: Write, db: DB):
    task = await task_or_404(db, task_id, ctx.org_id)
    row = await db.scalar(
        select(TaskLabel).where(TaskLabel.task_id == task_id, TaskLabel.label_id == label_id)
    )
    if row:
        await db.delete(row)
        record_change(db, ctx.org_id, task.project_id, "TASK_UPDATED", task_id, ctx.user.id)


@router.put("/{task_id}/watch", status_code=204)
async def watch(task_id: str, ctx: Read, db: DB):
    await task_or_404(db, task_id, ctx.org_id)
    row = await db.scalar(
        select(TaskWatcher).where(
            TaskWatcher.task_id == task_id, TaskWatcher.user_id == ctx.user.id
        )
    )
    if not row:
        db.add(TaskWatcher(task_id=task_id, user_id=ctx.user.id))


@router.delete("/{task_id}/watch", status_code=204)
async def unwatch(task_id: str, ctx: Read, db: DB):
    await task_or_404(db, task_id, ctx.org_id)
    row = await db.scalar(
        select(TaskWatcher).where(
            TaskWatcher.task_id == task_id, TaskWatcher.user_id == ctx.user.id
        )
    )
    if row:
        await db.delete(row)


class ChecklistCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    position: int = Field(default=0, ge=0)


class ChecklistUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    is_completed: bool | None = None
    position: int | None = Field(default=None, ge=0)


class ChecklistResponse(ChecklistCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    is_completed: bool


@router.get("/{task_id}/checklist", response_model=list[ChecklistResponse])
async def list_checklist(task_id: str, ctx: Read, db: DB):
    await task_or_404(db, task_id, ctx.org_id)
    return list(
        await db.scalars(
            select(ChecklistItem)
            .where(ChecklistItem.task_id == task_id)
            .order_by(ChecklistItem.position, ChecklistItem.id)
        )
    )


@router.post("/{task_id}/checklist", response_model=ChecklistResponse, status_code=201)
async def create_checklist(task_id: str, payload: ChecklistCreate, ctx: Write, db: DB):
    task = await task_or_404(db, task_id, ctx.org_id)
    if not payload.title.strip():
        raise ValidationException("Title cannot be blank")
    item = ChecklistItem(task_id=task_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    record_change(db, ctx.org_id, task.project_id, "TASK_UPDATED", task_id, ctx.user.id)
    return item


@router.patch("/{task_id}/checklist/{item_id}", response_model=ChecklistResponse)
async def update_checklist(
    task_id: str, item_id: str, payload: ChecklistUpdate, ctx: Write, db: DB
):
    task = await task_or_404(db, task_id, ctx.org_id)
    item = await db.scalar(
        select(ChecklistItem).where(ChecklistItem.id == item_id, ChecklistItem.task_id == task_id)
    )
    if not item:
        raise EntityNotFoundException("ChecklistItem", item_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None or key == "title" and not value.strip():
            raise ValidationException(f"Invalid {key}")
        setattr(item, key, value)
    await db.flush()
    record_change(db, ctx.org_id, task.project_id, "TASK_UPDATED", task_id, ctx.user.id)
    return item


@router.delete("/{task_id}/checklist/{item_id}", status_code=204)
async def delete_checklist(task_id: str, item_id: str, ctx: Write, db: DB):
    task = await task_or_404(db, task_id, ctx.org_id)
    item = await db.scalar(
        select(ChecklistItem).where(ChecklistItem.id == item_id, ChecklistItem.task_id == task_id)
    )
    if not item:
        raise EntityNotFoundException("ChecklistItem", item_id)
    await db.delete(item)
    record_change(db, ctx.org_id, task.project_id, "TASK_UPDATED", task_id, ctx.user.id)


class UploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    file_size: int = Field(ge=1, le=25 * 1024 * 1024)
    mime_type: str = Field(default="application/octet-stream", pattern=r"^[\w.+-]+/[\w.+-]+$")


class ConfirmUpload(BaseModel):
    attachment_id: str


@router.post("/{task_id}/attachments/upload-url")
async def attachment_upload(task_id: str, payload: UploadRequest, ctx: Write, db: DB):
    task = await task_or_404(db, task_id, ctx.org_id)
    attachment_id = str(uuid.uuid4())
    key = f"{ctx.org_id}/{task.project_id}/attachments/{attachment_id}"
    reservation = {
        **payload.model_dump(),
        "storage_key": key,
        "task_id": task_id,
        "user_id": ctx.user.id,
    }
    redis = await get_redis()
    await redis.set(f"upload:attachment:{attachment_id}", json.dumps(reservation), ex=600)
    return {
        "attachment_id": attachment_id,
        "upload_url": generate_presigned_put_url(key, payload.mime_type),
        "expires_in_seconds": 300,
    }


@router.post("/{task_id}/attachments/confirm", response_model=AttachmentResponse, status_code=201)
async def confirm_attachment(task_id: str, payload: ConfirmUpload, ctx: Write, db: DB):
    task = await task_or_404(db, task_id, ctx.org_id)
    existing = await db.get(Attachment, payload.attachment_id)
    if existing:
        if existing.task_id != task_id or existing.uploaded_by_id != ctx.user.id:
            raise EntityNotFoundException("Attachment", payload.attachment_id)
        return existing
    redis = await get_redis()
    raw = await redis.get(f"upload:attachment:{payload.attachment_id}")
    data = json.loads(raw) if raw else {}
    if data.get("task_id") != task_id or data.get("user_id") != ctx.user.id:
        raise ValidationException("Upload reservation is missing or expired")
    if settings.ENVIRONMENT != "test":
        try:
            meta = await asyncio.to_thread(head_object, data["storage_key"])
        except Exception:
            raise ValidationException("Uploaded file could not be verified") from None
        if (
            meta["ContentLength"] != data["file_size"]
            or meta.get("ContentType") != data["mime_type"]
        ):
            raise ValidationException("Uploaded file metadata does not match reservation")
    item = await TaskRepository(db).add_attachment(
        task_id,
        ctx.user.id,
        data["file_name"],
        data["file_size"],
        data["mime_type"],
        data["storage_key"],
    )
    # The returned reservation identifier remains the attachment identifier for retries.
    item.id = payload.attachment_id
    await db.flush()
    record_change(db, ctx.org_id, task.project_id, "TASK_UPDATED", task_id, ctx.user.id)
    return item


@router.get("/{task_id}/attachments/{attachment_id}/download-url")
async def download_attachment(task_id: str, attachment_id: str, ctx: Read, db: DB):
    await task_or_404(db, task_id, ctx.org_id)
    item = await db.scalar(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.task_id == task_id)
    )
    if not item:
        raise EntityNotFoundException("Attachment", attachment_id)
    return {"download_url": generate_presigned_get_url(item.storage_key), "expires_in_seconds": 300}


@router.delete("/{task_id}/attachments/{attachment_id}", status_code=204)
async def delete_attachment(task_id: str, attachment_id: str, ctx: Write, db: DB):
    task = await task_or_404(db, task_id, ctx.org_id)
    item = await db.scalar(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.task_id == task_id)
    )
    if not item:
        raise EntityNotFoundException("Attachment", attachment_id)
    if settings.ENVIRONMENT != "test":
        await asyncio.to_thread(delete_object, item.storage_key)
    await db.delete(item)
    record_change(db, ctx.org_id, task.project_id, "TASK_UPDATED", task_id, ctx.user.id)
