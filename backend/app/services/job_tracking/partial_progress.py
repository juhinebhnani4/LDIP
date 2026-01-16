"""Partial Progress Preservation for Document Processing.

Story 2c-3: Background Job Status Tracking and Retry

This module provides utilities for tracking granular progress within
processing stages, allowing jobs to resume from where they left off
on retry rather than starting from scratch.

Key concepts:
- Each stage tracks which items (pages, chunks) have been processed
- On retry, already-processed items are skipped
- Progress metadata is persisted to the job record
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.job_tracking.tracker import (
    JobTrackingService,
    get_job_tracking_service,
)

logger = structlog.get_logger(__name__)


@dataclass
class StageProgress:
    """Tracks progress within a single processing stage.

    Attributes:
        stage_name: Name of the stage (ocr, chunking, embedding, etc.)
        total_items: Total number of items to process
        processed_items: Set of processed item identifiers
        failed_items: Set of failed item identifiers with error info
        last_item_id: Last successfully processed item ID
        started_at: When stage processing started
    """

    stage_name: str
    total_items: int = 0
    processed_items: set[str] = field(default_factory=set)
    failed_items: dict[str, str] = field(default_factory=dict)  # item_id -> error
    last_item_id: str | None = None
    started_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stage_name": self.stage_name,
            "total_items": self.total_items,
            "processed_items": list(self.processed_items),
            "failed_items": self.failed_items,
            "last_item_id": self.last_item_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "progress_pct": self.progress_pct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageProgress:
        """Create from dictionary."""
        started_at = None
        if data.get("started_at"):
            with contextlib.suppress(ValueError, TypeError):
                started_at = datetime.fromisoformat(data["started_at"])

        return cls(
            stage_name=data.get("stage_name", ""),
            total_items=data.get("total_items", 0),
            processed_items=set(data.get("processed_items", [])),
            failed_items=data.get("failed_items", {}),
            last_item_id=data.get("last_item_id"),
            started_at=started_at,
        )

    @property
    def progress_pct(self) -> int:
        """Calculate progress percentage within stage."""
        if self.total_items == 0:
            return 0
        processed = len(self.processed_items)
        return min(100, int((processed / self.total_items) * 100))

    def mark_processed(self, item_id: str) -> None:
        """Mark an item as processed."""
        self.processed_items.add(item_id)
        self.last_item_id = item_id

    def mark_failed(self, item_id: str, error: str) -> None:
        """Mark an item as failed."""
        self.failed_items[item_id] = error

    def is_processed(self, item_id: str) -> bool:
        """Check if an item has already been processed."""
        return item_id in self.processed_items

    def get_remaining_items(self, all_items: list[str]) -> list[str]:
        """Get items that haven't been processed yet."""
        return [item for item in all_items if item not in self.processed_items]


class PartialProgressTracker:
    """Tracks partial progress for a processing job.

    Enables jobs to resume from where they left off on retry by:
    1. Storing processed item IDs in job metadata
    2. Providing methods to check if items are already processed
    3. Persisting progress to database for durability

    Example:
        >>> tracker = PartialProgressTracker(job_id="job-123")
        >>> progress = tracker.get_or_create_stage("embedding")
        >>> progress.total_items = 100
        >>>
        >>> for chunk in chunks:
        ...     if progress.is_processed(chunk.id):
        ...         continue  # Skip already-processed
        ...     process_chunk(chunk)
        ...     progress.mark_processed(chunk.id)
        ...     tracker.save_progress(progress)  # Persist periodically
    """

    def __init__(
        self,
        job_id: str,
        matter_id: str | None = None,
        job_tracker: JobTrackingService | None = None,
    ) -> None:
        """Initialize the tracker.

        Args:
            job_id: Processing job UUID.
            matter_id: Matter UUID for broadcasting.
            job_tracker: Optional JobTrackingService instance (for testing).
        """
        self.job_id = job_id
        self.matter_id = matter_id
        self._job_tracker = job_tracker
        self._stages: dict[str, StageProgress] = {}
        self._loaded = False

    @property
    def job_tracker(self) -> JobTrackingService:
        """Get or create job tracker instance."""
        if self._job_tracker is None:
            self._job_tracker = get_job_tracking_service()
        return self._job_tracker

    def _load_from_job_metadata(self) -> None:
        """Load progress from job metadata."""
        if self._loaded:
            return

        try:
            import asyncio

            job = asyncio.run(self.job_tracker.get_job(self.job_id))
            if job and job.metadata:
                partial_progress = job.metadata.get("partial_progress", {})
                for stage_name, stage_data in partial_progress.items():
                    self._stages[stage_name] = StageProgress.from_dict(stage_data)

        except Exception as e:
            logger.warning(
                "partial_progress_load_failed",
                job_id=self.job_id,
                error=str(e),
            )

        self._loaded = True

    def get_or_create_stage(self, stage_name: str) -> StageProgress:
        """Get or create progress tracking for a stage.

        Args:
            stage_name: Name of the processing stage.

        Returns:
            StageProgress instance for the stage.
        """
        self._load_from_job_metadata()

        if stage_name not in self._stages:
            self._stages[stage_name] = StageProgress(
                stage_name=stage_name,
                started_at=datetime.now(UTC),
            )

        return self._stages[stage_name]

    def save_progress(self, stage: StageProgress, force: bool = False) -> None:
        """Persist stage progress to job metadata.

        By default, only saves every 10th item to reduce database writes.
        Use force=True to save immediately (e.g., on stage completion).

        Args:
            stage: StageProgress to persist.
            force: If True, save immediately regardless of count.
        """
        # Only save every 10 items unless forced
        processed_count = len(stage.processed_items)
        if not force and processed_count % 10 != 0:
            return

        try:
            import asyncio

            async def _save_progress_async():
                job = await self.job_tracker.get_job(self.job_id)
                if not job:
                    return

                # Update metadata with partial progress
                metadata = job.metadata or {}
                if "partial_progress" not in metadata:
                    metadata["partial_progress"] = {}

                metadata["partial_progress"][stage.stage_name] = stage.to_dict()

                # Save updated metadata
                from app.models.job import ProcessingJobUpdate

                update = ProcessingJobUpdate(metadata=metadata)
                await self.job_tracker.update_job(self.job_id, update)

                logger.debug(
                    "partial_progress_saved",
                    job_id=self.job_id,
                    stage=stage.stage_name,
                    processed=processed_count,
                    total=stage.total_items,
                )

            asyncio.run(_save_progress_async())

        except Exception as e:
            logger.warning(
                "partial_progress_save_failed",
                job_id=self.job_id,
                stage=stage.stage_name,
                error=str(e),
            )

    def clear_stage(self, stage_name: str) -> None:
        """Clear progress for a stage (e.g., when starting fresh).

        Args:
            stage_name: Name of the stage to clear.
        """
        if stage_name in self._stages:
            del self._stages[stage_name]

        try:
            import asyncio

            async def _clear_stage_async():
                job = await self.job_tracker.get_job(self.job_id)
                if job and job.metadata:
                    metadata = job.metadata
                    if "partial_progress" in metadata and stage_name in metadata["partial_progress"]:
                        del metadata["partial_progress"][stage_name]

                        from app.models.job import ProcessingJobUpdate

                        update = ProcessingJobUpdate(metadata=metadata)
                        await self.job_tracker.update_job(self.job_id, update)

            asyncio.run(_clear_stage_async())

        except Exception as e:
            logger.warning(
                "partial_progress_clear_failed",
                job_id=self.job_id,
                stage=stage_name,
                error=str(e),
            )

    def get_stage_summary(self) -> dict[str, dict[str, Any]]:
        """Get summary of all stage progress.

        Returns:
            Dictionary of stage name -> progress summary.
        """
        self._load_from_job_metadata()
        return {name: stage.to_dict() for name, stage in self._stages.items()}


def create_progress_tracker(
    job_id: str | None,
    matter_id: str | None = None,
    job_tracker: JobTrackingService | None = None,
) -> PartialProgressTracker | None:
    """Create a partial progress tracker for a job.

    Returns None if job_id is not provided (job tracking disabled).

    Args:
        job_id: Processing job UUID.
        matter_id: Matter UUID.
        job_tracker: Optional JobTrackingService instance.

    Returns:
        PartialProgressTracker or None.
    """
    if not job_id:
        return None

    return PartialProgressTracker(
        job_id=job_id,
        matter_id=matter_id,
        job_tracker=job_tracker,
    )
