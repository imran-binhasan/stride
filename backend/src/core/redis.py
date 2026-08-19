"""Redis connection manager, caching, and Pub/Sub router."""

import logging
from typing import Any

import redis.asyncio as aioredis
from src.config import settings

logger = logging.getLogger("a3zen.redis")

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return a shared async Redis client instance, falling back to FakeRedis if configured."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        # Test connection
        await client.ping()
        _redis_client = client
        logger.info("Connected to Redis at %s", settings.REDIS_URL)
        return _redis_client
    except Exception as e:
        if settings.REDIS_USE_FAKE_IF_UNAVAILABLE or settings.ENVIRONMENT == "test":
            logger.warning(
                "Redis connection failed (%s), initializing FakeRedis for development/testing", e
            )
            import fakeredis.aioredis

            _redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
            return _redis_client
        raise


async def close_redis() -> None:
    """Close the shared Redis client connection safely."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
        finally:
            _redis_client = None


class RedisPubSubManager:
    """Manager for publishing and subscribing to real-time events over Redis."""

    def __init__(self, client: aioredis.Redis | None = None) -> None:
        self._client = client

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = await get_redis()
        return self._client

    async def publish(self, channel: str, message: str) -> int:
        """Publish a message string to a specified Redis channel."""
        client = await self._get_client()
        return await client.publish(channel, message)

    async def set_key(self, key: str, value: Any, expire_seconds: int | None = None) -> None:
        """Store key-value with optional TTL."""
        client = await self._get_client()
        if expire_seconds:
            await client.set(key, str(value), ex=expire_seconds)
        else:
            await client.set(key, str(value))

    async def get_key(self, key: str) -> str | None:
        """Get value by key."""
        client = await self._get_client()
        return await client.get(key)

    async def delete_key(self, key: str) -> None:
        """Delete key."""
        client = await self._get_client()
        await client.delete(key)
