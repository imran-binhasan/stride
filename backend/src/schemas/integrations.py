"""Pydantic v2 schemas for GitHub and Figma integrations."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GitHubIntegrationCreate(BaseModel):
    repo_owner: str = Field(min_length=1, max_length=100)
    repo_name: str = Field(min_length=1, max_length=100)
    auto_transition_pr_open: bool = True
    auto_transition_pr_merge: bool = True


class GitHubIntegrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    project_id: str
    repo_owner: str
    repo_name: str
    auto_transition_pr_open: bool
    auto_transition_pr_merge: bool
    created_at: datetime


class FigmaLinkCreate(BaseModel):
    figma_url: str = Field(description="Full Figma file or frame URL")
    file_name: str | None = None


class FigmaLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    figma_url: str
    file_key: str
    node_id: str | None
    file_name: str | None
    thumbnail_url: str | None
    created_at: datetime
