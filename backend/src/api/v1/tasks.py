"""Task, Comment, Attachment, and Dependency API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.rbac import AuthContext, Permission, require_permission
from src.models.auth import OrgRole
from src.models.task import TaskPriority
from src.schemas.task import (
    CommentCreate,
    CommentResponse,
    DependencyCreate,
    DependencyResponse,
    SubtaskCreate,
    TaskChildResponse,
    TaskCreate,
    TaskMoveRequest,
    TaskResponse,
    TaskUpdate,
)
from src.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    if ctx.role == OrgRole.CLIENT:
        # Clients may submit tickets, without assigning work or linking internal task trees.
        payload = TaskCreate(
            project_id=payload.project_id,
            title=payload.title,
            description=payload.description,
            is_client_ticket=True,
        )
    return await TaskService(db).create_task(
        org_id=ctx.org_id, creator_id=ctx.user.id, payload=payload
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    task = await TaskService(db).get_task(task_id=task_id, org_id=ctx.org_id)
    if ctx.role == OrgRole.CLIENT:
        task.comments = [c for c in task.comments if not c.is_internal]
        task.attachments = [
            a
            for a in task.attachments
            if a.comment_id is None or a.comment_id in {c.id for c in task.comments}
        ]
    return task


@router.get("/project/{project_id}", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    sprint_id: Annotated[str | None, Query()] = None,
    status_id: Annotated[str | None, Query()] = None,
    assignee_id: Annotated[str | None, Query()] = None,
    priority: TaskPriority | None = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TaskResponse]:
    return await TaskService(db).list_tasks(
        project_id=project_id,
        org_id=ctx.org_id,
        sprint_id=sprint_id,
        status_id=status_id,
        assignee_id=assignee_id,
        priority=priority,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    payload: TaskUpdate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    return await TaskService(db).update_task(task_id=task_id, org_id=ctx.org_id, payload=payload)


@router.patch("/{task_id}/move", response_model=TaskResponse)
async def move_task(
    task_id: str,
    payload: TaskMoveRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    return await TaskService(db).move_task(task_id=task_id, org_id=ctx.org_id, payload=payload)


# ── Comments ──────────────────────────────────────────────────────────────────


@router.post(
    "/{task_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED
)
async def add_comment(
    task_id: str,
    payload: CommentCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.COMMENT_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> CommentResponse:
    if ctx.role == OrgRole.CLIENT:
        payload.is_internal = False
    return await TaskService(db).add_comment(
        task_id=task_id, org_id=ctx.org_id, author_id=ctx.user.id, payload=payload
    )


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.COMMENT_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    can_delete_any = ctx.has_permission(Permission.COMMENT_DELETE_ANY)
    return await TaskService(db).delete_comment(
        comment_id=comment_id,
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        can_delete_any=can_delete_any,
    )


# ── Dependencies ──────────────────────────────────────────────────────────────


@router.post(
    "/{task_id}/dependencies",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_dependency(
    task_id: str,
    payload: DependencyCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DependencyResponse:
    return await TaskService(db).add_dependency(task_id=task_id, org_id=ctx.org_id, payload=payload)


@router.post("/{task_id}/subtasks", response_model=TaskChildResponse, status_code=201)
async def add_subtask(
    task_id: str,
    payload: SubtaskCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    return await TaskService(db).add_subtask(task_id, ctx.org_id, ctx.user.id, payload)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_DELETE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    await TaskService(db).delete_task(task_id, ctx.org_id)


@router.delete("/{task_id}/dependencies/{dependency_id}", status_code=204)
async def delete_dependency(
    task_id: str,
    dependency_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    await TaskService(db).delete_dependency(task_id, dependency_id, ctx.org_id)
