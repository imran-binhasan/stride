"""FastAPI application factory and lifespan configuration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.api.v1.api_router import api_v1_router
from src.config import settings
from src.core.database import async_session_factory, init_db
from src.core.exceptions import register_exception_handlers
from src.core.observability import (
    RequestContextMiddleware,
    configure_logging,
    metrics_response,
)
from src.core.redis import close_redis, get_redis
from src.core.websockets import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events."""
    if "sqlite" in settings.DATABASE_URL:
        await init_db()
    await get_redis()
    await ws_manager.start()
    yield
    await ws_manager.stop()
    await close_redis()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    configure_logging()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    cors_origins = settings.BACKEND_CORS_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        # Credentials cannot be combined with a wildcard origin per the CORS spec.
        allow_credentials="*" not in cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    # Mount v1 API
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health/live", tags=["Health"])
    async def liveness():
        """Liveness probe — process is up (no dependency checks)."""
        return {"status": "alive"}

    @app.get("/health", tags=["Health"])
    @app.get("/health/ready", tags=["Health"])
    async def readiness():
        """Readiness probe — verifies database and Redis connectivity."""
        db_ok = True
        redis_ok = True
        try:
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
        try:
            redis = await get_redis()
            await redis.ping()
        except Exception:
            redis_ok = False

        healthy = db_ok and redis_ok
        payload = {
            "status": "healthy" if healthy else "degraded",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": {"database": db_ok, "redis": redis_ok},
        }
        return JSONResponse(status_code=200 if healthy else 503, content=payload)

    @app.get("/metrics", tags=["Observability"])
    async def metrics():
        """Prometheus metrics exposition endpoint."""
        return metrics_response()

    return app


app = create_app()
