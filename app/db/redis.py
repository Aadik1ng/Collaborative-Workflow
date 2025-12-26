"""Redis connection and client management."""

from typing import Optional

import redis.asyncio as aioredis

from app.config import settings

# Global Redis client
redis_client: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    """Initialize Redis connection."""
    global redis_client

    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    # Test connection
    await redis_client.ping()


async def close_redis() -> None:
    """Close Redis connection."""
    global redis_client

    if redis_client:
        await redis_client.close()


def get_redis() -> aioredis.Redis:
    """Get Redis client instance."""
    if redis_client is None:
        raise RuntimeError("Redis is not initialized")
    return redis_client


async def get_redis_dependency() -> aioredis.Redis:
    """Dependency to get Redis client for FastAPI."""
    return get_redis()


# Cache utility functions
async def cache_get(key: str) -> Optional[str]:
    """Get value from cache."""
    client = get_redis()
    return await client.get(key)


async def cache_set(key: str, value: str, expire: int = 300) -> None:
    """Set value in cache with expiration in seconds."""
    client = get_redis()
    await client.setex(key, expire, value)


async def cache_delete(key: str) -> None:
    """Delete key from cache."""
    client = get_redis()
    await client.delete(key)


async def cache_invalidate_pattern(pattern: str) -> None:
    """Delete all keys matching pattern."""
    client = get_redis()
    async for key in client.scan_iter(match=pattern):
        await client.delete(key)
