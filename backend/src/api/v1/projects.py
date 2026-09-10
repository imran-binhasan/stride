"""Project, Sprint, Label, and Project Access API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.rbac import AuthContext, Permission, require_permission
from src.schemas.project import (
    LabelCreate,
    LabelResponse,
    ProjectAccessGrantCreate,
    ProjectAccessGrantResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    SprintCreate,
    SprintResponse,
    SprintUpdate,
    WorkflowStatusCreate,
    WorkflowStatusResponse,
)
from src.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    return await ProjectService(db).create_project(
        org_id=ctx.org_id, creator_id=ctx.user.id, payload=payload
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    return await ProjectService(db).get_project(project_id=project_id, org_id=ctx.org_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    return await ProjectService(db).update_project(
        project_id=project_id, org_id=ctx.org_id, payload=payload
    )


@router.get("/workspace/{workspace_id}", response_model=list[ProjectResponse])
async def list_workspace_projects(
    workspace_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ProjectResponse]:
    return await ProjectService(db).list_workspace_projects(
        workspace_id=workspace_id, org_id=ctx.org_id, limit=limit, offset=offset
    )


@router.post(
    "/{project_id}/statuses",
    response_model=WorkflowStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_workflow_status(
    project_id: str,
    payload: WorkflowStatusCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkflowStatusResponse:
    return await ProjectService(db).add_custom_status(
        project_id=project_id, org_id=ctx.org_id, payload=payload
    )


@router.delete("/statuses/{status_id}")
async def delete_workflow_status(
    status_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    return await ProjectService(db).delete_status(status_id=status_id, org_id=ctx.org_id)


# ── Sprints ───────────────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/sprints", response_model=SprintResponse, status_code=status.HTTP_201_CREATED
)
async def create_sprint(
    project_id: str,
    payload: SprintCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.SPRINT_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SprintResponse:
    return await ProjectService(db).create_sprint(
        project_id=project_id, org_id=ctx.org_id, payload=payload
    )


@router.patch("/sprints/{sprint_id}", response_model=SprintResponse)
async def update_sprint(
    sprint_id: str,
    payload: SprintUpdate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.SPRINT_UPDATE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SprintResponse:
    return await ProjectService(db).update_sprint(
        sprint_id=sprint_id, org_id=ctx.org_id, payload=payload
    )


# ── Labels ────────────────────────────────────────────────────────────────────

@router.post("/labels", response_model=LabelResponse, status_code=status.HTTP_201_CREATED)
async def create_label(
    payload: LabelCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LabelResponse:
    return await ProjectService(db).create_label(org_id=ctx.org_id, payload=payload)


@router.get("/labels", response_model=list[LabelResponse])
async def list_labels(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[LabelResponse]:
    return await ProjectService(db).list_labels(org_id=ctx.org_id)


# ── Project Access Grants ─────────────────────────────────────────────────────

@router.post(
    "/{project_id}/access", response_model=ProjectAccessGrantResponse, status_code=status.HTTP_201_CREATED
)
async def add_project_access(
    project_id: str,
    payload: ProjectAccessGrantCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectAccessGrantResponse:
    return await ProjectService(db).add_access_grant(
        project_id=project_id, org_id=ctx.org_id, granted_by_id=ctx.user.id, payload=payload
    )


@router.get("/{project_id}/access", response_model=list[ProjectAccessGrantResponse])
async def list_project_access(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ProjectAccessGrantResponse]:
    return await ProjectService(db).list_access_grants(
        project_id=project_id, org_id=ctx.org_id
    )
