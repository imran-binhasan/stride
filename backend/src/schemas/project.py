"""Pydantic v2 schemas for Projects, Workflow Statuses, and Sprints."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from src.models.project import StatusCategory


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
    is_active: bool
    is_closed: bool
    created_at: datetime


class SprintCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ProjectCreate(BaseModel):
    workspace_id: str
    name: str = Field(min_length=2, max_length=255)
    key: str = Field(
        min_length=2, max_length=10, description="Short identifier key e.g. A3Z or ENG"
    )
    description: str | None = None
    default_view: str = "kanban"


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    default_view: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    workspace_id: str
    key: str
    name: str
    description: str | None
    default_view: str
    task_counter: int
    created_at: datetime
    statuses: list[WorkflowStatusResponse] = []
