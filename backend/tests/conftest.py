"""Pytest fixtures and test environment configuration."""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force test environment settings
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_USE_FAKE_IF_UNAVAILABLE"] = "true"

from src.core.database import get_db_session
from src.core.redis import close_redis, get_redis
from src.main import create_app
from src.models.base import Base

# Setup in-memory SQLite async test engine
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db_tables():
    """Create all tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await close_redis()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean transactional async database session for a single test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def redis_client():
    """Provide a clean FakeRedis client for testing."""
    client = await get_redis()
    await client.flushall()
    yield client


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTPX AsyncClient bound to the FastAPI application with test DB override."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest_asyncio.fixture
def make_tenant(client: AsyncClient):
    """Factory that provisions an isolated tenant (user+org+workspace+project+task).

    Returns a dict with tokens, auth headers (incl. X-Org-ID), and created ids.
    """

    async def _make(email: str, key: str = "PRJ") -> dict:
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Password12345!", "full_name": "Test User"},
        )
        data = reg.json()["data"]
        token = data["tokens"]["access_token"]
        refresh = data["tokens"]["refresh_token"]
        headers = {"Authorization": f"Bearer {token}"}

        org_id = (
            await client.post(
                "/api/v1/organizations", json={"name": f"Org {email}"}, headers=headers
            )
        ).json()["id"]
        headers["X-Org-ID"] = org_id

        ws_id = (
            await client.post(
                f"/api/v1/organizations/{org_id}/workspaces",
                json={"name": "Workspace"},
                headers=headers,
            )
        ).json()["id"]

        project = (
            await client.post(
                "/api/v1/projects",
                json={"workspace_id": ws_id, "name": "Project", "key": key},
                headers=headers,
            )
        ).json()

        task = (
            await client.post(
                "/api/v1/tasks",
                json={"project_id": project["id"], "title": "Task"},
                headers=headers,
            )
        ).json()

        return {
            "email": email,
            "token": token,
            "refresh_token": refresh,
            "headers": dict(headers),
            "user_id": data["user"]["id"],
            "org_id": org_id,
            "ws_id": ws_id,
            "project": project,
            "task": task,
        }

    return _make
