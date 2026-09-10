"""Billing domain — SubscriptionPlan, Subscription, Invoice (SaaS only)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampedModel, generate_uuid

if TYPE_CHECKING:
    from src.models.auth import Organization


class SubscriptionStatus(enum.StrEnum):
    TRIALING  = "TRIALING"
    ACTIVE    = "ACTIVE"
    PAST_DUE  = "PAST_DUE"
    CANCELED  = "CANCELED"


class InvoiceStatus(enum.StrEnum):
    DRAFT         = "DRAFT"
    OPEN          = "OPEN"
    PAID          = "PAID"
    VOID          = "VOID"
    UNCOLLECTIBLE = "UNCOLLECTIBLE"


class SubscriptionPlan(Base, TimestampedModel):
    __tablename__ = "subscription_plans"

    id                     : Mapped[str]           = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name                   : Mapped[str]           = mapped_column(String(100), nullable=False)
    slug                   : Mapped[str]           = mapped_column(String(50), unique=True, nullable=False)
    price_monthly          : Mapped[float]         = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    price_yearly           : Mapped[float]         = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    currency               : Mapped[str]           = mapped_column(String(3), default="USD", nullable=False)
    max_members            : Mapped[int]           = mapped_column(default=5,   nullable=False)
    max_projects           : Mapped[int]           = mapped_column(default=3,   nullable=False)
    max_storage_gb         : Mapped[int]           = mapped_column(default=5,   nullable=False)
    feature_flags          : Mapped[dict[str,Any]] = mapped_column(JSON, default=dict, nullable=False)
    stripe_price_id_monthly: Mapped[str|None]      = mapped_column(String(255), nullable=True)
    stripe_price_id_yearly : Mapped[str|None]      = mapped_column(String(255), nullable=True)

    subscriptions: Mapped[list[Subscription]] = relationship("Subscription", back_populates="plan")


class Subscription(Base, TimestampedModel):
    __tablename__ = "subscriptions"

    id                    : Mapped[str]                = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id                : Mapped[str]                = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    plan_id               : Mapped[str]                = mapped_column(String(36), ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False)
    status                : Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus, native_enum=False, length=20), default=SubscriptionStatus.TRIALING, nullable=False)
    trial_start           : Mapped[datetime|None]      = mapped_column(DateTime(timezone=True), nullable=True)
    trial_end             : Mapped[datetime|None]      = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start  : Mapped[datetime|None]      = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end    : Mapped[datetime|None]      = mapped_column(DateTime(timezone=True), nullable=True)
    stripe_subscription_id: Mapped[str|None]           = mapped_column(String(255), unique=True, nullable=True)
    stripe_customer_id    : Mapped[str|None]           = mapped_column(String(255), nullable=True)
    canceled_at           : Mapped[datetime|None]      = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization]  = relationship("Organization")
    plan        : Mapped[SubscriptionPlan] = relationship("SubscriptionPlan", back_populates="subscriptions")
    invoices    : Mapped[list[Invoice]] = relationship("Invoice", back_populates="subscription", cascade="all, delete-orphan")


class Invoice(Base, TimestampedModel):
    __tablename__ = "invoices"

    id                : Mapped[str]           = mapped_column(String(36), primary_key=True, default=generate_uuid)
    org_id            : Mapped[str]           = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    subscription_id   : Mapped[str]           = mapped_column(String(36), ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=False)
    amount            : Mapped[float]         = mapped_column(Numeric(10, 2), nullable=False)
    currency          : Mapped[str]           = mapped_column(String(3), default="USD", nullable=False)
    status            : Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus, native_enum=False, length=20), default=InvoiceStatus.DRAFT, nullable=False)
    due_date          : Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at           : Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    stripe_invoice_id : Mapped[str|None]      = mapped_column(String(255), unique=True, nullable=True)

    subscription: Mapped[Subscription] = relationship("Subscription", back_populates="invoices")
