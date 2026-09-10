"""Role-Based Access Control — permissions, role mappings, and FastAPI dependencies."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db_session
from src.core.exceptions import AuthenticationError, PermissionDeniedException
from src.core.security import decode_access_token
from src.models.auth import OrgMember, OrgRole, MemberStatus, User
from src.models.client import ClientContact, ClientProjectAccess

security = HTTPBearer(auto_error=False)


# ── Permissions ────────────────────────────────────────────────────────────────

class Permission(str, enum.Enum):
    # Organization
    ORG_READ           = "org:read"
    ORG_UPDATE         = "org:update"
    ORG_DELETE         = "org:delete"
    ORG_MANAGE_MEMBERS = "org:manage_members"
    ORG_BILLING        = "org:billing"

    # Project
    PROJECT_CREATE         = "project:create"
    PROJECT_READ           = "project:read"
    PROJECT_UPDATE         = "project:update"
    PROJECT_DELETE         = "project:delete"
    PROJECT_MANAGE         = "project:manage"
    PROJECT_MANAGE_MEMBERS = "project:manage_members"

    # Task
    TASK_CREATE = "task:create"
    TASK_READ   = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_ASSIGN = "task:assign"

    # Comments & Attachments
    COMMENT_CREATE     = "comment:create"
    COMMENT_READ       = "comment:read"
    COMMENT_DELETE_ANY = "comment:delete_any"

    # Sprint
    SPRINT_CREATE = "sprint:create"
    SPRINT_READ   = "sprint:read"
    SPRINT_UPDATE = "sprint:update"
    SPRINT_CLOSE  = "sprint:close"

    # Time tracking
    TIME_LOG      = "time:log"
    TIME_READ_OWN = "time:read_own"
    TIME_READ_ALL = "time:read_all"
    TIME_APPROVE  = "time:approve"

    # HR / Payroll
    HR_READ    = "hr:read"
    HR_MANAGE  = "hr:manage"
    PAYROLL_RUN = "payroll:run"

    # Integrations
    INTEGRATION_MANAGE = "integration:manage"

    # AI pipeline
    AI_USE           = "ai:use"
    AI_PIPELINE_FULL = "ai:pipeline_full"


# ── Role → permission mapping ──────────────────────────────────────────────────

_ALL = frozenset(Permission)

ROLE_PERMISSIONS: dict[OrgRole, frozenset[Permission]] = {
    OrgRole.ORG_OWNER: _ALL,

    OrgRole.ORG_ADMIN: _ALL - {Permission.ORG_DELETE},

    OrgRole.MANAGER: frozenset({
        Permission.ORG_READ,
        Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
        Permission.PROJECT_MANAGE, Permission.PROJECT_MANAGE_MEMBERS,
        Permission.TASK_CREATE, Permission.TASK_READ, Permission.TASK_UPDATE,
        Permission.TASK_DELETE, Permission.TASK_ASSIGN,
        Permission.COMMENT_CREATE, Permission.COMMENT_READ, Permission.COMMENT_DELETE_ANY,
        Permission.SPRINT_CREATE, Permission.SPRINT_READ, Permission.SPRINT_UPDATE, Permission.SPRINT_CLOSE,
        Permission.TIME_LOG, Permission.TIME_READ_OWN, Permission.TIME_READ_ALL, Permission.TIME_APPROVE,
        Permission.HR_READ,
        Permission.INTEGRATION_MANAGE,
        Permission.AI_USE, Permission.AI_PIPELINE_FULL,
    }),

    OrgRole.MEMBER: frozenset({
        Permission.ORG_READ,
        Permission.PROJECT_READ,
        Permission.TASK_CREATE, Permission.TASK_READ, Permission.TASK_UPDATE, Permission.TASK_ASSIGN,
        Permission.COMMENT_CREATE, Permission.COMMENT_READ,
        Permission.SPRINT_READ,
        Permission.TIME_LOG, Permission.TIME_READ_OWN,
        Permission.AI_USE,
    }),

    # External client — project-scoped; specific project permissions come from ClientProjectAccess
    OrgRole.CLIENT: frozenset({
        Permission.ORG_READ,
        Permission.PROJECT_READ,
        Permission.TASK_READ,
        Permission.COMMENT_READ,
        Permission.SPRINT_READ,
    }),
}

_FULL_PROJECT_ACCESS_ROLES = frozenset({
    OrgRole.ORG_OWNER,
    OrgRole.ORG_ADMIN,
    OrgRole.MANAGER,
    OrgRole.MEMBER,
})

_ROLE_WEIGHT: dict[OrgRole, int] = {
    OrgRole.ORG_OWNER: 100,
    OrgRole.ORG_ADMIN: 80,
    OrgRole.MANAGER:   60,
    OrgRole.MEMBER:    40,
    OrgRole.CLIENT:    20,
}


# ── Auth context ───────────────────────────────────────────────────────────────

@dataclass
class AuthContext:
    user         : User
    org_id       : str | None = None
    role         : OrgRole | None = None
    is_superadmin: bool = False
    # For CLIENT role — project IDs they may access + per-project access flags
    project_ids  : frozenset[str] = field(default_factory=frozenset)
    client_access: dict[str, ClientProjectAccess] = field(default_factory=dict)

    def has_permission(self, permission: Permission) -> bool:
        if self.is_superadmin:
            return True
        if self.role is None:
            return False
        return permission in ROLE_PERMISSIONS.get(self.role, frozenset())

    def can_access_project(self, project_id: str) -> bool:
        if self.is_superadmin or self.role in _FULL_PROJECT_ACCESS_ROLES:
            return True
        return project_id in self.project_ids

    def client_can(self, project_id: str, flag: str) -> bool:
        """Check a specific per-project client permission flag."""
        access = self.client_access.get(project_id)
        return bool(access) and getattr(access, flag, False)

    # Legacy helper used by time_tracking report endpoint
    def has_min_role(self, required_role: OrgRole) -> bool:
        if self.is_superadmin or self.role == OrgRole.ORG_OWNER:
            return True
        if self.role is None:
            return False
        return _ROLE_WEIGHT.get(self.role, 0) >= _ROLE_WEIGHT.get(required_role, 0)


# ── FastAPI dependencies ───────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Authorization header with Bearer token is required")

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token payload missing subject identifier")

    stmt = (
        select(User)
        .where(User.id == user_id, User.is_active.is_(True))
        .options(selectinload(User.memberships))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("User not found or account is deactivated")
    return user


async def get_auth_context(
    user: Annotated[User, Depends(get_current_user)],
    x_org_id: Annotated[str | None, Header(alias="X-Org-ID")] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> AuthContext:
    if user.is_superadmin:
        return AuthContext(
            user=user,
            org_id=x_org_id or (user.memberships[0].org_id if user.memberships else None),
            role=OrgRole.ORG_OWNER,
            is_superadmin=True,
        )

    active_org_id = x_org_id
    if not active_org_id and user.memberships:
        active_org_id = user.memberships[0].org_id

    user_role: OrgRole | None = None
    if active_org_id:
        for m in user.memberships:
            if m.org_id == active_org_id and m.status == MemberStatus.ACTIVE:
                user_role = m.role
                break

    # Load project-scoped access for CLIENT role
    project_ids: frozenset[str] = frozenset()
    client_access: dict[str, ClientProjectAccess] = {}

    if user_role == OrgRole.CLIENT:
        contact_stmt = (
            select(ClientContact)
            .where(ClientContact.user_id == user.id, ClientContact.org_id == active_org_id)
            .options(selectinload(ClientContact.project_access))
        )
        contact_result = await db.execute(contact_stmt)
        contact = contact_result.scalar_one_or_none()
        if contact:
            project_ids = frozenset(a.project_id for a in contact.project_access)
            client_access = {a.project_id: a for a in contact.project_access}

    return AuthContext(
        user=user,
        org_id=active_org_id,
        role=user_role,
        is_superadmin=False,
        project_ids=project_ids,
        client_access=client_access,
    )


def require_permission(permission: Permission):
    """Gate a route behind a specific permission."""

    async def checker(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
        if not ctx.org_id:
            raise PermissionDeniedException("No organization context — send X-Org-ID header")
        if not ctx.has_permission(permission):
            raise PermissionDeniedException(
                f"Your role '{ctx.role}' does not have permission: {permission.value}"
            )
        return ctx

    return checker


# ── Path-scoped org helpers ────────────────────────────────────────────────────

def resolve_org_role(user: User, org_id: str) -> OrgRole | None:
    if user.is_superadmin:
        return OrgRole.ORG_OWNER
    for m in user.memberships:
        if m.org_id == org_id and m.status == MemberStatus.ACTIVE:
            return m.role
    return None


def role_rank(role: OrgRole | None) -> int:
    return _ROLE_WEIGHT.get(role, 0) if role else 0


def assert_org_permission(user: User, org_id: str, permission: Permission) -> OrgRole:
    role = resolve_org_role(user, org_id)
    if role is None:
        raise PermissionDeniedException("You are not a member of this organization")
    if not user.is_superadmin and permission not in ROLE_PERMISSIONS.get(role, frozenset()):
        raise PermissionDeniedException(
            f"Your role '{role}' does not have permission: {permission.value}"
        )
    return role


def assert_org_role(user: User, org_id: str, min_role: OrgRole) -> OrgRole:
    """Legacy path-scoped role check — prefer assert_org_permission for new code."""
    role = resolve_org_role(user, org_id)
    if role is None:
        raise PermissionDeniedException("You are not a member of this organization")
    if not user.is_superadmin and role_rank(role) < role_rank(min_role):
        raise PermissionDeniedException(
            f"Action requires at least '{min_role.value}' role"
        )
    return role
