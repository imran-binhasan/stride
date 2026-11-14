import hashlib
import hmac
import json
import time

import pytest
from src.config import settings


@pytest.fixture
def billing(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro")


async def deliver(client, event, secret="whsec_test", timestamp=None):
    timestamp = timestamp or int(time.time())
    body = json.dumps(event).encode()
    signature = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return await client.post(
        "/api/v1/billing/webhook",
        content=body,
        headers={
            "Stripe-Signature": f"t={timestamp},v1={signature}",
            "Content-Type": "application/json",
        },
    )


@pytest.mark.asyncio
async def test_subscription_requires_verified_provider_confirmation(
    client, make_tenant, billing, monkeypatch
):
    tenant = await make_tenant("billing-owner@example.com")
    sub = {
        "id": "sub_example",
        "customer": "cus_example",
        "metadata": {"org_id": tenant["org_id"]},
        "status": "active",
        "items": {"data": [{"price": {"id": "price_pro", "unit_amount": 2900, "currency": "usd"}}]},
    }
    calls = []

    async def stripe(method, path, data=None):
        calls.append((method, path, data))
        if path == "/checkout/sessions":
            return {"url": "https://checkout.stripe.com/example"}
        return sub

    monkeypatch.setattr("src.services.billing_service.stripe_request", stripe)
    checkout = await client.post(
        "/api/v1/billing/checkout", headers=tenant["headers"], json={"tier": "PRO"}
    )
    assert checkout.status_code == 200, checkout.text
    before = (await client.get("/api/v1/billing", headers=tenant["headers"])).json()
    assert before["tier"] == "FREE"
    event = {
        "id": "evt_test_billing",
        "type": "customer.subscription.updated",
        "data": {"object": sub},
    }
    assert (await deliver(client, event, secret="forged")).status_code == 401
    assert (await deliver(client, event, timestamp=int(time.time()) - 600)).status_code == 401
    result = await deliver(client, event)
    assert result.status_code == 200, result.text
    assert (await deliver(client, event)).json()["status"] == "duplicate"
    after = (await client.get("/api/v1/billing", headers=tenant["headers"])).json()
    assert after["tier"] == "PRO"
    assert after["subscription"]["status"] == "ACTIVE"
    assert after["max_members"] == 100
    sub["status"] = "canceled"
    event["id"] = "evt_test_cancel"
    assert (await deliver(client, event)).status_code == 200
    after = (await client.get("/api/v1/billing", headers=tenant["headers"])).json()
    assert after["tier"] == "FREE"
