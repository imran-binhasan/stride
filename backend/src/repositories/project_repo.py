"""Database repository for Projects, Workflow Statuses, and Sprints."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.models.project import Project, Sprint, StatusCategory, WorkflowStatus


class ProjectRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, project_id: str, org_id: str | None = None) -> Project | None:
        stmt = (
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.statuses),
                selectinload(Project.sprints),
            )
        )
        if org_id:
            stmt = stmt.where(Project.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_task_counter(self, project_id: str) -> int:
        """Atomically bump and return a project's task counter (avoids read-modify-write races)."""
        stmt = (
            update(Project)
            .where(Project.id == project_id)
            .values(task_counter=Project.task_counter + 1)
            .returning(Project.task_counter)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_by_key(self, key: str, org_id: str) -> Project | None:
        stmt = select(Project).where(Project.key == key.upper(), Project.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_workspace(
        self, workspace_id: str, org_id: str, limit: int = 100, offset: int = 0
    ) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.workspace_id == workspace_id, Project.org_id == org_id)
            .options(selectinload(Project.statuses))
            .order_by(Project.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_project(
        self,
        org_id: str,
        workspace_id: str,
        name: str,
        key: str,
        description: str | None = None,
        default_view: str = "kanban",
    ) -> Project:
        project = Project(
            org_id=org_id,
            workspace_id=workspace_id,
            name=name.strip(),
            key=key.upper().strip(),
            description=description,
            default_view=default_view,
            task_counter=0,
        )
        self.db.add(project)
        await self.db.flush()
        return project

    async def add_workflow_status(
        self,
        project_id: str,
        name: str,
        category: StatusCategory,
        color: str = "#6B7280",
        position: int = 0,
    ) -> WorkflowStatus:
        status = WorkflowStatus(
            project_id=project_id,
            name=name,
            category=category,
            color=color,
            position=position,
        )
        self.db.add(status)
        await self.db.flush()
        return status

    async def get_status_by_id(self, status_id: str) -> WorkflowStatus | None:
        stmt = select(WorkflowStatus).where(WorkflowStatus.id == status_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_workflow_status(self, status_id: str) -> bool:
        status = await self.get_status_by_id(status_id)
        if status:
            await self.db.delete(status)
            await self.db.flush()
            return True
        return False

    async def create_sprint(
        self,
        project_id: str,
        name: str,
        goal: str | None = None,
        start_date=None,
        end_date=None,
    ) -> Sprint:
        sprint = Sprint(
            project_id=project_id,
            name=name,
            goal=goal,
            start_date=start_date,
            end_date=end_date,
        )
        self.db.add(sprint)
        await self.db.flush()
        await self.db.refresh(sprint)
        return sprint

    async def get_sprint_by_id(self, sprint_id: str) -> Sprint | None:
        stmt = select(Sprint).where(Sprint.id == sprint_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
