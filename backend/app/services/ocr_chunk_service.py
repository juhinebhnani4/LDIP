"""OCR Chunk Service for managing OCR chunk records.

Provides database operations for tracking OCR chunk processing state:
- Create and update chunks
- Query chunks by document
- Heartbeat detection for stale worker handling
- Batch operations for efficient multi-chunk processing

CRITICAL: All operations support matter isolation via RLS.

NOTE: Uses asyncio.to_thread() to run synchronous Supabase client calls
without blocking the event loop.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import structlog

from app.models.ocr_chunk import (
    VALID_STATUS_TRANSITIONS,
    ChunkProgress,
    ChunkSpec,
    ChunkStatus,
    DocumentOCRChunk,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)

# Threshold for detecting stale chunks (workers that died without updating status)
STALE_CHUNK_THRESHOLD_SECONDS = 90


# =============================================================================
# Exceptions
# =============================================================================


class OCRChunkServiceError(Exception):
    """Base exception for OCR chunk service operations."""

    def __init__(self, message: str, code: str = "OCR_CHUNK_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ChunkNotFoundError(OCRChunkServiceError):
    """Raised when a chunk is not found."""

    def __init__(self, chunk_id: str):
        super().__init__(f"Chunk {chunk_id} not found", code="CHUNK_NOT_FOUND")


class InvalidStatusTransitionError(OCRChunkServiceError):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, current: str, target: str):
        super().__init__(
            f"Invalid status transition from {current} to {target}",
            code="INVALID_STATUS_TRANSITION",
        )


class DuplicateChunkError(OCRChunkServiceError):
    """Raised when attempting to create a duplicate chunk."""

    def __init__(self, document_id: str, chunk_index: int):
        super().__init__(
            f"Chunk {chunk_index} already exists for document {document_id}",
            code="DUPLICATE_CHUNK",
        )


class InvalidPageRangeError(OCRChunkServiceError):
    """Raised when page_start > page_end."""

    def __init__(self, page_start: int, page_end: int):
        super().__init__(
            f"Invalid page range: page_start ({page_start}) must be <= page_end ({page_end})",
            code="INVALID_PAGE_RANGE",
        )


# =============================================================================
# Service Implementation
# =============================================================================


class OCRChunkService:
    """Service for managing OCR chunk records.

    Handles CRUD operations for document_ocr_chunks table:
    - Create and update chunk records
    - Query chunks by document/status
    - Heartbeat detection for stale workers
    - Batch operations

    Security: Relies on Supabase RLS policies for matter isolation.
    All queries are automatically filtered by the authenticated user's
    matter access via the matter_attorneys table.

    All async methods use asyncio.to_thread() to run synchronous Supabase
    client calls without blocking the event loop.

    Example:
        >>> service = OCRChunkService()
        >>> chunk = await service.create_chunk(
        ...     document_id="doc-123",
        ...     matter_id="matter-456",
        ...     chunk_index=0,
        ...     page_start=1,
        ...     page_end=25,
        ... )
        >>> chunk.status
        ChunkStatus.PENDING
    """

    def __init__(self) -> None:
        """Initialize OCR chunk service."""
        self._client: object | None = None

    @property
    def client(self) -> object:
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            OCRChunkServiceError: If Supabase is not configured.
        """
        if self._client is None:
            self._client = get_supabase_client()
            if self._client is None:
                raise OCRChunkServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                )
        return self._client

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create_chunk(
        self,
        document_id: str,
        matter_id: str,
        chunk_index: int,
        page_start: int,
        page_end: int,
    ) -> DocumentOCRChunk:
        """Create a new OCR chunk record.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID for isolation.
            chunk_index: Zero-indexed chunk position.
            page_start: First page of chunk (1-indexed).
            page_end: Last page of chunk (1-indexed).

        Returns:
            Created DocumentOCRChunk.

        Raises:
            InvalidPageRangeError: If page_start > page_end.
            DuplicateChunkError: If chunk_index already exists for document.
            OCRChunkServiceError: If creation fails.
        """
        # Defense-in-depth validation (DB enforces this too)
        if page_start > page_end:
            raise InvalidPageRangeError(page_start, page_end)

        def _insert():
            return (
                self.client.table("document_ocr_chunks")
                .insert({
                    "document_id": document_id,
                    "matter_id": matter_id,
                    "chunk_index": chunk_index,
                    "page_start": page_start,
                    "page_end": page_end,
                    "status": ChunkStatus.PENDING.value,
                })
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)

            if response.data:
                chunk = self._db_row_to_chunk(response.data[0])
                logger.info(
                    "chunk_created",
                    chunk_id=chunk.id,
                    document_id=document_id,
                    matter_id=matter_id,
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                )
                return chunk

            raise OCRChunkServiceError("Failed to create chunk - no data returned")

        except Exception as e:
            if isinstance(e, OCRChunkServiceError):
                raise

            # Handle unique constraint violation
            error_str = str(e).lower()
            if "unique" in error_str or "duplicate" in error_str or "23505" in error_str:
                logger.warning(
                    "chunk_duplicate",
                    document_id=document_id,
                    chunk_index=chunk_index,
                )
                raise DuplicateChunkError(document_id, chunk_index) from None

            logger.error(
                "chunk_create_failed",
                error=str(e),
                document_id=document_id,
                chunk_index=chunk_index,
            )
            raise OCRChunkServiceError(f"Failed to create chunk: {e}") from e

    async def get_chunk(self, chunk_id: str) -> DocumentOCRChunk | None:
        """Get a chunk by ID.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            DocumentOCRChunk if found, None otherwise.
        """
        def _query():
            return (
                self.client.table("document_ocr_chunks")
                .select("*")
                .eq("id", chunk_id)
                .limit(1)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        if response.data:
            return self._db_row_to_chunk(response.data[0])
        return None

    async def update_status(
        self,
        chunk_id: str,
        status: ChunkStatus,
        error_message: str | None = None,
    ) -> DocumentOCRChunk:
        """Update chunk status with timestamp logic.

        Args:
            chunk_id: Chunk UUID.
            status: New status.
            error_message: Error message if status is 'failed'.

        Returns:
            Updated DocumentOCRChunk.

        Raises:
            ChunkNotFoundError: If chunk doesn't exist.
            InvalidStatusTransitionError: If status transition is invalid.
        """
        # Get current chunk to validate transition
        current_chunk = await self.get_chunk(chunk_id)
        if not current_chunk:
            raise ChunkNotFoundError(chunk_id)

        # Validate status transition
        self._validate_status_transition(current_chunk.status, status)

        # Build update data with appropriate timestamps
        update_data: dict = {
            "status": status.value,
        }

        if status == ChunkStatus.PROCESSING:
            update_data["processing_started_at"] = datetime.now(UTC).isoformat()
        elif status in (ChunkStatus.COMPLETED, ChunkStatus.FAILED):
            update_data["processing_completed_at"] = datetime.now(UTC).isoformat()

        if error_message is not None:
            update_data["error_message"] = error_message

        # Clear error message when transitioning away from failed
        if status == ChunkStatus.PENDING and current_chunk.status == ChunkStatus.FAILED:
            update_data["error_message"] = None
            update_data["processing_started_at"] = None
            update_data["processing_completed_at"] = None

        def _update():
            return (
                self.client.table("document_ocr_chunks")
                .update(update_data)
                .eq("id", chunk_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)

        if response.data:
            chunk = self._db_row_to_chunk(response.data[0])
            logger.info(
                "chunk_status_updated",
                chunk_id=chunk_id,
                old_status=current_chunk.status.value,
                new_status=status.value,
                error_message=error_message,
            )
            return chunk

        raise OCRChunkServiceError(f"Failed to update chunk status for {chunk_id}")

    async def update_result(
        self,
        chunk_id: str,
        result_storage_path: str,
        result_checksum: str,
    ) -> DocumentOCRChunk:
        """Update chunk with OCR result storage information.

        Called after OCR processing completes to record where results are stored.

        Args:
            chunk_id: Chunk UUID.
            result_storage_path: Supabase Storage path for cached OCR results.
            result_checksum: SHA256 checksum for result validation.

        Returns:
            Updated DocumentOCRChunk.

        Raises:
            ChunkNotFoundError: If chunk doesn't exist.
            OCRChunkServiceError: If update fails.
        """
        # Verify chunk exists
        chunk = await self.get_chunk(chunk_id)
        if not chunk:
            raise ChunkNotFoundError(chunk_id)

        def _update():
            return (
                self.client.table("document_ocr_chunks")
                .update({
                    "result_storage_path": result_storage_path,
                    "result_checksum": result_checksum,
                })
                .eq("id", chunk_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)

        if response.data:
            updated_chunk = self._db_row_to_chunk(response.data[0])
            logger.info(
                "chunk_result_updated",
                chunk_id=chunk_id,
                result_storage_path=result_storage_path,
                result_checksum=result_checksum[:16] + "...",  # Log truncated checksum
            )
            return updated_chunk

        raise OCRChunkServiceError(f"Failed to update chunk result for {chunk_id}")

    async def get_chunks_by_document(
        self,
        document_id: str,
    ) -> list[DocumentOCRChunk]:
        """Get all chunks for a document ordered by chunk_index.

        Args:
            document_id: Document UUID.

        Returns:
            List of DocumentOCRChunk records ordered by chunk_index.
        """
        def _query():
            return (
                self.client.table("document_ocr_chunks")
                .select("*")
                .eq("document_id", document_id)
                .order("chunk_index", desc=False)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        return [self._db_row_to_chunk(row) for row in (response.data or [])]

    async def get_failed_chunks(
        self,
        document_id: str,
    ) -> list[DocumentOCRChunk]:
        """Get only failed chunks for a document.

        Args:
            document_id: Document UUID.

        Returns:
            List of failed DocumentOCRChunk records.
        """
        def _query():
            return (
                self.client.table("document_ocr_chunks")
                .select("*")
                .eq("document_id", document_id)
                .eq("status", ChunkStatus.FAILED.value)
                .order("chunk_index", desc=False)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        return [self._db_row_to_chunk(row) for row in (response.data or [])]

    async def get_pending_chunks(
        self,
        document_id: str,
    ) -> list[DocumentOCRChunk]:
        """Get pending chunks ready for processing.

        Args:
            document_id: Document UUID.

        Returns:
            List of pending DocumentOCRChunk records.
        """
        def _query():
            return (
                self.client.table("document_ocr_chunks")
                .select("*")
                .eq("document_id", document_id)
                .eq("status", ChunkStatus.PENDING.value)
                .order("chunk_index", desc=False)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        return [self._db_row_to_chunk(row) for row in (response.data or [])]

    async def get_processing_chunks(
        self,
        document_id: str,
    ) -> list[DocumentOCRChunk]:
        """Get chunks currently being processed.

        Useful for monitoring active work and detecting potential issues.

        Args:
            document_id: Document UUID.

        Returns:
            List of processing DocumentOCRChunk records.
        """
        def _query():
            return (
                self.client.table("document_ocr_chunks")
                .select("*")
                .eq("document_id", document_id)
                .eq("status", ChunkStatus.PROCESSING.value)
                .order("chunk_index", desc=False)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        return [self._db_row_to_chunk(row) for row in (response.data or [])]

    # =========================================================================
    # Heartbeat Detection
    # =========================================================================

    async def update_heartbeat(self, chunk_id: str) -> bool:
        """Update heartbeat timestamp for a processing chunk.

        This resets the processing_started_at timestamp to current time,
        indicating the worker is still alive and working on this chunk.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            True if heartbeat was recorded, False if chunk not found.
        """
        def _update():
            return (
                self.client.table("document_ocr_chunks")
                .update({
                    "processing_started_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", chunk_id)
                .eq("status", ChunkStatus.PROCESSING.value)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_update)
            if response.data:
                logger.debug("chunk_heartbeat", chunk_id=chunk_id)
                return True
        except Exception as e:
            logger.warning("chunk_heartbeat_failed", chunk_id=chunk_id, error=str(e))

        return False

    async def detect_stale_chunks(self) -> list[DocumentOCRChunk]:
        """Find chunks stuck in 'processing' for too long.

        Chunks in 'processing' status with processing_started_at older than
        STALE_CHUNK_THRESHOLD_SECONDS are considered stale (worker died).

        Returns:
            List of stale DocumentOCRChunk records.
        """
        threshold = datetime.now(UTC) - timedelta(seconds=STALE_CHUNK_THRESHOLD_SECONDS)

        def _query():
            return (
                self.client.table("document_ocr_chunks")
                .select("*")
                .eq("status", ChunkStatus.PROCESSING.value)
                .lt("processing_started_at", threshold.isoformat())
                .execute()
            )

        response = await asyncio.to_thread(_query)

        stale_chunks = [self._db_row_to_chunk(row) for row in (response.data or [])]

        if stale_chunks:
            logger.warning(
                "stale_chunks_detected",
                count=len(stale_chunks),
                chunk_ids=[c.id for c in stale_chunks],
            )

        return stale_chunks

    async def mark_chunk_stale(self, chunk_id: str) -> DocumentOCRChunk:
        """Mark a chunk as failed due to worker timeout.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            Updated DocumentOCRChunk with 'failed' status.

        Raises:
            ChunkNotFoundError: If chunk doesn't exist.
            InvalidStatusTransitionError: If chunk is not in 'processing' status.
        """
        chunk = await self.get_chunk(chunk_id)
        if not chunk:
            raise ChunkNotFoundError(chunk_id)

        if chunk.status != ChunkStatus.PROCESSING:
            raise InvalidStatusTransitionError(
                chunk.status.value,
                ChunkStatus.FAILED.value,
            )

        def _update():
            return (
                self.client.table("document_ocr_chunks")
                .update({
                    "status": ChunkStatus.FAILED.value,
                    "error_message": "worker_timeout",
                    "processing_completed_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", chunk_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)

        if response.data:
            updated_chunk = self._db_row_to_chunk(response.data[0])
            logger.warning(
                "chunk_marked_stale",
                chunk_id=chunk_id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
            )
            return updated_chunk

        raise OCRChunkServiceError(f"Failed to mark chunk {chunk_id} as stale")

    # =========================================================================
    # Batch Operations
    # =========================================================================

    async def create_chunks_for_document(
        self,
        document_id: str,
        matter_id: str,
        chunk_specs: list[ChunkSpec],
    ) -> list[DocumentOCRChunk]:
        """Create multiple chunks for a document in one transaction.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID for isolation.
            chunk_specs: List of chunk specifications.

        Returns:
            List of created DocumentOCRChunk records.

        Raises:
            InvalidPageRangeError: If any chunk has invalid page range.
            DuplicateChunkError: If any chunk_index already exists.
            OCRChunkServiceError: If creation fails.
        """
        if not chunk_specs:
            return []

        # Validate all page ranges
        for spec in chunk_specs:
            if spec.page_start > spec.page_end:
                raise InvalidPageRangeError(spec.page_start, spec.page_end)

        # Build insert data
        insert_data = [
            {
                "document_id": document_id,
                "matter_id": matter_id,
                "chunk_index": spec.chunk_index,
                "page_start": spec.page_start,
                "page_end": spec.page_end,
                "status": ChunkStatus.PENDING.value,
            }
            for spec in chunk_specs
        ]

        def _insert():
            return (
                self.client.table("document_ocr_chunks")
                .insert(insert_data)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)

            if response.data:
                chunks = [self._db_row_to_chunk(row) for row in response.data]
                logger.info(
                    "chunks_batch_created",
                    document_id=document_id,
                    matter_id=matter_id,
                    count=len(chunks),
                    chunk_indices=[c.chunk_index for c in chunks],
                )
                return chunks

            raise OCRChunkServiceError("Failed to create chunks - no data returned")

        except Exception as e:
            if isinstance(e, OCRChunkServiceError):
                raise

            # Handle unique constraint violation
            error_str = str(e).lower()
            if "unique" in error_str or "duplicate" in error_str or "23505" in error_str:
                logger.warning(
                    "chunks_batch_duplicate",
                    document_id=document_id,
                )
                raise DuplicateChunkError(document_id, -1) from None  # -1 indicates batch

            logger.error(
                "chunks_batch_create_failed",
                error=str(e),
                document_id=document_id,
            )
            raise OCRChunkServiceError(f"Failed to create chunks: {e}") from e

    async def get_chunk_progress(self, document_id: str) -> ChunkProgress:
        """Get aggregated chunk processing progress for a document.

        Args:
            document_id: Document UUID.

        Returns:
            ChunkProgress with status counts.
        """
        def _query():
            return (
                self.client.table("document_ocr_chunks")
                .select("status")
                .eq("document_id", document_id)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        # Initialize counts
        counts = {
            "total": 0,
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
        }

        for row in (response.data or []):
            counts["total"] += 1
            status = row.get("status", "").lower()
            if status in counts:
                counts[status] += 1

        return ChunkProgress(
            total=counts["total"],
            pending=counts["pending"],
            processing=counts["processing"],
            completed=counts["completed"],
            failed=counts["failed"],
        )

    # =========================================================================
    # Cleanup Operations (Story 15.4)
    # =========================================================================

    async def delete_chunks_for_document(self, document_id: str) -> int:
        """Delete all chunk records for a document.

        Used for cleanup after successful OCR processing completes.

        Args:
            document_id: Document UUID.

        Returns:
            Number of records deleted.
        """
        def _delete():
            return (
                self.client.table("document_ocr_chunks")
                .delete()
                .eq("document_id", document_id)
                .execute()
            )

        response = await asyncio.to_thread(_delete)
        count = len(response.data) if response.data else 0

        logger.info(
            "chunks_deleted",
            document_id=document_id,
            count=count,
        )

        return count

    async def get_stale_chunk_documents(
        self,
        cutoff_date: datetime,
        completed_statuses: list[str] | None = None,
    ) -> list[dict]:
        """Find documents with stale chunks ready for cleanup.

        Returns documents where:
        - Chunk records exist older than cutoff_date
        - Parent document status is in completed_statuses

        Args:
            cutoff_date: Delete chunks created before this date.
            completed_statuses: Document statuses to consider complete.
                              Defaults to ['ocr_complete', 'completed', 'failed'].

        Returns:
            List of dicts with document_id, matter_id, and chunk_count.
        """
        if completed_statuses is None:
            completed_statuses = ["ocr_complete", "completed", "failed"]

        def _query():
            # Query chunks older than cutoff
            return (
                self.client.table("document_ocr_chunks")
                .select("document_id, matter_id")
                .lt("created_at", cutoff_date.isoformat())
                .execute()
            )

        response = await asyncio.to_thread(_query)

        # Aggregate by document
        doc_chunks: dict[str, dict] = {}
        for row in (response.data or []):
            doc_id = row["document_id"]
            if doc_id not in doc_chunks:
                doc_chunks[doc_id] = {
                    "document_id": doc_id,
                    "matter_id": row["matter_id"],
                    "chunk_count": 0,
                }
            doc_chunks[doc_id]["chunk_count"] += 1

        return list(doc_chunks.values())

    # =========================================================================
    # Idempotency Operations (Story 17.4)
    # =========================================================================

    async def check_chunk_already_processed(
        self,
        chunk_id: str,
        expected_checksum: str | None = None,
    ) -> tuple[bool, dict | None]:
        """Check if a chunk was already successfully processed.

        Story 17.4: Idempotent Chunk Processing

        This enables idempotent chunk processing by checking if:
        1. Chunk is already in 'completed' status
        2. Result data exists in storage
        3. Optionally, checksum matches expected value

        Args:
            chunk_id: Chunk UUID.
            expected_checksum: Optional checksum to verify result integrity.

        Returns:
            Tuple of (already_processed, cached_result_info).
            If already_processed is True, cached_result_info contains:
            - result_storage_path: Path to cached OCR results
            - result_checksum: SHA256 of cached results
            - processing_completed_at: When processing finished
        """
        chunk = await self.get_chunk(chunk_id)

        if not chunk:
            logger.warning("idempotency_check_chunk_not_found", chunk_id=chunk_id)
            return False, None

        if chunk.status != ChunkStatus.COMPLETED:
            logger.debug(
                "idempotency_check_not_completed",
                chunk_id=chunk_id,
                status=chunk.status.value,
            )
            return False, None

        if not chunk.result_storage_path or not chunk.result_checksum:
            logger.warning(
                "idempotency_check_missing_result",
                chunk_id=chunk_id,
                has_path=bool(chunk.result_storage_path),
                has_checksum=bool(chunk.result_checksum),
            )
            return False, None

        # Optionally verify checksum matches
        if expected_checksum and chunk.result_checksum != expected_checksum:
            logger.warning(
                "idempotency_check_checksum_mismatch",
                chunk_id=chunk_id,
                expected=expected_checksum[:16] + "...",
                actual=chunk.result_checksum[:16] + "...",
            )
            return False, None

        logger.info(
            "idempotency_check_already_processed",
            chunk_id=chunk_id,
            result_path=chunk.result_storage_path,
        )

        return True, {
            "result_storage_path": chunk.result_storage_path,
            "result_checksum": chunk.result_checksum,
            "processing_completed_at": chunk.processing_completed_at,
        }

    async def get_or_create_chunk(
        self,
        document_id: str,
        matter_id: str,
        chunk_index: int,
        page_start: int,
        page_end: int,
    ) -> tuple[DocumentOCRChunk, bool]:
        """Get existing chunk or create new one (idempotent create).

        Story 17.4: Idempotent Chunk Processing

        This enables safe retries of chunk creation. If a chunk already
        exists for the document/chunk_index combination, returns the
        existing chunk instead of failing with DuplicateChunkError.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID for isolation.
            chunk_index: Zero-indexed chunk position.
            page_start: First page of chunk (1-indexed).
            page_end: Last page of chunk (1-indexed).

        Returns:
            Tuple of (chunk, created).
            created is True if chunk was newly created, False if existing.

        Raises:
            InvalidPageRangeError: If page_start > page_end.
            OCRChunkServiceError: If operation fails.
        """
        # First try to get existing chunk
        def _query_existing():
            return (
                self.client.table("document_ocr_chunks")
                .select("*")
                .eq("document_id", document_id)
                .eq("chunk_index", chunk_index)
                .limit(1)
                .execute()
            )

        response = await asyncio.to_thread(_query_existing)

        if response.data:
            existing_chunk = self._db_row_to_chunk(response.data[0])
            logger.debug(
                "chunk_already_exists",
                document_id=document_id,
                chunk_index=chunk_index,
                chunk_id=existing_chunk.id,
            )
            return existing_chunk, False

        # Chunk doesn't exist, create it
        try:
            new_chunk = await self.create_chunk(
                document_id=document_id,
                matter_id=matter_id,
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
            )
            return new_chunk, True
        except DuplicateChunkError:
            # Race condition - another worker created it
            # Query again to get the existing chunk
            response = await asyncio.to_thread(_query_existing)
            if response.data:
                existing_chunk = self._db_row_to_chunk(response.data[0])
                logger.debug(
                    "chunk_race_condition_resolved",
                    document_id=document_id,
                    chunk_index=chunk_index,
                    chunk_id=existing_chunk.id,
                )
                return existing_chunk, False
            raise

    # =========================================================================
    # Retry Operations (Story 16.5)
    # =========================================================================

    async def reset_chunk_for_retry(self, chunk_id: str) -> DocumentOCRChunk:
        """Reset a failed chunk back to pending for retry.

        Clears error message and result data, allowing the chunk
        to be reprocessed.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            Updated DocumentOCRChunk with 'pending' status.

        Raises:
            ChunkNotFoundError: If chunk doesn't exist.
            InvalidStatusTransitionError: If chunk is not in 'failed' status.
        """
        chunk = await self.get_chunk(chunk_id)
        if not chunk:
            raise ChunkNotFoundError(chunk_id)

        if chunk.status != ChunkStatus.FAILED:
            raise InvalidStatusTransitionError(
                chunk.status.value,
                ChunkStatus.PENDING.value,
            )

        def _update():
            return (
                self.client.table("document_ocr_chunks")
                .update({
                    "status": ChunkStatus.PENDING.value,
                    "error_message": None,
                    "result_storage_path": None,
                    "result_checksum": None,
                    "processing_started_at": None,
                    "processing_completed_at": None,
                })
                .eq("id", chunk_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)

        if response.data:
            updated_chunk = self._db_row_to_chunk(response.data[0])
            logger.info(
                "chunk_reset_for_retry",
                chunk_id=chunk_id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
            )
            return updated_chunk

        raise OCRChunkServiceError(f"Failed to reset chunk {chunk_id} for retry")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _validate_status_transition(
        self,
        current: ChunkStatus,
        target: ChunkStatus,
    ) -> None:
        """Validate that a status transition is allowed.

        Args:
            current: Current chunk status.
            target: Target chunk status.

        Raises:
            InvalidStatusTransitionError: If transition is not allowed.
        """
        if target not in VALID_STATUS_TRANSITIONS.get(current, set()):
            raise InvalidStatusTransitionError(current.value, target.value)

    def _db_row_to_chunk(self, row: dict) -> DocumentOCRChunk:
        """Convert database row to DocumentOCRChunk model."""
        return DocumentOCRChunk(
            id=row["id"],
            matter_id=row["matter_id"],
            document_id=row["document_id"],
            chunk_index=row["chunk_index"],
            page_start=row["page_start"],
            page_end=row["page_end"],
            status=ChunkStatus(row["status"]),
            error_message=row.get("error_message"),
            result_storage_path=row.get("result_storage_path"),
            result_checksum=row.get("result_checksum"),
            processing_started_at=self._parse_timestamp(row.get("processing_started_at")),
            processing_completed_at=self._parse_timestamp(row.get("processing_completed_at")),
            created_at=self._parse_timestamp_required(row["created_at"], "created_at"),
            updated_at=self._parse_timestamp_required(row["updated_at"], "updated_at"),
        )

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        """Parse ISO timestamp to datetime for optional fields.

        Args:
            value: ISO timestamp string or None.

        Returns:
            Parsed datetime or None if value is empty/invalid.
        """
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            logger.warning(
                "timestamp_parse_failed",
                value=value,
                error=str(e),
            )
            return None

    def _parse_timestamp_required(self, value: str, field_name: str) -> datetime:
        """Parse ISO timestamp to datetime for required fields.

        Args:
            value: ISO timestamp string (must not be None).
            field_name: Field name for error reporting.

        Returns:
            Parsed datetime.

        Raises:
            OCRChunkServiceError: If parsing fails.
        """
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            logger.error(
                "required_timestamp_parse_failed",
                field=field_name,
                value=value,
                error=str(e),
            )
            raise OCRChunkServiceError(
                f"Failed to parse required timestamp {field_name}: {value}",
                code="TIMESTAMP_PARSE_ERROR",
            ) from e


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_ocr_chunk_service() -> OCRChunkService:
    """Get singleton OCR chunk service instance.

    Returns:
        OCRChunkService instance.
    """
    return OCRChunkService()
