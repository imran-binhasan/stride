"""GitHub webhook HMAC signature enforcement outside the test environment (H2)."""

import hashlib
import hmac
import json

import pytest
from httpx import AsyncClient
from src import config as config_module


@pytest.fixture
def production_webhook(monkeypatch):
    """Simulate a non-test environment so signature verification is enforced."""
    monkeypatch.setattr(config_module.settings, "ENVIRONMENT", "production")
    # Also patch the reference imported into the integrations router module.
    from src.api.v1 import integrations as integrations_module

    monkeypatch.setattr(integrations_module.settings, "ENVIRONMENT", "production")
    return config_module.settings.GITHUB_WEBHOOK_SECRET


@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(client: AsyncClient, production_webhook):
    body = json.dumps({"repository": {"name": "x", "owner": {"login": "y"}}}).encode()
    r = await client.post(
        "/api/v1/integrations/github/webhook",
        content=body,
        headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_valid_signature(client: AsyncClient, production_webhook):
    secret = production_webhook
    body = json.dumps({"repository": {"name": "x", "owner": {"login": "y"}}, "commits": []}).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    r = await client.post(
        "/api/v1/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 200
