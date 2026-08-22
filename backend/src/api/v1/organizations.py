"""Organization and Workspace management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.exceptions import PermissionDeniedException
from src.core.rbac import assert_org_role, get_current_user, role_rank
from src.models.auth import OrgRole, User
from src.schemas.auth import (
    MemberInviteRequest,
    MyOrgResponse,
    OrgCreateRequest,
    OrgMemberResponse,
    OrgResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from src.services.auth_service import AuthService

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=list[MyOrgResponse])
async def list_my_organizations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[MyOrgResponse]:
    """List the organizations the current user belongs to, with their role in each."""
    service = AuthService(db)
    return await service.list_user_organizations(user.id)


@router.get("/{org_id}/workspaces", response_model=list[WorkspaceResponse])
async def list_org_workspaces(
    org_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[WorkspaceResponse]:
    """List workspaces in an organization the user is a member of."""
    assert_org_role(user, org_id, OrgRole.GUEST)
    service = AuthService(db)
    return await service.list_org_workspaces(org_id)


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrgCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrgResponse:
    """Create a new tenant organization and grant creator ORG_OWNER role."""
    service = AuthService(db)
    return await service.create_organization(user_id=user.id, payload=payload)


@router.post(
    "/{org_id}/members", response_model=OrgMemberResponse, status_code=status.HTTP_201_CREATED
)
async def invite_organization_member(
    org_id: str,
    payload: MemberInviteRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrgMemberResponse:
    """Invite an existing user into the organization with specified role."""
    # Authorize against the target org (path), not the X-Org-ID header.
    inviter_role = assert_org_role(user, org_id, OrgRole.ORG_ADMIN)
    # A member cannot be granted a role higher than the inviter's own.
    if role_rank(payload.role) > role_rank(inviter_role):
        raise PermissionDeniedException("Cannot grant a role higher than your own")
    service = AuthService(db)
    return await service.invite_member(org_id=org_id, payload=payload)


@router.post(
    "/{org_id}/workspaces", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED
)
async def create_workspace(
    org_id: str,
    payload: WorkspaceCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceResponse:
    """Create a new departmental workspace inside an organization."""
    assert_org_role(user, org_id, OrgRole.ORG_ADMIN)
    service = AuthService(db)
    return await service.create_workspace(org_id=org_id, payload=payload)
