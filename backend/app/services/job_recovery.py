"""Job Recovery Service for detecting and recovering stale/stuck jobs.

This service handles:
1. Detection of jobs stuck in PROCESSING state beyond timeout
2. Automatic recovery by re-queuing stuck jobs
3. Document status reset when jobs are recovered
4. Logging and alerting for stuck job detection

Configuration:
- JOB_STALE_TIMEOUT_MINUTES: How long a job can be in PROCESSING (default: 30)
- JOB_MAX_RECOVERY_RETRIES: Max auto-recovery attempts (default: 3)
- JOB_RECOVERY_ENABLED: Master switch for auto-recovery (default: True)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings
from app.models.document import DocumentStatus
from app.models.job import JobStatus

if TYPE_CHECKING:
    from supabase import Client

logger = structlog.get_logger(__name__)
settings = get_settings()


class JobRecoveryService:
    """Service for detecting and recovering stale/stuck jobs."""

    def __init__(self, supabase: Client) -> None:
        """Initialize job recovery service.

        Args:
            supabase: Supabase client for database operations.
        """
        self.supabase = supabase

    async def find_stale_jobs(self, timeout_minutes: int | None = None) -> list[dict]:
        """Find jobs that have been stuck in PROCESSING state.

        A job is considered stale if:
        1. It has a heartbeat_at field and it's older than the timeout (preferred)
        2. OR it has no heartbeat_at and updated_at is older than the timeout (fallback)

        Using heartbeat_at when available is more accurate because:
        - updated_at changes with any field update
        - heartbeat_at specifically indicates the job is still actively running

        Args:
            timeout_minutes: Override for stale timeout. Uses config default if None.

        Returns:
            List of stale job records.
        """
        timeout = timeout_minutes or settings.job_stale_timeout_minutes
        cutoff_time = datetime.now(UTC) - timedelta(minutes=timeout)

        try:
            # Find PROCESSING jobs - we'll filter staleness in code
            # because we need to check heartbeat_at OR updated_at
            # Note: heartbeat_at column may not exist in all deployments,
            # so we exclude it from the query and rely on updated_at fallback
            response = self.supabase.table("processing_jobs").select(
                "id, matter_id, document_id, job_type, status, created_at, updated_at, "
                "current_stage, retry_count, metadata"
            ).eq(
                "status", JobStatus.PROCESSING.value
            ).execute()

            all_processing_jobs = response.data or []
            stale_jobs = []

            for job in all_processing_jobs:
                # Use updated_at for staleness check
                # (heartbeat_at column removed from query for compatibility)
                updated_at = job.get("updated_at")
                if not updated_at:
                    continue

                last_activity = datetime.fromisoformat(
                    updated_at.replace("Z", "+00:00")
                )

                # Check if job is stale
                if last_activity < cutoff_time:
                    stale_jobs.append(job)

            if stale_jobs:
                logger.warning(
                    "stale_jobs_detected",
                    count=len(stale_jobs),
                    timeout_minutes=timeout,
                    job_ids=[j["id"] for j in stale_jobs],
                )

            return stale_jobs

        except Exception as e:
            logger.error("stale_job_detection_failed", error=str(e))
            return []

    async def recover_stale_job(self, job_id: str) -> dict:
        """Attempt to recover a single stale job.

        Recovery process:
        1. Check if job is still stale (not updated since detection)
        2. Check recovery attempt count
        3. Reset job to QUEUED status
        4. Reset associated document to PENDING status
        5. Re-dispatch Celery task

        Args:
            job_id: The job ID to recover.

        Returns:
            Recovery result with status and details.
        """
        try:
            # Get current job state
            job_response = self.supabase.table("processing_jobs").select(
                "id, matter_id, document_id, job_type, status, updated_at, "
                "retry_count, metadata, current_stage"
            ).eq("id", job_id).single().execute()

            job = job_response.data
            if not job:
                return {"success": False, "error": "Job not found", "job_id": job_id}

            # Verify job is still stale
            if job["status"] != JobStatus.PROCESSING.value:
                return {
                    "success": False,
                    "error": f"Job no longer in PROCESSING state (current: {job['status']})",
                    "job_id": job_id,
                }

            # Check recovery attempt count
            metadata = job.get("metadata") or {}
            recovery_attempts = metadata.get("recovery_attempts", 0)

            if recovery_attempts >= settings.job_max_recovery_retries:
                # Mark as failed instead of recovering again
                await self._mark_job_permanently_failed(job_id, job)
                return {
                    "success": False,
                    "error": f"Max recovery attempts ({settings.job_max_recovery_retries}) exceeded",
                    "job_id": job_id,
                    "action": "marked_failed",
                }

            # Reset job to QUEUED
            new_metadata = {
                **metadata,
                "recovery_attempts": recovery_attempts + 1,
                "last_recovery_at": datetime.now(UTC).isoformat(),
                "recovered_from_stage": job.get("current_stage"),
            }

            self.supabase.table("processing_jobs").update({
                "status": JobStatus.QUEUED.value,
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": new_metadata,
                "error_message": None,  # Clear previous error
            }).eq("id", job_id).execute()

            # Reset document status to PENDING if document exists
            if job.get("document_id"):
                await self._reset_document_status(job["document_id"])

            # Re-dispatch the Celery task
            await self._redispatch_task(job)

            logger.info(
                "job_recovered",
                job_id=job_id,
                document_id=job.get("document_id"),
                recovery_attempt=recovery_attempts + 1,
                previous_stage=job.get("current_stage"),
            )

            return {
                "success": True,
                "job_id": job_id,
                "recovery_attempt": recovery_attempts + 1,
                "action": "requeued",
            }

        except Exception as e:
            logger.error("job_recovery_failed", job_id=job_id, error=str(e))
            return {"success": False, "error": str(e), "job_id": job_id}

    async def recover_all_stale_jobs(self) -> dict:
        """Find and recover all stale jobs.

        Returns:
            Summary of recovery operations.
        """
        if not settings.job_recovery_enabled:
            logger.info("job_recovery_disabled")
            return {"skipped": True, "reason": "Job recovery disabled in config"}

        stale_jobs = await self.find_stale_jobs()

        if not stale_jobs:
            return {"recovered": 0, "failed": 0, "jobs": []}

        results = []
        for job in stale_jobs:
            result = await self.recover_stale_job(job["id"])
            results.append(result)

        recovered = sum(1 for r in results if r.get("success"))
        failed = sum(1 for r in results if not r.get("success"))

        logger.info(
            "batch_job_recovery_complete",
            total=len(stale_jobs),
            recovered=recovered,
            failed=failed,
        )

        return {
            "recovered": recovered,
            "failed": failed,
            "total": len(stale_jobs),
            "jobs": results,
        }

    async def _reset_document_status(self, document_id: str) -> None:
        """Reset document status to PENDING for re-processing.

        Args:
            document_id: The document ID to reset.
        """
        try:
            self.supabase.table("documents").update({
                "status": DocumentStatus.PENDING.value,
                "updated_at": datetime.now(UTC).isoformat(),
            }).eq("id", document_id).execute()

            logger.debug("document_status_reset", document_id=document_id)

        except Exception as e:
            logger.error(
                "document_status_reset_failed",
                document_id=document_id,
                error=str(e),
            )

    async def _mark_job_permanently_failed(self, job_id: str, job: dict) -> None:
        """Mark a job as permanently failed after max recovery attempts.

        Args:
            job_id: The job ID.
            job: The job record.
        """
        try:
            self.supabase.table("processing_jobs").update({
                "status": JobStatus.FAILED.value,
                "updated_at": datetime.now(UTC).isoformat(),
                "error_message": f"Job failed after {settings.job_max_recovery_retries} recovery attempts",
            }).eq("id", job_id).execute()

            # Also update document status
            if job.get("document_id"):
                self.supabase.table("documents").update({
                    "status": DocumentStatus.FAILED.value,
                    "updated_at": datetime.now(UTC).isoformat(),
                }).eq("id", job["document_id"]).execute()

            logger.warning(
                "job_marked_permanently_failed",
                job_id=job_id,
                document_id=job.get("document_id"),
                recovery_attempts=settings.job_max_recovery_retries,
            )

        except Exception as e:
            logger.error(
                "mark_job_failed_error",
                job_id=job_id,
                error=str(e),
            )

    async def _redispatch_task(self, job: dict) -> None:
        """Re-dispatch the Celery task for a recovered job.

        Args:
            job: The job record to redispatch.
        """
        try:
            from app.workers.tasks.document_tasks import process_document

            document_id = job.get("document_id")
            if document_id:
                # Dispatch with countdown to avoid immediate retry storm
                process_document.apply_async(
                    args=[document_id],
                    countdown=5,  # 5 second delay
                )
                logger.debug(
                    "task_redispatched",
                    job_id=job["id"],
                    document_id=document_id,
                )

        except Exception as e:
            logger.error(
                "task_redispatch_failed",
                job_id=job["id"],
                error=str(e),
            )

    async def get_recovery_stats(self) -> dict:
        """Get statistics about job recovery.

        Returns:
            Dictionary with recovery statistics.
        """
        try:
            # Count jobs by status
            stats_response = self.supabase.rpc(
                "get_job_queue_stats"
            ).execute()

            # Count recently recovered jobs
            one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
            recovered_response = self.supabase.table("processing_jobs").select(
                "id", count="exact"
            ).gte(
                "metadata->>last_recovery_at", one_hour_ago.isoformat()
            ).execute()

            return {
                "queue_stats": stats_response.data,
                "recovered_last_hour": recovered_response.count or 0,
                "config": {
                    "stale_timeout_minutes": settings.job_stale_timeout_minutes,
                    "max_recovery_retries": settings.job_max_recovery_retries,
                    "recovery_enabled": settings.job_recovery_enabled,
                },
            }

        except Exception as e:
            logger.error("get_recovery_stats_failed", error=str(e))
            return {"error": str(e)}

    async def recover_with_chunked_processing(self, job: dict) -> dict:
        """Recover a job that failed due to page limit by using chunked processing.

        Story 19.3: Auto-convert SKIPPED jobs to chunked processing.

        Creates chunk records and dispatches chunked processing task for
        documents that exceeded the page limit.

        Args:
            job: The job record with document_id.

        Returns:
            Dict with recovery result including success flag and details.
        """
        from io import BytesIO

        import pypdf

        job_id = job.get("id")
        document_id = job.get("document_id")
        matter_id = job.get("matter_id")

        if not document_id:
            return {
                "success": False,
                "error": "No document_id in job",
                "job_id": job_id,
            }

        try:
            # Get document details
            doc_response = self.supabase.table("documents").select(
                "id, storage_path, filename"
            ).eq("id", document_id).limit(1).execute()

            if not doc_response.data:
                return {
                    "success": False,
                    "error": "Document not found",
                    "job_id": job_id,
                }

            document = doc_response.data[0]
            storage_path = document.get("storage_path")

            if not storage_path:
                return {
                    "success": False,
                    "error": "Document missing storage path",
                    "job_id": job_id,
                }

            # Get page count from the PDF
            from app.services.storage_service import get_storage_service
            storage_service = get_storage_service()
            pdf_bytes = storage_service.download_file(storage_path)
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            page_count = len(reader.pages)
            del reader
            del pdf_bytes

            # Create chunk records
            from app.services.pdf_router import CHUNK_SIZE
            chunks = await self._create_chunk_records_for_document(
                document_id=document_id,
                matter_id=matter_id,
                page_count=page_count,
                chunk_size=CHUNK_SIZE,
            )

            # Update job status and metadata
            metadata = job.get("metadata") or {}
            metadata["converted_to_chunked"] = True
            metadata["page_count"] = page_count
            metadata["chunk_count"] = len(chunks)
            metadata["converted_at"] = datetime.now(UTC).isoformat()

            self.supabase.table("processing_jobs").update({
                "status": JobStatus.QUEUED.value,
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": metadata,
                "error_message": None,
                "error_code": None,
            }).eq("id", job_id).execute()

            # Reset document status
            self.supabase.table("documents").update({
                "status": DocumentStatus.PROCESSING.value,
                "updated_at": datetime.now(UTC).isoformat(),
            }).eq("id", document_id).execute()

            # Dispatch chunked processing
            from app.workers.tasks.chunked_document_tasks import process_document_chunked

            process_document_chunked.apply_async(
                kwargs={
                    "document_id": document_id,
                    "matter_id": matter_id,
                    "job_id": job_id,
                },
                countdown=5,
            )

            logger.info(
                "job_converted_to_chunked",
                job_id=job_id,
                document_id=document_id,
                page_count=page_count,
                chunk_count=len(chunks),
            )

            return {
                "success": True,
                "job_id": job_id,
                "document_id": document_id,
                "action": "converted_to_chunked",
                "page_count": page_count,
                "chunk_count": len(chunks),
            }

        except Exception as e:
            logger.error(
                "chunked_recovery_failed",
                job_id=job_id,
                document_id=document_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": str(e),
                "job_id": job_id,
            }

    async def _create_chunk_records_for_document(
        self,
        document_id: str,
        matter_id: str,
        page_count: int,
        chunk_size: int = 15,
    ) -> list[dict]:
        """Create chunk records for parallel processing.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID.
            page_count: Total pages in document.
            chunk_size: Pages per chunk.

        Returns:
            List of created chunk records.
        """
        from app.models.ocr_chunk import ChunkSpec
        from app.services.ocr_chunk_service import get_ocr_chunk_service

        chunk_service = get_ocr_chunk_service()

        # Build chunk specs
        specs = []
        page_start = 1
        chunk_index = 0

        while page_start <= page_count:
            page_end = min(page_start + chunk_size - 1, page_count)

            specs.append(ChunkSpec(
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
            ))

            page_start = page_end + 1
            chunk_index += 1

        # Create chunks in database
        chunks = await chunk_service.create_chunks_for_document(
            document_id=document_id,
            matter_id=matter_id,
            chunk_specs=specs,
        )

        logger.info(
            "chunk_records_created_for_recovery",
            document_id=document_id,
            chunk_count=len(chunks),
            page_count=page_count,
        )

        return [{"id": c.id, "chunk_index": c.chunk_index} for c in chunks]


def get_job_recovery_service(supabase: Client) -> JobRecoveryService:
    """Factory function to get job recovery service instance.

    Args:
        supabase: Supabase client.

    Returns:
        JobRecoveryService instance.
    """
    return JobRecoveryService(supabase)
