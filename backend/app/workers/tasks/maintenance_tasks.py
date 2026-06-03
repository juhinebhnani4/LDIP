"""Maintenance tasks for job recovery and system health.

Periodic tasks for:
- Detecting and recovering stale/stuck jobs
- Cleaning up old job records
- System health monitoring
"""

import structlog

from app.workers.celery import celery_app
from app.workers.utils import run_async

logger = structlog.get_logger(__name__)


def _get_effective_stage_from_job(job: dict) -> str | None:
    """Determine actual resume stage from partial_progress metadata.

    current_stage can be wrong (reset to 'ocr' by previous recovery restarts).
    partial_progress accurately records which stages completed at 100%.
    """
    metadata = job.get("metadata") or {}
    partial_progress = metadata.get("partial_progress", {})

    if not partial_progress:
        return job.get("current_stage")

    dispatchable_stages = [
        "embedding", "entity_extraction", "alias_resolution",
        "citation_extraction", "contradiction_detection",
    ]

    last_completed_idx = -1
    for i, stage in enumerate(dispatchable_stages):
        stage_data = partial_progress.get(stage, {})
        if stage_data.get("progress_pct", 0) >= 100:
            last_completed_idx = i

    if last_completed_idx < 0:
        return job.get("current_stage")

    next_idx = last_completed_idx + 1
    if next_idx < len(dispatchable_stages):
        return dispatchable_stages[next_idx]

    return job.get("current_stage")


def _is_pipeline_data_complete(client, document_id: str, document_type: str = "case_file") -> bool:
    """Check if all pipeline stages produced output for a document.

    Stage 1.3: Smarter Recovery — prevents re-dispatching documents that
    already have all their data but whose job row is stuck at PROCESSING.

    Completion criteria depend on document_type:
    - case_file / annexure / other: chunks > 0, embeddings > 0, entity_mentions > 0
    - act: chunks > 0, embeddings > 0 (entity_mentions not required — acts
      go through a truncated pipeline where 0 entities is valid)

    This is the SINGLE SOURCE OF TRUTH for "is this document done?" — all
    sweep tasks should call this instead of implementing their own heuristics.
    """
    try:
        # 1. Check chunks exist
        chunks = (
            client.table("chunks")
            .select("id", count="exact")
            .eq("document_id", document_id)
            .execute()
        )
        chunk_count = chunks.count or 0

        # Acts that were routed to library pipeline may have 0 chunks in the
        # main chunks table — that's their correct terminal state.
        if document_type == "act" and chunk_count == 0:
            return True

        if chunk_count == 0:
            return False

        # 2. Check embeddings exist (at least some chunks have embeddings)
        embedded = (
            client.table("chunks")
            .select("id", count="exact")
            .eq("document_id", document_id)
            .not_.is_("embedding", "null")
            .execute()
        )
        if not embedded.count:
            return False

        # 3. For non-act documents: check entity mentions exist
        # Acts run a truncated pipeline (citations skipped, contradictions
        # dispatched directly) so 0 entity_mentions is valid.
        if document_type != "act":
            entities = (
                client.table("entity_mentions")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .execute()
            )
            if not (entities.count and entities.count > 0):
                return False

        return True

    except Exception as e:
        logger.warning(
            "pipeline_data_completeness_check_failed",
            document_id=document_id,
            error=str(e),
        )
        return False


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
        result = run_async(recovery_service.recover_all_stale_jobs())

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
    name="app.workers.tasks.maintenance_tasks.dispatch_stuck_queued_jobs",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def dispatch_stuck_queued_jobs(self, stale_minutes: int = 10) -> dict:
    """Periodic task to dispatch QUEUED jobs that haven't been picked up.

    This handles the case where jobs are set to QUEUED status but no Celery
    task was dispatched (e.g., after manual recovery or database edits).

    Args:
        stale_minutes: Minutes a job can be QUEUED without update before re-dispatching.

    Returns:
        Dictionary with dispatch results.
    """
    from datetime import UTC, datetime, timedelta

    from app.services.supabase.client import get_service_client

    logger.info("dispatch_stuck_queued_jobs_started", stale_minutes=stale_minutes)

    try:
        client = get_service_client()
        if not client:
            return {"error": "Database client not configured"}

        # Find QUEUED jobs that haven't been updated recently
        cutoff_time = datetime.now(UTC) - timedelta(minutes=stale_minutes)

        response = (
            client.table("processing_jobs")
            .select("id, document_id, matter_id, job_type, current_stage, updated_at, metadata")
            .eq("status", "QUEUED")
            .lt("updated_at", cutoff_time.isoformat())
            .execute()
        )

        stuck_jobs = response.data or []

        if not stuck_jobs:
            logger.debug("no_stuck_queued_jobs_found")
            return {"dispatched": 0, "total": 0}

        # Import tasks here to avoid circular imports
        from app.workers.tasks.document_tasks import (
            detect_contradictions,
            embed_chunks,
            extract_citations,
            extract_entities,
            process_document,
            resolve_aliases,
        )

        # Engine task job types that need special dispatch
        ENGINE_JOB_TYPES = {
            "DATE_EXTRACTION",
            "EVENT_CLASSIFICATION",
            "ENTITY_LINKING",
            "ANOMALY_DETECTION",
        }

        dispatched = 0
        skipped = 0
        errors = []

        # Stage 1.2: Import PipelineLock for dedup checks
        from app.services.distributed_lock import PipelineLock

        for job in stuck_jobs:
            job_id = job["id"]
            doc_id = job.get("document_id")
            matter_id = job.get("matter_id")
            job_type = job.get("job_type")
            stage = _get_effective_stage_from_job(job)

            # Stage 1.2: Skip if pipeline is already running for this document
            if doc_id and PipelineLock(doc_id).is_locked():
                logger.info(
                    "dispatch_stuck_queued_skipped_locked",
                    job_id=job_id,
                    document_id=doc_id,
                )
                skipped += 1
                continue

            # Handle engine task job types (DATE_EXTRACTION, etc.)
            # These are matter-level jobs that may not have a document_id
            if job_type in ENGINE_JOB_TYPES:
                if not matter_id:
                    errors.append({"job_id": job_id, "error": "engine job missing matter_id"})
                    continue

                try:
                    if job_type == "DATE_EXTRACTION":
                        from app.workers.tasks.engine_tasks import extract_dates_from_matter

                        extract_dates_from_matter.apply_async(
                            kwargs={
                                "matter_id": matter_id,
                                "force_reprocess": False,
                            },
                            countdown=2,
                        )
                    else:
                        # Other engine types — mark as completed since the
                        # data likely already exists from document processing
                        logger.info(
                            "stuck_engine_job_completed",
                            job_id=job_id,
                            job_type=job_type,
                            reason="engine job auto-completed, data exists from pipeline",
                        )
                        client.table("processing_jobs").update({
                            "status": "COMPLETED",
                            "updated_at": datetime.now(UTC).isoformat(),
                        }).eq("id", job_id).execute()
                        skipped += 1
                        continue

                    dispatched += 1
                    logger.info(
                        "stuck_engine_job_dispatched",
                        job_id=job_id,
                        job_type=job_type,
                        matter_id=matter_id,
                    )

                    # Update job timestamp to prevent re-dispatch
                    client.table("processing_jobs").update(
                        {"updated_at": datetime.now(UTC).isoformat()}
                    ).eq("id", job_id).execute()

                except Exception as e:
                    errors.append({"job_id": job_id, "error": str(e)})
                    logger.warning(
                        "stuck_engine_job_dispatch_failed",
                        job_id=job_id,
                        error=str(e),
                    )
                continue

            # Document pipeline jobs require document_id
            if not doc_id:
                errors.append({"job_id": job_id, "error": "no document_id"})
                continue

            # BUG-FIX #8+#11: Check if document is already completed before re-dispatching.
            # Zombie QUEUED jobs for completed documents should be auto-completed, not re-dispatched.
            try:
                doc_resp = client.table("documents").select("status, document_type").eq("id", doc_id).execute()
                doc_status = (doc_resp.data[0]["status"] if doc_resp.data else None)
                doc_type = (doc_resp.data[0].get("document_type", "case_file") if doc_resp.data else "case_file")
                if doc_status == "completed":
                    logger.info(
                        "stuck_queued_job_auto_completed",
                        job_id=job_id,
                        document_id=doc_id,
                        reason="document already completed",
                    )
                    client.table("processing_jobs").update({
                        "status": "COMPLETED",
                        "updated_at": datetime.now(UTC).isoformat(),
                    }).eq("id", job_id).execute()
                    skipped += 1
                    continue
            except Exception:
                doc_type = "case_file"  # Safe default if check fails

            # Stage 1.3: Check if pipeline data is already complete
            # If so, just mark the job COMPLETED instead of re-dispatching
            if _is_pipeline_data_complete(client, doc_id, document_type=doc_type):
                logger.info(
                    "stuck_queued_job_data_complete",
                    job_id=job_id,
                    document_id=doc_id,
                    reason="all pipeline data exists, marking COMPLETED",
                )
                client.table("processing_jobs").update({
                    "status": "COMPLETED",
                    "updated_at": datetime.now(UTC).isoformat(),
                }).eq("id", job_id).execute()
                # Also update document status if needed
                try:
                    client.table("documents").update(
                        {"status": "completed"}
                    ).eq("id", doc_id).neq("status", "completed").execute()
                except Exception:
                    pass
                skipped += 1
                continue

            # Stage 2.4: Per-matter concurrency limit
            if matter_id:
                try:
                    from app.core.config import get_settings as _get_settings
                    _settings = _get_settings()
                    matter_processing = (
                        client.table("processing_jobs")
                        .select("id", count="exact")
                        .eq("matter_id", matter_id)
                        .eq("status", "PROCESSING")
                        .execute()
                    ).count or 0
                    if matter_processing >= _settings.max_concurrent_docs_per_matter:
                        logger.info(
                            "dispatch_stuck_queued_skipped_concurrency",
                            job_id=job_id,
                            document_id=doc_id,
                            matter_id=matter_id,
                            processing_count=matter_processing,
                            limit=_settings.max_concurrent_docs_per_matter,
                        )
                        skipped += 1
                        continue
                except Exception:
                    pass  # Fail open

            try:
                # Dispatch based on current stage — targeted dispatch avoids
                # restarting the full pipeline which breaks on idempotency guards
                if stage == "embedding":
                    embed_chunks.apply_async(
                        kwargs={"document_id": doc_id, "force": True},
                        countdown=2,
                    )
                elif stage == "entity_extraction":
                    extract_entities.apply_async(
                        kwargs={"document_id": doc_id, "force": True},
                        countdown=2,
                    )
                elif stage == "alias_resolution":
                    resolve_aliases.apply_async(
                        kwargs={"document_id": doc_id},
                        countdown=2,
                    )
                elif stage == "citation_extraction":
                    extract_citations.apply_async(
                        kwargs={"document_id": doc_id},
                        countdown=2,
                    )
                elif stage == "contradiction_detection":
                    detect_contradictions.apply_async(
                        kwargs={"document_id": doc_id},
                        countdown=2,
                    )
                elif stage is None or stage == "":
                    # Fresh job - start from beginning
                    process_document.apply_async(
                        args=[doc_id],
                        countdown=2,
                    )
                else:
                    # For other stages, restart full processing
                    process_document.apply_async(
                        args=[doc_id],
                        countdown=2,
                    )

                dispatched += 1
                logger.info(
                    "stuck_queued_job_dispatched",
                    job_id=job_id,
                    document_id=doc_id,
                    stage=stage,
                )

                # Update job timestamp to prevent re-dispatch
                client.table("processing_jobs").update(
                    {"updated_at": datetime.now(UTC).isoformat()}
                ).eq("id", job_id).execute()

            except Exception as e:
                errors.append({"job_id": job_id, "error": str(e)})
                logger.warning(
                    "stuck_queued_job_dispatch_failed",
                    job_id=job_id,
                    error=str(e),
                )

        logger.info(
            "dispatch_stuck_queued_jobs_completed",
            dispatched=dispatched,
            total=len(stuck_jobs),
            errors=len(errors),
        )

        return {
            "dispatched": dispatched,
            "total": len(stuck_jobs),
            "errors": errors,
        }

    except Exception as e:
        logger.error("dispatch_stuck_queued_jobs_failed", error=str(e))
        return {"error": str(e)}


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.sync_stale_job_status",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def sync_stale_job_status(self, stale_minutes: int = 30) -> dict:
    """Periodic task to sync job status based on actual document state.

    This handles cases where tasks complete but job status wasn't updated
    (e.g., when tasks are called standalone without job_id).

    Args:
        stale_minutes: Minutes a job can be stale before syncing status.

    Returns:
        Dictionary with sync results.
    """
    from datetime import UTC, datetime, timedelta

    from app.services.supabase.client import get_service_client

    logger.info("sync_stale_job_status_started", stale_minutes=stale_minutes)

    try:
        client = get_service_client()
        if not client:
            return {"error": "Database client not configured"}

        # Find QUEUED/PROCESSING jobs that haven't been updated recently
        cutoff_time = datetime.now(UTC) - timedelta(minutes=stale_minutes)

        response = (
            client.table("processing_jobs")
            .select("id, document_id, matter_id, current_stage, status, progress_pct")
            .in_("status", ["QUEUED", "PROCESSING"])
            .lt("updated_at", cutoff_time.isoformat())
            .execute()
        )

        stale_jobs = response.data or []

        if not stale_jobs:
            logger.debug("no_stale_jobs_to_sync")
            return {"synced": 0, "total": 0}

        synced = 0
        errors = []

        for job in stale_jobs:
            job_id = job["id"]
            doc_id = job.get("document_id")
            matter_id = job.get("matter_id")
            current_stage = job.get("current_stage")
            current_progress = job.get("progress_pct", 0)

            if not doc_id or not matter_id:
                continue

            try:
                # Check actual state
                # 1. Check chunks
                chunks_resp = (
                    client.table("chunks")
                    .select("id", count="exact")
                    .eq("document_id", doc_id)
                    .execute()
                )
                chunk_count = chunks_resp.count or 0

                # 2. Check embeddings
                emb_resp = (
                    client.table("chunks")
                    .select("id", count="exact")
                    .eq("document_id", doc_id)
                    .not_.is_("embedding", "null")
                    .execute()
                )
                embedded_count = emb_resp.count or 0

                # 3. Check entities
                entity_resp = (
                    client.table("identity_nodes")
                    .select("id", count="exact")
                    .eq("matter_id", matter_id)
                    .execute()
                )
                entity_count = entity_resp.count or 0

                # Determine actual stage based on data
                actual_stage = current_stage
                actual_progress = current_progress
                new_status = "QUEUED"

                if chunk_count == 0:
                    actual_stage = "chunking"
                    actual_progress = 40
                elif embedded_count < chunk_count:
                    actual_stage = "embedding"
                    actual_progress = 60
                elif entity_count == 0:
                    actual_stage = "entity_extraction"
                    actual_progress = 70
                else:
                    # Has entities - likely at alias_resolution or later
                    actual_stage = "alias_resolution"
                    actual_progress = 80

                # Update if different
                if actual_stage != current_stage or actual_progress != current_progress:
                    client.table("processing_jobs").update({
                        "status": new_status,
                        "current_stage": actual_stage,
                        "progress_pct": actual_progress,
                        "updated_at": datetime.now(UTC).isoformat(),
                    }).eq("id", job_id).execute()

                    synced += 1
                    logger.info(
                        "job_status_synced",
                        job_id=job_id,
                        old_stage=current_stage,
                        new_stage=actual_stage,
                        old_progress=current_progress,
                        new_progress=actual_progress,
                    )

            except Exception as e:
                errors.append({"job_id": job_id, "error": str(e)})
                logger.warning(
                    "job_status_sync_failed",
                    job_id=job_id,
                    error=str(e),
                )

        logger.info(
            "sync_stale_job_status_completed",
            synced=synced,
            total=len(stale_jobs),
            errors=len(errors),
        )

        return {
            "synced": synced,
            "total": len(stale_jobs),
            "errors": errors,
        }

    except Exception as e:
        logger.error("sync_stale_job_status_failed", error=str(e))
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
        result = run_async(
            cleanup_service.cleanup_stale_chunks(retention_hours=retention_hours)
        )

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
        result = run_async(recovery_service.recover_all_stale_chunks())

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
        result = run_async(trigger_service.check_and_trigger_merges())

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
            result = run_async(
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


# =============================================================================
# Auto-Fix Missing Extracted Text Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.fix_missing_extracted_text",
    bind=True,
    max_retries=1,
)
def fix_missing_extracted_text(self) -> dict:
    """Periodic task to fix documents with missing extracted_text.

    Finds documents where:
    - status = 'ocr_complete'
    - extracted_text is NULL
    - bounding_boxes exist

    Reconstructs extracted_text from bounding_boxes table.

    Returns:
        Dictionary with fix results.
    """
    from app.services.supabase.client import get_supabase_client

    logger.info("fix_missing_extracted_text_started")

    try:
        client = get_supabase_client()

        # Find documents with missing extracted_text but OCR complete
        docs_response = (
            client.table("documents")
            .select("id, filename, status")
            .is_("extracted_text", "null")
            .eq("status", "ocr_complete")
            .is_("deleted_at", "null")
            .execute()
        )

        docs_to_fix = docs_response.data or []
        results = {
            "checked": len(docs_to_fix),
            "fixed": 0,
            "skipped": 0,
            "errors": [],
        }

        for doc in docs_to_fix:
            doc_id = doc["id"]
            try:
                # Get all bounding boxes for this document
                bboxes_response = (
                    client.table("bounding_boxes")
                    .select("page_number, reading_order_index, text")
                    .eq("document_id", doc_id)
                    .order("page_number")
                    .order("reading_order_index")
                    .execute()
                )

                bboxes = bboxes_response.data or []
                if not bboxes:
                    logger.debug(
                        "fix_extracted_text_no_bboxes",
                        document_id=doc_id,
                    )
                    results["skipped"] += 1
                    continue

                # Build full text from bounding boxes
                texts_by_page: dict[int, list[str]] = {}
                for bbox in bboxes:
                    page = bbox.get("page_number", 1)
                    text = bbox.get("text", "")
                    if text:
                        if page not in texts_by_page:
                            texts_by_page[page] = []
                        texts_by_page[page].append(text)

                # Combine texts - join words on same page with spaces, pages with newlines
                full_text = ""
                for page in sorted(texts_by_page.keys()):
                    page_text = " ".join(texts_by_page[page])
                    full_text += page_text + "\n\n"

                full_text = full_text.strip()

                if not full_text:
                    results["skipped"] += 1
                    continue

                # Update document with extracted_text
                client.table("documents").update(
                    {"extracted_text": full_text}
                ).eq("id", doc_id).execute()

                logger.info(
                    "fix_extracted_text_success",
                    document_id=doc_id,
                    text_length=len(full_text),
                    bbox_count=len(bboxes),
                )
                results["fixed"] += 1

            except Exception as e:
                logger.error(
                    "fix_extracted_text_document_failed",
                    document_id=doc_id,
                    error=str(e),
                )
                results["errors"].append({
                    "document_id": doc_id,
                    "error": str(e),
                })

        logger.info(
            "fix_missing_extracted_text_completed",
            checked=results["checked"],
            fixed=results["fixed"],
            skipped=results["skipped"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("fix_missing_extracted_text_failed", error=str(e))
        return {"error": str(e)}


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.sync_missing_entity_ids",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def sync_missing_entity_ids(self) -> dict:
    """Sync entity_ids from entity_mentions to chunks for documents missing the linkage.

    This maintenance task finds documents that have entity_mentions but where
    chunks.entity_ids is not populated, and syncs them. This handles:
    - Documents processed before the entity_ids sync was added
    - Documents where the sync failed for any reason

    Runs every 10 minutes to catch any missed syncs.

    Returns:
        Dictionary with sync results.
    """
    from app.services.supabase.client import get_service_client

    logger.info("sync_missing_entity_ids_started")

    results = {
        "documents_checked": 0,
        "documents_synced": 0,
        "chunks_updated": 0,
        "errors": [],
    }

    try:
        client = get_service_client()
        if client is None:
            return {"error": "Database client not configured"}

        # Find documents with entity_mentions but potentially missing chunk linkage
        # Get all documents that have entity_mentions with chunk_ids
        mentions_response = (
            client.table("entity_mentions")
            .select("document_id")
            .not_.is_("chunk_id", "null")
            .execute()
        )

        if not mentions_response.data:
            logger.info("sync_missing_entity_ids_no_mentions")
            return results

        # Get unique document IDs
        doc_ids_with_mentions = set(m["document_id"] for m in mentions_response.data)
        results["documents_checked"] = len(doc_ids_with_mentions)

        # For each document, check if chunks have entity_ids synced
        for doc_id in doc_ids_with_mentions:
            try:
                # Check if this document has any chunks with entity_ids
                synced_check = (
                    client.table("chunks")
                    .select("id", count="exact")
                    .eq("document_id", doc_id)
                    .not_.is_("entity_ids", "null")
                    .limit(1)
                    .execute()
                )

                # If already synced, skip
                if synced_check.count and synced_check.count > 0:
                    continue

                # Get entity_mentions for this document and sync
                doc_mentions = (
                    client.table("entity_mentions")
                    .select("entity_id, chunk_id")
                    .eq("document_id", doc_id)
                    .not_.is_("chunk_id", "null")
                    .execute()
                )

                if not doc_mentions.data:
                    continue

                # Build chunk -> entity_ids map
                chunk_entities: dict[str, set[str]] = {}
                for m in doc_mentions.data:
                    chunk_id = m.get("chunk_id")
                    entity_id = m.get("entity_id")
                    if chunk_id and entity_id:
                        if chunk_id not in chunk_entities:
                            chunk_entities[chunk_id] = set()
                        chunk_entities[chunk_id].add(entity_id)

                # Update each chunk
                for chunk_id, entity_ids in chunk_entities.items():
                    client.table("chunks").update(
                        {"entity_ids": list(entity_ids)}
                    ).eq("id", chunk_id).execute()
                    results["chunks_updated"] += 1

                results["documents_synced"] += 1
                logger.info(
                    "sync_entity_ids_document_complete",
                    document_id=doc_id,
                    chunks_updated=len(chunk_entities),
                )

            except Exception as e:
                logger.warning(
                    "sync_entity_ids_document_failed",
                    document_id=doc_id,
                    error=str(e),
                )
                results["errors"].append({"document_id": doc_id, "error": str(e)})

        logger.info(
            "sync_missing_entity_ids_completed",
            documents_checked=results["documents_checked"],
            documents_synced=results["documents_synced"],
            chunks_updated=results["chunks_updated"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("sync_missing_entity_ids_failed", error=str(e))
        return {"error": str(e)}


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.resume_stuck_pipelines",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def resume_stuck_pipelines(self, stale_hours: int = 1, stale_minutes: int | None = None) -> dict:
    """Resume document processing pipelines that got stuck at intermediate stages.

    Finds documents that are stuck at ocr_complete (or other intermediate states)
    AND processing_jobs stuck in PROCESSING state (BUG-LT-G fix).

    This handles:
    - Documents where Celery task chain broke
    - Documents where worker crashed mid-pipeline
    - Documents uploaded before a bug fix
    - Processing jobs stuck at any intermediate stage after worker restart

    Runs every 15 minutes to recover stuck documents.

    Args:
        stale_hours: Hours after which a document is considered stuck (legacy).
        stale_minutes: Minutes after which a job is considered stuck (preferred).

    Returns:
        Dictionary with recovery results.
    """
    from datetime import datetime, timedelta, timezone

    from app.services.supabase.client import get_service_client

    # Use stale_minutes if provided, otherwise fall back to stale_hours
    effective_minutes = stale_minutes if stale_minutes is not None else stale_hours * 60
    logger.info("resume_stuck_pipelines_started", stale_minutes=effective_minutes)

    results = {
        "checked": 0,
        "resumed": 0,
        "skipped": 0,
        "errors": [],
    }

    try:
        client = get_service_client()
        if client is None:
            return {"error": "Database client not configured"}

        # RECONCILER STEP (ARCH-003 stepping stone, 2026-05-14):
        # Query ALL non-terminal documents past the cutoff, not just "ocr_complete".
        # This catches documents stuck at ANY status — the forensic hunt (2026-05-14)
        # found that 10 of 13 statuses were invisible to all sweeps.
        # The old query: .eq("status", "ocr_complete").not_.is_("extracted_text", "null")
        # The new query: status NOT IN terminal states. Let _is_pipeline_data_complete()
        # decide what to do — it's the single source of truth for completion.
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=effective_minutes)

        _TERMINAL_STATUSES = ["completed", "failed", "deleted"]
        stuck_docs = (
            client.table("documents")
            .select("id, matter_id, filename, status, updated_at, extracted_text, document_type")
            .not_.in_("status", _TERMINAL_STATUSES)
            .is_("deleted_at", "null")
            .lt("updated_at", cutoff_time.isoformat())
            .execute()
        )

        if not stuck_docs.data:
            logger.info("resume_stuck_pipelines_none_found")
            # Don't return early — still need to check library_documents below

        results["checked"] = len(stuck_docs.data or [])

        # Stage 1.2: Import PipelineLock for dedup checks
        from app.services.distributed_lock import PipelineLock

        for doc in (stuck_docs.data or []):
            doc_id = doc["id"]
            matter_id = doc["matter_id"]
            filename = doc.get("filename", "unknown")
            doc_type = doc.get("document_type", "case_file")

            # Stage 1.2: Skip if pipeline is already running
            if PipelineLock(doc_id).is_locked():
                logger.info(
                    "resume_stuck_pipeline_skipped_locked",
                    document_id=doc_id,
                    filename=filename,
                )
                results["skipped"] += 1
                continue

            try:
                # Stage 1.3: Fast path — if all pipeline data exists, mark complete
                if _is_pipeline_data_complete(client, doc_id, document_type=doc_type):
                    logger.info(
                        "reconciler_data_complete",
                        document_id=doc_id,
                        filename=filename,
                        doc_status=doc.get("status", ""),
                        reason="all pipeline data exists, marking completed",
                    )
                    client.table("documents").update(
                        {"status": "completed"}
                    ).eq("id", doc_id).execute()
                    # Also complete any stuck processing jobs
                    try:
                        from datetime import datetime as dt_cls, timezone as tz_cls
                        client.table("processing_jobs").update({
                            "status": "COMPLETED",
                            "updated_at": dt_cls.now(tz_cls.utc).isoformat(),
                        }).eq("document_id", doc_id).in_(
                            "status", ["PROCESSING", "QUEUED"]
                        ).execute()
                    except Exception:
                        pass
                    results["resumed"] += 1
                    continue

                # Reconciler: derive correct action from observed data, not status label.
                # Check what stages are missing and dispatch from the right point.
                doc_status = doc.get("status", "")
                has_text = doc.get("extracted_text") is not None

                # Pre-OCR statuses: no extracted_text yet — need full pipeline restart
                if not has_text and doc_status in ("pending", "processing"):
                    logger.info(
                        "reconciler_dispatch_full_pipeline",
                        document_id=doc_id,
                        filename=filename,
                        doc_status=doc_status,
                        reason="no extracted_text, restarting from OCR",
                    )
                    from app.workers.tasks.document_tasks import process_document
                    process_document.apply_async(
                        kwargs={"document_id": doc_id},
                        countdown=5,
                    )
                    results["resumed"] += 1
                    continue

                # Also mark FAILED jobs for this doc as QUEUED so Part B can re-dispatch
                try:
                    from datetime import datetime as dt_cls2, timezone as tz_cls2
                    client.table("processing_jobs").update({
                        "status": "QUEUED",
                        "updated_at": dt_cls2.now(tz_cls2.utc).isoformat(),
                    }).eq("document_id", doc_id).eq("status", "FAILED").execute()
                except Exception:
                    pass  # Best effort — Part A handles recovery below

                # 1. Check if chunks exist
                chunks = (
                    client.table("chunks")
                    .select("id", count="exact")
                    .eq("document_id", doc_id)
                    .execute()
                )

                if not chunks.count or chunks.count == 0:
                    # No chunks - need to run from chunking stage
                    logger.info(
                        "reconciler_dispatch_from_chunking",
                        document_id=doc_id,
                        filename=filename,
                        doc_status=doc_status,
                    )
                    _dispatch_from_chunking(doc_id, matter_id)
                    results["resumed"] += 1
                    continue

                # 2. Check if embeddings exist (embedding column in chunks table)
                embeddings = (
                    client.table("chunks")
                    .select("id", count="exact")
                    .eq("document_id", doc_id)
                    .not_.is_("embedding", "null")
                    .execute()
                )

                if not embeddings.count or embeddings.count == 0:
                    # No embeddings - need to run from embedding stage
                    logger.info(
                        "resume_pipeline_from_embedding",
                        document_id=doc_id,
                        filename=filename,
                    )
                    _dispatch_from_embedding(doc_id, matter_id)
                    results["resumed"] += 1
                    continue

                # 3. Check if entities exist
                entities = (
                    client.table("entity_mentions")
                    .select("id", count="exact")
                    .eq("document_id", doc_id)
                    .execute()
                )

                if not entities.count or entities.count == 0:
                    # No entities - need to run from entity extraction
                    logger.info(
                        "resume_pipeline_from_entities",
                        document_id=doc_id,
                        filename=filename,
                    )
                    _dispatch_from_entities(doc_id, matter_id)
                    results["resumed"] += 1
                    continue

                # 4. Document has all stages but status never updated
                # Just update status to completed
                logger.info(
                    "resume_pipeline_mark_complete",
                    document_id=doc_id,
                    filename=filename,
                )
                client.table("documents").update(
                    {"status": "completed"}
                ).eq("id", doc_id).execute()
                results["resumed"] += 1

            except Exception as e:
                logger.warning(
                    "resume_pipeline_document_failed",
                    document_id=doc_id,
                    error=str(e),
                )
                results["errors"].append({"document_id": doc_id, "error": str(e)})

        # =================================================================
        # BUG-LT-G FIX: Also recover stuck PROCESSING jobs at any stage
        # The original code only checked documents with status="ocr_complete".
        # When a worker restarts, in-flight tasks are lost but the processing_job
        # remains in PROCESSING state. This section catches those stuck jobs.
        # =================================================================
        try:
            stuck_jobs = (
                client.table("processing_jobs")
                .select("id, document_id, matter_id, current_stage, updated_at, metadata, status")
                .eq("status", "PROCESSING")
                .lt("updated_at", cutoff_time.isoformat())
                .execute()
            )

            for job in (stuck_jobs.data or []):
                job_doc_id = job.get("document_id")
                job_matter_id = job.get("matter_id")
                stage = job.get("current_stage", "")

                if not job_doc_id:
                    continue

                # Stage 1.2: Skip if pipeline is already running
                if PipelineLock(job_doc_id).is_locked():
                    logger.info(
                        "resume_stuck_job_skipped_locked",
                        job_id=job["id"],
                        document_id=job_doc_id,
                    )
                    continue

                # BUG-FIX #8+#11: Check if document is already completed before re-dispatching.
                job_doc_type = "case_file"
                try:
                    doc_check = client.table("documents").select("status, document_type").eq("id", job_doc_id).execute()
                    doc_st = (doc_check.data[0]["status"] if doc_check.data else None)
                    job_doc_type = (doc_check.data[0].get("document_type", "case_file") if doc_check.data else "case_file")
                    if doc_st == "completed":
                        logger.info(
                            "stuck_processing_job_auto_completed",
                            job_id=job["id"],
                            document_id=job_doc_id,
                            reason="document already completed",
                        )
                        client.table("processing_jobs").update({
                            "status": "COMPLETED",
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }).eq("id", job["id"]).execute()
                        results["resumed"] += 1
                        continue
                except Exception:
                    pass  # If check fails, proceed with normal dispatch

                # Stage 1.3: Check if pipeline data is complete — mark done instead of re-dispatching
                if _is_pipeline_data_complete(client, job_doc_id, document_type=job_doc_type):
                    logger.info(
                        "stuck_processing_job_data_complete",
                        job_id=job["id"],
                        document_id=job_doc_id,
                        reason="all pipeline data exists, marking COMPLETED",
                    )
                    client.table("processing_jobs").update({
                        "status": "COMPLETED",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", job["id"]).execute()
                    client.table("documents").update(
                        {"status": "completed"}
                    ).eq("id", job_doc_id).neq("status", "completed").execute()
                    results["resumed"] += 1
                    continue

                try:
                    # Determine which stage to resume from based on current_stage
                    if stage in ("contradiction_detection",):
                        # Last stage — just mark completed if contradictions exist
                        contradictions = (
                            client.table("statement_comparisons")
                            .select("id", count="exact")
                            .eq("matter_id", job_matter_id)
                            .execute()
                        )
                        if contradictions.count and contradictions.count > 0:
                            client.table("processing_jobs").update(
                                {"status": "COMPLETED"}
                            ).eq("id", job["id"]).execute()
                            results["resumed"] += 1
                            logger.info(
                                "resume_stuck_job_completed",
                                job_id=job["id"],
                                document_id=job_doc_id,
                                stage=stage,
                            )
                        else:
                            # Re-dispatch contradiction detection
                            from app.workers.tasks.document_tasks import detect_contradictions
                            detect_contradictions.apply_async(
                                kwargs={"document_id": job_doc_id},
                                queue="default",
                                countdown=5,
                            )
                            results["resumed"] += 1
                    elif stage in ("citation_extraction", "citation_verification"):
                        from app.workers.tasks.document_tasks import extract_citations
                        extract_citations.apply_async(
                            kwargs={"document_id": job_doc_id},
                            queue="default",
                            countdown=5,
                        )
                        results["resumed"] += 1
                    elif stage == "entity_extraction":
                        _dispatch_from_entities(job_doc_id, job_matter_id)
                        results["resumed"] += 1
                    elif stage == "embedding":
                        _dispatch_from_embedding(job_doc_id, job_matter_id)
                        results["resumed"] += 1
                    elif stage in ("chunking", "validation", "confidence", "ocr"):
                        _dispatch_from_chunking(job_doc_id, job_matter_id)
                        results["resumed"] += 1
                    else:
                        # Unknown stage — restart from chunking as safe default
                        _dispatch_from_chunking(job_doc_id, job_matter_id)
                        results["resumed"] += 1

                    # Update job timestamp to prevent immediate re-dispatch
                    from datetime import datetime as dt_cls, timezone as tz_cls
                    client.table("processing_jobs").update(
                        {"updated_at": dt_cls.now(tz_cls.utc).isoformat()}
                    ).eq("id", job["id"]).execute()

                    logger.info(
                        "resume_stuck_processing_job",
                        job_id=job["id"],
                        document_id=job_doc_id,
                        stage=stage,
                    )

                except Exception as e:
                    logger.warning(
                        "resume_stuck_processing_job_failed",
                        job_id=job["id"],
                        document_id=job_doc_id,
                        error=str(e),
                    )
                    results["errors"].append({"job_id": job["id"], "error": str(e)})

        except Exception as e:
            logger.warning("resume_stuck_processing_jobs_scan_failed", error=str(e))

        # Also recover stuck library documents (pending/processing for too long)
        handled_lib_ids = set()
        try:
            stuck_lib_docs = (
                client.table("library_documents")
                .select("id, storage_path, status")
                .in_("status", ["pending", "processing"])
                .lt("updated_at", cutoff_time.isoformat())
                .execute()
            )
            for lib_doc in (stuck_lib_docs.data or []):
                lib_doc_id = lib_doc["id"]
                handled_lib_ids.add(lib_doc_id)

                # Check if chunks already exist — if so, skip OCR and just embed
                chunk_check = (
                    client.table("library_chunks")
                    .select("id", count="exact")
                    .eq("library_document_id", lib_doc_id)
                    .execute()
                )
                chunk_count = chunk_check.count or 0

                if chunk_count > 0:
                    # Chunks exist — dispatch embedding only (not full OCR)
                    from app.workers.tasks.library_tasks import embed_library_chunks
                    embed_library_chunks.apply_async(
                        kwargs={"library_document_id": lib_doc_id},
                        queue="default",
                    )
                    results["resumed"] += 1
                    logger.info(
                        "resume_stuck_library_document_embed_only",
                        library_document_id=lib_doc_id,
                        chunk_count=chunk_count,
                        status=lib_doc["status"],
                    )
                elif lib_doc.get("storage_path"):
                    # No chunks — need full OCR + chunk + embed
                    from app.workers.tasks.library_tasks import ocr_and_process_library_document
                    ocr_and_process_library_document.apply_async(
                        kwargs={"library_document_id": lib_doc_id, "storage_path": lib_doc["storage_path"]},
                        queue="default",
                    )
                    results["resumed"] += 1
                    logger.info(
                        "resume_stuck_library_document",
                        library_document_id=lib_doc_id,
                        status=lib_doc["status"],
                    )
        except Exception as e:
            logger.warning("resume_stuck_library_documents_failed", error=str(e))

        # GAP-21: derive "needs embedding" from OBSERVED chunk state, not status.
        # The status-keyed query above cannot see a library doc wrongly marked
        # COMPLETED while NULL-embedding chunks remain (the GAP-21 bug — e.g. the
        # Income Tax Act, fetch-truncated at 1000 of 2422 chunks). Find any doc
        # with NULL-embedding chunks and re-dispatch embed-only. Excludes 'failed'
        # docs (we gave up — avoids re-dispatch thrash) and docs already handled
        # above. Convergence is guaranteed by embed_library_chunks itself: every
        # re-run reaches COMPLETED (0 NULL remain) or FAILED (no progress) —
        # never an infinite loop (cf. E2E-007 non-converging sweeps).
        try:
            null_emb_rows = (
                client.table("library_chunks")
                .select("library_document_id")
                .is_("embedding", "null")
                .limit(5000)  # distinct doc-ids only; N=1 scale, far above need
                .execute()
            )
            candidate_ids = {
                r["library_document_id"] for r in (null_emb_rows.data or [])
            } - handled_lib_ids
            if candidate_ids:
                reconcile_docs = (
                    client.table("library_documents")
                    .select("id, status")
                    .in_("id", list(candidate_ids))
                    .neq("status", "failed")
                    .execute()
                )
                from app.workers.tasks.library_tasks import embed_library_chunks
                for rec_doc in (reconcile_docs.data or []):
                    embed_library_chunks.apply_async(
                        kwargs={"library_document_id": rec_doc["id"]},
                        queue="default",
                    )
                    results["resumed"] += 1
                    logger.info(
                        "reconcile_library_doc_null_embeddings",
                        library_document_id=rec_doc["id"],
                        status=rec_doc["status"],
                    )
        except Exception as e:
            logger.warning("reconcile_library_null_embeddings_failed", error=str(e))

        logger.info(
            "resume_stuck_pipelines_completed",
            checked=results["checked"],
            resumed=results["resumed"],
            skipped=results["skipped"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("resume_stuck_pipelines_failed", error=str(e))
        return {"error": str(e)}


def _dispatch_from_chunking(document_id: str, matter_id: str) -> None:
    """Dispatch unified post-OCR pipeline from the beginning.

    Uses create_post_ocr_chain for consistency with normal document processing.
    The unified chain starts with validate_ocr → chunk_document → etc.
    """
    from app.workers.tasks.pipeline_chains import create_post_ocr_chain

    # Use the unified chain - same as normal document processing
    # This ensures feature parity and consistent behavior
    chain = create_post_ocr_chain(
        document_id=document_id,
        matter_id=matter_id,
        job_id=None,  # No job tracking for recovery
    )
    chain.apply_async(queue="default")

    logger.info(
        "recovery_pipeline_dispatched",
        document_id=document_id,
        matter_id=matter_id,
        stage="from_chunking",
    )


def _dispatch_from_embedding(document_id: str, matter_id: str) -> None:
    """Dispatch pipeline from embedding stage onwards.

    extract_entities fans out to citations, dates, and aliases on completion.
    """
    from celery import chain as celery_chain

    from app.workers.tasks.document_tasks import (
        embed_chunks,
        extract_entities,
    )

    # Pass prev_result dict with document_id for chain tasks
    prev_result = {"document_id": document_id, "status": "chunked"}

    task_chain = celery_chain(
        embed_chunks.s(prev_result),
        extract_entities.s(),
    )
    task_chain.apply_async(queue="default")

    logger.info(
        "recovery_pipeline_dispatched",
        document_id=document_id,
        matter_id=matter_id,
        stage="from_embedding",
    )


def _dispatch_from_entities(document_id: str, matter_id: str) -> None:
    """Dispatch pipeline from entity extraction stage onwards.

    extract_entities fans out to citations, dates, and aliases on completion.
    """
    from app.workers.tasks.document_tasks import extract_entities

    # Pass prev_result dict with document_id for chain tasks
    prev_result = {"document_id": document_id, "status": "embedded"}

    extract_entities.apply_async(
        args=[prev_result],
        queue="default",
    )

    logger.info(
        "recovery_pipeline_dispatched",
        document_id=document_id,
        matter_id=matter_id,
        stage="from_entities",
    )


# =============================================================================
# Act Resolution Sync Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.sync_act_resolutions_with_documents",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def sync_act_resolutions_with_documents(self) -> dict:
    """Periodic task to sync act_resolutions with documents table.

    This handles cases where:
    - Act documents were uploaded/fetched but resolution wasn't updated
    - Resolution shows 'missing' but matching document exists
    - Document was deleted but resolution still shows 'available'

    Runs every 15 minutes to ensure data consistency.

    Returns:
        Dictionary with sync results.
    """
    from app.engines.citation.abbreviations import normalize_act_name
    from app.services.supabase.client import get_service_client

    logger.info("sync_act_resolutions_with_documents_started")

    results = {
        "matters_checked": 0,
        "resolutions_fixed": 0,
        "missing_to_available": 0,
        "available_to_missing": 0,
        "missing_to_auto_fetching": 0,
        "errors": [],
    }

    try:
        client = get_service_client()
        if client is None:
            return {"error": "Database client not configured"}

        # Get all matters with act_resolutions
        matters_response = (
            client.table("act_resolutions")
            .select("matter_id")
            .execute()
        )

        if not matters_response.data:
            logger.info("sync_act_resolutions_no_matters")
            return results

        # Get unique matter IDs
        matter_ids = set(r["matter_id"] for r in matters_response.data)
        results["matters_checked"] = len(matter_ids)

        for matter_id in matter_ids:
            try:
                # Get all act documents for this matter (exclude soft-deleted)
                docs_response = (
                    client.table("documents")
                    .select("id, filename")
                    .eq("matter_id", matter_id)
                    .eq("document_type", "act")
                    .is_("deleted_at", "null")
                    .execute()
                )

                act_docs = docs_response.data or []

                # Build map of normalized act name -> document
                act_doc_map: dict[str, dict] = {}
                for doc in act_docs:
                    # Extract act name from filename
                    act_name = doc.get("filename", "")
                    if act_name:
                        normalized = normalize_act_name(act_name)
                        act_doc_map[normalized] = doc

                # Get all resolutions for this matter
                resolutions_response = (
                    client.table("act_resolutions")
                    .select("id, act_name_normalized, resolution_status, act_document_id, validation_cache_id, is_valid")
                    .eq("matter_id", matter_id)
                    .execute()
                )

                resolutions = resolutions_response.data or []

                for resolution in resolutions:
                    res_id = resolution["id"]
                    normalized_name = resolution["act_name_normalized"]
                    current_status = resolution["resolution_status"]
                    current_doc_id = resolution.get("act_document_id")

                    # Check if we have a matching document
                    matching_doc = act_doc_map.get(normalized_name)

                    # Case 1: Resolution says 'missing' but document exists
                    if current_status == "missing" and matching_doc:
                        client.table("act_resolutions").update({
                            "resolution_status": "available",
                            "act_document_id": matching_doc["id"],
                            "user_action": "uploaded",
                        }).eq("id", res_id).execute()

                        results["resolutions_fixed"] += 1
                        results["missing_to_available"] += 1
                        logger.info(
                            "act_resolution_fixed_missing_to_available",
                            matter_id=matter_id,
                            act_name=normalized_name,
                            document_id=matching_doc["id"],
                        )

                    # Case 2: Resolution says 'available' but document doesn't exist
                    # (and document_id is set but document was deleted)
                    elif current_status in ("available", "auto_fetched") and current_doc_id:
                        # Check if the referenced document still exists
                        doc_check = (
                            client.table("documents")
                            .select("id")
                            .eq("id", current_doc_id)
                            .execute()
                        )

                        if not doc_check.data:
                            # Document was deleted, revert to missing
                            client.table("act_resolutions").update({
                                "resolution_status": "missing",
                                "act_document_id": None,
                                "user_action": "pending",
                            }).eq("id", res_id).execute()

                            results["resolutions_fixed"] += 1
                            results["available_to_missing"] += 1
                            logger.info(
                                "act_resolution_fixed_available_to_missing",
                                matter_id=matter_id,
                                act_name=normalized_name,
                                deleted_document_id=current_doc_id,
                            )

                    # Case 3: Resolution says 'missing' but is validated + auto-fetch enabled
                    # Catches acts validated before auto-fetch was deployed, or any future state drift
                    elif current_status == "missing" and not matching_doc:
                        if resolution.get("validation_cache_id") and resolution.get("is_valid"):
                            from app.core.config import get_settings
                            settings = get_settings()
                            if settings.india_code_auto_fetch_enabled:
                                client.table("act_resolutions").update({
                                    "resolution_status": "auto_fetching",
                                }).eq("id", res_id).execute()

                                results["resolutions_fixed"] += 1
                                results["missing_to_auto_fetching"] += 1
                                logger.info(
                                    "act_resolution_fixed_missing_to_auto_fetching",
                                    matter_id=matter_id,
                                    act_name=normalized_name,
                                )

            except Exception as e:
                logger.warning(
                    "sync_act_resolutions_matter_failed",
                    matter_id=matter_id,
                    error=str(e),
                )
                results["errors"].append({"matter_id": matter_id, "error": str(e)})

        logger.info(
            "sync_act_resolutions_with_documents_completed",
            matters_checked=results["matters_checked"],
            resolutions_fixed=results["resolutions_fixed"],
            missing_to_available=results["missing_to_available"],
            available_to_missing=results["available_to_missing"],
            missing_to_auto_fetching=results["missing_to_auto_fetching"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("sync_act_resolutions_with_documents_failed", error=str(e))
        return {"error": str(e)}


# =============================================================================
# One-Time Repair: Stuck Missing Acts
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.repair_stuck_missing_acts",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def repair_stuck_missing_acts(self) -> dict:
    """One-time repair task for acts stuck in 'missing' that should be 'auto_fetching'.

    Finds all act_resolutions where:
    - resolution_status = 'missing'
    - is_valid = True
    - validation_cache_id IS NOT NULL

    These are acts that were validated before auto-fetch was deployed.
    Transitions them to 'auto_fetching' and triggers the fetch pipeline.

    Idempotent — safe to re-run.

    Returns:
        Dictionary with repair results.
    """
    from app.core.config import get_settings
    from app.services.supabase.client import get_service_client

    logger.info("repair_stuck_missing_acts_started")

    results = {
        "found": 0,
        "transitioned": 0,
        "errors": [],
    }

    try:
        settings = get_settings()
        if not settings.india_code_auto_fetch_enabled:
            logger.info("repair_stuck_missing_acts_skipped_auto_fetch_disabled")
            return {"skipped": True, "reason": "auto_fetch_disabled"}

        client = get_service_client()
        if client is None:
            return {"error": "Database client not configured"}

        # Find all stuck acts: missing + validated + has cache entry
        stuck_response = (
            client.table("act_resolutions")
            .select("id, matter_id, act_name_normalized, act_name_display, validation_cache_id")
            .eq("resolution_status", "missing")
            .eq("is_valid", True)
            .not_.is_("validation_cache_id", "null")
            .execute()
        )

        stuck_acts = stuck_response.data or []
        results["found"] = len(stuck_acts)

        if not stuck_acts:
            logger.info("repair_stuck_missing_acts_none_found")
            return results

        for act in stuck_acts:
            try:
                client.table("act_resolutions").update({
                    "resolution_status": "auto_fetching",
                }).eq("id", act["id"]).execute()

                results["transitioned"] += 1
                logger.info(
                    "repair_stuck_act_transitioned",
                    act_name=act.get("act_name_normalized"),
                    matter_id=act.get("matter_id"),
                )
            except Exception as e:
                results["errors"].append({
                    "act_id": act["id"],
                    "error": str(e),
                })

        # Trigger fetch pipeline to process the newly queued acts
        if results["transitioned"] > 0:
            from app.workers.tasks.act_validation_tasks import fetch_acts_from_india_code
            fetch_acts_from_india_code.apply_async(queue="low")
            logger.info("repair_stuck_missing_acts_fetch_triggered", count=results["transitioned"])

        logger.info(
            "repair_stuck_missing_acts_completed",
            found=results["found"],
            transitioned=results["transitioned"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("repair_stuck_missing_acts_failed", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Citation Status Sync Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.sync_citation_statuses_with_resolutions",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def sync_citation_statuses_with_resolutions(self) -> dict:
    """Periodic task to sync citation verification_status with act_resolutions.

    This handles cases where:
    - Act was uploaded but citation statuses weren't updated (trigger task failed)
    - Citations show 'act_unavailable' but matching act_resolution shows 'available'

    Uses normalized act name matching to handle variations like:
    - "TORTS Act" vs "Torts Act"
    - "Companies Act, 2013" vs "Companies Act"

    Runs every 15 minutes to ensure data consistency.

    Returns:
        Dictionary with sync results.
    """
    from app.engines.citation.abbreviations import normalize_act_name
    from app.services.supabase.client import get_service_client

    logger.info("sync_citation_statuses_with_resolutions_started")

    results = {
        "matters_checked": 0,
        "citations_updated": 0,
        "act_unavailable_to_pending": 0,
        "verifications_dispatched": 0,
        "errors": [],
    }

    # RISK-1 (2026-06-03): derived-state authority for citation verification.
    # Verification for auto-fetched Acts used to fire ONLY from a transient Celery
    # chain callback (act_validation_tasks -> fire_library_callbacks). That callback
    # is persisted nowhere, so any Act healed by the embed reconciler
    # (resume_stuck_pipelines, which re-dispatches embed-only with no callbacks) got
    # embedded but never verified — its citations were flipped act_unavailable->pending
    # below and then stranded forever. We now DERIVE "verification owed" from DB state
    # (auto_fetched/available resolution + fully-embedded Act doc + >=1 non-terminal
    # citation) and fire the SAME convergence task the callback uses
    # (trigger_verification_on_act_upload). Convergence is guaranteed by
    # get_citations_for_act(exclude_verified=True), which now excludes the full terminal
    # set {verified, mismatch, section_not_found} — once every citation is terminal the
    # verify task is a 0-Gemini no-op and this sweep stops selecting the Act.
    # Budget bucket: GEMINI_FLASH (operation="citation_verification"), behind the
    # existing get_rate_limiter(LLMProvider.GEMINI). No new queue/worker/quota.
    from app.workers.tasks.verification_tasks import trigger_verification_on_act_upload

    _NON_TERMINAL = ["act_unavailable", "pending"]
    _embed_cache: dict[str, bool] = {}

    def _act_doc_fully_embedded(lib_doc_id: str | None) -> bool:
        """True iff the library Act doc is COMPLETED with >=1 chunk and 0 NULL
        embeddings — the GAP-21 derived-state definition of 'fully embedded'.
        Verifying against partial embeddings yields false section_not_found
        (RISK-1(b)), so this gate must pass before dispatch."""
        if not lib_doc_id:
            return False
        if lib_doc_id in _embed_cache:
            return _embed_cache[lib_doc_id]
        ok = False
        try:
            doc = (
                client.table("library_documents")
                .select("status")
                .eq("id", lib_doc_id)
                .limit(1)
                .execute()
            )
            if doc.data and doc.data[0].get("status") == "completed":
                total = (
                    client.table("library_chunks")
                    .select("id", count="exact")
                    .eq("library_document_id", lib_doc_id)
                    .limit(1)
                    .execute()
                )
                if (total.count or 0) > 0:
                    null_emb = (
                        client.table("library_chunks")
                        .select("id", count="exact")
                        .eq("library_document_id", lib_doc_id)
                        .is_("embedding", "null")
                        .limit(1)
                        .execute()
                    )
                    ok = (null_emb.count or 0) == 0
        except Exception as e:
            logger.warning(
                "act_doc_embed_gate_check_failed",
                library_document_id=lib_doc_id,
                error=str(e),
            )
            ok = False
        _embed_cache[lib_doc_id] = ok
        return ok

    try:
        client = get_service_client()
        if client is None:
            return {"error": "Database client not configured"}

        # Get all act_resolutions that have act_document_id (i.e., available)
        available_resolutions = (
            client.table("act_resolutions")
            .select("matter_id, act_name_normalized, act_name_display, act_document_id")
            .not_.is_("act_document_id", "null")
            .in_("resolution_status", ["available", "auto_fetched"])
            .execute()
        )

        if not available_resolutions.data:
            logger.info("sync_citation_statuses_no_available_resolutions")
            return results

        # Group by matter_id for efficient processing
        matters_map: dict[str, list[dict]] = {}
        for res in available_resolutions.data:
            matter_id = res["matter_id"]
            if matter_id not in matters_map:
                matters_map[matter_id] = []
            matters_map[matter_id].append(res)

        results["matters_checked"] = len(matters_map)

        for matter_id, resolutions in matters_map.items():
            try:
                # Map normalized name -> resolution (for dispatch lookup). Multiple
                # resolutions may share a normalized name; any maps to the same Act doc.
                res_by_norm = {res["act_name_normalized"]: res for res in resolutions}
                available_normalized_names = set(res_by_norm.keys())

                # Get all NON-TERMINAL citations for this matter (act_unavailable +
                # pending). Two uses: (a) flip act_unavailable->pending where the Act is
                # now available (existing behaviour); (b) RISK-1: discover which Acts
                # still have non-terminal citations so we can derive verification owed.
                # Handle pagination (Supabase returns max 1000 rows per request).
                citations_to_update = []
                non_terminal_norms: set[str] = set()
                offset = 0
                page_size = 1000

                while True:
                    citations_response = (
                        client.table("citations")
                        .select("id, act_name, verification_status")
                        .eq("matter_id", matter_id)
                        .in_("verification_status", _NON_TERMINAL)
                        .range(offset, offset + page_size - 1)
                        .execute()
                    )

                    citations = citations_response.data or []
                    if not citations:
                        break

                    for citation in citations:
                        citation_normalized = normalize_act_name(citation.get("act_name", ""))
                        # Track every non-terminal citation whose Act is resolved here —
                        # this is the per-Act "still needs verification" signal (RISK-1).
                        if citation_normalized in available_normalized_names:
                            non_terminal_norms.add(citation_normalized)
                            # Flip only the act_unavailable ones to pending.
                            if citation.get("verification_status") == "act_unavailable":
                                citations_to_update.append(citation["id"])

                    # If we got fewer than page_size, we've reached the end
                    if len(citations) < page_size:
                        break
                    offset += page_size

                # Batch update citation statuses (max 100 per request to avoid JSON errors)
                if citations_to_update:
                    from datetime import UTC, datetime

                    UPDATE_BATCH_SIZE = 100
                    matter_updated = 0

                    for i in range(0, len(citations_to_update), UPDATE_BATCH_SIZE):
                        batch = citations_to_update[i:i + UPDATE_BATCH_SIZE]
                        update_result = client.table("citations").update({
                            "verification_status": "pending",
                            "updated_at": datetime.now(UTC).isoformat(),
                        }).in_("id", batch).execute()
                        matter_updated += len(update_result.data) if update_result.data else 0

                    results["citations_updated"] += matter_updated
                    results["act_unavailable_to_pending"] += matter_updated

                    logger.info(
                        "citation_statuses_synced",
                        matter_id=matter_id,
                        citations_updated=matter_updated,
                    )

                # RISK-1: derive verification owed. For each Act in this matter that
                # (a) still has >=1 non-terminal citation and (b) is FULLY embedded,
                # dispatch the same convergence task the upload callback uses. This is
                # idempotent and self-converging: trigger_verification_on_act_upload ->
                # verify_citations_for_act -> get_citations_for_act(exclude_verified=True),
                # which excludes the full terminal set, so once every citation is terminal
                # this becomes a 0-Gemini no-op and non_terminal_norms drops the Act.
                for norm in non_terminal_norms:
                    res = res_by_norm.get(norm)
                    if not res:
                        continue
                    act_doc_id = res.get("act_document_id")
                    if not _act_doc_fully_embedded(act_doc_id):
                        continue
                    try:
                        trigger_verification_on_act_upload.apply_async(
                            kwargs={
                                "matter_id": matter_id,
                                "act_name": res.get("act_name_display") or norm,
                                "act_document_id": act_doc_id,
                            },
                            queue="default",
                        )
                        results["verifications_dispatched"] += 1
                        logger.info(
                            "citation_verification_dispatched_by_reconciler",
                            matter_id=matter_id,
                            act_document_id=act_doc_id,
                            act_name=res.get("act_name_display") or norm,
                        )
                    except Exception as e:
                        logger.warning(
                            "citation_verification_dispatch_failed",
                            matter_id=matter_id,
                            act_document_id=act_doc_id,
                            error=str(e),
                        )

            except Exception as e:
                logger.warning(
                    "sync_citation_statuses_matter_failed",
                    matter_id=matter_id,
                    error=str(e),
                )
                results["errors"].append({"matter_id": matter_id, "error": str(e)})

        logger.info(
            "sync_citation_statuses_with_resolutions_completed",
            matters_checked=results["matters_checked"],
            citations_updated=results["citations_updated"],
            act_unavailable_to_pending=results["act_unavailable_to_pending"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("sync_citation_statuses_with_resolutions_failed", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Hard Delete Expired Documents Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.hard_delete_expired_documents",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def hard_delete_expired_documents(self, retention_days: int = 30) -> dict:
    """Permanently delete documents that were soft-deleted more than retention_days ago.

    Documents are soft-deleted (deleted_at timestamp set) when users delete them
    from the UI. This task runs daily and permanently removes documents that have
    been in the trash for longer than the retention period.

    Also cleans up the associated storage files.

    Args:
        retention_days: Days to retain soft-deleted documents before permanent deletion.

    Returns:
        Dictionary with deletion results.
    """
    from datetime import UTC, datetime, timedelta

    from app.services.supabase.client import get_service_client

    logger.info("hard_delete_expired_documents_started", retention_days=retention_days)

    results = {
        "checked": 0,
        "deleted": 0,
        "storage_cleaned": 0,
        "errors": [],
    }

    try:
        client = get_service_client()
        if client is None:
            return {"error": "Database client not configured"}

        # Find documents where deleted_at is older than retention period
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)

        expired_docs = (
            client.table("documents")
            .select("id, matter_id, filename, storage_path, deleted_at")
            .not_.is_("deleted_at", "null")
            .lt("deleted_at", cutoff.isoformat())
            .execute()
        )

        if not expired_docs.data:
            logger.info("hard_delete_expired_documents_none_found")
            return results

        results["checked"] = len(expired_docs.data)

        for doc in expired_docs.data:
            doc_id = doc["id"]
            storage_path = doc.get("storage_path")

            try:
                # Delete storage file if path exists
                if storage_path:
                    try:
                        client.storage.from_("documents").remove([storage_path])
                        results["storage_cleaned"] += 1
                    except Exception as storage_err:
                        logger.warning(
                            "hard_delete_storage_cleanup_failed",
                            document_id=doc_id,
                            storage_path=storage_path,
                            error=str(storage_err),
                        )

                # Hard delete the document row (cascade cleanup already ran on soft-delete,
                # but delete any stragglers that may have been created after soft-delete)
                client.table("chunks").delete().eq("document_id", doc_id).execute()
                client.table("citations").delete().eq("source_document_id", doc_id).execute()
                client.table("entity_mentions").delete().eq("document_id", doc_id).execute()
                client.table("processing_jobs").delete().eq("document_id", doc_id).execute()
                client.table("events").update({"document_id": None}).eq("document_id", doc_id).execute()
                client.table("bounding_boxes").delete().eq("document_id", doc_id).execute()

                # Finally delete the document itself
                client.table("documents").delete().eq("id", doc_id).execute()

                results["deleted"] += 1
                logger.info(
                    "document_hard_deleted",
                    document_id=doc_id,
                    filename=doc.get("filename"),
                    deleted_at=doc.get("deleted_at"),
                )

            except Exception as e:
                logger.error(
                    "hard_delete_document_failed",
                    document_id=doc_id,
                    error=str(e),
                )
                results["errors"].append({"document_id": doc_id, "error": str(e)})

        logger.info(
            "hard_delete_expired_documents_completed",
            checked=results["checked"],
            deleted=results["deleted"],
            storage_cleaned=results["storage_cleaned"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("hard_delete_expired_documents_failed", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Hard Delete Expired Matters Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.hard_delete_expired_matters",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def hard_delete_expired_matters(self, retention_days: int = 30) -> dict:
    """Permanently delete matters that were soft-deleted more than retention_days ago.

    Matters are soft-deleted (deleted_at timestamp set) when users delete them
    from the UI. This task runs daily and permanently removes matters that have
    been in the trash for longer than the retention period.

    When a matter is deleted, PostgreSQL CASCADE deletes all related records:
    - documents, chunks, bounding_boxes, entities, citations, events, etc.

    This task also cleans up storage files before deleting the matter.

    Args:
        retention_days: Days to keep soft-deleted matters before permanent deletion.

    Returns:
        Dictionary with deletion results.
    """
    from datetime import UTC, datetime, timedelta

    from app.services.supabase.client import get_service_client

    logger.info("hard_delete_expired_matters_started", retention_days=retention_days)

    results = {
        "checked": 0,
        "deleted": 0,
        "storage_cleaned": 0,
        "errors": [],
    }

    try:
        client = get_service_client()
        if not client:
            logger.error("hard_delete_expired_matters_no_client")
            return {"error": "Database client not configured"}

        # Find matters where deleted_at is older than retention period
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)

        expired_matters = (
            client.table("matters")
            .select("id, title, deleted_at")
            .not_.is_("deleted_at", "null")
            .lt("deleted_at", cutoff.isoformat())
            .execute()
        )

        if not expired_matters.data:
            logger.info("hard_delete_expired_matters_none_found")
            return results

        results["checked"] = len(expired_matters.data)

        for matter in expired_matters.data:
            matter_id = matter["id"]
            matter_name = matter.get("title", "unknown")

            try:
                # Get all documents in this matter to clean up storage
                docs_response = (
                    client.table("documents")
                    .select("id, storage_path")
                    .eq("matter_id", matter_id)
                    .execute()
                )

                documents = docs_response.data or []

                # Clean up storage files for all documents
                for doc in documents:
                    storage_path = doc.get("storage_path")
                    if storage_path:
                        try:
                            client.storage.from_("documents").remove([storage_path])
                            results["storage_cleaned"] += 1
                        except Exception as storage_err:
                            logger.warning(
                                "hard_delete_matter_storage_cleanup_failed",
                                matter_id=matter_id,
                                document_id=doc["id"],
                                storage_path=storage_path,
                                error=str(storage_err),
                            )

                # Delete the matter row - CASCADE will handle all related records
                client.table("matters").delete().eq("id", matter_id).execute()

                results["deleted"] += 1
                logger.info(
                    "matter_hard_deleted",
                    matter_id=matter_id,
                    matter_name=matter_name,
                    documents_cleaned=len(documents),
                    deleted_at=matter.get("deleted_at"),
                )

            except Exception as e:
                logger.error(
                    "hard_delete_matter_failed",
                    matter_id=matter_id,
                    error=str(e),
                )
                results["errors"].append({"matter_id": matter_id, "error": str(e)})

        logger.info(
            "hard_delete_expired_matters_completed",
            checked=results["checked"],
            deleted=results["deleted"],
            storage_cleaned=results["storage_cleaned"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("hard_delete_expired_matters_failed", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Stuck Document Recovery Task (Auto-fix OCR_COMPLETE with 0 chunks)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.recover_stuck_documents",
    bind=True,
    max_retries=1,
)
def recover_stuck_documents(self) -> dict:
    """Periodic task to recover documents stuck at OCR_COMPLETE with 0 chunks.

    Finds documents where:
    - status = 'ocr_complete' or 'completed'
    - chunk count = 0 (in chunks table)

    These documents got stuck due to the finalize_chunked_document race condition
    where OCR_COMPLETE was set but downstream processing never triggered.

    Triggers downstream processing chain to create chunks and complete pipeline.

    Returns:
        Dictionary with recovery results.
    """
    from app.services.supabase.client import get_service_client

    logger.info("recover_stuck_documents_started")

    results = {
        "checked": 0,
        "recovered": 0,
        "skipped": 0,
        "errors": [],
    }

    try:
        client = get_service_client()

        # Find documents with OCR_COMPLETE status but 0 chunks
        # Try RPC first, fall back to manual query if function doesn't exist
        stuck_docs = None
        try:
            stuck_docs_response = client.rpc(
                "find_stuck_documents",
                {}
            ).execute()
            if stuck_docs_response.data:
                stuck_docs = stuck_docs_response.data
        except Exception as rpc_error:
            # RPC function doesn't exist - use manual fallback
            logger.debug(
                "find_stuck_documents_rpc_unavailable",
                error=str(rpc_error)[:100],
            )

        # If RPC failed or returned no data, fall back to manual query
        if stuck_docs is None:
            # Manual approach: get all OCR_COMPLETE/COMPLETED documents (exclude soft-deleted)
            docs_response = (
                client.table("documents")
                .select("id, matter_id, filename, status, extracted_text, page_count, document_type")
                .in_("status", ["ocr_complete", "completed"])
                .is_("deleted_at", "null")
                .execute()
            )

            if not docs_response.data:
                logger.info("recover_stuck_documents_no_documents_found")
                return results

            stuck_docs = []
            for doc in docs_response.data:
                doc_type = doc.get("document_type", "case_file")

                # Use the single source of truth for completeness check.
                # If all expected pipeline data exists for this document type,
                # it's not stuck — skip it. This prevents infinite re-dispatch
                # of e.g. act documents that legitimately have 0 chunks.
                if _is_pipeline_data_complete(client, doc["id"], document_type=doc_type):
                    continue

                stuck_docs.append(doc)

        results["checked"] = len(stuck_docs)

        if not stuck_docs:
            logger.info("recover_stuck_documents_none_stuck")
            return results

        logger.info(
            "recover_stuck_documents_found",
            stuck_count=len(stuck_docs),
        )

        # Trigger recovery for each stuck document
        from app.workers.tasks.chunked_document_tasks import finalize_chunked_document

        for doc in stuck_docs:
            document_id = doc["id"]
            matter_id = doc.get("matter_id")

            if not matter_id:
                logger.warning(
                    "recover_stuck_document_no_matter_id",
                    document_id=document_id,
                )
                results["skipped"] += 1
                continue

            try:
                # Get job_id if available
                job_response = (
                    client.table("processing_jobs")
                    .select("id")
                    .eq("document_id", document_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                job_id = job_response.data[0]["id"] if job_response.data else None

                # Trigger finalize_chunked_document which has recovery logic built-in
                # It will detect 0 chunks and trigger downstream processing
                finalize_chunked_document.apply_async(
                    kwargs={
                        "document_id": document_id,
                        "matter_id": matter_id,
                        "job_id": job_id,
                    },
                    queue="default",
                    countdown=2,  # Small delay to avoid overwhelming
                )

                results["recovered"] += 1
                logger.info(
                    "recover_stuck_document_triggered",
                    document_id=document_id,
                    matter_id=matter_id,
                    filename=doc.get("filename"),
                )

            except Exception as e:
                logger.error(
                    "recover_stuck_document_failed",
                    document_id=document_id,
                    error=str(e),
                )
                results["errors"].append({
                    "document_id": document_id,
                    "error": str(e),
                })

        logger.info(
            "recover_stuck_documents_completed",
            checked=results["checked"],
            recovered=results["recovered"],
            skipped=results["skipped"],
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("recover_stuck_documents_failed", error=str(e))
        return {"error": str(e)}


# =============================================================================
# Worker Heartbeat (INF-005)
# =============================================================================

@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.write_worker_heartbeat",
)
def write_worker_heartbeat() -> dict:
    """Write a Redis TTL key to prove the worker is alive.

    The health endpoint reads this key instead of using inspect.ping(),
    which doesn't work when broker_heartbeat=0 (disabled for Upstash Redis).
    Runs every 60s via beat; key has 180s TTL (3x interval as safety margin).
    """
    from app.services.distributed_lock import get_sync_redis_client

    r = get_sync_redis_client()
    r.setex("celery:worker:alive", 180, "1")
    return {"status": "heartbeat_written"}