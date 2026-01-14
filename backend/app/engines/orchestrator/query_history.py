"""Query History Store for Matter Memory persistence.

Story 6-3: Audit Trail Logging (AC: #4)

Stores query audit records in the matter_query_history table,
implementing append-only semantics for forensic integrity.

CRITICAL: This is append-only storage. Once a record is created,
it cannot be modified or deleted (except via database admin).
"""

import asyncio
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from app.models.orchestrator import QueryAuditEntry, QueryAuditRecord

logger = structlog.get_logger(__name__)


class QueryHistoryStore:
    """Append-only store for query audit records.

    Story 6-3: Implements matter_query_history persistence
    with forensic integrity (no updates/deletes).

    Example:
        >>> store = get_query_history_store(db_client)
        >>> record = await store.append_query(audit_entry)
        >>> record.id
        'record-uuid-...'
    """

    def __init__(self, db_client: Any = None) -> None:
        """Initialize query history store.

        Args:
            db_client: Supabase client for database operations.
        """
        self._db = db_client

    async def append_query(
        self,
        audit_entry: QueryAuditEntry,
    ) -> QueryAuditRecord:
        """Append query audit record to matter's history (AC: #4).

        Args:
            audit_entry: Complete audit entry to store.

        Returns:
            QueryAuditRecord with generated ID and timestamp.

        Note:
            This is an APPEND-ONLY operation. Records cannot
            be modified after creation.
        """
        record_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        record = QueryAuditRecord(
            id=record_id,
            matter_id=audit_entry.matter_id,
            query_id=audit_entry.query_id,
            audit_data=audit_entry,
            created_at=created_at,
        )

        if self._db:
            await self._persist_to_database(record)
        else:
            # Log-only mode if no database
            logger.info(
                "query_audit_record_created",
                record_id=record_id,
                matter_id=audit_entry.matter_id,
                query_id=audit_entry.query_id,
            )

        return record

    async def _persist_to_database(
        self,
        record: QueryAuditRecord,
    ) -> None:
        """Persist record to database.

        Uses asyncio.to_thread for non-blocking insert.
        """
        try:
            db_record = {
                "id": record.id,
                "matter_id": record.matter_id,
                "query_id": record.query_id,
                "audit_data": record.audit_data.model_dump(mode="json"),
                "created_at": record.created_at,
            }

            def _insert() -> Any:
                return (
                    self._db.table("matter_query_history").insert(db_record).execute()
                )

            await asyncio.to_thread(_insert)

            logger.info(
                "query_audit_persisted",
                record_id=record.id,
                matter_id=record.matter_id,
            )

        except Exception as e:
            # Log error but don't fail - audit is non-critical
            logger.error(
                "query_audit_persistence_failed",
                record_id=record.id,
                matter_id=record.matter_id,
                error=str(e),
            )

    async def get_query_history(
        self,
        matter_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[QueryAuditRecord]:
        """Retrieve query history for a matter (AC: #4).

        Args:
            matter_id: Matter UUID.
            limit: Maximum records to return.
            offset: Number of records to skip.

        Returns:
            List of QueryAuditRecord ordered by created_at DESC.
        """
        if not self._db:
            logger.warning("get_query_history_no_db", matter_id=matter_id)
            return []

        try:

            def _query() -> Any:
                return (
                    self._db.table("matter_query_history")
                    .select("*")
                    .eq("matter_id", matter_id)
                    .order("created_at", desc=True)
                    .range(offset, offset + limit - 1)
                    .execute()
                )

            response = await asyncio.to_thread(_query)

            records = []
            for row in response.data:
                records.append(
                    QueryAuditRecord(
                        id=row["id"],
                        matter_id=row["matter_id"],
                        query_id=row["query_id"],
                        audit_data=QueryAuditEntry(**row["audit_data"]),
                        created_at=row["created_at"],
                    )
                )

            return records

        except Exception as e:
            logger.error(
                "get_query_history_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return []

    async def get_query_by_id(
        self,
        matter_id: str,
        query_id: str,
    ) -> QueryAuditRecord | None:
        """Retrieve specific query audit record.

        Args:
            matter_id: Matter UUID (for RLS).
            query_id: Query UUID to retrieve.

        Returns:
            QueryAuditRecord if found, None otherwise.
        """
        if not self._db:
            return None

        try:

            def _query() -> Any:
                return (
                    self._db.table("matter_query_history")
                    .select("*")
                    .eq("matter_id", matter_id)
                    .eq("query_id", query_id)
                    .single()
                    .execute()
                )

            response = await asyncio.to_thread(_query)

            if response.data:
                return QueryAuditRecord(
                    id=response.data["id"],
                    matter_id=response.data["matter_id"],
                    query_id=response.data["query_id"],
                    audit_data=QueryAuditEntry(**response.data["audit_data"]),
                    created_at=response.data["created_at"],
                )
            return None

        except Exception as e:
            logger.error(
                "get_query_by_id_failed",
                matter_id=matter_id,
                query_id=query_id,
                error=str(e),
            )
            return None


# Thread-safe singleton implementation
_query_history_store: QueryHistoryStore | None = None
_query_history_store_lock = threading.Lock()


def get_query_history_store(db_client: Any = None) -> QueryHistoryStore:
    """Get or create QueryHistoryStore instance (thread-safe).

    Args:
        db_client: Optional Supabase client.

    Returns:
        QueryHistoryStore instance.
    """
    global _query_history_store

    # Fast path - no lock needed if already initialized
    if _query_history_store is not None and (
        db_client is None or _query_history_store._db is not None
    ):
        return _query_history_store

    # Slow path - need lock for initialization
    with _query_history_store_lock:
        if _query_history_store is None:
            _query_history_store = QueryHistoryStore(db_client)
        elif db_client is not None and _query_history_store._db is None:
            _query_history_store._db = db_client

    return _query_history_store


def reset_query_history_store() -> None:
    """Reset the singleton instance (for testing).

    This allows tests to get a fresh instance with mocked dependencies.
    """
    global _query_history_store
    with _query_history_store_lock:
        _query_history_store = None
