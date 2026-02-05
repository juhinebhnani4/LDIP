"""Chunk Recovery Service for detecting and recovering stale chunks.

Story 19.1: Automatic stale chunk recovery

This service detects chunks stuck in PROCESSING state and recovers them
by resetting to PENDING for retry. Follows the JobRecoveryService pattern.
"""

import asyncio
from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.models.ocr_chunk import ChunkStatus, DocumentOCRChunk
from app.services.ocr_chunk_service import (
    OCRChunkService,
    get_ocr_chunk_service,
)

logger = structlog.get_logger(__name__)


class ChunkRecoveryService:
    """Service for detecting and recovering stale/stuck chunks."""

    def __init__(
        self,
        chunk_service: OCRChunkService | None = None,
    ) -> None:
        self._chunk_service = chunk_service

    @property
    def chunk_service(self) -> OCRChunkService:
        if self._chunk_service is None:
            self._chunk_service = get_ocr_chunk_service()
        return self._chunk_service

    async def find_stale_chunks(self) -> list[DocumentOCRChunk]:
        """Find chunks stuck in PROCESSING state beyond threshold."""
        return await self.chunk_service.detect_stale_chunks()

    async def find_orphaned_pending_chunks(
        self,
        orphan_threshold_seconds: int = 300,
    ) -> list[DocumentOCRChunk]:
        """Find PENDING chunks that were never picked up by a worker.

        This catches Celery task delivery failures (e.g., chord tasks lost
        due to broker issues).

        Args:
            orphan_threshold_seconds: Time after which PENDING chunk is orphaned.

        Returns:
            List of orphaned PENDING chunks.
        """
        return await self.chunk_service.detect_orphaned_pending_chunks(
            orphan_threshold_seconds=orphan_threshold_seconds
        )

    async def find_retriable_failed_chunks(self) -> list[DocumentOCRChunk]:
        """Find FAILED chunks that can be auto-retried.

        Story 19.1+: Auto-retry chunks that failed due to transient errors
        like asyncio event loop issues.

        Only retries chunks with known transient error patterns:
        - event loop is closed
        - no running event loop
        - attached to a different loop
        - worker_timeout

        Returns:
            List of FAILED chunks eligible for retry.
        """
        from app.services.supabase.client import get_service_client

        client = get_service_client()

        # Find all failed chunks
        response = (
            client.table("document_ocr_chunks")
            .select("*")
            .eq("status", "failed")
            .execute()
        )

        if not response.data:
            return []

        # Filter to only retryable errors (transient asyncio/worker issues)
        retryable_patterns = [
            "event loop",
            "different loop",
            "worker_timeout",
            "no running",
            "no current",
        ]

        retriable = []
        for chunk_data in response.data:
            error_msg = (chunk_data.get("error_message") or "").lower()
            # Check if error matches any retryable pattern
            if any(pattern in error_msg for pattern in retryable_patterns):
                chunk = DocumentOCRChunk.model_validate(chunk_data)
                retriable.append(chunk)

        return retriable

    async def recover_stale_chunk(self, chunk: DocumentOCRChunk) -> dict:
        """Recover a single stale chunk.

        Recovery process:
        1. Check recovery attempt count from metadata
        2. Reset to PENDING if under max retries
        3. Mark as FAILED if max retries exceeded
        4. Re-dispatch chunk task
        """
        try:
            # Get fresh chunk state
            current_chunk = await self.chunk_service.get_chunk(chunk.id)
            if not current_chunk:
                return {
                    "success": False,
                    "error": "Chunk not found",
                    "chunk_id": chunk.id,
                }

            if current_chunk.status != ChunkStatus.PROCESSING:
                return {
                    "success": False,
                    "error": f"Chunk no longer processing (current: {current_chunk.status.value})",
                    "chunk_id": chunk.id,
                }

            # Parse recovery attempts from error_message (simple metadata)
            recovery_attempts = self._get_recovery_attempts(current_chunk)

            # Get max retries from config (Story 4.3)
            settings = get_settings()
            max_recovery_attempts = settings.chunk_max_recovery_retries

            if recovery_attempts >= max_recovery_attempts:
                # Mark as failed
                await self.chunk_service.update_status(
                    chunk.id,
                    ChunkStatus.FAILED,
                    error_message=f"Max recovery attempts ({max_recovery_attempts}) exceeded - worker_timeout",
                )
                logger.warning(
                    "chunk_max_recovery_exceeded",
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    recovery_attempts=recovery_attempts,
                )
                return {
                    "success": False,
                    "error": "Max recovery attempts exceeded",
                    "chunk_id": chunk.id,
                    "action": "marked_failed",
                }

            # Reset to pending for retry using the existing reset method
            await self.chunk_service.reset_chunk_for_retry(chunk.id)

            # Update error message to track recovery attempts
            await self.chunk_service.update_status(
                chunk.id,
                ChunkStatus.PENDING,
                error_message=f"worker_timeout_recovery_{recovery_attempts + 1}",
            )

            # Re-dispatch the chunk task
            self._redispatch_chunk_task(current_chunk)

            logger.info(
                "chunk_recovered",
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                recovery_attempt=recovery_attempts + 1,
            )

            return {
                "success": True,
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "recovery_attempt": recovery_attempts + 1,
                "action": "reset_to_pending",
            }

        except Exception as e:
            logger.error(
                "chunk_recovery_failed",
                chunk_id=chunk.id,
                error=str(e),
            )
            return {"success": False, "error": str(e), "chunk_id": chunk.id}

    async def recover_orphaned_chunk(self, chunk: DocumentOCRChunk) -> dict:
        """Recover a single orphaned PENDING chunk by re-dispatching it.

        Unlike stale PROCESSING chunks, orphaned PENDING chunks just need
        to be re-dispatched - they never started processing.

        Args:
            chunk: The orphaned PENDING chunk.

        Returns:
            Dictionary with recovery result.
        """
        try:
            # Get fresh chunk state
            current_chunk = await self.chunk_service.get_chunk(chunk.id)
            if not current_chunk:
                return {
                    "success": False,
                    "error": "Chunk not found",
                    "chunk_id": chunk.id,
                }

            if current_chunk.status != ChunkStatus.PENDING:
                return {
                    "success": False,
                    "error": f"Chunk no longer pending (current: {current_chunk.status.value})",
                    "chunk_id": chunk.id,
                }

            # Re-dispatch the chunk task
            self._redispatch_chunk_task(current_chunk)

            logger.info(
                "orphaned_chunk_redispatched",
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
            )

            return {
                "success": True,
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "action": "redispatched",
            }

        except Exception as e:
            logger.error(
                "orphaned_chunk_recovery_failed",
                chunk_id=chunk.id,
                error=str(e),
            )
            return {"success": False, "error": str(e), "chunk_id": chunk.id}

    async def recover_failed_chunk(self, chunk: DocumentOCRChunk) -> dict:
        """Recover a single FAILED chunk by resetting to PENDING and re-dispatching.

        Story 19.1+: Auto-retry chunks that failed due to transient errors.

        Args:
            chunk: The FAILED chunk to retry.

        Returns:
            Dictionary with recovery result.
        """
        try:
            # Get fresh chunk state
            current_chunk = await self.chunk_service.get_chunk(chunk.id)
            if not current_chunk:
                return {
                    "success": False,
                    "error": "Chunk not found",
                    "chunk_id": chunk.id,
                }

            if current_chunk.status != ChunkStatus.FAILED:
                return {
                    "success": False,
                    "error": f"Chunk no longer failed (current: {current_chunk.status.value})",
                    "chunk_id": chunk.id,
                }

            # Parse recovery attempts
            recovery_attempts = self._get_failed_recovery_attempts(current_chunk)

            # Max retries for failed chunks (separate from stale recovery)
            max_failed_retries = 3

            if recovery_attempts >= max_failed_retries:
                logger.warning(
                    "failed_chunk_max_retries_exceeded",
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    recovery_attempts=recovery_attempts,
                )
                return {
                    "success": False,
                    "error": f"Max failed retries ({max_failed_retries}) exceeded",
                    "chunk_id": chunk.id,
                    "action": "skipped",
                }

            # Reset to pending for retry
            await self.chunk_service.reset_chunk_for_retry(chunk.id)

            # Update error message to track recovery attempts
            await self.chunk_service.update_status(
                chunk.id,
                ChunkStatus.PENDING,
                error_message=f"failed_auto_retry_{recovery_attempts + 1}",
            )

            # Re-dispatch the chunk task
            self._redispatch_chunk_task(current_chunk)

            logger.info(
                "failed_chunk_recovered",
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                recovery_attempt=recovery_attempts + 1,
                original_error=chunk.error_message[:100] if chunk.error_message else None,
            )

            return {
                "success": True,
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "recovery_attempt": recovery_attempts + 1,
                "action": "reset_and_redispatched",
            }

        except Exception as e:
            logger.error(
                "failed_chunk_recovery_error",
                chunk_id=chunk.id,
                error=str(e),
            )
            return {"success": False, "error": str(e), "chunk_id": chunk.id}

    def _get_failed_recovery_attempts(self, chunk: DocumentOCRChunk) -> int:
        """Extract failed recovery attempts from error_message metadata."""
        if not chunk.error_message:
            return 0
        if "failed_auto_retry_" in chunk.error_message:
            try:
                return int(chunk.error_message.split("_")[-1])
            except (ValueError, IndexError):
                pass
        return 0

    def _get_recovery_attempts(self, chunk: DocumentOCRChunk) -> int:
        """Extract recovery attempts from error_message metadata."""
        if not chunk.error_message:
            return 0
        if "worker_timeout_recovery_" in chunk.error_message:
            try:
                return int(chunk.error_message.split("_")[-1])
            except (ValueError, IndexError):
                pass
        return 0

    def _redispatch_chunk_task(self, chunk: DocumentOCRChunk) -> None:
        """Re-dispatch Celery task for recovered chunk."""
        from app.workers.tasks.chunked_document_tasks import process_single_chunk

        # Get the job_id from processing_jobs table if available
        job_id = self._get_job_id_for_document(chunk.document_id)

        process_single_chunk.apply_async(
            kwargs={
                "document_id": chunk.document_id,
                "matter_id": chunk.matter_id,
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "job_id": job_id,
            },
            countdown=5,  # Small delay to avoid immediate retry storm
        )

    def _get_job_id_for_document(self, document_id: str) -> str | None:
        """Get the job ID for a document from processing_jobs table."""
        try:
            from app.services.supabase.client import get_service_client

            client = get_service_client()
            response = (
                client.table("processing_jobs")
                .select("id")
                .eq("document_id", document_id)
                .eq("status", "PROCESSING")
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]["id"]
        except Exception as e:
            logger.warning(
                "failed_to_get_job_id",
                document_id=document_id,
                error=str(e),
            )
        return None

    async def recover_all_stale_chunks(self) -> dict:
        """Find and recover all stale chunks (PROCESSING, orphaned PENDING, and retriable FAILED)."""
        # 1. Recover chunks stuck in PROCESSING
        stale_chunks = await self.find_stale_chunks()
        stale_results = []

        if stale_chunks:
            logger.info(
                "stale_processing_chunks_found",
                count=len(stale_chunks),
                chunk_ids=[c.id for c in stale_chunks],
            )
            for chunk in stale_chunks:
                result = await self.recover_stale_chunk(chunk)
                result["recovery_type"] = "stale_processing"
                stale_results.append(result)

        # 2. Recover orphaned PENDING chunks (never picked up by worker)
        orphaned_chunks = await self.find_orphaned_pending_chunks()
        orphan_results = []

        if orphaned_chunks:
            logger.info(
                "orphaned_pending_chunks_found",
                count=len(orphaned_chunks),
                chunk_ids=[c.id for c in orphaned_chunks],
            )
            for chunk in orphaned_chunks:
                result = await self.recover_orphaned_chunk(chunk)
                result["recovery_type"] = "orphaned_pending"
                orphan_results.append(result)

        # 3. Recover FAILED chunks with retriable errors (asyncio/event loop issues)
        failed_chunks = await self.find_retriable_failed_chunks()
        failed_results = []

        if failed_chunks:
            logger.info(
                "retriable_failed_chunks_found",
                count=len(failed_chunks),
                chunk_ids=[c.id for c in failed_chunks],
            )
            for chunk in failed_chunks:
                result = await self.recover_failed_chunk(chunk)
                result["recovery_type"] = "failed_retry"
                failed_results.append(result)

        # Combine results
        all_results = stale_results + orphan_results + failed_results

        if not all_results:
            logger.debug("no_chunks_to_recover")
            return {
                "recovered": 0,
                "failed": 0,
                "total": 0,
                "stale_processing": 0,
                "orphaned_pending": 0,
                "failed_retry": 0,
                "chunks": [],
            }

        recovered = sum(1 for r in all_results if r.get("success"))
        failed = sum(1 for r in all_results if not r.get("success"))
        stale_recovered = sum(1 for r in stale_results if r.get("success"))
        orphan_recovered = sum(1 for r in orphan_results if r.get("success"))
        failed_recovered = sum(1 for r in failed_results if r.get("success"))

        logger.info(
            "batch_chunk_recovery_complete",
            total=len(all_results),
            recovered=recovered,
            failed=failed,
            stale_processing_recovered=stale_recovered,
            orphaned_pending_recovered=orphan_recovered,
            failed_retry_recovered=failed_recovered,
        )

        return {
            "recovered": recovered,
            "failed": failed,
            "total": len(all_results),
            "stale_processing": stale_recovered,
            "orphaned_pending": orphan_recovered,
            "failed_retry": failed_recovered,
            "chunks": all_results,
        }


@lru_cache(maxsize=1)
def get_chunk_recovery_service() -> ChunkRecoveryService:
    """Get or create the ChunkRecoveryService singleton."""
    return ChunkRecoveryService()
