"""Task, Subtask, and Dependency API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.rbac import AuthContext, require_role
from src.models.auth import OrgRole
from src.schemas.task import (
    DependencyCreate,
    DependencyResponse,
    SubtaskCreate,
    SubtaskResponse,
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
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    """Create a new task with auto-assigned short identifier and custom fields."""
    service = TaskService(db)
    return await service.create_task(
        org_id=ctx.org_id,
        creator_id=ctx.user.id,
        payload=payload,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.GUEST))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    """Retrieve detailed task entity."""
    service = TaskService(db)
    return await service.get_task(task_id=task_id, org_id=ctx.org_id)


@router.get("/project/{project_id}", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.GUEST))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    sprint_id: Annotated[str | None, Query()] = None,
    status_id: Annotated[str | None, Query()] = None,
    assignee_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TaskResponse]:
    """List tasks in a project with optional sprint, status, and assignee filters."""
    service = TaskService(db)
    return await service.list_tasks(
        project_id=project_id,
        org_id=ctx.org_id,
        sprint_id=sprint_id,
        status_id=status_id,
        assignee_id=assignee_id,
        limit=limit,
        offset=offset,
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    payload: TaskUpdate,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    """Update task details, custom fields, assignee, or priority."""
    service = TaskService(db)
    return await service.update_task(task_id=task_id, org_id=ctx.org_id, payload=payload)


@router.patch("/{task_id}/move", response_model=TaskResponse)
async def move_task(
    task_id: str,
    payload: TaskMoveRequest,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    """Update task status and Kanban position."""
    service = TaskService(db)
    return await service.move_task(task_id=task_id, org_id=ctx.org_id, payload=payload)


@router.post(
    "/{task_id}/subtasks", response_model=SubtaskResponse, status_code=status.HTTP_201_CREATED
)
async def add_subtask(
    task_id: str,
    payload: SubtaskCreate,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SubtaskResponse:
    """Add a subtask to a parent task."""
    service = TaskService(db)
    return await service.add_subtask(task_id=task_id, org_id=ctx.org_id, payload=payload)


@router.post(
    "/{task_id}/dependencies",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_dependency(
    task_id: str,
    payload: DependencyCreate,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DependencyResponse:
    """Link tasks with directional dependency, validated against cycles."""
    service = TaskService(db)
    return await service.add_dependency(task_id=task_id, org_id=ctx.org_id, payload=payload)
