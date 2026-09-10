"""Pydantic v2 schemas for Client Portal."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClientContactCreate(BaseModel):
    user_id: str
    company_name: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None


class ClientContactUpdate(BaseModel):
    company_name: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class ClientContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    user_id: str
    company_name: str | None
    phone: str | None
    address: str | None
    notes: str | None
    is_active: bool
    created_at: datetime


class ClientProjectAccessCreate(BaseModel):
    project_id: str
    can_create_tickets: bool = True
    can_comment: bool = True
    can_view_timesheets: bool = False


class ClientProjectAccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_contact_id: str
    project_id: str
    can_create_tickets: bool
    can_comment: bool
    can_view_timesheets: bool
    granted_by_id: str | None
    created_at: datetime
