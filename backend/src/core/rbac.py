"""Role-Based Access Control (RBAC) and Security Dependencies."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.core.database import get_db_session
from src.core.exceptions import AuthenticationError, PermissionDeniedException
from src.core.security import decode_access_token
from src.models.auth import OrgRole, User

security = HTTPBearer(auto_error=False)

# Hierarchical weight of roles
ROLE_HIERARCHY: dict[OrgRole, int] = {
    OrgRole.ORG_OWNER: 100,
    OrgRole.ORG_ADMIN: 80,
    OrgRole.PROJECT_MANAGER: 60,
    OrgRole.MEMBER: 40,
    OrgRole.GUEST: 20,
}


@dataclass
class AuthContext:
    """Authenticated request context holding user identity, tenant org, and role."""

    user: User
    org_id: str | None = None
    role: OrgRole | None = None
    is_superadmin: bool = False

    def has_min_role(self, required_role: OrgRole) -> bool:
        """Check if user has at least the required role hierarchy level."""
        if self.is_superadmin or self.role == OrgRole.ORG_OWNER:
            return True
        if self.role is None:
            return False
        return ROLE_HIERARCHY.get(self.role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Extract and validate user from Bearer JWT access token."""
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
    """Resolve user and their specific organization role context from header or first membership."""
    if user.is_superadmin:
        return AuthContext(
            user=user,
            org_id=x_org_id or (user.memberships[0].org_id if user.memberships else None),
            role=OrgRole.ORG_OWNER,
            is_superadmin=True,
        )

    # Determine active organization
    active_org_id = x_org_id
    if not active_org_id and user.memberships:
        active_org_id = user.memberships[0].org_id

    # Lookup role in active organization
    user_role: OrgRole | None = None
    if active_org_id:
        for m in user.memberships:
            if m.org_id == active_org_id:
                user_role = m.role
                break

    return AuthContext(
        user=user,
        org_id=active_org_id,
        role=user_role,
        is_superadmin=user.is_superadmin,
    )


def role_rank(role: OrgRole | None) -> int:
    """Return the hierarchy weight of a role (0 when unset)."""
    return ROLE_HIERARCHY.get(role, 0) if role else 0


def resolve_org_role(user: User, org_id: str) -> OrgRole | None:
    """Resolve a user's role within a *specific* organization (by membership, not header)."""
    if user.is_superadmin:
        return OrgRole.ORG_OWNER
    for membership in user.memberships:
        if membership.org_id == org_id:
            return membership.role
    return None


def assert_org_role(user: User, org_id: str, min_role: OrgRole) -> OrgRole:
    """Authorize an action against the given organization, returning the caller's role.

    Unlike ``require_role`` (which trusts the X-Org-ID header), this verifies membership
    in the exact ``org_id`` being acted upon — the correct check for path-scoped mutations.
    """
    role = resolve_org_role(user, org_id)
    if role is None:
        raise PermissionDeniedException("You are not a member of this organization")
    if not user.is_superadmin and role_rank(role) < role_rank(min_role):
        raise PermissionDeniedException(
            f"Action requires at least '{min_role.value}' role in this organization"
        )
    return role


def require_role(min_role: OrgRole):
    """FastAPI Dependency factory enforcing minimum organization role level."""

    async def role_checker(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
        if not ctx.org_id:
            raise PermissionDeniedException("No organization context selected")
        if not ctx.has_min_role(min_role):
            raise PermissionDeniedException(
                f"Action requires at least '{min_role.value}' role in this organization"
            )
        return ctx

    return role_checker
