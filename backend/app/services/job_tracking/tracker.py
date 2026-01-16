"""Job Tracking Service for background processing jobs.

Provides database operations for tracking document processing jobs:
- Create and update jobs
- Track stage-level progress
- Support partial progress preservation for recovery
- Matter isolation via RLS

CRITICAL: Always validates matter_id for Layer 4 matter isolation.

NOTE: Uses asyncio.to_thread() to run synchronous Supabase client calls
without blocking the event loop.
"""

import asyncio
from datetime import UTC, datetime
from functools import lru_cache

import structlog

from app.models.job import (
    JobListItem,
    JobQueueStats,
    JobStageHistory,
    JobStatus,
    JobType,
    ProcessingJob,
    ProcessingJobUpdate,
    ProcessingJobWithHistory,
    StageStatus,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class JobTrackingError(Exception):
    """Base exception for job tracking operations."""

    def __init__(
        self,
        message: str,
        code: str = "JOB_TRACKING_ERROR",
    ):
        self.message = message
        self.code = code
        super().__init__(message)


class JobNotFoundError(JobTrackingError):
    """Raised when job is not found."""

    def __init__(self, message: str):
        super().__init__(message, code="JOB_NOT_FOUND")


# =============================================================================
# Service Implementation
# =============================================================================


class JobTrackingService:
    """Service for tracking background processing jobs.

    Handles CRUD operations for:
    - processing_jobs: Job tracking records
    - job_stage_history: Granular stage progress

    CRITICAL: All operations validate matter_id for security.

    All async methods use asyncio.to_thread() to run synchronous Supabase
    client calls without blocking the event loop.

    Example:
        >>> service = JobTrackingService()
        >>> job = await service.create_job(
        ...     matter_id="matter-123",
        ...     document_id="doc-456",
        ...     job_type=JobType.DOCUMENT_PROCESSING,
        ... )
        >>> job.status
        JobStatus.QUEUED
    """

    def __init__(self) -> None:
        """Initialize job tracking service."""
        self._client = None

    @property
    def client(self):
        """Get Supabase client.

        Raises:
            JobTrackingError: If Supabase is not configured.
        """
        if self._client is None:
            self._client = get_supabase_client()
            if self._client is None:
                raise JobTrackingError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                )
        return self._client

    # =========================================================================
    # Job CRUD Operations
    # =========================================================================

    async def create_job(
        self,
        matter_id: str,
        job_type: JobType,
        document_id: str | None = None,
        celery_task_id: str | None = None,
        max_retries: int = 3,
        metadata: dict | None = None,
    ) -> ProcessingJob:
        """Create a new processing job.

        Args:
            matter_id: Matter UUID for isolation.
            job_type: Type of processing job.
            document_id: Optional document UUID.
            celery_task_id: Optional Celery task ID for correlation.
            max_retries: Maximum retry attempts (default 3).
            metadata: Optional initial metadata.

        Returns:
            Created ProcessingJob.

        Raises:
            JobTrackingError: If creation fails.
        """
        def _insert():
            return (
                self.client.table("processing_jobs")
                .insert({
                    "matter_id": matter_id,
                    "document_id": document_id,
                    "job_type": job_type.value,
                    "status": JobStatus.QUEUED.value,
                    "celery_task_id": celery_task_id,
                    "max_retries": max_retries,
                    "metadata": metadata or {},
                })
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)

            if response.data:
                job = self._db_row_to_processing_job(response.data[0])
                logger.info(
                    "job_created",
                    job_id=job.id,
                    matter_id=matter_id,
                    document_id=document_id,
                    job_type=job_type.value,
                )
                return job

            raise JobTrackingError("Failed to create job - no data returned")

        except Exception as e:
            if isinstance(e, JobTrackingError):
                raise
            logger.error("job_create_failed", error=str(e), matter_id=matter_id)
            raise JobTrackingError(f"Failed to create job: {e}")

    async def get_job(
        self,
        job_id: str,
        matter_id: str | None = None,
    ) -> ProcessingJob | None:
        """Get a job by ID.

        Args:
            job_id: Job UUID.
            matter_id: Optional matter UUID for validation.

        Returns:
            ProcessingJob if found, None otherwise.
        """
        def _query():
            query = (
                self.client.table("processing_jobs")
                .select("*")
                .eq("id", job_id)
            )
            if matter_id:
                query = query.eq("matter_id", matter_id)
            return query.limit(1).execute()

        response = await asyncio.to_thread(_query)

        if response.data:
            return self._db_row_to_processing_job(response.data[0])
        return None

    async def get_job_with_history(
        self,
        job_id: str,
        matter_id: str,
    ) -> ProcessingJobWithHistory | None:
        """Get a job with its stage history.

        Args:
            job_id: Job UUID.
            matter_id: Matter UUID for validation.

        Returns:
            ProcessingJobWithHistory if found, None otherwise.
        """
        # Get job
        job = await self.get_job(job_id, matter_id)
        if not job:
            return None

        # Get stage history
        history = await self.get_stage_history(job_id)

        return ProcessingJobWithHistory(
            **job.model_dump(),
            stage_history=history,
        )

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        stage: str | None = None,
        progress_pct: int | None = None,
        error_message: str | None = None,
        error_code: str | None = None,
        matter_id: str | None = None,
    ) -> ProcessingJob | None:
        """Update job status and progress.

        Args:
            job_id: Job UUID.
            status: New status.
            stage: Current stage name.
            progress_pct: Progress percentage (0-100).
            error_message: Error message if failed.
            error_code: Machine-readable error code.
            matter_id: Optional matter UUID for validation.

        Returns:
            Updated ProcessingJob or None if not found.
        """
        update_data: dict = {
            "status": status.value,
            "updated_at": datetime.now(UTC).isoformat(),
        }

        if stage is not None:
            update_data["current_stage"] = stage

        if progress_pct is not None:
            update_data["progress_pct"] = progress_pct

        if error_message is not None:
            update_data["error_message"] = error_message

        if error_code is not None:
            update_data["error_code"] = error_code

        # Set timestamps based on status
        if status == JobStatus.PROCESSING:
            update_data["started_at"] = datetime.now(UTC).isoformat()
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.SKIPPED):
            update_data["completed_at"] = datetime.now(UTC).isoformat()

        def _update():
            query = (
                self.client.table("processing_jobs")
                .update(update_data)
                .eq("id", job_id)
            )
            if matter_id:
                query = query.eq("matter_id", matter_id)
            return query.execute()

        response = await asyncio.to_thread(_update)

        if response.data:
            job = self._db_row_to_processing_job(response.data[0])
            logger.info(
                "job_status_updated",
                job_id=job_id,
                status=status.value,
                stage=stage,
                progress_pct=progress_pct,
            )
            return job

        return None

    async def update_job(
        self,
        job_id: str,
        update: ProcessingJobUpdate,
        matter_id: str | None = None,
    ) -> ProcessingJob | None:
        """Update job with arbitrary fields.

        Args:
            job_id: Job UUID.
            update: Update model with fields to update.
            matter_id: Optional matter UUID for validation.

        Returns:
            Updated ProcessingJob or None if not found.
        """
        update_data = update.model_dump(exclude_none=True)
        update_data["updated_at"] = datetime.now(UTC).isoformat()

        # Convert enum to value if present
        if "status" in update_data and isinstance(update_data["status"], JobStatus):
            update_data["status"] = update_data["status"].value

        def _update():
            query = (
                self.client.table("processing_jobs")
                .update(update_data)
                .eq("id", job_id)
            )
            if matter_id:
                query = query.eq("matter_id", matter_id)
            return query.execute()

        response = await asyncio.to_thread(_update)

        if response.data:
            return self._db_row_to_processing_job(response.data[0])
        return None

    async def increment_retry_count(
        self,
        job_id: str,
        matter_id: str | None = None,
    ) -> ProcessingJob | None:
        """Increment job retry count.

        Args:
            job_id: Job UUID.
            matter_id: Optional matter UUID for validation.

        Returns:
            Updated ProcessingJob or None if not found.
        """
        # Get current job
        job = await self.get_job(job_id, matter_id)
        if not job:
            return None

        new_retry_count = job.retry_count + 1

        def _update():
            query = (
                self.client.table("processing_jobs")
                .update({
                    "retry_count": new_retry_count,
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", job_id)
            )
            if matter_id:
                query = query.eq("matter_id", matter_id)
            return query.execute()

        response = await asyncio.to_thread(_update)

        if response.data:
            logger.info("job_retry_incremented", job_id=job_id, retry_count=new_retry_count)
            return self._db_row_to_processing_job(response.data[0])
        return None

    async def update_job_metadata(
        self,
        job_id: str,
        metadata_update: dict,
        matter_id: str | None = None,
    ) -> ProcessingJob | None:
        """Update job metadata (merge with existing).

        Args:
            job_id: Job UUID.
            metadata_update: Metadata to merge.
            matter_id: Optional matter UUID for validation.

        Returns:
            Updated ProcessingJob or None if not found.
        """
        # Get current job
        job = await self.get_job(job_id, matter_id)
        if not job:
            return None

        # Merge metadata
        new_metadata = {**job.metadata, **metadata_update}

        def _update():
            query = (
                self.client.table("processing_jobs")
                .update({
                    "metadata": new_metadata,
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", job_id)
            )
            if matter_id:
                query = query.eq("matter_id", matter_id)
            return query.execute()

        response = await asyncio.to_thread(_update)

        if response.data:
            return self._db_row_to_processing_job(response.data[0])
        return None

    async def set_estimated_completion(
        self,
        job_id: str,
        estimated_completion: datetime,
        matter_id: str | None = None,
    ) -> ProcessingJob | None:
        """Set job estimated completion time.

        Args:
            job_id: Job UUID.
            estimated_completion: Estimated completion timestamp.
            matter_id: Optional matter UUID for validation.

        Returns:
            Updated ProcessingJob or None if not found.
        """
        def _update():
            query = (
                self.client.table("processing_jobs")
                .update({
                    "estimated_completion": estimated_completion.isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", job_id)
            )
            if matter_id:
                query = query.eq("matter_id", matter_id)
            return query.execute()

        response = await asyncio.to_thread(_update)

        if response.data:
            return self._db_row_to_processing_job(response.data[0])
        return None

    async def heartbeat(
        self,
        job_id: str,
        progress_info: dict | None = None,
    ) -> bool:
        """Send heartbeat for a long-running job.

        This method updates the heartbeat_at timestamp to indicate the job is
        still actively running. Use this during long-running operations like
        OCR or embedding generation to prevent false stale job detection.

        Args:
            job_id: Job UUID.
            progress_info: Optional progress info to merge into metadata
                          (e.g., {"pages_processed": 5, "total_pages": 10}).

        Returns:
            True if heartbeat was recorded, False if job not found.
        """
        now = datetime.now(UTC).isoformat()

        def _update():
            update_data = {
                "heartbeat_at": now,
                "updated_at": now,
            }

            # Optionally merge progress info into metadata
            if progress_info:
                # Get current metadata first
                job_response = (
                    self.client.table("processing_jobs")
                    .select("metadata")
                    .eq("id", job_id)
                    .single()
                    .execute()
                )
                if job_response.data:
                    current_metadata = job_response.data.get("metadata") or {}
                    update_data["metadata"] = {
                        **current_metadata,
                        "heartbeat_progress": progress_info,
                        "last_heartbeat_info": {
                            "timestamp": now,
                            **progress_info,
                        },
                    }

            return (
                self.client.table("processing_jobs")
                .update(update_data)
                .eq("id", job_id)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_update)
            if response.data:
                logger.debug(
                    "job_heartbeat",
                    job_id=job_id,
                    progress_info=progress_info,
                )
                return True
        except Exception as e:
            logger.warning("job_heartbeat_failed", job_id=job_id, error=str(e))

        return False

    def heartbeat_sync(
        self,
        job_id: str,
        progress_info: dict | None = None,
    ) -> bool:
        """Synchronous heartbeat for use in Celery tasks.

        Same as heartbeat() but synchronous for use in non-async contexts.

        Args:
            job_id: Job UUID.
            progress_info: Optional progress info.

        Returns:
            True if heartbeat was recorded, False if failed.
        """
        now = datetime.now(UTC).isoformat()

        try:
            update_data = {
                "heartbeat_at": now,
                "updated_at": now,
            }

            if progress_info:
                job_response = (
                    self.client.table("processing_jobs")
                    .select("metadata")
                    .eq("id", job_id)
                    .single()
                    .execute()
                )
                if job_response.data:
                    current_metadata = job_response.data.get("metadata") or {}
                    update_data["metadata"] = {
                        **current_metadata,
                        "heartbeat_progress": progress_info,
                        "last_heartbeat_info": {
                            "timestamp": now,
                            **progress_info,
                        },
                    }

            response = (
                self.client.table("processing_jobs")
                .update(update_data)
                .eq("id", job_id)
                .execute()
            )

            if response.data:
                logger.debug(
                    "job_heartbeat_sync",
                    job_id=job_id,
                    progress_info=progress_info,
                )
                return True

        except Exception as e:
            logger.warning("job_heartbeat_sync_failed", job_id=job_id, error=str(e))

        return False

    # =========================================================================
    # Stage History Operations
    # =========================================================================

    async def record_stage_start(
        self,
        job_id: str,
        stage_name: str,
        metadata: dict | None = None,
    ) -> JobStageHistory | None:
        """Record stage start.

        Args:
            job_id: Job UUID.
            stage_name: Stage name.
            metadata: Optional stage metadata.

        Returns:
            Created JobStageHistory or None if failed.
        """
        def _insert():
            return (
                self.client.table("job_stage_history")
                .insert({
                    "job_id": job_id,
                    "stage_name": stage_name,
                    "status": StageStatus.IN_PROGRESS.value,
                    "started_at": datetime.now(UTC).isoformat(),
                    "metadata": metadata or {},
                })
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)

            if response.data:
                logger.debug("stage_started", job_id=job_id, stage_name=stage_name)
                return self._db_row_to_stage_history(response.data[0])

        except Exception as e:
            logger.warning("stage_start_failed", job_id=job_id, stage_name=stage_name, error=str(e))

        return None

    async def record_stage_complete(
        self,
        job_id: str,
        stage_name: str,
        metadata: dict | None = None,
    ) -> JobStageHistory | None:
        """Record stage completion.

        Args:
            job_id: Job UUID.
            stage_name: Stage name.
            metadata: Optional metadata to merge.

        Returns:
            Updated JobStageHistory or None if not found.
        """
        # Find existing stage record
        def _find():
            return (
                self.client.table("job_stage_history")
                .select("*")
                .eq("job_id", job_id)
                .eq("stage_name", stage_name)
                .eq("status", StageStatus.IN_PROGRESS.value)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

        response = await asyncio.to_thread(_find)

        if not response.data:
            # Create completed stage if no in-progress found
            return await self._create_completed_stage(job_id, stage_name, metadata)

        stage_id = response.data[0]["id"]
        existing_metadata = response.data[0].get("metadata", {}) or {}

        def _update():
            return (
                self.client.table("job_stage_history")
                .update({
                    "status": StageStatus.COMPLETED.value,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "metadata": {**existing_metadata, **(metadata or {})},
                })
                .eq("id", stage_id)
                .execute()
            )

        update_response = await asyncio.to_thread(_update)

        if update_response.data:
            logger.debug("stage_completed", job_id=job_id, stage_name=stage_name)
            return self._db_row_to_stage_history(update_response.data[0])

        return None

    async def _create_completed_stage(
        self,
        job_id: str,
        stage_name: str,
        metadata: dict | None = None,
    ) -> JobStageHistory | None:
        """Create a completed stage record (for cases where start wasn't recorded)."""
        def _insert():
            now = datetime.now(UTC).isoformat()
            return (
                self.client.table("job_stage_history")
                .insert({
                    "job_id": job_id,
                    "stage_name": stage_name,
                    "status": StageStatus.COMPLETED.value,
                    "started_at": now,
                    "completed_at": now,
                    "metadata": metadata or {},
                })
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)
            if response.data:
                return self._db_row_to_stage_history(response.data[0])
        except Exception as e:
            logger.warning("stage_complete_create_failed", job_id=job_id, stage_name=stage_name, error=str(e))

        return None

    async def record_stage_failure(
        self,
        job_id: str,
        stage_name: str,
        error_message: str,
        metadata: dict | None = None,
    ) -> JobStageHistory | None:
        """Record stage failure.

        Args:
            job_id: Job UUID.
            stage_name: Stage name.
            error_message: Error message.
            metadata: Optional metadata to merge.

        Returns:
            Updated JobStageHistory or None if not found.
        """
        # Find existing stage record
        def _find():
            return (
                self.client.table("job_stage_history")
                .select("*")
                .eq("job_id", job_id)
                .eq("stage_name", stage_name)
                .eq("status", StageStatus.IN_PROGRESS.value)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

        response = await asyncio.to_thread(_find)

        if not response.data:
            # Create failed stage if no in-progress found
            return await self._create_failed_stage(job_id, stage_name, error_message, metadata)

        stage_id = response.data[0]["id"]
        existing_metadata = response.data[0].get("metadata", {}) or {}

        def _update():
            return (
                self.client.table("job_stage_history")
                .update({
                    "status": StageStatus.FAILED.value,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "error_message": error_message,
                    "metadata": {**existing_metadata, **(metadata or {})},
                })
                .eq("id", stage_id)
                .execute()
            )

        update_response = await asyncio.to_thread(_update)

        if update_response.data:
            logger.warning("stage_failed", job_id=job_id, stage_name=stage_name, error=error_message)
            return self._db_row_to_stage_history(update_response.data[0])

        return None

    async def _create_failed_stage(
        self,
        job_id: str,
        stage_name: str,
        error_message: str,
        metadata: dict | None = None,
    ) -> JobStageHistory | None:
        """Create a failed stage record."""
        def _insert():
            now = datetime.now(UTC).isoformat()
            return (
                self.client.table("job_stage_history")
                .insert({
                    "job_id": job_id,
                    "stage_name": stage_name,
                    "status": StageStatus.FAILED.value,
                    "started_at": now,
                    "completed_at": now,
                    "error_message": error_message,
                    "metadata": metadata or {},
                })
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)
            if response.data:
                return self._db_row_to_stage_history(response.data[0])
        except Exception as e:
            logger.warning("stage_failure_create_failed", job_id=job_id, stage_name=stage_name, error=str(e))

        return None

    async def get_stage_history(
        self,
        job_id: str,
    ) -> list[JobStageHistory]:
        """Get all stage history for a job.

        Args:
            job_id: Job UUID.

        Returns:
            List of JobStageHistory records.
        """
        def _query():
            return (
                self.client.table("job_stage_history")
                .select("*")
                .eq("job_id", job_id)
                .order("created_at", desc=False)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        if response.data:
            return [self._db_row_to_stage_history(row) for row in response.data]
        return []

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def list_jobs_for_matter(
        self,
        matter_id: str,
        status_filter: JobStatus | None = None,
        job_type_filter: JobType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProcessingJob]:
        """List all jobs for a matter with optional filters.

        Args:
            matter_id: Matter UUID.
            status_filter: Optional status filter.
            job_type_filter: Optional job type filter.
            limit: Maximum results.
            offset: Offset for pagination.

        Returns:
            List of ProcessingJob records.
        """
        def _query():
            query = (
                self.client.table("processing_jobs")
                .select("*")
                .eq("matter_id", matter_id)
            )

            if status_filter:
                query = query.eq("status", status_filter.value)

            if job_type_filter:
                query = query.eq("job_type", job_type_filter.value)

            # Order by created_at descending (newest first)
            query = query.order("created_at", desc=True)

            # Pagination
            query = query.range(offset, offset + limit - 1)

            return query.execute()

        response = await asyncio.to_thread(_query)

        return [self._db_row_to_processing_job(row) for row in (response.data or [])]

    async def reset_retry_count(
        self,
        job_id: str,
        matter_id: str | None = None,
    ) -> ProcessingJob | None:
        """Reset job retry count to 0.

        Args:
            job_id: Job UUID.
            matter_id: Optional matter UUID for validation.

        Returns:
            Updated ProcessingJob or None if not found.
        """
        def _update():
            query = (
                self.client.table("processing_jobs")
                .update({
                    "retry_count": 0,
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", job_id)
            )
            if matter_id:
                query = query.eq("matter_id", matter_id)
            return query.execute()

        response = await asyncio.to_thread(_update)

        if response.data:
            logger.info("job_retry_count_reset", job_id=job_id)
            return self._db_row_to_processing_job(response.data[0])
        return None

    async def get_jobs_by_matter(
        self,
        matter_id: str,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[JobListItem], int]:
        """Get all jobs for a matter with optional filters.

        Args:
            matter_id: Matter UUID.
            status: Optional status filter.
            job_type: Optional job type filter.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (job list, total count).
        """
        def _query():
            query = (
                self.client.table("processing_jobs")
                .select("*", count="exact")
                .eq("matter_id", matter_id)
            )

            if status:
                query = query.eq("status", status.value)

            if job_type:
                query = query.eq("job_type", job_type.value)

            # Order by created_at descending (newest first)
            query = query.order("created_at", desc=True)

            # Pagination
            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            return query.execute()

        response = await asyncio.to_thread(_query)

        jobs = [self._db_row_to_job_list_item(row) for row in (response.data or [])]
        total = response.count or 0

        return jobs, total

    async def get_jobs_by_document(
        self,
        document_id: str,
        matter_id: str | None = None,
    ) -> list[ProcessingJob]:
        """Get all jobs for a document.

        Args:
            document_id: Document UUID.
            matter_id: Optional matter UUID for validation.

        Returns:
            List of ProcessingJob records.
        """
        def _query():
            query = (
                self.client.table("processing_jobs")
                .select("*")
                .eq("document_id", document_id)
            )
            if matter_id:
                query = query.eq("matter_id", matter_id)
            return query.order("created_at", desc=True).execute()

        response = await asyncio.to_thread(_query)

        if response.data:
            return [self._db_row_to_processing_job(row) for row in response.data]
        return []

    async def get_active_job_for_document(
        self,
        document_id: str,
        matter_id: str | None = None,
    ) -> ProcessingJob | None:
        """Get active (queued/processing) job for a document.

        Args:
            document_id: Document UUID.
            matter_id: Optional matter UUID for validation.

        Returns:
            Active ProcessingJob or None.
        """
        def _query():
            query = (
                self.client.table("processing_jobs")
                .select("*")
                .eq("document_id", document_id)
                .in_("status", [JobStatus.QUEUED.value, JobStatus.PROCESSING.value])
            )
            if matter_id:
                query = query.eq("matter_id", matter_id)
            return query.order("created_at", desc=True).limit(1).execute()

        response = await asyncio.to_thread(_query)

        if response.data:
            return self._db_row_to_processing_job(response.data[0])
        return None

    async def get_queue_stats(
        self,
        matter_id: str,
    ) -> JobQueueStats:
        """Get queue statistics for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            JobQueueStats with counts and averages.
        """
        # Use the database function for efficiency
        def _query():
            return self.client.rpc(
                "get_job_queue_stats",
                {"p_matter_id": matter_id},
            ).execute()

        try:
            response = await asyncio.to_thread(_query)

            if response.data and len(response.data) > 0:
                row = response.data[0]
                return JobQueueStats(
                    queued=row.get("queued", 0) or 0,
                    processing=row.get("processing", 0) or 0,
                    completed=row.get("completed", 0) or 0,
                    failed=row.get("failed", 0) or 0,
                    cancelled=row.get("cancelled", 0) or 0,
                    skipped=row.get("skipped", 0) or 0,
                    avg_processing_time_ms=row.get("avg_processing_time_ms", 0) or 0,
                )
        except Exception as e:
            logger.warning("get_queue_stats_rpc_failed", error=str(e), matter_id=matter_id)

        # Fallback: Calculate manually
        return await self._calculate_queue_stats_manually(matter_id)

    async def _calculate_queue_stats_manually(
        self,
        matter_id: str,
    ) -> JobQueueStats:
        """Calculate queue stats manually (fallback if RPC fails)."""
        def _query():
            return (
                self.client.table("processing_jobs")
                .select("status, started_at, completed_at")
                .eq("matter_id", matter_id)
                .execute()
            )

        response = await asyncio.to_thread(_query)

        stats = {
            "queued": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "skipped": 0,
        }

        processing_times = []

        for row in (response.data or []):
            status = row.get("status", "").upper()
            if status in stats:
                stats[status.lower()] += 1

            # Calculate processing time for completed jobs
            if status == "COMPLETED" and row.get("started_at") and row.get("completed_at"):
                try:
                    started = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
                    completed = datetime.fromisoformat(row["completed_at"].replace("Z", "+00:00"))
                    processing_times.append((completed - started).total_seconds() * 1000)
                except (ValueError, TypeError):
                    pass

        avg_time = int(sum(processing_times) / len(processing_times)) if processing_times else 0

        return JobQueueStats(
            queued=stats["queued"],
            processing=stats["processing"],
            completed=stats["completed"],
            failed=stats["failed"],
            cancelled=stats["cancelled"],
            skipped=stats["skipped"],
            avg_processing_time_ms=avg_time,
        )

    # =========================================================================
    # Retry and Cancel Operations
    # =========================================================================

    async def retry_job(
        self,
        job_id: str,
        matter_id: str,
    ) -> ProcessingJob | None:
        """Retry a failed job.

        Resets status to QUEUED and increments retry count.
        Only works for FAILED status.

        Args:
            job_id: Job UUID.
            matter_id: Matter UUID for validation.

        Returns:
            Updated ProcessingJob or None if not found/invalid.
        """
        job = await self.get_job(job_id, matter_id)
        if not job:
            return None

        if job.status != JobStatus.FAILED:
            logger.warning("retry_invalid_status", job_id=job_id, status=job.status.value)
            return None

        def _update():
            return (
                self.client.table("processing_jobs")
                .update({
                    "status": JobStatus.QUEUED.value,
                    "retry_count": job.retry_count + 1,
                    "error_message": None,
                    "error_code": None,
                    "started_at": None,
                    "completed_at": None,
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", job_id)
                .eq("matter_id", matter_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)

        if response.data:
            logger.info("job_retry_initiated", job_id=job_id, retry_count=job.retry_count + 1)
            return self._db_row_to_processing_job(response.data[0])

        return None

    async def cancel_job(
        self,
        job_id: str,
        matter_id: str,
    ) -> ProcessingJob | None:
        """Cancel a pending or processing job.

        Args:
            job_id: Job UUID.
            matter_id: Matter UUID for validation.

        Returns:
            Updated ProcessingJob or None if not found/invalid.
        """
        job = await self.get_job(job_id, matter_id)
        if not job:
            return None

        if job.status not in (JobStatus.QUEUED, JobStatus.PROCESSING):
            logger.warning("cancel_invalid_status", job_id=job_id, status=job.status.value)
            return None

        def _update():
            return (
                self.client.table("processing_jobs")
                .update({
                    "status": JobStatus.CANCELLED.value,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", job_id)
                .eq("matter_id", matter_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)

        if response.data:
            logger.info("job_cancelled", job_id=job_id)
            return self._db_row_to_processing_job(response.data[0])

        return None

    async def skip_job(
        self,
        job_id: str,
        matter_id: str,
    ) -> ProcessingJob | None:
        """Skip a failed job (mark as SKIPPED).

        Args:
            job_id: Job UUID.
            matter_id: Matter UUID for validation.

        Returns:
            Updated ProcessingJob or None if not found/invalid.
        """
        job = await self.get_job(job_id, matter_id)
        if not job:
            return None

        if job.status != JobStatus.FAILED:
            logger.warning("skip_invalid_status", job_id=job_id, status=job.status.value)
            return None

        def _update():
            return (
                self.client.table("processing_jobs")
                .update({
                    "status": JobStatus.SKIPPED.value,
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", job_id)
                .eq("matter_id", matter_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)

        if response.data:
            logger.info("job_skipped", job_id=job_id)
            return self._db_row_to_processing_job(response.data[0])

        return None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _db_row_to_processing_job(self, row: dict) -> ProcessingJob:
        """Convert database row to ProcessingJob model."""
        return ProcessingJob(
            id=row["id"],
            matter_id=row["matter_id"],
            document_id=row.get("document_id"),
            job_type=JobType(row["job_type"]),
            status=JobStatus(row["status"]),
            celery_task_id=row.get("celery_task_id"),
            current_stage=row.get("current_stage"),
            total_stages=row.get("total_stages", 7) or 7,
            completed_stages=row.get("completed_stages", 0) or 0,
            progress_pct=row.get("progress_pct", 0) or 0,
            estimated_completion=self._parse_timestamp(row.get("estimated_completion")),
            error_message=row.get("error_message"),
            error_code=row.get("error_code"),
            retry_count=row.get("retry_count", 0) or 0,
            max_retries=row.get("max_retries", 3) or 3,
            metadata=row.get("metadata", {}) or {},
            started_at=self._parse_timestamp(row.get("started_at")),
            completed_at=self._parse_timestamp(row.get("completed_at")),
            created_at=self._parse_timestamp(row["created_at"]),
            updated_at=self._parse_timestamp(row["updated_at"]),
            heartbeat_at=self._parse_timestamp(row.get("heartbeat_at")),
        )

    def _db_row_to_job_list_item(self, row: dict) -> JobListItem:
        """Convert database row to JobListItem model."""
        return JobListItem(
            id=row["id"],
            matter_id=row["matter_id"],
            document_id=row.get("document_id"),
            job_type=JobType(row["job_type"]),
            status=JobStatus(row["status"]),
            current_stage=row.get("current_stage"),
            progress_pct=row.get("progress_pct", 0) or 0,
            estimated_completion=self._parse_timestamp(row.get("estimated_completion")),
            retry_count=row.get("retry_count", 0) or 0,
            error_message=row.get("error_message"),
            created_at=self._parse_timestamp(row["created_at"]),
        )

    def _db_row_to_stage_history(self, row: dict) -> JobStageHistory:
        """Convert database row to JobStageHistory model."""
        return JobStageHistory(
            id=row["id"],
            job_id=row["job_id"],
            stage_name=row["stage_name"],
            status=StageStatus(row["status"]),
            started_at=self._parse_timestamp(row.get("started_at")),
            completed_at=self._parse_timestamp(row.get("completed_at")),
            error_message=row.get("error_message"),
            metadata=row.get("metadata", {}) or {},
            created_at=self._parse_timestamp(row["created_at"]),
        )

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        """Parse ISO timestamp to datetime."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_job_tracking_service() -> JobTrackingService:
    """Get singleton job tracking service instance.

    Returns:
        JobTrackingService instance.
    """
    return JobTrackingService()
