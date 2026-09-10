"""Organization, Workspace, Department, Team, and Invite API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.exceptions import PermissionDeniedException
from src.core.rbac import (
    AuthContext,
    Permission,
    assert_org_permission,
    get_auth_context,
    get_current_user,
    require_permission,
    role_rank,
)
from src.models.auth import OrgRole, User
from src.schemas.auth import (
    AcceptInviteRequest,
    DepartmentCreate,
    DepartmentResponse,
    MemberInviteRequest,
    MyOrgResponse,
    OrgCreateRequest,
    OrgMemberResponse,
    OrgResponse,
    TeamCreate,
    TeamMemberAddRequest,
    TeamMemberResponse,
    TeamResponse,
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
    return await AuthService(db).list_user_organizations(user.id)


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrgCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrgResponse:
    return await AuthService(db).create_organization(
        user_id=user.id, user_email=user.email, payload=payload
    )


@router.get("/{org_id}/workspaces", response_model=list[WorkspaceResponse])
async def list_org_workspaces(
    org_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[WorkspaceResponse]:
    return await AuthService(db).list_org_workspaces(org_id)


@router.post(
    "/{org_id}/workspaces", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED
)
async def create_workspace(
    org_id: str,
    payload: WorkspaceCreateRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceResponse:
    return await AuthService(db).create_workspace(org_id=org_id, payload=payload)


# ── Members ───────────────────────────────────────────────────────────────────

@router.post(
    "/{org_id}/members/invite",
    response_model=OrgMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    org_id: str,
    payload: MemberInviteRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrgMemberResponse:
    """Invite a user by email. Creates a PENDING membership + signed invite token."""
    inviter_role = assert_org_permission(ctx.user, org_id, Permission.ORG_MANAGE_MEMBERS)
    if role_rank(payload.role) > role_rank(inviter_role):
        raise PermissionDeniedException("Cannot grant a role higher than your own")
    member_response, _token = await AuthService(db).invite_member(
        org_id=org_id, inviter_id=ctx.user.id, payload=payload
    )
    # In production, email _token to the invitee. Returning member for now.
    return member_response


@router.post("/invites/accept", response_model=dict)
async def accept_invite(
    payload: AcceptInviteRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Accept an email invite. Creates user account if not already registered."""
    token_response = await AuthService(db).accept_invite(
        token=payload.token, payload=payload
    )
    return token_response.model_dump()


# ── Departments ───────────────────────────────────────────────────────────────

@router.post(
    "/{org_id}/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED
)
async def create_department(
    org_id: str,
    payload: DepartmentCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DepartmentResponse:
    return await AuthService(db).create_department(org_id=org_id, payload=payload)


@router.get("/{org_id}/departments", response_model=list[DepartmentResponse])
async def list_departments(
    org_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DepartmentResponse]:
    return await AuthService(db).list_departments(org_id=org_id)


# ── Teams ─────────────────────────────────────────────────────────────────────

@router.post(
    "/{org_id}/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED
)
async def create_team(
    org_id: str,
    payload: TeamCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TeamResponse:
    return await AuthService(db).create_team(org_id=org_id, payload=payload)


@router.get("/{org_id}/teams", response_model=list[TeamResponse])
async def list_teams(
    org_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[TeamResponse]:
    return await AuthService(db).list_teams(org_id=org_id)


@router.post(
    "/{org_id}/teams/{team_id}/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_member(
    org_id: str,
    team_id: str,
    payload: TeamMemberAddRequest,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TeamMemberResponse:
    return await AuthService(db).add_team_member(
        org_id=org_id, team_id=team_id, payload=payload
    )
