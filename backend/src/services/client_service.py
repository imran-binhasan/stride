"""Client Portal business logic."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ConflictException, EntityNotFoundException
from src.repositories.client_repo import ClientRepository
from src.schemas.client import (
    ClientContactCreate,
    ClientContactResponse,
    ClientContactUpdate,
    ClientProjectAccessCreate,
    ClientProjectAccessResponse,
)


class ClientService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ClientRepository(db)

    async def create_contact(self, org_id: str, payload: ClientContactCreate) -> ClientContactResponse:
        existing = await self.repo.get_contact_by_user(payload.user_id, org_id)
        if existing:
            raise ConflictException("A client contact already exists for this user")
        contact = await self.repo.create_contact(
            org_id=org_id,
            user_id=payload.user_id,
            company_name=payload.company_name,
            phone=payload.phone,
            address=payload.address,
            notes=payload.notes,
        )
        return ClientContactResponse.model_validate(contact)

    async def get_contact(self, contact_id: str, org_id: str) -> ClientContactResponse:
        contact = await self.repo.get_contact_by_id(contact_id, org_id)
        if not contact:
            raise EntityNotFoundException("ClientContact", contact_id)
        return ClientContactResponse.model_validate(contact)

    async def list_contacts(self, org_id: str) -> list[ClientContactResponse]:
        contacts = await self.repo.list_contacts(org_id)
        return [ClientContactResponse.model_validate(c) for c in contacts]

    async def update_contact(
        self, contact_id: str, org_id: str, payload: ClientContactUpdate
    ) -> ClientContactResponse:
        contact = await self.repo.get_contact_by_id(contact_id, org_id)
        if not contact:
            raise EntityNotFoundException("ClientContact", contact_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(contact, field, value)
        await self.db.flush()
        return ClientContactResponse.model_validate(contact)

    async def grant_project_access(
        self, contact_id: str, org_id: str, granted_by_id: str, payload: ClientProjectAccessCreate
    ) -> ClientProjectAccessResponse:
        contact = await self.repo.get_contact_by_id(contact_id, org_id)
        if not contact:
            raise EntityNotFoundException("ClientContact", contact_id)

        existing = await self.repo.get_project_access(contact_id, payload.project_id)
        if existing:
            raise ConflictException("Client already has access to this project")

        access = await self.repo.grant_project_access(
            client_contact_id=contact_id,
            project_id=payload.project_id,
            can_create_tickets=payload.can_create_tickets,
            can_comment=payload.can_comment,
            can_view_timesheets=payload.can_view_timesheets,
            granted_by_id=granted_by_id,
        )
        return ClientProjectAccessResponse.model_validate(access)

    async def revoke_project_access(self, access_id: str) -> dict:
        success = await self.repo.revoke_project_access(access_id)
        if not success:
            raise EntityNotFoundException("ClientProjectAccess", access_id)
        return {"success": True}
