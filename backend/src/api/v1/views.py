"""Project View Engine API endpoints (Kanban, Calendar, Gantt CPM)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.rbac import AuthContext, Permission, require_permission
from src.schemas.views import CalendarViewResponse, GanttChartResponse, KanbanBoardResponse
from src.services.view_service import ViewService

router = APIRouter(prefix="/views", tags=["Views"])


@router.get("/kanban/{project_id}", response_model=KanbanBoardResponse)
async def get_kanban_board(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    sprint_id: Annotated[str | None, Query()] = None,
) -> KanbanBoardResponse:
    return await ViewService(db).get_kanban_board(
        project_id=project_id, org_id=ctx.org_id, sprint_id=sprint_id
    )


@router.get("/calendar/{project_id}", response_model=CalendarViewResponse)
async def get_calendar_view(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    year: Annotated[int | None, Query(ge=2020, le=2050)] = None,
) -> CalendarViewResponse:
    return await ViewService(db).get_calendar_view(
        project_id=project_id, org_id=ctx.org_id, month=month, year=year
    )


@router.get("/gantt/{project_id}", response_model=GanttChartResponse)
async def get_gantt_cpm_view(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GanttChartResponse:
    return await ViewService(db).get_gantt_cpm(project_id=project_id, org_id=ctx.org_id)


@router.get("/table/{project_id}")
async def get_table(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    sort_by: str = "position",
    descending: bool = False,
    search: Annotated[str | None, Query(max_length=255)] = None,
    status_id: str | None = None,
    assignee_id: str | None = None,
    sprint_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    from sqlalchemy import func, select
    from src.core.exceptions import ValidationException
    from src.models.task import Task
    from src.repositories.project_repo import ProjectRepository
    from src.repositories.task_repo import TaskRepository
    from src.schemas.task import TaskResponse

    if not await ProjectRepository(db).get_by_id(project_id, org_id=ctx.org_id):
        from src.core.exceptions import EntityNotFoundException

        raise EntityNotFoundException("Project", project_id)
    allowed = {
        "position",
        "title",
        "priority",
        "due_date",
        "created_at",
        "updated_at",
        "story_points",
    }
    if sort_by not in allowed:
        raise ValidationException("Unsupported sort column")
    filters = [
        Task.project_id == project_id,
        Task.org_id == ctx.org_id,
        Task.parent_task_id.is_(None),
    ]
    for field, value in (
        ("status_id", status_id),
        ("assignee_id", assignee_id),
        ("sprint_id", sprint_id),
    ):
        if value:
            filters.append(getattr(Task, field) == value)
    if search:
        filters.append(
            Task.title.ilike(
                "%" + search.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"
            )
        )
    column = getattr(Task, sort_by)
    total = await db.scalar(select(func.count()).select_from(Task).where(*filters))
    ids = list(
        await db.scalars(
            select(Task.id)
            .where(*filters)
            .order_by(column.desc() if descending else column.asc(), Task.id)
            .limit(limit)
            .offset(offset)
        )
    )
    repo = TaskRepository(db)
    items = []
    rows = {t.id: t for t in await repo.get_many(ids, ctx.org_id)}
    for task_id in ids:
        task = rows[task_id]
        item = TaskResponse.model_validate(task)
        item.comments, item.attachments = [], []
        items.append(item)
    return {
        "project_id": project_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/calendar/{project_id}/export.ics")
async def export_calendar(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.TASK_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    from datetime import UTC, datetime, timedelta

    from fastapi.responses import Response

    calendar = await ViewService(db).get_calendar_view(project_id, ctx.org_id)

    def escape(value):
        return (
            value.replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\r", "")
        )

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//A3Zen//Stride//EN", "CALSCALE:GREGORIAN"]
    for event in calendar.events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{event.id}@stride",
            f"DTSTAMP:{datetime.now(UTC):%Y%m%dT%H%M%SZ}",
            f"DTSTART;VALUE=DATE:{event.due_date:%Y%m%d}",
            f"DTEND;VALUE=DATE:{event.due_date + timedelta(days=1):%Y%m%d}",
            "SUMMARY:" + escape(event.title),
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    # Fold on UTF-8 byte boundaries to honor the iCalendar 75-octet line limit.
    folded = []
    for line in lines:
        part = ""
        for char in line:
            if len((part + char).encode()) > 75:
                folded.append(part)
                part = " "
            part += char
        folded.append(part)
    return Response(
        "\r\n".join(folded) + "\r\n",
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="stride-calendar.ics"'},
    )
