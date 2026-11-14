"""Pydantic v2 schemas for Tasks, Comments, Attachments, and Dependencies."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from src.models.task import DependencyType, TaskPriority, TaskType
from src.schemas.auth import UserProfileResponse
from src.schemas.project import LabelResponse, WorkflowStatusResponse


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    author_id: str
    content: str
    is_internal: bool
    parent_comment_id: str | None
    author: UserProfileResponse | None = None
    created_at: datetime
    updated_at: datetime


class CommentCreate(BaseModel):
    content: str = Field(min_length=1)
    is_internal: bool = False
    parent_comment_id: str | None = None


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    comment_id: str | None
    uploaded_by_id: str
    file_name: str
    file_size: int
    mime_type: str
    storage_key: str
    created_at: datetime


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


class TaskAssigneeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    user: UserProfileResponse | None = None


class TaskChildResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    short_id: str
    title: str
    status_id: str
    parent_task_id: str | None
    position: int
    is_completed: bool = False


class TaskLabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    label_id: str
    label: LabelResponse


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    project_id: str
    sprint_id: str | None
    status_id: str
    parent_task_id: str | None
    short_id: str
    title: str
    description: str | None
    type: TaskType
    priority: TaskPriority
    story_points: float | None
    estimated_hours: float | None
    start_date: date | None
    due_date: date | None
    position: int
    custom_fields: dict[str, Any] = {}
    is_client_ticket: bool
    creator_id: str
    assignee_id: str | None
    created_at: datetime
    updated_at: datetime

    status: WorkflowStatusResponse | None = None
    assignee: UserProfileResponse | None = None
    assignees: list[TaskAssigneeResponse] = []
    labels: list[TaskLabelResponse] = []
    children: list[TaskChildResponse] = []
    dependencies_out: list[DependencyResponse] = []
    dependencies_in: list[DependencyResponse] = []
    comments: list[CommentResponse] = []
    attachments: list[AttachmentResponse] = []

    @computed_field
    @property
    def subtasks(self) -> list[TaskChildResponse]:
        return self.children


class SubtaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    position: int = Field(default=0, ge=0)


class TaskCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    type: TaskType = TaskType.TASK
    status_id: str | None = None
    sprint_id: str | None = None
    parent_task_id: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    story_points: float | None = Field(default=None, ge=0)
    estimated_hours: float | None = Field(default=None, ge=0)
    start_date: date | None = None
    due_date: date | None = None
    assignee_id: str | None = None
    is_client_ticket: bool = False
    custom_fields: dict[str, Any] = {}

    @field_validator("title")
    @classmethod
    def valid_title(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip() if value is not None else value


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    type: TaskType | None = None
    status_id: str | None = None
    sprint_id: str | None = None
    parent_task_id: str | None = None
    priority: TaskPriority | None = None
    story_points: float | None = Field(default=None, ge=0)
    estimated_hours: float | None = Field(default=None, ge=0)
    start_date: date | None = None
    due_date: date | None = None
    assignee_id: str | None = None
    is_client_ticket: bool | None = None
    custom_fields: dict[str, Any] | None = None

    @field_validator("title")
    @classmethod
    def valid_title(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip() if value is not None else value


class TaskMoveRequest(BaseModel):
    status_id: str
    new_position: int
