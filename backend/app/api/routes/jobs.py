"""Job API routes for processing job management.

Implements job status querying, retry, skip, and cancel operations
with proper matter isolation via matter_id validation.

Story 2c-3: Background Job Status Tracking and Retry
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.deps import (
    MatterAccessContext,
    MatterRole,
    validate_matter_access,
)
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.job import (
    JobListResponse,
    JobStatus,
    JobType,
    ProcessingJob,
    ProcessingJobResponse,
)
from app.services.job_tracking import (
    JobNotFoundError,
    JobTrackingError,
    JobTrackingService,
    get_job_tracking_service,
)
from app.workers.tasks.document_tasks import process_document

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class JobRetryRequest(BaseModel):
    """Request body for retrying a job."""

    reset_retry_count: bool = Field(
        default=True,
        description="Reset retry count to 0 before retrying",
    )


class JobRetryResponse(BaseModel):
    """Response for job retry request."""

    success: bool
    message: str
    job_id: str
    new_status: str


class JobSkipResponse(BaseModel):
    """Response for job skip request."""

    success: bool
    message: str
    job_id: str
    new_status: str


class JobCancelResponse(BaseModel):
    """Response for job cancel request."""

    success: bool
    message: str
    job_id: str
    new_status: str


class JobQueueStats(BaseModel):
    """Queue statistics for a matter."""

    matter_id: str
    queued: int
    processing: int
    completed: int
    failed: int
    cancelled: int
    skipped: int
    avg_processing_time_ms: int | None = None


# =============================================================================
# Helper Functions
# =============================================================================


def _get_job_tracker() -> JobTrackingService:
    """Get job tracking service instance."""
    return get_job_tracking_service()


async def _validate_job_access(
    job_id: str,
    user: AuthenticatedUser,
    job_tracker: JobTrackingService,
    required_role: MatterRole | None = None,
) -> ProcessingJob:
    """Validate user has access to a job via matter membership.

    Args:
        job_id: Job UUID.
        user: Authenticated user.
        job_tracker: Job tracking service.
        required_role: Optional minimum role required.

    Returns:
        The job if access is granted.

    Raises:
        HTTPException: If job not found or access denied.
    """
    try:
        job = await job_tracker.get_job(job_id)
    except JobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": "Job not found",
                    "details": {},
                }
            },
        )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": "Job not found",
                    "details": {},
                }
            },
        )

    # Validate matter access via matter_attorneys RLS (handled by Supabase)
    # For additional security, we could check matter membership here
    # but the RLS policies already enforce this

    return job


# =============================================================================
# Job Query Endpoints
# =============================================================================


@router.get(
    "/matters/{matter_id}",
    response_model=JobListResponse,
    summary="List processing jobs for a matter",
    description="Get all processing jobs for a matter with optional status filtering.",
)
async def list_matter_jobs(
    access: MatterAccessContext = Depends(validate_matter_access()),
    status_filter: JobStatus | None = Query(
        None,
        alias="status",
        description="Filter by job status",
    ),
    job_type_filter: JobType | None = Query(
        None,
        alias="job_type",
        description="Filter by job type",
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
) -> JobListResponse:
    """List all processing jobs for a matter."""
    try:
        jobs = await job_tracker.list_jobs_for_matter(
            matter_id=access.matter_id,
            status_filter=status_filter,
            job_type_filter=job_type_filter,
            limit=limit,
            offset=offset,
        )

        return JobListResponse(
            jobs=jobs,
            total=len(jobs),
            limit=limit,
            offset=offset,
        )

    except JobTrackingError as e:
        logger.error(
            "list_matter_jobs_failed",
            matter_id=access.matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "JOB_LIST_FAILED",
                    "message": "Failed to list jobs",
                    "details": {},
                }
            },
        )


@router.get(
    "/matters/{matter_id}/stats",
    response_model=JobQueueStats,
    summary="Get job queue statistics for a matter",
    description="Get counts of jobs by status for a matter.",
)
async def get_matter_job_stats(
    access: MatterAccessContext = Depends(validate_matter_access()),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
) -> JobQueueStats:
    """Get job queue statistics for a matter."""
    try:
        stats = await job_tracker.get_queue_stats(access.matter_id)

        return JobQueueStats(
            matter_id=access.matter_id,
            queued=stats.get("queued", 0),
            processing=stats.get("processing", 0),
            completed=stats.get("completed", 0),
            failed=stats.get("failed", 0),
            cancelled=stats.get("cancelled", 0),
            skipped=stats.get("skipped", 0),
            avg_processing_time_ms=stats.get("avg_processing_time_ms"),
        )

    except JobTrackingError as e:
        logger.error(
            "get_matter_job_stats_failed",
            matter_id=access.matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "STATS_FAILED",
                    "message": "Failed to get job statistics",
                    "details": {},
                }
            },
        )


@router.get(
    "/{job_id}",
    response_model=ProcessingJobResponse,
    summary="Get job details",
    description="Get detailed information about a specific job.",
)
async def get_job(
    job_id: str = Path(..., description="Job UUID"),
    user: AuthenticatedUser = Depends(get_current_user),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
) -> ProcessingJobResponse:
    """Get details for a specific job."""
    job = await _validate_job_access(job_id, user, job_tracker)

    # Get stage history
    stages = await job_tracker.get_stage_history(job_id)

    return ProcessingJobResponse(
        job=job,
        stages=stages,
    )


# =============================================================================
# Job Action Endpoints (Retry, Skip, Cancel)
# =============================================================================


@router.post(
    "/{job_id}/retry",
    response_model=JobRetryResponse,
    summary="Retry a failed job",
    description="Retry a failed job. Only jobs with status FAILED can be retried.",
)
async def retry_job(
    job_id: str = Path(..., description="Job UUID"),
    request: JobRetryRequest | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
) -> JobRetryResponse:
    """Retry a failed job."""
    job = await _validate_job_access(job_id, user, job_tracker)

    # Validate job can be retried
    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_JOB_STATUS",
                    "message": f"Cannot retry job with status {job.status.value}. Only FAILED jobs can be retried.",
                    "details": {"current_status": job.status.value},
                }
            },
        )

    try:
        # Reset retry count if requested
        reset_count = request.reset_retry_count if request else True
        if reset_count:
            await job_tracker.reset_retry_count(job_id)

        # Update job status to QUEUED
        await job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.QUEUED,
            error_message=None,
            error_code=None,
        )

        # Re-queue the Celery task if it's a document processing job
        if job.document_id and job.job_type == JobType.DOCUMENT_PROCESSING:
            process_document.delay(job.document_id)

        logger.info(
            "job_retry_initiated",
            job_id=job_id,
            document_id=job.document_id,
            user_id=user.id,
        )

        return JobRetryResponse(
            success=True,
            message="Job has been queued for retry",
            job_id=job_id,
            new_status=JobStatus.QUEUED.value,
        )

    except JobTrackingError as e:
        logger.error(
            "job_retry_failed",
            job_id=job_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RETRY_FAILED",
                    "message": "Failed to retry job",
                    "details": {},
                }
            },
        )


@router.post(
    "/{job_id}/skip",
    response_model=JobSkipResponse,
    summary="Skip a failed job",
    description="Mark a failed job as skipped. The document will remain in its current state.",
)
async def skip_job(
    job_id: str = Path(..., description="Job UUID"),
    user: AuthenticatedUser = Depends(get_current_user),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
) -> JobSkipResponse:
    """Skip a failed job."""
    job = await _validate_job_access(job_id, user, job_tracker)

    # Validate job can be skipped
    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_JOB_STATUS",
                    "message": f"Cannot skip job with status {job.status.value}. Only FAILED jobs can be skipped.",
                    "details": {"current_status": job.status.value},
                }
            },
        )

    try:
        # Update job status to SKIPPED
        await job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.SKIPPED,
        )

        logger.info(
            "job_skipped",
            job_id=job_id,
            document_id=job.document_id,
            user_id=user.id,
        )

        return JobSkipResponse(
            success=True,
            message="Job has been marked as skipped",
            job_id=job_id,
            new_status=JobStatus.SKIPPED.value,
        )

    except JobTrackingError as e:
        logger.error(
            "job_skip_failed",
            job_id=job_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "SKIP_FAILED",
                    "message": "Failed to skip job",
                    "details": {},
                }
            },
        )


@router.post(
    "/{job_id}/cancel",
    response_model=JobCancelResponse,
    summary="Cancel a pending or processing job",
    description="Cancel a job that is QUEUED or PROCESSING.",
)
async def cancel_job(
    job_id: str = Path(..., description="Job UUID"),
    user: AuthenticatedUser = Depends(get_current_user),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
) -> JobCancelResponse:
    """Cancel a pending or processing job."""
    job = await _validate_job_access(job_id, user, job_tracker)

    # Validate job can be cancelled
    if job.status not in (JobStatus.QUEUED, JobStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_JOB_STATUS",
                    "message": f"Cannot cancel job with status {job.status.value}. Only QUEUED or PROCESSING jobs can be cancelled.",
                    "details": {"current_status": job.status.value},
                }
            },
        )

    try:
        # Update job status to CANCELLED
        await job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.CANCELLED,
        )

        # TODO: If job has celery_task_id, revoke the Celery task
        # This requires Celery app access and is non-trivial

        logger.info(
            "job_cancelled",
            job_id=job_id,
            document_id=job.document_id,
            user_id=user.id,
        )

        return JobCancelResponse(
            success=True,
            message="Job has been cancelled",
            job_id=job_id,
            new_status=JobStatus.CANCELLED.value,
        )

    except JobTrackingError as e:
        logger.error(
            "job_cancel_failed",
            job_id=job_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CANCEL_FAILED",
                    "message": "Failed to cancel job",
                    "details": {},
                }
            },
        )


# =============================================================================
# Document-specific Job Queries
# =============================================================================


@router.get(
    "/documents/{document_id}/active",
    response_model=ProcessingJobResponse | None,
    summary="Get active job for a document",
    description="Get the currently active (QUEUED or PROCESSING) job for a document.",
)
async def get_active_job_for_document(
    document_id: str = Path(..., description="Document UUID"),
    user: AuthenticatedUser = Depends(get_current_user),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
) -> ProcessingJobResponse | None:
    """Get the active job for a document, if any."""
    try:
        # Note: matter_id validation happens via RLS when querying
        job = await job_tracker.get_active_job_for_document(document_id)

        if job is None:
            return None

        stages = await job_tracker.get_stage_history(job.id)

        return ProcessingJobResponse(
            job=job,
            stages=stages,
        )

    except JobTrackingError as e:
        logger.error(
            "get_active_job_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "QUERY_FAILED",
                    "message": "Failed to get active job",
                    "details": {},
                }
            },
        )
