"""Hosted Stripe billing: application never accepts card numbers or payment success claims."""

from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import quote

import httpx
from sqlalchemy import select, text
from src.config import settings
from src.core.exceptions import EntityNotFoundException, ValidationException
from src.core.tenant_scope import set_tenant_scope
from src.models.auth import Organization, SubscriptionTier
from src.models.billing import (
    Invoice,
    InvoiceStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from src.models.integrations import WebhookEventLog

LIMITS = {
    "FREE": (5, 3, 5),
    "STARTER": (20, 20, 50),
    "PRO": (100, 200, 500),
    "ENTERPRISE": (1000, 2000, 5000),
}


def prices():
    return {
        tier: price
        for tier, price in {
            "STARTER": settings.STRIPE_PRICE_STARTER,
            "PRO": settings.STRIPE_PRICE_PRO,
            "ENTERPRISE": settings.STRIPE_PRICE_ENTERPRISE,
        }.items()
        if price
    }


async def stripe_request(method, path, data=None):
    if not settings.STRIPE_SECRET_KEY:
        raise ValidationException("Billing provider is not configured")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(
                method,
                "https://api.stripe.com/v1" + path,
                auth=(settings.STRIPE_SECRET_KEY, ""),
                data=data,
            )
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ValidationException(
            "Billing provider request failed; no local payment state was changed"
        ) from exc


class BillingService:
    def __init__(self, db):
        self.db = db

    async def checkout(self, org_id, tier):
        price = prices().get(tier)
        if not price:
            raise ValidationException("This plan is not available for checkout")
        existing = await self.db.scalar(select(Subscription).where(Subscription.org_id == org_id))
        if existing and existing.status in {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE,
        }:
            raise ValidationException("Manage your existing subscription in the billing portal")
        result = await stripe_request(
            "POST",
            "/checkout/sessions",
            {
                "mode": "subscription",
                "line_items[0][price]": price,
                "line_items[0][quantity]": "1",
                "client_reference_id": org_id,
                "subscription_data[metadata][org_id]": org_id,
                "success_url": settings.WEB_BASE_URL.rstrip("/") + "/?billing=success",
                "cancel_url": settings.WEB_BASE_URL.rstrip("/") + "/?billing=canceled",
            },
        )
        return {"url": result["url"]}

    async def portal(self, org_id):
        sub = await self.db.scalar(select(Subscription).where(Subscription.org_id == org_id))
        if not sub or not sub.stripe_customer_id:
            raise ValidationException("No billing account exists yet")
        result = await stripe_request(
            "POST",
            "/billing_portal/sessions",
            {"customer": sub.stripe_customer_id, "return_url": settings.WEB_BASE_URL.rstrip("/")},
        )
        return {"url": result["url"]}

    async def webhook(self, event):
        obj = event.get("data", {}).get("object", {})
        kind = event.get("type", "")
        if kind.startswith("customer.subscription."):
            sub_id = obj.get("id")
            org_id = obj.get("metadata", {}).get("org_id")
        elif kind == "checkout.session.completed":
            sub_id = obj.get("subscription")
            org_id = obj.get("client_reference_id")
        elif kind in {"invoice.paid", "invoice.payment_failed", "invoice.voided"}:
            sub_id = obj.get("subscription") or obj.get("parent", {}).get(
                "subscription_details", {}
            ).get("subscription")
            if not sub_id:
                return {"status": "ignored"}
            data = await stripe_request("GET", "/subscriptions/" + quote(sub_id, safe=""))
            org_id = data.get("metadata", {}).get("org_id")
        else:
            return {"status": "ignored"}
        if not org_id or not sub_id:
            return {"status": "ignored"}
        await set_tenant_scope(self.db, org_id)
        org = await self.db.scalar(
            select(Organization).where(Organization.id == org_id).with_for_update()
        )
        if not org:
            raise EntityNotFoundException("Organization", org_id)
        if await self.db.get(WebhookEventLog, event["id"]):
            return {"status": "duplicate"}
        # Fetch after acquiring the organization lock; stale deliveries cannot roll back entitlements.
        data = await stripe_request("GET", "/subscriptions/" + quote(sub_id, safe=""))
        if data.get("metadata", {}).get("org_id") != org_id:
            raise ValidationException("Subscription does not belong to this organization")
        items = data.get("items", {}).get("data", [])
        if not items:
            raise ValidationException("Subscription has no price items")
        item = items[0]
        price = item.get("price", {})
        if price.get("currency", "usd").upper() not in {"USD", "EUR", "GBP", "CAD", "AUD", "BDT"}:
            raise ValidationException("Configure a supported two-decimal billing currency")
        tier = next(
            (tier for tier, price_id in prices().items() if price_id == price.get("id")), None
        )
        if not tier:
            raise ValidationException("Subscription price is not a configured plan")
        if self.db.bind.dialect.name == "postgresql":
            await self.db.execute(text("SELECT pg_advisory_xact_lock(892348123)"))
        plan = await self.db.scalar(
            select(SubscriptionPlan).where(SubscriptionPlan.slug == tier.lower())
        )
        if not plan:
            members, projects, storage = LIMITS[tier]
            plan = SubscriptionPlan(
                id=tier.lower(),
                slug=tier.lower(),
                name=tier.title(),
                max_members=members,
                max_projects=projects,
                max_storage_gb=storage,
                price_monthly=Decimal(str(price.get("unit_amount", 0))) / 100,
                price_yearly=0,
                currency=price.get("currency", "usd").upper(),
            )
            self.db.add(plan)
            await self.db.flush()
        subscription = await self.db.scalar(
            select(Subscription).where(Subscription.org_id == org_id)
        )
        if not subscription:
            subscription = Subscription(org_id=org_id, plan_id=plan.id)
            self.db.add(subscription)
        subscription.plan_id = plan.id
        subscription.stripe_subscription_id = sub_id
        subscription.stripe_customer_id = data.get("customer")
        subscription.status = {
            "active": SubscriptionStatus.ACTIVE,
            "trialing": SubscriptionStatus.TRIALING,
            "past_due": SubscriptionStatus.PAST_DUE,
        }.get(data.get("status"), SubscriptionStatus.CANCELED)

        def timestamp(value):
            return datetime.fromtimestamp(value, UTC) if value else None

        subscription.current_period_start = timestamp(
            data.get("current_period_start") or item.get("current_period_start")
        )
        subscription.current_period_end = timestamp(
            data.get("current_period_end") or item.get("current_period_end")
        )
        subscription.trial_start = timestamp(data.get("trial_start"))
        subscription.trial_end = timestamp(data.get("trial_end"))
        subscription.canceled_at = timestamp(data.get("canceled_at"))
        active = subscription.status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING}
        org.subscription_tier = SubscriptionTier(tier if active else "FREE")
        org.max_members, org.max_projects, org.max_storage_gb = LIMITS[tier if active else "FREE"]
        await self.db.flush()
        if kind.startswith("invoice."):
            invoice = await self.db.scalar(
                select(Invoice).where(Invoice.stripe_invoice_id == obj["id"])
            )
            if not invoice:
                invoice = Invoice(
                    org_id=org_id,
                    subscription_id=subscription.id,
                    stripe_invoice_id=obj["id"],
                    amount=0,
                )
                self.db.add(invoice)
            invoice.amount = Decimal(str(obj.get("amount_due", 0))) / 100
            invoice.currency = obj.get("currency", "usd").upper()
            invoice.status = {
                "invoice.paid": InvoiceStatus.PAID,
                "invoice.voided": InvoiceStatus.VOID,
            }.get(kind, InvoiceStatus.OPEN)
            invoice.paid_at = timestamp(obj.get("status_transitions", {}).get("paid_at"))
            invoice.due_date = timestamp(obj.get("due_date"))
        self.db.add(
            WebhookEventLog(
                id=event["id"],
                provider="stripe",
                event_type=kind,
                payload_json="{}",
                processed_successfully=True,
            )
        )
        await self.db.flush()
        return {"status": "processed"}
