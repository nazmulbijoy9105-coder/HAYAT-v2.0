"""
HAYAT v2.0 — Redis Cache & Session Store
High-speed caching, rate limiting, and session management.
"""

from typing import Optional, Any
import json

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("hayat.db.redis")

_pool: Optional[redis.Redis] = None


async def get_redis_pool() -> redis.Redis:
    """Get or create Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = redis.from_url(
            str(settings.redis_url),
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            decode_responses=True,
        )
    return _pool


async def init_redis() -> None:
    """Initialize Redis connection."""
    pool = await get_redis_pool()
    await pool.ping()
    logger.info("redis_initialized")


async def close_redis() -> None:
    """Close Redis connection."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("redis_closed")


class CacheManager:
    """
    Redis-backed cache manager with TTL support.
    """

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        self.redis = await get_redis_pool()

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        if not self.redis:
            await self.connect()
        value = await self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """Set cached value with TTL."""
        if not self.redis:
            await self.connect()
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await self.redis.setex(key, ttl, serialized)

    async def delete(self, key: str) -> None:
        """Delete cached value."""
        if not self.redis:
            await self.connect()
        await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.redis:
            await self.connect()
        return await self.redis.exists(key) > 0

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter (for rate limiting)."""
        if not self.redis:
            await self.connect()
        return await self.redis.incrby(key, amount)

    async def expire(self, key: str, ttl: int) -> None:
        """Set expiration on key."""
        if not self.redis:
            await self.connect()
        await self.redis.expire(key, ttl)

    async def get_search_results(self, query_hash: str) -> Optional[Any]:
        """Get cached search results."""
        return await self.get(f"search:{query_hash}")

    async def cache_search_results(
        self, query_hash: str, results: Any, ttl: int = 300
    ) -> None:
        """Cache search results for 5 minutes."""
        await self.set(f"search:{query_hash}", results, ttl)

    async def get_document_cache(self, doc_id: str) -> Optional[Any]:
        """Get cached document."""
        return await self.get(f"doc:{doc_id}")

    async def cache_document(self, doc_id: str, document: Any, ttl: int = 1800) -> None:
        """Cache document for 30 minutes."""
        await self.set(f"doc:{doc_id}", document, ttl)
