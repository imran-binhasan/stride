import hashlib
import hmac
import json
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.database import get_db_session
from src.core.exceptions import AuthenticationError, ValidationException
from src.core.rbac import AuthContext, Permission, require_permission
from src.models.auth import Organization
from src.models.billing import Invoice, Subscription
from src.schemas.billing import InvoiceResponse, SubscriptionResponse
from src.services.billing_service import LIMITS, BillingService, prices

router = APIRouter(prefix="/billing", tags=["Billing"])
DB = Annotated[AsyncSession, Depends(get_db_session)]
Owner = Annotated[AuthContext, Depends(require_permission(Permission.ORG_BILLING))]


@router.get("")
async def status(ctx: Owner, db: DB):
    org = await db.get(Organization, ctx.org_id)
    sub = await db.scalar(select(Subscription).where(Subscription.org_id == ctx.org_id))
    invoices = list(
        await db.scalars(
            select(Invoice)
            .where(Invoice.org_id == ctx.org_id)
            .order_by(Invoice.created_at.desc())
            .limit(100)
        )
    )
    return {
        "tier": org.subscription_tier,
        "max_members": org.max_members,
        "max_projects": org.max_projects,
        "subscription": SubscriptionResponse.model_validate(sub) if sub else None,
        "invoices": [InvoiceResponse.model_validate(i) for i in invoices],
        "plans": [
            {"tier": tier, "max_members": LIMITS[tier][0], "max_projects": LIMITS[tier][1]}
            for tier in prices()
        ],
    }


class Checkout(BaseModel):
    tier: Literal["STARTER", "PRO", "ENTERPRISE"]


@router.post("/checkout")
async def checkout(payload: Checkout, ctx: Owner, db: DB):
    return await BillingService(db).checkout(ctx.org_id, payload.tier)


@router.post("/portal")
async def portal(ctx: Owner, db: DB):
    return await BillingService(db).portal(ctx.org_id)


@router.post("/webhook")
async def webhook(
    request: Request, db: DB, stripe_signature: Annotated[str | None, Header()] = None
):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise ValidationException("Billing webhook is not configured")
    body = await request.body()
    if len(body) > 1024 * 1024:
        raise ValidationException("Webhook is too large")
    parts = [p.split("=", 1) for p in (stripe_signature or "").split(",") if "=" in p]
    try:
        timestamp = int(next(v for k, v in parts if k == "t"))
    except (ValueError, StopIteration) as exc:
        raise AuthenticationError("Invalid webhook signature") from exc
    expected = hmac.new(
        settings.STRIPE_WEBHOOK_SECRET.encode(),
        str(timestamp).encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    if abs(time.time() - timestamp) > 300 or not any(
        k == "v1" and hmac.compare_digest(v, expected) for k, v in parts
    ):
        raise AuthenticationError("Invalid webhook signature")
    try:
        event = json.loads(body)
    except ValueError as exc:
        raise ValidationException("Invalid webhook payload") from exc
    if not isinstance(event, dict) or not isinstance(event.get("id"), str) or len(event["id"]) > 36:
        raise ValidationException("Invalid event identifier")
    return await BillingService(db).webhook(event)
