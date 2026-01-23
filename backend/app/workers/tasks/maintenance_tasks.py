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
            .select("id, document_id, current_stage, updated_at")
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
            embed_chunks,
            extract_entities,
            process_document,
        )

        dispatched = 0
        errors = []

        for job in stuck_jobs:
            job_id = job["id"]
            doc_id = job.get("document_id")
            stage = job.get("current_stage")

            if not doc_id:
                errors.append({"job_id": job_id, "error": "no document_id"})
                continue

            try:
                # Dispatch based on current stage
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
def resume_stuck_pipelines(self, stale_hours: int = 1) -> dict:
    """Resume document processing pipelines that got stuck at intermediate stages.

    Finds documents that are stuck at ocr_complete (or other intermediate states)
    for longer than stale_hours and re-triggers the remaining pipeline stages.

    This handles:
    - Documents where Celery task chain broke
    - Documents where worker crashed mid-pipeline
    - Documents uploaded before a bug fix

    Runs every 30 minutes to recover stuck documents.

    Args:
        stale_hours: Hours after which a document is considered stuck.

    Returns:
        Dictionary with recovery results.
    """
    from datetime import datetime, timedelta, timezone

    from app.services.supabase.client import get_service_client

    logger.info("resume_stuck_pipelines_started", stale_hours=stale_hours)

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

        # Find documents stuck at ocr_complete for more than stale_hours
        # These should have progressed to 'completed' but didn't
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=stale_hours)

        stuck_docs = (
            client.table("documents")
            .select("id, matter_id, filename, status, updated_at")
            .eq("status", "ocr_complete")
            .lt("updated_at", cutoff_time.isoformat())
            .execute()
        )

        if not stuck_docs.data:
            logger.info("resume_stuck_pipelines_none_found")
            return results

        results["checked"] = len(stuck_docs.data)

        for doc in stuck_docs.data:
            doc_id = doc["id"]
            matter_id = doc["matter_id"]
            filename = doc.get("filename", "unknown")

            try:
                # Check what stages are missing for this document
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
                        "resume_pipeline_from_chunking",
                        document_id=doc_id,
                        filename=filename,
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
    """Dispatch pipeline from chunking stage onwards."""
    from celery import chain

    from app.workers.tasks.document_tasks import (
        chunk_document,
        embed_chunks,
        extract_entities,
        resolve_aliases,
    )

    task_chain = chain(
        chunk_document.s({"document_id": document_id, "status": "ocr_complete"}),
        embed_chunks.s(),
        extract_entities.s(),
        resolve_aliases.s(),
    )
    task_chain.apply_async()


def _dispatch_from_embedding(document_id: str, matter_id: str) -> None:
    """Dispatch pipeline from embedding stage onwards."""
    from celery import chain

    from app.workers.tasks.document_tasks import (
        embed_chunks,
        extract_entities,
        resolve_aliases,
    )

    task_chain = chain(
        embed_chunks.s({"document_id": document_id, "status": "chunked"}),
        extract_entities.s(),
        resolve_aliases.s(),
    )
    task_chain.apply_async()


def _dispatch_from_entities(document_id: str, matter_id: str) -> None:
    """Dispatch pipeline from entity extraction stage onwards."""
    from celery import chain

    from app.workers.tasks.document_tasks import (
        extract_entities,
        resolve_aliases,
    )

    task_chain = chain(
        extract_entities.s({"document_id": document_id, "status": "embedded"}),
        resolve_aliases.s(),
    )
    task_chain.apply_async()


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
                # Get all act documents for this matter
                docs_response = (
                    client.table("documents")
                    .select("id, filename, act_name")
                    .eq("matter_id", matter_id)
                    .eq("document_type", "act")
                    .execute()
                )

                act_docs = docs_response.data or []

                # Build map of normalized act name -> document
                act_doc_map: dict[str, dict] = {}
                for doc in act_docs:
                    # Use act_name if available, otherwise extract from filename
                    act_name = doc.get("act_name") or doc.get("filename", "")
                    if act_name:
                        normalized = normalize_act_name(act_name)
                        act_doc_map[normalized] = doc

                # Get all resolutions for this matter
                resolutions_response = (
                    client.table("act_resolutions")
                    .select("id, act_name_normalized, resolution_status, act_document_id")
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
            errors=len(results["errors"]),
        )

        return results

    except Exception as e:
        logger.error("sync_act_resolutions_with_documents_failed", error=str(e))
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
        "errors": [],
    }

    try:
        client = get_service_client()
        if client is None:
            return {"error": "Database client not configured"}

        # Get all act_resolutions that have act_document_id (i.e., available)
        available_resolutions = (
            client.table("act_resolutions")
            .select("matter_id, act_name_normalized, act_document_id")
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
                # Build set of normalized names that have available Acts
                available_normalized_names = {
                    res["act_name_normalized"] for res in resolutions
                }

                # Get all citations for this matter with act_unavailable status
                # Handle pagination (Supabase returns max 1000 rows per request)
                citations_to_update = []
                offset = 0
                page_size = 1000

                while True:
                    citations_response = (
                        client.table("citations")
                        .select("id, act_name")
                        .eq("matter_id", matter_id)
                        .eq("verification_status", "act_unavailable")
                        .range(offset, offset + page_size - 1)
                        .execute()
                    )

                    citations = citations_response.data or []
                    if not citations:
                        break

                    # Find citations where Act is actually available
                    for citation in citations:
                        citation_normalized = normalize_act_name(citation.get("act_name", ""))
                        if citation_normalized in available_normalized_names:
                            citations_to_update.append(citation["id"])

                    # If we got fewer than page_size, we've reached the end
                    if len(citations) < page_size:
                        break
                    offset += page_size

                if not citations_to_update:
                    continue

                # Batch update citation statuses (max 100 per request to avoid JSON errors)
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