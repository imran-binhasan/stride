"""Authentication and organization business logic."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.exceptions import AuthenticationError, ConflictException, EntityNotFoundException
from src.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from src.models.auth import MemberStatus, OrgRole, TeamRole, User
from src.repositories.user_repo import UserRepository
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
    TokenResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
    UserUpdateRequest,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def register(
        self, payload: UserRegisterRequest
    ) -> tuple[UserProfileResponse, TokenResponse]:
        if await self.repo.get_by_email(payload.email):
            raise ConflictException(f"User with email '{payload.email}' already exists")

        hashed = await asyncio.to_thread(hash_password, payload.password)
        user = await self.repo.create_user(
            email=payload.email, hashed_password=hashed, full_name=payload.full_name
        )

        org_name = payload.organization_name or f"{payload.full_name.split()[0]}'s Org"
        org = await self.repo.create_organization(name=org_name)

        # Bootstrap trial: 30 days
        org.trial_ends_at = datetime.now(UTC) + timedelta(days=30)
        org.is_trial_used = True
        await self.db.flush()

        await self.repo.add_org_member(
            org_id=org.id,
            user_id=user.id,
            email=user.email,
            role=OrgRole.ORG_OWNER,
            status=MemberStatus.ACTIVE,
        )
        await self.repo.create_workspace(org_id=org.id, name="General", description="Default Workspace")

        token_response = await self._generate_token_pair(user, active_org_id=org.id, role=OrgRole.ORG_OWNER)
        return UserProfileResponse.model_validate(user), token_response

    async def login(self, payload: UserLoginRequest) -> TokenResponse:
        user = await self.repo.get_by_email(payload.email)
        valid = bool(user) and await asyncio.to_thread(
            verify_password, payload.password, user.hashed_password
        )
        if not valid:
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        # Only consider ACTIVE memberships
        active = [m for m in user.memberships if m.status == MemberStatus.ACTIVE]
        default_org_id = active[0].org_id if active else None
        default_role = active[0].role if active else None

        return await self._generate_token_pair(user, active_org_id=default_org_id, role=default_role)

    async def refresh_tokens(self, refresh_token_str: str) -> TokenResponse:
        rt = await self.repo.get_refresh_token(refresh_token_str)
        if not rt:
            raise AuthenticationError("Invalid or expired refresh token")

        await self.repo.revoke_refresh_token(refresh_token_str)

        user = rt.user
        if not user.is_active:
            raise AuthenticationError("User account is inactive")
        active = [m for m in user.memberships if m.status == MemberStatus.ACTIVE]
        default_org_id = active[0].org_id if active else None
        default_role = active[0].role if active else None

        return await self._generate_token_pair(user, active_org_id=default_org_id, role=default_role)

    async def logout(self, refresh_token_str: str) -> dict:
        await self.repo.revoke_refresh_token(refresh_token_str)
        return {"success": True, "message": "Logged out"}

    async def update_profile(self, user: User, payload: UserUpdateRequest) -> UserProfileResponse:
        await self.repo.update_user(user, **payload.model_dump(exclude_none=True))
        return UserProfileResponse.model_validate(user)

    # ── Organizations ─────────────────────────────────────────────────────────

    async def list_user_organizations(self, user_id: str) -> list[MyOrgResponse]:
        rows = await self.repo.list_user_orgs(user_id)
        return [
            MyOrgResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                subscription_tier=org.subscription_tier,
                role=role,
                created_at=org.created_at,
            )
            for org, role in rows
        ]

    async def create_organization(self, user_id: str, user_email: str, payload: OrgCreateRequest) -> OrgResponse:
        org = await self.repo.create_organization(name=payload.name, slug=payload.slug)
        org.trial_ends_at = datetime.now(UTC) + timedelta(days=30)
        org.is_trial_used = True
        await self.db.flush()

        await self.repo.add_org_member(
            org_id=org.id,
            user_id=user_id,
            email=user_email,
            role=OrgRole.ORG_OWNER,
            status=MemberStatus.ACTIVE,
        )
        await self.repo.create_workspace(org_id=org.id, name="General")
        return OrgResponse.model_validate(org)

    async def list_org_workspaces(self, org_id: str) -> list[WorkspaceResponse]:
        workspaces = await self.repo.list_workspaces(org_id)
        return [WorkspaceResponse.model_validate(ws) for ws in workspaces]

    # ── Invites ───────────────────────────────────────────────────────────────

    async def invite_member(
        self, org_id: str, inviter_id: str, payload: MemberInviteRequest
    ) -> tuple[OrgMemberResponse, str]:
        """Create invite record and return (member_response, plaintext_token)."""
        existing = await self.repo.get_member_by_email(org_id=org_id, email=payload.email)
        if existing:
            raise ConflictException(f"Email '{payload.email}' already has a pending or active membership")

        member = await self.repo.create_invite(
            org_id=org_id,
            email=payload.email,
            role=payload.role,
            invited_by_id=inviter_id,
        )
        token = member._plaintext_token  # noqa: SLF001
        return OrgMemberResponse.model_validate(member), token

    async def accept_invite(self, token: str, payload: AcceptInviteRequest) -> TokenResponse:
        member = await self.repo.get_invite_by_token(token)
        if not member:
            raise AuthenticationError("Invalid or expired invite token")

        # Create user account if not already registered
        existing = await self.repo.get_by_email(member.email)
        if existing:
            user = existing
        else:
            hashed = await asyncio.to_thread(hash_password, payload.password)
            user = await self.repo.create_user(
                email=member.email,
                hashed_password=hashed,
                full_name=payload.full_name,
            )

        await self.repo.activate_invite(member, user.id)
        return await self._generate_token_pair(user, active_org_id=member.org_id, role=member.role)

    # ── Workspaces ────────────────────────────────────────────────────────────

    async def create_workspace(self, org_id: str, payload: WorkspaceCreateRequest) -> WorkspaceResponse:
        ws = await self.repo.create_workspace(
            org_id=org_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
        return WorkspaceResponse.model_validate(ws)

    # ── Departments ───────────────────────────────────────────────────────────

    async def create_department(self, org_id: str, payload: DepartmentCreate) -> DepartmentResponse:
        dept = await self.repo.create_department(
            org_id=org_id,
            name=payload.name,
            description=payload.description,
            head_user_id=payload.head_user_id,
        )
        return DepartmentResponse.model_validate(dept)

    async def list_departments(self, org_id: str) -> list[DepartmentResponse]:
        depts = await self.repo.list_departments(org_id)
        return [DepartmentResponse.model_validate(d) for d in depts]

    # ── Teams ─────────────────────────────────────────────────────────────────

    async def create_team(self, org_id: str, payload: TeamCreate) -> TeamResponse:
        team = await self.repo.create_team(
            org_id=org_id,
            name=payload.name,
            identifier=payload.identifier,
            department_id=payload.department_id,
            color=payload.color,
        )
        return TeamResponse.model_validate(team)

    async def list_teams(self, org_id: str) -> list[TeamResponse]:
        teams = await self.repo.list_teams(org_id)
        return [TeamResponse.model_validate(t) for t in teams]

    async def add_team_member(
        self, org_id: str, team_id: str, payload: TeamMemberAddRequest
    ) -> TeamMemberResponse:
        team = await self.repo.get_team_by_id(team_id, org_id)
        if not team:
            raise EntityNotFoundException("Team", team_id)

        tm = await self.repo.add_team_member(
            team_id=team_id, user_id=payload.user_id, role=payload.role
        )
        return TeamMemberResponse.model_validate(tm)

    # ── Token Utility ─────────────────────────────────────────────────────────

    async def _generate_token_pair(
        self,
        user: User,
        active_org_id: str | None = None,
        role: OrgRole | None = None,
    ) -> TokenResponse:
        claims = {
            "email": user.email,
            "name": user.full_name,
            "org_id": active_org_id,
            "role": role.value if role else None,
            "is_superadmin": user.is_superadmin,
        }
        access_token = create_access_token(subject=user.id, claims=claims)
        refresh_token_str = generate_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        await self.repo.save_refresh_token(
            user_id=user.id, token=refresh_token_str, expires_at=expires_at
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
