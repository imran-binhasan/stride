"""Fixed-window rate limiting backed by Redis, exposed as a FastAPI dependency."""

from fastapi import Request
from src.config import settings
from src.core.exceptions import RateLimitExceededException
from src.core.redis import get_redis


def rate_limit(max_requests: int, window_seconds: int, scope: str):
    """Dependency factory: allow at most `max_requests` per `window_seconds` per client IP.

    Disabled under the test environment so the suite is deterministic; exercised directly
    in a dedicated test. Fails open if Redis is unavailable (availability over strictness).
    """

    async def _dependency(request: Request) -> None:
        if settings.ENVIRONMENT == "test":
            return
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{scope}:{client_ip}"
        try:
            redis = await get_redis()
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, window_seconds)
        except Exception:
            return  # fail open on limiter infrastructure errors
        if current > max_requests:
            raise RateLimitExceededException(retry_after_seconds=window_seconds)

    return _dependency
