"""Database repository for Tasks, Subtasks, and Dependencies."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.models.task import DependencyType, Subtask, Task, TaskDependency, TaskPriority


class TaskRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, task_id: str, org_id: str | None = None) -> Task | None:
        stmt = (
            select(Task)
            .where(Task.id == task_id)
            .options(
                selectinload(Task.status),
                selectinload(Task.assignee),
                selectinload(Task.subtasks),
                selectinload(Task.dependencies_out),
                selectinload(Task.dependencies_in),
            )
        )
        if org_id:
            stmt = stmt.where(Task.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_short_id(self, project_id: str, short_id: str) -> Task | None:
        stmt = (
            select(Task)
            .where(Task.project_id == project_id, Task.short_id == short_id)
            .options(
                selectinload(Task.status),
                selectinload(Task.assignee),
                selectinload(Task.subtasks),
                selectinload(Task.dependencies_out),
                selectinload(Task.dependencies_in),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many_by_short_ids(self, project_id: str, short_ids: list[str]) -> list[Task]:
        """Batch-fetch tasks by short id within a project (single IN query, no N+1)."""
        if not short_ids:
            return []
        stmt = (
            select(Task)
            .where(Task.project_id == project_id, Task.short_id.in_(short_ids))
            .options(selectinload(Task.status))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_project(
        self,
        project_id: str,
        org_id: str,
        sprint_id: str | None = None,
        status_id: str | None = None,
        assignee_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Task]:
        stmt = (
            select(Task)
            .where(Task.project_id == project_id, Task.org_id == org_id)
            .options(
                selectinload(Task.status),
                selectinload(Task.assignee),
                selectinload(Task.subtasks),
                selectinload(Task.dependencies_out),
                selectinload(Task.dependencies_in),
            )
            .order_by(Task.position.asc())
        )
        if sprint_id:
            stmt = stmt.where(Task.sprint_id == sprint_id)
        if status_id:
            stmt = stmt.where(Task.status_id == status_id)
        if assignee_id:
            stmt = stmt.where(Task.assignee_id == assignee_id)
        # Pagination is opt-in: view aggregations (Kanban/Gantt) pass no limit and load the
        # full project; the paginated list endpoint supplies limit/offset.
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_task(
        self,
        org_id: str,
        project_id: str,
        short_id: str,
        title: str,
        status_id: str,
        creator_id: str,
        description: str | None = None,
        sprint_id: str | None = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        story_points: float | None = None,
        estimated_hours: float | None = None,
        due_date: date | None = None,
        assignee_id: str | None = None,
        position: int = 1000,
        custom_fields: dict[str, Any] | None = None,
    ) -> Task:
        task = Task(
            org_id=org_id,
            project_id=project_id,
            short_id=short_id,
            title=title.strip(),
            status_id=status_id,
            creator_id=creator_id,
            description=description,
            sprint_id=sprint_id,
            priority=priority,
            story_points=story_points,
            estimated_hours=estimated_hours,
            due_date=due_date,
            assignee_id=assignee_id,
            position=position,
            custom_fields=custom_fields or {},
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def add_subtask(self, task_id: str, title: str, position: int = 0) -> Subtask:
        subtask = Subtask(task_id=task_id, title=title.strip(), position=position)
        self.db.add(subtask)
        await self.db.flush()
        return subtask

    async def add_dependency(
        self,
        predecessor_id: str,
        successor_id: str,
        dependency_type: DependencyType = DependencyType.BLOCKS,
        lag_days: int = 0,
    ) -> TaskDependency:
        dep = TaskDependency(
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            dependency_type=dependency_type,
            lag_days=lag_days,
        )
        self.db.add(dep)
        await self.db.flush()
        return dep

    async def get_dependency_graph(self, project_id: str) -> list[TaskDependency]:
        stmt = (
            select(TaskDependency)
            .join(Task, Task.id == TaskDependency.predecessor_id)
            .where(Task.project_id == project_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
