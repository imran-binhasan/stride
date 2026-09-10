"""Database repository for Tasks, Comments, Attachments, and Dependencies."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.task import (
    Attachment,
    Comment,
    DependencyType,
    Task,
    TaskAssignee,
    TaskDependency,
    TaskPriority,
    TaskType,
)


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
                selectinload(Task.assignees),
                selectinload(Task.children),
                selectinload(Task.comments).selectinload(Comment.author),
                selectinload(Task.attachments),
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
            .options(selectinload(Task.status), selectinload(Task.assignee))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many_by_short_ids(self, project_id: str, short_ids: list[str]) -> list[Task]:
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
        task_type: TaskType | None = None,
        parent_task_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Task]:
        stmt = (
            select(Task)
            .where(Task.project_id == project_id, Task.org_id == org_id)
            .options(
                selectinload(Task.status),
                selectinload(Task.assignee),
                selectinload(Task.assignees),
                selectinload(Task.children),
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
        if task_type:
            stmt = stmt.where(Task.type == task_type)
        if parent_task_id is not None:
            stmt = stmt.where(Task.parent_task_id == parent_task_id)
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
        task_type: TaskType = TaskType.TASK,
        description: str | None = None,
        sprint_id: str | None = None,
        parent_task_id: str | None = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        story_points: float | None = None,
        estimated_hours: float | None = None,
        start_date: date | None = None,
        due_date: date | None = None,
        assignee_id: str | None = None,
        is_client_ticket: bool = False,
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
            type=task_type,
            description=description,
            sprint_id=sprint_id,
            parent_task_id=parent_task_id,
            priority=priority,
            story_points=story_points,
            estimated_hours=estimated_hours,
            start_date=start_date,
            due_date=due_date,
            assignee_id=assignee_id,
            is_client_ticket=is_client_ticket,
            position=position,
            custom_fields=custom_fields or {},
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def add_assignee(self, task_id: str, user_id: str) -> TaskAssignee:
        ta = TaskAssignee(task_id=task_id, user_id=user_id)
        self.db.add(ta)
        await self.db.flush()
        return ta

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

    # ── Comments ──────────────────────────────────────────────────────────────

    async def add_comment(
        self,
        task_id: str,
        author_id: str,
        content: str,
        is_internal: bool = False,
        parent_comment_id: str | None = None,
    ) -> Comment:
        comment = Comment(
            task_id=task_id,
            author_id=author_id,
            content=content,
            is_internal=is_internal,
            parent_comment_id=parent_comment_id,
        )
        self.db.add(comment)
        await self.db.flush()
        await self.db.refresh(comment)
        return comment

    async def get_comment_by_id(self, comment_id: str) -> Comment | None:
        stmt = select(Comment).where(Comment.id == comment_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_comment(self, comment_id: str) -> bool:
        comment = await self.get_comment_by_id(comment_id)
        if comment:
            await self.db.delete(comment)
            await self.db.flush()
            return True
        return False

    # ── Attachments ───────────────────────────────────────────────────────────

    async def add_attachment(
        self,
        task_id: str,
        uploaded_by_id: str,
        file_name: str,
        file_size: int,
        mime_type: str,
        storage_key: str,
        comment_id: str | None = None,
    ) -> Attachment:
        att = Attachment(
            task_id=task_id,
            uploaded_by_id=uploaded_by_id,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            storage_key=storage_key,
            comment_id=comment_id,
        )
        self.db.add(att)
        await self.db.flush()
        await self.db.refresh(att)
        return att
