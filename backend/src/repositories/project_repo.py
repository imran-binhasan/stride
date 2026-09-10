"""Database repository for Projects, Sprints, Labels, and Project Access Grants."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.project import (
    GranteeType,
    Label,
    Project,
    ProjectAccessGrant,
    ProjectStatus,
    Sprint,
    SprintStatus,
    StatusCategory,
    WorkflowStatus,
)


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

    async def get_by_key(self, key: str, org_id: str) -> Project | None:
        stmt = select(Project).where(Project.key == key.upper(), Project.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_workspace(
        self, workspace_id: str, org_id: str, limit: int = 100, offset: int = 0
    ) -> list[Project]:
        stmt = (
            select(Project)
            .where(
                Project.workspace_id == workspace_id,
                Project.org_id == org_id,
                Project.status != ProjectStatus.ARCHIVED,
            )
            .options(selectinload(Project.statuses), selectinload(Project.sprints))
            .order_by(Project.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def increment_task_counter(self, project_id: str) -> int:
        stmt = (
            update(Project)
            .where(Project.id == project_id)
            .values(task_counter=Project.task_counter + 1)
            .returning(Project.task_counter)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def create_project(
        self,
        org_id: str,
        workspace_id: str,
        name: str,
        key: str,
        created_by_id: str | None = None,
        description: str | None = None,
        default_view: str = "kanban",
        color: str = "#6B7280",
        icon: str | None = None,
        start_date=None,
        target_date=None,
        client_contact_id: str | None = None,
    ) -> Project:
        project = Project(
            org_id=org_id,
            workspace_id=workspace_id,
            name=name.strip(),
            key=key.upper().strip(),
            created_by_id=created_by_id,
            description=description,
            default_view=default_view,
            color=color,
            icon=icon,
            start_date=start_date,
            target_date=target_date,
            client_contact_id=client_contact_id,
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
            project_id=project_id, name=name, category=category, color=color, position=position
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

    # ── Sprints ───────────────────────────────────────────────────────────────

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
            status=SprintStatus.PLANNED,
        )
        self.db.add(sprint)
        await self.db.flush()
        await self.db.refresh(sprint)
        return sprint

    async def get_sprint_by_id(self, sprint_id: str) -> Sprint | None:
        stmt = select(Sprint).where(Sprint.id == sprint_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ── Labels ────────────────────────────────────────────────────────────────

    async def create_label(self, org_id: str, name: str, color: str = "#6B7280") -> Label:
        label = Label(org_id=org_id, name=name.strip(), color=color)
        self.db.add(label)
        await self.db.flush()
        await self.db.refresh(label)
        return label

    async def list_labels(self, org_id: str) -> list[Label]:
        stmt = select(Label).where(Label.org_id == org_id).order_by(Label.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_label_by_id(self, label_id: str, org_id: str) -> Label | None:
        stmt = select(Label).where(Label.id == label_id, Label.org_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ── Project Access Grants ─────────────────────────────────────────────────

    async def add_access_grant(
        self,
        project_id: str,
        grantee_type: GranteeType,
        grantee_id: str,
        granted_by_id: str | None = None,
    ) -> ProjectAccessGrant:
        grant = ProjectAccessGrant(
            project_id=project_id,
            grantee_type=grantee_type,
            grantee_id=grantee_id,
            granted_by_id=granted_by_id,
        )
        self.db.add(grant)
        await self.db.flush()
        await self.db.refresh(grant)
        return grant

    async def list_access_grants(self, project_id: str) -> list[ProjectAccessGrant]:
        stmt = select(ProjectAccessGrant).where(ProjectAccessGrant.project_id == project_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
