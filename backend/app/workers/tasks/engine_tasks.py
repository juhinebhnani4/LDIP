"""Celery tasks related to engine execution.

Implements background tasks for:
- Timeline Engine: Date extraction from documents (Story 4-1)
- Citation Engine: (Future)
- Contradiction Engine: (Future)

Job Tracking Integration:
- Creates processing jobs when engine tasks start
- Updates job status and progress as processing continues
- Records completion and failure states
"""

import asyncio

import structlog

from app.engines.timeline import DateExtractor, get_date_extractor
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
) -> dict:
    """Extract dates from a document's text content.

    Loads document chunks, runs Gemini date extraction, and saves
    results to the events table as raw_date events.

    Args:
        document_id: Document UUID to process.
        matter_id: Matter UUID for isolation.
        job_id: Optional job ID for progress tracking.
        force_reprocess: If True, deletes existing dates before extraction.

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

        return {
            "status": "completed",
            "document_id": document_id,
            "matter_id": matter_id,
            "dates_found": len(extraction_result.dates),
            "events_created": len(event_ids),
            "event_ids": event_ids,
            "processing_time_ms": extraction_result.processing_time_ms,
        }

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
) -> dict:
    """Extract dates from all case file documents in a matter.

    Queues date extraction for each document. Can optionally specify
    which documents to process.

    Args:
        matter_id: Matter UUID.
        document_ids: Optional list of specific documents. If None, all case files.
        force_reprocess: If True, reprocess already processed documents.

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
