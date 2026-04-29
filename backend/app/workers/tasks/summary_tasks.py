"""Celery tasks for background summary generation.

Moves the summary pipeline (5 DB queries + 3 GPT-4 calls) out of the HTTP
request path and into the Celery worker queue. The API handler dispatches
this task and returns immediately; the frontend polls for completion.

Job Tracking Integration:
- Updates processing_jobs status as generation progresses
- Broadcasts progress via PubSub for real-time UI updates
- Retries on transient failures (ConnectionError, TimeoutError)
"""

import structlog
from celery.exceptions import SoftTimeLimitExceeded

from app.models.job import JobStatus
from app.services.job_tracking import get_job_tracking_service
from app.services.pubsub_service import (
    broadcast_job_progress,
    broadcast_job_status_change,
)
from app.services.summary_service import get_summary_service
from app.workers.celery import celery_app
from app.workers.utils import run_async

logger = structlog.get_logger(__name__)

# Redis lock key pattern — matches the lock set in the API handler
_LOCK_KEY_PATTERN = "summary_gen_lock:{matter_id}"


async def _async_release_lock(matter_id: str) -> None:
    """Delete the Redis dedup lock so a new generation can be dispatched."""
    from app.services.memory.redis_client import get_redis_client

    redis = await get_redis_client()
    lock_key = _LOCK_KEY_PATTERN.format(matter_id=matter_id)
    await redis.delete(lock_key)


def _release_dedup_lock(matter_id: str) -> None:
    """Release the Redis dedup lock (sync wrapper for Celery context)."""
    try:
        run_async(_async_release_lock(matter_id), timeout=5)
    except Exception:
        # Lock has a 600s TTL anyway — safe to ignore cleanup failure
        pass


@celery_app.task(
    name="app.workers.tasks.summary_tasks.generate_summary",
    bind=True,
    max_retries=2,
    soft_time_limit=300,  # 5 min soft limit
    time_limit=360,  # 6 min hard kill
)
def generate_summary(self, matter_id: str, job_id: str | None = None) -> dict:
    """Generate matter summary in background.

    Args:
        self: Celery task instance (bind=True).
        matter_id: Matter UUID to generate summary for.
        job_id: Processing job UUID for status tracking. When None
            (pipeline pre-generation), a job record is created internally.

    Returns:
        Dict with generation result status.
    """
    tracker = get_job_tracking_service()

    # Pipeline pre-generation dispatches without a pre-created job record.
    # Create one here so progress tracking and dedup still work.
    if not job_id:
        try:
            from app.models.job import JobType

            job = run_async(
                tracker.create_job(
                    matter_id=matter_id,
                    job_type=JobType.SUMMARY_GENERATION,
                    max_retries=2,
                ),
                timeout=15,
            )
            job_id = job.id
        except Exception as e:
            # If job creation fails, still generate — just no progress tracking
            logger.warning(
                "summary_pregen_job_creation_failed",
                matter_id=matter_id,
                error=str(e),
            )

    log = logger.bind(matter_id=matter_id, job_id=job_id, task_id=self.request.id)
    log.info("summary_generation_started")

    summary_service = get_summary_service()
    current_status = JobStatus.QUEUED.value

    try:
        # 1. Update job status → PROCESSING
        if job_id:
            run_async(
                tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PROCESSING,
                    stage="db_queries",
                    progress_pct=10,
                    matter_id=matter_id,
                ),
                timeout=30,
            )
            broadcast_job_progress(
                matter_id=matter_id,
                job_id=job_id,
                stage="db_queries",
                progress_pct=10,
            )
            broadcast_job_status_change(
                matter_id=matter_id,
                job_id=job_id,
                old_status=current_status,
                new_status=JobStatus.PROCESSING.value,
            )
        current_status = JobStatus.PROCESSING.value

        # 2. Run the full summary pipeline (DB queries + GPT-4 calls)
        summary = run_async(
            summary_service.get_summary(matter_id=matter_id, force_refresh=True),
            timeout=280,
        )

        # 3. Broadcast near-completion progress
        if job_id:
            broadcast_job_progress(
                matter_id=matter_id,
                job_id=job_id,
                stage="validation_and_cache",
                progress_pct=90,
            )

        # 4. Validate the generated summary
        #    If invalid, invalidate cache to prevent stale bad data from being served,
        #    since get_summary() already cached the result before returning.
        if not summary_service.is_summary_valid(summary):
            run_async(summary_service.invalidate_cache(matter_id), timeout=10)
            raise ValueError("Generated summary failed validation checks")

        # 5. Mark job as COMPLETED and release the dedup lock
        if job_id:
            run_async(
                tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    stage="completed",
                    progress_pct=100,
                    matter_id=matter_id,
                ),
                timeout=30,
            )
            broadcast_job_progress(
                matter_id=matter_id,
                job_id=job_id,
                stage="completed",
                progress_pct=100,
            )
            broadcast_job_status_change(
                matter_id=matter_id,
                job_id=job_id,
                old_status=current_status,
                new_status=JobStatus.COMPLETED.value,
            )

        _release_dedup_lock(matter_id)
        log.info("summary_generation_completed")
        return {"status": "completed", "matter_id": matter_id, "job_id": job_id}

    except SoftTimeLimitExceeded:
        log.error("summary_generation_soft_timeout")
        if job_id:
            _mark_job_failed(
                tracker, matter_id, job_id, current_status,
                "Summary generation timed out (5 min limit)",
            )
        _release_dedup_lock(matter_id)
        return {"status": "failed", "matter_id": matter_id, "error": "timeout"}

    except Exception as e:
        error_type = type(e).__name__
        log.error("summary_generation_failed", error=str(e), error_type=error_type)

        # Retry on transient errors only
        is_transient = isinstance(e, (ConnectionError, TimeoutError, OSError))
        if is_transient and self.request.retries < self.max_retries:
            if job_id:
                run_async(
                    tracker.update_job_status(
                        job_id=job_id,
                        status=JobStatus.PROCESSING,
                        stage="retrying",
                        error_message=f"Retrying ({self.request.retries + 1}/{self.max_retries}) due to {error_type}",
                        matter_id=matter_id,
                    ),
                    timeout=30,
                )
            raise self.retry(countdown=30 * (self.request.retries + 1), exc=e)

        # Non-retriable or retries exhausted → mark failed
        # Sanitize error message to avoid leaking internal details
        safe_message = f"{error_type}: {str(e)[:200]}" if is_transient else str(e)[:500]
        if job_id:
            _mark_job_failed(tracker, matter_id, job_id, current_status, safe_message)
        _release_dedup_lock(matter_id)
        return {"status": "failed", "matter_id": matter_id, "error": safe_message}


def _mark_job_failed(
    tracker,
    matter_id: str,
    job_id: str,
    old_status: str,
    error_message: str,
) -> None:
    """Mark a summary generation job as failed and release the dedup lock."""
    try:
        run_async(
            tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                stage="failed",
                error_message=error_message,
                matter_id=matter_id,
            ),
            timeout=30,
        )
        broadcast_job_status_change(
            matter_id=matter_id,
            job_id=job_id,
            old_status=old_status,
            new_status=JobStatus.FAILED.value,
        )
    except Exception as e:
        logger.error(
            "summary_job_status_update_failed",
            job_id=job_id,
            error=str(e),
        )
    finally:
        _release_dedup_lock(matter_id)
