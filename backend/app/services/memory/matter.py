"""Matter Memory Repository for persistent matter-level storage.

Story 7-2: Session TTL and Context Restoration
Story 7-3: Matter Memory PostgreSQL JSONB Storage

Manages matter-level memory storage in PostgreSQL matter_memory table:
- Archived sessions (Story 7-2)
- Query history (Story 7-3)
- Timeline cache (Story 7-3)
- Entity graph cache (Story 7-3)

Table: matter_memory with memory_type discriminator
"""

from datetime import datetime
from typing import Any

import structlog
from pydantic import ValidationError

from app.models.memory import (
    ArchivedSession,
    EntityGraphCache,
    QueryHistory,
    QueryHistoryEntry,
    TimelineCache,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)

# =============================================================================
# Memory Type Constants
# =============================================================================

ARCHIVED_SESSION_TYPE = "archived_session"
QUERY_HISTORY_TYPE = "query_history"
TIMELINE_CACHE_TYPE = "timeline_cache"
ENTITY_GRAPH_TYPE = "entity_graph"

# Default query limits
DEFAULT_ARCHIVE_QUERY_LIMIT = 10
DEFAULT_QUERY_HISTORY_LIMIT = 100


# =============================================================================
# Cache Staleness Utility (Story 7-3)
# =============================================================================


def is_cache_stale(
    cache_timestamp: str | None,
    last_doc_upload: str | None,
) -> bool:
    """Check if cache is stale (doc uploaded after cache created).

    Story 7-3: Determines if timeline or entity graph cache needs rebuild.

    Args:
        cache_timestamp: When cache was created (ISO8601).
        last_doc_upload: When last document was uploaded (ISO8601).

    Returns:
        True if cache is stale (should rebuild), False otherwise.
    """
    if not cache_timestamp:
        return True  # No cache = stale

    if not last_doc_upload:
        return False  # No docs uploaded = not stale

    # Compare timestamps
    try:
        cache_time = datetime.fromisoformat(cache_timestamp.replace("Z", "+00:00"))
        upload_time = datetime.fromisoformat(last_doc_upload.replace("Z", "+00:00"))
        return upload_time > cache_time
    except (ValueError, TypeError) as e:
        logger.warning(
            "cache_staleness_check_failed",
            cache_timestamp=cache_timestamp,
            last_doc_upload=last_doc_upload,
            error=str(e),
        )
        return True  # Assume stale on parse error


class MatterMemoryRepository:
    """Repository for matter memory operations.

    Story 7-2: Manages archived session storage and retrieval.

    Uses Supabase PostgreSQL with JSONB storage for flexible data.
    RLS policies ensure matter isolation.

    Note: Methods are marked async for interface consistency with other services,
    though Supabase Python client operations are synchronous. This allows for
    future migration to async client without breaking callers.
    """

    def __init__(self, supabase_client: Any = None) -> None:
        """Initialize matter memory repository.

        Args:
            supabase_client: Optional Supabase client (injected for testing).
        """
        self._supabase = supabase_client
        self._initialized = False

    def _ensure_client(self) -> None:
        """Ensure Supabase client is initialized."""
        if self._supabase is None:
            self._supabase = get_supabase_client()
            if self._supabase is None:
                raise RuntimeError("Supabase client not configured")
        self._initialized = True

    async def save_archived_session(
        self,
        archive: ArchivedSession,
    ) -> str:
        """Save an archived session to matter memory.

        Story 7-2: Task 6.2 - Stores archived session as JSONB.

        Args:
            archive: ArchivedSession to save.

        Returns:
            UUID of the created record.

        Raises:
            RuntimeError: If database operation fails.
        """
        self._ensure_client()

        # Serialize to dict (converts nested Pydantic models)
        data = archive.model_dump(mode="json")

        try:
            result = (
                self._supabase.table("matter_memory")
                .insert(
                    {
                        "matter_id": archive.matter_id,
                        "memory_type": ARCHIVED_SESSION_TYPE,
                        "data": data,
                    }
                )
                .execute()
            )
        except Exception as e:
            logger.error(
                "save_archived_session_failed",
                session_id=archive.session_id,
                matter_id=archive.matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to save archived session: {e}") from e

        record_id = result.data[0]["id"] if result.data else None

        logger.info(
            "archived_session_saved",
            record_id=record_id,
            session_id=archive.session_id,
            matter_id=archive.matter_id,
            user_id=archive.user_id,
        )

        return record_id

    async def get_latest_archived_session(
        self,
        matter_id: str,
        user_id: str,
    ) -> ArchivedSession | None:
        """Get the most recent archived session for a matter/user.

        Story 7-2: Task 6.3 - Retrieves latest archived session for restoration.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.

        Returns:
            ArchivedSession if found, None otherwise.
        """
        self._ensure_client()

        try:
            # Query for archived sessions with user_id filter in JSONB
            # Using data->>user_id filter for defense-in-depth (in addition to RLS)
            result = (
                self._supabase.table("matter_memory")
                .select("data")
                .eq("matter_id", matter_id)
                .eq("memory_type", ARCHIVED_SESSION_TYPE)
                .eq("data->>user_id", user_id)  # Filter by user_id in JSONB
                .order("created_at", desc=True)
                .limit(1)  # Only need the latest one
                .execute()
            )
        except Exception as e:
            logger.error(
                "get_latest_archived_session_failed",
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get archived session: {e}") from e

        if not result.data:
            return None

        # Parse the first (and only) result
        data = result.data[0].get("data", {})
        try:
            return ArchivedSession.model_validate(data)
        except ValidationError as e:
            logger.warning(
                "archived_session_validation_failed",
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )
            return None

    async def get_archived_sessions(
        self,
        matter_id: str,
        user_id: str | None = None,
        limit: int = DEFAULT_ARCHIVE_QUERY_LIMIT,
        offset: int = 0,
    ) -> list[ArchivedSession]:
        """Get archived sessions for a matter with pagination.

        Story 7-2: Task 6.4 - Lists archived sessions.

        Args:
            matter_id: Matter UUID.
            user_id: Optional user UUID to filter by (defense-in-depth).
            limit: Maximum records to return.
            offset: Records to skip.

        Returns:
            List of ArchivedSession objects.
        """
        self._ensure_client()

        try:
            query = (
                self._supabase.table("matter_memory")
                .select("data")
                .eq("matter_id", matter_id)
                .eq("memory_type", ARCHIVED_SESSION_TYPE)
            )

            # Filter by user_id in JSONB if provided (defense-in-depth)
            if user_id:
                query = query.eq("data->>user_id", user_id)

            query = query.order("created_at", desc=True).range(
                offset, offset + limit - 1
            )

            result = query.execute()
        except Exception as e:
            logger.error(
                "get_archived_sessions_failed",
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get archived sessions: {e}") from e

        sessions: list[ArchivedSession] = []

        for record in result.data or []:
            data = record.get("data", {})
            try:
                sessions.append(ArchivedSession.model_validate(data))
            except ValidationError as e:
                logger.warning(
                    "archived_session_validation_failed",
                    matter_id=matter_id,
                    error=str(e),
                )
                continue

        return sessions

    # =========================================================================
    # Story 7-3: Query History Methods
    # =========================================================================

    async def get_query_history(
        self,
        matter_id: str,
        limit: int = DEFAULT_QUERY_HISTORY_LIMIT,
    ) -> QueryHistory:
        """Get query history for a matter.

        Story 7-3: AC #2 - Retrieve append-only query records.

        Args:
            matter_id: Matter UUID.
            limit: Maximum entries to return (newest last).

        Returns:
            QueryHistory with entries.
        """
        self._ensure_client()

        try:
            result = (
                self._supabase.table("matter_memory")
                .select("data")
                .eq("matter_id", matter_id)
                .eq("memory_type", QUERY_HISTORY_TYPE)
                .maybe_single()
                .execute()
            )
        except Exception as e:
            logger.error(
                "get_query_history_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get query history: {e}") from e

        if not result.data:
            return QueryHistory(entries=[])

        data = result.data.get("data", {})
        entries = data.get("entries", [])

        # Return most recent entries up to limit
        return QueryHistory(entries=entries[-limit:])

    async def append_query(
        self,
        matter_id: str,
        entry: QueryHistoryEntry,
    ) -> str:
        """Append a query entry to history (append-only).

        Story 7-3: AC #2 - Uses DB function for atomic append.

        Args:
            matter_id: Matter UUID.
            entry: Query entry to append.

        Returns:
            Record UUID.

        Raises:
            RuntimeError: If database operation fails.
        """
        self._ensure_client()

        try:
            # Use append_to_matter_memory DB function for atomic append
            result = self._supabase.rpc(
                "append_to_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": QUERY_HISTORY_TYPE,
                    "p_key": "entries",
                    "p_item": entry.model_dump(mode="json"),
                },
            ).execute()
        except Exception as e:
            logger.error(
                "append_query_failed",
                matter_id=matter_id,
                query_id=entry.query_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to append query: {e}") from e

        logger.info(
            "query_appended",
            matter_id=matter_id,
            query_id=entry.query_id,
        )

        return result.data

    # =========================================================================
    # Story 7-3: Timeline Cache Methods
    # =========================================================================

    async def get_timeline_cache(
        self,
        matter_id: str,
    ) -> TimelineCache | None:
        """Get cached timeline for a matter.

        Story 7-3: AC #3 - Retrieve pre-built timeline.

        Args:
            matter_id: Matter UUID.

        Returns:
            TimelineCache if exists, None otherwise.
        """
        self._ensure_client()

        try:
            result = (
                self._supabase.table("matter_memory")
                .select("data")
                .eq("matter_id", matter_id)
                .eq("memory_type", TIMELINE_CACHE_TYPE)
                .maybe_single()
                .execute()
            )
        except Exception as e:
            logger.error(
                "get_timeline_cache_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get timeline cache: {e}") from e

        if not result.data:
            return None

        data = result.data.get("data", {})

        try:
            return TimelineCache.model_validate(data)
        except ValidationError as e:
            logger.warning(
                "timeline_cache_validation_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return None

    async def set_timeline_cache(
        self,
        matter_id: str,
        cache: TimelineCache,
    ) -> str:
        """Set/update timeline cache for a matter.

        Story 7-3: AC #3 - Store pre-built timeline.

        Args:
            matter_id: Matter UUID.
            cache: Timeline cache to store.

        Returns:
            Record UUID.

        Raises:
            RuntimeError: If database operation fails.
        """
        self._ensure_client()

        try:
            # Use upsert_matter_memory DB function
            result = self._supabase.rpc(
                "upsert_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": TIMELINE_CACHE_TYPE,
                    "p_data": cache.model_dump(mode="json"),
                },
            ).execute()
        except Exception as e:
            logger.error(
                "set_timeline_cache_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to set timeline cache: {e}") from e

        logger.info(
            "timeline_cache_set",
            matter_id=matter_id,
            event_count=cache.event_count,
        )

        return result.data

    async def invalidate_timeline_cache(
        self,
        matter_id: str,
    ) -> bool:
        """Invalidate (delete) timeline cache.

        Story 7-3: Called when new documents uploaded.

        Args:
            matter_id: Matter UUID.

        Returns:
            True if deleted, False if not found.
        """
        self._ensure_client()

        try:
            result = (
                self._supabase.table("matter_memory")
                .delete()
                .eq("matter_id", matter_id)
                .eq("memory_type", TIMELINE_CACHE_TYPE)
                .execute()
            )
        except Exception as e:
            logger.error(
                "invalidate_timeline_cache_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to invalidate timeline cache: {e}") from e

        deleted = len(result.data) > 0 if result.data else False

        logger.info(
            "timeline_cache_invalidated",
            matter_id=matter_id,
            deleted=deleted,
        )

        return deleted

    # =========================================================================
    # Story 7-3: Entity Graph Cache Methods
    # =========================================================================

    async def get_entity_graph_cache(
        self,
        matter_id: str,
    ) -> EntityGraphCache | None:
        """Get cached entity graph for a matter.

        Story 7-3: AC #4 - Retrieve pre-built MIG graph.

        Args:
            matter_id: Matter UUID.

        Returns:
            EntityGraphCache if exists, None otherwise.
        """
        self._ensure_client()

        try:
            result = (
                self._supabase.table("matter_memory")
                .select("data")
                .eq("matter_id", matter_id)
                .eq("memory_type", ENTITY_GRAPH_TYPE)
                .maybe_single()
                .execute()
            )
        except Exception as e:
            logger.error(
                "get_entity_graph_cache_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get entity graph cache: {e}") from e

        if not result.data:
            return None

        data = result.data.get("data", {})

        try:
            return EntityGraphCache.model_validate(data)
        except ValidationError as e:
            logger.warning(
                "entity_graph_cache_validation_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return None

    async def set_entity_graph_cache(
        self,
        matter_id: str,
        cache: EntityGraphCache,
    ) -> str:
        """Set/update entity graph cache for a matter.

        Story 7-3: AC #4 - Store pre-built MIG graph.

        Args:
            matter_id: Matter UUID.
            cache: Entity graph cache to store.

        Returns:
            Record UUID.

        Raises:
            RuntimeError: If database operation fails.
        """
        self._ensure_client()

        try:
            # Use upsert_matter_memory DB function
            result = self._supabase.rpc(
                "upsert_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": ENTITY_GRAPH_TYPE,
                    "p_data": cache.model_dump(mode="json"),
                },
            ).execute()
        except Exception as e:
            logger.error(
                "set_entity_graph_cache_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to set entity graph cache: {e}") from e

        logger.info(
            "entity_graph_cache_set",
            matter_id=matter_id,
            entity_count=cache.entity_count,
            relationship_count=cache.relationship_count,
        )

        return result.data

    async def invalidate_entity_graph_cache(
        self,
        matter_id: str,
    ) -> bool:
        """Invalidate (delete) entity graph cache.

        Story 7-3: Called when new documents uploaded.

        Args:
            matter_id: Matter UUID.

        Returns:
            True if deleted, False if not found.
        """
        self._ensure_client()

        try:
            result = (
                self._supabase.table("matter_memory")
                .delete()
                .eq("matter_id", matter_id)
                .eq("memory_type", ENTITY_GRAPH_TYPE)
                .execute()
            )
        except Exception as e:
            logger.error(
                "invalidate_entity_graph_cache_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to invalidate entity graph cache: {e}") from e

        deleted = len(result.data) > 0 if result.data else False

        logger.info(
            "entity_graph_cache_invalidated",
            matter_id=matter_id,
            deleted=deleted,
        )

        return deleted

    # =========================================================================
    # Story 7-3: Generic Memory Methods
    # =========================================================================

    async def get_memory(
        self,
        matter_id: str,
        memory_type: str,
    ) -> dict[str, Any] | None:
        """Get generic memory data for a matter.

        Story 7-3: Flexible method for any memory type.

        Args:
            matter_id: Matter UUID.
            memory_type: Memory type discriminator.

        Returns:
            Raw data dict if exists, None otherwise.
        """
        self._ensure_client()

        try:
            result = (
                self._supabase.table("matter_memory")
                .select("data")
                .eq("matter_id", matter_id)
                .eq("memory_type", memory_type)
                .maybe_single()
                .execute()
            )
        except Exception as e:
            logger.error(
                "get_memory_failed",
                matter_id=matter_id,
                memory_type=memory_type,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get memory: {e}") from e

        if not result.data:
            return None

        return result.data.get("data", {})

    async def set_memory(
        self,
        matter_id: str,
        memory_type: str,
        data: dict[str, Any],
    ) -> str:
        """Set generic memory data for a matter.

        Story 7-3: Flexible method for any memory type.

        Args:
            matter_id: Matter UUID.
            memory_type: Memory type discriminator.
            data: Data to store.

        Returns:
            Record UUID.

        Raises:
            RuntimeError: If database operation fails.
        """
        self._ensure_client()

        try:
            result = self._supabase.rpc(
                "upsert_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": memory_type,
                    "p_data": data,
                },
            ).execute()
        except Exception as e:
            logger.error(
                "set_memory_failed",
                matter_id=matter_id,
                memory_type=memory_type,
                error=str(e),
            )
            raise RuntimeError(f"Failed to set memory: {e}") from e

        logger.info(
            "memory_set",
            matter_id=matter_id,
            memory_type=memory_type,
        )

        return result.data


# Singleton instance
_matter_memory_repository: MatterMemoryRepository | None = None


def get_matter_memory_repository(
    supabase_client: Any = None,
) -> MatterMemoryRepository:
    """Get or create MatterMemoryRepository instance.

    Factory function following project pattern.

    Args:
        supabase_client: Optional Supabase client for injection (only used on first call).

    Returns:
        MatterMemoryRepository instance.

    Note:
        Client injection only works on first call. To inject a different client,
        call reset_matter_memory_repository() first. This prevents inconsistent
        state from late injection after the singleton is already in use.
    """
    global _matter_memory_repository

    if _matter_memory_repository is None:
        _matter_memory_repository = MatterMemoryRepository(supabase_client)
    elif supabase_client is not None:
        logger.warning(
            "matter_memory_repository_client_injection_ignored",
            reason="singleton already created - call reset_matter_memory_repository() first",
        )

    return _matter_memory_repository


def reset_matter_memory_repository() -> None:
    """Reset singleton (for testing)."""
    global _matter_memory_repository
    _matter_memory_repository = None
    logger.debug("matter_memory_repository_reset")
