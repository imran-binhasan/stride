"""Authentication and organization business logic service."""

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
from src.models.auth import OrgRole, User
from src.repositories.user_repo import UserRepository
from src.schemas.auth import (
    MemberInviteRequest,
    MyOrgResponse,
    OrgCreateRequest,
    OrgMemberResponse,
    OrgResponse,
    TokenResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
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
        existing_user = await self.repo.get_by_email(payload.email)
        if existing_user:
            raise ConflictException(f"User with email '{payload.email}' already exists")

        # 1. Create user account (Argon2 is CPU-bound — run off the event loop)
        hashed = await asyncio.to_thread(hash_password, payload.password)
        user = await self.repo.create_user(
            email=payload.email,
            hashed_password=hashed,
            full_name=payload.full_name,
        )

        # 2. Create initial organization & workspace if requested or default
        org_name = payload.organization_name or f"{payload.full_name.split()[0]}'s Org"
        org = await self.repo.create_organization(name=org_name)
        await self.repo.add_org_member(org_id=org.id, user_id=user.id, role=OrgRole.ORG_OWNER)
        await self.repo.create_workspace(
            org_id=org.id, name="General", description="Default Workspace"
        )

        # 3. Issue Token Pair
        token_response = await self._generate_token_pair(
            user, active_org_id=org.id, role=OrgRole.ORG_OWNER
        )
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

        # Determine default org context
        default_org_id = user.memberships[0].org_id if user.memberships else None
        default_role = user.memberships[0].role if user.memberships else None

        return await self._generate_token_pair(
            user, active_org_id=default_org_id, role=default_role
        )

    async def refresh_tokens(self, refresh_token_str: str) -> TokenResponse:
        rt = await self.repo.get_refresh_token(refresh_token_str)
        if not rt:
            raise AuthenticationError("Invalid or expired refresh token")

        # Revoke old token for rotation
        await self.repo.revoke_refresh_token(refresh_token_str)

        user = rt.user
        if not user.is_active:
            raise AuthenticationError("User account is inactive")
        default_org_id = user.memberships[0].org_id if user.memberships else None
        default_role = user.memberships[0].role if user.memberships else None

        return await self._generate_token_pair(
            user, active_org_id=default_org_id, role=default_role
        )

    async def logout(self, refresh_token_str: str) -> dict:
        """Revoke a refresh token so it can no longer be used to mint access tokens."""
        await self.repo.revoke_refresh_token(refresh_token_str)
        return {"success": True, "message": "Logged out"}

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

    async def list_org_workspaces(self, org_id: str) -> list[WorkspaceResponse]:
        workspaces = await self.repo.list_workspaces(org_id)
        return [WorkspaceResponse.model_validate(ws) for ws in workspaces]

    async def create_organization(self, user_id: str, payload: OrgCreateRequest) -> OrgResponse:
        org = await self.repo.create_organization(name=payload.name, slug=payload.slug)
        await self.repo.add_org_member(org_id=org.id, user_id=user_id, role=OrgRole.ORG_OWNER)
        await self.repo.create_workspace(org_id=org.id, name="General")
        return OrgResponse.model_validate(org)

    async def invite_member(self, org_id: str, payload: MemberInviteRequest) -> OrgMemberResponse:
        user = await self.repo.get_by_email(payload.email)
        if not user:
            raise EntityNotFoundException("User", payload.email)

        existing = await self.repo.get_org_membership(org_id=org_id, user_id=user.id)
        if existing:
            raise ConflictException(
                f"User is already a member of this organization with role {existing.role.value}"
            )

        member = await self.repo.add_org_member(org_id=org_id, user_id=user.id, role=payload.role)
        # Build explicitly: OrgMember has no `joined_at` column, and validating the ORM
        # object directly would lazy-load `member.user` in the async context.
        return OrgMemberResponse(
            id=member.id,
            user_id=member.user_id,
            role=member.role,
            joined_at=member.created_at,
            user=UserProfileResponse.model_validate(user),
        )

    async def create_workspace(
        self, org_id: str, payload: WorkspaceCreateRequest
    ) -> WorkspaceResponse:
        ws = await self.repo.create_workspace(
            org_id=org_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
        return WorkspaceResponse.model_validate(ws)

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
