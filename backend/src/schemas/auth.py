"""Pydantic v2 validation schemas for Authentication and Organizations."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from src.models.auth import OrgRole


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Password with minimum 8 characters")
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
    is_active: bool
    is_superadmin: bool
    created_at: datetime


class OrgCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=100)


class OrgMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    role: OrgRole
    joined_at: datetime
    user: UserProfileResponse | None = None


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    subscription_tier: str
    created_at: datetime


class MyOrgResponse(BaseModel):
    """An organization the current user belongs to, with their role in it."""

    id: str
    name: str
    slug: str
    subscription_tier: str
    role: OrgRole
    created_at: datetime


class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: OrgRole = OrgRole.MEMBER


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
