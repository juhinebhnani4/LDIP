"""Celery tasks related to document processing.

Implements OCR processing using Google Document AI with retry logic
and proper status updates. Includes Gemini-based OCR validation
and parent-child chunking for RAG pipelines.

Job Tracking Integration (Story 2c-3):
- Creates processing jobs when document processing starts
- Updates job status and progress as each stage completes
- Records stage history for granular tracking
- Preserves partial progress for failure recovery
"""

import asyncio
import contextlib

import structlog
from celery.exceptions import MaxRetriesExceededError

from app.engines.citation import (
    CitationExtractor,
    CitationExtractorError,
    CitationStorageService,
    get_citation_extractor,
    get_citation_storage_service,
)
from app.models.activity import ActivityTypeEnum
from app.models.document import DocumentStatus
from app.models.job import JobStatus, JobType
from app.models.ocr_validation import CorrectionType, ValidationStatus
from app.services.activity_service import (
    get_activity_service,
)
from app.services.bounding_box_service import (
    BoundingBoxService,
    get_bounding_box_service,
)
from app.services.chunk_service import (
    ChunkService,
    ChunkServiceError,
    get_chunk_service,
)
from app.services.chunking.bbox_linker import link_chunks_to_bboxes
from app.services.chunking.parent_child_chunker import ParentChildChunker
from app.services.document_service import (
    DocumentService,
    DocumentServiceError,
    get_document_service,
)
from app.core.config import get_settings
from app.services.job_tracking import (
    JobTrackingService,
    create_progress_tracker,
    get_job_tracking_service,
)
from app.services.job_tracking.time_estimator import TimeEstimator, get_time_estimator
from app.services.mig import (
    EntityResolver,
    MIGEntityExtractor,
    MIGGraphService,
    get_entity_resolver,
    get_mig_extractor,
    get_mig_graph_service,
)
from app.services.mig.entity_resolver import AliasResolutionError
from app.services.mig.extractor import MIGExtractorError
from app.services.ocr import OCRProcessor, OCRServiceError, get_ocr_processor
from app.services.ocr.confidence_calculator import (
    ConfidenceCalculatorError,
    update_document_confidence,
)
from app.services.ocr.gemini_validator import (
    GeminiOCRValidator,
    GeminiValidatorError,
    get_gemini_validator,
)
from app.services.ocr.human_review_service import (
    HumanReviewService,
    HumanReviewServiceError,
    get_human_review_service,
)
from app.services.ocr.pattern_corrector import apply_pattern_corrections
from app.services.ocr.validation_extractor import (
    ValidationExtractor,
    ValidationExtractorError,
    get_validation_extractor,
)
from app.services.pubsub_service import (
    FeatureType,
    broadcast_document_status,
    broadcast_entity_discovery,
    broadcast_entity_streaming,
    broadcast_feature_ready,
    broadcast_job_progress,
    broadcast_job_status_change,
)
from app.services.rag.embedder import (
    EmbeddingService,
    EmbeddingServiceError,
    get_embedding_service,
)
from app.services.storage_service import (
    StorageError,
    StorageService,
    get_storage_service,
)
from app.services.summary_service import get_summary_service
from app.services.pdf_chunker import get_pdf_chunker, CHUNK_THRESHOLD
from app.services.pdf_router import CHUNK_SIZE
from app.services.ocr_chunk_service import get_ocr_chunk_service
from app.services.contradiction import (
    StatementComparisonService,
    get_statement_comparison_service,
)
from app.services.contradiction.comparator import ComparisonServiceError
from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [30, 60, 120]  # Exponential backoff: 30s, 60s, 120s

# PDF magic bytes signature
PDF_MAGIC_BYTES = b"%PDF-"


def _validate_pdf_content(content: bytes, document_id: str) -> None:
    """Validate that content appears to be a PDF file.

    Args:
        content: File content bytes.
        document_id: Document ID for logging.

    Raises:
        OCRServiceError: If content is not a valid PDF.
    """
    if not content.startswith(PDF_MAGIC_BYTES):
        logger.error(
            "document_invalid_pdf",
            document_id=document_id,
            first_bytes=content[:20].hex() if content else "empty",
        )
        raise OCRServiceError(
            message="File does not appear to be a valid PDF",
            code="INVALID_PDF_FORMAT",
            is_retryable=False,
        )


def _get_pdf_page_count(pdf_content: bytes, document_id: str) -> int:
    """Get page count from PDF without loading full content into memory.

    Story 16.1: Page count detection for routing large documents.

    Args:
        pdf_content: PDF file bytes.
        document_id: Document ID for logging.

    Returns:
        Number of pages in the PDF.

    Raises:
        OCRServiceError: If PDF cannot be parsed.
    """
    from io import BytesIO
    import pypdf

    try:
        reader = pypdf.PdfReader(BytesIO(pdf_content))
        page_count = len(reader.pages)

        logger.info(
            "pdf_page_count_detected",
            document_id=document_id,
            page_count=page_count,
            requires_chunking=page_count > CHUNK_THRESHOLD,
        )

        return page_count

    except pypdf.errors.PdfReadError as e:
        logger.error(
            "pdf_page_count_failed",
            document_id=document_id,
            error=str(e),
        )
        raise OCRServiceError(
            message=f"Failed to read PDF page count: {e}",
            code="PDF_PARSE_ERROR",
            is_retryable=False,
        ) from e


async def _create_chunk_records(
    document_id: str,
    matter_id: str,
    page_count: int,
    chunk_size: int = CHUNK_SIZE,
) -> list:
    """Create chunk records in database for parallel processing.

    Story 16.1: Create chunk tracking records before dispatching.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID.
        page_count: Total pages in document.
        chunk_size: Pages per chunk (default from CHUNK_SIZE config).

    Returns:
        List of created chunk records.
    """
    chunk_service = get_ocr_chunk_service()
    chunks = []

    page_start = 1
    chunk_index = 0

    while page_start <= page_count:
        page_end = min(page_start + chunk_size - 1, page_count)

        chunk = await chunk_service.create_chunk(
            document_id=document_id,
            matter_id=matter_id,
            chunk_index=chunk_index,
            page_start=page_start,
            page_end=page_end,
        )
        chunks.append(chunk)

        logger.debug(
            "chunk_record_created",
            document_id=document_id,
            chunk_index=chunk_index,
            page_start=page_start,
            page_end=page_end,
        )

        page_start = page_end + 1
        chunk_index += 1

    logger.info(
        "chunk_records_created",
        document_id=document_id,
        chunk_count=len(chunks),
        page_count=page_count,
    )

    return chunks


# =============================================================================
# Job Tracking Helper Functions (Story 2c-3)
# =============================================================================

# Stage names for the processing pipeline (must match TimeEstimator stages)
PIPELINE_STAGES = [
    "ocr",
    "validation",
    "confidence",
    "chunking",
    "embedding",
    "entity_extraction",
    "alias_resolution",
    "citation_extraction",
    "citation_verification",  # Story 3-3: Citation Verification
    "contradiction_detection",  # Epic 5: Contradiction Detection
]

STAGE_INDEX = {stage: idx for idx, stage in enumerate(PIPELINE_STAGES)}


def _run_async(coro):
    """Run async coroutine in sync context for Celery tasks.

    Creates a new event loop to run async operations from sync Celery tasks.
    This is necessary because Celery workers run synchronously, but our
    database operations use asyncio.

    Note:
        Uses asyncio.run() which properly creates and cleans up an event loop.
        For batch operations, prefer wrapping all async calls in a single
        async function and calling asyncio.run() once.

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The result of the coroutine execution.

    Example:
        >>> result = _run_async(some_async_function(arg1, arg2))
    """
    return asyncio.run(coro)


def _get_or_create_job(
    matter_id: str,
    document_id: str,
    celery_task_id: str | None = None,
    job_tracker: JobTrackingService | None = None,
) -> str | None:
    """Get existing active job or create a new one for document processing.

    Args:
        matter_id: Matter UUID.
        document_id: Document UUID.
        celery_task_id: Optional Celery task ID for correlation.
        job_tracker: Optional JobTrackingService instance (for testing).

    Returns:
        Job ID if created/found, None if failed.
    """
    tracker = job_tracker or get_job_tracking_service()

    try:
        # Check for existing active job
        existing_job = _run_async(
            tracker.get_active_job_for_document(document_id, matter_id)
        )

        if existing_job:
            logger.debug(
                "job_tracking_existing_job_found",
                job_id=existing_job.id,
                document_id=document_id,
            )
            return existing_job.id

        # Create new job
        job = _run_async(
            tracker.create_job(
                matter_id=matter_id,
                document_id=document_id,
                job_type=JobType.DOCUMENT_PROCESSING,
                celery_task_id=celery_task_id,
            )
        )

        logger.info(
            "job_tracking_job_created",
            job_id=job.id,
            document_id=document_id,
            matter_id=matter_id,
        )

        return job.id

    except Exception as e:
        # Job tracking failures are non-critical - log and continue
        logger.warning(
            "job_tracking_create_failed",
            document_id=document_id,
            error=str(e),
        )
        return None


def _update_job_stage_start(
    job_id: str | None,
    stage_name: str,
    matter_id: str | None = None,
    job_tracker: JobTrackingService | None = None,
    time_estimator: TimeEstimator | None = None,
    page_count: int | None = None,
) -> None:
    """Record stage start and update job progress.

    Args:
        job_id: Job UUID.
        stage_name: Stage name (ocr, validation, etc.).
        matter_id: Matter UUID for broadcasting.
        job_tracker: Optional JobTrackingService instance.
        time_estimator: Optional TimeEstimator instance.
        page_count: Document page count for time estimation.
    """
    if not job_id:
        return

    tracker = job_tracker or get_job_tracking_service()
    estimator = time_estimator or get_time_estimator()

    try:
        # Record stage start
        _run_async(tracker.record_stage_start(job_id, stage_name))

        # Calculate progress percentage
        progress_pct = estimator.estimate_stage_progress(stage_name, 0.0)

        # Calculate estimated completion if we have page count
        estimated_completion = None
        if page_count and page_count > 0:
            estimated_completion = estimator.estimate_completion_time(
                page_count=page_count,
                current_stage=stage_name,
            )

        # Update job status
        _run_async(
            tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                stage=stage_name,
                progress_pct=progress_pct,
            )
        )

        # Update estimated completion if available
        if estimated_completion:
            _run_async(
                tracker.set_estimated_completion(job_id, estimated_completion)
            )

        # Broadcast progress
        if matter_id:
            broadcast_job_progress(
                matter_id=matter_id,
                job_id=job_id,
                stage=stage_name,
                progress_pct=progress_pct,
                estimated_completion=estimated_completion,
            )

        logger.debug(
            "job_tracking_stage_started",
            job_id=job_id,
            stage=stage_name,
            progress_pct=progress_pct,
        )

    except Exception as e:
        logger.warning(
            "job_tracking_stage_start_failed",
            job_id=job_id,
            stage=stage_name,
            error=str(e),
        )


def _update_job_stage_complete(
    job_id: str | None,
    stage_name: str,
    matter_id: str | None = None,
    job_tracker: JobTrackingService | None = None,
    time_estimator: TimeEstimator | None = None,
    metadata: dict | None = None,
) -> None:
    """Record stage completion and update job progress.

    Args:
        job_id: Job UUID.
        stage_name: Stage name that completed.
        matter_id: Matter UUID for broadcasting.
        job_tracker: Optional JobTrackingService instance.
        time_estimator: Optional TimeEstimator instance.
        metadata: Optional stage metadata to record.
    """
    if not job_id:
        return

    tracker = job_tracker or get_job_tracking_service()
    estimator = time_estimator or get_time_estimator()

    try:
        # Record stage complete
        _run_async(tracker.record_stage_complete(job_id, stage_name, metadata))

        # Calculate progress (stage 100% complete)
        progress_pct = estimator.estimate_stage_progress(stage_name, 1.0)

        # Update completed stages count
        stage_idx = STAGE_INDEX.get(stage_name, -1)
        completed_stages = stage_idx + 1 if stage_idx >= 0 else None

        # Get current job to update
        job = _run_async(tracker.get_job(job_id))
        if job:
            from app.models.job import ProcessingJobUpdate

            update = ProcessingJobUpdate(
                progress_pct=progress_pct,
                completed_stages=completed_stages,
            )
            _run_async(tracker.update_job(job_id, update))

        # Broadcast progress
        if matter_id:
            broadcast_job_progress(
                matter_id=matter_id,
                job_id=job_id,
                stage=stage_name,
                progress_pct=progress_pct,
            )

        logger.debug(
            "job_tracking_stage_completed",
            job_id=job_id,
            stage=stage_name,
            progress_pct=progress_pct,
        )

    except Exception as e:
        logger.warning(
            "job_tracking_stage_complete_failed",
            job_id=job_id,
            stage=stage_name,
            error=str(e),
        )


def _update_job_stage_failure(
    job_id: str | None,
    stage_name: str,
    error_message: str,
    error_code: str | None = None,
    matter_id: str | None = None,
    job_tracker: JobTrackingService | None = None,
) -> None:
    """Record stage failure and update job status.

    Args:
        job_id: Job UUID.
        stage_name: Stage name that failed.
        error_message: Error description.
        error_code: Machine-readable error code.
        matter_id: Matter UUID for broadcasting.
        job_tracker: Optional JobTrackingService instance.
    """
    if not job_id:
        return

    tracker = job_tracker or get_job_tracking_service()

    try:
        # Record stage failure
        _run_async(tracker.record_stage_failure(job_id, stage_name, error_message))

        # Increment retry count
        _run_async(tracker.increment_retry_count(job_id))

        logger.debug(
            "job_tracking_stage_failed",
            job_id=job_id,
            stage=stage_name,
            error=error_message,
        )

    except Exception as e:
        logger.warning(
            "job_tracking_stage_failure_record_failed",
            job_id=job_id,
            stage=stage_name,
            error=str(e),
        )


def _mark_job_failed(
    job_id: str | None,
    error_message: str,
    error_code: str | None = None,
    matter_id: str | None = None,
    job_tracker: JobTrackingService | None = None,
) -> None:
    """Mark job as failed after all retries exhausted.

    Args:
        job_id: Job UUID.
        error_message: Error description.
        error_code: Machine-readable error code.
        matter_id: Matter UUID for broadcasting.
        job_tracker: Optional JobTrackingService instance.
    """
    if not job_id:
        return

    tracker = job_tracker or get_job_tracking_service()

    try:
        _run_async(
            tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=error_message,
                error_code=error_code,
            )
        )

        # Broadcast status change
        if matter_id:
            broadcast_job_status_change(
                matter_id=matter_id,
                job_id=job_id,
                old_status=JobStatus.PROCESSING.value,
                new_status=JobStatus.FAILED.value,
            )

            # Story 14.5: AC #6 - Create activity for processing failure
            try:
                activity_service = get_activity_service()
                _run_async(
                    activity_service.create_activity_for_matter_members(
                        matter_id=matter_id,
                        type=ActivityTypeEnum.PROCESSING_FAILED,
                        description="Document processing failed",
                        metadata={"job_id": job_id, "error_code": error_code},
                    )
                )
                logger.info(
                    "activity_created_on_job_failed",
                    job_id=job_id,
                    matter_id=matter_id,
                )
            except Exception as activity_err:
                # Non-fatal: log and continue
                logger.warning(
                    "activity_creation_failed_on_job_failed",
                    job_id=job_id,
                    matter_id=matter_id,
                    error=str(activity_err),
                )

        logger.info(
            "job_tracking_job_failed",
            job_id=job_id,
            error_code=error_code,
        )

    except Exception as e:
        logger.warning(
            "job_tracking_mark_failed_error",
            job_id=job_id,
            error=str(e),
        )


def _mark_job_completed(
    job_id: str | None,
    matter_id: str | None = None,
    document_id: str | None = None,
    job_tracker: JobTrackingService | None = None,
) -> None:
    """Mark job as completed successfully and update document status.

    Args:
        job_id: Job UUID.
        matter_id: Matter UUID for broadcasting.
        document_id: Document UUID to update status.
        job_tracker: Optional JobTrackingService instance.
    """
    if not job_id:
        return

    tracker = job_tracker or get_job_tracking_service()

    try:
        _run_async(
            tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                progress_pct=100,
            )
        )

        # Update document status to completed
        if document_id:
            try:
                doc_service = get_document_service()
                doc_service.update_ocr_status(
                    document_id=document_id,
                    status=DocumentStatus.COMPLETED,
                )
                logger.info(
                    "document_status_updated_to_completed",
                    document_id=document_id,
                    job_id=job_id,
                )
            except Exception as doc_err:
                logger.warning(
                    "document_status_update_failed",
                    document_id=document_id,
                    job_id=job_id,
                    error=str(doc_err),
                )

        # Broadcast status change
        if matter_id:
            broadcast_job_status_change(
                matter_id=matter_id,
                job_id=job_id,
                old_status=JobStatus.PROCESSING.value,
                new_status=JobStatus.COMPLETED.value,
            )

            # Invalidate summary cache so next summary fetch gets fresh data
            # Story 14.1: AC #4 - Invalidate cache on processing completion
            try:
                summary_service = get_summary_service()
                _run_async(summary_service.invalidate_cache(matter_id))
                logger.info(
                    "summary_cache_invalidated_on_job_complete",
                    job_id=job_id,
                    matter_id=matter_id,
                )
            except Exception as cache_err:
                # Non-fatal: log and continue
                logger.warning(
                    "summary_cache_invalidation_failed_on_job_complete",
                    job_id=job_id,
                    matter_id=matter_id,
                    error=str(cache_err),
                )

            # Story 14.5: AC #6 - Create activity for processing completion
            try:
                activity_service = get_activity_service()
                _run_async(
                    activity_service.create_activity_for_matter_members(
                        matter_id=matter_id,
                        type=ActivityTypeEnum.PROCESSING_COMPLETE,
                        description="Document processing complete",
                        metadata={"job_id": job_id},
                    )
                )
                logger.info(
                    "activity_created_on_job_complete",
                    job_id=job_id,
                    matter_id=matter_id,
                )
            except Exception as activity_err:
                # Non-fatal: log and continue
                logger.warning(
                    "activity_creation_failed_on_job_complete",
                    job_id=job_id,
                    matter_id=matter_id,
                    error=str(activity_err),
                )

        logger.info(
            "job_tracking_job_completed",
            job_id=job_id,
        )

    except Exception as e:
        logger.warning(
            "job_tracking_mark_completed_error",
            job_id=job_id,
            error=str(e),
        )


# =============================================================================
# Job ID Lookup and Idempotency Helpers (Pipeline Resilience)
# =============================================================================


def _lookup_job_id_for_document(document_id: str) -> str | None:
    """Lookup job_id from database when not provided in task chain.

    This enables standalone task calls (via apply_async with just document_id)
    to still update job progress correctly.

    Args:
        document_id: Document UUID.

    Returns:
        Job ID if found, None otherwise.
    """
    from app.services.supabase.client import get_service_client

    try:
        client = get_service_client()
        if client is None:
            return None

        # Find active job for this document
        response = (
            client.table("processing_jobs")
            .select("id")
            .eq("document_id", document_id)
            .in_("status", ["QUEUED", "PROCESSING"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:
            job_id = response.data[0]["id"]
            logger.debug(
                "job_id_lookup_success",
                document_id=document_id,
                job_id=job_id,
            )
            return job_id

        logger.debug(
            "job_id_lookup_no_active_job",
            document_id=document_id,
        )
        return None

    except Exception as e:
        logger.warning(
            "job_id_lookup_failed",
            document_id=document_id,
            error=str(e),
        )
        return None


def _check_embedding_complete(document_id: str) -> tuple[bool, int, int]:
    """Check if embedding is already complete for a document.

    Returns:
        Tuple of (is_complete, total_chunks, embedded_chunks).
    """
    from app.services.supabase.client import get_service_client

    try:
        client = get_service_client()
        if client is None:
            return False, 0, 0

        # Count total chunks
        total_resp = (
            client.table("chunks")
            .select("id", count="exact")
            .eq("document_id", document_id)
            .execute()
        )
        total_count = total_resp.count or 0

        if total_count == 0:
            return False, 0, 0

        # Count chunks with embeddings
        embedded_resp = (
            client.table("chunks")
            .select("id", count="exact")
            .eq("document_id", document_id)
            .not_.is_("embedding", "null")
            .execute()
        )
        embedded_count = embedded_resp.count or 0

        is_complete = total_count > 0 and total_count == embedded_count

        logger.debug(
            "embedding_completeness_check",
            document_id=document_id,
            total_chunks=total_count,
            embedded_chunks=embedded_count,
            is_complete=is_complete,
        )

        return is_complete, total_count, embedded_count

    except Exception as e:
        logger.warning(
            "embedding_completeness_check_failed",
            document_id=document_id,
            error=str(e),
        )
        return False, 0, 0


def _check_entities_exist(matter_id: str) -> tuple[bool, int]:
    """Check if entities have been extracted for a matter.

    Returns:
        Tuple of (has_entities, entity_count).
    """
    from app.services.supabase.client import get_service_client

    try:
        client = get_service_client()
        if client is None:
            return False, 0

        response = (
            client.table("identity_nodes")
            .select("id", count="exact")
            .eq("matter_id", matter_id)
            .execute()
        )
        entity_count = response.count or 0

        logger.debug(
            "entity_existence_check",
            matter_id=matter_id,
            entity_count=entity_count,
        )

        return entity_count > 0, entity_count

    except Exception as e:
        logger.warning(
            "entity_existence_check_failed",
            matter_id=matter_id,
            error=str(e),
        )
        return False, 0


def _check_entity_mentions_exist_for_document(document_id: str) -> tuple[bool, int]:
    """Check if entity mentions have been extracted for a specific document.

    This is used for per-document idempotency to ensure entity extraction
    runs for each document, not just once per matter.

    Returns:
        Tuple of (has_mentions, mention_count).
    """
    from app.services.supabase.client import get_service_client

    try:
        client = get_service_client()
        if client is None:
            return False, 0

        response = (
            client.table("entity_mentions")
            .select("id", count="exact")
            .eq("document_id", document_id)
            .execute()
        )
        mention_count = response.count or 0

        logger.debug(
            "entity_mentions_document_check",
            document_id=document_id,
            mention_count=mention_count,
        )

        return mention_count > 0, mention_count
    except Exception as e:
        logger.warning(
            "entity_mentions_document_check_failed",
            document_id=document_id,
            error=str(e),
        )
        return False, 0


def _sync_entity_ids_to_chunks(document_id: str) -> int:
    """Sync entity_ids from entity_mentions to chunks table.

    After entity extraction, this function populates the chunks.entity_ids
    array based on entity_mentions records. This denormalized array enables
    efficient filtering during contradiction detection and other queries.

    Args:
        document_id: Document UUID.

    Returns:
        Number of chunks updated.
    """
    from app.services.supabase.client import get_service_client

    try:
        client = get_service_client()
        if client is None:
            logger.warning(
                "sync_entity_ids_no_client",
                document_id=document_id,
            )
            return 0

        # Step 1: Get all entity mentions for this document
        # Group by chunk_id to build the entity_ids array for each chunk
        mentions_response = (
            client.table("entity_mentions")
            .select("entity_id, chunk_id")
            .eq("document_id", document_id)
            .not_.is_("chunk_id", "null")
            .execute()
        )

        if not mentions_response.data:
            logger.info(
                "sync_entity_ids_no_mentions",
                document_id=document_id,
            )
            return 0

        # Step 2: Build chunk_id -> entity_ids map
        chunk_entities: dict[str, set[str]] = {}
        for row in mentions_response.data:
            chunk_id = row.get("chunk_id")
            entity_id = row.get("entity_id")
            if chunk_id and entity_id:
                if chunk_id not in chunk_entities:
                    chunk_entities[chunk_id] = set()
                chunk_entities[chunk_id].add(entity_id)

        if not chunk_entities:
            logger.info(
                "sync_entity_ids_no_chunk_mappings",
                document_id=document_id,
            )
            return 0

        # Step 3: Update each chunk with its entity_ids
        updated_count = 0
        for chunk_id, entity_ids in chunk_entities.items():
            try:
                client.table("chunks").update(
                    {"entity_ids": list(entity_ids)}
                ).eq("id", chunk_id).execute()
                updated_count += 1
            except Exception as e:
                logger.warning(
                    "sync_entity_ids_chunk_update_failed",
                    chunk_id=chunk_id,
                    error=str(e),
                )

        logger.info(
            "sync_entity_ids_completed",
            document_id=document_id,
            chunks_updated=updated_count,
            total_chunk_entity_pairs=sum(len(ids) for ids in chunk_entities.values()),
        )

        return updated_count

    except Exception as e:
        logger.error(
            "sync_entity_ids_failed",
            document_id=document_id,
            error=str(e),
        )
        return 0


@celery_app.task(
    name="app.workers.tasks.document_tasks.process_document",
    bind=True,
    autoretry_for=(OCRServiceError, StorageError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=MAX_RETRIES,
    retry_jitter=True,
)  # type: ignore[misc]
def process_document(
    self,  # type: ignore[no-untyped-def]
    document_id: str,
    document_service: DocumentService | None = None,
    storage_service: StorageService | None = None,
    ocr_processor: OCRProcessor | None = None,
    bounding_box_service: BoundingBoxService | None = None,
    job_tracker: JobTrackingService | None = None,
) -> dict[str, str | int | float | None]:
    """Process a document through OCR pipeline.

    Downloads PDF from Supabase Storage, processes with Google Document AI,
    and saves extracted text and bounding boxes.

    Args:
        document_id: Document UUID to process.
        document_service: Optional DocumentService instance (for testing).
        storage_service: Optional StorageService instance (for testing).
        ocr_processor: Optional OCRProcessor instance (for testing).
        bounding_box_service: Optional BoundingBoxService instance (for testing).
        job_tracker: Optional JobTrackingService instance (for testing).

    Returns:
        Task result with status, page_count, and processing details.

    Raises:
        OCRServiceError: If OCR processing fails (will trigger retry).
        StorageError: If storage operations fail (will trigger retry).
    """
    # Use injected services or get defaults
    doc_service = document_service or get_document_service()
    store_service = storage_service or get_storage_service()
    ocr = ocr_processor or get_ocr_processor()
    bbox_service = bounding_box_service or get_bounding_box_service()

    # Job tracking context (initialized below)
    job_id: str | None = None
    matter_id: str | None = None

    logger.info(
        "document_processing_task_started",
        document_id=document_id,
        retry_count=self.request.retries,
    )

    try:
        # Get document info
        storage_path, matter_id = doc_service.get_document_for_processing(document_id)

        # Create or get existing job for tracking (Story 2c-3)
        job_id = _get_or_create_job(
            matter_id=matter_id,
            document_id=document_id,
            celery_task_id=self.request.id,
            job_tracker=job_tracker,
        )

        # Update status to processing
        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.PROCESSING,
        )

        # Broadcast status change
        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="processing",
        )

        # Track OCR stage start
        _update_job_stage_start(job_id, "ocr", matter_id)

        # Download PDF from storage
        logger.info(
            "document_downloading",
            document_id=document_id,
            storage_path=storage_path,
        )
        pdf_content = store_service.download_file(storage_path)

        # Validate PDF format before sending to OCR
        _validate_pdf_content(pdf_content, document_id)

        # Story 16.1: Detect page count and route to chunked processing if >30 pages
        page_count = _get_pdf_page_count(pdf_content, document_id)

        if page_count > CHUNK_THRESHOLD:
            # Large document - route to chunked parallel processing
            logger.info(
                "routing_to_chunked_processing",
                document_id=document_id,
                page_count=page_count,
                threshold=CHUNK_THRESHOLD,
            )

            # Create chunk records in database
            _run_async(_create_chunk_records(
                document_id=document_id,
                matter_id=matter_id,
                page_count=page_count,
            ))

            # Import here to avoid circular dependency
            from app.workers.tasks.chunked_document_tasks import process_document_chunked

            # Dispatch to chunked processing task
            process_document_chunked.delay(
                document_id=document_id,
                matter_id=matter_id,
                job_id=job_id,
            )

            logger.info(
                "chunked_processing_dispatched",
                document_id=document_id,
                page_count=page_count,
                job_id=job_id,
            )

            return {
                "status": "chunked_processing_dispatched",
                "document_id": document_id,
                "page_count": page_count,
                "job_id": job_id,
                "message": f"Document with {page_count} pages routed to chunked processing",
            }

        # Small document (≤30 pages) - process with sync Document AI call
        logger.info(
            "document_ocr_processing",
            document_id=document_id,
            content_size=len(pdf_content),
            page_count=page_count,
        )
        ocr_result = ocr.process_document(
            pdf_content=pdf_content,
            document_id=document_id,
        )

        # Save bounding boxes
        logger.info(
            "document_saving_bounding_boxes",
            document_id=document_id,
            bbox_count=len(ocr_result.bounding_boxes),
        )

        # Delete any existing bounding boxes (in case of reprocessing)
        bbox_service.delete_bounding_boxes(document_id)

        # Save new bounding boxes
        saved_bbox_count = bbox_service.save_bounding_boxes(
            document_id=document_id,
            matter_id=matter_id,
            bounding_boxes=ocr_result.bounding_boxes,
        )

        # Calculate average quality score from pages
        avg_quality_score = None
        quality_scores = [
            p.image_quality_score
            for p in ocr_result.pages
            if p.image_quality_score is not None
        ]
        if quality_scores:
            avg_quality_score = sum(quality_scores) / len(quality_scores)

        # Update document with OCR results
        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.OCR_COMPLETE,
            extracted_text=ocr_result.full_text,
            page_count=ocr_result.page_count,
            ocr_confidence=ocr_result.overall_confidence,
            ocr_quality_score=avg_quality_score,
        )

        # Broadcast completion status
        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="ocr_complete",
            page_count=ocr_result.page_count,
            ocr_confidence=ocr_result.overall_confidence,
        )

        # Track OCR stage completion with metadata
        _update_job_stage_complete(
            job_id,
            "ocr",
            matter_id,
            metadata={
                "page_count": ocr_result.page_count,
                "bbox_count": saved_bbox_count,
                "confidence": ocr_result.overall_confidence,
            },
        )

        logger.info(
            "document_processing_task_completed",
            document_id=document_id,
            page_count=ocr_result.page_count,
            bbox_count=saved_bbox_count,
            processing_time_ms=ocr_result.processing_time_ms,
            overall_confidence=ocr_result.overall_confidence,
        )

        return {
            "status": "ocr_complete",
            "document_id": document_id,
            "page_count": ocr_result.page_count,
            "bbox_count": saved_bbox_count,
            "processing_time_ms": ocr_result.processing_time_ms,
            "overall_confidence": ocr_result.overall_confidence,
            "job_id": job_id,
        }

    except (OCRServiceError, StorageError) as e:
        # Handle retryable errors
        retry_count = self.request.retries
        error_code = getattr(e, "code", "UNKNOWN")

        logger.warning(
            "document_processing_task_retry",
            document_id=document_id,
            retry_count=retry_count,
            max_retries=MAX_RETRIES,
            error=str(e),
            error_code=error_code,
        )

        # Track stage failure for job tracking
        _update_job_stage_failure(
            job_id, "ocr", str(e), error_code, matter_id
        )

        # Increment retry count in database
        try:
            doc_service.increment_ocr_retry_count(document_id)
        except DocumentServiceError:
            pass  # Don't fail the retry because of this

        # Check if we've exhausted retries
        # Note: matter_id may not be available if it failed before retrieval
        if retry_count >= MAX_RETRIES:
            _matter_id = matter_id
            if not _matter_id:
                with contextlib.suppress(Exception):
                    _, _matter_id = doc_service.get_document_for_processing(document_id)
            # Mark job as failed
            _mark_job_failed(job_id, str(e), error_code, _matter_id)
            return _handle_max_retries_exceeded(doc_service, document_id, e, _matter_id)

        # Re-raise to trigger retry
        raise

    except MaxRetriesExceededError as e:
        _matter_id = matter_id
        if not _matter_id:
            with contextlib.suppress(Exception):
                _, _matter_id = doc_service.get_document_for_processing(document_id)
        # Mark job as failed
        _mark_job_failed(
            job_id,
            f"Max retries exceeded: {e.__cause__ or e}",
            "MAX_RETRIES_EXCEEDED",
            _matter_id,
        )
        return _handle_max_retries_exceeded(
            doc_service, document_id, e.__cause__ or e, _matter_id
        )

    except DocumentServiceError as e:
        # Document service errors are not retryable
        logger.error(
            "document_processing_task_failed",
            document_id=document_id,
            error=str(e),
            error_code=e.code,
        )

        # Mark job as failed
        _mark_job_failed(job_id, e.message, e.code, matter_id)

        with contextlib.suppress(DocumentServiceError):
            doc_service.update_ocr_status(
                document_id=document_id,
                status=DocumentStatus.OCR_FAILED,
                ocr_error=f"{e.code}: {e.message}",
            )

        return {
            "status": "ocr_failed",
            "document_id": document_id,
            "error_code": e.code,
            "error_message": e.message,
            "job_id": job_id,
        }

    except Exception as e:
        # Unexpected errors
        logger.error(
            "document_processing_task_unexpected_error",
            document_id=document_id,
            error=str(e),
            error_type=type(e).__name__,
        )

        # Mark job as failed
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", matter_id)

        with contextlib.suppress(DocumentServiceError):
            doc_service.update_ocr_status(
                document_id=document_id,
                status=DocumentStatus.OCR_FAILED,
                ocr_error=f"Unexpected error: {e!s}",
            )

        return {
            "status": "ocr_failed",
            "document_id": document_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
            "job_id": job_id,
        }


def _handle_max_retries_exceeded(
    doc_service: DocumentService,
    document_id: str,
    error: Exception,
    matter_id: str | None = None,
) -> dict[str, str]:
    """Handle the case when max retries have been exceeded.

    Args:
        doc_service: DocumentService instance.
        document_id: Document UUID.
        error: The error that caused the failure.
        matter_id: Optional matter UUID for broadcasting.

    Returns:
        Task result indicating failure.
    """
    error_code = getattr(error, "code", "MAX_RETRIES_EXCEEDED")
    error_message = str(error)

    logger.error(
        "document_processing_task_max_retries",
        document_id=document_id,
        error=error_message,
        error_code=error_code,
    )

    try:
        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.OCR_FAILED,
            ocr_error=f"Max retries exceeded ({MAX_RETRIES}): {error_message}",
        )
    except DocumentServiceError as e:
        logger.error(
            "document_processing_task_status_update_failed",
            document_id=document_id,
            error=str(e),
        )

    # Broadcast failure status
    if matter_id:
        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="ocr_failed",
            error_message=f"Max retries exceeded: {error_message}",
        )

    return {
        "status": "ocr_failed",
        "document_id": document_id,
        "error_code": error_code,
        "error_message": f"Max retries exceeded: {error_message}",
    }


@celery_app.task(name="app.workers.tasks.document_tasks.retry_ocr")  # type: ignore[misc]
def retry_ocr(document_id: str) -> dict[str, str]:
    """Manually retry OCR for a failed document.

    Resets retry count and requeues the document for processing.

    Args:
        document_id: Document UUID to retry.

    Returns:
        Task submission result.
    """
    logger.info("document_manual_retry_requested", document_id=document_id)

    doc_service = get_document_service()

    try:
        # Reset the document status to pending
        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.PENDING,
            ocr_error=None,  # Clear previous error
        )

        # Queue for processing
        process_document.delay(document_id)

        logger.info("document_manual_retry_queued", document_id=document_id)

        return {
            "status": "queued",
            "document_id": document_id,
            "message": "Document queued for OCR retry",
        }

    except DocumentServiceError as e:
        logger.error(
            "document_manual_retry_failed",
            document_id=document_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "document_id": document_id,
            "error": e.message,
        }


@celery_app.task(
    name="app.workers.tasks.document_tasks.validate_ocr",
    bind=True,
    autoretry_for=(GeminiValidatorError, ValidationExtractorError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=MAX_RETRIES,
    retry_jitter=True,
)  # type: ignore[misc]
def validate_ocr(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    validation_extractor: ValidationExtractor | None = None,
    gemini_validator: GeminiOCRValidator | None = None,
    human_review_service: HumanReviewService | None = None,
    document_service: DocumentService | None = None,
    bounding_box_service: BoundingBoxService | None = None,
    job_tracker: JobTrackingService | None = None,
) -> dict[str, str | int | float | None]:
    """Validate OCR results using pattern correction and Gemini.

    This task runs after process_document to validate low-confidence words.
    It applies pattern corrections first, then uses Gemini for remaining
    low-confidence words, and queues very low confidence words for human review.

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        validation_extractor: Optional ValidationExtractor instance (for testing).
        gemini_validator: Optional GeminiOCRValidator instance (for testing).
        human_review_service: Optional HumanReviewService instance (for testing).
        document_service: Optional DocumentService instance (for testing).
        bounding_box_service: Optional BoundingBoxService instance (for testing).
        job_tracker: Optional JobTrackingService instance (for testing).

    Returns:
        Task result with validation summary.

    Raises:
        GeminiValidatorError: If Gemini validation fails (will trigger retry).
        ValidationExtractorError: If extraction fails (will trigger retry).
    """
    # Get document_id and job_id from prev_result or parameter
    doc_id = document_id
    job_id: str | None = None
    matter_id: str | None = None

    if prev_result:
        if doc_id is None:
            doc_id = prev_result.get("document_id")  # type: ignore[assignment]
        job_id = prev_result.get("job_id")  # type: ignore[assignment]

    # If job_id not in prev_result, look it up from database
    if job_id is None and doc_id:
        job_id = _lookup_job_id_for_document(doc_id)

    if not doc_id:
        logger.error("validate_ocr_no_document_id")
        return {
            "status": "validation_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Check if OCR was successful
    if prev_result and prev_result.get("status") != "ocr_complete":
        logger.info(
            "validate_ocr_skipped_ocr_not_complete",
            document_id=doc_id,
            ocr_status=prev_result.get("status"),
        )
        return {
            "status": "validation_skipped",
            "document_id": doc_id,
            "reason": "OCR not complete",
            "job_id": job_id,
        }

    # Use injected services or get defaults
    extractor = validation_extractor or get_validation_extractor()
    gemini = gemini_validator or get_gemini_validator()
    human_review = human_review_service or get_human_review_service()
    doc_service = document_service or get_document_service()
    bbox_service = bounding_box_service or get_bounding_box_service()

    logger.info(
        "validate_ocr_task_started",
        document_id=doc_id,
        retry_count=self.request.retries,
    )

    try:
        # Get matter_id for the document
        _, matter_id = doc_service.get_document_for_processing(doc_id)

        # Track validation stage start (Story 2c-3)
        _update_job_stage_start(job_id, "validation", matter_id)

        # Step 1: Extract low-confidence words
        words_for_gemini, words_for_human = extractor.extract_low_confidence_words(doc_id)

        total_low_confidence = len(words_for_gemini) + len(words_for_human)

        if total_low_confidence == 0:
            # No validation needed - update status and return
            _update_validation_status(doc_service, doc_id, ValidationStatus.VALIDATED)
            # Mark validation stage complete immediately
            _update_job_stage_complete(job_id, "validation", matter_id)
            logger.info(
                "validate_ocr_no_low_confidence_words",
                document_id=doc_id,
            )
            return {
                "status": "validated",
                "document_id": doc_id,
                "validation_status": "validated",
                "total_validated": 0,
                "pattern_corrections": 0,
                "gemini_corrections": 0,
                "human_review_queued": 0,
                "job_id": job_id,
            }

        # Step 2: Apply pattern corrections first
        pattern_results, remaining_for_gemini = apply_pattern_corrections(words_for_gemini)

        # Step 3: Validate remaining words with Gemini
        gemini_results = []
        if remaining_for_gemini:
            try:
                gemini_results = gemini.validate_batch_sync(remaining_for_gemini)
            except GeminiValidatorError as e:
                logger.warning(
                    "validate_ocr_gemini_failed",
                    document_id=doc_id,
                    error=str(e),
                )
                # Continue with pattern results only if Gemini fails
                # but re-raise if retryable
                if e.is_retryable:
                    raise

        # Step 4: Queue very low confidence words for human review
        human_review_count = 0
        if words_for_human:
            human_review_count = human_review.add_to_queue(
                document_id=doc_id,
                matter_id=matter_id,
                words=words_for_human,
            )

        # Step 5: Apply corrections to bounding boxes and log
        all_results = pattern_results + gemini_results
        corrections_applied = _apply_validation_results(
            bbox_service=bbox_service,
            doc_service=doc_service,
            document_id=doc_id,
            results=all_results,
        )

        # Step 6: Update document validation status
        final_status = ValidationStatus.VALIDATED
        if human_review_count > 0:
            final_status = ValidationStatus.REQUIRES_HUMAN_REVIEW

        _update_validation_status(doc_service, doc_id, final_status)

        # Count corrections by type
        pattern_count = sum(
            1 for r in all_results
            if r.was_corrected and r.correction_type == CorrectionType.PATTERN
        )
        gemini_count = sum(
            1 for r in all_results
            if r.was_corrected and r.correction_type == CorrectionType.GEMINI
        )

        logger.info(
            "validate_ocr_task_completed",
            document_id=doc_id,
            total_validated=len(all_results),
            pattern_corrections=pattern_count,
            gemini_corrections=gemini_count,
            human_review_queued=human_review_count,
            validation_status=final_status.value,
        )

        # Track validation stage completion (Story 2c-3)
        _update_job_stage_complete(
            job_id,
            "validation",
            matter_id,
            metadata={
                "total_validated": len(all_results),
                "pattern_corrections": pattern_count,
                "gemini_corrections": gemini_count,
            },
        )

        # Broadcast validation status
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="validation_complete",
            validation_status=final_status.value,
        )

        return {
            "status": "validated",
            "document_id": doc_id,
            "validation_status": final_status.value,
            "total_validated": len(all_results),
            "pattern_corrections": pattern_count,
            "gemini_corrections": gemini_count,
            "human_review_queued": human_review_count,
            "corrections_applied": corrections_applied,
            "job_id": job_id,
        }

    except (GeminiValidatorError, ValidationExtractorError) as e:
        retry_count = self.request.retries
        error_code = getattr(e, "code", "UNKNOWN")

        logger.warning(
            "validate_ocr_task_retry",
            document_id=doc_id,
            retry_count=retry_count,
            max_retries=MAX_RETRIES,
            error=str(e),
            error_code=error_code,
        )

        # Track stage failure
        _update_job_stage_failure(job_id, "validation", str(e), error_code, matter_id)

        if retry_count >= MAX_RETRIES:
            _mark_job_failed(job_id, str(e), error_code, matter_id)
            return _handle_validation_failure(doc_service, doc_id, e)

        raise

    except HumanReviewServiceError as e:
        # Human review errors are not critical - log and continue
        logger.warning(
            "validate_ocr_human_review_failed",
            document_id=doc_id,
            error=str(e),
        )
        # Track stage complete despite warning
        _update_job_stage_complete(job_id, "validation", matter_id)
        # Don't fail the whole task for human review issues
        return {
            "status": "validated_with_warnings",
            "document_id": doc_id,
            "warning": "Human review queue failed",
            "error_message": str(e),
            "job_id": job_id,
        }

    except DocumentServiceError as e:
        logger.error(
            "validate_ocr_document_service_error",
            document_id=doc_id,
            error=str(e),
        )
        _mark_job_failed(job_id, e.message, e.code, matter_id)
        return _handle_validation_failure(doc_service, doc_id, e)

    except Exception as e:
        logger.error(
            "validate_ocr_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", matter_id)
        return _handle_validation_failure(doc_service, doc_id, e)


def _apply_validation_results(
    bbox_service: BoundingBoxService,
    doc_service: DocumentService,
    document_id: str,
    results: list,
) -> int:
    """Apply validation results to bounding boxes and log corrections.

    Args:
        bbox_service: BoundingBoxService instance.
        doc_service: DocumentService instance.
        document_id: Document UUID.
        results: List of ValidationResult.

    Returns:
        Number of corrections applied.
    """
    from app.services.supabase.client import get_service_client

    client = get_service_client()
    if client is None:
        return 0

    corrections_applied = 0

    for result in results:
        if not result.was_corrected:
            continue

        try:
            # Update bounding box with corrected text
            if result.bbox_id:
                client.table("bounding_boxes").update({
                    "text": result.corrected,
                    "confidence": result.new_confidence,
                }).eq("id", result.bbox_id).execute()

            # Log the correction
            client.table("ocr_validation_log").insert({
                "document_id": document_id,
                "bbox_id": result.bbox_id if result.bbox_id else None,
                "original_text": result.original,
                "corrected_text": result.corrected,
                "old_confidence": result.old_confidence,
                "new_confidence": result.new_confidence,
                "validation_type": result.correction_type.value if result.correction_type else "pattern",
                "reasoning": result.reasoning,
            }).execute()

            corrections_applied += 1

        except Exception as e:
            logger.warning(
                "validate_ocr_apply_result_failed",
                document_id=document_id,
                bbox_id=result.bbox_id,
                error=str(e),
            )

    return corrections_applied


def _update_validation_status(
    doc_service: DocumentService,
    document_id: str,
    status: ValidationStatus,
) -> None:
    """Update document validation status.

    Args:
        doc_service: DocumentService instance.
        document_id: Document UUID.
        status: New validation status.
    """
    from app.services.supabase.client import get_service_client

    client = get_service_client()
    if client is None:
        return

    try:
        client.table("documents").update({
            "validation_status": status.value,
        }).eq("id", document_id).execute()
    except Exception as e:
        logger.warning(
            "validate_ocr_status_update_failed",
            document_id=document_id,
            status=status.value,
            error=str(e),
        )


def _handle_validation_failure(
    doc_service: DocumentService,
    document_id: str,
    error: Exception,
) -> dict[str, str]:
    """Handle validation task failure.

    Args:
        doc_service: DocumentService instance.
        document_id: Document UUID.
        error: The error that caused the failure.

    Returns:
        Task result indicating failure.
    """
    error_code = getattr(error, "code", "VALIDATION_FAILED")
    error_message = str(error)

    logger.error(
        "validate_ocr_task_failed",
        document_id=document_id,
        error=error_message,
        error_code=error_code,
    )

    # Update status to indicate validation is pending (not failed OCR)
    # The document OCR is still valid, just validation couldn't complete
    _update_validation_status(
        doc_service,
        document_id,
        ValidationStatus.PENDING,
    )

    return {
        "status": "validation_failed",
        "document_id": document_id,
        "error_code": error_code,
        "error_message": error_message,
    }


@celery_app.task(
    name="app.workers.tasks.document_tasks.calculate_confidence",
    bind=True,
    autoretry_for=(ConfidenceCalculatorError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
)  # type: ignore[misc]
def calculate_confidence(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
) -> dict[str, str | int | float | None]:
    """Calculate and store OCR confidence metrics for a document.

    This task runs after validate_ocr to calculate overall and per-page
    confidence metrics, determine quality status, and update the document.

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).

    Returns:
        Task result with confidence metrics.

    Raises:
        ConfidenceCalculatorError: If calculation fails (will trigger retry).
    """
    # Get document_id and job_id from prev_result or parameter
    doc_id = document_id
    job_id: str | None = None
    if prev_result:
        if doc_id is None:
            doc_id = prev_result.get("document_id")  # type: ignore[assignment]
        job_id = prev_result.get("job_id")  # type: ignore[assignment]

    # If job_id not in prev_result, look it up from database
    if job_id is None and doc_id:
        job_id = _lookup_job_id_for_document(doc_id)

    if not doc_id:
        logger.error("calculate_confidence_no_document_id")
        return {
            "status": "confidence_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
            "job_id": job_id,
        }

    # Skip if OCR/validation wasn't successful
    if prev_result:
        prev_status = prev_result.get("status")
        if prev_status not in ("validated", "validated_with_warnings", "validation_skipped"):
            logger.info(
                "calculate_confidence_skipped",
                document_id=doc_id,
                prev_status=prev_status,
            )
            return {
                "status": "confidence_skipped",
                "document_id": doc_id,
                "job_id": job_id,
                "reason": f"Previous task status: {prev_status}",
            }

    doc_service = document_service or get_document_service()

    logger.info(
        "calculate_confidence_task_started",
        document_id=doc_id,
        job_id=job_id,
        retry_count=self.request.retries,
    )

    try:
        # Get matter_id for broadcasting
        _, matter_id = doc_service.get_document_for_processing(doc_id)

        # Record stage start for job tracking (Story 2c-3)
        _update_job_stage_start(job_id, "confidence", matter_id)

        # Calculate and update confidence metrics
        result = update_document_confidence(doc_id)

        # Record stage completion for job tracking (Story 2c-3)
        _update_job_stage_complete(job_id, "confidence", matter_id)

        logger.info(
            "calculate_confidence_task_completed",
            document_id=doc_id,
            job_id=job_id,
            overall_confidence=result.overall_confidence,
            quality_status=result.quality_status,
            total_words=result.total_words,
            page_count=len(result.page_confidences),
        )

        # Broadcast confidence update
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="confidence_calculated",
            ocr_confidence=result.overall_confidence,
            quality_status=result.quality_status,
        )

        return {
            "status": "confidence_calculated",
            "document_id": doc_id,
            "job_id": job_id,
            "overall_confidence": result.overall_confidence,
            "quality_status": result.quality_status,
            "total_words": result.total_words,
            "page_count": len(result.page_confidences),
        }

    except ConfidenceCalculatorError as e:
        retry_count = self.request.retries
        error_code = "CONFIDENCE_CALCULATION_FAILED"

        logger.warning(
            "calculate_confidence_task_retry",
            document_id=doc_id,
            job_id=job_id,
            retry_count=retry_count,
            max_retries=2,
            error=str(e),
        )

        # Record stage failure for job tracking (Story 2c-3)
        _update_job_stage_failure(job_id, "confidence", str(e), error_code, matter_id)

        if retry_count >= 2:
            logger.error(
                "calculate_confidence_task_failed",
                document_id=doc_id,
                job_id=job_id,
                error=str(e),
            )
            _mark_job_failed(job_id, str(e), error_code, matter_id)
            return {
                "status": "confidence_failed",
                "document_id": doc_id,
                "job_id": job_id,
                "error_code": error_code,
                "error_message": str(e),
            }

        raise

    except DocumentServiceError as e:
        logger.error(
            "calculate_confidence_document_error",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
        )
        _update_job_stage_failure(job_id, "confidence", str(e), e.code, None)
        _mark_job_failed(job_id, e.message, e.code, None)
        return {
            "status": "confidence_failed",
            "document_id": doc_id,
            "job_id": job_id,
            "error_code": e.code,
            "error_message": e.message,
        }

    except Exception as e:
        logger.error(
            "calculate_confidence_unexpected_error",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        _update_job_stage_failure(job_id, "confidence", str(e), "UNEXPECTED_ERROR", None)
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", None)
        return {
            "status": "confidence_failed",
            "document_id": doc_id,
            "job_id": job_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
        }


@celery_app.task(
    name="app.workers.tasks.document_tasks.chunk_document",
    bind=True,
    autoretry_for=(ChunkServiceError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
)  # type: ignore[misc]
def chunk_document(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
    chunk_service: ChunkService | None = None,
    bounding_box_service: BoundingBoxService | None = None,
    force: bool = False,
    skip_bbox_linking: bool = False,
) -> dict[str, str | int | float | None]:
    """Chunk a document into parent-child hierarchy for RAG.

    This task runs after confidence calculation to create document chunks.
    Parent chunks (1500-2000 tokens) provide context, while child chunks
    (400-700 tokens) enable precise retrieval.

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).
        chunk_service: Optional ChunkService instance (for testing).
        bounding_box_service: Optional BoundingBoxService instance (for testing).
        force: If True, skip status validation and run regardless of prev_result.
        skip_bbox_linking: If True, skip bbox linking (saves chunks faster,
            bbox highlighting can be done later via link_chunks_to_bboxes_task).

    Returns:
        Task result with chunking summary.

    Raises:
        ChunkServiceError: If chunking fails (will trigger retry).
    """
    # Get document_id and job_id from prev_result or parameter
    doc_id = document_id
    job_id: str | None = None
    if prev_result:
        if doc_id is None:
            doc_id = prev_result.get("document_id")  # type: ignore[assignment]
        job_id = prev_result.get("job_id")  # type: ignore[assignment]

    # If job_id not in prev_result, look it up from database
    if job_id is None and doc_id:
        job_id = _lookup_job_id_for_document(doc_id)

    if not doc_id:
        logger.error("chunk_document_no_document_id")
        return {
            "status": "chunking_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
            "job_id": job_id,
        }

    # Log force mode usage for audit trail
    if force:
        logger.info(
            "chunk_document_force_mode",
            document_id=doc_id,
            job_id=job_id,
            reason="Bypassing status validation",
        )

    # Skip if previous task explicitly failed (unless force=True)
    if prev_result and not force:
        prev_status = prev_result.get("status")
        # Expanded valid statuses - allow chunking after OCR complete
        # (most common case for parallel pipeline)
        valid_statuses = (
            "confidence_calculated",
            "confidence_skipped",
            "validated",
            "validated_with_warnings",
            "validation_skipped",
            "ocr_complete",  # Most common status after OCR
        )
        # Only skip on explicit failure statuses
        failed_statuses = (
            "failed",
            "error",
            "ocr_failed",
            "validation_failed",
        )
        if prev_status in failed_statuses:
            logger.info(
                "chunk_document_skipped",
                document_id=doc_id,
                prev_status=prev_status,
                reason="Previous task failed",
            )
            return {
                "status": "chunking_skipped",
                "document_id": doc_id,
                "job_id": job_id,
                "reason": f"Previous task failed with status: {prev_status}",
            }
        # Log if running with unexpected status (but proceed anyway)
        if prev_status and prev_status not in valid_statuses:
            logger.warning(
                "chunk_document_unexpected_status",
                document_id=doc_id,
                prev_status=prev_status,
                action="proceeding_anyway",
            )

    # Use injected services or get defaults
    doc_service = document_service or get_document_service()
    chunks_service = chunk_service or get_chunk_service()
    bbox_service = bounding_box_service or get_bounding_box_service()

    logger.info(
        "chunk_document_task_started",
        document_id=doc_id,
        job_id=job_id,
        retry_count=self.request.retries,
    )

    try:
        # Get document info including extracted text
        storage_path, matter_id = doc_service.get_document_for_processing(doc_id)
        doc = doc_service.get_document(doc_id)

        if not doc.extracted_text:
            logger.warning(
                "chunk_document_no_text",
                document_id=doc_id,
                job_id=job_id,
            )
            return {
                "status": "chunking_skipped",
                "document_id": doc_id,
                "job_id": job_id,
                "reason": "No extracted text available",
            }

        # IDEMPOTENCY CHECK: Skip if chunking was already completed successfully
        # We verify completion by checking if BOTH parent AND child chunks exist.
        # Partial failure would typically have only parents (children created after)
        # or be empty. If only one type exists, we re-chunk from scratch.
        async def _check_chunking_complete() -> tuple[bool, int, int]:
            """Check if chunking is complete (not partial).

            Returns:
                Tuple of (is_complete, parent_count, child_count)
            """
            parent_count = await chunks_service.count_chunks_for_document(
                doc_id, chunk_type="parent"
            )
            child_count = await chunks_service.count_chunks_for_document(
                doc_id, chunk_type="child"
            )

            # Chunking is complete if we have BOTH parent and child chunks
            is_complete = parent_count > 0 and child_count > 0

            return is_complete, parent_count, child_count

        is_chunking_complete, parent_count, child_count = asyncio.run(
            _check_chunking_complete()
        )

        if is_chunking_complete and not force:
            logger.info(
                "chunk_document_already_complete",
                document_id=doc_id,
                job_id=job_id,
                parent_chunks=parent_count,
                child_chunks=child_count,
                action="skipping_rechunk",
            )
            # Mark stage complete and return success
            _update_job_stage_complete(job_id, "chunking", matter_id)
            broadcast_document_status(
                matter_id=matter_id,
                document_id=doc_id,
                status="chunking_complete",
                parent_chunks=parent_count,
                child_chunks=child_count,
                note="Chunks already existed (idempotent skip)",
            )
            return {
                "status": "chunking_complete",
                "document_id": doc_id,
                "job_id": job_id,
                "parent_chunks": parent_count,
                "child_chunks": child_count,
                "note": "Chunking already complete, skipped re-chunking",
            }
        elif parent_count > 0 or child_count > 0:
            # Partial chunks exist - log warning, proceed to re-chunk
            # (save_chunks will delete existing chunks first)
            logger.warning(
                "chunk_document_partial_detected",
                document_id=doc_id,
                job_id=job_id,
                parent_chunks=parent_count,
                child_chunks=child_count,
                action="will_delete_and_rechunk",
            )

        # Record stage start for job tracking (Story 2c-3)
        _update_job_stage_start(job_id, "chunking", matter_id)

        # Create chunker and process document
        chunker = ParentChildChunker()
        result = chunker.chunk_document(doc_id, doc.extracted_text)

        # Prepare all chunks for saving
        all_chunks = result.parent_chunks + result.child_chunks

        # Run async operations in sync context
        async def _save_chunks_async():
            # Link chunks to bounding boxes (can be slow for large documents)
            # Skip if requested - bbox linking can be done later via background task
            if not skip_bbox_linking:
                await link_chunks_to_bboxes(all_chunks, doc_id, bbox_service)
            else:
                logger.info(
                    "chunk_document_bbox_linking_skipped",
                    document_id=doc_id,
                    chunk_count=len(all_chunks),
                    reason="skip_bbox_linking=True",
                )

            return await chunks_service.save_chunks(
                document_id=doc_id,
                matter_id=matter_id,
                parent_chunks=result.parent_chunks,
                child_chunks=result.child_chunks,
            )

        saved_count = asyncio.run(_save_chunks_async())

        # Record stage completion for job tracking (Story 2c-3)
        _update_job_stage_complete(job_id, "chunking", matter_id)

        # Broadcast chunking completion
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="chunking_complete",
            parent_chunks=len(result.parent_chunks),
            child_chunks=len(result.child_chunks),
        )

        # Story 7.1: Broadcast search feature availability
        broadcast_feature_ready(
            matter_id=matter_id,
            document_id=doc_id,
            feature=FeatureType.SEARCH,
            metadata={"chunk_count": saved_count},
        )

        logger.info(
            "chunk_document_task_completed",
            document_id=doc_id,
            job_id=job_id,
            parent_chunks=len(result.parent_chunks),
            child_chunks=len(result.child_chunks),
            total_tokens=result.total_tokens,
            saved_count=saved_count,
        )

        return {
            "status": "chunking_complete",
            "document_id": doc_id,
            "job_id": job_id,
            "parent_chunks": len(result.parent_chunks),
            "child_chunks": len(result.child_chunks),
            "total_tokens": result.total_tokens,
            "saved_count": saved_count,
        }

    except ChunkServiceError as e:
        retry_count = self.request.retries
        error_code = "CHUNKING_FAILED"

        logger.warning(
            "chunk_document_task_retry",
            document_id=doc_id,
            job_id=job_id,
            retry_count=retry_count,
            max_retries=2,
            error=str(e),
        )

        # Record stage failure for job tracking (Story 2c-3)
        _update_job_stage_failure(job_id, "chunking", str(e), error_code, matter_id)

        if retry_count >= 2:
            logger.error(
                "chunk_document_task_failed",
                document_id=doc_id,
                job_id=job_id,
                error=str(e),
            )
            _mark_job_failed(job_id, str(e), error_code, matter_id)
            return {
                "status": "chunking_failed",
                "document_id": doc_id,
                "job_id": job_id,
                "error_code": error_code,
                "error_message": str(e),
            }

        raise

    except DocumentServiceError as e:
        logger.error(
            "chunk_document_document_error",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
        )
        _update_job_stage_failure(job_id, "chunking", str(e), e.code, None)
        _mark_job_failed(job_id, e.message, e.code, None)
        return {
            "status": "chunking_failed",
            "document_id": doc_id,
            "job_id": job_id,
            "error_code": e.code,
            "error_message": e.message,
        }

    except Exception as e:
        logger.error(
            "chunk_document_unexpected_error",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        _update_job_stage_failure(job_id, "chunking", str(e), "UNEXPECTED_ERROR", None)
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", None)
        return {
            "status": "chunking_failed",
            "document_id": doc_id,
            "job_id": job_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
        }


# =============================================================================
# Bbox Linking Task (Decoupled from Chunking)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.document_tasks.link_chunks_to_bboxes_task",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
)  # type: ignore[misc]
def link_chunks_to_bboxes_task(
    self,  # type: ignore[no-untyped-def]
    document_id: str,
    chunk_service: ChunkService | None = None,
    bounding_box_service: BoundingBoxService | None = None,
) -> dict[str, str | int | float | None]:
    """Link existing chunks to bounding boxes for a document.

    This task can be run independently after chunking to enable bbox
    highlighting in the UI. It's useful when chunk_document was called
    with skip_bbox_linking=True for faster initial processing.

    Args:
        document_id: Document UUID.
        chunk_service: Optional ChunkService instance (for testing).
        bounding_box_service: Optional BoundingBoxService instance (for testing).

    Returns:
        Task result with linking summary.
    """
    logger.info(
        "link_chunks_to_bboxes_task_started",
        document_id=document_id,
        retry_count=self.request.retries,
    )

    # Use injected services or get defaults
    chunks_service = chunk_service or get_chunk_service()
    bbox_service = bounding_box_service or get_bounding_box_service()

    try:
        # Get all chunks for this document (parent + child)
        async def _get_and_link_chunks():
            from app.services.supabase.client import get_service_client

            client = get_service_client()

            # Get all chunks for this document
            result = (
                client.table("chunks")
                .select("id, content, char_start, char_end, parent_id, document_id")
                .eq("document_id", document_id)
                .execute()
            )

            if not result.data:
                return 0

            # Convert to chunk-like objects for link_chunks_to_bboxes
            from dataclasses import dataclass

            @dataclass
            class ChunkData:
                id: str
                content: str
                char_start: int
                char_end: int
                parent_id: str | None

            chunks = [
                ChunkData(
                    id=row["id"],
                    content=row["content"],
                    char_start=row["char_start"],
                    char_end=row["char_end"],
                    parent_id=row.get("parent_id"),
                )
                for row in result.data
            ]

            # Link chunks to bounding boxes
            await link_chunks_to_bboxes(chunks, document_id, bbox_service)

            # Get matter_id for feature broadcast
            doc_result = (
                client.table("documents")
                .select("matter_id")
                .eq("id", document_id)
                .limit(1)
                .execute()
            )
            matter_id = doc_result.data[0]["matter_id"] if doc_result.data else None

            return len(chunks), matter_id

        linked_count, matter_id = asyncio.run(_get_and_link_chunks())

        logger.info(
            "link_chunks_to_bboxes_task_completed",
            document_id=document_id,
            linked_count=linked_count,
        )

        # Story 7.1: Broadcast bbox highlighting feature availability
        if matter_id:
            broadcast_feature_ready(
                matter_id=matter_id,
                document_id=document_id,
                feature=FeatureType.BBOX_HIGHLIGHTING,
                metadata={"linked_count": linked_count},
            )

        return {
            "status": "bbox_linking_complete",
            "document_id": document_id,
            "linked_count": linked_count,
        }

    except Exception as e:
        retry_count = self.request.retries

        logger.warning(
            "link_chunks_to_bboxes_task_error",
            document_id=document_id,
            retry_count=retry_count,
            error=str(e),
            error_type=type(e).__name__,
        )

        if retry_count >= 2:
            logger.error(
                "link_chunks_to_bboxes_task_failed",
                document_id=document_id,
                error=str(e),
            )
            return {
                "status": "bbox_linking_failed",
                "document_id": document_id,
                "error_code": "BBOX_LINKING_FAILED",
                "error_message": str(e),
            }

        raise


# =============================================================================
# Embedding Population Constants
# =============================================================================

EMBEDDING_BATCH_SIZE = 50  # Chunks per OpenAI API call
EMBEDDING_RATE_LIMIT_DELAY = 0.5  # Seconds between batches to respect rate limits


@celery_app.task(
    name="app.workers.tasks.document_tasks.embed_chunks",
    bind=True,
    autoretry_for=(EmbeddingServiceError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
)  # type: ignore[misc]
def embed_chunks(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
    embedding_service: EmbeddingService | None = None,
    force: bool = False,
) -> dict[str, str | int | float | None]:
    """Generate embeddings for document chunks.

    This task runs after chunk_document to populate embeddings for
    semantic search. Processes chunks in batches of 50 to respect
    OpenAI API rate limits.

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).
        embedding_service: Optional EmbeddingService instance (for testing).
        force: If True, skip status validation and run regardless of prev_result.

    Returns:
        Task result with embedding summary.

    Raises:
        EmbeddingServiceError: If embedding generation fails (will trigger retry).
    """

    from app.services.supabase.client import get_service_client

    # Get document_id from prev_result or parameter
    doc_id = document_id
    if doc_id is None and prev_result:
        doc_id = prev_result.get("document_id")  # type: ignore[assignment]

    if not doc_id:
        logger.error("embed_chunks_no_document_id")
        return {
            "status": "embedding_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Log force mode usage for audit trail
    if force:
        logger.info(
            "embed_chunks_force_mode",
            document_id=doc_id,
            reason="Bypassing status validation",
        )

    # Skip if previous task explicitly failed (unless force=True)
    if prev_result and not force:
        prev_status = prev_result.get("status")
        # Expanded valid statuses - allow embedding after chunking
        # or searchable (for re-embedding)
        valid_statuses = (
            "chunking_complete",
            "searchable",
            "ocr_complete",  # Allow if chunks exist
        )
        # Only skip on explicit failure statuses
        failed_statuses = (
            "failed",
            "error",
            "ocr_failed",
            "chunking_failed",
            "chunking_skipped",
        )
        if prev_status in failed_statuses:
            logger.info(
                "embed_chunks_skipped",
                document_id=doc_id,
                prev_status=prev_status,
                reason="Previous task failed",
            )
            return {
                "status": "embedding_skipped",
                "document_id": doc_id,
                "reason": f"Previous task failed with status: {prev_status}",
            }
        # Log if running with unexpected status (but proceed anyway)
        if prev_status and prev_status not in valid_statuses:
            logger.warning(
                "embed_chunks_unexpected_status",
                document_id=doc_id,
                prev_status=prev_status,
                action="proceeding_anyway",
            )

    # Use injected services or get defaults
    doc_service = document_service or get_document_service()
    embedder = embedding_service or get_embedding_service()

    logger.info(
        "embed_chunks_task_started",
        document_id=doc_id,
        retry_count=self.request.retries,
    )

    try:
        # Get matter_id for broadcasting
        _, matter_id = doc_service.get_document_for_processing(doc_id)

        # Get service client to query and update chunks
        client = get_service_client()
        if client is None:
            raise EmbeddingServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
                is_retryable=False,
            )

        # Get job_id for partial progress tracking
        # First try prev_result, then lookup from database
        job_id: str | None = None
        if prev_result:
            job_id = prev_result.get("job_id")  # type: ignore[assignment]
        if job_id is None:
            job_id = _lookup_job_id_for_document(doc_id)

        # IDEMPOTENCY CHECK: Skip if embedding is already complete
        is_embedding_complete, total_chunks, embedded_chunks = _check_embedding_complete(doc_id)
        if is_embedding_complete and not force:
            logger.info(
                "embed_chunks_idempotency_skip",
                document_id=doc_id,
                total_chunks=total_chunks,
                embedded_chunks=embedded_chunks,
                reason="All chunks already have embeddings",
            )
            # Update job stage to mark embedding complete
            _update_job_stage_complete(job_id, "embedding", matter_id)
            return {
                "status": "embedding_complete",
                "document_id": doc_id,
                "embedded_count": embedded_chunks,
                "reason": "Idempotency check: all chunks already embedded",
                "job_id": job_id,
            }

        # Get chunks without embeddings for this document
        response = (
            client.table("chunks")
            .select("id, content")
            .eq("document_id", doc_id)
            .is_("embedding", "null")
            .order("chunk_index", desc=False)
            .execute()
        )

        chunks = response.data or []

        if not chunks:
            logger.info(
                "embed_chunks_no_chunks_to_embed",
                document_id=doc_id,
            )
            return {
                "status": "embedding_complete",
                "document_id": doc_id,
                "embedded_count": 0,
                "reason": "No chunks without embeddings",
                "job_id": job_id,
            }

        # Initialize partial progress tracker (Story 2c-3)
        progress_tracker = create_progress_tracker(job_id, matter_id)
        stage_progress = None
        if progress_tracker:
            stage_progress = progress_tracker.get_or_create_stage("embedding")
            stage_progress.total_items = len(chunks)

        # Get already-processed chunk IDs from previous run (for retry)
        already_processed: set[str] = set()
        if stage_progress:
            already_processed = stage_progress.processed_items

        logger.info(
            "embed_chunks_processing",
            document_id=doc_id,
            chunk_count=len(chunks),
            already_processed=len(already_processed),
            batch_size=EMBEDDING_BATCH_SIZE,
        )

        # Process chunks in batches
        embedded_count = 0
        failed_count = 0
        skipped_count = 0

        # Process all batches in a single async context
        async def _embed_all_batches():
            nonlocal embedded_count, failed_count, skipped_count

            for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
                batch = chunks[i : i + EMBEDDING_BATCH_SIZE]

                # Filter out already-processed chunks (partial progress)
                chunks_to_process = [
                    c for c in batch
                    if c["id"] not in already_processed
                ]

                if not chunks_to_process:
                    skipped_count += len(batch)
                    continue

                batch_texts = [c["content"] for c in chunks_to_process]
                batch_ids = [c["id"] for c in chunks_to_process]

                try:
                    # Generate embeddings for batch
                    embeddings = await embedder.embed_batch(batch_texts, skip_empty=True)

                    # Update chunks with embeddings
                    for _j, (chunk_id, embedding) in enumerate(zip(batch_ids, embeddings, strict=False)):
                        if embedding is None:
                            failed_count += 1
                            if stage_progress:
                                stage_progress.mark_failed(chunk_id, "Empty embedding")
                            continue

                        try:
                            client.table("chunks").update({
                                "embedding": embedding,
                            }).eq("id", chunk_id).execute()
                            embedded_count += 1

                            # Track partial progress
                            if stage_progress:
                                stage_progress.mark_processed(chunk_id)

                        except Exception as e:
                            logger.warning(
                                "embed_chunks_update_failed",
                                document_id=doc_id,
                                chunk_id=chunk_id,
                                error=str(e),
                            )
                            failed_count += 1
                            if stage_progress:
                                stage_progress.mark_failed(chunk_id, str(e))

                    # Persist partial progress periodically
                    if progress_tracker and stage_progress:
                        progress_tracker.save_progress(stage_progress)

                    logger.debug(
                        "embed_chunks_batch_complete",
                        document_id=doc_id,
                        batch_number=i // EMBEDDING_BATCH_SIZE + 1,
                        batch_embedded=len([e for e in embeddings if e is not None]),
                    )

                    # Rate limit delay between batches
                    if i + EMBEDDING_BATCH_SIZE < len(chunks):
                        await asyncio.sleep(EMBEDDING_RATE_LIMIT_DELAY)

                except EmbeddingServiceError as e:
                    logger.warning(
                        "embed_chunks_batch_failed",
                        document_id=doc_id,
                        batch_start=i,
                        error=str(e),
                    )
                    failed_count += len(chunks_to_process)

                    # Save progress before retry
                    if progress_tracker and stage_progress:
                        progress_tracker.save_progress(stage_progress, force=True)

                    if e.is_retryable:
                        raise  # Let Celery retry

        try:
            asyncio.run(_embed_all_batches())
        finally:
            # Save final progress
            if progress_tracker and stage_progress:
                progress_tracker.save_progress(stage_progress, force=True)

        # Update document status to searchable
        try:
            client.table("documents").update({
                "status": "searchable",
            }).eq("id", doc_id).execute()

            logger.info(
                "document_status_updated_to_searchable",
                document_id=doc_id,
            )
        except Exception as e:
            logger.warning(
                "embed_chunks_status_update_failed",
                document_id=doc_id,
                error=str(e),
            )

        # Broadcast embedding completion
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="searchable",
            embedded_count=embedded_count,
            failed_count=failed_count,
        )

        # Story 7.1: Broadcast semantic search feature availability
        broadcast_feature_ready(
            matter_id=matter_id,
            document_id=doc_id,
            feature=FeatureType.SEMANTIC_SEARCH,
            metadata={"embedded_count": embedded_count},
        )

        logger.info(
            "embed_chunks_task_completed",
            document_id=doc_id,
            embedded_count=embedded_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            total_chunks=len(chunks),
        )

        # Dispatch downstream tasks based on document type
        # - Act documents: index sections for split-view navigation
        # - Case files: extract citations with source bbox_ids
        try:
            from app.workers.celery import celery_app

            doc_type_result = (
                client.table("documents")
                .select("document_type")
                .eq("id", doc_id)
                .single()
                .execute()
            )
            document_type = doc_type_result.data.get("document_type") if doc_type_result.data else None

            if document_type == "act":
                # Index sections for accurate split-view navigation
                celery_app.send_task(
                    "app.workers.tasks.document_tasks.index_act_sections",
                    kwargs={
                        "prev_result": {
                            "document_id": doc_id,
                            "status": "searchable",
                            "job_id": job_id,
                        },
                        "document_id": doc_id,
                    },
                )
                logger.info(
                    "index_act_sections_dispatched",
                    document_id=doc_id,
                    document_type=document_type,
                )
            else:
                # Extract citations after chunks with bbox_ids are ready
                celery_app.send_task(
                    "app.workers.tasks.document_tasks.extract_citations",
                    kwargs={
                        "prev_result": {
                            "document_id": doc_id,
                            "status": "searchable",
                            "job_id": job_id,
                        },
                        "document_id": doc_id,
                    },
                )
                logger.info(
                    "extract_citations_dispatched_after_embedding",
                    document_id=doc_id,
                    document_type=document_type,
                )
        except Exception as e:
            # Non-fatal: downstream tasks can be triggered manually or via backfill
            logger.warning(
                "downstream_task_dispatch_failed",
                document_id=doc_id,
                error=str(e),
            )

        return {
            "status": "searchable",
            "document_id": doc_id,
            "embedded_count": embedded_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "total_chunks": len(chunks),
            "job_id": job_id,
        }

    except EmbeddingServiceError as e:
        retry_count = self.request.retries

        logger.warning(
            "embed_chunks_task_retry",
            document_id=doc_id,
            retry_count=retry_count,
            max_retries=3,
            error=str(e),
        )

        if retry_count >= 3:
            logger.error(
                "embed_chunks_task_failed",
                document_id=doc_id,
                error=str(e),
            )
            return {
                "status": "embedding_failed",
                "document_id": doc_id,
                "error_code": e.code,
                "error_message": e.message,
            }

        raise

    except DocumentServiceError as e:
        logger.error(
            "embed_chunks_document_error",
            document_id=doc_id,
            error=str(e),
        )
        return {
            "status": "embedding_failed",
            "document_id": doc_id,
            "error_code": e.code,
            "error_message": e.message,
        }

    except Exception as e:
        logger.error(
            "embed_chunks_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "status": "embedding_failed",
            "document_id": doc_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
        }


# =============================================================================
# Section Indexing Task (for Act documents)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.document_tasks.index_act_sections",
    bind=True,
    max_retries=2,
    retry_backoff=True,
)  # type: ignore[misc]
def index_act_sections(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    force: bool = False,
) -> dict[str, str | int | float | None]:
    """Index sections in Act documents for fast section lookups.

    This task runs after chunking for Act documents to pre-compute
    section -> page mappings, enabling O(1) lookups in split-view.

    Pipeline: OCR -> Chunk -> **Index Sections** (Acts only)

    Args:
        prev_result: Result from previous task in chain.
        document_id: Document UUID.
        force: If True, re-index even if already indexed.

    Returns:
        Task result with indexing summary.
    """
    from app.services.section_index_service import (
        SectionIndexService,
        get_section_index_service,
    )
    from app.services.supabase.client import get_service_client

    # Get document_id from prev_result or parameter
    doc_id = document_id
    if doc_id is None and prev_result:
        doc_id = prev_result.get("document_id")  # type: ignore[assignment]

    if not doc_id:
        logger.error("index_act_sections_no_document_id")
        return {
            "status": "section_indexing_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Skip if previous task failed
    if prev_result and not force:
        prev_status = prev_result.get("status", "")
        if "failed" in str(prev_status).lower():
            logger.info(
                "index_act_sections_skipped_prev_failed",
                document_id=doc_id,
                prev_status=prev_status,
            )
            return {
                "status": "section_indexing_skipped",
                "document_id": doc_id,
                "reason": f"Previous task failed: {prev_status}",
            }

    client = get_service_client()

    # Check if this is an Act document
    doc_result = (
        client.table("documents")
        .select("document_type, matter_id")
        .eq("id", doc_id)
        .single()
        .execute()
    )

    if not doc_result.data:
        logger.warning(
            "index_act_sections_document_not_found",
            document_id=doc_id,
        )
        return {
            "status": "section_indexing_skipped",
            "document_id": doc_id,
            "reason": "Document not found",
        }

    document_type = doc_result.data.get("document_type")
    matter_id = doc_result.data.get("matter_id")

    # Only index Act documents
    if document_type != "act":
        logger.info(
            "index_act_sections_skipped_not_act",
            document_id=doc_id,
            document_type=document_type,
        )
        return {
            "status": "section_indexing_skipped",
            "document_id": doc_id,
            "reason": f"Not an Act document (type: {document_type})",
        }

    logger.info(
        "index_act_sections_started",
        document_id=doc_id,
        matter_id=matter_id,
    )

    try:
        # Index sections
        section_service = get_section_index_service()
        section_count = section_service.index_document_sections(
            document_id=doc_id,
            matter_id=matter_id,
        )

        logger.info(
            "index_act_sections_completed",
            document_id=doc_id,
            section_count=section_count,
        )

        return {
            "status": "section_indexing_complete",
            "document_id": doc_id,
            "sections_indexed": section_count,
        }

    except Exception as e:
        logger.error(
            "index_act_sections_failed",
            document_id=doc_id,
            error=str(e),
        )

        if self.request.retries < 2:
            raise self.retry(exc=e)

        return {
            "status": "section_indexing_failed",
            "document_id": doc_id,
            "error_code": "INDEXING_ERROR",
            "error_message": str(e),
        }


# =============================================================================
# Entity Extraction Task (MIG)
# =============================================================================

# Entity extraction config defaults (can be overridden by settings)
ENTITY_EXTRACTION_BATCH_SIZE = 10  # Chunks per parallel batch
ENTITY_EXTRACTION_MEGA_BATCH_SIZE = 5  # Chunks per mega-batch API call
ENTITY_EXTRACTION_CONCURRENT_LIMIT = 5  # Max concurrent API calls
ENTITY_EXTRACTION_RATE_LIMIT_DELAY = 0.3  # Seconds between batches


@celery_app.task(
    name="app.workers.tasks.document_tasks.extract_entities",
    bind=True,
    autoretry_for=(MIGExtractorError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
)  # type: ignore[misc]
def extract_entities(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
    mig_extractor: MIGEntityExtractor | None = None,
    mig_graph_service: MIGGraphService | None = None,
    force: bool = False,
) -> dict[str, str | int | float | None]:
    """Extract entities from document chunks using Gemini.

    This task runs after embed_chunks to populate the Matter Identity Graph
    with extracted entities (people, organizations, institutions, assets).

    Pipeline: OCR -> Validate -> Confidence -> Chunk -> Embed -> **Extract Entities**

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).
        mig_extractor: Optional MIGEntityExtractor instance (for testing).
        mig_graph_service: Optional MIGGraphService instance (for testing).
        force: If True, skip status validation and run regardless of prev_result.

    Returns:
        Task result with entity extraction summary.

    Raises:
        MIGExtractorError: If extraction fails (will trigger retry).
    """

    from app.services.supabase.client import get_service_client

    # Get document_id from prev_result or parameter
    doc_id = document_id
    if doc_id is None and prev_result:
        doc_id = prev_result.get("document_id")  # type: ignore[assignment]

    if not doc_id:
        logger.error("extract_entities_no_document_id")
        return {
            "status": "entity_extraction_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Log force mode usage for audit trail
    if force:
        logger.info(
            "extract_entities_force_mode",
            document_id=doc_id,
            reason="Bypassing status validation",
        )

    # Skip if previous task explicitly failed (unless force=True)
    if prev_result and not force:
        prev_status = prev_result.get("status")
        # Expanded valid statuses - allow entity extraction to run after
        # OCR completes, chunking, or embedding (parallel pipeline support)
        valid_statuses = (
            "searchable",
            "embedding_complete",
            "ocr_complete",
            "chunking_complete",
            "validated",
            "validated_with_warnings",
            "validation_skipped",
            "confidence_calculated",
            "confidence_skipped",
        )
        # Only skip on explicit failure statuses
        failed_statuses = (
            "failed",
            "error",
            "ocr_failed",
            "validation_failed",
            "chunking_failed",
            "embedding_failed",
            "entity_extraction_failed",
        )
        if prev_status in failed_statuses:
            logger.info(
                "extract_entities_skipped",
                document_id=doc_id,
                prev_status=prev_status,
                reason="Previous task failed",
            )
            return {
                "status": "entity_extraction_skipped",
                "document_id": doc_id,
                "reason": f"Previous task failed with status: {prev_status}",
            }
        # Log if running with unexpected status (but proceed anyway)
        if prev_status and prev_status not in valid_statuses:
            logger.warning(
                "extract_entities_unexpected_status",
                document_id=doc_id,
                prev_status=prev_status,
                action="proceeding_anyway",
            )

    # Use injected services or get defaults
    doc_service = document_service or get_document_service()
    extractor = mig_extractor or get_mig_extractor()
    graph_service = mig_graph_service or get_mig_graph_service()

    logger.info(
        "extract_entities_task_started",
        document_id=doc_id,
        retry_count=self.request.retries,
    )

    try:
        # Get matter_id for the document
        _, matter_id = doc_service.get_document_for_processing(doc_id)

        # Get database client
        client = get_service_client()
        if client is None:
            raise MIGExtractorError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
                is_retryable=False,
            )

        # Get job_id for partial progress tracking
        # First try prev_result, then lookup from database
        job_id: str | None = None
        if prev_result:
            job_id = prev_result.get("job_id")  # type: ignore[assignment]
        if job_id is None:
            job_id = _lookup_job_id_for_document(doc_id)

        # IDEMPOTENCY CHECK: Skip if entity mentions already exist for this DOCUMENT
        # Changed from per-matter to per-document to ensure all documents get processed
        has_mentions, mention_count = _check_entity_mentions_exist_for_document(doc_id)
        if has_mentions and not force:
            logger.info(
                "extract_entities_idempotency_skip",
                document_id=doc_id,
                matter_id=matter_id,
                mention_count=mention_count,
                reason="Entity mentions already exist for this document",
            )
            # Update job stage to mark entity_extraction complete
            _update_job_stage_complete(job_id, "entity_extraction", matter_id)
            return {
                "status": "entities_extracted",
                "document_id": doc_id,
                "entities_extracted": mention_count,
                "reason": "Idempotency check: entity mentions already exist for document",
                "job_id": job_id,
            }

        # Get all chunks for this document (child chunks for more granular extraction)
        response = (
            client.table("chunks")
            .select("id, content, chunk_type, page_number")
            .eq("document_id", doc_id)
            .eq("chunk_type", "child")  # Extract from child chunks for precision
            .order("chunk_index", desc=False)
            .execute()
        )

        chunks = response.data or []

        # Story 2.2: Fallback to raw extracted_text if no chunks available
        # This allows entity extraction to run in parallel with chunking
        use_raw_text_fallback = False
        raw_text_windows: list[dict] = []

        if not chunks:
            logger.info(
                "extract_entities_no_chunks_trying_raw_text",
                document_id=doc_id,
            )

            # Get document's extracted_text as fallback
            doc = doc_service.get_document(doc_id)
            if doc and doc.extracted_text and len(doc.extracted_text.strip()) > 0:
                # Split raw text into windows for batch processing
                raw_text = doc.extracted_text
                window_size = 8000  # ~2000 tokens, safe for most LLMs
                overlap = 500  # Small overlap to avoid cutting entities

                for i in range(0, len(raw_text), window_size - overlap):
                    window_text = raw_text[i : i + window_size]
                    if window_text.strip():
                        raw_text_windows.append({
                            "id": f"raw_window_{i}",
                            "content": window_text,
                            "chunk_type": "raw_window",
                            "page_number": None,
                        })

                if raw_text_windows:
                    use_raw_text_fallback = True
                    chunks = raw_text_windows
                    logger.info(
                        "extract_entities_using_raw_text_fallback",
                        document_id=doc_id,
                        window_count=len(raw_text_windows),
                        text_length=len(raw_text),
                    )
                else:
                    logger.info(
                        "extract_entities_no_text_available",
                        document_id=doc_id,
                    )
                    return {
                        "status": "entity_extraction_complete",
                        "document_id": doc_id,
                        "entities_extracted": 0,
                        "reason": "No chunks or text found for entity extraction",
                        "job_id": job_id,
                    }
            else:
                logger.info(
                    "extract_entities_no_chunks_or_text",
                    document_id=doc_id,
                )
                return {
                    "status": "entity_extraction_complete",
                    "document_id": doc_id,
                    "entities_extracted": 0,
                    "reason": "No chunks or extracted text available",
                    "job_id": job_id,
                }

        # Initialize partial progress tracker (Story 2c-3)
        progress_tracker = create_progress_tracker(job_id, matter_id)
        stage_progress = None
        if progress_tracker:
            stage_progress = progress_tracker.get_or_create_stage("entity_extraction")
            stage_progress.total_items = len(chunks)

        # Get already-processed chunk IDs from previous run (for retry)
        already_processed: set[str] = set()
        if stage_progress:
            already_processed = stage_progress.processed_items

        logger.info(
            "extract_entities_processing",
            document_id=doc_id,
            chunk_count=len(chunks),
            already_processed=len(already_processed),
            batch_size=ENTITY_EXTRACTION_BATCH_SIZE,
        )

        # Process chunks and extract entities
        total_entities = 0
        total_relationships = 0
        failed_chunks = 0
        skipped_chunks = 0

        # Get config for extraction strategy
        settings = get_settings()
        use_mega_batch = settings.entity_extraction_use_batch
        mega_batch_size = settings.entity_extraction_batch_size
        concurrent_limit = settings.entity_extraction_concurrent_limit
        rate_delay = settings.entity_extraction_rate_delay

        logger.info(
            "extract_entities_strategy",
            document_id=doc_id,
            use_mega_batch=use_mega_batch,
            mega_batch_size=mega_batch_size,
            concurrent_limit=concurrent_limit,
            chunk_count=len(chunks),
        )

        # Process all batches in a single async context with PARALLEL extraction
        async def _extract_entities_async():
            nonlocal total_entities, total_relationships, failed_chunks, skipped_chunks

            # Semaphore to limit concurrent API calls (avoid rate limits)
            semaphore = asyncio.Semaphore(concurrent_limit)

            async def _process_mega_batch(mega_batch: list[dict]) -> tuple[int, int, int]:
                """Process multiple chunks in a single API call (mega-batch).

                Returns:
                    Tuple of (entities_count, relationships_count, failed_count).
                """
                async with semaphore:
                    try:
                        # MEGA-BATCH: Extract from multiple chunks in one call
                        extraction_results = await extractor.extract_entities_batch(
                            chunks=mega_batch,
                            document_id=doc_id,
                            matter_id=matter_id,
                        )

                        batch_entities = 0
                        batch_relationships = 0
                        batch_failed = 0

                        # Process each result and save to database
                        for chunk, result in zip(mega_batch, extraction_results, strict=False):
                            chunk_id = chunk["id"]

                            if result.entities:
                                saved = await graph_service.save_entities(
                                    matter_id=matter_id,
                                    extraction_result=result,
                                )
                                batch_entities += len(saved)

                            if result.relationships:
                                batch_relationships += len(result.relationships)

                            # Track progress
                            if stage_progress:
                                stage_progress.mark_processed(chunk_id)

                        return (batch_entities, batch_relationships, batch_failed)

                    except Exception as e:
                        logger.warning(
                            "extract_entities_mega_batch_error",
                            document_id=doc_id,
                            batch_size=len(mega_batch),
                            error=str(e),
                        )
                        # Mark all chunks in batch as failed
                        for chunk in mega_batch:
                            if stage_progress:
                                stage_progress.mark_failed(chunk["id"], str(e))
                        return (0, 0, len(mega_batch))

            async def _process_single_chunk(chunk: dict) -> tuple[int, int, bool]:
                """Process a single chunk (fallback when mega-batch disabled).

                Returns:
                    Tuple of (entities_count, relationships_count, success).
                """
                chunk_id = chunk["id"]

                async with semaphore:
                    try:
                        extraction_result = await extractor.extract_entities(
                            text=chunk["content"],
                            document_id=doc_id,
                            matter_id=matter_id,
                            chunk_id=chunk_id,
                            page_number=chunk.get("page_number"),
                        )

                        entities_count = 0
                        relationships_count = 0

                        if extraction_result.entities:
                            saved_entities = await graph_service.save_entities(
                                matter_id=matter_id,
                                extraction_result=extraction_result,
                            )
                            entities_count = len(saved_entities)

                        if extraction_result.relationships:
                            relationships_count = len(extraction_result.relationships)

                        if stage_progress:
                            stage_progress.mark_processed(chunk_id)

                        return (entities_count, relationships_count, True)

                    except MIGExtractorError as e:
                        if stage_progress:
                            stage_progress.mark_failed(chunk_id, str(e))
                        if e.is_retryable:
                            if progress_tracker and stage_progress:
                                progress_tracker.save_progress(stage_progress, force=True)
                            raise
                        return (0, 0, False)
                    except Exception as e:
                        if stage_progress:
                            stage_progress.mark_failed(chunk_id, str(e))
                        return (0, 0, False)

            # Filter out already-processed chunks
            chunks_to_process = [c for c in chunks if c["id"] not in already_processed]
            skipped_chunks = len(chunks) - len(chunks_to_process)

            if use_mega_batch:
                # MEGA-BATCH MODE: Process chunks in groups, each group = 1 API call
                # Example: 657 chunks / 5 per batch = 132 API calls (instead of 657)
                for i in range(0, len(chunks_to_process), ENTITY_EXTRACTION_BATCH_SIZE):
                    outer_batch = chunks_to_process[i : i + ENTITY_EXTRACTION_BATCH_SIZE]

                    # Split into mega-batches for parallel API calls
                    mega_batches = [
                        outer_batch[j : j + mega_batch_size]
                        for j in range(0, len(outer_batch), mega_batch_size)
                    ]

                    # Process mega-batches in parallel (limited by semaphore)
                    results = await asyncio.gather(
                        *[_process_mega_batch(mb) for mb in mega_batches],
                        return_exceptions=True,
                    )

                    for result in results:
                        if isinstance(result, Exception):
                            failed_chunks += mega_batch_size
                            logger.warning(
                                "extract_entities_mega_batch_exception",
                                document_id=doc_id,
                                error=str(result),
                            )
                        else:
                            entities, relationships, failed = result
                            total_entities += entities
                            total_relationships += relationships
                            failed_chunks += failed

                    # Persist progress periodically
                    if progress_tracker and stage_progress:
                        progress_tracker.save_progress(stage_progress)

                    # Broadcast progressive entity discovery for real-time UI updates
                    if total_entities > 0:
                        broadcast_entity_discovery(
                            matter_id=matter_id,
                            total_entities=total_entities,
                        )

                    # Rate limit between outer batches
                    if i + ENTITY_EXTRACTION_BATCH_SIZE < len(chunks_to_process):
                        await asyncio.sleep(rate_delay)

                    logger.debug(
                        "extract_entities_batch_complete",
                        document_id=doc_id,
                        batch_number=i // ENTITY_EXTRACTION_BATCH_SIZE + 1,
                        total_batches=(len(chunks_to_process) + ENTITY_EXTRACTION_BATCH_SIZE - 1) // ENTITY_EXTRACTION_BATCH_SIZE,
                        mode="mega_batch",
                        api_calls=len(mega_batches),
                    )
            else:
                # PARALLEL MODE: Individual API calls per chunk (faster with semaphore)
                for i in range(0, len(chunks_to_process), ENTITY_EXTRACTION_BATCH_SIZE):
                    batch = chunks_to_process[i : i + ENTITY_EXTRACTION_BATCH_SIZE]

                    results = await asyncio.gather(
                        *[_process_single_chunk(chunk) for chunk in batch],
                        return_exceptions=True,
                    )

                    for result in results:
                        if isinstance(result, Exception):
                            failed_chunks += 1
                        else:
                            entities, relationships, success = result
                            total_entities += entities
                            total_relationships += relationships
                            if not success:
                                failed_chunks += 1

                    if progress_tracker and stage_progress:
                        progress_tracker.save_progress(stage_progress)

                    # Broadcast progressive entity discovery for real-time UI updates
                    if total_entities > 0:
                        broadcast_entity_discovery(
                            matter_id=matter_id,
                            total_entities=total_entities,
                        )

                    if i + ENTITY_EXTRACTION_BATCH_SIZE < len(chunks_to_process):
                        await asyncio.sleep(rate_delay)

                    logger.debug(
                        "extract_entities_batch_complete",
                        document_id=doc_id,
                        batch_number=i // ENTITY_EXTRACTION_BATCH_SIZE + 1,
                        total_batches=(len(chunks_to_process) + ENTITY_EXTRACTION_BATCH_SIZE - 1) // ENTITY_EXTRACTION_BATCH_SIZE,
                        mode="parallel",
                    )

        try:
            asyncio.run(_extract_entities_async())
        finally:
            # Save final progress
            if progress_tracker and stage_progress:
                progress_tracker.save_progress(stage_progress, force=True)

        # Broadcast entity extraction completion
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="entities_extracted",
            entities_extracted=total_entities,
            relationships_found=total_relationships,
        )

        # Story 7.1: Broadcast entities feature availability
        broadcast_feature_ready(
            matter_id=matter_id,
            document_id=doc_id,
            feature=FeatureType.ENTITIES,
            metadata={"entities_count": total_entities},
        )

        logger.info(
            "extract_entities_task_completed",
            document_id=doc_id,
            entities_extracted=total_entities,
            relationships_found=total_relationships,
            chunks_processed=len(chunks),
            failed_chunks=failed_chunks,
            skipped_chunks=skipped_chunks,
            used_raw_text_fallback=use_raw_text_fallback,
        )

        # Sync entity_ids to chunks for downstream tasks (e.g., contradiction detection)
        # This must happen after entity extraction to populate chunks.entity_ids array
        chunks_synced = 0
        if total_entities > 0 and not use_raw_text_fallback:
            chunks_synced = _sync_entity_ids_to_chunks(doc_id)

        return {
            "status": "entities_extracted",
            "document_id": doc_id,
            "entities_extracted": total_entities,
            "relationships_found": total_relationships,
            "chunks_processed": len(chunks),
            "failed_chunks": failed_chunks,
            "skipped_chunks": skipped_chunks,
            "job_id": job_id,
            "used_raw_text_fallback": use_raw_text_fallback,
            "chunks_synced_entity_ids": chunks_synced,
        }

    except MIGExtractorError as e:
        retry_count = self.request.retries

        logger.warning(
            "extract_entities_task_retry",
            document_id=doc_id,
            retry_count=retry_count,
            max_retries=3,
            error=str(e),
        )

        if retry_count >= 3:
            logger.error(
                "extract_entities_task_failed",
                document_id=doc_id,
                error=str(e),
            )
            return {
                "status": "entity_extraction_failed",
                "document_id": doc_id,
                "error_code": e.code,
                "error_message": e.message,
            }

        raise

    except DocumentServiceError as e:
        logger.error(
            "extract_entities_document_error",
            document_id=doc_id,
            error=str(e),
        )
        return {
            "status": "entity_extraction_failed",
            "document_id": doc_id,
            "error_code": e.code,
            "error_message": e.message,
        }

    except Exception as e:
        logger.error(
            "extract_entities_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "status": "entity_extraction_failed",
            "document_id": doc_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
        }


# =============================================================================
# Downstream Task Dispatch Helper
# =============================================================================


def _dispatch_downstream_tasks(
    document_id: str,
    matter_id: str,
    job_id: str | None = None,
) -> dict[str, list[str]]:
    """Dispatch downstream tasks after alias resolution completes.

    Triggers citation extraction and date extraction in parallel.
    These tasks can run independently on the document text.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID for namespace isolation.
        job_id: Optional job tracking UUID.

    Returns:
        Dict with lists of triggered and failed task names.
    """
    from app.workers.celery import celery_app
    from app.workers.tasks.engine_tasks import extract_dates_from_document

    triggered_tasks: list[str] = []
    failed_tasks: list[str] = []

    # Build prev_result for task chain simulation
    prev_result = {
        "document_id": document_id,
        "status": "aliases_resolved",
        "job_id": job_id,
    }

    # Task 1: Citation extraction (use send_task to avoid forward reference)
    try:
        celery_app.send_task(
            "app.workers.tasks.document_tasks.extract_citations",
            kwargs={
                "prev_result": prev_result,
                "document_id": document_id,
            },
        )
        triggered_tasks.append("extract_citations")
        logger.debug("extract_citations_dispatched", document_id=document_id)
    except Exception as e:
        failed_tasks.append("extract_citations")
        logger.warning(
            "extract_citations_dispatch_failed",
            document_id=document_id,
            error=str(e),
        )

    # Task 2: Date extraction
    try:
        extract_dates_from_document.delay(
            document_id=document_id,
            matter_id=matter_id,
        )
        triggered_tasks.append("extract_dates_from_document")
        logger.debug("extract_dates_dispatched", document_id=document_id)
    except Exception as e:
        failed_tasks.append("extract_dates_from_document")
        logger.warning(
            "extract_dates_dispatch_failed",
            document_id=document_id,
            error=str(e),
        )

    logger.info(
        "downstream_tasks_dispatched",
        document_id=document_id,
        triggered=triggered_tasks,
        failed=failed_tasks,
    )

    return {
        "triggered": triggered_tasks,
        "failed": failed_tasks,
    }


# =============================================================================
# Alias Resolution Task (Story 2c-2)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.document_tasks.resolve_aliases",
    bind=True,
    autoretry_for=(AliasResolutionError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
)  # type: ignore[misc]
def resolve_aliases(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
    entity_resolver: EntityResolver | None = None,
    mig_graph_service: MIGGraphService | None = None,
    job_tracker: JobTrackingService | None = None,
) -> dict[str, str | int | float | None]:
    """Resolve entity aliases after extraction.

    This task runs after extract_entities to find and link name variants
    (e.g., "N.D. Jobalia" -> "Nirav D. Jobalia") as aliases.

    Pipeline: ... -> Extract Entities -> **Resolve Aliases**

    Three-phase resolution:
    1. High similarity (>0.85): Auto-link as aliases
    2. Medium similarity (0.60-0.85): Use Gemini context analysis
    3. Low similarity (<0.60): Skip

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).
        entity_resolver: Optional EntityResolver instance (for testing).
        mig_graph_service: Optional MIGGraphService instance (for testing).
        job_tracker: Optional JobTrackingService instance (for testing).

    Returns:
        Task result with alias resolution summary.

    Raises:
        AliasResolutionError: If resolution fails (will trigger retry).
    """
    from app.services.supabase.client import get_service_client

    # Get document_id and job_id from prev_result or parameter
    doc_id = document_id
    job_id: str | None = None
    matter_id: str | None = None

    if prev_result:
        if doc_id is None:
            doc_id = prev_result.get("document_id")  # type: ignore[assignment]
        job_id = prev_result.get("job_id")  # type: ignore[assignment]

    # If job_id not in prev_result, look it up from database
    if job_id is None and doc_id:
        job_id = _lookup_job_id_for_document(doc_id)

    if not doc_id:
        logger.error("resolve_aliases_no_document_id")
        return {
            "status": "alias_resolution_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Skip if previous task wasn't successful
    if prev_result:
        prev_status = prev_result.get("status")
        valid_statuses = (
            "entities_extracted",
        )
        if prev_status not in valid_statuses:
            logger.info(
                "resolve_aliases_skipped",
                document_id=doc_id,
                prev_status=prev_status,
            )
            return {
                "status": "alias_resolution_skipped",
                "document_id": doc_id,
                "reason": f"Previous task status: {prev_status}",
                "job_id": job_id,
            }

    # Use injected services or get defaults
    doc_service = document_service or get_document_service()
    resolver = entity_resolver or get_entity_resolver()
    graph_service = mig_graph_service or get_mig_graph_service()

    logger.info(
        "resolve_aliases_task_started",
        document_id=doc_id,
        retry_count=self.request.retries,
    )

    try:
        # Get matter_id for the document
        _, matter_id = doc_service.get_document_for_processing(doc_id)

        # Track alias resolution stage start (Story 2c-3)
        _update_job_stage_start(job_id, "alias_resolution", matter_id)

        # Get database client
        client = get_service_client()
        if client is None:
            raise AliasResolutionError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        # Run async operations in single context
        async def _resolve_aliases_async():
            # Get all entities for this matter (returns tuple of entities, total_count)
            entities, _total = await graph_service.get_entities_by_matter(
                matter_id=matter_id, per_page=1000  # Get all entities for alias resolution
            )

            if not entities:
                return None, 0  # No entities to resolve

            # Build entity contexts from mentions for Gemini analysis
            entity_contexts: dict[str, str] = {}

            # Query entity_mentions for context
            mentions_response = client.table("entity_mentions").select(
                "entity_id, context"
            ).execute()

            if mentions_response.data:
                for mention in mentions_response.data:
                    entity_id = mention["entity_id"]
                    context = mention.get("context", "")
                    if entity_id not in entity_contexts:
                        entity_contexts[entity_id] = context
                    else:
                        # Append additional context
                        entity_contexts[entity_id] += f" | {context}"

            # Run alias resolution
            resolution_result, edges_to_create = await resolver.resolve_aliases(
                matter_id=matter_id,
                entities=entities,
                entity_contexts=entity_contexts,
            )

            # Create alias edges in the database
            aliases_created = 0
            for edge in edges_to_create:
                created_edge = await graph_service.create_alias_edge(
                    matter_id=matter_id,
                    source_id=edge.source_entity_id,
                    target_id=edge.target_entity_id,
                    confidence=edge.confidence or 0.0,
                    metadata=edge.metadata,
                )
                if created_edge:
                    aliases_created += 1

                    # Also update the aliases array on the canonical entity
                    # (entity with higher mention count gets the alias name)
                    source_entity = next(
                        (e for e in entities if e.id == edge.source_entity_id), None
                    )
                    target_entity = next(
                        (e for e in entities if e.id == edge.target_entity_id), None
                    )

                    if source_entity and target_entity:
                        # Canonical is the one with more mentions
                        if source_entity.mention_count >= target_entity.mention_count:
                            await graph_service.add_alias_to_entity(
                                entity_id=source_entity.id,
                                matter_id=matter_id,
                                alias=target_entity.canonical_name,
                            )
                        else:
                            await graph_service.add_alias_to_entity(
                                entity_id=target_entity.id,
                                matter_id=matter_id,
                                alias=source_entity.canonical_name,
                            )

            return resolution_result, aliases_created

        result = asyncio.run(_resolve_aliases_async())

        if result[0] is None:
            # No entities to resolve - mark stage and job complete
            _update_job_stage_complete(job_id, "alias_resolution", matter_id)
            _mark_job_completed(job_id, matter_id, document_id=doc_id)
            logger.info(
                "resolve_aliases_no_entities",
                document_id=doc_id,
                matter_id=matter_id,
            )
            return {
                "status": "alias_resolution_complete",
                "document_id": doc_id,
                "aliases_created": 0,
                "reason": "No entities found for alias resolution",
                "job_id": job_id,
            }

        resolution_result, aliases_created = result

        # Broadcast alias resolution completion
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="aliases_resolved",
            aliases_created=aliases_created,
            entities_processed=resolution_result.entities_processed,
            pairs_found=resolution_result.alias_pairs_found,
        )

        # Track alias resolution stage completion (Story 2c-3)
        _update_job_stage_complete(
            job_id,
            "alias_resolution",
            matter_id,
            metadata={
                "entities_processed": resolution_result.entities_processed,
                "aliases_created": aliases_created,
            },
        )

        # Mark the entire job as COMPLETED since this is the final stage
        _mark_job_completed(job_id, matter_id, document_id=doc_id)

        logger.info(
            "resolve_aliases_task_completed",
            document_id=doc_id,
            matter_id=matter_id,
            entities_processed=resolution_result.entities_processed,
            pairs_found=resolution_result.alias_pairs_found,
            aliases_created=aliases_created,
            high_confidence=resolution_result.high_confidence_links,
            medium_confidence=resolution_result.medium_confidence_links,
            skipped=resolution_result.skipped_low_confidence,
        )

        # Dispatch downstream tasks in parallel (citations and dates)
        # These tasks can run independently after alias resolution
        downstream_triggered = _dispatch_downstream_tasks(
            document_id=doc_id,
            matter_id=matter_id,
            job_id=job_id,
        )

        return {
            "status": "aliases_resolved",
            "document_id": doc_id,
            "entities_processed": resolution_result.entities_processed,
            "pairs_found": resolution_result.alias_pairs_found,
            "aliases_created": aliases_created,
            "high_confidence_links": resolution_result.high_confidence_links,
            "medium_confidence_links": resolution_result.medium_confidence_links,
            "skipped_low_confidence": resolution_result.skipped_low_confidence,
            "job_id": job_id,
            "downstream_tasks": downstream_triggered,
        }

    except AliasResolutionError as e:
        retry_count = self.request.retries

        logger.warning(
            "resolve_aliases_task_retry",
            document_id=doc_id,
            retry_count=retry_count,
            max_retries=3,
            error=str(e),
        )

        # Track stage failure
        _update_job_stage_failure(job_id, "alias_resolution", str(e), e.code, matter_id)

        if retry_count >= 3:
            logger.error(
                "resolve_aliases_task_failed",
                document_id=doc_id,
                error=str(e),
            )
            # Mark job as failed
            _mark_job_failed(job_id, e.message, e.code, matter_id)
            return {
                "status": "alias_resolution_failed",
                "document_id": doc_id,
                "error_code": e.code,
                "error_message": e.message,
                "job_id": job_id,
            }

        raise

    except DocumentServiceError as e:
        logger.error(
            "resolve_aliases_document_error",
            document_id=doc_id,
            error=str(e),
        )
        _mark_job_failed(job_id, e.message, e.code, matter_id)
        return {
            "status": "alias_resolution_failed",
            "document_id": doc_id,
            "error_code": e.code,
            "error_message": e.message,
            "job_id": job_id,
        }

    except Exception as e:
        logger.error(
            "resolve_aliases_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", matter_id)
        return {
            "status": "alias_resolution_failed",
            "document_id": doc_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
            "job_id": job_id,
        }


# =============================================================================
# Citation Extraction Task (Story 3-1)
# =============================================================================

CITATION_EXTRACTION_BATCH_SIZE = 10  # Chunks per Gemini API call
CITATION_EXTRACTION_RATE_LIMIT_DELAY = 0.5  # Seconds between batches


@celery_app.task(
    name="app.workers.tasks.document_tasks.extract_citations",
    bind=True,
    autoretry_for=(CitationExtractorError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
)  # type: ignore[misc]
def extract_citations(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
    citation_extractor: CitationExtractor | None = None,
    citation_storage: CitationStorageService | None = None,
) -> dict[str, str | int | float | None]:
    """Extract Act citations from document chunks using Gemini.

    This task runs after embed_chunks to identify Act references.
    Can run in parallel with entity extraction.

    Pipeline: OCR -> Validate -> Confidence -> Chunk -> Embed -> **Extract Citations**

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).
        citation_extractor: Optional CitationExtractor instance (for testing).
        citation_storage: Optional CitationStorageService instance (for testing).

    Returns:
        Task result with citation extraction summary.

    Raises:
        CitationExtractorError: If extraction fails (will trigger retry).
    """

    from app.services.supabase.client import get_service_client

    # Get document_id from prev_result or parameter
    doc_id = document_id
    if doc_id is None and prev_result:
        doc_id = prev_result.get("document_id")  # type: ignore[assignment]

    if not doc_id:
        logger.error("extract_citations_no_document_id")
        return {
            "status": "citation_extraction_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Skip if previous task wasn't successful
    if prev_result:
        prev_status = prev_result.get("status")
        valid_statuses = (
            "searchable",
            "embedding_complete",
            "entities_extracted",
            "aliases_resolved",
        )
        if prev_status not in valid_statuses:
            logger.info(
                "extract_citations_skipped",
                document_id=doc_id,
                prev_status=prev_status,
            )
            return {
                "status": "citation_extraction_skipped",
                "document_id": doc_id,
                "reason": f"Previous task status: {prev_status}",
            }

    # Use injected services or get defaults
    doc_service = document_service or get_document_service()
    extractor = citation_extractor or get_citation_extractor()
    storage = citation_storage or get_citation_storage_service()

    logger.info(
        "extract_citations_task_started",
        document_id=doc_id,
        retry_count=self.request.retries,
    )

    try:
        # Get matter_id for the document
        _, matter_id = doc_service.get_document_for_processing(doc_id)

        # Get database client
        client = get_service_client()
        if client is None:
            raise CitationExtractorError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
                is_retryable=False,
            )

        # Check document type - skip citation extraction for Act documents
        # Citations should only be extracted from case files, not from Acts
        doc_type_result = (
            client.table("documents")
            .select("document_type")
            .eq("id", doc_id)
            .single()
            .execute()
        )
        document_type = doc_type_result.data.get("document_type") if doc_type_result.data else None
        if document_type == "act":
            logger.info(
                "extract_citations_skipped_act_document",
                document_id=doc_id,
                document_type=document_type,
            )
            return {
                "status": "citation_extraction_skipped",
                "document_id": doc_id,
                "reason": "Act documents are not processed for citation extraction",
            }

        # Get job_id for partial progress tracking
        job_id: str | None = None
        if prev_result:
            job_id = prev_result.get("job_id")  # type: ignore[assignment]

        # If job_id not in prev_result, look it up from database
        if job_id is None:
            job_id = _lookup_job_id_for_document(doc_id)

        # Track citation extraction stage start (Story 2c-3)
        _update_job_stage_start(job_id, "citation_extraction", matter_id)

        # Get all chunks for this document (child chunks for granular extraction)
        # Include bbox_ids for linking citations to source bounding boxes
        response = (
            client.table("chunks")
            .select("id, content, chunk_type, page_number, bbox_ids")
            .eq("document_id", doc_id)
            .eq("chunk_type", "child")  # Extract from child chunks for precision
            .order("chunk_index", desc=False)
            .execute()
        )

        chunks = response.data or []

        if not chunks:
            logger.info(
                "extract_citations_no_chunks",
                document_id=doc_id,
            )
            return {
                "status": "citation_extraction_complete",
                "document_id": doc_id,
                "citations_extracted": 0,
                "unique_acts_found": 0,
                "reason": "No chunks found for citation extraction",
                "job_id": job_id,
            }

        # Initialize partial progress tracker
        progress_tracker = create_progress_tracker(job_id, matter_id)
        stage_progress = None
        if progress_tracker:
            stage_progress = progress_tracker.get_or_create_stage("citation_extraction")
            stage_progress.total_items = len(chunks)

        # Get already-processed chunk IDs from previous run (for retry)
        already_processed: set[str] = set()
        if stage_progress:
            already_processed = stage_progress.processed_items

        logger.info(
            "extract_citations_processing",
            document_id=doc_id,
            chunk_count=len(chunks),
            already_processed=len(already_processed),
            batch_size=CITATION_EXTRACTION_BATCH_SIZE,
        )

        # Process chunks and extract citations
        total_citations = 0
        total_unique_acts: set[str] = set()
        failed_chunks = 0
        skipped_chunks = 0

        # Process all batches in a single async context
        async def _extract_citations_async():
            nonlocal total_citations, failed_chunks, skipped_chunks

            for i in range(0, len(chunks), CITATION_EXTRACTION_BATCH_SIZE):
                batch = chunks[i : i + CITATION_EXTRACTION_BATCH_SIZE]

                for chunk in batch:
                    chunk_id = chunk["id"]

                    # Skip already-processed chunks (partial progress)
                    if chunk_id in already_processed:
                        skipped_chunks += 1
                        continue

                    try:
                        # Extract citations from chunk
                        extraction_result = extractor.extract_from_text_sync(
                            text=chunk["content"],
                            document_id=doc_id,
                            matter_id=matter_id,
                            chunk_id=chunk_id,
                            page_number=chunk.get("page_number"),
                        )

                        if extraction_result.citations:
                            # Save citations to database with source bbox IDs for highlighting
                            # bbox_ids come from the chunk's bbox linking step
                            chunk_bbox_ids = chunk.get("bbox_ids") or []
                            saved_count = await storage.save_citations(
                                matter_id=matter_id,
                                document_id=doc_id,
                                extraction_result=extraction_result,
                                source_bbox_ids=chunk_bbox_ids,
                            )
                            total_citations += saved_count

                        if extraction_result.unique_acts:
                            total_unique_acts.update(extraction_result.unique_acts)

                        # Track partial progress
                        if stage_progress:
                            stage_progress.mark_processed(chunk_id)

                    except CitationExtractorError as e:
                        if stage_progress:
                            stage_progress.mark_failed(chunk_id, str(e))

                        if e.is_retryable:
                            # Save progress before retry
                            if progress_tracker and stage_progress:
                                progress_tracker.save_progress(stage_progress, force=True)
                            raise  # Let Celery retry
                        logger.warning(
                            "extract_citations_chunk_failed",
                            document_id=doc_id,
                            chunk_id=chunk_id,
                            error=str(e),
                        )
                        failed_chunks += 1
                    except Exception as e:
                        logger.warning(
                            "extract_citations_chunk_error",
                            document_id=doc_id,
                            chunk_id=chunk_id,
                            error=str(e),
                        )
                        failed_chunks += 1
                        if stage_progress:
                            stage_progress.mark_failed(chunk_id, str(e))

                # Persist partial progress periodically
                if progress_tracker and stage_progress:
                    progress_tracker.save_progress(stage_progress)

                # Rate limit delay between batches
                if i + CITATION_EXTRACTION_BATCH_SIZE < len(chunks):
                    await asyncio.sleep(CITATION_EXTRACTION_RATE_LIMIT_DELAY)

                logger.debug(
                    "extract_citations_batch_complete",
                    document_id=doc_id,
                    batch_number=i // CITATION_EXTRACTION_BATCH_SIZE + 1,
                    total_batches=(len(chunks) + CITATION_EXTRACTION_BATCH_SIZE - 1) // CITATION_EXTRACTION_BATCH_SIZE,
                )

        try:
            asyncio.run(_extract_citations_async())
        finally:
            # Save final progress
            if progress_tracker and stage_progress:
                progress_tracker.save_progress(stage_progress, force=True)

        # Broadcast citation extraction completion
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="citations_extracted",
            citations_extracted=total_citations,
            unique_acts_found=len(total_unique_acts),
        )

        # Track citation extraction stage completion
        _update_job_stage_complete(
            job_id,
            "citation_extraction",
            matter_id,
            metadata={
                "citations_extracted": total_citations,
                "unique_acts_found": len(total_unique_acts),
            },
        )

        # Story 7.1: Broadcast citations feature availability
        broadcast_feature_ready(
            matter_id=matter_id,
            document_id=doc_id,
            feature=FeatureType.CITATIONS,
            metadata={
                "citations_count": total_citations,
                "unique_acts": len(total_unique_acts),
            },
        )

        logger.info(
            "extract_citations_task_completed",
            document_id=doc_id,
            citations_extracted=total_citations,
            unique_acts_found=len(total_unique_acts),
            chunks_processed=len(chunks),
            failed_chunks=failed_chunks,
            skipped_chunks=skipped_chunks,
        )

        # Chain to contradiction detection (Epic 5)
        citation_result = {
            "status": "citations_extracted",
            "document_id": doc_id,
            "citations_extracted": total_citations,
            "unique_acts_found": len(total_unique_acts),
            "unique_acts": list(total_unique_acts),
            "chunks_processed": len(chunks),
            "failed_chunks": failed_chunks,
            "skipped_chunks": skipped_chunks,
            "job_id": job_id,
        }

        # Dispatch contradiction detection task
        try:
            celery_app.send_task(
                "app.workers.tasks.document_tasks.detect_contradictions",
                kwargs={
                    "prev_result": citation_result,
                    "document_id": doc_id,
                },
            )
            logger.debug("detect_contradictions_dispatched", document_id=doc_id)
        except Exception as dispatch_error:
            logger.warning(
                "detect_contradictions_dispatch_failed",
                document_id=doc_id,
                error=str(dispatch_error),
            )

        # Trigger act validation and auto-fetching (if unique acts were found)
        if total_unique_acts:
            try:
                celery_app.send_task(
                    "app.workers.tasks.act_validation_tasks.validate_acts_for_matter",
                    kwargs={
                        "matter_id": matter_id,
                    },
                    queue="low",  # Low priority - background processing
                )
                logger.debug(
                    "act_validation_triggered",
                    matter_id=matter_id,
                    unique_acts=len(total_unique_acts),
                )
            except Exception as validation_error:
                logger.warning(
                    "act_validation_dispatch_failed",
                    matter_id=matter_id,
                    error=str(validation_error),
                )

        return citation_result

    except CitationExtractorError as e:
        retry_count = self.request.retries

        logger.warning(
            "extract_citations_task_retry",
            document_id=doc_id,
            retry_count=retry_count,
            max_retries=3,
            error=str(e),
        )

        if retry_count >= 3:
            logger.error(
                "extract_citations_task_failed",
                document_id=doc_id,
                error=str(e),
            )
            return {
                "status": "citation_extraction_failed",
                "document_id": doc_id,
                "error_code": e.code,
                "error_message": e.message,
            }

        raise

    except DocumentServiceError as e:
        logger.error(
            "extract_citations_document_error",
            document_id=doc_id,
            error=str(e),
        )
        return {
            "status": "citation_extraction_failed",
            "document_id": doc_id,
            "error_code": e.code,
            "error_message": e.message,
        }

    except Exception as e:
        logger.error(
            "extract_citations_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "status": "citation_extraction_failed",
            "document_id": doc_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
        }


# =============================================================================
# Contradiction Detection Task (Epic 5)
# =============================================================================

# Configuration
CONTRADICTION_MAX_ENTITIES_PER_RUN = 50  # Max entities to process per task run
CONTRADICTION_MAX_PAIRS_PER_ENTITY = 25  # Max pairs per entity (cost control)


@celery_app.task(
    name="app.workers.tasks.document_tasks.detect_contradictions",
    bind=True,
    autoretry_for=(ComparisonServiceError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
)  # type: ignore[misc]
def detect_contradictions(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
    comparison_service: StatementComparisonService | None = None,
    mig_graph_service: MIGGraphService | None = None,
    job_tracker: JobTrackingService | None = None,
) -> dict[str, str | int | float | None]:
    """Detect contradictions for entities in a document's matter.

    This task runs after citation extraction to identify contradictions
    between statements about the same entities across documents.

    Epic 5: Consistency & Contradiction Engine

    Pipeline: ... -> Extract Citations -> **Detect Contradictions**

    The task:
    1. Gets all entities mentioned in the document
    2. For each entity, compares statement pairs using GPT-4
    3. Stores contradiction results in statement_comparisons table
    4. Updates job tracking with contradiction counts

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).
        comparison_service: Optional StatementComparisonService (for testing).
        mig_graph_service: Optional MIGGraphService (for testing).
        job_tracker: Optional JobTrackingService (for testing).

    Returns:
        Task result with contradiction detection summary.

    Raises:
        ComparisonServiceError: If comparison fails (will trigger retry).
    """
    from app.services.supabase.client import get_service_client

    # Get document_id and job_id from prev_result or parameter
    doc_id = document_id
    job_id: str | None = None

    if prev_result:
        if doc_id is None:
            doc_id = prev_result.get("document_id")  # type: ignore[assignment]
        job_id = prev_result.get("job_id")  # type: ignore[assignment]

    # If job_id not in prev_result, look it up from database
    if job_id is None and doc_id:
        job_id = _lookup_job_id_for_document(doc_id)

    if not doc_id:
        logger.error("detect_contradictions_no_document_id")
        return {
            "status": "contradiction_detection_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Skip if previous task wasn't successful
    if prev_result:
        prev_status = prev_result.get("status")
        valid_statuses = (
            "citations_extracted",
            "citation_extraction_complete",
            "searchable",
        )
        if prev_status not in valid_statuses:
            logger.info(
                "detect_contradictions_skipped",
                document_id=doc_id,
                prev_status=prev_status,
            )
            return {
                "status": "contradiction_detection_skipped",
                "document_id": doc_id,
                "reason": f"Previous task status: {prev_status}",
            }

    # Use injected services or get defaults
    doc_service = document_service or get_document_service()
    compare_service = comparison_service or get_statement_comparison_service()
    mig_service = mig_graph_service or get_mig_graph_service()

    logger.info(
        "detect_contradictions_task_started",
        document_id=doc_id,
        retry_count=self.request.retries,
    )

    try:
        # Get matter_id for the document
        _, matter_id = doc_service.get_document_for_processing(doc_id)

        # Get database client
        client = get_service_client()
        if client is None:
            raise ComparisonServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        # Track contradiction detection stage start (Story 2c-3)
        _update_job_stage_start(job_id, "contradiction_detection", matter_id)

        # Get entities mentioned in this document from chunks.entity_ids
        response = (
            client.table("chunks")
            .select("entity_ids")
            .eq("document_id", doc_id)
            .not_.is_("entity_ids", "null")
            .execute()
        )

        # Collect unique entity IDs
        entity_ids: set[str] = set()
        for chunk in response.data or []:
            chunk_entities = chunk.get("entity_ids") or []
            entity_ids.update(chunk_entities)

        if not entity_ids:
            logger.info(
                "detect_contradictions_no_entities",
                document_id=doc_id,
            )
            _update_job_stage_complete(
                job_id,
                "contradiction_detection",
                matter_id,
                metadata={"entities_processed": 0, "contradictions_found": 0},
            )
            return {
                "status": "contradiction_detection_complete",
                "document_id": doc_id,
                "entities_processed": 0,
                "contradictions_found": 0,
                "reason": "No entities found in document",
                "job_id": job_id,
            }

        # Limit entities for cost control
        entities_to_process = list(entity_ids)[:CONTRADICTION_MAX_ENTITIES_PER_RUN]

        logger.info(
            "detect_contradictions_processing",
            document_id=doc_id,
            total_entities=len(entity_ids),
            entities_to_process=len(entities_to_process),
        )

        # Process entities and detect contradictions
        total_contradictions = 0
        total_pairs_compared = 0
        entities_processed = 0
        entities_skipped = 0
        total_cost_usd = 0.0

        async def _detect_contradictions_async():
            nonlocal total_contradictions, total_pairs_compared, entities_processed
            nonlocal entities_skipped, total_cost_usd

            for entity_id in entities_to_process:
                try:
                    # Compare statements for this entity
                    comparison_result = await compare_service.compare_entity_statements(
                        entity_id=entity_id,
                        matter_id=matter_id,
                        max_pairs=CONTRADICTION_MAX_PAIRS_PER_ENTITY,
                        confidence_threshold=0.5,
                        include_aliases=True,
                    )

                    # Aggregate results
                    total_contradictions += comparison_result.meta.contradictions_found
                    total_pairs_compared += comparison_result.meta.pairs_compared
                    total_cost_usd += comparison_result.meta.total_cost_usd
                    entities_processed += 1

                    logger.debug(
                        "detect_contradictions_entity_complete",
                        document_id=doc_id,
                        entity_id=entity_id,
                        contradictions=comparison_result.meta.contradictions_found,
                        pairs_compared=comparison_result.meta.pairs_compared,
                    )

                except Exception as e:
                    # Log but continue with other entities
                    logger.warning(
                        "detect_contradictions_entity_failed",
                        document_id=doc_id,
                        entity_id=entity_id,
                        error=str(e),
                    )
                    entities_skipped += 1

        # Run async comparison
        asyncio.run(_detect_contradictions_async())

        # Broadcast contradiction detection completion
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="contradictions_detected",
            contradictions_found=total_contradictions,
        )

        # Track contradiction detection stage completion
        _update_job_stage_complete(
            job_id,
            "contradiction_detection",
            matter_id,
            metadata={
                "entities_processed": entities_processed,
                "entities_skipped": entities_skipped,
                "contradictions_found": total_contradictions,
                "pairs_compared": total_pairs_compared,
                "cost_usd": total_cost_usd,
            },
        )

        # Broadcast contradictions feature availability
        broadcast_feature_ready(
            matter_id=matter_id,
            document_id=doc_id,
            feature=FeatureType.CONTRADICTIONS,
            metadata={
                "contradictions_count": total_contradictions,
                "entities_analyzed": entities_processed,
            },
        )

        logger.info(
            "detect_contradictions_task_completed",
            document_id=doc_id,
            entities_processed=entities_processed,
            entities_skipped=entities_skipped,
            contradictions_found=total_contradictions,
            pairs_compared=total_pairs_compared,
            cost_usd=total_cost_usd,
        )

        return {
            "status": "contradictions_detected",
            "document_id": doc_id,
            "entities_processed": entities_processed,
            "entities_skipped": entities_skipped,
            "contradictions_found": total_contradictions,
            "pairs_compared": total_pairs_compared,
            "cost_usd": total_cost_usd,
            "job_id": job_id,
        }

    except ComparisonServiceError as e:
        retry_count = self.request.retries

        logger.warning(
            "detect_contradictions_task_retry",
            document_id=doc_id,
            retry_count=retry_count,
            max_retries=3,
            error=str(e),
        )

        if retry_count >= 3:
            logger.error(
                "detect_contradictions_task_failed",
                document_id=doc_id,
                error=str(e),
            )
            return {
                "status": "contradiction_detection_failed",
                "document_id": doc_id,
                "error_code": e.code,
                "error_message": e.message,
            }

        raise

    except DocumentServiceError as e:
        logger.error(
            "detect_contradictions_document_error",
            document_id=doc_id,
            error=str(e),
        )
        return {
            "status": "contradiction_detection_failed",
            "document_id": doc_id,
            "error_code": e.code,
            "error_message": e.message,
        }

    except Exception as e:
        logger.error(
            "detect_contradictions_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "status": "contradiction_detection_failed",
            "document_id": doc_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
        }
