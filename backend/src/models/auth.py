"""Authentication, Organization, Teams, and License database models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampedModel, generate_uuid, utc_now

if TYPE_CHECKING:
    from src.models.client import ClientContact
    from src.models.hr import EmployeeProfile


class OrgRole(enum.StrEnum):
    ORG_OWNER = "ORG_OWNER"
    ORG_ADMIN = "ORG_ADMIN"
    MANAGER   = "MANAGER"
    MEMBER    = "MEMBER"
    CLIENT    = "CLIENT"   # external client — project-scoped via client_contacts


class MemberStatus(enum.StrEnum):
    PENDING   = "PENDING"    # invited, not yet accepted
    ACTIVE    = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REMOVED   = "REMOVED"


class DeploymentType(enum.StrEnum):
    SAAS        = "SAAS"
    SELF_HOSTED = "SELF_HOSTED"


class SubscriptionTier(enum.StrEnum):
    FREE       = "FREE"
    STARTER    = "STARTER"
    PRO        = "PRO"
    ENTERPRISE = "ENTERPRISE"


class TeamRole(enum.StrEnum):
    LEAD   = "LEAD"
    MEMBER = "MEMBER"


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base, TimestampedModel):
    __tablename__ = "users"

    id             : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email          : Mapped[str]      = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str]      = mapped_column(String(255), nullable=False)
    full_name      : Mapped[str]      = mapped_column(String(255), nullable=False)
    avatar_url     : Mapped[str|None] = mapped_column(String(512), nullable=True)
    phone          : Mapped[str|None] = mapped_column(String(50),  nullable=True)
    timezone       : Mapped[str]      = mapped_column(String(60),  default="UTC", nullable=False)
    locale         : Mapped[str]      = mapped_column(String(10),  default="en", nullable=False)
    is_active      : Mapped[bool]     = mapped_column(Boolean, default=True,  nullable=False)
    is_superadmin  : Mapped[bool]     = mapped_column(Boolean, default=False, nullable=False)

    memberships    : Mapped[list[OrgMember]]    = relationship("OrgMember", back_populates="user", cascade="all, delete-orphan", foreign_keys="OrgMember.user_id")
    refresh_tokens : Mapped[list[RefreshToken]] = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    employee_profile: Mapped[EmployeeProfile|None] = relationship("EmployeeProfile", back_populates="user", uselist=False)


# ── Organization ───────────────────────────────────────────────────────────────

class Organization(Base, TimestampedModel):
    __tablename__ = "organizations"

    id               : Mapped[str]       = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name             : Mapped[str]       = mapped_column(String(255), nullable=False)
    slug             : Mapped[str]       = mapped_column(String(100), unique=True, index=True, nullable=False)
    logo_url         : Mapped[str|None]  = mapped_column(String(512), nullable=True)
    deployment_type  : Mapped[DeploymentType] = mapped_column(Enum(DeploymentType, native_enum=False, length=20), default=DeploymentType.SAAS, nullable=False)
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier, native_enum=False, length=20), default=SubscriptionTier.FREE, nullable=False)
    trial_ends_at    : Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_trial_used    : Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    max_members      : Mapped[int]       = mapped_column(default=5,   nullable=False)
    max_projects     : Mapped[int]       = mapped_column(default=3,   nullable=False)
    max_storage_gb   : Mapped[int]       = mapped_column(default=5,   nullable=False)

    members          : Mapped[list[OrgMember]]  = relationship("OrgMember", back_populates="organization", cascade="all, delete-orphan")
    workspaces       : Mapped[list[Workspace]]  = relationship("Workspace",  back_populates="organization", cascade="all, delete-orphan")
    departments      : Mapped[list[Department]] = relationship("Department", back_populates="organization", cascade="all, delete-orphan")
    teams            : Mapped[list[Team]]       = relationship("Team", back_populates="organization", cascade="all, delete-orphan")
    license          : Mapped[License|None]     = relationship("License", back_populates="organization", uselist=False)


# ── Self-hosted license ────────────────────────────────────────────────────────

class License(Base, TimestampedModel):
    __tablename__ = "licenses"

    id             : Mapped[str]           = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id         : Mapped[str]           = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    license_key    : Mapped[str]           = mapped_column(String(255), unique=True, nullable=False)
    licensed_email : Mapped[str]           = mapped_column(String(255), nullable=False)
    max_seats      : Mapped[int]           = mapped_column(default=10, nullable=False)
    tier           : Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier, native_enum=False, length=20), default=SubscriptionTier.STARTER, nullable=False)
    purchased_at   : Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at     : Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship("Organization", back_populates="license")


# ── Membership ─────────────────────────────────────────────────────────────────

class OrgMember(Base, TimestampedModel):
    """Tracks the full invite → active → suspended lifecycle in one record."""

    __tablename__ = "org_members"

    id                : Mapped[str]           = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id            : Mapped[str]           = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id           : Mapped[str|None]      = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    email             : Mapped[str]           = mapped_column(String(255), nullable=False)
    role              : Mapped[OrgRole]       = mapped_column(Enum(OrgRole, native_enum=False, length=20), default=OrgRole.MEMBER, nullable=False)
    status            : Mapped[MemberStatus]  = mapped_column(Enum(MemberStatus, native_enum=False, length=20), default=MemberStatus.PENDING, nullable=False)
    invite_token      : Mapped[str|None]      = mapped_column(String(255), nullable=True)
    invite_expires_at : Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_by_id     : Mapped[str|None]      = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    joined_at         : Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_org_member_email"),)

    organization: Mapped[Organization] = relationship("Organization", back_populates="members")
    user        : Mapped[User|None]    = relationship("User", back_populates="memberships", foreign_keys=[user_id])
    invited_by  : Mapped[User|None]    = relationship("User", foreign_keys=[invited_by_id])


# ── Workspace ──────────────────────────────────────────────────────────────────

class Workspace(Base, TimestampedModel):
    __tablename__ = "workspaces"

    id         : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id     : Mapped[str]      = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    name       : Mapped[str]      = mapped_column(String(255), nullable=False)
    slug       : Mapped[str]      = mapped_column(String(100), nullable=False)
    description: Mapped[str|None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_workspace_org_slug"),)

    organization: Mapped[Organization] = relationship("Organization", back_populates="workspaces")


# ── Departments & Teams ────────────────────────────────────────────────────────

class Department(Base, TimestampedModel):
    __tablename__ = "departments"

    id          : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id      : Mapped[str]      = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    name        : Mapped[str]      = mapped_column(String(255), nullable=False)
    description : Mapped[str|None] = mapped_column(Text, nullable=True)
    head_user_id: Mapped[str|None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    organization: Mapped[Organization] = relationship("Organization", back_populates="departments")
    head        : Mapped[User|None]    = relationship("User", foreign_keys=[head_user_id])
    teams       : Mapped[list[Team]]   = relationship("Team", back_populates="department")


class Team(Base, TimestampedModel):
    __tablename__ = "teams"

    id            : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id        : Mapped[str]      = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    department_id : Mapped[str|None] = mapped_column(String(36), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    name          : Mapped[str]      = mapped_column(String(255), nullable=False)
    identifier    : Mapped[str]      = mapped_column(String(20), nullable=False)
    color         : Mapped[str]      = mapped_column(String(20), default="#6B7280", nullable=False)

    organization: Mapped[Organization]    = relationship("Organization", back_populates="teams")
    department  : Mapped[Department|None] = relationship("Department", back_populates="teams")
    members     : Mapped[list[TeamMember]] = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base, TimestampedModel):
    __tablename__ = "team_members"

    id      : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    team_id : Mapped[str]      = mapped_column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id : Mapped[str]      = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role    : Mapped[TeamRole] = mapped_column(Enum(TeamRole, native_enum=False, length=10), default=TeamRole.MEMBER, nullable=False)

    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member"),)

    team: Mapped[Team] = relationship("Team", back_populates="members")
    user: Mapped[User] = relationship("User")


# ── Refresh Tokens ─────────────────────────────────────────────────────────────

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         : Mapped[str]      = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id    : Mapped[str]      = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token      : Mapped[str]      = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked    : Mapped[bool]     = mapped_column(Boolean, default=False, nullable=False)
    created_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")
