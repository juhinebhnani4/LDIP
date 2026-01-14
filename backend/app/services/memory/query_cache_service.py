"""High-level Query Cache Service.

Story 7-5: Query Cache Redis Storage

Provides high-level caching operations that combine:
- Query normalization and hashing
- Cache repository operations
- Cache statistics and monitoring

This service is the primary interface for query caching.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from app.models.memory import CachedQueryResult
from app.services.memory.query_cache import (
    QueryCacheRepository,
    get_query_cache_repository,
)
from app.services.memory.query_normalizer import (
    QueryNormalizer,
    get_query_normalizer,
)
from app.services.memory.redis_keys import CACHE_TTL

logger = structlog.get_logger(__name__)


class QueryCacheService:
    """High-level service for query caching.

    Story 7-5: Task 4 - QueryCacheService with high-level methods.

    Combines query normalization with cache operations
    to provide a simple interface for caching query results.

    Features:
    - Check cache for existing results (AC #2)
    - Cache new results with auto-normalization (AC #1)
    - Invalidate cache on document upload (AC #4)
    - Cache statistics for monitoring
    """

    def __init__(
        self,
        cache_repository: QueryCacheRepository | None = None,
        query_normalizer: QueryNormalizer | None = None,
    ) -> None:
        """Initialize query cache service.

        Args:
            cache_repository: Optional repository (injected for testing).
            query_normalizer: Optional normalizer (injected for testing).
        """
        self._repository = cache_repository
        self._normalizer = query_normalizer

    def _ensure_repository(self) -> QueryCacheRepository:
        """Ensure cache repository is initialized."""
        if self._repository is None:
            self._repository = get_query_cache_repository()
        return self._repository

    def _ensure_normalizer(self) -> QueryNormalizer:
        """Ensure query normalizer is initialized."""
        if self._normalizer is None:
            self._normalizer = get_query_normalizer()
        return self._normalizer

    async def check_cache(
        self,
        matter_id: str,
        query: str,
    ) -> CachedQueryResult | None:
        """Check cache for existing query result.

        Story 7-5: Task 4.2 - Cache check.
        AC #2: Cached results returned in ~10ms.

        Normalizes the query and looks up the cache.

        Args:
            matter_id: Matter UUID for isolation.
            query: Original user query.

        Returns:
            CachedQueryResult if cache hit, None if miss.
        """
        normalizer = self._ensure_normalizer()
        repository = self._ensure_repository()

        # Normalize and hash
        query_hash = normalizer.hash(query)

        # Check cache
        result = await repository.get_cached_result(matter_id, query_hash)

        if result:
            logger.info(
                "query_cache_hit",
                matter_id=matter_id,
                query_hash=query_hash[:16] + "...",
                original_query=query[:50] + "..." if len(query) > 50 else query,
                cached_at=result.cached_at,
            )
        else:
            logger.debug(
                "query_cache_miss",
                matter_id=matter_id,
                query_hash=query_hash[:16] + "...",
            )

        return result

    async def cache_result(
        self,
        matter_id: str,
        query: str,
        result_summary: str,
        response_data: dict[str, Any],
        engine_used: str | None = None,
        findings_count: int = 0,
        confidence: float = 0.0,
    ) -> CachedQueryResult:
        """Cache a query result.

        Story 7-5: Task 4.3 - Cache result.
        AC #1: Results cached at cache:query:{matter_id}:{query_hash}.
        AC #3: 1-hour TTL.

        Normalizes the query, creates cached result, and stores it.

        Args:
            matter_id: Matter UUID for isolation.
            query: Original user query.
            result_summary: Brief summary of the result.
            response_data: Complete response payload.
            engine_used: Optional engine that processed query.
            findings_count: Number of findings in result.
            confidence: Overall confidence 0-100.

        Returns:
            The cached CachedQueryResult.
        """
        normalizer = self._ensure_normalizer()
        repository = self._ensure_repository()

        # Normalize and hash
        normalized, query_hash = normalizer.normalize_and_hash(query)

        # Calculate timestamps
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=CACHE_TTL)

        # Create cached result
        cached = CachedQueryResult(
            query_hash=query_hash,
            matter_id=matter_id,
            original_query=query,
            normalized_query=normalized,
            cached_at=now.isoformat(),
            expires_at=expires.isoformat(),
            result_summary=result_summary,
            engine_used=engine_used,
            findings_count=findings_count,
            confidence=confidence,
            response_data=response_data,
        )

        # Store in cache
        await repository.set_cached_result(cached)

        logger.info(
            "query_result_cached",
            matter_id=matter_id,
            query_hash=query_hash[:16] + "...",
            engine_used=engine_used,
            ttl_seconds=CACHE_TTL,
        )

        return cached

    async def invalidate_on_document_upload(
        self,
        matter_id: str,
    ) -> int:
        """Invalidate cache on document upload.

        Story 7-5: Task 4.4 - Document upload hook.
        AC #4: Invalidate all cache entries for matter on upload.

        This should be called when a new document is uploaded
        to ensure queries run fresh with new content.

        Args:
            matter_id: Matter UUID.

        Returns:
            Number of cache entries deleted.
        """
        repository = self._ensure_repository()

        deleted_count = await repository.invalidate_matter_cache(matter_id)

        logger.info(
            "cache_invalidated_on_upload",
            matter_id=matter_id,
            entries_deleted=deleted_count,
        )

        return deleted_count

    async def get_cache_stats(
        self,
        matter_id: str,
    ) -> dict[str, Any]:
        """Get cache statistics for monitoring.

        Story 7-5: Task 4.5 - Cache stats.

        Args:
            matter_id: Matter UUID.

        Returns:
            Dict with cache statistics.
        """
        repository = self._ensure_repository()

        stats = await repository.get_cache_stats(matter_id)

        return {
            "matter_id": matter_id,
            "cached_queries": stats.get("count", 0),
            "cache_keys": stats.get("keys", []),
            "ttl_seconds": CACHE_TTL,
        }

    async def delete_cached_query(
        self,
        matter_id: str,
        query: str,
    ) -> bool:
        """Delete a specific cached query result.

        Args:
            matter_id: Matter UUID.
            query: Original user query.

        Returns:
            True if deleted, False if not found.
        """
        normalizer = self._ensure_normalizer()
        repository = self._ensure_repository()

        query_hash = normalizer.hash(query)

        return await repository.delete_cached_result(matter_id, query_hash)


# =============================================================================
# Factory Functions
# =============================================================================

_query_cache_service: QueryCacheService | None = None


def get_query_cache_service(
    cache_repository: QueryCacheRepository | None = None,
    query_normalizer: QueryNormalizer | None = None,
) -> QueryCacheService:
    """Get or create QueryCacheService instance.

    Factory function following project pattern.

    Args:
        cache_repository: Optional repository for injection.
        query_normalizer: Optional normalizer for injection.

    Returns:
        QueryCacheService instance.
    """
    global _query_cache_service

    if _query_cache_service is None:
        _query_cache_service = QueryCacheService(cache_repository, query_normalizer)
    else:
        if cache_repository is not None and _query_cache_service._repository is None:
            _query_cache_service._repository = cache_repository
        if query_normalizer is not None and _query_cache_service._normalizer is None:
            _query_cache_service._normalizer = query_normalizer

    return _query_cache_service


def reset_query_cache_service() -> None:
    """Reset singleton (for testing)."""
    global _query_cache_service
    _query_cache_service = None
    logger.debug("query_cache_service_reset")
