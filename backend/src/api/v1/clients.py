"""Client Portal API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.rbac import AuthContext, Permission, require_permission
from src.schemas.client import (
    ClientContactCreate,
    ClientContactResponse,
    ClientContactUpdate,
    ClientProjectAccessCreate,
    ClientProjectAccessResponse,
)
from src.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.post("", response_model=ClientContactResponse, status_code=status.HTTP_201_CREATED)
async def create_client_contact(
    payload: ClientContactCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ClientContactResponse:
    return await ClientService(db).create_contact(org_id=ctx.org_id, payload=payload)


@router.get("", response_model=list[ClientContactResponse])
async def list_client_contacts(
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ClientContactResponse]:
    return await ClientService(db).list_contacts(org_id=ctx.org_id)


@router.get("/{contact_id}", response_model=ClientContactResponse)
async def get_client_contact(
    contact_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ClientContactResponse:
    return await ClientService(db).get_contact(contact_id=contact_id, org_id=ctx.org_id)


@router.patch("/{contact_id}", response_model=ClientContactResponse)
async def update_client_contact(
    contact_id: str,
    payload: ClientContactUpdate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ClientContactResponse:
    return await ClientService(db).update_contact(
        contact_id=contact_id, org_id=ctx.org_id, payload=payload
    )


@router.post(
    "/{contact_id}/project-access",
    response_model=ClientProjectAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_project_access(
    contact_id: str,
    payload: ClientProjectAccessCreate,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ClientProjectAccessResponse:
    return await ClientService(db).grant_project_access(
        contact_id=contact_id, org_id=ctx.org_id, granted_by_id=ctx.user.id, payload=payload
    )


@router.delete("/project-access/{access_id}")
async def revoke_project_access(
    access_id: str,
    ctx: Annotated[AuthContext, Depends(require_permission(Permission.PROJECT_MANAGE_MEMBERS))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    return await ClientService(db).revoke_project_access(access_id=access_id)
