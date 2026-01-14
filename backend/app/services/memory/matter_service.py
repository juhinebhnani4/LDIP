"""Matter Memory Service - High-level facade for matter-level memory.

Story 7-3: Matter Memory PostgreSQL JSONB Storage

Provides high-level orchestration for matter memory operations:
- Query history logging
- Timeline cache management
- Entity graph cache management
- Cache invalidation on document uploads

This service sits above MatterMemoryRepository and adds business logic.
"""

from datetime import UTC, datetime
from typing import Any

import structlog

from app.models.memory import (
    CachedEntity,
    EntityGraphCache,
    EntityRelationship,
    QueryHistory,
    QueryHistoryEntry,
    TimelineCache,
    TimelineCacheEntry,
)
from app.services.memory.matter import (
    MatterMemoryRepository,
    get_matter_memory_repository,
    is_cache_stale,
)

logger = structlog.get_logger(__name__)


class MatterMemoryService:
    """High-level service for matter memory operations.

    Story 7-3: Facade providing business logic over repository.

    This service:
    - Orchestrates repository calls with business logic
    - Handles cache staleness detection
    - Provides convenience methods for common patterns
    - Manages cache invalidation hooks
    """

    def __init__(
        self,
        repository: MatterMemoryRepository | None = None,
    ) -> None:
        """Initialize matter memory service.

        Args:
            repository: Optional repository instance (injected for testing).
        """
        self._repository = repository or get_matter_memory_repository()

    # =========================================================================
    # Query History Methods (AC #2)
    # =========================================================================

    async def log_query(
        self,
        matter_id: str,
        query_id: str,
        query_text: str,
        asked_by: str,
        *,
        normalized_query: str | None = None,
        response_summary: str = "",
        engines_used: list[str] | None = None,
        confidence: float | None = None,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
    ) -> str:
        """Log a query to matter history.

        Story 7-3: Convenience method for query logging.
        Creates QueryHistoryEntry and appends to history.

        Args:
            matter_id: Matter UUID.
            query_id: Unique query UUID.
            query_text: Original query text.
            asked_by: User UUID who asked.
            normalized_query: Optional normalized query for cache.
            response_summary: Brief response summary.
            engines_used: List of engines used.
            confidence: Response confidence 0-100.
            tokens_used: Total tokens consumed.
            cost_usd: Total cost in USD.

        Returns:
            Record UUID from database.
        """
        entry = QueryHistoryEntry(
            query_id=query_id,
            query_text=query_text,
            normalized_query=normalized_query,
            asked_by=asked_by,
            asked_at=datetime.now(UTC).isoformat(),
            response_summary=response_summary,
            engines_used=engines_used or [],
            confidence=confidence,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )

        result = await self._repository.append_query(matter_id, entry)

        logger.info(
            "query_logged",
            matter_id=matter_id,
            query_id=query_id,
            engines=engines_used,
        )

        return result

    async def get_query_history(
        self,
        matter_id: str,
        limit: int = 100,
    ) -> QueryHistory:
        """Get query history for a matter.

        Args:
            matter_id: Matter UUID.
            limit: Maximum entries to return.

        Returns:
            QueryHistory with entries.
        """
        return await self._repository.get_query_history(matter_id, limit)

    async def mark_query_verified(
        self,
        matter_id: str,
        query_id: str,
        verified_by: str,
    ) -> bool:
        """Mark a query as verified by attorney.

        Story 7-3: Updates verification status in query history.

        Note: This requires updating the specific entry in the JSONB array.
        For simplicity, we read-modify-write the entire history.
        Consider optimizing with a DB function if this becomes a bottleneck.

        Args:
            matter_id: Matter UUID.
            query_id: Query UUID to verify.
            verified_by: User UUID who verified.

        Returns:
            True if found and updated, False if not found.
        """
        history = await self._repository.get_query_history(matter_id, limit=1000)

        found = False
        for entry in history.entries:
            if entry.query_id == query_id:
                entry.verified = True
                entry.verified_by = verified_by
                entry.verified_at = datetime.now(UTC).isoformat()
                found = True
                break

        if not found:
            logger.warning(
                "query_not_found_for_verification",
                matter_id=matter_id,
                query_id=query_id,
            )
            return False

        # Update the full history (upsert)
        await self._repository.set_memory(
            matter_id,
            "query_history",
            {"entries": [e.model_dump(mode="json") for e in history.entries]},
        )

        logger.info(
            "query_marked_verified",
            matter_id=matter_id,
            query_id=query_id,
            verified_by=verified_by,
        )

        return True

    # =========================================================================
    # Timeline Cache Methods (AC #3)
    # =========================================================================

    async def get_or_build_timeline(
        self,
        matter_id: str,
        last_document_upload: str | None = None,
        *,
        builder_fn: Any | None = None,
    ) -> TimelineCache | None:
        """Get timeline cache, building if stale or missing.

        Story 7-3: Check cache, rebuild if stale/missing.

        Args:
            matter_id: Matter UUID.
            last_document_upload: Latest doc upload timestamp for staleness.
            builder_fn: Optional async function to build timeline.
                        Should return list of TimelineCacheEntry.

        Returns:
            TimelineCache if available, None if no cache and no builder.
        """
        cache = await self._repository.get_timeline_cache(matter_id)

        # Check if cache is valid
        if cache and not is_cache_stale(cache.cached_at, last_document_upload):
            logger.debug(
                "timeline_cache_hit",
                matter_id=matter_id,
                event_count=cache.event_count,
            )
            return cache

        # Cache is stale or missing
        if builder_fn is None:
            logger.debug(
                "timeline_cache_miss_no_builder",
                matter_id=matter_id,
            )
            return None

        # Build new cache
        logger.info(
            "timeline_cache_building",
            matter_id=matter_id,
            reason="stale" if cache else "missing",
        )

        events: list[TimelineCacheEntry] = await builder_fn(matter_id)

        # Sort events by date
        sorted_events = sorted(events, key=lambda e: e.event_date)

        new_cache = TimelineCache(
            cached_at=datetime.now(UTC).isoformat(),
            last_document_upload=last_document_upload,
            version=(cache.version + 1) if cache else 1,
            events=sorted_events,
            date_range_start=sorted_events[0].event_date if sorted_events else None,
            date_range_end=sorted_events[-1].event_date if sorted_events else None,
            event_count=len(sorted_events),
        )

        await self._repository.set_timeline_cache(matter_id, new_cache)

        logger.info(
            "timeline_cache_built",
            matter_id=matter_id,
            event_count=new_cache.event_count,
        )

        return new_cache

    async def set_timeline_cache(
        self,
        matter_id: str,
        events: list[TimelineCacheEntry],
        last_document_upload: str | None = None,
    ) -> TimelineCache:
        """Set timeline cache with provided events.

        Args:
            matter_id: Matter UUID.
            events: Timeline events to cache.
            last_document_upload: Latest doc upload timestamp.

        Returns:
            Created TimelineCache.
        """
        # Get current version if exists
        current = await self._repository.get_timeline_cache(matter_id)
        version = (current.version + 1) if current else 1

        # Sort events by date
        sorted_events = sorted(events, key=lambda e: e.event_date)

        cache = TimelineCache(
            cached_at=datetime.now(UTC).isoformat(),
            last_document_upload=last_document_upload,
            version=version,
            events=sorted_events,
            date_range_start=sorted_events[0].event_date if sorted_events else None,
            date_range_end=sorted_events[-1].event_date if sorted_events else None,
            event_count=len(sorted_events),
        )

        await self._repository.set_timeline_cache(matter_id, cache)

        return cache

    # =========================================================================
    # Entity Graph Cache Methods (AC #4)
    # =========================================================================

    async def get_or_build_entity_graph(
        self,
        matter_id: str,
        last_document_upload: str | None = None,
        *,
        builder_fn: Any | None = None,
    ) -> EntityGraphCache | None:
        """Get entity graph cache, building if stale or missing.

        Story 7-3: Check cache, rebuild if stale/missing.

        Args:
            matter_id: Matter UUID.
            last_document_upload: Latest doc upload timestamp for staleness.
            builder_fn: Optional async function to build graph.
                        Should return tuple (entities_dict, relationships_list).

        Returns:
            EntityGraphCache if available, None if no cache and no builder.
        """
        cache = await self._repository.get_entity_graph_cache(matter_id)

        # Check if cache is valid
        if cache and not is_cache_stale(cache.cached_at, last_document_upload):
            logger.debug(
                "entity_graph_cache_hit",
                matter_id=matter_id,
                entity_count=cache.entity_count,
            )
            return cache

        # Cache is stale or missing
        if builder_fn is None:
            logger.debug(
                "entity_graph_cache_miss_no_builder",
                matter_id=matter_id,
            )
            return None

        # Build new cache
        logger.info(
            "entity_graph_cache_building",
            matter_id=matter_id,
            reason="stale" if cache else "missing",
        )

        entities, relationships = await builder_fn(matter_id)

        new_cache = EntityGraphCache(
            cached_at=datetime.now(UTC).isoformat(),
            last_document_upload=last_document_upload,
            version=(cache.version + 1) if cache else 1,
            entities=entities,
            relationships=relationships,
            entity_count=len(entities),
            relationship_count=len(relationships),
        )

        await self._repository.set_entity_graph_cache(matter_id, new_cache)

        logger.info(
            "entity_graph_cache_built",
            matter_id=matter_id,
            entity_count=new_cache.entity_count,
            relationship_count=new_cache.relationship_count,
        )

        return new_cache

    async def set_entity_graph_cache(
        self,
        matter_id: str,
        entities: dict[str, CachedEntity],
        relationships: list[EntityRelationship],
        last_document_upload: str | None = None,
    ) -> EntityGraphCache:
        """Set entity graph cache with provided data.

        Args:
            matter_id: Matter UUID.
            entities: Map of entity_id -> CachedEntity.
            relationships: List of EntityRelationship.
            last_document_upload: Latest doc upload timestamp.

        Returns:
            Created EntityGraphCache.
        """
        # Get current version if exists
        current = await self._repository.get_entity_graph_cache(matter_id)
        version = (current.version + 1) if current else 1

        cache = EntityGraphCache(
            cached_at=datetime.now(UTC).isoformat(),
            last_document_upload=last_document_upload,
            version=version,
            entities=entities,
            relationships=relationships,
            entity_count=len(entities),
            relationship_count=len(relationships),
        )

        await self._repository.set_entity_graph_cache(matter_id, cache)

        return cache

    # =========================================================================
    # Cache Invalidation (Task 4)
    # =========================================================================

    async def invalidate_matter_caches(
        self,
        matter_id: str,
    ) -> dict[str, bool]:
        """Invalidate all matter caches (timeline and entity graph).

        Story 7-3: Task 4.1 - Called when documents are uploaded.

        Args:
            matter_id: Matter UUID.

        Returns:
            Dict with deletion status for each cache type.
        """
        timeline_deleted = await self._repository.invalidate_timeline_cache(matter_id)
        entity_graph_deleted = await self._repository.invalidate_entity_graph_cache(
            matter_id
        )

        logger.info(
            "matter_caches_invalidated",
            matter_id=matter_id,
            timeline_deleted=timeline_deleted,
            entity_graph_deleted=entity_graph_deleted,
        )

        return {
            "timeline_cache": timeline_deleted,
            "entity_graph_cache": entity_graph_deleted,
        }

    async def is_timeline_stale(
        self,
        matter_id: str,
        last_document_upload: str,
    ) -> bool:
        """Check if timeline cache is stale.

        Args:
            matter_id: Matter UUID.
            last_document_upload: Latest doc upload timestamp.

        Returns:
            True if cache is stale or missing.
        """
        cache = await self._repository.get_timeline_cache(matter_id)
        if not cache:
            return True
        return is_cache_stale(cache.cached_at, last_document_upload)

    async def is_entity_graph_stale(
        self,
        matter_id: str,
        last_document_upload: str,
    ) -> bool:
        """Check if entity graph cache is stale.

        Args:
            matter_id: Matter UUID.
            last_document_upload: Latest doc upload timestamp.

        Returns:
            True if cache is stale or missing.
        """
        cache = await self._repository.get_entity_graph_cache(matter_id)
        if not cache:
            return True
        return is_cache_stale(cache.cached_at, last_document_upload)


# =============================================================================
# Factory Function
# =============================================================================

_matter_memory_service: MatterMemoryService | None = None


def get_matter_memory_service(
    repository: MatterMemoryRepository | None = None,
) -> MatterMemoryService:
    """Get or create MatterMemoryService instance.

    Factory function following project pattern.

    Args:
        repository: Optional repository for injection.

    Returns:
        MatterMemoryService instance.
    """
    global _matter_memory_service

    if _matter_memory_service is None:
        _matter_memory_service = MatterMemoryService(repository)

    return _matter_memory_service


def reset_matter_memory_service() -> None:
    """Reset singleton (for testing)."""
    global _matter_memory_service
    _matter_memory_service = None
    logger.debug("matter_memory_service_reset")
