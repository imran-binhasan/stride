"""Project, Workflow Status, and Sprint API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.rbac import AuthContext, require_role
from src.models.auth import OrgRole
from src.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    SprintCreate,
    SprintResponse,
    WorkflowStatusCreate,
    WorkflowStatusResponse,
)
from src.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.MEMBER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    """Create a new project with auto-initialized 5-stage workflow statuses."""
    service = ProjectService(db)
    return await service.create_project(org_id=ctx.org_id, payload=payload)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.GUEST))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectResponse:
    """Retrieve details for a specific project."""
    service = ProjectService(db)
    return await service.get_project(project_id=project_id, org_id=ctx.org_id)


@router.get("/workspace/{workspace_id}", response_model=list[ProjectResponse])
async def list_workspace_projects(
    workspace_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.GUEST))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ProjectResponse]:
    """List all projects under a given workspace."""
    service = ProjectService(db)
    return await service.list_workspace_projects(
        workspace_id=workspace_id, org_id=ctx.org_id, limit=limit, offset=offset
    )


@router.post(
    "/{project_id}/statuses",
    response_model=WorkflowStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_custom_workflow_status(
    project_id: str,
    payload: WorkflowStatusCreate,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.PROJECT_MANAGER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkflowStatusResponse:
    """Add a custom workflow status column (e.g. 'QA Testing', 'Client Review')."""
    service = ProjectService(db)
    return await service.add_custom_status(
        project_id=project_id, org_id=ctx.org_id, payload=payload
    )


@router.delete("/statuses/{status_id}")
async def delete_workflow_status(
    status_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.PROJECT_MANAGER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Delete a custom workflow status column."""
    service = ProjectService(db)
    return await service.delete_status(status_id=status_id, org_id=ctx.org_id)


@router.post(
    "/{project_id}/sprints", response_model=SprintResponse, status_code=status.HTTP_201_CREATED
)
async def create_sprint(
    project_id: str,
    payload: SprintCreate,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.PROJECT_MANAGER))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SprintResponse:
    """Create a new agile sprint iteration under a project."""
    service = ProjectService(db)
    return await service.create_sprint(project_id=project_id, org_id=ctx.org_id, payload=payload)
