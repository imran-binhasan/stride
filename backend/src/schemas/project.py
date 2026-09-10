"""Pydantic v2 schemas for Projects, Sprints, Labels, and Project Access."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.project import GranteeType, ProjectStatus, SprintStatus, StatusCategory


class WorkflowStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: StatusCategory
    color: str
    position: int


class WorkflowStatusCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: StatusCategory = StatusCategory.TODO
    color: str = "#6B7280"
    position: int = 0


class SprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    goal: str | None
    start_date: date | None
    end_date: date | None
    status: SprintStatus
    created_at: datetime


class SprintCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class SprintUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: SprintStatus | None = None


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = "#6B7280"


class LabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    name: str
    color: str


class ProjectAccessGrantCreate(BaseModel):
    grantee_type: GranteeType
    grantee_id: str


class ProjectAccessGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    grantee_type: GranteeType
    grantee_id: str
    granted_by_id: str | None
    created_at: datetime


class ProjectCreate(BaseModel):
    workspace_id: str
    name: str = Field(min_length=2, max_length=255)
    key: str = Field(min_length=2, max_length=10, description="Short identifier e.g. ENG")
    description: str | None = None
    default_view: str = "kanban"
    color: str = "#6B7280"
    icon: str | None = None
    start_date: date | None = None
    target_date: date | None = None
    client_contact_id: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    default_view: str | None = None
    status: ProjectStatus | None = None
    color: str | None = None
    icon: str | None = None
    start_date: date | None = None
    target_date: date | None = None
    client_contact_id: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    workspace_id: str
    key: str
    name: str
    description: str | None
    status: ProjectStatus
    default_view: str
    color: str
    icon: str | None
    task_counter: int
    start_date: date | None
    target_date: date | None
    client_contact_id: str | None
    created_by_id: str | None
    created_at: datetime
    statuses: list[WorkflowStatusResponse] = []
    sprints: list[SprintResponse] = []
