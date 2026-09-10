"""Pydantic v2 schemas for Billing — Plans, Subscriptions, Invoices."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.models.billing import InvoiceStatus, SubscriptionStatus


class SubscriptionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    price_monthly: float
    price_yearly: float
    currency: str
    max_members: int
    max_projects: int
    max_storage_gb: int


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    plan_id: str
    status: SubscriptionStatus
    trial_start: datetime | None
    trial_end: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    canceled_at: datetime | None
    created_at: datetime


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    subscription_id: str
    amount: float
    currency: str
    status: InvoiceStatus
    due_date: datetime | None
    paid_at: datetime | None
    stripe_invoice_id: str | None
    created_at: datetime
