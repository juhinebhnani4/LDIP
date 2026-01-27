"""Celery tasks for reasoning trace archival (Story 4.2).

Epic 4: Legal Defensibility (Gap Remediation)

This module contains the periodic task for archiving old reasoning traces
to cold storage (Supabase Storage).

Implements:
- AC 4.2.1: Nightly archival of traces older than 30 days
- AC 4.2.3: Retry on failure, alert if failures exceed threshold
"""

import asyncio

import structlog

from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.reasoning_archive_tasks.archive_reasoning_traces",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def archive_reasoning_traces(self) -> dict[str, int]:
    """Nightly task to archive old reasoning traces.

    Story 4.2: AC 4.2.1 - Archive traces older than 30 days.

    Scheduled via Celery Beat to run daily at 2 AM.
    Processes in batches until no more traces to archive.

    Returns:
        Dict with total_archived and total_failed counts.

    Raises:
        Retry: If task fails and retries are available.
    """
    async def run_archival() -> dict[str, int]:
        from app.services.reasoning_archive_service import get_reasoning_archive_service

        service = get_reasoning_archive_service()
        total_archived = 0
        total_failed = 0
        consecutive_failures = 0

        # Process in batches until no more traces to archive
        while True:
            result = await service.archive_old_traces()
            total_archived += result["archived"]
            total_failed += result["failed"]

            # Track consecutive failures for alerting
            if result["failed"] > 0 and result["archived"] == 0:
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            # Stop conditions
            if result["archived"] == 0:
                # No more traces to archive
                break

            if consecutive_failures > 3:
                # Too many consecutive failures - alert and stop
                logger.critical(
                    "reasoning_archival_consecutive_failures",
                    consecutive_failures=consecutive_failures,
                    total_failed=total_failed,
                    message="Archival stopped due to consecutive failures. Investigation required.",
                )
                break

            if total_failed > 10:
                # Too many total failures in this run
                logger.warning(
                    "reasoning_archival_high_failure_rate",
                    total_archived=total_archived,
                    total_failed=total_failed,
                )
                break

        return {"total_archived": total_archived, "total_failed": total_failed}

    try:
        result = asyncio.run(run_archival())
        logger.info(
            "reasoning_archival_task_complete",
            total_archived=result["total_archived"],
            total_failed=result["total_failed"],
        )
        return result
    except Exception as e:
        logger.error(
            "reasoning_archival_task_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise self.retry(exc=e)


@celery_app.task(
    name="app.workers.tasks.reasoning_archive_tasks.restore_reasoning_trace",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def restore_reasoning_trace(self, trace_id: str, matter_id: str) -> bool:
    """Restore a single trace from cold storage.

    Story 4.2: On-demand restoration for frequently accessed archived traces.

    Args:
        trace_id: Trace UUID to restore.
        matter_id: Matter UUID for validation.

    Returns:
        True if restoration succeeded.
    """
    async def run_restore() -> bool:
        from app.services.reasoning_archive_service import get_reasoning_archive_service

        service = get_reasoning_archive_service()
        return await service.restore_trace(trace_id, matter_id)

    try:
        result = asyncio.run(run_restore())
        logger.info(
            "reasoning_trace_restoration_complete",
            trace_id=trace_id,
            matter_id=matter_id,
            success=result,
        )
        return result
    except Exception as e:
        logger.error(
            "reasoning_trace_restoration_failed",
            trace_id=trace_id,
            matter_id=matter_id,
            error=str(e),
        )
        raise self.retry(exc=e)
