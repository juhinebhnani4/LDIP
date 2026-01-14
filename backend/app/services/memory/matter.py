"""Matter Memory Repository for persistent matter-level storage.

Story 7-2: Session TTL and Context Restoration

Manages archived session storage in PostgreSQL matter_memory table.
This repository is specifically for archived session operations.
Full Matter Memory implementation comes in Story 7-3.

Table: matter_memory with memory_type='archived_session'
"""

from typing import TYPE_CHECKING, Any

import structlog
from pydantic import ValidationError

from app.models.memory import ArchivedSession
from app.services.supabase.client import get_supabase_client

if TYPE_CHECKING:
    from app.models.memory import SessionEntityMention, SessionMessage

logger = structlog.get_logger(__name__)

# Memory type for archived sessions
ARCHIVED_SESSION_TYPE = "archived_session"

# Default query limit for archived session retrieval
DEFAULT_ARCHIVE_QUERY_LIMIT = 10


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


# Singleton instance
_matter_memory_repository: MatterMemoryRepository | None = None


def get_matter_memory_repository(
    supabase_client: Any = None,
) -> MatterMemoryRepository:
    """Get or create MatterMemoryRepository instance.

    Factory function following project pattern.

    Args:
        supabase_client: Optional Supabase client for injection.

    Returns:
        MatterMemoryRepository instance.
    """
    global _matter_memory_repository

    if _matter_memory_repository is None:
        _matter_memory_repository = MatterMemoryRepository(supabase_client)
    elif supabase_client is not None and _matter_memory_repository._supabase is None:
        _matter_memory_repository._supabase = supabase_client

    return _matter_memory_repository


def reset_matter_memory_repository() -> None:
    """Reset singleton (for testing)."""
    global _matter_memory_repository
    _matter_memory_repository = None
    logger.debug("matter_memory_repository_reset")
