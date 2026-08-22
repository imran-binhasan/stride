"""Pydantic v2 schemas for Tasks, Subtasks, Dependencies, and Custom Fields."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from src.models.task import DependencyType, TaskPriority
from src.schemas.auth import UserProfileResponse
from src.schemas.project import WorkflowStatusResponse


class SubtaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    title: str
    is_completed: bool
    position: int
    created_at: datetime


class SubtaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    position: int = 0


class SubtaskUpdate(BaseModel):
    title: str | None = None
    is_completed: bool | None = None
    position: int | None = None


class DependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    predecessor_id: str
    successor_id: str
    dependency_type: DependencyType
    lag_days: int
    created_at: datetime


class DependencyCreate(BaseModel):
    successor_id: str
    dependency_type: DependencyType = DependencyType.BLOCKS
    lag_days: int = 0


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    project_id: str
    sprint_id: str | None
    status_id: str
    short_id: str
    title: str
    description: str | None
    priority: TaskPriority
    story_points: float | None
    estimated_hours: float | None
    due_date: date | None
    position: int
    custom_fields: dict[str, Any] = {}
    creator_id: str
    assignee_id: str | None
    created_at: datetime
    updated_at: datetime

    status: WorkflowStatusResponse | None = None
    assignee: UserProfileResponse | None = None
    subtasks: list[SubtaskResponse] = []
    dependencies_out: list[DependencyResponse] = []
    dependencies_in: list[DependencyResponse] = []


class TaskCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status_id: str | None = None
    sprint_id: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    story_points: float | None = None
    estimated_hours: float | None = None
    due_date: date | None = None
    assignee_id: str | None = None
    custom_fields: dict[str, Any] = {}


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status_id: str | None = None
    sprint_id: str | None = None
    priority: TaskPriority | None = None
    story_points: float | None = None
    estimated_hours: float | None = None
    due_date: date | None = None
    assignee_id: str | None = None
    custom_fields: dict[str, Any] | None = None


class TaskMoveRequest(BaseModel):
    status_id: str
    new_position: int
