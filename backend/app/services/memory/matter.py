"""Matter Memory Repository for persistent matter-level storage.

Story 7-2: Session TTL and Context Restoration
Story 7-3: Matter Memory PostgreSQL JSONB Storage
Story 7-4: Key Findings and Research Notes

Manages matter-level memory storage in PostgreSQL matter_memory table:
- Archived sessions (Story 7-2)
- Query history (Story 7-3)
- Timeline cache (Story 7-3)
- Entity graph cache (Story 7-3)
- Key findings (Story 7-4)
- Research notes (Story 7-4)

Table: matter_memory with memory_type discriminator
"""

from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.memory import (
    ArchivedSession,
    EntityGraphCache,
    KeyFinding,
    KeyFindings,
    QueryHistory,
    QueryHistoryEntry,
    ResearchNote,
    ResearchNotes,
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
KEY_FINDINGS_TYPE = "key_findings"  # Story 7-4: Task 3.1
RESEARCH_NOTES_TYPE = "research_notes"  # Story 7-4: Task 4.1

# JSONB array keys within each memory type document (Code Review Issue #7)
KEY_FINDINGS_KEY = "findings"  # Key for findings array in KEY_FINDINGS_TYPE
RESEARCH_NOTES_KEY = "notes"  # Key for notes array in RESEARCH_NOTES_TYPE
QUERY_HISTORY_KEY = "entries"  # Key for entries array in QUERY_HISTORY_TYPE


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
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ArchivedSession]:
        """Get archived sessions for a matter with pagination.

        Story 7-2: Task 6.4 - Lists archived sessions.

        Args:
            matter_id: Matter UUID.
            user_id: Optional user UUID to filter by (defense-in-depth).
            limit: Maximum records to return. Uses config default if None.
            offset: Records to skip.

        Returns:
            List of ArchivedSession objects.
        """
        self._ensure_client()

        # Use configurable default limit
        settings = get_settings()
        if limit is None:
            limit = settings.archived_session_query_limit

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
        limit: int | None = None,
    ) -> QueryHistory:
        """Get query history for a matter using efficient DB-side slicing.

        Story 7-3: AC #2 - Retrieve append-only query records.
        Epic 7 Code Review Fix: Uses DB function to avoid loading entire JSONB blob.

        Args:
            matter_id: Matter UUID.
            limit: Maximum entries to return (newest last). Uses config default if None.

        Returns:
            QueryHistory with entries.
        """
        self._ensure_client()

        # Use configurable default limit
        settings = get_settings()
        if limit is None:
            limit = settings.query_history_default_limit

        try:
            # Use DB function for efficient slicing (Epic 7 Code Review Fix)
            result = self._supabase.rpc(
                "get_matter_memory_entries",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": QUERY_HISTORY_TYPE,
                    "p_key": QUERY_HISTORY_KEY,
                    "p_limit": limit,
                },
            ).execute()
        except Exception as e:
            logger.error(
                "get_query_history_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get query history: {e}") from e

        # RPC returns the JSONB array directly
        entries_data = result.data if result.data else []

        # Parse entries into QueryHistoryEntry objects
        entries = []
        for entry_data in entries_data:
            try:
                entries.append(QueryHistoryEntry.model_validate(entry_data))
            except ValidationError as e:
                logger.warning(
                    "query_history_entry_validation_failed",
                    matter_id=matter_id,
                    error=str(e),
                )
                continue

        return QueryHistory(entries=entries)

    async def append_query(
        self,
        matter_id: str,
        entry: QueryHistoryEntry,
    ) -> str:
        """Append a query entry to history with bounded size.

        Story 7-3: AC #2 - Uses DB function for atomic append.
        Epic 7 Code Review Fix: Uses configurable limit to prevent unbounded growth.

        Args:
            matter_id: Matter UUID.
            entry: Query entry to append.

        Returns:
            Record UUID.

        Raises:
            RuntimeError: If database operation fails.
        """
        self._ensure_client()

        # Use configurable max entries limit
        settings = get_settings()
        max_entries = settings.query_history_max_entries

        try:
            # Use append_to_matter_memory DB function for atomic append with limit
            result = self._supabase.rpc(
                "append_to_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": QUERY_HISTORY_TYPE,
                    "p_key": QUERY_HISTORY_KEY,
                    "p_item": entry.model_dump(mode="json"),
                    "p_max_entries": max_entries,  # Epic 7 Code Review Fix
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
            max_entries=max_entries,
        )

        # RPC returns UUID string from DB function
        return str(result.data) if result.data else ""

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

        # RPC returns UUID string from DB function
        return str(result.data) if result.data else ""

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

        # RPC returns UUID string from DB function
        return str(result.data) if result.data else ""

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

        # RPC returns UUID string from DB function
        return str(result.data) if result.data else ""

    # =========================================================================
    # Story 7-4: Key Findings Methods (Task 3)
    # =========================================================================

    async def get_key_findings(
        self,
        matter_id: str,
    ) -> KeyFindings:
        """Get all key findings for a matter.

        Story 7-4: Task 3.2 - AC #1 - Retrieve verified findings.

        Args:
            matter_id: Matter UUID.

        Returns:
            KeyFindings container with findings list.
        """
        self._ensure_client()

        try:
            result = (
                self._supabase.table("matter_memory")
                .select("data")
                .eq("matter_id", matter_id)
                .eq("memory_type", KEY_FINDINGS_TYPE)
                .maybe_single()
                .execute()
            )
        except Exception as e:
            logger.error(
                "get_key_findings_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get key findings: {e}") from e

        if not result.data:
            return KeyFindings(findings=[])

        data = result.data.get("data", {})

        try:
            return KeyFindings.model_validate(data)
        except ValidationError as e:
            logger.warning(
                "key_findings_validation_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return KeyFindings(findings=[])

    async def add_key_finding(
        self,
        matter_id: str,
        finding: KeyFinding,
    ) -> str:
        """Add a key finding (append-only).

        Story 7-4: Task 3.3 - AC #1 - Uses DB function for atomic append.

        Args:
            matter_id: Matter UUID.
            finding: KeyFinding to add.

        Returns:
            Record UUID.

        Raises:
            RuntimeError: If database operation fails.
        """
        self._ensure_client()

        try:
            result = self._supabase.rpc(
                "append_to_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": KEY_FINDINGS_TYPE,
                    "p_key": KEY_FINDINGS_KEY,
                    "p_item": finding.model_dump(mode="json"),
                },
            ).execute()
        except Exception as e:
            logger.error(
                "add_key_finding_failed",
                matter_id=matter_id,
                finding_id=finding.finding_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to add key finding: {e}") from e

        logger.info(
            "key_finding_added",
            matter_id=matter_id,
            finding_id=finding.finding_id,
            finding_type=finding.finding_type,
        )

        return str(result.data) if result.data else ""

    async def update_key_finding(
        self,
        matter_id: str,
        finding_id: str,
        updates: dict[str, Any],
    ) -> bool:
        """Update a key finding by ID.

        Story 7-4: Task 3.4 - Uses read-modify-write pattern.

        Warning: Race Condition Risk (Code Review Issue #1)
            This method is NOT atomic. Two concurrent updates could overwrite
            each other. Acceptable for current usage patterns (low concurrency).

            TODO: If verification volume becomes high (>10 updates/minute per matter),
            implement atomic DB function: `update_key_finding_item(p_matter_id,
            p_finding_id, p_updates jsonb)` that uses jsonb_set() for atomic update.

        Note: For high-volume, consider DB function.

        Args:
            matter_id: Matter UUID.
            finding_id: Finding to update.
            updates: Fields to update (verified_by, verified_at, notes, etc.).

        Returns:
            True if updated, False if not found.
        """
        self._ensure_client()

        # Get current findings
        current = await self.get_key_findings(matter_id)

        # Find and update the target finding
        updated = False
        for i, finding in enumerate(current.findings):
            if finding.finding_id == finding_id:
                finding_dict = finding.model_dump()
                finding_dict.update(updates)
                finding_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
                current.findings[i] = KeyFinding.model_validate(finding_dict)
                updated = True
                break

        if not updated:
            logger.warning(
                "key_finding_not_found_for_update",
                matter_id=matter_id,
                finding_id=finding_id,
            )
            return False

        # Save back
        try:
            self._supabase.rpc(
                "upsert_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": KEY_FINDINGS_TYPE,
                    "p_data": current.model_dump(mode="json"),
                },
            ).execute()
        except Exception as e:
            logger.error(
                "update_key_finding_failed",
                matter_id=matter_id,
                finding_id=finding_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to update key finding: {e}") from e

        logger.info(
            "key_finding_updated",
            matter_id=matter_id,
            finding_id=finding_id,
        )

        return True

    async def delete_key_finding(
        self,
        matter_id: str,
        finding_id: str,
    ) -> bool:
        """Delete a key finding by ID (soft delete by removal).

        Story 7-4: Task 3.5 - Remove finding from list.

        Args:
            matter_id: Matter UUID.
            finding_id: Finding to delete.

        Returns:
            True if deleted, False if not found.
        """
        self._ensure_client()

        # Get current findings
        current = await self.get_key_findings(matter_id)

        # Find and remove the target finding
        original_count = len(current.findings)
        current.findings = [f for f in current.findings if f.finding_id != finding_id]

        if len(current.findings) == original_count:
            logger.warning(
                "key_finding_not_found_for_delete",
                matter_id=matter_id,
                finding_id=finding_id,
            )
            return False

        # Save back
        try:
            self._supabase.rpc(
                "upsert_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": KEY_FINDINGS_TYPE,
                    "p_data": current.model_dump(mode="json"),
                },
            ).execute()
        except Exception as e:
            logger.error(
                "delete_key_finding_failed",
                matter_id=matter_id,
                finding_id=finding_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to delete key finding: {e}") from e

        logger.info(
            "key_finding_deleted",
            matter_id=matter_id,
            finding_id=finding_id,
        )

        return True

    async def get_key_finding_by_id(
        self,
        matter_id: str,
        finding_id: str,
    ) -> KeyFinding | None:
        """Get a single key finding by ID.

        Story 7-4: Task 3.6 - Retrieve single finding.

        Args:
            matter_id: Matter UUID.
            finding_id: Finding UUID.

        Returns:
            KeyFinding if found, None otherwise.
        """
        findings = await self.get_key_findings(matter_id)

        for finding in findings.findings:
            if finding.finding_id == finding_id:
                return finding

        return None

    # =========================================================================
    # Story 7-4: Research Notes Methods (Task 4)
    # =========================================================================

    async def get_research_notes(
        self,
        matter_id: str,
    ) -> ResearchNotes:
        """Get all research notes for a matter.

        Story 7-4: Task 4.2 - AC #2 - Retrieve all notes.

        Args:
            matter_id: Matter UUID.

        Returns:
            ResearchNotes container with notes list.
        """
        self._ensure_client()

        try:
            result = (
                self._supabase.table("matter_memory")
                .select("data")
                .eq("matter_id", matter_id)
                .eq("memory_type", RESEARCH_NOTES_TYPE)
                .maybe_single()
                .execute()
            )
        except Exception as e:
            logger.error(
                "get_research_notes_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to get research notes: {e}") from e

        if not result.data:
            return ResearchNotes(notes=[])

        data = result.data.get("data", {})

        try:
            return ResearchNotes.model_validate(data)
        except ValidationError as e:
            logger.warning(
                "research_notes_validation_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return ResearchNotes(notes=[])

    async def add_research_note(
        self,
        matter_id: str,
        note: ResearchNote,
    ) -> str:
        """Add a research note.

        Story 7-4: Task 4.3 - AC #2 - Create new note.

        Args:
            matter_id: Matter UUID.
            note: ResearchNote to add.

        Returns:
            Record UUID.

        Raises:
            RuntimeError: If database operation fails.
        """
        self._ensure_client()

        try:
            result = self._supabase.rpc(
                "append_to_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": RESEARCH_NOTES_TYPE,
                    "p_key": RESEARCH_NOTES_KEY,
                    "p_item": note.model_dump(mode="json"),
                },
            ).execute()
        except Exception as e:
            logger.error(
                "add_research_note_failed",
                matter_id=matter_id,
                note_id=note.note_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to add research note: {e}") from e

        logger.info(
            "research_note_added",
            matter_id=matter_id,
            note_id=note.note_id,
            title=note.title,
        )

        return str(result.data) if result.data else ""

    async def update_research_note(
        self,
        matter_id: str,
        note_id: str,
        updates: dict[str, Any],
    ) -> bool:
        """Update a research note by ID.

        Story 7-4: Task 4.4 - Update note content/title/tags.

        Warning: Race Condition Risk (Code Review Issue #1)
            This method is NOT atomic. See update_key_finding() for details.
            Acceptable for current usage patterns (low concurrency).

        Args:
            matter_id: Matter UUID.
            note_id: Note to update.
            updates: Fields to update (title, content, tags, linked_findings).

        Returns:
            True if updated, False if not found.
        """
        self._ensure_client()

        # Get current notes
        current = await self.get_research_notes(matter_id)

        # Find and update the target note
        updated = False
        for i, note in enumerate(current.notes):
            if note.note_id == note_id:
                note_dict = note.model_dump()
                note_dict.update(updates)
                note_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
                current.notes[i] = ResearchNote.model_validate(note_dict)
                updated = True
                break

        if not updated:
            logger.warning(
                "research_note_not_found_for_update",
                matter_id=matter_id,
                note_id=note_id,
            )
            return False

        # Save back
        try:
            self._supabase.rpc(
                "upsert_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": RESEARCH_NOTES_TYPE,
                    "p_data": current.model_dump(mode="json"),
                },
            ).execute()
        except Exception as e:
            logger.error(
                "update_research_note_failed",
                matter_id=matter_id,
                note_id=note_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to update research note: {e}") from e

        logger.info(
            "research_note_updated",
            matter_id=matter_id,
            note_id=note_id,
        )

        return True

    async def delete_research_note(
        self,
        matter_id: str,
        note_id: str,
    ) -> bool:
        """Delete a research note by ID.

        Story 7-4: Task 4.5 - Remove note from list.

        Args:
            matter_id: Matter UUID.
            note_id: Note to delete.

        Returns:
            True if deleted, False if not found.
        """
        self._ensure_client()

        # Get current notes
        current = await self.get_research_notes(matter_id)

        # Find and remove the target note
        original_count = len(current.notes)
        current.notes = [n for n in current.notes if n.note_id != note_id]

        if len(current.notes) == original_count:
            logger.warning(
                "research_note_not_found_for_delete",
                matter_id=matter_id,
                note_id=note_id,
            )
            return False

        # Save back
        try:
            self._supabase.rpc(
                "upsert_matter_memory",
                {
                    "p_matter_id": matter_id,
                    "p_memory_type": RESEARCH_NOTES_TYPE,
                    "p_data": current.model_dump(mode="json"),
                },
            ).execute()
        except Exception as e:
            logger.error(
                "delete_research_note_failed",
                matter_id=matter_id,
                note_id=note_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to delete research note: {e}") from e

        logger.info(
            "research_note_deleted",
            matter_id=matter_id,
            note_id=note_id,
        )

        return True

    async def get_research_note_by_id(
        self,
        matter_id: str,
        note_id: str,
    ) -> ResearchNote | None:
        """Get a single research note by ID.

        Story 7-4: Task 4.6 - Retrieve single note.

        Args:
            matter_id: Matter UUID.
            note_id: Note UUID.

        Returns:
            ResearchNote if found, None otherwise.
        """
        notes = await self.get_research_notes(matter_id)

        for note in notes.notes:
            if note.note_id == note_id:
                return note

        return None

    async def search_research_notes(
        self,
        matter_id: str,
        tag: str | None = None,
        title_contains: str | None = None,
    ) -> list[ResearchNote]:
        """Search research notes by tag or title.

        Story 7-4: Task 4.7 - Optional search functionality.

        Args:
            matter_id: Matter UUID.
            tag: Tag to filter by.
            title_contains: Substring to search in title.

        Returns:
            List of matching ResearchNote objects.
        """
        notes = await self.get_research_notes(matter_id)

        results = []
        for note in notes.notes:
            # Filter by tag
            if tag and tag not in note.tags:
                continue
            # Filter by title
            if title_contains and title_contains.lower() not in note.title.lower():
                continue
            results.append(note)

        return results


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
