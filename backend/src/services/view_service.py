"""View aggregation engines: Kanban Board, Calendar, and Gantt Critical Path Method (CPM)."""

from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.exceptions import EntityNotFoundException
from src.repositories.project_repo import ProjectRepository
from src.repositories.task_repo import TaskRepository
from src.schemas.project import WorkflowStatusResponse
from src.schemas.task import TaskResponse
from src.schemas.views import (
    CalendarTaskItem,
    CalendarViewResponse,
    GanttChartResponse,
    GanttNodeResponse,
    KanbanBoardResponse,
    KanbanColumnResponse,
)


class ViewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.task_repo = TaskRepository(db)

    async def get_kanban_board(
        self,
        project_id: str,
        org_id: str,
        sprint_id: str | None = None,
    ) -> KanbanBoardResponse:
        project = await self.project_repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)

        tasks = await self.task_repo.list_by_project(
            project_id=project_id,
            org_id=org_id,
            sprint_id=sprint_id,
            limit=settings.MAX_VIEW_TASKS,
        )

        # Group tasks by status ID
        tasks_by_status: dict[str, list[TaskResponse]] = defaultdict(list)
        for task in tasks:
            tasks_by_status[task.status_id].append(TaskResponse.model_validate(task))

        columns: list[KanbanColumnResponse] = []
        for status in project.statuses:
            status_tasks = tasks_by_status.get(status.id, [])
            columns.append(
                KanbanColumnResponse(
                    status=WorkflowStatusResponse.model_validate(status),
                    task_count=len(status_tasks),
                    tasks=status_tasks,
                )
            )

        return KanbanBoardResponse(
            project_id=project_id,
            total_tasks=len(tasks),
            columns=columns,
        )

    async def get_calendar_view(
        self,
        project_id: str,
        org_id: str,
        month: int | None = None,
        year: int | None = None,
    ) -> CalendarViewResponse:
        project = await self.project_repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)

        tasks = await self.task_repo.list_by_project(
            project_id=project_id, org_id=org_id, limit=settings.MAX_VIEW_TASKS
        )

        events: list[CalendarTaskItem] = []
        for t in tasks:
            if t.due_date is not None:
                if month is not None and t.due_date.month != month:
                    continue
                if year is not None and t.due_date.year != year:
                    continue

                events.append(
                    CalendarTaskItem(
                        id=t.id,
                        short_id=t.short_id,
                        title=t.title,
                        status_name=t.status.name if t.status else "To Do",
                        status_color=t.status.color if t.status else "#6B7280",
                        due_date=t.due_date,
                        assignee_name=t.assignee.full_name if t.assignee else None,
                    )
                )

        return CalendarViewResponse(
            project_id=project_id,
            month=month,
            year=year,
            events=events,
        )

    async def get_gantt_cpm(self, project_id: str, org_id: str) -> GanttChartResponse:
        """Calculate project schedule and critical path using Critical Path Method (CPM)."""
        project = await self.project_repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)

        tasks = await self.task_repo.list_by_project(
            project_id=project_id, org_id=org_id, limit=settings.MAX_VIEW_TASKS
        )
        if not tasks:
            return GanttChartResponse(
                project_id=project_id, project_duration_days=0, critical_path=[], nodes=[]
            )

        # Durations (default to 1 day or story points / 8 hours if specified)
        durations: dict[str, int] = {}
        for t in tasks:
            if t.estimated_hours:
                durations[t.id] = max(1, int(round(t.estimated_hours / 8.0)))
            elif t.story_points:
                durations[t.id] = max(1, int(round(t.story_points)))
            else:
                durations[t.id] = 1

        # Build adjacency graph
        preds: dict[str, list[tuple[str, int]]] = defaultdict(list)
        succs: dict[str, list[tuple[str, int]]] = defaultdict(list)

        for t in tasks:
            for dep in t.dependencies_out:
                preds[dep.successor_id].append((t.id, dep.lag_days))
                succs[t.id].append((dep.successor_id, dep.lag_days))

        # Topological Sort (Kahn's algorithm)
        in_degree: dict[str, int] = {t.id: 0 for t in tasks}
        for t in tasks:
            for dep in t.dependencies_out:
                in_degree[dep.successor_id] = in_degree.get(dep.successor_id, 0) + 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        topo_order: list[str] = []

        while queue:
            curr = queue.pop(0)
            topo_order.append(curr)
            for succ_id, _ in succs.get(curr, []):
                in_degree[succ_id] -= 1
                if in_degree[succ_id] == 0:
                    queue.append(succ_id)

        # Fallback if any unvisited nodes remain
        for t in tasks:
            if t.id not in topo_order:
                topo_order.append(t.id)

        # 1. Forward Pass (ES & EF)
        early_start: dict[str, int] = {}
        early_finish: dict[str, int] = {}

        for tid in topo_order:
            if not preds[tid]:
                es = 0
            else:
                es = max(early_finish.get(p_id, 0) + lag for p_id, lag in preds[tid])
            early_start[tid] = es
            early_finish[tid] = es + durations[tid]

        project_duration = max(early_finish.values()) if early_finish else 0

        # 2. Backward Pass (LS & LF)
        late_start: dict[str, int] = {}
        late_finish: dict[str, int] = {}

        for tid in reversed(topo_order):
            if not succs[tid]:
                lf = project_duration
            else:
                lf = min(late_start.get(s_id, project_duration) - lag for s_id, lag in succs[tid])
            late_finish[tid] = lf
            late_start[tid] = lf - durations[tid]

        # 3. Float & Critical Path determination
        critical_path_ids: list[str] = []
        nodes: list[GanttNodeResponse] = []

        for t in tasks:
            tid = t.id
            es = early_start.get(tid, 0)
            ef = early_finish.get(tid, durations[tid])
            ls = late_start.get(tid, 0)
            lf = late_finish.get(tid, project_duration)
            total_float = max(0, lf - ef)
            is_critical = total_float == 0

            if is_critical:
                critical_path_ids.append(tid)

            nodes.append(
                GanttNodeResponse(
                    id=tid,
                    short_id=t.short_id,
                    title=t.title,
                    duration_days=durations[tid],
                    early_start=es,
                    early_finish=ef,
                    late_start=ls,
                    late_finish=lf,
                    total_float=total_float,
                    is_critical=is_critical,
                    dependencies_out=[succ_id for succ_id, _ in succs.get(tid, [])],
                )
            )

        return GanttChartResponse(
            project_id=project_id,
            project_duration_days=project_duration,
            critical_path=critical_path_ids,
            nodes=nodes,
        )
