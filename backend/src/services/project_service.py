"""Project, Sprint, Label, and Project Access business logic."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ConflictException, EntityNotFoundException, ValidationException
from src.models.project import GranteeType, SprintStatus, StatusCategory
from src.repositories.project_repo import ProjectRepository
from src.schemas.project import (
    LabelCreate,
    LabelResponse,
    ProjectAccessGrantCreate,
    ProjectAccessGrantResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    SprintCreate,
    SprintResponse,
    SprintUpdate,
    WorkflowStatusCreate,
    WorkflowStatusResponse,
)


class ProjectService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProjectRepository(db)

    async def create_project(
        self, org_id: str, creator_id: str, payload: ProjectCreate
    ) -> ProjectResponse:
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
            created_by_id=creator_id,
            description=payload.description,
            default_view=payload.default_view,
            color=payload.color,
            icon=payload.icon,
            start_date=payload.start_date,
            target_date=payload.target_date,
            client_contact_id=payload.client_contact_id,
        )

        for name, category, color, pos in [
            ("Backlog",     StatusCategory.BACKLOG,      "#9CA3AF", 0),
            ("To Do",       StatusCategory.TODO,         "#3B82F6", 1),
            ("In Progress", StatusCategory.IN_PROGRESS,  "#F59E0B", 2),
            ("In Review",   StatusCategory.IN_REVIEW,    "#8B5CF6", 3),
            ("Done",        StatusCategory.DONE,         "#10B981", 4),
        ]:
            await self.repo.add_workflow_status(project_id=project.id, name=name, category=category, color=color, position=pos)

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
        projects = await self.repo.list_by_workspace(workspace_id, org_id=org_id, limit=limit, offset=offset)
        return [ProjectResponse.model_validate(p) for p in projects]

    async def update_project(
        self, project_id: str, org_id: str, payload: ProjectUpdate
    ) -> ProjectResponse:
        project = await self.repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(project, field, value)
        await self.db.flush()
        fresh = await self.repo.get_by_id(project_id, org_id=org_id)
        return ProjectResponse.model_validate(fresh)

    async def add_custom_status(
        self, project_id: str, org_id: str, payload: WorkflowStatusCreate
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

    # ── Sprints ───────────────────────────────────────────────────────────────

    async def create_sprint(self, project_id: str, org_id: str, payload: SprintCreate) -> SprintResponse:
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

    async def update_sprint(
        self, sprint_id: str, org_id: str, payload: SprintUpdate
    ) -> SprintResponse:
        sprint = await self.repo.get_sprint_by_id(sprint_id)
        if not sprint:
            raise EntityNotFoundException("Sprint", sprint_id)
        project = await self.repo.get_by_id(sprint.project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", sprint.project_id)

        if payload.status == SprintStatus.ACTIVE:
            # Only one active sprint per project
            for s in project.sprints:
                if s.id != sprint_id and s.status == SprintStatus.ACTIVE:
                    raise ConflictException("Another sprint is already active in this project")

        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(sprint, field, value)
        await self.db.flush()
        return SprintResponse.model_validate(sprint)

    # ── Labels ────────────────────────────────────────────────────────────────

    async def create_label(self, org_id: str, payload: LabelCreate) -> LabelResponse:
        label = await self.repo.create_label(org_id=org_id, name=payload.name, color=payload.color)
        return LabelResponse.model_validate(label)

    async def list_labels(self, org_id: str) -> list[LabelResponse]:
        labels = await self.repo.list_labels(org_id)
        return [LabelResponse.model_validate(l) for l in labels]

    # ── Project Access Grants ─────────────────────────────────────────────────

    async def add_access_grant(
        self, project_id: str, org_id: str, granted_by_id: str, payload: ProjectAccessGrantCreate
    ) -> ProjectAccessGrantResponse:
        project = await self.repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)
        grant = await self.repo.add_access_grant(
            project_id=project_id,
            grantee_type=payload.grantee_type,
            grantee_id=payload.grantee_id,
            granted_by_id=granted_by_id,
        )
        return ProjectAccessGrantResponse.model_validate(grant)

    async def list_access_grants(self, project_id: str, org_id: str) -> list[ProjectAccessGrantResponse]:
        project = await self.repo.get_by_id(project_id, org_id=org_id)
        if not project:
            raise EntityNotFoundException("Project", project_id)
        grants = await self.repo.list_access_grants(project_id)
        return [ProjectAccessGrantResponse.model_validate(g) for g in grants]
