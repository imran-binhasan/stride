"""Pydantic v2 schemas for Kanban, Calendar, and Gantt CPM View engines."""

from datetime import date

from pydantic import BaseModel
from src.schemas.project import WorkflowStatusResponse
from src.schemas.task import TaskResponse


class KanbanColumnResponse(BaseModel):
    status: WorkflowStatusResponse
    task_count: int
    tasks: list[TaskResponse] = []


class KanbanBoardResponse(BaseModel):
    project_id: str
    total_tasks: int
    columns: list[KanbanColumnResponse] = []


class CalendarTaskItem(BaseModel):
    id: str
    short_id: str
    title: str
    status_name: str
    status_color: str
    due_date: date | None
    assignee_name: str | None


class CalendarViewResponse(BaseModel):
    project_id: str
    month: int | None = None
    year: int | None = None
    events: list[CalendarTaskItem] = []


class GanttNodeResponse(BaseModel):
    id: str
    short_id: str
    title: str
    duration_days: int
    early_start: int
    early_finish: int
    late_start: int
    late_finish: int
    total_float: int
    is_critical: bool
    dependencies_out: list[str] = []


class GanttChartResponse(BaseModel):
    project_id: str
    project_duration_days: int
    critical_path: list[str] = []
    nodes: list[GanttNodeResponse] = []
