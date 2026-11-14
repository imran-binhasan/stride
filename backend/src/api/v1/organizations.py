"""Organization, Workspace, Department, Team, and Invite API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.core.database import get_db_session
from src.core.exceptions import (
    ConflictException,
    EntityNotFoundException,
    PermissionDeniedException,
)
from src.core.rbac import (
    AuthContext,
    Permission,
    assert_org_permission,
    get_current_user,
    require_permission,
    role_rank,
)
from src.models.auth import MemberStatus, OrgMember, OrgRole, User
from src.repositories.user_repo import UserRepository
from src.schemas.auth import (
    AcceptInviteRequest,
    DepartmentCreate,
    DepartmentResponse,
    InviteResponse,
    MemberInviteRequest,
    MemberUpdateRequest,
    MyOrgResponse,
    OrgCreateRequest,
    OrgMemberResponse,
    OrgResponse,
    OrgUpdateRequest,
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
    if user.is_superadmin:
        from src.models.auth import Organization

        rows = list(
            await db.scalars(
                select(Organization).order_by(Organization.created_at.desc()).limit(200)
            )
        )
        return [
            MyOrgResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                subscription_tier=org.subscription_tier,
                role=OrgRole.ORG_OWNER,
                created_at=org.created_at,
            )
            for org in rows
        ]
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
    assert_org_permission(ctx.user, org_id, Permission.ORG_READ)
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
    assert_org_permission(ctx.user, org_id, Permission.ORG_MANAGE_MEMBERS)
    return await AuthService(db).create_workspace(org_id=org_id, payload=payload)


# ── Members ───────────────────────────────────────────────────────────────────


@router.post(
    "/{org_id}/members/invite",
    response_model=InviteResponse,
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
    return InviteResponse(**member_response.model_dump(), invite_token=_token)


@router.post("/invites/accept", response_model=dict)
async def accept_invite(
    payload: AcceptInviteRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Accept an email invite. Creates user account if not already registered."""
    token_response = await AuthService(db).accept_invite(token=payload.token, payload=payload)
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
    assert_org_permission(ctx.user, org_id, Permission.ORG_MANAGE_MEMBERS)
    return await AuthService(db).create_department(org_id=org_id, payload=payload)


@router.get("/{org_id}/departments", response_model=list[DepartmentResponse])
async def list_departments(
    org_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DepartmentResponse]:
    assert_org_permission(ctx.user, org_id, Permission.ORG_READ)
    return await AuthService(db).list_departments(org_id=org_id)


# ── Teams ─────────────────────────────────────────────────────────────────────


@router.post("/{org_id}/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    org_id: str,
    payload: TeamCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TeamResponse:
    assert_org_permission(ctx.user, org_id, Permission.ORG_MANAGE_MEMBERS)
    return await AuthService(db).create_team(org_id=org_id, payload=payload)


@router.get("/{org_id}/teams", response_model=list[TeamResponse])
async def list_teams(
    org_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.ORG_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[TeamResponse]:
    assert_org_permission(ctx.user, org_id, Permission.ORG_READ)
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
    assert_org_permission(ctx.user, org_id, Permission.ORG_MANAGE_MEMBERS)
    return await AuthService(db).add_team_member(org_id=org_id, team_id=team_id, payload=payload)


@router.get("/{org_id}/members", response_model=list[OrgMemberResponse])
async def list_members(
    org_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    assert_org_permission(user, org_id, Permission.ORG_READ)
    result = await db.scalars(
        select(OrgMember).where(OrgMember.org_id == org_id).options(selectinload(OrgMember.user))
    )
    return [OrgMemberResponse.model_validate(m) for m in result]


@router.post("/{org_id}/members", response_model=OrgMemberResponse, status_code=201)
async def add_existing_member(
    org_id: str,
    payload: MemberInviteRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    role = assert_org_permission(user, org_id, Permission.ORG_MANAGE_MEMBERS)
    if role_rank(payload.role) > role_rank(role):
        raise PermissionDeniedException("Cannot grant a role higher than your own")
    repo = UserRepository(db)
    target = await repo.get_by_email(payload.email)
    if not target:
        raise EntityNotFoundException("User", payload.email)
    if await repo.get_member_by_email(org_id, payload.email):
        raise ConflictException("User already has a membership")
    from src.services.quota_service import reserve_capacity

    await reserve_capacity(db, org_id, "members")
    member = await repo.add_org_member(org_id, target.id, payload.role, target.email)
    member.user = target
    return OrgMemberResponse.model_validate(member)


@router.patch("/{org_id}/members/{member_id}", response_model=OrgMemberResponse)
async def update_member(
    org_id: str,
    member_id: str,
    payload: MemberUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    from src.models.auth import Organization
    from src.services.notification_service import NotificationService

    actor_role = assert_org_permission(user, org_id, Permission.ORG_MANAGE_MEMBERS)
    # Lock the organization to serialize simultaneous last-owner changes.
    await db.execute(select(Organization.id).where(Organization.id == org_id).with_for_update())
    member = await db.scalar(
        select(OrgMember)
        .where(OrgMember.id == member_id, OrgMember.org_id == org_id)
        .options(selectinload(OrgMember.user))
    )
    if not member:
        raise EntityNotFoundException("Member", member_id)
    if (
        role_rank(member.role) > role_rank(actor_role)
        or payload.role
        and role_rank(payload.role) > role_rank(actor_role)
    ):
        raise PermissionDeniedException(
            "Cannot modify a higher-ranked member or grant a higher role"
        )
    if member.status == MemberStatus.PENDING and payload.status == MemberStatus.ACTIVE:
        raise ConflictException("Pending invitations must be accepted by the invitee")
    if payload.status == MemberStatus.PENDING:
        raise ConflictException("Use the invite endpoint to create pending memberships")
    loses_owner = (
        member.role == OrgRole.ORG_OWNER
        and member.status == MemberStatus.ACTIVE
        and (
            payload.role is not None
            and payload.role != OrgRole.ORG_OWNER
            or payload.status is not None
            and payload.status != MemberStatus.ACTIVE
        )
    )
    if loses_owner:
        others = list(
            await db.scalars(
                select(OrgMember.id).where(
                    OrgMember.org_id == org_id,
                    OrgMember.role == OrgRole.ORG_OWNER,
                    OrgMember.status == MemberStatus.ACTIVE,
                    OrgMember.id != member_id,
                )
            )
        )
        if not others:
            raise ConflictException("An organization must retain at least one active owner")
    if member.status == MemberStatus.REMOVED and payload.status == MemberStatus.ACTIVE:
        from src.services.quota_service import reserve_capacity

        await reserve_capacity(db, org_id, "members")
    old = {"role": member.role.value, "status": member.status.value}
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            from src.core.exceptions import ValidationException

            raise ValidationException(f"{key} cannot be null")
        setattr(member, key, value)
    await db.flush()
    await NotificationService(db).log_audit(
        org_id,
        "member.updated",
        user.id,
        "member",
        member.id,
        old,
        {"role": member.role.value, "status": member.status.value},
    )
    return OrgMemberResponse.model_validate(member)


@router.get("/{org_id}", response_model=OrgResponse)
async def get_organization(
    org_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    assert_org_permission(user, org_id, Permission.ORG_READ)
    org = await UserRepository(db).get_org_by_id(org_id)
    if not org:
        raise EntityNotFoundException("Organization", org_id)
    return OrgResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_organization(
    org_id: str,
    payload: OrgUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    assert_org_permission(user, org_id, Permission.ORG_UPDATE)
    org = await UserRepository(db).get_org_by_id(org_id)
    if not org:
        raise EntityNotFoundException("Organization", org_id)
    if payload.name is not None:
        org.name = payload.name
    if "logo_url" in payload.model_fields_set:
        org.logo_url = payload.logo_url
    await db.flush()
    return OrgResponse.model_validate(org)
