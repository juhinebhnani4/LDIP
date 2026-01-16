"""Chunk Progress Tracker for large document parallel processing.

Integrates OCRChunkService with JobTrackingService to provide
granular progress updates during large document OCR processing.

Story 15.3: Integrate Chunk Progress with Job Tracking
"""

from functools import lru_cache

import structlog

from app.models.job import JobStatus
from app.models.ocr_chunk import ChunkProgress
from app.services.job_tracking.tracker import (
    JobTrackingService,
    get_job_tracking_service,
)
from app.services.ocr_chunk_service import (
    OCRChunkService,
    get_ocr_chunk_service,
)
from app.services.pubsub_service import broadcast_job_progress

logger = structlog.get_logger(__name__)


def format_chunk_failure_message(
    chunk_index: int,
    page_start: int,
    page_end: int,
    error_message: str,
) -> str:
    """Format chunk failure for user display.

    Args:
        chunk_index: Zero-indexed chunk position.
        page_start: First page of chunk (1-indexed).
        page_end: Last page of chunk (1-indexed).
        error_message: Error description.

    Returns:
        Human-readable failure message.
    """
    return f"Chunk {chunk_index + 1} (pages {page_start}-{page_end}) failed: {error_message}"


class ChunkProgressTracker:
    """Tracks chunk processing progress and updates job status.

    Integrates OCRChunkService with JobTrackingService to provide
    granular progress updates during large document processing.

    Example:
        >>> tracker = ChunkProgressTracker()
        >>> await tracker.update_chunk_progress(
        ...     job_id="job-123",
        ...     document_id="doc-456",
        ...     matter_id="matter-789",
        ... )
    """

    def __init__(
        self,
        job_tracker: JobTrackingService | None = None,
        chunk_service: OCRChunkService | None = None,
    ) -> None:
        """Initialize chunk progress tracker.

        Args:
            job_tracker: Optional job tracking service (for testing).
            chunk_service: Optional chunk service (for testing).
        """
        self._job_tracker = job_tracker
        self._chunk_service = chunk_service

    @property
    def job_tracker(self) -> JobTrackingService:
        """Get job tracking service instance."""
        if self._job_tracker is None:
            self._job_tracker = get_job_tracking_service()
        return self._job_tracker

    @property
    def chunk_service(self) -> OCRChunkService:
        """Get OCR chunk service instance."""
        if self._chunk_service is None:
            self._chunk_service = get_ocr_chunk_service()
        return self._chunk_service

    async def update_chunk_progress(
        self,
        job_id: str,
        document_id: str,
        matter_id: str,
    ) -> ChunkProgress:
        """Update job progress based on chunk completion status.

        Called after each chunk completes to update the job's
        progress and broadcast updates to the frontend.

        Args:
            job_id: Job UUID.
            document_id: Document UUID.
            matter_id: Matter UUID for broadcasting.

        Returns:
            Current ChunkProgress with status counts.
        """
        progress = await self.chunk_service.get_chunk_progress(document_id)

        # Calculate percentage based on completed chunks only
        # (failed chunks are handled separately)
        completed = progress.completed
        total = progress.total
        progress_pct = int((completed / total) * 100) if total > 0 else 0

        stage_message = f"Processing chunk {completed}/{total}"

        await self.job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            stage=stage_message,
            progress_pct=progress_pct,
        )

        # Broadcast to frontend
        broadcast_job_progress(
            matter_id=matter_id,
            job_id=job_id,
            progress_pct=progress_pct,
            stage=stage_message,
        )

        logger.info(
            "chunk_progress_updated",
            job_id=job_id,
            document_id=document_id,
            completed=completed,
            total=total,
            failed=progress.failed,
            progress_pct=progress_pct,
        )

        return progress

    async def start_merge_stage(
        self,
        job_id: str,
        document_id: str,
        matter_id: str,
    ) -> None:
        """Indicate that all chunks completed and merge is starting.

        Called when all chunks have completed successfully and
        the results are being merged.

        Args:
            job_id: Job UUID.
            document_id: Document UUID.
            matter_id: Matter UUID for broadcasting.
        """
        stage_message = "Merging OCR results"

        await self.job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            stage=stage_message,
            progress_pct=95,  # Merge is near completion
        )

        # Broadcast to frontend
        broadcast_job_progress(
            matter_id=matter_id,
            job_id=job_id,
            progress_pct=95,
            stage=stage_message,
        )

        logger.info(
            "chunk_merge_stage_started",
            job_id=job_id,
            document_id=document_id,
        )

    async def report_chunk_failure(
        self,
        job_id: str,
        document_id: str,
        matter_id: str,
        chunk_index: int,
        page_start: int,
        page_end: int,
        error_message: str,
    ) -> None:
        """Report a chunk processing failure.

        Updates job status with detailed failure information
        including which chunk and page range failed.

        Args:
            job_id: Job UUID.
            document_id: Document UUID.
            matter_id: Matter UUID for broadcasting.
            chunk_index: Zero-indexed chunk that failed.
            page_start: First page of failed chunk (1-indexed).
            page_end: Last page of failed chunk (1-indexed).
            error_message: Error description.
        """
        failure_message = format_chunk_failure_message(
            chunk_index=chunk_index,
            page_start=page_start,
            page_end=page_end,
            error_message=error_message,
        )

        # Get current progress for context
        progress = await self.chunk_service.get_chunk_progress(document_id)

        # Don't mark job as failed yet - allow retry
        # Just update with failure information
        stage_message = f"Chunk {chunk_index + 1} failed ({progress.failed} failed, {progress.completed}/{progress.total} completed)"

        await self.job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            stage=stage_message,
            error_message=failure_message,
        )

        # Broadcast failure info
        broadcast_job_progress(
            matter_id=matter_id,
            job_id=job_id,
            progress_pct=progress.progress_pct,
            stage=stage_message,
        )

        logger.warning(
            "chunk_failure_reported",
            job_id=job_id,
            document_id=document_id,
            chunk_index=chunk_index,
            page_start=page_start,
            page_end=page_end,
            error_message=error_message,
            total_failed=progress.failed,
        )

    async def get_progress_summary(
        self,
        document_id: str,
    ) -> dict:
        """Get a summary of chunk processing progress.

        Returns a dict suitable for job metadata.

        Args:
            document_id: Document UUID.

        Returns:
            Dict with progress details for job metadata.
        """
        progress = await self.chunk_service.get_chunk_progress(document_id)

        return {
            "chunk_processing": {
                "total_chunks": progress.total,
                "completed_chunks": progress.completed,
                "failed_chunks": progress.failed,
                "pending_chunks": progress.pending,
                "processing_chunks": progress.processing,
                "progress_pct": progress.progress_pct,
                "is_complete": progress.is_complete,
                "has_failures": progress.has_failures,
            }
        }


@lru_cache(maxsize=1)
def get_chunk_progress_tracker() -> ChunkProgressTracker:
    """Get singleton ChunkProgressTracker instance.

    Returns:
        ChunkProgressTracker instance.
    """
    return ChunkProgressTracker()
