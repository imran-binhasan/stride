"""Database repository for Client Portal — ClientContact and ClientProjectAccess."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.client import ClientContact, ClientProjectAccess


class ClientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_contact_by_id(self, contact_id: str, org_id: str) -> ClientContact | None:
        stmt = (
            select(ClientContact)
            .where(ClientContact.id == contact_id, ClientContact.org_id == org_id)
            .options(selectinload(ClientContact.project_access))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_contact_by_user(self, user_id: str, org_id: str) -> ClientContact | None:
        stmt = (
            select(ClientContact)
            .where(ClientContact.user_id == user_id, ClientContact.org_id == org_id)
            .options(selectinload(ClientContact.project_access))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_contacts(self, org_id: str) -> list[ClientContact]:
        stmt = (
            select(ClientContact)
            .where(ClientContact.org_id == org_id)
            .options(selectinload(ClientContact.project_access))
            .order_by(ClientContact.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_contact(
        self,
        org_id: str,
        user_id: str,
        company_name: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        notes: str | None = None,
    ) -> ClientContact:
        contact = ClientContact(
            org_id=org_id,
            user_id=user_id,
            company_name=company_name,
            phone=phone,
            address=address,
            notes=notes,
        )
        self.db.add(contact)
        await self.db.flush()
        await self.db.refresh(contact)
        return contact

    async def grant_project_access(
        self,
        client_contact_id: str,
        project_id: str,
        can_create_tickets: bool = True,
        can_comment: bool = True,
        can_view_timesheets: bool = False,
        granted_by_id: str | None = None,
    ) -> ClientProjectAccess:
        access = ClientProjectAccess(
            client_contact_id=client_contact_id,
            project_id=project_id,
            can_create_tickets=can_create_tickets,
            can_comment=can_comment,
            can_view_timesheets=can_view_timesheets,
            granted_by_id=granted_by_id,
        )
        self.db.add(access)
        await self.db.flush()
        await self.db.refresh(access)
        return access

    async def get_project_access(
        self, client_contact_id: str, project_id: str
    ) -> ClientProjectAccess | None:
        stmt = select(ClientProjectAccess).where(
            ClientProjectAccess.client_contact_id == client_contact_id,
            ClientProjectAccess.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_project_access(self, access_id: str) -> bool:
        stmt = select(ClientProjectAccess).where(ClientProjectAccess.id == access_id)
        result = await self.db.execute(stmt)
        access = result.scalar_one_or_none()
        if access:
            await self.db.delete(access)
            await self.db.flush()
            return True
        return False
