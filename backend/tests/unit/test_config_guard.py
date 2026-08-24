"""Unit tests for production secret guard (C2) and WebSocket room authorization (H3)."""

import pytest
from pydantic import ValidationError
from src.config import Settings
from src.core.websockets import room_authorized


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production")


def test_production_accepts_overridden_secrets():
    s = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-very-strong-production-secret-key-32chars-min",
        GITHUB_WEBHOOK_SECRET="another-strong-webhook-secret-value",
        S3_SECRET_KEY="a-real-s3-secret",
    )
    assert s.ENVIRONMENT == "production"


def test_non_production_allows_defaults():
    s = Settings(ENVIRONMENT="development")
    assert s.ENVIRONMENT == "development"


def test_room_authorized_scopes_by_org():
    assert room_authorized("room:org:acme:project:p1", "acme") is True
    assert room_authorized("room:org:acme:project:p1", "evilcorp") is False
    assert room_authorized("", "acme") is False
    assert room_authorized("room:org:acme:project:p1", "") is False
