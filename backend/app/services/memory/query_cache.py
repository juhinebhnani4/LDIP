"""Query Cache Repository for Redis CRUD operations.

Story 7-5: Query Cache Redis Storage

Manages cached query results in Redis with:
- 1-hour TTL (automatic expiration)
- Matter-isolated keys (cache:query:{matter_id}:{query_hash})
- Bulk invalidation on document upload

CRITICAL: All cache data is scoped by matter_id for Layer 3 isolation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from app.models.memory import CachedQueryResult
from app.services.memory.redis_client import get_redis_client
from app.services.memory.redis_keys import (
    CACHE_TTL,
    cache_key,
    cache_pattern,
    validate_key_access,
)

logger = structlog.get_logger(__name__)


class QueryCacheRepository:
    """Repository for query cache Redis operations.

    Story 7-5: Task 2 - Redis CRUD for cached query results.

    Features:
    - Store cached results with 1-hour TTL (AC #3)
    - Retrieve cached results by query hash (AC #2)
    - Delete single cache entry
    - Bulk invalidation for matter (AC #4)
    - Matter isolation via key prefix

    Key format: cache:query:{matter_id}:{query_hash}
    """

    def __init__(self, redis_client: Any = None) -> None:
        """Initialize query cache repository.

        Args:
            redis_client: Optional Redis client (injected for testing).
        """
        self._redis = redis_client

    async def _ensure_client(self) -> None:
        """Ensure Redis client is initialized."""
        if self._redis is None:
            self._redis = await get_redis_client()

    async def get_cached_result(
        self,
        matter_id: str,
        query_hash: str,
    ) -> CachedQueryResult | None:
        """Retrieve cached query result by hash.

        Story 7-5: Task 2.2 - Get cached result.
        AC #2: Cached results returned in ~10ms.

        Args:
            matter_id: Matter UUID for isolation.
            query_hash: SHA256 hash of normalized query.

        Returns:
            CachedQueryResult if found, None otherwise.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        await self._ensure_client()

        key = cache_key(matter_id, query_hash)

        # Defense-in-depth: validate key belongs to requested matter
        if not validate_key_access(key, matter_id):
            logger.error(
                "cache_key_validation_failed",
                key=key,
                matter_id=matter_id,
            )
            raise ValueError("Cache key does not match requested matter")

        try:
            data = await self._redis.get(key)
        except Exception as e:
            logger.error(
                "redis_get_cached_result_failed",
                matter_id=matter_id,
                query_hash=query_hash[:16] + "...",  # Truncate for logging
                error=str(e),
            )
            raise RuntimeError(f"Failed to get cached result from Redis: {e}") from e

        if data is None:
            logger.debug(
                "cache_miss",
                matter_id=matter_id,
                query_hash=query_hash[:16] + "...",
            )
            return None

        try:
            result = CachedQueryResult.model_validate_json(data)
            logger.debug(
                "cache_hit",
                matter_id=matter_id,
                query_hash=query_hash[:16] + "...",
                cached_at=result.cached_at,
            )
            return result
        except Exception as e:
            logger.error(
                "cache_parse_failed",
                matter_id=matter_id,
                query_hash=query_hash[:16] + "...",
                error=str(e),
            )
            # Corrupt cache entry - delete it
            await self.delete_cached_result(matter_id, query_hash)
            return None

    async def set_cached_result(
        self,
        result: CachedQueryResult,
    ) -> None:
        """Store cached query result with TTL.

        Story 7-5: Task 2.3 - Store with 1-hour TTL.
        AC #1: Results cached at cache:query:{matter_id}:{query_hash}.
        AC #3: 1-hour TTL automatic expiration.

        Args:
            result: CachedQueryResult to store.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        await self._ensure_client()

        key = cache_key(result.matter_id, result.query_hash)

        try:
            await self._redis.setex(
                key,
                CACHE_TTL,  # 1 hour in seconds
                result.model_dump_json(),
            )
        except Exception as e:
            logger.error(
                "redis_set_cached_result_failed",
                matter_id=result.matter_id,
                query_hash=result.query_hash[:16] + "...",
                error=str(e),
            )
            raise RuntimeError(f"Failed to store cached result in Redis: {e}") from e

        logger.info(
            "result_cached",
            matter_id=result.matter_id,
            query_hash=result.query_hash[:16] + "...",
            ttl_seconds=CACHE_TTL,
            engine_used=result.engine_used,
        )

    async def delete_cached_result(
        self,
        matter_id: str,
        query_hash: str,
    ) -> bool:
        """Delete a single cached result.

        Story 7-5: Task 2.4 - Delete single entry.

        Args:
            matter_id: Matter UUID.
            query_hash: SHA256 hash of normalized query.

        Returns:
            True if entry was deleted, False if not found.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        await self._ensure_client()

        key = cache_key(matter_id, query_hash)

        try:
            deleted = await self._redis.delete(key)
        except Exception as e:
            logger.error(
                "redis_delete_cached_result_failed",
                matter_id=matter_id,
                query_hash=query_hash[:16] + "...",
                error=str(e),
            )
            raise RuntimeError(f"Failed to delete cached result from Redis: {e}") from e

        logger.info(
            "cache_entry_deleted",
            matter_id=matter_id,
            query_hash=query_hash[:16] + "...",
            deleted=deleted > 0,
        )

        return deleted > 0

    async def invalidate_matter_cache(
        self,
        matter_id: str,
    ) -> int:
        """Delete all cache entries for a matter.

        Story 7-5: Task 2.5 - Bulk invalidation.
        AC #4: Invalidate on document upload.

        Uses SCAN to find and delete all matching keys safely
        (doesn't block like KEYS command).

        Args:
            matter_id: Matter UUID.

        Returns:
            Number of keys deleted.

        Raises:
            RuntimeError: If Redis operation fails.
        """
        await self._ensure_client()

        pattern = cache_pattern(matter_id)  # "cache:query:{matter_id}:*"
        deleted_count = 0

        try:
            # Use SCAN for safe iteration (non-blocking)
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._redis.delete(*keys)
                    deleted_count += len(keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error(
                "redis_invalidate_matter_cache_failed",
                matter_id=matter_id,
                deleted_before_error=deleted_count,
                error=str(e),
            )
            raise RuntimeError(f"Failed to invalidate matter cache: {e}") from e

        logger.info(
            "matter_cache_invalidated",
            matter_id=matter_id,
            keys_deleted=deleted_count,
        )

        return deleted_count

    async def get_cache_stats(
        self,
        matter_id: str,
    ) -> dict[str, Any]:
        """Get cache statistics for a matter.

        Returns count and estimated size of cached entries.
        Useful for monitoring and debugging.

        Args:
            matter_id: Matter UUID.

        Returns:
            Dict with 'count', 'keys' list.
        """
        await self._ensure_client()

        pattern = cache_pattern(matter_id)
        keys: list[str] = []

        try:
            cursor = 0
            while True:
                cursor, batch = await self._redis.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error(
                "redis_get_cache_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return {"count": 0, "keys": [], "error": str(e)}

        return {
            "count": len(keys),
            "keys": keys,
        }


# =============================================================================
# Factory Functions
# =============================================================================

_query_cache_repository: QueryCacheRepository | None = None


def get_query_cache_repository(
    redis_client: Any = None,
) -> QueryCacheRepository:
    """Get or create QueryCacheRepository instance.

    Factory function following project pattern.

    Args:
        redis_client: Optional Redis client for injection.

    Returns:
        QueryCacheRepository instance.
    """
    global _query_cache_repository

    if _query_cache_repository is None:
        _query_cache_repository = QueryCacheRepository(redis_client)
    elif redis_client is not None and _query_cache_repository._redis is None:
        _query_cache_repository._redis = redis_client

    return _query_cache_repository


def reset_query_cache_repository() -> None:
    """Reset singleton (for testing)."""
    global _query_cache_repository
    _query_cache_repository = None
    logger.debug("query_cache_repository_reset")
