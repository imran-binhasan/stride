"""Database repository for User, Organization, Membership, Teams, and Departments."""

import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.security import hash_token
from src.models.auth import (
    Department,
    MemberStatus,
    OrgMember,
    OrgRole,
    Organization,
    RefreshToken,
    Team,
    TeamMember,
    TeamRole,
    User,
    Workspace,
)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.memberships).selectinload(OrgMember.organization))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.lower())
            .options(selectinload(User.memberships).selectinload(OrgMember.organization))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        hashed_password: str,
        full_name: str,
        is_superadmin: bool = False,
    ) -> User:
        user = User(
            email=email.lower().strip(),
            hashed_password=hashed_password,
            full_name=full_name.strip(),
            is_superadmin=is_superadmin,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_user(self, user: User, **fields) -> User:
        for k, v in fields.items():
            if v is not None:
                setattr(user, k, v)
        await self.db.flush()
        return user

    # ── Organizations ─────────────────────────────────────────────────────────

    async def create_organization(self, name: str, slug: str | None = None) -> Organization:
        base_slug = slugify(slug or name)
        final_slug = base_slug
        counter = 1
        while True:
            existing = await self.get_org_by_slug(final_slug)
            if not existing:
                break
            final_slug = f"{base_slug}-{counter}"
            counter += 1

        org = Organization(name=name.strip(), slug=final_slug)
        self.db.add(org)
        await self.db.flush()
        await self.db.refresh(org)
        return org

    async def get_org_by_id(self, org_id: str) -> Organization | None:
        stmt = (
            select(Organization)
            .where(Organization.id == org_id)
            .options(
                selectinload(Organization.members).selectinload(OrgMember.user),
                selectinload(Organization.workspaces),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_org_by_slug(self, slug: str) -> Organization | None:
        stmt = select(Organization).where(Organization.slug == slug)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ── Memberships ───────────────────────────────────────────────────────────

    async def add_org_member(
        self,
        org_id: str,
        user_id: str,
        role: OrgRole,
        email: str,
        status: MemberStatus = MemberStatus.ACTIVE,
    ) -> OrgMember:
        member = OrgMember(
            org_id=org_id,
            user_id=user_id,
            email=email.lower(),
            role=role,
            status=status,
            joined_at=datetime.now(UTC) if status == MemberStatus.ACTIVE else None,
        )
        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def create_invite(
        self,
        org_id: str,
        email: str,
        role: OrgRole,
        invited_by_id: str,
        ttl_hours: int = 72,
    ) -> OrgMember:
        token = secrets.token_urlsafe(32)
        member = OrgMember(
            org_id=org_id,
            email=email.lower(),
            role=role,
            status=MemberStatus.PENDING,
            invite_token=hash_token(token),
            invite_expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
            invited_by_id=invited_by_id,
        )
        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(member)
        # Return token in plaintext so the caller can email it
        member._plaintext_token = token  # noqa: SLF001
        return member

    async def get_invite_by_token(self, token: str) -> OrgMember | None:
        stmt = select(OrgMember).where(
            OrgMember.invite_token == hash_token(token),
            OrgMember.status == MemberStatus.PENDING,
            OrgMember.invite_expires_at > datetime.now(UTC),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def activate_invite(self, member: OrgMember, user_id: str) -> OrgMember:
        member.user_id = user_id
        member.status = MemberStatus.ACTIVE
        member.joined_at = datetime.now(UTC)
        member.invite_token = None
        member.invite_expires_at = None
        await self.db.flush()
        return member

    async def get_org_membership(self, org_id: str, user_id: str) -> OrgMember | None:
        stmt = select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_member_by_email(self, org_id: str, email: str) -> OrgMember | None:
        stmt = select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.email == email.lower(),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_user_orgs(self, user_id: str) -> list[tuple[Organization, OrgRole]]:
        stmt = (
            select(Organization, OrgMember.role)
            .join(OrgMember, OrgMember.org_id == Organization.id)
            .where(OrgMember.user_id == user_id, OrgMember.status == MemberStatus.ACTIVE)
            .order_by(Organization.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    # ── Workspaces ────────────────────────────────────────────────────────────

    async def list_workspaces(self, org_id: str) -> list[Workspace]:
        stmt = (
            select(Workspace)
            .where(Workspace.org_id == org_id)
            .order_by(Workspace.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_workspace(
        self, org_id: str, name: str, slug: str | None = None, description: str | None = None
    ) -> Workspace:
        ws = Workspace(
            org_id=org_id,
            name=name.strip(),
            slug=slugify(slug or name),
            description=description,
        )
        self.db.add(ws)
        await self.db.flush()
        await self.db.refresh(ws)
        return ws

    # ── Departments ───────────────────────────────────────────────────────────

    async def create_department(
        self, org_id: str, name: str, description: str | None = None, head_user_id: str | None = None
    ) -> Department:
        dept = Department(org_id=org_id, name=name.strip(), description=description, head_user_id=head_user_id)
        self.db.add(dept)
        await self.db.flush()
        await self.db.refresh(dept)
        return dept

    async def list_departments(self, org_id: str) -> list[Department]:
        stmt = select(Department).where(Department.org_id == org_id).order_by(Department.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Teams ─────────────────────────────────────────────────────────────────

    async def create_team(
        self,
        org_id: str,
        name: str,
        identifier: str,
        department_id: str | None = None,
        color: str = "#6B7280",
    ) -> Team:
        team = Team(
            org_id=org_id,
            name=name.strip(),
            identifier=identifier.upper().strip(),
            department_id=department_id,
            color=color,
        )
        self.db.add(team)
        await self.db.flush()
        await self.db.refresh(team)
        return team

    async def list_teams(self, org_id: str) -> list[Team]:
        stmt = (
            select(Team)
            .where(Team.org_id == org_id)
            .options(selectinload(Team.members))
            .order_by(Team.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_team_by_id(self, team_id: str, org_id: str) -> Team | None:
        stmt = (
            select(Team)
            .where(Team.id == team_id, Team.org_id == org_id)
            .options(selectinload(Team.members))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_team_member(self, team_id: str, user_id: str, role: TeamRole) -> TeamMember:
        tm = TeamMember(team_id=team_id, user_id=user_id, role=role)
        self.db.add(tm)
        await self.db.flush()
        await self.db.refresh(tm)
        return tm

    # ── Refresh Tokens ────────────────────────────────────────────────────────

    async def save_refresh_token(self, user_id: str, token: str, expires_at: datetime) -> RefreshToken:
        rt = RefreshToken(user_id=user_id, token=hash_token(token), expires_at=expires_at)
        self.db.add(rt)
        await self.db.flush()
        return rt

    async def get_refresh_token(self, token: str) -> RefreshToken | None:
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.token == hash_token(token),
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > datetime.now(UTC),
            )
            .options(selectinload(RefreshToken.user).selectinload(User.memberships))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token: str) -> None:
        stmt = select(RefreshToken).where(RefreshToken.token == hash_token(token))
        result = await self.db.execute(stmt)
        rt = result.scalar_one_or_none()
        if rt:
            rt.revoked = True
            await self.db.flush()
