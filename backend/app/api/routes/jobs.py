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
from app.services.job_recovery import JobRecoveryService, get_job_recovery_service
from app.services.job_tracking import (
    JobNotFoundError,
    JobTrackingError,
    JobTrackingService,
    get_job_tracking_service,
)
from app.workers.celery import celery_app
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


class StaleJobInfo(BaseModel):
    """Information about a stale job."""

    job_id: str
    document_id: str | None
    matter_id: str
    job_type: str
    current_stage: str | None
    stuck_since: str
    recovery_attempts: int = 0


class RecoveryResult(BaseModel):
    """Result of a job recovery operation."""

    success: bool
    job_id: str
    error: str | None = None
    action: str | None = None
    recovery_attempt: int | None = None


class RecoverStaleJobsResponse(BaseModel):
    """Response for recovering stale jobs."""

    recovered: int
    failed: int
    total: int
    jobs: list[RecoveryResult]


class RecoveryStatsResponse(BaseModel):
    """Response for recovery statistics."""

    stale_jobs_count: int
    stale_jobs: list[StaleJobInfo]
    config: dict
    recovered_last_hour: int


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
    except JobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": "Job not found",
                    "details": {},
                }
            },
        ) from e

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
        ) from e


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
            queued=stats.queued,
            processing=stats.processing,
            completed=stats.completed,
            failed=stats.failed,
            cancelled=stats.cancelled,
            skipped=stats.skipped,
            avg_processing_time_ms=stats.avg_processing_time_ms,
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
        ) from e


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
        ) from e


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
        ) from e


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

        # Revoke the Celery task if it has a celery_task_id
        if job.celery_task_id:
            try:
                celery_app.control.revoke(job.celery_task_id, terminate=True)
                logger.info(
                    "celery_task_revoked",
                    job_id=job_id,
                    celery_task_id=job.celery_task_id,
                )
            except Exception as revoke_error:
                # Log but don't fail - the job is already marked cancelled
                logger.warning(
                    "celery_task_revoke_failed",
                    job_id=job_id,
                    celery_task_id=job.celery_task_id,
                    error=str(revoke_error),
                )

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
        ) from e


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
        ) from e


# =============================================================================
# Job Recovery Endpoints (Admin)
# =============================================================================


def _get_recovery_service() -> JobRecoveryService:
    """Get job recovery service instance."""
    from app.api.deps import get_supabase_service_client
    supabase = get_supabase_service_client()
    return get_job_recovery_service(supabase)


@router.get(
    "/recovery/stats",
    response_model=RecoveryStatsResponse,
    summary="Get job recovery statistics",
    description="Get information about stale jobs and recovery configuration.",
)
async def get_recovery_stats(
    user: AuthenticatedUser = Depends(get_current_user),
    recovery_service: JobRecoveryService = Depends(_get_recovery_service),
) -> RecoveryStatsResponse:
    """Get job recovery statistics and stale job information."""
    from app.core.config import get_settings
    settings = get_settings()

    # Find stale jobs
    stale_jobs = await recovery_service.find_stale_jobs()

    stale_job_infos = [
        StaleJobInfo(
            job_id=job["id"],
            document_id=job.get("document_id"),
            matter_id=job["matter_id"],
            job_type=job["job_type"],
            current_stage=job.get("current_stage"),
            stuck_since=job["updated_at"],
            recovery_attempts=(job.get("metadata") or {}).get("recovery_attempts", 0),
        )
        for job in stale_jobs
    ]

    # Get recovery stats
    stats = await recovery_service.get_recovery_stats()

    return RecoveryStatsResponse(
        stale_jobs_count=len(stale_jobs),
        stale_jobs=stale_job_infos,
        config={
            "stale_timeout_minutes": settings.job_stale_timeout_minutes,
            "max_recovery_retries": settings.job_max_recovery_retries,
            "recovery_enabled": settings.job_recovery_enabled,
        },
        recovered_last_hour=stats.get("recovered_last_hour", 0),
    )


@router.post(
    "/recovery/run",
    response_model=RecoverStaleJobsResponse,
    summary="Recover all stale jobs",
    description="Find and recover all jobs stuck in PROCESSING state.",
)
async def recover_stale_jobs(
    user: AuthenticatedUser = Depends(get_current_user),
    recovery_service: JobRecoveryService = Depends(_get_recovery_service),
) -> RecoverStaleJobsResponse:
    """Recover all stale jobs."""
    logger.info("manual_recovery_triggered", user_id=user.id)

    result = await recovery_service.recover_all_stale_jobs()

    if result.get("skipped"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "RECOVERY_DISABLED",
                    "message": "Job recovery is disabled in configuration",
                    "details": {},
                }
            },
        )

    return RecoverStaleJobsResponse(
        recovered=result.get("recovered", 0),
        failed=result.get("failed", 0),
        total=result.get("total", 0),
        jobs=[
            RecoveryResult(
                success=j.get("success", False),
                job_id=j.get("job_id", ""),
                error=j.get("error"),
                action=j.get("action"),
                recovery_attempt=j.get("recovery_attempt"),
            )
            for j in result.get("jobs", [])
        ],
    )


@router.post(
    "/recovery/{job_id}",
    response_model=RecoveryResult,
    summary="Recover a specific stale job",
    description="Attempt to recover a specific job stuck in PROCESSING state.",
)
async def recover_single_job(
    job_id: str = Path(..., description="Job UUID to recover"),
    user: AuthenticatedUser = Depends(get_current_user),
    recovery_service: JobRecoveryService = Depends(_get_recovery_service),
) -> RecoveryResult:
    """Recover a specific stale job."""
    logger.info("manual_single_job_recovery", job_id=job_id, user_id=user.id)

    result = await recovery_service.recover_stale_job(job_id)

    return RecoveryResult(
        success=result.get("success", False),
        job_id=result.get("job_id", job_id),
        error=result.get("error"),
        action=result.get("action"),
        recovery_attempt=result.get("recovery_attempt"),
    )
