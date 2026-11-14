from urllib.parse import parse_qs, urlparse

import pytest
from src.config import settings


@pytest.fixture
def oauth(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-secret")

    async def identity(*args):
        return "subject-123", "oauth-user@example.com", "OAuth User"

    monkeypatch.setattr("src.api.v1.oauth.fetch_identity", identity)


async def begin(client):
    response = await client.get("/api/v1/auth/oauth/google/start")
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    return query["state"][0]


@pytest.mark.asyncio
async def test_oauth_state_binding_and_one_use_ticket(client, oauth):
    state = await begin(client)
    callback = await client.get(
        "/api/v1/auth/oauth/google/callback", params={"state": state, "code": "valid-code"}
    )
    assert callback.status_code == 302, callback.text
    ticket = parse_qs(urlparse(callback.headers["location"]).fragment)["oauth_ticket"][0]
    exchange = await client.post("/api/v1/auth/oauth/exchange", json={"ticket": ticket})
    assert exchange.status_code == 200, exchange.text
    token = exchange.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
    assert me.json()["email"] == "oauth-user@example.com"
    assert (
        await client.post("/api/v1/auth/oauth/exchange", json={"ticket": ticket})
    ).status_code == 401
    assert (
        await client.get(
            "/api/v1/auth/oauth/google/callback", params={"state": state, "code": "replay"}
        )
    ).status_code == 401


@pytest.mark.asyncio
async def test_oauth_rejects_missing_browser_cookie(client, oauth):
    state = await begin(client)
    client.cookies.clear()
    result = await client.get(
        "/api/v1/auth/oauth/google/callback", params={"state": state, "code": "code"}
    )
    assert result.status_code == 401


@pytest.mark.asyncio
async def test_oauth_does_not_take_over_password_account(client, oauth, make_tenant):
    await make_tenant("oauth-user@example.com")
    state = await begin(client)
    result = await client.get(
        "/api/v1/auth/oauth/google/callback", params={"state": state, "code": "code"}
    )
    assert result.status_code == 409, result.text
