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
    from app.api.deps import get_supabase_service_client
    from app.core.config import get_settings
    from app.services.job_recovery import get_job_recovery_service

    settings = get_settings()

    if not settings.job_recovery_enabled:
        logger.debug("job_recovery_task_skipped", reason="disabled_in_config")
        return {"skipped": True, "reason": "Job recovery disabled"}

    logger.info("job_recovery_task_started")

    try:
        # Get service client (uses service role key for admin access)
        supabase = get_supabase_service_client()
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
