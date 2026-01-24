"""Celery tasks related to engine execution.

Implements background tasks for:
- Timeline Engine: Date extraction from documents (Story 4-1)
- Timeline Engine: Event classification (Story 4-2)
- Timeline Engine: Entity linking (Story 4-3)
- Timeline Engine: Anomaly detection (Story 4-4)
- Citation Engine: (Future)
- Contradiction Engine: (Future)

Job Tracking Integration:
- Creates processing jobs when engine tasks start
- Updates job status and progress as processing continues
- Records completion and failure states
"""

import asyncio

import structlog

from app.engines.timeline import (
    get_anomaly_detector,
    get_date_extractor,
    get_event_classifier,
    get_event_entity_linker,
    get_timeline_builder,
)
from app.models.job import JobStatus, JobType
from app.services.anomaly_service import get_anomaly_service
from app.services.chunk_service import get_chunk_service
from app.services.document_service import get_document_service
from app.services.job_tracking import get_job_tracking_service
from app.services.mig.graph import get_mig_graph_service
from app.services.pubsub_service import (
    FeatureType,
    broadcast_feature_ready,
    broadcast_timeline_discovery,
)
from app.services.timeline_cache import get_timeline_cache_service
from app.services.timeline_service import get_timeline_service
from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)


# Thread-local storage for reusing event loops within a task
import threading

_task_loop_storage = threading.local()


def _get_task_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create an event loop for the current Celery task.

    Reuses event loop within a single task to avoid overhead of
    creating/destroying loops for each async call.

    Returns:
        Event loop for the current task.
    """
    loop = getattr(_task_loop_storage, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _task_loop_storage.loop = loop
    return loop


def _run_async(coro):
    """Run async coroutine in sync context for Celery tasks.

    Uses a per-task event loop to reduce overhead from repeated async calls.
    """
    loop = _get_task_event_loop()
    return loop.run_until_complete(coro)


def _cleanup_task_loop():
    """Clean up event loop at end of task execution."""
    loop = getattr(_task_loop_storage, "loop", None)
    if loop is not None and not loop.is_closed():
        loop.close()
        _task_loop_storage.loop = None


@celery_app.task(name="app.workers.tasks.engine_tasks.run_engine")  # type: ignore[untyped-decorator]
def run_engine(matter_id: str, engine: str) -> dict[str, str]:
    """Placeholder task for running a specific engine against a matter.

    Args:
        matter_id: Matter identifier.
        engine: Engine name (e.g., "citation", "timeline", "contradiction").

    Returns:
        Task result payload.
    """
    logger.info("engine_task_placeholder", task="run_engine", matter_id=matter_id, engine=engine)
    return {"status": "not_implemented", "matter_id": matter_id, "engine": engine}


# =============================================================================
# Timeline Engine Tasks (Story 4-1)
# =============================================================================


def _deduplicate_extracted_dates(dates: list) -> list:
    """Deduplicate dates extracted from multiple chunks.

    Dates are considered duplicates if they have the same extracted_date
    and similar context. Keeps the date with higher confidence or more
    complete metadata (page_number, bbox_ids).

    Args:
        dates: List of ExtractedDate objects from multiple chunks.

    Returns:
        Deduplicated list of ExtractedDate objects.
    """
    if not dates:
        return []

    # Group by extracted_date
    date_groups: dict[str, list] = {}
    for d in dates:
        key = d.extracted_date.isoformat() if d.extracted_date else "unknown"
        if key not in date_groups:
            date_groups[key] = []
        date_groups[key].append(d)

    # For each group, pick the best one (highest confidence, has page/bbox)
    unique_dates = []
    for date_key, group in date_groups.items():
        if len(group) == 1:
            unique_dates.append(group[0])
        else:
            # Sort by: has page_number, has bbox_ids, confidence
            def score(d):
                return (
                    1 if d.page_number is not None else 0,
                    len(d.bbox_ids) if d.bbox_ids else 0,
                    d.confidence or 0,
                )
            group.sort(key=score, reverse=True)
            unique_dates.append(group[0])

    return unique_dates


@celery_app.task(
    name="app.workers.tasks.engine_tasks.extract_dates_from_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)  # type: ignore[untyped-decorator]
def extract_dates_from_document(
    self,
    document_id: str,
    matter_id: str,
    job_id: str | None = None,
    force_reprocess: bool = False,
    auto_classify: bool = False,
) -> dict:
    """Extract dates from a document's text content.

    Loads document chunks, runs Gemini date extraction, and saves
    results to the events table as raw_date events.

    Args:
        document_id: Document UUID to process.
        matter_id: Matter UUID for isolation.
        job_id: Optional job ID for progress tracking.
        force_reprocess: If True, deletes existing dates before extraction.
        auto_classify: If True, automatically classify events after extraction (Story 4-2).

    Returns:
        Dict with extraction results.
    """
    logger.info(
        "date_extraction_started",
        document_id=document_id,
        matter_id=matter_id,
        job_id=job_id,
    )

    job_tracker = get_job_tracking_service()
    timeline_service = get_timeline_service()
    chunk_service = get_chunk_service()
    date_extractor = get_date_extractor()

    try:
        # Update job status if job exists
        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PROCESSING,
                    stage="date_extraction",
                    progress_pct=10,
                    matter_id=matter_id,
                )
            )

        # Check if already processed (unless force)
        if not force_reprocess:
            has_dates = timeline_service.has_dates_for_document_sync(
                document_id=document_id,
                matter_id=matter_id,
            )
            if has_dates:
                logger.info(
                    "date_extraction_skipped",
                    document_id=document_id,
                    reason="already_processed",
                )
                if job_id:
                    _run_async(
                        job_tracker.update_job_status(
                            job_id=job_id,
                            status=JobStatus.COMPLETED,
                            stage="date_extraction",
                            progress_pct=100,
                            matter_id=matter_id,
                        )
                    )
                return {
                    "status": "skipped",
                    "document_id": document_id,
                    "reason": "already_processed",
                }

        # Delete existing dates if force reprocess
        if force_reprocess:
            _run_async(
                timeline_service.delete_raw_dates_for_document(
                    document_id=document_id,
                    matter_id=matter_id,
                )
            )

        # Load document chunks to get text
        # ChunkService.get_chunks_for_document is synchronous, returns (chunks, parent_count, child_count)
        chunks, _, _ = chunk_service.get_chunks_for_document(
            document_id=document_id,
        )

        if not chunks:
            logger.warning(
                "date_extraction_no_chunks",
                document_id=document_id,
            )
            if job_id:
                _run_async(
                    job_tracker.update_job_status(
                        job_id=job_id,
                        status=JobStatus.COMPLETED,
                        stage="date_extraction",
                        progress_pct=100,
                        matter_id=matter_id,
                    )
                )
            return {
                "status": "completed",
                "document_id": document_id,
                "dates_found": 0,
                "reason": "no_chunks",
            }

        # Process per-chunk to preserve page_number and bbox_ids
        # Using parent chunks if available (they have better context), otherwise child chunks
        # ChunkWithContent is a Pydantic model, access attributes directly
        parent_chunks = [c for c in chunks if c.parent_chunk_id is None]
        chunks_to_process = parent_chunks if parent_chunks else chunks

        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PROCESSING,
                    stage="date_extraction",
                    progress_pct=30,
                    matter_id=matter_id,
                )
            )

        # Extract dates from each chunk individually to preserve page/bbox info
        from app.models.timeline import ExtractedDate
        all_dates: list[ExtractedDate] = []
        total_chunks = len(chunks_to_process)

        for idx, chunk in enumerate(chunks_to_process):
            # Run date extraction via Gemini for this chunk
            chunk_result = date_extractor.extract_dates_sync(
                text=chunk.content,
                document_id=document_id,
                matter_id=matter_id,
                page_number=chunk.page_number,  # Pass chunk's page number
                bbox_ids=chunk.bbox_ids or [],  # Pass chunk's bbox_ids
            )
            all_dates.extend(chunk_result.dates)

            # Update progress proportionally
            if job_id and total_chunks > 1:
                progress = 30 + int((idx + 1) / total_chunks * 40)  # 30-70%
                _run_async(
                    job_tracker.update_job_status(
                        job_id=job_id,
                        status=JobStatus.PROCESSING,
                        stage="date_extraction",
                        progress_pct=progress,
                        matter_id=matter_id,
                    )
                )

        # Deduplicate dates that appear in multiple chunks (same date + similar context)
        unique_dates = _deduplicate_extracted_dates(all_dates)

        logger.info(
            "date_extraction_chunks_processed",
            document_id=document_id,
            total_chunks=total_chunks,
            raw_dates=len(all_dates),
            unique_dates=len(unique_dates),
        )

        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PROCESSING,
                    stage="date_extraction",
                    progress_pct=70,
                    matter_id=matter_id,
                )
            )

        # Save extracted dates to events table
        event_ids = timeline_service.save_extracted_dates_sync(
            matter_id=matter_id,
            document_id=document_id,
            dates=unique_dates,
        )

        # Mark job complete
        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    stage="date_extraction",
                    progress_pct=100,
                    matter_id=matter_id,
                )
            )

        logger.info(
            "date_extraction_complete",
            document_id=document_id,
            matter_id=matter_id,
            dates_found=len(unique_dates),
            events_created=len(event_ids),
        )

        # Broadcast progressive timeline discovery for real-time UI updates
        if len(unique_dates) > 0:
            # Calculate date range
            date_range_start = None
            date_range_end = None
            sorted_dates = sorted(
                [d.extracted_date for d in unique_dates if d.extracted_date],
            )
            if sorted_dates:
                date_range_start = sorted_dates[0]
                date_range_end = sorted_dates[-1]

            broadcast_timeline_discovery(
                matter_id=matter_id,
                total_events=len(event_ids),
                date_range_start=date_range_start,
                date_range_end=date_range_end,
            )

        # Story 7.1: Broadcast timeline feature availability
        broadcast_feature_ready(
            matter_id=matter_id,
            document_id=document_id,
            feature=FeatureType.TIMELINE,
            metadata={
                "dates_found": len(unique_dates),
                "events_created": len(event_ids),
            },
        )

        result = {
            "status": "completed",
            "document_id": document_id,
            "matter_id": matter_id,
            "dates_found": len(unique_dates),
            "events_created": len(event_ids),
            "event_ids": event_ids,
        }

        # Auto-classify events if requested (Story 4-2)
        if auto_classify and event_ids:
            logger.info(
                "auto_classification_triggered",
                document_id=document_id,
                events_to_classify=len(event_ids),
            )
            classify_events_for_document.delay(
                document_id=document_id,
                matter_id=matter_id,
                job_id=None,
            )
            result["classification_queued"] = True

        return result

    except Exception as e:
        logger.error(
            "date_extraction_failed",
            document_id=document_id,
            matter_id=matter_id,
            error=str(e),
        )

        # Update job to failed
        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    stage="date_extraction",
                    error_message=str(e),
                    error_code="DATE_EXTRACTION_FAILED",
                    matter_id=matter_id,
                )
            )

        # Retry if possible
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "document_id": document_id,
                "error": str(e),
            }

        raise


@celery_app.task(
    name="app.workers.tasks.engine_tasks.extract_dates_from_matter",
    bind=True,
    max_retries=1,
)  # type: ignore[untyped-decorator]
def extract_dates_from_matter(
    self,
    matter_id: str,
    document_ids: list[str] | None = None,
    force_reprocess: bool = False,
    auto_classify: bool = False,
) -> dict:
    """Extract dates from all case file documents in a matter.

    Queues date extraction for each document. Can optionally specify
    which documents to process.

    Args:
        matter_id: Matter UUID.
        document_ids: Optional list of specific documents. If None, all case files.
        force_reprocess: If True, reprocess already processed documents.
        auto_classify: If True, automatically classify events after extraction (Story 4-2).

    Returns:
        Dict with job information.
    """
    logger.info(
        "matter_date_extraction_started",
        matter_id=matter_id,
        document_count=len(document_ids) if document_ids else "all",
        force_reprocess=force_reprocess,
    )

    job_tracker = get_job_tracking_service()
    document_service = get_document_service()
    timeline_service = get_timeline_service()

    try:
        # Create master job for tracking
        master_job = _run_async(
            job_tracker.create_job(
                matter_id=matter_id,
                job_type=JobType.DATE_EXTRACTION,
                celery_task_id=self.request.id,
                metadata={"scope": "matter", "force_reprocess": force_reprocess},
            )
        )

        # Get documents to process
        if document_ids:
            # Use provided document IDs
            docs_to_process = document_ids
        else:
            # Get all case_file documents for the matter
            documents = _run_async(
                document_service.get_documents_by_matter(
                    matter_id=matter_id,
                    page=1,
                    per_page=1000,  # Get all documents
                )
            )

            # Filter to case files only (not Acts)
            docs_to_process = [
                doc.id for doc in documents[0]
                if doc.document_type == "case_file" and doc.status == "completed"
            ]

        # Skip already processed unless force
        if not force_reprocess:
            filtered_docs = []
            for doc_id in docs_to_process:
                has_dates = timeline_service.has_dates_for_document_sync(
                    document_id=doc_id,
                    matter_id=matter_id,
                )
                if not has_dates:
                    filtered_docs.append(doc_id)
            docs_to_process = filtered_docs

        if not docs_to_process:
            logger.info(
                "matter_date_extraction_no_documents",
                matter_id=matter_id,
                reason="all_processed",
            )
            _run_async(
                job_tracker.update_job_status(
                    job_id=master_job.id,
                    status=JobStatus.COMPLETED,
                    progress_pct=100,
                    matter_id=matter_id,
                )
            )
            return {
                "status": "completed",
                "matter_id": matter_id,
                "job_id": master_job.id,
                "documents_queued": 0,
                "reason": "all_documents_already_processed",
            }

        # Queue extraction for each document
        queued_tasks = []
        for i, doc_id in enumerate(docs_to_process):
            task = extract_dates_from_document.delay(
                document_id=doc_id,
                matter_id=matter_id,
                job_id=None,  # Individual jobs not tracked separately
                force_reprocess=force_reprocess,
                auto_classify=auto_classify,  # Pass through to document task
            )
            queued_tasks.append({"document_id": doc_id, "task_id": task.id})

            # Update progress
            progress = int((i + 1) / len(docs_to_process) * 100)
            _run_async(
                job_tracker.update_job_status(
                    job_id=master_job.id,
                    status=JobStatus.PROCESSING,
                    progress_pct=progress,
                    matter_id=matter_id,
                )
            )

        logger.info(
            "matter_date_extraction_queued",
            matter_id=matter_id,
            documents_queued=len(queued_tasks),
            job_id=master_job.id,
        )

        return {
            "status": "queued",
            "matter_id": matter_id,
            "job_id": master_job.id,
            "documents_to_process": len(docs_to_process),
            "tasks": queued_tasks,
        }

    except Exception as e:
        logger.error(
            "matter_date_extraction_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise


# =============================================================================
# Event Classification Tasks (Story 4-2)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.engine_tasks.classify_events_for_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)  # type: ignore[untyped-decorator]
def classify_events_for_document(
    self,
    document_id: str,
    matter_id: str,
    job_id: str | None = None,
) -> dict:
    """Classify raw_date events for a specific document.

    Loads raw_date events from the document, runs Gemini classification,
    and updates events with classified types.

    Args:
        document_id: Document UUID whose events to classify.
        matter_id: Matter UUID for isolation.
        job_id: Optional job ID for progress tracking.

    Returns:
        Dict with classification results.
    """
    logger.info(
        "event_classification_doc_started",
        document_id=document_id,
        matter_id=matter_id,
        job_id=job_id,
    )

    job_tracker = get_job_tracking_service()
    timeline_service = get_timeline_service()
    event_classifier = get_event_classifier()

    try:
        # Update job status if job exists
        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PROCESSING,
                    stage="event_classification",
                    progress_pct=10,
                    matter_id=matter_id,
                )
            )

        # Get raw_date events for this document (Issue #3 fix - filter at DB level)
        doc_events = timeline_service.get_events_for_classification_sync(
            matter_id=matter_id,
            document_id=document_id,  # Filter at database level
            limit=1000,
        )

        if not doc_events:
            logger.info(
                "event_classification_doc_no_events",
                document_id=document_id,
                reason="no_raw_date_events",
            )
            if job_id:
                _run_async(
                    job_tracker.update_job_status(
                        job_id=job_id,
                        status=JobStatus.COMPLETED,
                        stage="event_classification",
                        progress_pct=100,
                        matter_id=matter_id,
                    )
                )
            return {
                "status": "completed",
                "document_id": document_id,
                "events_classified": 0,
                "reason": "no_raw_date_events",
            }

        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PROCESSING,
                    stage="event_classification",
                    progress_pct=30,
                    matter_id=matter_id,
                )
            )

        # Prepare events for batch classification
        events_for_classification = [
            {
                "event_id": e.id,
                "date_text": e.event_date_text or str(e.event_date),
                "context": e.description,
            }
            for e in doc_events
        ]

        # Run batch classification
        classification_results = event_classifier.classify_events_batch_sync(
            events=events_for_classification
        )

        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PROCESSING,
                    stage="event_classification",
                    progress_pct=70,
                    matter_id=matter_id,
                )
            )

        # Update events with classification results
        updated_count = timeline_service.bulk_update_classifications_sync(
            classifications=classification_results,
            matter_id=matter_id,
        )

        # Mark job complete
        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    stage="event_classification",
                    progress_pct=100,
                    matter_id=matter_id,
                )
            )

        logger.info(
            "event_classification_doc_complete",
            document_id=document_id,
            matter_id=matter_id,
            events_processed=len(doc_events),
            events_updated=updated_count,
        )

        # Auto-trigger entity linking after classification
        if updated_count > 0:
            logger.info(
                "entity_linking_auto_triggered",
                document_id=document_id,
                matter_id=matter_id,
            )
            link_entities_after_extraction.delay(
                document_id=document_id,
                matter_id=matter_id,
            )

        return {
            "status": "completed",
            "document_id": document_id,
            "matter_id": matter_id,
            "events_processed": len(doc_events),
            "events_updated": updated_count,
            "entity_linking_queued": updated_count > 0,
        }

    except Exception as e:
        logger.error(
            "event_classification_doc_failed",
            document_id=document_id,
            matter_id=matter_id,
            error=str(e),
        )

        if job_id:
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    stage="event_classification",
                    error_message=str(e),
                    error_code="EVENT_CLASSIFICATION_FAILED",
                    matter_id=matter_id,
                )
            )

        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "document_id": document_id,
                "error": str(e),
            }

        raise


@celery_app.task(
    name="app.workers.tasks.engine_tasks.classify_events_for_matter",
    bind=True,
    max_retries=1,
)  # type: ignore[untyped-decorator]
def classify_events_for_matter(
    self,
    matter_id: str,
    document_ids: list[str] | None = None,
    force_reclassify: bool = False,
) -> dict:
    """Classify raw_date events for all documents in a matter.

    Processes all raw_date events in batches using Gemini classification.

    Args:
        matter_id: Matter UUID.
        document_ids: Optional list of specific documents. If None, all with raw_date events.
        force_reclassify: If True, reclassify already classified events (re-processes
            all events including those already classified, not just raw_date).

    Returns:
        Dict with job information.
    """
    logger.info(
        "event_classification_matter_started",
        matter_id=matter_id,
        document_ids=document_ids,
        force_reclassify=force_reclassify,
    )

    job_tracker = get_job_tracking_service()
    timeline_service = get_timeline_service()
    event_classifier = get_event_classifier()

    try:
        # Create master job for tracking
        master_job = _run_async(
            job_tracker.create_job(
                matter_id=matter_id,
                job_type=JobType.EVENT_CLASSIFICATION,
                celery_task_id=self.request.id,
                metadata={
                    "scope": "matter",
                    "document_ids": document_ids,
                    "force_reclassify": force_reclassify,
                },
            )
        )

        # Get events for classification
        # If force_reclassify, get ALL events (not just raw_date)
        # Otherwise, only get raw_date events
        if force_reclassify:
            raw_events = timeline_service.get_all_events_for_reclassification_sync(
                matter_id=matter_id,
                limit=10000,
            )
        else:
            raw_events = timeline_service.get_events_for_classification_sync(
                matter_id=matter_id,
                limit=10000,  # Process up to 10k events
            )

        # Filter by document_ids if specified
        if document_ids:
            raw_events = [e for e in raw_events if e.document_id in document_ids]

        if not raw_events:
            logger.info(
                "event_classification_matter_no_events",
                matter_id=matter_id,
                reason="no_raw_date_events",
            )
            _run_async(
                job_tracker.update_job_status(
                    job_id=master_job.id,
                    status=JobStatus.COMPLETED,
                    progress_pct=100,
                    matter_id=matter_id,
                )
            )
            return {
                "status": "completed",
                "matter_id": matter_id,
                "job_id": master_job.id,
                "events_classified": 0,
                "reason": "no_raw_date_events",
            }

        _run_async(
            job_tracker.update_job_status(
                job_id=master_job.id,
                status=JobStatus.PROCESSING,
                stage="event_classification",
                progress_pct=10,
                matter_id=matter_id,
            )
        )

        # Prepare events for batch classification
        events_for_classification = [
            {
                "event_id": e.id,
                "date_text": e.event_date_text or str(e.event_date),
                "context": e.description,
            }
            for e in raw_events
        ]

        # Process in batches of 20 (handled by classifier)
        total_events = len(events_for_classification)
        batch_size = 20
        total_updated = 0

        for i in range(0, total_events, batch_size):
            batch = events_for_classification[i : i + batch_size]

            # Classify batch
            classification_results = event_classifier.classify_events_batch_sync(
                events=batch
            )

            # Update events
            updated = timeline_service.bulk_update_classifications_sync(
                classifications=classification_results,
                matter_id=matter_id,
            )
            total_updated += updated

            # Update progress
            progress = min(10 + int((i + batch_size) / total_events * 85), 95)
            _run_async(
                job_tracker.update_job_status(
                    job_id=master_job.id,
                    status=JobStatus.PROCESSING,
                    stage="event_classification",
                    progress_pct=progress,
                    matter_id=matter_id,
                )
            )

        # Mark complete
        _run_async(
            job_tracker.update_job_status(
                job_id=master_job.id,
                status=JobStatus.COMPLETED,
                stage="event_classification",
                progress_pct=100,
                matter_id=matter_id,
            )
        )

        logger.info(
            "event_classification_matter_complete",
            matter_id=matter_id,
            job_id=master_job.id,
            events_processed=total_events,
            events_updated=total_updated,
        )

        return {
            "status": "completed",
            "matter_id": matter_id,
            "job_id": master_job.id,
            "events_processed": total_events,
            "events_updated": total_updated,
        }

    except Exception as e:
        logger.error(
            "event_classification_matter_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise


# =============================================================================
# Entity Linking Tasks (Story 4-3)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.engine_tasks.link_entities_for_matter",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)  # type: ignore[untyped-decorator]
def link_entities_for_matter(
    self,
    matter_id: str,
    force_relink: bool = False,
) -> dict:
    """Link entities to timeline events for a matter.

    Processes events without entity links, extracting entity mentions
    from descriptions and matching them to MIG entities.

    Args:
        matter_id: Matter UUID.
        force_relink: If True, reprocess all events (not just unlinked).

    Returns:
        Dict with linking results.
    """
    logger.info(
        "entity_linking_matter_started",
        matter_id=matter_id,
        force_relink=force_relink,
    )

    job_tracker = get_job_tracking_service()
    timeline_service = get_timeline_service()
    mig_service = get_mig_graph_service()
    entity_linker = get_event_entity_linker()
    cache_service = get_timeline_cache_service()

    try:
        # Create job for tracking
        master_job = _run_async(
            job_tracker.create_job(
                matter_id=matter_id,
                job_type=JobType.ENTITY_LINKING,
                celery_task_id=self.request.id,
                metadata={
                    "scope": "matter",
                    "force_relink": force_relink,
                },
            )
        )

        # Get events to process
        if force_relink:
            # Get all events
            events = timeline_service.get_all_events_for_reclassification_sync(
                matter_id=matter_id,
                limit=10000,
            )
        else:
            # Get only unlinked events
            events = timeline_service.get_events_for_entity_linking_sync(
                matter_id=matter_id,
                limit=10000,
            )

        if not events:
            logger.info(
                "entity_linking_matter_no_events",
                matter_id=matter_id,
                reason="no_unlinked_events" if not force_relink else "no_events",
            )
            _run_async(
                job_tracker.update_job_status(
                    job_id=master_job.id,
                    status=JobStatus.COMPLETED,
                    progress_pct=100,
                    matter_id=matter_id,
                )
            )
            return {
                "status": "completed",
                "matter_id": matter_id,
                "job_id": master_job.id,
                "events_processed": 0,
                "events_linked": 0,
                "reason": "no_events_to_process",
            }

        _run_async(
            job_tracker.update_job_status(
                job_id=master_job.id,
                status=JobStatus.PROCESSING,
                stage="entity_linking",
                progress_pct=10,
                matter_id=matter_id,
            )
        )

        # Load all entities for the matter using pagination (Issue #2 fix)
        # Fetch in pages to avoid memory issues for large matters
        entities = []
        page = 1
        per_page = 500  # Reasonable page size
        while True:
            page_entities, total = _run_async(
                mig_service.get_entities_by_matter(
                    matter_id=matter_id,
                    page=page,
                    per_page=per_page,
                )
            )
            if not page_entities:
                break
            entities.extend(page_entities)
            # Check if we've loaded all entities
            if len(entities) >= total:
                break
            page += 1
            # Safety limit to prevent infinite loops
            if page > 100:
                logger.warning(
                    "entity_loading_page_limit_reached",
                    matter_id=matter_id,
                    entities_loaded=len(entities),
                )
                break

        if not entities:
            logger.info(
                "entity_linking_matter_no_mig_entities",
                matter_id=matter_id,
            )
            _run_async(
                job_tracker.update_job_status(
                    job_id=master_job.id,
                    status=JobStatus.COMPLETED,
                    progress_pct=100,
                    matter_id=matter_id,
                )
            )
            return {
                "status": "completed",
                "matter_id": matter_id,
                "job_id": master_job.id,
                "events_processed": len(events),
                "events_linked": 0,
                "reason": "no_mig_entities",
            }

        # Process events in batches with parallel processing
        batch_size = 50
        total_events = len(events)
        events_with_links = 0
        total_entity_links = 0

        for i in range(0, total_events, batch_size):
            batch = events[i : i + batch_size]

            # Link entities for batch using parallel processing (ThreadPoolExecutor)
            # This is significantly faster than sequential processing for large batches
            event_entities = entity_linker.link_entities_batch_parallel(
                events=batch,
                matter_id=matter_id,
                entities=entities,
                max_workers=10,  # Parallel threads for CPU-bound entity matching
            )

            # Count results
            for entity_ids in event_entities.values():
                if entity_ids:
                    events_with_links += 1
                    total_entity_links += len(entity_ids)

            # Bulk update events with entity links
            if event_entities:
                # Filter to only events that have links
                links_to_update = {k: v for k, v in event_entities.items() if v}
                if links_to_update:
                    timeline_service.bulk_update_event_entities_sync(
                        event_entities=links_to_update,
                        matter_id=matter_id,
                    )

            # Update progress
            progress = min(10 + int((i + batch_size) / total_events * 85), 95)
            _run_async(
                job_tracker.update_job_status(
                    job_id=master_job.id,
                    status=JobStatus.PROCESSING,
                    stage="entity_linking",
                    progress_pct=progress,
                    matter_id=matter_id,
                )
            )

        # Invalidate timeline cache since entity links changed
        _run_async(cache_service.invalidate_timeline(matter_id))

        # Mark complete
        _run_async(
            job_tracker.update_job_status(
                job_id=master_job.id,
                status=JobStatus.COMPLETED,
                stage="entity_linking",
                progress_pct=100,
                matter_id=matter_id,
            )
        )

        logger.info(
            "entity_linking_matter_complete",
            matter_id=matter_id,
            job_id=master_job.id,
            events_processed=total_events,
            events_with_links=events_with_links,
            total_entity_links=total_entity_links,
        )

        result = {
            "status": "completed",
            "matter_id": matter_id,
            "job_id": master_job.id,
            "events_processed": total_events,
            "events_with_links": events_with_links,
            "total_entity_links": total_entity_links,
        }

        # Auto-trigger anomaly detection (Story 14-7)
        # Only trigger if there are events that could have anomalies
        if events_with_links > 0 or total_events > 0:
            try:
                logger.info(
                    "auto_triggering_anomaly_detection",
                    matter_id=matter_id,
                    events_processed=total_events,
                    events_linked=events_with_links,
                )
                detect_timeline_anomalies.delay(
                    matter_id=matter_id,
                    force_redetect=False,
                    job_id=None,  # Creates own job
                )
                result["anomaly_detection_queued"] = True
            except Exception as e:
                logger.warning(
                    "anomaly_detection_trigger_failed",
                    matter_id=matter_id,
                    error=str(e),
                )
                result["anomaly_detection_queued"] = False
                # Don't re-raise - entity linking succeeded

        return result

    except Exception as e:
        logger.error(
            "entity_linking_matter_failed",
            matter_id=matter_id,
            error=str(e),
        )

        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "matter_id": matter_id,
                "error": str(e),
            }

        raise

    finally:
        # Clean up event loop at end of task (Issue #4/#8 fix)
        _cleanup_task_loop()


@celery_app.task(
    name="app.workers.tasks.engine_tasks.link_entities_after_extraction",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)  # type: ignore[untyped-decorator]
def link_entities_after_extraction(
    self,
    document_id: str,
    matter_id: str,
) -> dict:
    """Link entities to events immediately after date extraction.

    Called automatically after extract_dates_from_document when
    auto_link_entities=True.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID.

    Returns:
        Dict with linking results.
    """
    logger.info(
        "entity_linking_doc_started",
        document_id=document_id,
        matter_id=matter_id,
    )

    timeline_service = get_timeline_service()
    mig_service = get_mig_graph_service()
    entity_linker = get_event_entity_linker()
    cache_service = get_timeline_cache_service()

    try:
        # Get events for this document that don't have entity links
        all_events = timeline_service.get_events_for_entity_linking_sync(
            matter_id=matter_id,
            limit=10000,
        )

        # Filter to document
        events = [e for e in all_events if e.document_id == document_id]

        if not events:
            logger.debug(
                "entity_linking_doc_no_events",
                document_id=document_id,
                matter_id=matter_id,
            )
            return {
                "status": "completed",
                "document_id": document_id,
                "events_processed": 0,
                "events_linked": 0,
            }

        # Load entities using pagination to avoid OOM
        all_entities = []
        entity_page = 1
        batch_size = 500

        while True:
            entities_batch, total = _run_async(
                mig_service.get_entities_by_matter(
                    matter_id=matter_id,
                    page=entity_page,
                    per_page=batch_size,
                )
            )
            all_entities.extend(entities_batch)

            if len(all_entities) >= total or not entities_batch:
                break
            entity_page += 1

        entities = all_entities

        if not entities:
            # No MIG entities, but still trigger anomaly detection for timeline events
            # Events could have sequence/gap anomalies even without entity links
            result = {
                "status": "completed",
                "document_id": document_id,
                "events_processed": len(events),
                "events_linked": 0,
                "reason": "no_mig_entities",
            }
            # Trigger anomaly detection if there are events to analyze (Story 14-7)
            if len(events) > 0:
                try:
                    logger.info(
                        "auto_triggering_anomaly_detection",
                        document_id=document_id,
                        matter_id=matter_id,
                        events_processed=len(events),
                        events_linked=0,
                        reason="no_mig_entities_but_events_exist",
                    )
                    detect_timeline_anomalies.delay(
                        matter_id=matter_id,
                        force_redetect=False,
                        job_id=None,
                    )
                    result["anomaly_detection_queued"] = True
                except Exception as e:
                    logger.warning(
                        "anomaly_detection_trigger_failed",
                        document_id=document_id,
                        matter_id=matter_id,
                        error=str(e),
                    )
                    result["anomaly_detection_queued"] = False
            return result

        # Link entities using parallel batch processing
        event_entities = entity_linker.link_entities_batch_parallel(
            events=events,
            matter_id=matter_id,
            entities=entities,
            max_workers=10,  # Parallel threads for CPU-bound entity matching
        )

        # Count linked events
        events_linked = sum(1 for ids in event_entities.values() if ids)

        # Update events with links
        links_to_update = {k: v for k, v in event_entities.items() if v}
        if links_to_update:
            timeline_service.bulk_update_event_entities_sync(
                event_entities=links_to_update,
                matter_id=matter_id,
            )
            # Invalidate cache
            _run_async(cache_service.invalidate_timeline(matter_id))

        logger.info(
            "entity_linking_doc_complete",
            document_id=document_id,
            matter_id=matter_id,
            events_processed=len(events),
            events_linked=events_linked,
        )

        result = {
            "status": "completed",
            "document_id": document_id,
            "matter_id": matter_id,
            "events_processed": len(events),
            "events_linked": events_linked,
        }

        # Auto-trigger anomaly detection for incremental processing (Story 14-7)
        # Trigger when events exist (even without links) - consistent with link_entities_for_matter
        if events_linked > 0 or len(events) > 0:
            try:
                logger.info(
                    "auto_triggering_anomaly_detection",
                    document_id=document_id,
                    matter_id=matter_id,
                    events_processed=len(events),
                    events_linked=events_linked,
                )
                detect_timeline_anomalies.delay(
                    matter_id=matter_id,
                    force_redetect=False,  # Incremental - don't delete existing
                    job_id=None,
                )
                result["anomaly_detection_queued"] = True
            except Exception as e:
                logger.warning(
                    "anomaly_detection_trigger_failed",
                    document_id=document_id,
                    matter_id=matter_id,
                    error=str(e),
                )
                result["anomaly_detection_queued"] = False
                # Don't re-raise - entity linking succeeded

        return result

    except Exception as e:
        logger.error(
            "entity_linking_doc_failed",
            document_id=document_id,
            error=str(e),
        )

        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "document_id": document_id,
                "error": str(e),
            }

        raise

    finally:
        # Clean up event loop at end of task (consistency with link_entities_for_matter)
        _cleanup_task_loop()


# =============================================================================
# Anomaly Detection Tasks (Story 4-4)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.engine_tasks.detect_timeline_anomalies",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)  # type: ignore[untyped-decorator]
def detect_timeline_anomalies(
    self,
    matter_id: str,
    force_redetect: bool = False,
    job_id: str | None = None,
) -> dict:
    """Detect anomalies in a matter's timeline.

    Analyzes timeline events for sequence violations, unusual gaps,
    potential duplicates, and statistical outliers.

    Args:
        matter_id: Matter UUID.
        force_redetect: If True, delete existing anomalies before detection.
        job_id: Optional job ID for progress tracking.

    Returns:
        Dict with detection results.
    """
    logger.info(
        "anomaly_detection_started",
        matter_id=matter_id,
        force_redetect=force_redetect,
        job_id=job_id,
    )

    job_tracker = get_job_tracking_service()
    anomaly_service = get_anomaly_service()
    timeline_builder = get_timeline_builder()
    anomaly_detector = get_anomaly_detector()
    cache_service = get_timeline_cache_service()

    try:
        # Create job if not provided (auto-trigger case - Story 14-7)
        if not job_id:
            master_job = _run_async(
                job_tracker.create_job(
                    matter_id=matter_id,
                    job_type=JobType.ANOMALY_DETECTION,
                    celery_task_id=self.request.id,
                    metadata={"triggered_by": "pipeline", "force_redetect": force_redetect},
                )
            )
            job_id = master_job.id
            logger.info(
                "anomaly_detection_job_created",
                matter_id=matter_id,
                job_id=job_id,
                triggered_by="pipeline",
            )

        # Update job status
        _run_async(
            job_tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                stage="anomaly_detection",
                progress_pct=10,
                matter_id=matter_id,
            )
        )

        # Delete existing anomalies if force redetect
        if force_redetect:
            deleted = anomaly_service.delete_anomalies_for_matter_sync(matter_id)
            logger.info(
                "anomaly_detection_cleared_existing",
                matter_id=matter_id,
                deleted_count=deleted,
            )

        _run_async(
            job_tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                stage="anomaly_detection",
                progress_pct=20,
                matter_id=matter_id,
            )
        )

        # Build timeline to get all events using pagination to avoid OOM
        all_timeline_events = []
        timeline_page = 1
        batch_size = 500

        while True:
            timeline = _run_async(
                timeline_builder.build_timeline(
                    matter_id=matter_id,
                    include_entities=True,
                    include_raw_dates=False,  # Only classified events
                    page=timeline_page,
                    per_page=batch_size,
                )
            )
            all_timeline_events.extend(timeline.events)

            if timeline_page >= timeline.total_pages or not timeline.events:
                break
            timeline_page += 1

        events = all_timeline_events

        if not events:
            logger.info(
                "anomaly_detection_no_events",
                matter_id=matter_id,
            )
            _run_async(
                job_tracker.update_job_status(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    stage="anomaly_detection",
                    progress_pct=100,
                    matter_id=matter_id,
                )
            )
            return {
                "status": "completed",
                "matter_id": matter_id,
                "events_analyzed": 0,
                "anomalies_detected": 0,
                "reason": "no_events",
            }

        _run_async(
            job_tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                stage="anomaly_detection",
                progress_pct=40,
                matter_id=matter_id,
            )
        )

        # Run anomaly detection
        anomalies = _run_async(
            anomaly_detector.detect_anomalies(
                matter_id=matter_id,
                events=events,
            )
        )

        _run_async(
            job_tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                stage="anomaly_detection",
                progress_pct=70,
                matter_id=matter_id,
            )
        )

        # Save detected anomalies
        anomaly_ids = []
        if anomalies:
            anomaly_ids = anomaly_service.save_anomalies_sync(anomalies)

        _run_async(
            job_tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                stage="anomaly_detection",
                progress_pct=90,
                matter_id=matter_id,
            )
        )

        # Invalidate timeline cache since anomalies may affect display
        _run_async(cache_service.invalidate_timeline(matter_id))

        # Mark job complete
        _run_async(
            job_tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                stage="anomaly_detection",
                progress_pct=100,
                matter_id=matter_id,
            )
        )

        logger.info(
            "anomaly_detection_complete",
            matter_id=matter_id,
            events_analyzed=len(events),
            anomalies_detected=len(anomalies),
        )

        return {
            "status": "completed",
            "matter_id": matter_id,
            "events_analyzed": len(events),
            "anomalies_detected": len(anomalies),
            "anomaly_ids": anomaly_ids,
        }

    except Exception as e:
        logger.error(
            "anomaly_detection_failed",
            matter_id=matter_id,
            error=str(e),
        )

        # Update job status if job was created (job_id might be None if error occurred during job creation)
        if job_id:
            import contextlib

            with contextlib.suppress(Exception):
                _run_async(
                    job_tracker.update_job_status(
                        job_id=job_id,
                        status=JobStatus.FAILED,
                        stage="anomaly_detection",
                        error_message=str(e),
                        error_code="ANOMALY_DETECTION_FAILED",
                        matter_id=matter_id,
                    )
                )

        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "matter_id": matter_id,
                "error": str(e),
            }

        raise

    finally:
        _cleanup_task_loop()
