"""Database repository for User, Organization, and Membership entities."""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.core.security import hash_token
from src.models.auth import Organization, OrgMember, OrgRole, RefreshToken, User, Workspace


def slugify(text: str) -> str:
    """Convert text into URL-friendly slug."""
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

    async def create_organization(self, name: str, slug: str | None = None) -> Organization:
        base_slug = slugify(slug or name)
        final_slug = base_slug
        counter = 1

        # Check for slug collision
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

    async def add_org_member(self, org_id: str, user_id: str, role: OrgRole) -> OrgMember:
        member = OrgMember(org_id=org_id, user_id=user_id, role=role)
        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def get_org_membership(self, org_id: str, user_id: str) -> OrgMember | None:
        stmt = select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_user_orgs(self, user_id: str) -> list[tuple[Organization, OrgRole]]:
        """Return (organization, role) for every org the user is a member of."""
        stmt = (
            select(Organization, OrgMember.role)
            .join(OrgMember, OrgMember.org_id == Organization.id)
            .where(OrgMember.user_id == user_id)
            .order_by(Organization.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

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
        base_slug = slugify(slug or name)
        ws = Workspace(org_id=org_id, name=name.strip(), slug=base_slug, description=description)
        self.db.add(ws)
        await self.db.flush()
        await self.db.refresh(ws)
        return ws

    async def save_refresh_token(
        self, user_id: str, token: str, expires_at: datetime
    ) -> RefreshToken:
        # Store only the hash so a database leak does not expose usable tokens.
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
