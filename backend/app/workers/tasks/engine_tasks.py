"""Celery tasks related to engine execution.

Implements background tasks for:
- Timeline Engine: Date extraction from documents (Story 4-1)
- Timeline Engine: Event classification (Story 4-2)
- Citation Engine: (Future)
- Contradiction Engine: (Future)

Job Tracking Integration:
- Creates processing jobs when engine tasks start
- Updates job status and progress as processing continues
- Records completion and failure states
"""

import asyncio

import structlog

from app.engines.timeline import DateExtractor, get_date_extractor, EventClassifier, get_event_classifier
from app.models.job import JobStatus, JobType
from app.services.chunk_service import get_chunk_service
from app.services.document_service import get_document_service
from app.services.job_tracking import get_job_tracking_service
from app.services.timeline_service import TimelineService, get_timeline_service
from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run async coroutine in sync context for Celery tasks.

    Creates a new event loop to run async operations from sync Celery tasks.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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
        chunks = _run_async(
            chunk_service.get_chunks_by_document(
                document_id=document_id,
                matter_id=matter_id,
            )
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

        # Combine chunk content for extraction
        # Using parent chunks if available, otherwise all chunks
        parent_chunks = [c for c in chunks if c.get("parent_chunk_id") is None]
        chunks_to_process = parent_chunks if parent_chunks else chunks

        # Extract text from chunks
        full_text = "\n\n".join(
            chunk.get("content", "") for chunk in chunks_to_process
        )

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

        # Run date extraction via Gemini
        extraction_result = date_extractor.extract_dates_sync(
            text=full_text,
            document_id=document_id,
            matter_id=matter_id,
            page_number=None,  # Will be refined if we process per-page
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
            dates=extraction_result.dates,
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
            dates_found=len(extraction_result.dates),
            events_created=len(event_ids),
            processing_time_ms=extraction_result.processing_time_ms,
        )

        result = {
            "status": "completed",
            "document_id": document_id,
            "matter_id": matter_id,
            "dates_found": len(extraction_result.dates),
            "events_created": len(event_ids),
            "event_ids": event_ids,
            "processing_time_ms": extraction_result.processing_time_ms,
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

        # Get raw_date events for this document
        raw_events = timeline_service.get_events_for_classification_sync(
            matter_id=matter_id,
            limit=1000,  # Get all for document
        )

        # Filter to only events from this document
        doc_events = [e for e in raw_events if e.document_id == document_id]

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

        return {
            "status": "completed",
            "document_id": document_id,
            "matter_id": matter_id,
            "events_processed": len(doc_events),
            "events_updated": updated_count,
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
        force_reclassify: If True, reclassify already classified events (not implemented).

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

        # Get raw_date events for classification
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
