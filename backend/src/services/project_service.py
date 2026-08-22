"""Project and Sprint business logic service."""

from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import ConflictException, EntityNotFoundException, ValidationException
from src.models.project import StatusCategory
from src.repositories.project_repo import ProjectRepository
from src.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    SprintCreate,
    SprintResponse,
    WorkflowStatusCreate,
    WorkflowStatusResponse,
)


class ProjectService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProjectRepository(db)

    async def create_project(self, org_id: str, payload: ProjectCreate) -> ProjectResponse:
        existing = await self.repo.get_by_key(payload.key, org_id=org_id)
        if existing:
            raise ConflictException(
                f"Project with key '{payload.key.upper()}' already exists in this organization"
            )

        project = await self.repo.create_project(
            org_id=org_id,
            workspace_id=payload.workspace_id,
            name=payload.name,
            key=payload.key,
            description=payload.description,
            default_view=payload.default_view,
        )

        default_statuses = [
            ("Backlog", StatusCategory.BACKLOG, "#9CA3AF", 0),
            ("To Do", StatusCategory.TODO, "#3B82F6", 1),
            ("In Progress", StatusCategory.IN_PROGRESS, "#F59E0B", 2),
            ("In Review", StatusCategory.IN_REVIEW, "#8B5CF6", 3),
            ("Done", StatusCategory.DONE, "#10B981", 4),
        ]
        for name, category, color, pos in default_statuses:
            await self.repo.add_workflow_status(
                project_id=project.id,
                name=name,
                category=category,
                color=color,
                position=pos,
            )

        fresh = await self.repo.get_by_id(project.id, org_id=org_id)
        return ProjectResponse.model_validate(fresh)

    async def get_project(self, project_id: str, org_id: str) -> ProjectResponse:
        project = await self.repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)
        return ProjectResponse.model_validate(project)

    async def list_workspace_projects(
        self, workspace_id: str, org_id: str, limit: int = 100, offset: int = 0
    ) -> list[ProjectResponse]:
        projects = await self.repo.list_by_workspace(
            workspace_id, org_id=org_id, limit=limit, offset=offset
        )
        return [ProjectResponse.model_validate(p) for p in projects]

    async def add_custom_status(
        self,
        project_id: str,
        org_id: str,
        payload: WorkflowStatusCreate,
    ) -> WorkflowStatusResponse:
        project = await self.repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)

        status = await self.repo.add_workflow_status(
            project_id=project.id,
            name=payload.name,
            category=payload.category,
            color=payload.color,
            position=payload.position,
        )
        return WorkflowStatusResponse.model_validate(status)

    async def delete_status(self, status_id: str, org_id: str) -> dict:
        status = await self.repo.get_status_by_id(status_id)
        if not status:
            raise EntityNotFoundException("WorkflowStatus", status_id)

        project = await self.repo.get_by_id(status.project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", status.project_id)

        if len(project.statuses) <= 1:
            raise ValidationException("A project must maintain at least one workflow status")

        deleted = await self.repo.delete_workflow_status(status_id)
        return {"success": deleted, "deleted_status_id": status_id}

    async def create_sprint(
        self, project_id: str, org_id: str, payload: SprintCreate
    ) -> SprintResponse:
        project = await self.repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)

        sprint = await self.repo.create_sprint(
            project_id=project.id,
            name=payload.name,
            goal=payload.goal,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        return SprintResponse.model_validate(sprint)
