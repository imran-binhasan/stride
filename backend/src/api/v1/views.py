"""Project View Engine API endpoints (Kanban, Calendar, Gantt CPM)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.rbac import AuthContext, require_role
from src.models.auth import OrgRole
from src.schemas.views import (
    CalendarViewResponse,
    GanttChartResponse,
    KanbanBoardResponse,
)
from src.services.view_service import ViewService

router = APIRouter(prefix="/views", tags=["Views"])


@router.get("/kanban/{project_id}", response_model=KanbanBoardResponse)
async def get_kanban_board(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.GUEST))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    sprint_id: Annotated[str | None, Query()] = None,
) -> KanbanBoardResponse:
    """Retrieve Kanban board column aggregations with tasks ordered by position."""
    service = ViewService(db)
    return await service.get_kanban_board(
        project_id=project_id,
        org_id=ctx.org_id,
        sprint_id=sprint_id,
    )


@router.get("/calendar/{project_id}", response_model=CalendarViewResponse)
async def get_calendar_view(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.GUEST))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    year: Annotated[int | None, Query(ge=2020, le=2050)] = None,
) -> CalendarViewResponse:
    """Retrieve scheduled tasks and milestones for interactive calendar view."""
    service = ViewService(db)
    return await service.get_calendar_view(
        project_id=project_id,
        org_id=ctx.org_id,
        month=month,
        year=year,
    )


@router.get("/gantt/{project_id}", response_model=GanttChartResponse)
async def get_gantt_cpm_view(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(OrgRole.GUEST))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GanttChartResponse:
    """Retrieve Gantt timeline with Critical Path Method (CPM) and slack calculations."""
    service = ViewService(db)
    return await service.get_gantt_cpm(
        project_id=project_id,
        org_id=ctx.org_id,
    )
