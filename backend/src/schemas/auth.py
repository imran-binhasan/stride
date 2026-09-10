"""Pydantic v2 schemas for Authentication, Organizations, Teams, and Invites."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.models.auth import MemberStatus, OrgRole, SubscriptionTier, TeamRole


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)
    organization_name: str | None = Field(default=None, min_length=2, max_length=255)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    avatar_url: str | None
    phone: str | None
    timezone: str
    locale: str
    is_active: bool
    is_superadmin: bool
    created_at: datetime


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = None
    timezone: str | None = None
    locale: str | None = None
    avatar_url: str | None = None


# ── Organization ──────────────────────────────────────────────────────────────

class OrgCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=100)


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    logo_url: str | None
    subscription_tier: SubscriptionTier
    trial_ends_at: datetime | None
    max_members: int
    max_projects: int
    created_at: datetime


class MyOrgResponse(BaseModel):
    """Org the current user belongs to, with their role."""

    id: str
    name: str
    slug: str
    subscription_tier: SubscriptionTier
    role: OrgRole
    created_at: datetime


# ── Members ───────────────────────────────────────────────────────────────────

class OrgMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    email: str
    role: OrgRole
    status: MemberStatus
    joined_at: datetime | None
    user: UserProfileResponse | None = None


class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: OrgRole = OrgRole.MEMBER


class AcceptInviteRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)


# ── Workspace ─────────────────────────────────────────────────────────────────

class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = None
    description: str | None = None


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    name: str
    slug: str
    description: str | None
    created_at: datetime


# ── Departments & Teams ───────────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    head_user_id: str | None = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    name: str
    description: str | None
    head_user_id: str | None
    created_at: datetime


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    identifier: str = Field(min_length=2, max_length=20)
    department_id: str | None = None
    color: str = "#6B7280"


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    department_id: str | None
    name: str
    identifier: str
    color: str
    created_at: datetime


class TeamMemberAddRequest(BaseModel):
    user_id: str
    role: TeamRole = TeamRole.MEMBER


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    user_id: str
    role: TeamRole
    user: UserProfileResponse | None = None
