"""Maintenance tasks for job recovery and system health.

Periodic tasks for:
- Detecting and recovering stale/stuck jobs
- Cleaning up old job records
- System health monitoring
"""

import asyncio

import structlog

from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.recover_stale_jobs",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def recover_stale_jobs(self) -> dict:
    """Periodic task to find and recover stale jobs.

    This task runs on a schedule (configured in celery.py beat_schedule)
    and automatically recovers jobs that have been stuck in PROCESSING
    state for longer than the configured timeout.

    Returns:
        Dictionary with recovery results.
    """
    from app.core.config import get_settings
    from app.services.job_recovery import get_job_recovery_service
    from app.services.supabase.client import get_service_client

    settings = get_settings()

    if not settings.job_recovery_enabled:
        logger.debug("job_recovery_task_skipped", reason="disabled_in_config")
        return {"skipped": True, "reason": "Job recovery disabled"}

    logger.info("job_recovery_task_started")

    try:
        # Get service client (uses service role key for admin access)
        supabase = get_service_client()
        recovery_service = get_job_recovery_service(supabase)

        # Run recovery asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(recovery_service.recover_all_stale_jobs())
        finally:
            loop.close()

        logger.info(
            "job_recovery_task_completed",
            recovered=result.get("recovered", 0),
            failed=result.get("failed", 0),
            total=result.get("total", 0),
        )

        return result

    except Exception as e:
        logger.error("job_recovery_task_failed", error=str(e))
        # Don't retry on failure - will run again on next schedule
        return {"error": str(e)}


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.cleanup_stale_chunks",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def cleanup_stale_chunks(self, retention_hours: int = 24) -> dict:
    """Periodic task to clean up stale chunk records.

    Story 15.4: Chunk Cleanup Mechanism

    This task runs on a schedule (configured in celery.py beat_schedule)
    and automatically cleans up chunk records older than the retention period.

    Args:
        retention_hours: Hours to retain chunk records (default 24).

    Returns:
        Dictionary with cleanup results.
    """
    from app.services.chunk_cleanup_service import get_chunk_cleanup_service

    logger.info(
        "chunk_cleanup_task_started",
        retention_hours=retention_hours,
    )

    try:
        cleanup_service = get_chunk_cleanup_service()

        # Run cleanup asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                cleanup_service.cleanup_stale_chunks(retention_hours=retention_hours)
            )
        finally:
            loop.close()

        logger.info(
            "chunk_cleanup_task_completed",
            documents_cleaned=result.get("documents_cleaned", 0),
            total_chunks_deleted=result.get("total_chunks_deleted", 0),
            errors=len(result.get("errors", [])),
        )

        return result

    except Exception as e:
        logger.error("chunk_cleanup_task_failed", error=str(e))
        # Don't retry on failure - will run again on next schedule
        return {"error": str(e)}


# =============================================================================
# Chunk Recovery Task (Story 19.1)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.recover_stale_chunks",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def recover_stale_chunks(self) -> dict:
    """Periodic task to find and recover stale chunks.

    Story 19.1: Automatic stale chunk recovery

    Detects chunks stuck in PROCESSING state > 90 seconds
    and resets them to PENDING for retry.

    Returns:
        Dictionary with recovery results.
    """
    from app.services.chunk_recovery_service import get_chunk_recovery_service

    logger.info("chunk_recovery_task_started")

    try:
        recovery_service = get_chunk_recovery_service()

        # Run recovery asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(recovery_service.recover_all_stale_chunks())
        finally:
            loop.close()

        logger.info(
            "chunk_recovery_task_completed",
            recovered=result.get("recovered", 0),
            failed=result.get("failed", 0),
            total=result.get("total", 0),
        )

        return result

    except Exception as e:
        logger.error("chunk_recovery_task_failed", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Auto-Merge Trigger Task (Story 19.2)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.trigger_pending_merges",
    bind=True,
    max_retries=1,
)
def trigger_pending_merges(self) -> dict:
    """Periodic task to trigger merges for completed chunked documents.

    Story 19.2: Auto-merge trigger safety net

    Safety net that detects documents where:
    - All chunks have status 'completed'
    - Document is still in PROCESSING status
    - Merge hasn't been triggered

    Returns:
        Dictionary with trigger results.
    """
    from app.services.merge_trigger_service import get_merge_trigger_service

    logger.info("merge_trigger_task_started")

    try:
        trigger_service = get_merge_trigger_service()

        # Run trigger check asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(trigger_service.check_and_trigger_merges())
        finally:
            loop.close()

        logger.info(
            "merge_trigger_task_completed",
            checked=result.get("checked", 0),
            triggered=result.get("triggered", 0),
            skipped=result.get("skipped", 0),
            already_complete=result.get("already_complete", 0),
            errors=len(result.get("errors", [])),
        )

        return result

    except Exception as e:
        logger.error("merge_trigger_task_failed", error=str(e))
        return {"error": str(e)}


# =============================================================================
# SKIPPED Large Document Recovery Task (Story 19.3)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.recover_skipped_large_documents",
    bind=True,
    max_retries=1,
)
def recover_skipped_large_documents(self) -> dict:
    """Recover SKIPPED jobs that failed due to page limits.

    Story 19.3: Auto-convert SKIPPED jobs to chunked processing

    Finds jobs with:
    - status = SKIPPED
    - error contains PAGE_LIMIT_EXCEEDED or similar

    Then creates chunk records and dispatches chunked processing.

    Returns:
        Dictionary with recovery results.
    """
    from app.services.job_recovery import get_job_recovery_service
    from app.services.supabase.client import get_service_client

    logger.info("recover_skipped_large_documents_started")

    try:
        supabase = get_service_client()
        recovery_service = get_job_recovery_service(supabase)

        # Find SKIPPED jobs with page limit errors
        response = supabase.table("processing_jobs").select(
            "id, matter_id, document_id, error_message, metadata"
        ).eq("status", "SKIPPED").execute()

        skipped_jobs = response.data or []
        results = {
            "checked": len(skipped_jobs),
            "converted": 0,
            "skipped": 0,
            "errors": [],
        }

        for job in skipped_jobs:
            error_msg = job.get("error_message", "") or ""
            metadata = job.get("metadata") or {}

            # Check if this is a page limit failure
            is_page_limit = (
                "PAGE_LIMIT" in error_msg.upper()
                or "page limit" in error_msg.lower()
                or metadata.get("page_limit_exceeded")
                or "too many pages" in error_msg.lower()
                or "pages exceed" in error_msg.lower()
            )

            if not is_page_limit:
                results["skipped"] += 1
                continue

            # Attempt recovery with chunked processing
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    recovery_service.recover_with_chunked_processing(job)
                )
                if result.get("success"):
                    results["converted"] += 1
                    logger.info(
                        "skipped_job_converted_to_chunked",
                        job_id=job["id"],
                        document_id=job.get("document_id"),
                        page_count=result.get("page_count"),
                        chunk_count=result.get("chunk_count"),
                    )
                else:
                    results["errors"].append({
                        "job_id": job["id"],
                        "error": result.get("error"),
                    })
            finally:
                loop.close()

        logger.info(
            "recover_skipped_large_documents_completed",
            checked=results["checked"],
            converted=results["converted"],
            skipped=results["skipped"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("recover_skipped_large_documents_failed", error=str(e))
        return {"error": str(e)}