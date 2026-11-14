"""Project View Engine API endpoints (Kanban, Calendar, Gantt CPM)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
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
    group_by: str | None = None,
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

    project = await ProjectRepository(db).get_by_id(project_id, org_id=ctx.org_id)
    if not project:
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
    sorts = sort_by.split(",")
    if len(sorts) > 5 or any(field.lstrip("-") not in allowed for field in sorts):
        raise ValidationException("Unsupported sort column or more than five columns")
    if group_by and group_by not in {"status_id", "assignee_id", "priority", "sprint_id"}:
        raise ValidationException("Unsupported grouping")
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
    ordering = []
    if group_by:
        ordering.append(getattr(Task, group_by).asc())
    for field in sorts:
        column = getattr(Task, field.lstrip("-"))
        ordering.append(column.desc() if descending or field.startswith("-") else column.asc())
    total = await db.scalar(select(func.count()).select_from(Task).where(*filters))
    ids = list(
        await db.scalars(
            select(Task.id).where(*filters).order_by(*ordering, Task.id).limit(limit).offset(offset)
        )
    )
    repo = TaskRepository(db)
    items = []
    rows = {t.id: t for t in await repo.get_many(ids, ctx.org_id)}
    for task_id in ids:
        task = rows[task_id]
        item = TaskResponse.model_validate(task)
        from src.services.custom_field_service import computed_values

        item.custom_fields = computed_values(task, project.custom_field_definitions)
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


@router.post("/calendar/{project_id}/feed")
async def create_calendar_feed(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    import hashlib
    import json
    import secrets

    from src.config import settings
    from src.core.exceptions import EntityNotFoundException
    from src.core.redis import get_redis
    from src.repositories.project_repo import ProjectRepository

    if not await ProjectRepository(db).get_by_id(project_id, org_id=ctx.org_id):
        raise EntityNotFoundException("Project", project_id)
    redis = await get_redis()
    owner = f"calendar:owner:{ctx.user.id}:{project_id}"
    old = await redis.get(owner)
    if old:
        await redis.delete("calendar:feed:" + old)
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    await redis.set(
        "calendar:feed:" + digest,
        json.dumps({"org_id": ctx.org_id, "project_id": project_id, "user_id": ctx.user.id}),
        ex=30 * 86400,
    )
    await redis.set(owner, digest, ex=30 * 86400)
    return {
        "url": f"{settings.OAUTH_PUBLIC_BASE_URL}/views/calendar/feed/{token}.ics",
        "expires_in_seconds": 30 * 86400,
    }


@router.delete("/calendar/{project_id}/feed", status_code=204)
async def revoke_calendar_feed(
    project_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
):
    from src.core.redis import get_redis

    redis = await get_redis()
    owner = f"calendar:owner:{ctx.user.id}:{project_id}"
    digest = await redis.getdel(owner)
    if digest:
        await redis.delete("calendar:feed:" + digest)


@router.get("/calendar/feed/{token}.ics")
async def subscribed_calendar(token: str, db: Annotated[AsyncSession, Depends(get_db_session)]):
    import hashlib
    import json

    from src.core.exceptions import EntityNotFoundException
    from src.core.redis import get_redis
    from src.core.tenant_scope import set_tenant_scope
    from src.models.auth import MemberStatus, OrgRole
    from src.repositories.user_repo import UserRepository

    redis = await get_redis()
    raw = await redis.get("calendar:feed:" + hashlib.sha256(token.encode()).hexdigest())
    if not raw:
        raise EntityNotFoundException("Calendar feed", "expired or revoked")
    data = json.loads(raw)
    repo = UserRepository(db)
    user = await repo.get_by_id(data["user_id"])
    member = await repo.get_org_membership(data["org_id"], data["user_id"])
    if (
        not user
        or not user.is_active
        or not member
        or member.status != MemberStatus.ACTIVE
        or member.role == OrgRole.CLIENT
    ):
        raise EntityNotFoundException("Calendar feed", "access revoked")
    await set_tenant_scope(db, data["org_id"])
    ctx = AuthContext(user=user, org_id=data["org_id"], role=member.role)
    result = await export_calendar(data["project_id"], ctx, db)
    result.headers["Cache-Control"] = "private, no-store"
    return result


class ScheduleRequest(BaseModel):
    start_date: date
    preview: bool = True


@router.post("/gantt/{project_id}/schedule")
async def schedule_project(
    project_id: str,
    payload: ScheduleRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_MANAGE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    from datetime import timedelta

    from sqlalchemy import select
    from src.models.project import Project, StatusCategory
    from src.schemas.task import TaskUpdate
    from src.services.task_service import TaskService

    await db.execute(
        select(Project.id)
        .where(Project.id == project_id, Project.org_id == ctx.org_id)
        .with_for_update()
    )
    chart = await ViewService(db).get_gantt_cpm(project_id, ctx.org_id)
    changes = []
    for node in chart.nodes:
        task = await TaskService(db).task_repo.get_by_id(node.id, org_id=ctx.org_id)
        if task.status.category == StatusCategory.DONE:
            continue
        start = payload.start_date + timedelta(days=node.early_start)
        end = start + timedelta(days=max(0, node.duration_days - 1))
        changes.append(
            {"id": node.id, "short_id": node.short_id, "start_date": start, "due_date": end}
        )
        if not payload.preview:
            await TaskService(db).update_task(
                node.id, ctx.org_id, TaskUpdate(start_date=start, due_date=end)
            )
    if not payload.preview:
        project = await db.get(Project, project_id)
        project.start_date = payload.start_date
        await db.flush()
    return {"project_id": project_id, "preview": payload.preview, "changes": changes}
