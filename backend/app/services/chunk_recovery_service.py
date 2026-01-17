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
        """Find and recover all stale chunks."""
        stale_chunks = await self.find_stale_chunks()

        if not stale_chunks:
            logger.debug("no_stale_chunks_found")
            return {"recovered": 0, "failed": 0, "total": 0, "chunks": []}

        logger.info(
            "stale_chunks_found",
            count=len(stale_chunks),
            chunk_ids=[c.id for c in stale_chunks],
        )

        results = []
        for chunk in stale_chunks:
            result = await self.recover_stale_chunk(chunk)
            results.append(result)

        recovered = sum(1 for r in results if r.get("success"))
        failed = sum(1 for r in results if not r.get("success"))

        logger.info(
            "batch_chunk_recovery_complete",
            total=len(stale_chunks),
            recovered=recovered,
            failed=failed,
        )

        return {
            "recovered": recovered,
            "failed": failed,
            "total": len(stale_chunks),
            "chunks": results,
        }


@lru_cache(maxsize=1)
def get_chunk_recovery_service() -> ChunkRecoveryService:
    """Get or create the ChunkRecoveryService singleton."""
    return ChunkRecoveryService()
