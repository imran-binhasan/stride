"""Unit tests for configuration, exceptions, database and redis layer."""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.core.exceptions import (
    ConflictException,
    EntityNotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from src.core.redis import RedisPubSubManager


@pytest.mark.asyncio
async def test_settings_loaded():
    """Verify application settings defaults."""
    assert settings.APP_NAME == "Stride"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.JWT_ALGORITHM == "HS256"


@pytest.mark.asyncio
async def test_database_session_executes_query(db_session: AsyncSession):
    """Verify async database connection and simple query execution."""
    result = await db_session.execute(text("SELECT 1 AS num"))
    row = result.mappings().one()
    assert row["num"] == 1


@pytest.mark.asyncio
async def test_redis_pubsub_manager(redis_client):
    """Verify Redis get/set/pubsub operations."""
    manager = RedisPubSubManager(redis_client)
    await manager.set_key("test_key", "test_val", expire_seconds=60)
    val = await manager.get_key("test_key")
    assert val == "test_val"

    await manager.delete_key("test_key")
    val_after_del = await manager.get_key("test_key")
    assert val_after_del is None


@pytest.mark.asyncio
async def test_domain_exceptions():
    """Verify domain exception attributes and status codes."""
    exc_404 = EntityNotFoundException("Project", "PRJ-001")
    assert exc_404.status_code == 404
    assert "PRJ-001" in exc_404.message

    exc_403 = PermissionDeniedException()
    assert exc_403.status_code == 403

    exc_409 = ConflictException("Duplicate slug")
    assert exc_409.status_code == 409

    exc_422 = ValidationException("Invalid status", details={"field": "status"})
    assert exc_422.status_code == 422
    assert exc_422.details == {"field": "status"}


@pytest.mark.asyncio
async def test_health_check_endpoint(client):
    """Verify /health endpoint returns 200 and healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "Stride"
