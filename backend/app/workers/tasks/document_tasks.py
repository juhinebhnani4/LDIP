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
from celery.exceptions import Ignore, MaxRetriesExceededError, SoftTimeLimitExceeded

from app.core.config import get_settings
from app.engines.citation import (
    CitationExtractor,
    CitationExtractorError,
    CitationStorageService,
    get_citation_extractor,
    get_citation_storage_service,
)
from app.models.activity import ActivityTypeEnum
from app.models.contradiction import (
    ComparisonResult,
    EntityComparisonsResponse,
)
from app.models.document import DocumentStatus
from app.models.entity import EntityEdgeCreate
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
from app.services.chunking.spatial_text_mapper import (
    enrich_layout_with_text,
    fetch_all_bboxes_for_document,
)
from app.services.contradiction import (
    StatementComparisonService,
    get_statement_comparison_service,
)
from app.services.contradiction.comparator import ComparisonServiceError
from app.services.document_service import (
    DocumentService,
    DocumentServiceError,
    get_document_service,
)
from app.services.eta_calculator import get_eta_calculator
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
from app.services.ocr_chunk_service import get_ocr_chunk_service
from app.services.pdf_chunker import CHUNK_THRESHOLD
from app.services.pdf_router import CHUNK_SIZE
from app.services.pubsub_service import (
    FeatureType,
    broadcast_document_status,
    broadcast_entity_discovery,
    broadcast_feature_ready,
    broadcast_job_progress,
    broadcast_job_status_change,
)
from app.services.rag.embedder import (
    EmbeddingService,
    EmbeddingServiceError,
    get_current_embedding_model_version,
    get_embedding_service,
)
from app.services.storage_service import (
    StorageError,
    StorageService,
    get_storage_service,
)
from app.services.summary_service import get_summary_service
from app.services.table_extraction.layout_extractor import (
    LayoutExtractorError,
    get_layout_extractor,
)
from app.services.table_extraction.models import DocumentLayout
from app.workers.celery import celery_app
from app.workers.utils import run_async

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


def _run_async(coro, timeout=300):
    """Run async coroutine in sync context for Celery tasks.

    Delegates to shared gevent-compatible run_async utility.

    Args:
        coro: Async coroutine to run.
        timeout: Timeout in seconds (default 300). Pass higher values
            for long-running tasks like alias resolution.
    """
    return run_async(coro, timeout=timeout)


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

        # Update completed stages count (use MAX to prevent regression from parallel tasks)
        stage_idx = STAGE_INDEX.get(stage_name, -1)
        new_completed_stages = stage_idx + 1 if stage_idx >= 0 else None

        # Get current job to update
        job = _run_async(tracker.get_job(job_id))
        if job:
            from app.models.job import ProcessingJobUpdate

            # Use MAX to prevent regression from parallel stage completion
            # e.g., citation_extraction (idx 7) completing before alias_resolution (idx 6)
            current_stages = getattr(job, 'completed_stages', 0) or 0
            if new_completed_stages is not None:
                completed_stages = max(current_stages, new_completed_stages)
            else:
                completed_stages = current_stages

            # Also prevent progress_pct regression (stages not in time_estimator return 0)
            current_pct = getattr(job, 'progress_pct', 0) or 0
            progress_pct = max(current_pct, progress_pct)

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

            # Gap #19: Check for batch completion and trigger email notification
            _check_batch_completion_and_notify(matter_id, job_id)

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


def _release_pipeline_lock_safe(document_id: str) -> None:
    """Release the pipeline deduplication lock on failure.

    Called from terminal failure handlers so that retrying doesn't get
    blocked by a stale lock. Safe to call even if no lock is held.
    """
    if not document_id:
        return
    try:
        from app.services.distributed_lock import PipelineLock
        PipelineLock(document_id).release()
    except Exception as e:
        logger.warning(
            "pipeline_lock_release_on_failure_error",
            document_id=document_id,
            error=str(e),
        )


def _populate_verification_records(matter_id: str, document_id: str) -> None:
    """Create finding_verifications records from engine results.

    Runs BEFORE _mark_job_completed(). Non-blocking — failures logged but don't break pipeline.
    SAFETY: Entire function wrapped in try/except — cannot prevent job completion.

    Creates a `findings` row for each contradiction/failed citation first (FK requirement),
    then creates the `finding_verifications` record pointing to that `findings` row.
    """
    from app.models.verification import FindingVerificationCreate
    from app.services.supabase.client import get_service_client
    from app.services.verification.verification_service import get_verification_service

    try:
        client = get_service_client()
        if client is None:
            return

        verification_service = get_verification_service()

        # 1. Fetch contradictions from statement_comparisons (include chunk refs for source tracking)
        contradictions = client.table("statement_comparisons") \
            .select("id, explanation, confidence, statement_a_id, statement_b_id") \
            .eq("matter_id", matter_id) \
            .eq("result", "contradiction") \
            .execute()

        # 1b. Resolve chunk IDs → document_id + page_number for source references
        chunk_ids_needed: set[str] = set()
        for row in (contradictions.data or []):
            chunk_ids_needed.add(row["statement_a_id"])
            chunk_ids_needed.add(row["statement_b_id"])

        chunk_info: dict[str, dict] = {}  # chunk id -> {document_id, page_number}
        if chunk_ids_needed:
            chunks_result = client.table("chunks") \
                .select("id, document_id, page_number") \
                .in_("id", list(chunk_ids_needed)) \
                .execute()
            for c in (chunks_result.data or []):
                chunk_info[c["id"]] = {
                    "document_id": c.get("document_id"),
                    "page_number": c.get("page_number"),
                }

        # 2. Fetch failed citations from citations
        failed_citations = client.table("citations") \
            .select("id, raw_citation_text, confidence, verification_status") \
            .eq("matter_id", matter_id) \
            .in_("verification_status", ["mismatch", "section_not_found"]) \
            .execute()

        # 3. Get existing findings (by source_id in content JSONB) to skip duplicates on re-runs
        existing_findings = client.table("findings") \
            .select("id, content") \
            .eq("matter_id", matter_id) \
            .in_("engine_type", ["contradiction", "citation"]) \
            .execute()

        # Build set of source IDs that already have findings rows
        existing_source_ids: set[str] = set()
        finding_id_by_source: dict[str, str] = {}
        for f in (existing_findings.data or []):
            content = f.get("content") or {}
            src_id = content.get("statement_comparison_id") or content.get("citation_id")
            if src_id:
                existing_source_ids.add(src_id)
                finding_id_by_source[src_id] = f["id"]

        # 4. Get existing finding_verifications to skip duplicates
        existing_verifications = client.table("finding_verifications") \
            .select("finding_id") \
            .eq("matter_id", matter_id) \
            .execute()
        existing_verification_finding_ids = {r["finding_id"] for r in (existing_verifications.data or [])}

        # 5. Create findings rows and build verification records
        records_to_create: list[FindingVerificationCreate] = []

        for row in (contradictions.data or []):
            source_id = row["id"]

            # Create findings row if not already exists
            if source_id not in existing_source_ids:
                try:
                    confidence_raw = row.get("confidence") or 50.0

                    # Resolve source document IDs and pages from chunks
                    source_doc_ids: list[str] = []
                    source_pages: list[int] = []
                    for chunk_id in [row.get("statement_a_id"), row.get("statement_b_id")]:
                        info = chunk_info.get(chunk_id, {})
                        if info.get("document_id"):
                            source_doc_ids.append(info["document_id"])
                        if info.get("page_number") is not None:
                            source_pages.append(info["page_number"])

                    finding_data = {
                        "matter_id": matter_id,
                        "engine_type": "contradiction",
                        "finding_type": "contradiction_detected",
                        "content": {
                            "statement_comparison_id": source_id,
                            "explanation": row.get("explanation"),
                        },
                        "confidence": min(confidence_raw / 100.0, 1.0),
                        "status": "pending",
                    }
                    if source_doc_ids:
                        finding_data["source_document_ids"] = source_doc_ids
                    if source_pages:
                        finding_data["source_pages"] = source_pages

                    finding_result = client.table("findings").insert(
                        finding_data
                    ).execute()
                    if finding_result.data:
                        finding_id = finding_result.data[0]["id"]
                        finding_id_by_source[source_id] = finding_id
                except Exception as e:
                    logger.warning(
                        "finding_create_failed",
                        source_type="contradiction",
                        source_id=source_id,
                        error=str(e),
                    )
                    continue

            finding_id = finding_id_by_source.get(source_id)
            if not finding_id or finding_id in existing_verification_finding_ids:
                continue

            records_to_create.append(FindingVerificationCreate(
                matter_id=matter_id,
                finding_id=finding_id,
                finding_type="contradiction_detected",
                finding_summary=(row.get("explanation") or "Contradiction between statements")[:500],
                confidence_before=row.get("confidence") or 50.0,
            ))

        for row in (failed_citations.data or []):
            source_id = row["id"]

            # Create findings row if not already exists
            if source_id not in existing_source_ids:
                try:
                    confidence_raw = row.get("confidence") or 60.0
                    finding_result = client.table("findings").insert({
                        "matter_id": matter_id,
                        "engine_type": "citation",
                        "finding_type": "citation_verification_failed",
                        "content": {
                            "citation_id": source_id,
                            "raw_citation_text": row.get("raw_citation_text"),
                            "verification_status": row.get("verification_status"),
                        },
                        "confidence": min(confidence_raw / 100.0, 1.0),
                        "status": "pending",
                    }).execute()
                    if finding_result.data:
                        finding_id = finding_result.data[0]["id"]
                        finding_id_by_source[source_id] = finding_id
                except Exception as e:
                    logger.warning(
                        "finding_create_failed",
                        source_type="citation",
                        source_id=source_id,
                        error=str(e),
                    )
                    continue

            finding_id = finding_id_by_source.get(source_id)
            if not finding_id or finding_id in existing_verification_finding_ids:
                continue

            records_to_create.append(FindingVerificationCreate(
                matter_id=matter_id,
                finding_id=finding_id,
                finding_type="citation_verification_failed",
                finding_summary=(row.get("raw_citation_text") or f"Citation {row.get('verification_status', 'issue')}")[:500],
                confidence_before=row.get("confidence") or 60.0,
            ))

        if not records_to_create:
            logger.debug("verification_records_none_needed", matter_id=matter_id)
            return

        # 6. Batch-create all verification records in ONE _run_async() call (gevent-safe)
        async def _create_all():
            created = 0
            failed = 0
            for record in records_to_create:
                try:
                    await verification_service.create_verification_record(
                        create_data=record,
                        supabase=client,
                    )
                    created += 1
                except Exception as e:
                    failed += 1
                    logger.warning(
                        "verification_record_create_failed",
                        finding_id=str(record.finding_id),
                        finding_type=record.finding_type,
                        error=str(e),
                    )
            return created, failed

        created_count, failed_count = _run_async(_create_all())

        logger.info(
            "verification_records_populated",
            matter_id=matter_id,
            document_id=document_id,
            records_created=created_count,
            records_failed=failed_count,
            records_attempted=len(records_to_create),
        )

    except Exception as e:
        # CRITICAL: Catch-all — cannot prevent job completion or trigger Celery retry
        logger.error(
            "verification_records_population_failed",
            matter_id=matter_id,
            document_id=document_id,
            error=str(e),
        )


def _dispatch_summary_pregeneration(matter_id: str | None) -> None:
    """Fire-and-forget: dispatch summary pre-generation after pipeline completes.

    Tier 1 #3: Summary is pre-generated so it's ready when the user visits
    the Summary tab. Failure here is silent — the on-demand path remains
    as fallback.
    """
    if not matter_id:
        return
    try:
        from app.workers.tasks.summary_tasks import generate_summary

        generate_summary.delay(matter_id)
        logger.info("summary_pregeneration_dispatched", matter_id=matter_id)
    except Exception as e:
        # Non-fatal: summary will regenerate on-demand when user visits tab
        logger.warning(
            "summary_pregeneration_dispatch_failed",
            matter_id=matter_id,
            error=str(e),
        )


def _mark_job_completed(
    job_id: str | None,
    matter_id: str | None = None,
    document_id: str | None = None,
    job_tracker: JobTrackingService | None = None,
    page_count: int | None = None,
    processing_start_time: float | None = None,
) -> None:
    """Mark job as completed successfully and update document status.

    Args:
        job_id: Job UUID.
        matter_id: Matter UUID for broadcasting.
        document_id: Document UUID to update status.
        job_tracker: Optional JobTrackingService instance.
        page_count: Number of pages (for ETA recording, Story 5.7).
        processing_start_time: Unix timestamp when processing started (Story 5.7).
    """
    # Always update document status, even without a job_id.
    # Admin retries and orphaned chains can run without a processing_jobs row.
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

    if not job_id:
        # Release pipeline lock even without a job
        if document_id:
            _release_pipeline_lock_safe(document_id)
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

            # Gap #19: Check for batch completion and trigger email notification
            _check_batch_completion_and_notify(matter_id, job_id)

        # Story 5.7: Record completion for ETA calculation
        if document_id:
            try:
                # Fetch page_count from document if not provided
                doc_page_count = page_count
                if doc_page_count is None:
                    doc_service = get_document_service()
                    doc = doc_service.get_document(document_id)
                    if doc and doc.page_count:
                        doc_page_count = doc.page_count

                if doc_page_count and doc_page_count > 0:
                    # Use provided start time or estimate based on typical processing
                    import time

                    if processing_start_time:
                        processing_time_ms = int((time.time() - processing_start_time) * 1000)
                    else:
                        # Fallback: estimate 3 seconds per page (conservative)
                        processing_time_ms = doc_page_count * 3000

                    eta_calculator = get_eta_calculator()
                    _run_async(
                        eta_calculator.record_completion(
                            document_id=document_id,
                            page_count=doc_page_count,
                            processing_time_ms=processing_time_ms,
                        )
                    )
                    logger.debug(
                        "eta_completion_recorded",
                        document_id=document_id,
                        page_count=doc_page_count,
                        processing_time_ms=processing_time_ms,
                    )
            except Exception as eta_err:
                # Non-fatal: log and continue
                logger.warning(
                    "eta_completion_record_failed",
                    document_id=document_id,
                    error=str(eta_err),
                )

        # Stage 1.2: Release pipeline deduplication lock
        if document_id:
            try:
                from app.services.distributed_lock import PipelineLock
                PipelineLock(document_id).release()
            except Exception as lock_err:
                logger.warning(
                    "pipeline_lock_release_failed_in_mark_completed",
                    document_id=document_id,
                    error=str(lock_err),
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
# Gap #19: Batch Completion Detection and Email Notification
# =============================================================================


def _check_batch_completion_and_notify(matter_id: str, completed_job_id: str) -> None:
    """Check if all jobs for a matter are complete and trigger email notification.

    Gap #19: AC #1 - Email sent when upload batch completes.

    This function checks if there are any remaining QUEUED or PROCESSING jobs
    for the matter. If not, it calculates batch statistics and triggers an
    email notification to all matter members who have email notifications enabled.

    Args:
        matter_id: Matter UUID.
        completed_job_id: Job UUID that just completed (for deduplication).
    """
    from app.services.supabase.client import get_service_client
    from app.workers.tasks.email_tasks import send_processing_complete_notification

    try:
        client = get_service_client()
        if client is None:
            logger.warning(
                "batch_completion_check_skipped",
                reason="supabase_not_configured",
                matter_id=matter_id,
            )
            return

        # Check if there are any remaining active jobs for this matter
        active_jobs = (
            client.table("processing_jobs")
            .select("id", count="exact")
            .eq("matter_id", matter_id)
            .in_("status", ["QUEUED", "PROCESSING"])
            .execute()
        )

        active_count = active_jobs.count or 0

        if active_count > 0:
            logger.debug(
                "batch_not_complete",
                matter_id=matter_id,
                active_jobs=active_count,
            )
            return

        # All jobs are complete - calculate batch statistics
        # Get jobs completed in the last hour (to approximate the batch)
        from datetime import UTC, datetime, timedelta

        cutoff_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

        completed_jobs = (
            client.table("processing_jobs")
            .select("status")
            .eq("matter_id", matter_id)
            .gte("updated_at", cutoff_time)
            .in_("status", ["COMPLETED", "FAILED", "SKIPPED"])
            .execute()
        )

        if not completed_jobs.data:
            logger.debug(
                "batch_completion_no_recent_jobs",
                matter_id=matter_id,
            )
            return

        # Calculate statistics
        doc_count = len(completed_jobs.data)
        success_count = sum(1 for j in completed_jobs.data if j["status"] == "COMPLETED")
        failed_count = sum(1 for j in completed_jobs.data if j["status"] in ("FAILED", "SKIPPED"))

        if doc_count == 0:
            return

        # Get all matter members to send emails
        matter_members = (
            client.table("matter_attorneys")
            .select("user_id")
            .eq("matter_id", matter_id)
            .execute()
        )

        if not matter_members.data:
            logger.warning(
                "batch_completion_no_members",
                matter_id=matter_id,
            )
            return

        # Trigger email notification for each member
        # (The email task will check individual opt-out preferences)
        for member in matter_members.data:
            user_id = member["user_id"]
            try:
                send_processing_complete_notification.apply_async(
                    kwargs={
                        "matter_id": matter_id,
                        "user_id": user_id,
                        "doc_count": doc_count,
                        "success_count": success_count,
                        "failed_count": failed_count,
                    },
                    queue="low",  # Email notifications are low priority
                )
                logger.debug(
                    "batch_completion_email_queued",
                    matter_id=matter_id,
                    user_id=user_id,
                )
            except Exception as e:
                logger.warning(
                    "batch_completion_email_queue_failed",
                    matter_id=matter_id,
                    user_id=user_id,
                    error=str(e),
                )

        logger.info(
            "batch_completion_emails_triggered",
            matter_id=matter_id,
            doc_count=doc_count,
            success_count=success_count,
            failed_count=failed_count,
            member_count=len(matter_members.data),
        )

    except Exception as e:
        # Non-fatal: log and continue
        logger.warning(
            "batch_completion_check_error",
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
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


def _extract_layout_for_chunking(document_id: str, matter_id: str) -> DocumentLayout | None:
    """Extract document layout using Docling for layout-aware chunking.

    This function downloads the PDF and runs Docling's layout extraction
    to detect structural elements (paragraphs, headings, tables, stamps).

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID for logging.

    Returns:
        DocumentLayout with detected blocks, or None on failure.
    """
    import tempfile
    from pathlib import Path

    from app.services.storage_service import get_storage_service
    from app.services.supabase.client import get_service_client

    try:
        # Check if Docling is available before attempting layout extraction
        from app.services.table_extraction.docling_provider import get_docling_provider
        if not get_docling_provider().is_available():
            logger.warning(
                "layout_extraction_docling_not_available",
                document_id=document_id,
                hint="Docling import failed. Check runtime has libgomp1 and all shared libs.",
            )
            return None

        # Get document info to find the storage path
        client = get_service_client()
        if client is None:
            logger.warning(
                "layout_extraction_no_client",
                document_id=document_id,
            )
            return None

        doc_response = (
            client.table("documents")
            .select("filename, storage_path")
            .eq("id", document_id)
            .limit(1)
            .execute()
        )

        if not doc_response.data:
            logger.warning(
                "layout_extraction_document_not_found",
                document_id=document_id,
            )
            return None

        doc = doc_response.data[0]
        storage_path = doc.get("storage_path")

        if not storage_path:
            logger.warning(
                "layout_extraction_no_storage_path",
                document_id=document_id,
            )
            return None

        # Download PDF to temp file
        storage_service = get_storage_service()
        pdf_content = storage_service.download_file(storage_path)

        if not pdf_content:
            logger.warning(
                "layout_extraction_download_failed",
                document_id=document_id,
                storage_path=storage_path,
            )
            return None

        # Write to temp file (Docling requires file path)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(pdf_content)
            tmp_path = Path(tmp_file.name)

        try:
            # Extract layout using Docling (sync operation - Issue #6 fix)
            layout_extractor = get_layout_extractor()
            layout = layout_extractor.extract_layout(tmp_path, document_id)

            logger.info(
                "layout_extraction_complete",
                document_id=document_id,
                matter_id=matter_id,
                block_count=len(layout.blocks) if layout else 0,
                success=layout.success if layout else False,
            )

            return layout

        finally:
            # Clean up temp file
            try:
                tmp_path.unlink()
            except Exception as cleanup_error:
                logger.debug(
                    "layout_extraction_temp_file_cleanup_failed",
                    document_id=document_id,
                    error=str(cleanup_error),
                )

    except LayoutExtractorError as e:
        logger.warning(
            "layout_extraction_error",
            document_id=document_id,
            error=str(e),
            code=e.code,
        )
        return None

    except Exception as e:
        logger.warning(
            "layout_extraction_unexpected_error",
            document_id=document_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


@celery_app.task(
    name="app.workers.tasks.document_tasks.process_document",
    bind=True,
    autoretry_for=(OCRServiceError, StorageError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=MAX_RETRIES,
    retry_jitter=True,
    soft_time_limit=900,  # 15 minutes - allows cleanup on timeout
    time_limit=960,  # 16 minutes - hard kill
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
            from app.workers.tasks.chunked_document_tasks import (
                process_document_chunked,
            )

            # Dispatch to chunked processing task
            process_document_chunked.apply_async(
                kwargs={
                    "document_id": document_id,
                    "matter_id": matter_id,
                    "job_id": job_id,
                },
                queue="default",  # Explicit queue routing - workers listen on default, not celery
            )

            logger.info(
                "chunked_processing_dispatched",
                document_id=document_id,
                page_count=page_count,
                job_id=job_id,
            )

            # Stop the original chain - chunked processing handles everything
            # This prevents the chain from racing through and marking job COMPLETED
            # before the actual work finishes. The job_id is passed to chunked
            # processing which will update progress and mark complete when done.
            raise Ignore()

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
            matter_id=matter_id,
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

    except SoftTimeLimitExceeded:
        # Task timeout - mark as failed so it can be retried later
        logger.error(
            "document_processing_task_timeout",
            document_id=document_id,
            timeout_seconds=900,  # soft_time_limit value
        )

        _matter_id = matter_id
        if not _matter_id:
            with contextlib.suppress(Exception):
                _, _matter_id = doc_service.get_document_for_processing(document_id)

        # Mark job as failed with timeout error
        _mark_job_failed(
            job_id,
            "Processing timeout exceeded (15 minutes)",
            "TIMEOUT",
            _matter_id,
        )

        with contextlib.suppress(DocumentServiceError):
            doc_service.update_ocr_status(
                document_id=document_id,
                status=DocumentStatus.OCR_FAILED,
                ocr_error="Processing timeout exceeded - document may be too large or service unavailable",
            )

        # Broadcast failure
        if _matter_id:
            broadcast_document_status(
                matter_id=_matter_id,
                document_id=document_id,
                status="ocr_failed",
                error_message="Processing timeout",
            )

        return {
            "status": "ocr_failed",
            "document_id": document_id,
            "error_code": "TIMEOUT",
            "error_message": "Processing timeout exceeded (15 minutes)",
            "job_id": job_id,
        }

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

    except Ignore:
        # Large document handoff - let Celery handle this properly
        # Do NOT mark as failed, do NOT catch in generic handler
        raise

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
        process_document.apply_async(
            args=[document_id],
            queue="default",  # Explicit queue routing - workers listen on default, not celery
        )

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
    soft_time_limit=300,  # 5 minutes - Gemini validation
    time_limit=360,  # 6 minutes - hard kill
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

    # Stage 1.2: Pipeline deduplication — acquire lock to prevent duplicate runs
    from app.services.distributed_lock import PipelineLock
    pipeline_lock = PipelineLock(doc_id)
    if not pipeline_lock.acquire():
        logger.info(
            "validate_ocr_skipped_pipeline_locked",
            document_id=doc_id,
        )
        return {
            "status": "validation_skipped",
            "document_id": doc_id,
            "reason": "Pipeline already running for this document",
            "job_id": job_id,
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
                gemini_results = gemini.validate_batch_sync(remaining_for_gemini, document_id=doc_id, matter_id=matter_id)
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
            _handle_validation_failure(doc_service, doc_id, e, job_id, matter_id)

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
        _handle_validation_failure(doc_service, doc_id, e, job_id, matter_id)

    except Exception as e:
        logger.error(
            "validate_ocr_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", matter_id)
        _handle_validation_failure(doc_service, doc_id, e, job_id, matter_id)


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
    job_id: str | None = None,
    matter_id: str | None = None,
) -> None:
    """Handle validation task failure — cleanup then raise.

    Performs cleanup (lock release, status update) then raises
    PipelineTaskError to stop the chain (DPP-002).

    Args:
        doc_service: DocumentService instance.
        document_id: Document UUID.
        error: The error that caused the failure.
        job_id: Processing job UUID (for error callback context).
        matter_id: Matter UUID (for error callback context).

    Raises:
        PipelineTaskError: Always raised after cleanup.
    """
    from app.workers.tasks.pipeline_errors import PipelineTaskError

    error_code = getattr(error, "code", "VALIDATION_FAILED")
    error_message = str(error)

    logger.error(
        "validate_ocr_task_failed",
        document_id=document_id,
        error=error_message,
        error_code=error_code,
    )

    # Release pipeline lock so retry is not blocked
    _release_pipeline_lock_safe(document_id)

    # Update status to indicate validation is pending (not failed OCR)
    # The document OCR is still valid, just validation couldn't complete
    _update_validation_status(
        doc_service,
        document_id,
        ValidationStatus.PENDING,
    )

    # DPP-002: Raise instead of return — Celery stops the chain
    raise PipelineTaskError(
        error_message,
        error_code=error_code,
        document_id=document_id,
        job_id=job_id,
        matter_id=matter_id,
        stage="validation",
    )


@celery_app.task(
    name="app.workers.tasks.document_tasks.calculate_confidence",
    bind=True,
    autoretry_for=(ConfidenceCalculatorError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
    soft_time_limit=120,  # 2 minutes
    time_limit=180,  # 3 minutes - hard kill
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
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error("calculate_confidence_no_document_id")
        raise PipelineTaskError(
            "No document_id provided",
            error_code="NO_DOCUMENT_ID",
            stage="confidence",
        )

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
            from app.workers.tasks.pipeline_errors import PipelineTaskError
            logger.error(
                "calculate_confidence_task_failed",
                document_id=doc_id,
                job_id=job_id,
                error=str(e),
            )
            _mark_job_failed(job_id, str(e), error_code, matter_id)
            _release_pipeline_lock_safe(doc_id)  # P8 fix: was missing
            raise PipelineTaskError(
                str(e),
                error_code=error_code,
                document_id=doc_id,
                job_id=job_id,
                matter_id=matter_id,
                stage="confidence",
            )

        raise

    except DocumentServiceError as e:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error(
            "calculate_confidence_document_error",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
        )
        _update_job_stage_failure(job_id, "confidence", str(e), e.code, None)
        _mark_job_failed(job_id, e.message, e.code, None)
        _release_pipeline_lock_safe(doc_id)  # P8 fix: was missing
        raise PipelineTaskError(
            e.message,
            error_code=e.code,
            document_id=doc_id,
            job_id=job_id,
            stage="confidence",
        )

    except Exception as e:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error(
            "calculate_confidence_unexpected_error",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        _update_job_stage_failure(job_id, "confidence", str(e), "UNEXPECTED_ERROR", None)
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", None)
        _release_pipeline_lock_safe(doc_id)  # P8 fix: was missing
        raise PipelineTaskError(
            str(e),
            error_code="UNEXPECTED_ERROR",
            document_id=doc_id,
            job_id=job_id,
            stage="confidence",
        )


@celery_app.task(
    name="app.workers.tasks.document_tasks.chunk_document",
    bind=True,
    autoretry_for=(ChunkServiceError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
    soft_time_limit=300,  # 5 minutes - chunking can be slow for large docs
    time_limit=360,  # 6 minutes - hard kill
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

        is_chunking_complete, parent_count, child_count = _run_async(
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

        # Layout-aware chunking: Extract layout structure if enabled
        settings = get_settings()
        layout: DocumentLayout | None = None
        layout_used = False

        if settings.layout_aware_chunking_enabled:
            try:
                layout = _extract_layout_for_chunking(doc_id, matter_id)
                if layout and layout.success and layout.has_blocks:
                    layout_used = True
                    logger.info(
                        "layout_extraction_for_chunking_success",
                        document_id=doc_id,
                        block_count=len(layout.blocks),
                        page_count=layout.page_count,
                    )

                    # Enrich layout blocks with Document AI text via IoS
                    # spatial matching. This bridges the gap between Docling
                    # (layout structure) and Document AI (OCR text).
                    try:
                        docai_bboxes = fetch_all_bboxes_for_document(
                            bbox_service, doc_id
                        )
                        if docai_bboxes:
                            enrich_layout_with_text(
                                layout, docai_bboxes, doc.extracted_text or ""
                            )
                    except Exception as e:
                        logger.warning(
                            "spatial_text_mapping_failed",
                            document_id=doc_id,
                            error=str(e),
                            action="chunking_proceeds_without_enrichment",
                        )
                else:
                    logger.info(
                        "layout_extraction_for_chunking_fallback",
                        document_id=doc_id,
                        reason=layout.error if layout else "No layout returned",
                    )
            except Exception as e:
                logger.warning(
                    "layout_extraction_for_chunking_failed",
                    document_id=doc_id,
                    error=str(e),
                    action="falling_back_to_text_chunking",
                )

        # Create chunker and process document
        chunker = ParentChildChunker()
        result = chunker.chunk_document(
            doc_id, doc.extracted_text, layout=layout,
            document_context=doc.filename,
        )

        # Prepare all chunks for saving
        all_chunks = result.parent_chunks + result.child_chunks

        # Run async operations in sync context
        async def _save_chunks_async():
            # Link chunks to bounding boxes for citation highlighting.
            # With spatial text mapping, layout-derived chunks now have
            # text_start/text_end offsets, enabling deterministic bbox linking.
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

        saved_count = _run_async(_save_chunks_async())

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

        # F1: Cache chunks to Redis for downstream engines (entity, citation, timeline)
        # This eliminates 2 extra Supabase reads per document
        try:
            from app.services.chunk_service import cache_chunks_to_redis
            # Build chunk dicts matching the format downstream tasks expect
            chunk_dicts = []
            for chunk_data in result.parent_chunks + result.child_chunks:
                chunk_dicts.append({
                    "id": str(chunk_data.id),
                    "content": chunk_data.content,
                    "chunk_type": chunk_data.chunk_type,
                    "page_number": chunk_data.page_number,
                    "chunk_index": chunk_data.chunk_index,
                    "bbox_ids": [str(b) for b in chunk_data.bbox_ids] if chunk_data.bbox_ids else [],
                })
            cache_chunks_to_redis(doc_id, chunk_dicts)
        except Exception as e:
            logger.debug("shared_chunk_cache_after_chunking_error", error=str(e))

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
            from app.workers.tasks.pipeline_errors import PipelineTaskError
            logger.error(
                "chunk_document_task_failed",
                document_id=doc_id,
                job_id=job_id,
                error=str(e),
            )
            _mark_job_failed(job_id, str(e), error_code, matter_id)
            _release_pipeline_lock_safe(doc_id)
            raise PipelineTaskError(
                str(e),
                error_code=error_code,
                document_id=doc_id,
                job_id=job_id,
                matter_id=matter_id,
                stage="chunking",
            )

        raise

    except DocumentServiceError as e:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error(
            "chunk_document_document_error",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
        )
        _update_job_stage_failure(job_id, "chunking", str(e), e.code, None)
        _mark_job_failed(job_id, e.message, e.code, None)
        _release_pipeline_lock_safe(doc_id)
        raise PipelineTaskError(
            e.message,
            error_code=e.code,
            document_id=doc_id,
            job_id=job_id,
            stage="chunking",
        )

    except Exception as e:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error(
            "chunk_document_unexpected_error",
            document_id=doc_id,
            job_id=job_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        _update_job_stage_failure(job_id, "chunking", str(e), "UNEXPECTED_ERROR", None)
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", None)
        _release_pipeline_lock_safe(doc_id)
        raise PipelineTaskError(
            str(e),
            error_code="UNEXPECTED_ERROR",
            document_id=doc_id,
            job_id=job_id,
            stage="chunking",
        )


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
            # Schema verified against migration 20260106000002 + 20260224000001:
            # id, content, chunk_index, parent_chunk_id, chunk_type, page_number,
            # token_count, text_start_offset, text_end_offset
            result = (
                client.table("chunks")
                .select("id, content, chunk_index, parent_chunk_id, chunk_type, page_number, token_count, text_start_offset, text_end_offset")
                .eq("document_id", document_id)
                .execute()
            )

            if not result.data:
                return 0

            # Use the real ChunkData from parent_child_chunker (expected by link_chunks_to_bboxes)
            from uuid import UUID as _UUID

            from app.services.chunking.parent_child_chunker import ChunkData

            chunks = [
                ChunkData(
                    id=_UUID(row["id"]) if isinstance(row["id"], str) else row["id"],
                    content=row["content"],
                    chunk_type=row.get("chunk_type", "parent"),
                    chunk_index=row.get("chunk_index", 0),
                    parent_id=_UUID(row["parent_chunk_id"]) if row.get("parent_chunk_id") else None,
                    token_count=row.get("token_count", 0),
                    page_number=row.get("page_number"),
                    text_start_offset=row.get("text_start_offset"),
                    text_end_offset=row.get("text_end_offset"),
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

        linked_count, matter_id = _run_async(_get_and_link_chunks())

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
    soft_time_limit=900,  # 15 minutes - embedding 500+ chunks on large docs
    time_limit=960,  # 16 minutes - hard kill
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
            "table_extraction_complete",  # Gap 5: extract_tables runs before embed_chunks
            "table_extraction_partial",
            "table_extraction_skipped",
            "table_extraction_failed",  # Non-critical — still embed text chunks
        )
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
        # Priority ordering: page_number first so earlier pages are embedded first
        # This enables "optimistic RAG" - users can search early content sooner
        response = (
            client.table("chunks")
            .select("id, content")
            .eq("document_id", doc_id)
            .is_("embedding", "null")
            .order("page_number", desc=False, nullsfirst=False)
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
                    embeddings = await embedder.embed_batch(batch_texts, skip_empty=True, matter_id=matter_id)

                    # Update chunks with embeddings
                    for _j, (chunk_id, embedding) in enumerate(zip(batch_ids, embeddings, strict=False)):
                        if embedding is None:
                            failed_count += 1
                            if stage_progress:
                                stage_progress.mark_failed(chunk_id, "Empty embedding")
                            continue

                        try:
                            # Story 1.3: Store embedding model version with vectors
                            client.table("chunks").update({
                                "embedding": embedding,
                                "embedding_model_version": get_current_embedding_model_version(),
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
                        await progress_tracker.save_progress_async(stage_progress)

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
                        await progress_tracker.save_progress_async(stage_progress, force=True)

                    if e.is_retryable:
                        raise  # Let Celery retry

        try:
            _run_async(_embed_all_batches(), timeout=840)  # Below soft_time_limit=900
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

        # Dispatch act-specific tasks after embedding
        # - Act documents: index sections for split-view navigation
        # - Citations are dispatched later from extract_entities -> _dispatch_post_entity_tasks()
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
                    queue="default",  # Explicit queue routing - workers listen on default, not celery
                )
                logger.info(
                    "index_act_sections_dispatched",
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

    except SoftTimeLimitExceeded:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        # Task timeout - save progress and mark as failed
        logger.error(
            "embed_chunks_task_timeout",
            document_id=doc_id,
            timeout_seconds=600,
            embedded_count=embedded_count,
        )
        # Save progress so we can resume from where we left off
        if progress_tracker and stage_progress:
            progress_tracker.save_progress(stage_progress, force=True)
        _mark_job_failed(job_id, "Embedding timeout exceeded (10 minutes)", "TIMEOUT", matter_id)  # P8 fix: was missing
        _release_pipeline_lock_safe(doc_id)
        raise PipelineTaskError(
            "Embedding timeout exceeded (10 minutes)",
            error_code="TIMEOUT",
            document_id=doc_id,
            job_id=job_id,
            matter_id=matter_id,
            stage="embedding",
        )

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
            from app.workers.tasks.pipeline_errors import PipelineTaskError
            logger.error(
                "embed_chunks_task_failed",
                document_id=doc_id,
                error=str(e),
            )
            _mark_job_failed(job_id, e.message, e.code, matter_id)  # P8 fix: was missing
            _release_pipeline_lock_safe(doc_id)
            raise PipelineTaskError(
                e.message,
                error_code=e.code,
                document_id=doc_id,
                job_id=job_id,
                matter_id=matter_id,
                stage="embedding",
            )

        raise

    except DocumentServiceError as e:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error(
            "embed_chunks_document_error",
            document_id=doc_id,
            error=str(e),
        )
        _mark_job_failed(job_id, e.message, e.code, matter_id)  # P8 fix: was missing
        _release_pipeline_lock_safe(doc_id)
        raise PipelineTaskError(
            e.message,
            error_code=e.code,
            document_id=doc_id,
            job_id=job_id,
            matter_id=matter_id,
            stage="embedding",
        )

    except Exception as e:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error(
            "embed_chunks_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", matter_id)  # P8 fix: was missing
        _release_pipeline_lock_safe(doc_id)
        raise PipelineTaskError(
            str(e),
            error_code="UNEXPECTED_ERROR",
            document_id=doc_id,
            job_id=job_id,
            matter_id=matter_id,
            stage="embedding",
        )


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
    soft_time_limit=600,  # 10 minutes - LLM entity extraction
    time_limit=660,  # 11 minutes - hard kill
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
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error("extract_entities_no_document_id")
        raise PipelineTaskError(
            "No document_id provided",
            error_code="NO_DOCUMENT_ID",
            stage="entity_extraction",
        )

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
        # On Celery retry, bypass idempotency to allow partial re-extraction
        is_celery_retry = self.request.retries > 0
        has_mentions, mention_count = _check_entity_mentions_exist_for_document(doc_id)
        if has_mentions and not force and not is_celery_retry:
            logger.info(
                "extract_entities_idempotency_skip",
                document_id=doc_id,
                matter_id=matter_id,
                mention_count=mention_count,
                reason="Entity mentions already exist for this document",
            )
            # Update job stage to mark entity_extraction complete
            _update_job_stage_complete(job_id, "entity_extraction", matter_id)
            # Dispatch downstream tasks (citations, dates, aliases) — they have their own idempotency
            _dispatch_post_entity_tasks(doc_id, matter_id, job_id)
            return {
                "status": "entities_extracted",
                "document_id": doc_id,
                "entities_extracted": mention_count,
                "reason": "Idempotency check: entity mentions already exist for document",
                "job_id": job_id,
            }

        if is_celery_retry and has_mentions:
            logger.warning(
                "extract_entities_retry_bypassing_idempotency",
                document_id=doc_id,
                retry_number=self.request.retries,
                existing_mention_count=mention_count,
                reason="Previous run may have been partial; re-extracting remaining chunks",
            )

        # F1: Try shared chunk cache first (avoids Supabase read)
        from app.services.chunk_service import get_cached_chunks
        chunks = get_cached_chunks(doc_id, chunk_type_filter="child")

        if chunks is None:
            # Cache miss — fall back to Supabase
            # Get all chunks for this document (child chunks for more granular extraction)
            # Include bbox_ids for spatial data passthrough (gold standard pattern)
            response = (
                client.table("chunks")
                .select("id, content, chunk_type, page_number, bbox_ids")
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

                                # Save relationship edges (name→ID resolution)
                                if result.relationships and saved:
                                    name_to_id = {
                                        node.canonical_name.lower(): node.id
                                        for node in saved
                                    }
                                    edges = []
                                    for rel in result.relationships:
                                        src_id = name_to_id.get(rel.source.lower())
                                        tgt_id = name_to_id.get(rel.target.lower())
                                        if src_id and tgt_id:
                                            edges.append(EntityEdgeCreate(
                                                source_entity_id=src_id,
                                                target_entity_id=tgt_id,
                                                relationship_type=rel.type,
                                                matter_id=matter_id,
                                                confidence=rel.confidence,
                                                metadata={"description": rel.description} if rel.description else {},
                                            ))
                                    if edges:
                                        await graph_service.save_edges(
                                            matter_id=matter_id,
                                            edges=edges,
                                        )

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
                        # Extract bbox_ids and convert to string list for gold standard pattern
                        chunk_bbox_ids = chunk.get("bbox_ids") or []
                        bbox_ids_list = [str(b) for b in chunk_bbox_ids] if chunk_bbox_ids else []

                        extraction_result = await extractor.extract_entities(
                            text=chunk["content"],
                            document_id=doc_id,
                            matter_id=matter_id,
                            chunk_id=chunk_id,
                            page_number=chunk.get("page_number"),
                            bbox_ids=bbox_ids_list,
                        )

                        entities_count = 0
                        relationships_count = 0

                        if extraction_result.entities:
                            saved_entities = await graph_service.save_entities(
                                matter_id=matter_id,
                                extraction_result=extraction_result,
                            )
                            entities_count = len(saved_entities)

                            # Save relationship edges (name→ID resolution)
                            if extraction_result.relationships and saved_entities:
                                name_to_id = {
                                    node.canonical_name.lower(): node.id
                                    for node in saved_entities
                                }
                                edges = []
                                for rel in extraction_result.relationships:
                                    src_id = name_to_id.get(rel.source.lower())
                                    tgt_id = name_to_id.get(rel.target.lower())
                                    if src_id and tgt_id:
                                        edges.append(EntityEdgeCreate(
                                            source_entity_id=src_id,
                                            target_entity_id=tgt_id,
                                            relationship_type=rel.type,
                                            matter_id=matter_id,
                                            confidence=rel.confidence,
                                            metadata={"description": rel.description} if rel.description else {},
                                        ))
                                if edges:
                                    await graph_service.save_edges(
                                        matter_id=matter_id,
                                        edges=edges,
                                    )

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
                                await progress_tracker.save_progress_async(stage_progress, force=True)
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
                        await progress_tracker.save_progress_async(stage_progress)

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
                        await progress_tracker.save_progress_async(stage_progress)

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
            _run_async(_extract_entities_async(), timeout=540)  # Below soft_time_limit=600
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

        # Fan out: dispatch citations, dates, and aliases in parallel
        _dispatch_post_entity_tasks(doc_id, matter_id, job_id)

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

    except SoftTimeLimitExceeded:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        # Task timeout - mark as failed for retry later
        logger.error(
            "extract_entities_task_timeout",
            document_id=doc_id,
            timeout_seconds=600,
        )
        # Save progress so we can resume from where we left off
        if progress_tracker and stage_progress:
            progress_tracker.save_progress(stage_progress, force=True)
        _mark_job_failed(job_id, "Entity extraction timeout exceeded (10 minutes)", "TIMEOUT", matter_id)  # P8 fix: was missing
        _release_pipeline_lock_safe(doc_id)
        raise PipelineTaskError(
            "Entity extraction timeout exceeded (10 minutes)",
            error_code="TIMEOUT",
            document_id=doc_id,
            job_id=job_id,
            matter_id=matter_id,
            stage="entity_extraction",
        )

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
            from app.workers.tasks.pipeline_errors import PipelineTaskError
            logger.error(
                "extract_entities_task_failed",
                document_id=doc_id,
                error=str(e),
            )
            _mark_job_failed(job_id, e.message, e.code, matter_id)  # P8 fix: was missing
            _release_pipeline_lock_safe(doc_id)
            raise PipelineTaskError(
                e.message,
                error_code=e.code,
                document_id=doc_id,
                job_id=job_id,
                matter_id=matter_id,
                stage="entity_extraction",
            )

        raise

    except DocumentServiceError as e:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error(
            "extract_entities_document_error",
            document_id=doc_id,
            error=str(e),
        )
        _mark_job_failed(job_id, e.message, e.code, matter_id)  # P8 fix: was missing
        _release_pipeline_lock_safe(doc_id)
        raise PipelineTaskError(
            e.message,
            error_code=e.code,
            document_id=doc_id,
            job_id=job_id,
            matter_id=matter_id,
            stage="entity_extraction",
        )

    except Exception as e:
        from app.workers.tasks.pipeline_errors import PipelineTaskError
        logger.error(
            "extract_entities_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        _mark_job_failed(job_id, str(e), "UNEXPECTED_ERROR", matter_id)  # P8 fix: was missing
        _release_pipeline_lock_safe(doc_id)
        raise PipelineTaskError(
            str(e),
            error_code="UNEXPECTED_ERROR",
            document_id=doc_id,
            job_id=job_id,
            matter_id=matter_id,
            stage="entity_extraction",
        )


# =============================================================================
# Downstream Task Dispatch Helper
# =============================================================================


def _dispatch_post_entity_tasks(
    document_id: str,
    matter_id: str,
    job_id: str | None = None,
) -> dict[str, list[str]]:
    """Dispatch downstream tasks after entity extraction completes.

    Fan-out: triggers citation extraction, date extraction, and alias resolution
    in parallel. Citations and dates don't need aliases, so we decouple them
    from the alias resolution gate.

    The job completion chain (extract_citations -> detect_contradictions ->
    _mark_job_completed) continues independently of alias resolution.

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

    # Build prev_result for citation extraction
    prev_result = {
        "document_id": document_id,
        "status": "entities_extracted",
        "job_id": job_id,
    }

    # Task 1: Citation extraction (use send_task to avoid forward reference)
    # NOTE: no explicit queue= — task_routes in celery.py is the single source of truth
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
        logger.error(
            "extract_citations_dispatch_failed",
            document_id=document_id,
            error=str(e),
        )
        # DPP-014: extract_citations gates job completion (citations → contradictions → _mark_job_completed).
        # If dispatch fails, mark job failed immediately — don't let it silently orphan.
        _mark_job_failed(job_id, f"Failed to dispatch extract_citations: {e}", "DISPATCH_FAILED", matter_id)
        _release_pipeline_lock_safe(document_id)

    # Task 2: Date extraction (with auto-classification enabled)
    # NOTE: no explicit queue= — task_routes in celery.py is the single source of truth
    try:
        extract_dates_from_document.apply_async(
            kwargs={
                "document_id": document_id,
                "matter_id": matter_id,
                "auto_classify": True,
            },
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

    # Task 3: Alias resolution (runs independently, no longer gates downstream)
    # NOTE: no explicit queue= — task_routes in celery.py is the single source of truth
    try:
        celery_app.send_task(
            "app.workers.tasks.document_tasks.resolve_aliases",
            kwargs={
                "document_id": document_id,
            },
        )
        triggered_tasks.append("resolve_aliases")
        logger.debug("resolve_aliases_dispatched", document_id=document_id)
    except Exception as e:
        failed_tasks.append("resolve_aliases")
        logger.warning(
            "resolve_aliases_dispatch_failed",
            document_id=document_id,
            error=str(e),
        )

    logger.info(
        "post_entity_tasks_dispatched",
        document_id=document_id,
        matter_id=matter_id,
        job_id=job_id,
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


# =============================================================================
# Alias Resolution — Fan-Out/Fan-In (WPS-001 Layer 4)
#
# Three-phase decomposition replaces the monolithic 30-minute resolve_aliases:
#
# Phase 1 (resolve_aliases):     CPU-only. Fetches entities, finds pairs,
#                                 creates high-confidence edges inline,
#                                 dispatches Phase 2 batches for medium pairs.
#                                 ~10 seconds, holds greenlet briefly.
#
# Phase 2 (resolve_aliases_batch): LLM-bound. Each batch analyzes ~20 pairs
#                                   via Gemini. ~30-120 seconds per batch.
#                                   Parallel batches on low queue (heavy worker).
#                                   Last batch to finish triggers Phase 3.
#
# Phase 3 (resolve_aliases_finalize): CPU-only. Applies transitive closure,
#                                      persists edges, updates alias arrays.
#                                      Single convergence point — no race on
#                                      add_alias_to_entity (fixes hostile review G2).
#
# Completion tracking: Redis INCR counter. Phase 1 sets total. Each Phase 2
# INCRs done. When done == total, that batch dispatches Phase 3. No polling,
# no chord (task_ignore_result=True globally).
#
# Key properties preserved:
# - Aliases are DECOUPLED from pipeline completion (no _mark_job_completed)
# - All DB writes use UPSERT (idempotent)
# - Failure in any phase does NOT block document processing
# =============================================================================

# Redis key helpers for fan-out coordination
_ALIAS_KEY_PREFIX = "alias_resolve"
_ALIAS_KEY_TTL = 7200  # 2 hours — enough for largest matters


def _alias_redis_key(document_id: str, suffix: str) -> str:
    """Build a Redis key for alias resolution fan-out coordination."""
    return f"{_ALIAS_KEY_PREFIX}:{document_id}:{suffix}"


# Context cap: max chars per entity to prevent unbounded memory growth (Risk B2)
_MAX_CONTEXT_CHARS_PER_ENTITY = 2000


@celery_app.task(
    name="app.workers.tasks.document_tasks.resolve_aliases",
    bind=True,
    autoretry_for=(AliasResolutionError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
    soft_time_limit=300,   # 5 minutes — Phase 1 is CPU-only, should be fast
    time_limit=360,
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
    """Phase 1: Find alias pairs and dispatch LLM batches.

    WPS-001 Layer 4 fan-out: this task is CPU-only (~10s). It finds high/medium
    similarity pairs, creates high-confidence edges inline, and dispatches
    Phase 2 batches (resolve_aliases_batch) for medium-confidence pairs.

    Aliases are DECOUPLED from pipeline completion — failure here does NOT
    block document processing.
    """
    from app.services.distributed_lock import get_sync_redis_client
    from app.services.supabase.client import get_service_client

    # --- Parameter extraction (unchanged) ---
    doc_id = document_id
    job_id: str | None = None
    matter_id: str | None = None

    if prev_result:
        if doc_id is None:
            doc_id = prev_result.get("document_id")  # type: ignore[assignment]
        job_id = prev_result.get("job_id")  # type: ignore[assignment]

    if job_id is None and doc_id:
        job_id = _lookup_job_id_for_document(doc_id)

    if not doc_id:
        logger.error("resolve_aliases_no_document_id")
        return {
            "status": "alias_resolution_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    if prev_result:
        prev_status = prev_result.get("status")
        if prev_status not in ("entities_extracted",):
            logger.info("resolve_aliases_skipped", document_id=doc_id, prev_status=prev_status)
            return {"status": "alias_resolution_skipped", "document_id": doc_id, "job_id": job_id}

    # --- Dedup guard (hostile review C1): prevent concurrent runs for same doc ---
    redis_client = get_sync_redis_client()
    dedup_key = _alias_redis_key(doc_id, "running")
    # SET NX with 30-min TTL — if key exists, another task is already running
    if not redis_client.set(dedup_key, "1", nx=True, ex=1800):
        logger.info("resolve_aliases_dedup_skip", document_id=doc_id)
        return {"status": "alias_resolution_skipped", "document_id": doc_id,
                "reason": "Another resolve_aliases is already running", "job_id": job_id}

    doc_service = document_service or get_document_service()
    resolver = entity_resolver or get_entity_resolver()
    graph_service = mig_graph_service or get_mig_graph_service()

    logger.info("resolve_aliases_phase1_started", document_id=doc_id, retry_count=self.request.retries)

    try:
        _, matter_id = doc_service.get_document_for_processing(doc_id)
        _update_job_stage_start(job_id, "alias_resolution", matter_id)

        client = get_service_client()
        if client is None:
            raise AliasResolutionError(message="Database client not configured", code="DATABASE_NOT_CONFIGURED")

        async def _phase1_async():
            # --- Fetch ALL entities with pagination (fixes hostile review B3: 1000 cap) ---
            all_entities = []
            page = 1
            per_page = 500
            while True:
                batch, total = await graph_service.get_entities_by_matter(
                    matter_id=matter_id, page=page, per_page=per_page,
                )
                all_entities.extend(batch)
                if len(all_entities) >= total or not batch:
                    break
                page += 1

            if not all_entities:
                return None

            # --- Incremental: get entity IDs from this document only ---
            doc_entity_ids: set[str] | None = None
            if doc_id:
                doc_mentions_resp = client.table("entity_mentions").select(
                    "entity_id"
                ).eq("document_id", doc_id).execute()
                if doc_mentions_resp.data:
                    doc_entity_ids = {m["entity_id"] for m in doc_mentions_resp.data}

            logger.info(
                "resolve_aliases_phase1_entities",
                document_id=doc_id,
                total_entities=len(all_entities),
                document_entities=len(doc_entity_ids) if doc_entity_ids else 0,
            )

            # --- Build entity contexts (with per-entity cap — Risk B2) ---
            entity_contexts: dict[str, str] = {}
            matter_entity_ids = [e.id for e in all_entities]
            for batch_start in range(0, len(matter_entity_ids), 100):
                batch_ids = matter_entity_ids[batch_start:batch_start + 100]
                mentions_response = client.table("entity_mentions").select(
                    "entity_id, context"
                ).in_("entity_id", batch_ids).execute()
                if mentions_response.data:
                    for mention in mentions_response.data:
                        eid = mention["entity_id"]
                        ctx = mention.get("context") or ""
                        if eid not in entity_contexts:
                            entity_contexts[eid] = ctx[:_MAX_CONTEXT_CHARS_PER_ENTITY]
                        else:
                            current = entity_contexts[eid]
                            if len(current) < _MAX_CONTEXT_CHARS_PER_ENTITY:
                                entity_contexts[eid] = (current + " | " + ctx)[:_MAX_CONTEXT_CHARS_PER_ENTITY]

            # --- Phase 1: CPU-only pair finding (high + medium) ---
            # Use resolver's find_potential_aliases for each source entity
            from app.models.entity import EntityType
            from app.services.mig.entity_resolver import (
                MEDIUM_SIMILARITY_THRESHOLD,
            )

            entities_by_type: dict[EntityType, list] = {}
            for entity in all_entities:
                entities_by_type.setdefault(entity.entity_type, []).append(entity)

            high_confidence_edges = []
            medium_confidence_pairs = []
            skipped_low = 0

            for _etype, type_entities in entities_by_type.items():
                if len(type_entities) < 2:
                    continue

                source_entities = (
                    [e for e in type_entities if e.id in doc_entity_ids]
                    if doc_entity_ids else type_entities
                )
                seen_pairs: set[tuple[str, str]] = set()

                for entity in source_entities:
                    candidates = resolver.find_potential_aliases(entity, type_entities)
                    for candidate in candidates:
                        pair_key = tuple(sorted([candidate.entity_id, candidate.candidate_entity_id]))
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)

                        if candidate.is_auto_linked:
                            high_confidence_edges.append({
                                "source_entity_id": candidate.entity_id,
                                "target_entity_id": candidate.candidate_entity_id,
                                "confidence": candidate.similarity_score,
                                "metadata": {
                                    "auto_linked": True,
                                    "name_similarity": candidate.name_similarity,
                                    "component_similarity": candidate.component_similarity,
                                },
                            })
                        elif candidate.similarity_score >= MEDIUM_SIMILARITY_THRESHOLD:
                            medium_confidence_pairs.append({
                                "entity_id": candidate.entity_id,
                                "entity_name": candidate.entity_name,
                                "candidate_entity_id": candidate.candidate_entity_id,
                                "candidate_name": candidate.candidate_name,
                                "similarity_score": candidate.similarity_score,
                                "name_similarity": candidate.name_similarity,
                                "context1": entity_contexts.get(candidate.entity_id, ""),
                                "context2": entity_contexts.get(candidate.candidate_entity_id, ""),
                            })
                        else:
                            skipped_low += 1

            # --- Create high-confidence edges inline (CPU, fast) ---
            for edge_data in high_confidence_edges:
                await graph_service.create_alias_edge(
                    matter_id=matter_id,
                    source_id=edge_data["source_entity_id"],
                    target_id=edge_data["target_entity_id"],
                    confidence=edge_data["confidence"],
                    metadata=edge_data["metadata"],
                )

            return {
                "high_confidence_count": len(high_confidence_edges),
                "medium_pairs": medium_confidence_pairs,
                "skipped_low": skipped_low,
                "total_entities": len(all_entities),
                "high_confidence_edges": high_confidence_edges,
            }

        result = _run_async(_phase1_async(), timeout=240)

        if result is None:
            _update_job_stage_complete(job_id, "alias_resolution", matter_id)
            redis_client.delete(dedup_key)
            logger.info("resolve_aliases_no_entities", document_id=doc_id, matter_id=matter_id)
            return {"status": "alias_resolution_complete", "document_id": doc_id,
                    "aliases_created": 0, "reason": "No entities", "job_id": job_id}

        medium_pairs = result["medium_pairs"]
        high_count = result["high_confidence_count"]

        # --- Dispatch Phase 2 batches for medium-confidence pairs ---
        if not medium_pairs:
            # No medium pairs — skip to finalize with just high-confidence edges
            _dispatch_alias_finalize(
                doc_id, matter_id, job_id,
                high_confidence_edges=result["high_confidence_edges"],
                batch_results=[],
                redis_client=redis_client,
            )
            logger.info(
                "resolve_aliases_phase1_complete_no_medium",
                document_id=doc_id, high_confidence=high_count,
                skipped_low=result["skipped_low"],
            )
            return {"status": "alias_phase1_complete", "document_id": doc_id,
                    "high_confidence": high_count, "medium_batches": 0, "job_id": job_id}

        # Split medium pairs into batches of 20 (2x CONTEXT_ANALYSIS_BATCH_SIZE for fewer tasks)
        FANOUT_BATCH_SIZE = 20
        batches = [
            medium_pairs[i:i + FANOUT_BATCH_SIZE]
            for i in range(0, len(medium_pairs), FANOUT_BATCH_SIZE)
        ]

        # Store high-confidence edges in Redis for Phase 3
        import json
        high_edges_key = _alias_redis_key(doc_id, "high_edges")
        redis_client.set(high_edges_key, json.dumps(result["high_confidence_edges"]), ex=_ALIAS_KEY_TTL)

        # Set total batch count for completion tracking
        total_key = _alias_redis_key(doc_id, "total")
        done_key = _alias_redis_key(doc_id, "done")
        redis_client.set(total_key, str(len(batches)), ex=_ALIAS_KEY_TTL)
        redis_client.delete(done_key)  # Reset counter

        # Store matter_id and job_id for Phase 3
        meta_key = _alias_redis_key(doc_id, "meta")
        redis_client.set(meta_key, json.dumps({"matter_id": matter_id, "job_id": job_id}), ex=_ALIAS_KEY_TTL)

        # Dispatch Phase 2 batches
        from app.workers.celery import celery_app as _celery_app
        for batch_idx, batch in enumerate(batches):
            _celery_app.send_task(
                "app.workers.tasks.document_tasks.resolve_aliases_batch",
                kwargs={
                    "document_id": doc_id,
                    "matter_id": matter_id,
                    "batch_index": batch_idx,
                    "pairs": batch,
                },
            )

        logger.info(
            "resolve_aliases_phase1_complete",
            document_id=doc_id,
            matter_id=matter_id,
            high_confidence=high_count,
            medium_batches=len(batches),
            medium_pairs=len(medium_pairs),
            skipped_low=result["skipped_low"],
            total_entities=result["total_entities"],
        )

        return {
            "status": "alias_phase1_complete",
            "document_id": doc_id,
            "high_confidence": high_count,
            "medium_batches": len(batches),
            "medium_pairs": len(medium_pairs),
            "job_id": job_id,
        }

    except AliasResolutionError as e:
        retry_count = self.request.retries
        logger.warning("resolve_aliases_phase1_retry", document_id=doc_id,
                        retry_count=retry_count, error=str(e))
        _update_job_stage_failure(job_id, "alias_resolution", str(e), e.code, matter_id)
        redis_client.delete(dedup_key)
        if retry_count >= 3:
            return {"status": "alias_resolution_failed", "document_id": doc_id,
                    "error_code": e.code, "error_message": e.message, "job_id": job_id}
        raise

    except (TimeoutError, SoftTimeLimitExceeded):
        logger.warning("resolve_aliases_phase1_timeout", document_id=doc_id, matter_id=matter_id)
        _update_job_stage_failure(job_id, "alias_resolution", "Phase 1 timed out", "TIMEOUT", matter_id)
        redis_client.delete(dedup_key)
        return {"status": "alias_resolution_failed", "document_id": doc_id,
                "error_code": "TIMEOUT", "job_id": job_id}

    except DocumentServiceError as e:
        logger.error("resolve_aliases_document_error", document_id=doc_id, error=str(e))
        _update_job_stage_failure(job_id, "alias_resolution", e.message, e.code, matter_id)
        redis_client.delete(dedup_key)
        return {"status": "alias_resolution_failed", "document_id": doc_id,
                "error_code": e.code, "error_message": e.message, "job_id": job_id}

    except Exception as e:
        logger.error("resolve_aliases_phase1_error", document_id=doc_id,
                     error=str(e), error_type=type(e).__name__)
        _update_job_stage_failure(job_id, "alias_resolution", str(e), "UNEXPECTED_ERROR", matter_id)
        redis_client.delete(dedup_key)
        return {"status": "alias_resolution_failed", "document_id": doc_id,
                "error_code": "UNEXPECTED_ERROR", "error_message": str(e), "job_id": job_id}


def _dispatch_alias_finalize(
    document_id: str,
    matter_id: str,
    job_id: str | None,
    high_confidence_edges: list[dict],
    batch_results: list[dict],
    redis_client=None,
) -> None:
    """Dispatch Phase 3 finalization. Called when all Phase 2 batches are done,
    or immediately when there are no medium-confidence pairs."""
    from app.workers.celery import celery_app as _celery_app

    _celery_app.send_task(
        "app.workers.tasks.document_tasks.resolve_aliases_finalize",
        kwargs={
            "document_id": document_id,
            "matter_id": matter_id,
            "job_id": job_id,
        },
    )


@celery_app.task(
    name="app.workers.tasks.document_tasks.resolve_aliases_batch",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
    soft_time_limit=180,   # 3 minutes per batch — ~20 pairs, 2 Gemini calls
    time_limit=240,
)  # type: ignore[misc]
def resolve_aliases_batch(
    self,  # type: ignore[no-untyped-def]
    document_id: str | None = None,
    matter_id: str | None = None,
    batch_index: int = 0,
    pairs: list[dict] | None = None,
) -> dict:
    """Phase 2: Analyze medium-confidence pairs via Gemini.

    Each batch handles ~20 pairs. Makes 2 Gemini API calls (10 pairs each).
    Stores results in Redis. When all batches complete (Redis counter),
    the last batch dispatches Phase 3 (resolve_aliases_finalize).

    Runs on low queue (heavy worker, 10 greenlets). ~30-120 seconds per batch.
    """
    import json

    from app.services.distributed_lock import get_sync_redis_client

    if not document_id or not pairs:
        return {"status": "skipped", "reason": "missing args"}

    redis_client = get_sync_redis_client()
    resolver = get_entity_resolver()
    batch_failed = False
    gemini_failures = 0

    logger.info("resolve_aliases_batch_started", document_id=document_id,
                batch_index=batch_index, pairs_count=len(pairs))

    try:
        # Build batch_pairs in the format analyze_batch_context expects
        batch_pairs = []
        for i, pair in enumerate(pairs):
            batch_pairs.append({
                "pair_id": f"batch{batch_index}_pair{i}",
                "name1": pair["entity_name"],
                "context1": pair.get("context1", ""),
                "name2": pair["candidate_name"],
                "context2": pair.get("context2", ""),
            })

        # Call Gemini via the entity resolver's batch analysis
        # Split into sub-batches of CONTEXT_ANALYSIS_BATCH_SIZE (10)
        from app.services.mig.entity_resolver import CONTEXT_ANALYSIS_BATCH_SIZE

        async def _analyze_batches():
            nonlocal gemini_failures
            all_confidences: dict[str, float] = {}
            sub_batches = [
                batch_pairs[i:i + CONTEXT_ANALYSIS_BATCH_SIZE]
                for i in range(0, len(batch_pairs), CONTEXT_ANALYSIS_BATCH_SIZE)
            ]
            for sub_batch in sub_batches:
                try:
                    result = await resolver.analyze_batch_context(sub_batch, matter_id=matter_id)
                    all_confidences.update(result)
                except Exception as e:
                    gemini_failures += 1
                    logger.warning("resolve_aliases_batch_gemini_failed",
                                   batch_index=batch_index, error=str(e))
                    # Default to 0.5 for failed sub-batches (safe — rejects, not false-positives)
                    for p in sub_batch:
                        all_confidences[p["pair_id"]] = 0.5
            return all_confidences

        confidences = _run_async(_analyze_batches(), timeout=150)

        # Build results: pair data + confidence scores
        batch_results = []
        for i, pair in enumerate(pairs):
            pair_id = f"batch{batch_index}_pair{i}"
            confidence = confidences.get(pair_id, 0.5)
            batch_results.append({
                "entity_id": pair["entity_id"],
                "candidate_entity_id": pair["candidate_entity_id"],
                "entity_name": pair["entity_name"],
                "candidate_name": pair["candidate_name"],
                "similarity_score": pair["similarity_score"],
                "name_similarity": pair["name_similarity"],
                "context_confidence": confidence,
            })

        # Store results in Redis list
        results_key = _alias_redis_key(document_id, "results")
        redis_client.rpush(results_key, json.dumps(batch_results))
        redis_client.expire(results_key, _ALIAS_KEY_TTL)

    except Exception as e:
        batch_failed = True
        logger.error("resolve_aliases_batch_failed", document_id=document_id,
                     batch_index=batch_index, error=str(e), error_type=type(e).__name__)
        # Store empty result so counter still advances — partial results are better than stuck
        results_key = _alias_redis_key(document_id, "results")
        redis_client.rpush(results_key, json.dumps([]))
        redis_client.expire(results_key, _ALIAS_KEY_TTL)

    # --- Increment done counter. If done == total, dispatch Phase 3 ---
    done_key = _alias_redis_key(document_id, "done")
    total_key = _alias_redis_key(document_id, "total")
    done_count = redis_client.incr(done_key)
    redis_client.expire(done_key, _ALIAS_KEY_TTL)

    total_raw = redis_client.get(total_key)
    total_count = int(total_raw) if total_raw else 0

    logger.info("resolve_aliases_batch_complete", document_id=document_id,
                batch_index=batch_index, done=done_count, total=total_count,
                gemini_failures=gemini_failures, batch_failed=batch_failed)

    if done_count >= total_count and total_count > 0:
        # Last batch — dispatch Phase 3 finalize
        meta_key = _alias_redis_key(document_id, "meta")
        meta_raw = redis_client.get(meta_key)
        meta = json.loads(meta_raw) if meta_raw else {}

        from app.workers.celery import celery_app as _celery_app
        _celery_app.send_task(
            "app.workers.tasks.document_tasks.resolve_aliases_finalize",
            kwargs={
                "document_id": document_id,
                "matter_id": meta.get("matter_id", matter_id),
                "job_id": meta.get("job_id"),
            },
        )
        logger.info("resolve_aliases_finalize_dispatched", document_id=document_id)

    return {"status": "batch_complete", "document_id": document_id,
            "batch_index": batch_index, "pairs_analyzed": len(pairs)}


@celery_app.task(
    name="app.workers.tasks.document_tasks.resolve_aliases_finalize",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
    soft_time_limit=180,   # 3 minutes — transitive closure + DB writes
    time_limit=240,
)  # type: ignore[misc]
def resolve_aliases_finalize(
    self,  # type: ignore[no-untyped-def]
    document_id: str | None = None,
    matter_id: str | None = None,
    job_id: str | None = None,
) -> dict:
    """Phase 3: Apply transitive closure and persist all edges.

    Single convergence point for all alias writes. This fixes the hostile
    review G2 race condition: add_alias_to_entity is called from ONE task
    (this one), never concurrently.

    Reads high-confidence edges and Phase 2 batch results from Redis.
    Applies transitive closure. Persists edges via UPSERT. Updates alias
    arrays on canonical entities. Cleans up Redis keys.
    """
    import json

    from app.services.distributed_lock import get_sync_redis_client
    from app.services.mig.entity_resolver import CONTEXT_CONFIDENCE_THRESHOLD

    if not document_id or not matter_id:
        return {"status": "skipped", "reason": "missing args"}

    redis_client = get_sync_redis_client()
    graph_service = get_mig_graph_service()

    logger.info("resolve_aliases_finalize_started", document_id=document_id, matter_id=matter_id)

    try:
        # --- Read high-confidence edges from Redis ---
        high_edges_key = _alias_redis_key(document_id, "high_edges")
        high_edges_raw = redis_client.get(high_edges_key)
        high_edges = json.loads(high_edges_raw) if high_edges_raw else []

        # --- Read Phase 2 batch results from Redis ---
        results_key = _alias_redis_key(document_id, "results")
        all_results_raw = redis_client.lrange(results_key, 0, -1)
        medium_results = []
        for raw in all_results_raw:
            batch = json.loads(raw) if raw else []
            medium_results.extend(batch)

        # --- Filter medium results by confidence threshold ---
        from app.models.entity import RelationshipType
        edges_to_create = []

        # High-confidence edges (already decided in Phase 1)
        for edge_data in high_edges:
            edges_to_create.append(EntityEdgeCreate(
                source_entity_id=edge_data["source_entity_id"],
                target_entity_id=edge_data["target_entity_id"],
                relationship_type=RelationshipType.ALIAS_OF,
                matter_id=matter_id,
                confidence=edge_data["confidence"],
                metadata=edge_data.get("metadata", {}),
            ))

        # Medium-confidence edges (decided by Phase 2 Gemini analysis)
        medium_links = 0
        for pair_result in medium_results:
            context_confidence = pair_result.get("context_confidence", 0.5)
            similarity = pair_result.get("similarity_score", 0.5)
            final_score = (similarity + context_confidence) / 2
            if final_score >= CONTEXT_CONFIDENCE_THRESHOLD:
                edges_to_create.append(EntityEdgeCreate(
                    source_entity_id=pair_result["entity_id"],
                    target_entity_id=pair_result["candidate_entity_id"],
                    relationship_type=RelationshipType.ALIAS_OF,
                    matter_id=matter_id,
                    confidence=final_score,
                    metadata={
                        "auto_linked": False,
                        "context_analyzed": True,
                        "name_similarity": pair_result.get("name_similarity", 0),
                        "context_confidence": context_confidence,
                    },
                ))
                medium_links += 1

        # --- Apply transitive closure ---
        resolver = get_entity_resolver()
        edges_to_create = resolver._apply_transitive_closure(edges_to_create, matter_id)

        # --- Persist edges and update alias arrays (single convergence point) ---
        async def _persist_edges():
            aliases_created = 0

            # Fetch entities once for mention_count comparison
            all_entities = []
            page = 1
            while True:
                batch, total = await graph_service.get_entities_by_matter(
                    matter_id=matter_id, page=page, per_page=500,
                )
                all_entities.extend(batch)
                if len(all_entities) >= total or not batch:
                    break
                page += 1

            entity_map = {e.id: e for e in all_entities}

            # Collect all alias updates to apply in bulk (fixes G2 race)
            alias_updates: dict[str, list[str]] = {}  # entity_id -> [alias_names]

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

                    source = entity_map.get(edge.source_entity_id)
                    target = entity_map.get(edge.target_entity_id)
                    if source and target:
                        if source.mention_count >= target.mention_count:
                            alias_updates.setdefault(source.id, []).append(target.canonical_name)
                        else:
                            alias_updates.setdefault(target.id, []).append(source.canonical_name)

            # Apply alias array updates — one call per entity, no concurrent race
            for entity_id, new_aliases in alias_updates.items():
                for alias_name in new_aliases:
                    await graph_service.add_alias_to_entity(
                        entity_id=entity_id,
                        matter_id=matter_id,
                        alias=alias_name,
                    )

            return aliases_created

        aliases_created = _run_async(_persist_edges(), timeout=150)

        # --- Broadcast completion + update job stage ---
        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="aliases_resolved",
            aliases_created=aliases_created,
        )
        _update_job_stage_complete(
            job_id, "alias_resolution", matter_id,
            metadata={"aliases_created": aliases_created, "medium_links": medium_links,
                      "high_links": len(high_edges)},
        )

        logger.info(
            "resolve_aliases_finalize_complete",
            document_id=document_id, matter_id=matter_id,
            aliases_created=aliases_created,
            high_confidence=len(high_edges),
            medium_links=medium_links,
            total_edges=len(edges_to_create),
        )

        return {
            "status": "aliases_resolved",
            "document_id": document_id,
            "aliases_created": aliases_created,
            "high_confidence": len(high_edges),
            "medium_links": medium_links,
            "job_id": job_id,
        }

    except Exception as e:
        logger.error("resolve_aliases_finalize_error", document_id=document_id,
                     error=str(e), error_type=type(e).__name__)
        _update_job_stage_failure(job_id, "alias_resolution", str(e), "FINALIZE_ERROR", matter_id)
        return {"status": "alias_resolution_failed", "document_id": document_id,
                "error_code": "FINALIZE_ERROR", "error_message": str(e), "job_id": job_id}

    finally:
        # --- Cleanup Redis keys ---
        try:
            for suffix in ("running", "total", "done", "results", "high_edges", "meta"):
                redis_client.delete(_alias_redis_key(document_id, suffix))
        except Exception:
            pass  # Best-effort cleanup, TTL ensures eventual cleanup


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
    soft_time_limit=600,  # 10 minutes - LLM citation extraction
    time_limit=660,  # 11 minutes - hard kill
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

    This task runs after entity extraction to identify Act references.
    Dispatched from extract_entities -> _dispatch_post_entity_tasks().

    Pipeline: OCR -> Validate -> Confidence -> Chunk -> Embed -> Entities -> **Extract Citations**

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

    # IDEMPOTENCY CHECK: Skip if citations already exist for this document
    # On Celery retry, bypass idempotency to allow partial re-extraction
    is_celery_retry = self.request.retries > 0
    client = get_service_client()
    citation_check = None
    if client:
        citation_check = client.table("citations").select("id", count="exact").eq(
            "source_document_id", doc_id
        ).execute()
    if citation_check and citation_check.count and citation_check.count > 0 and not is_celery_retry:
        logger.info(
            "extract_citations_idempotency_skip",
            document_id=doc_id,
            existing_count=citation_check.count,
        )
        # Get job_id for downstream dispatch
        job_id: str | None = None
        if prev_result:
            job_id = prev_result.get("job_id")  # type: ignore[assignment]
        if job_id is None:
            job_id = _lookup_job_id_for_document(doc_id)

        # Still dispatch contradiction detection (it may not have run yet)
        citation_result = {
            "status": "citations_extracted",
            "document_id": doc_id,
            "citations_extracted": citation_check.count,
            "job_id": job_id,
        }
        try:
            # Get matter_id for analysis_mode check
            doc_service_tmp = document_service or get_document_service()
            _, matter_id_tmp = doc_service_tmp.get_document_for_processing(doc_id)

            analysis_mode = "deep_analysis"
            try:
                matter_result = (
                    client.table("matters")
                    .select("analysis_mode")
                    .eq("id", matter_id_tmp)
                    .single()
                    .execute()
                )
                if matter_result.data:
                    analysis_mode = matter_result.data.get("analysis_mode", "deep_analysis")
            except Exception:
                pass

            if analysis_mode != "quick_scan":
                celery_app.send_task(
                    "app.workers.tasks.document_tasks.detect_contradictions",
                    kwargs={
                        "prev_result": citation_result,
                        "document_id": doc_id,
                    },
                    queue="default",
                )
                logger.debug("detect_contradictions_dispatched_from_idempotency", document_id=doc_id)
            else:
                # Mark contradiction stage as skipped
                _update_job_stage_complete(
                    job_id,
                    "contradiction_detection",
                    matter_id_tmp,
                    metadata={"skipped": True, "reason": "quick_scan mode"},
                )
        except Exception as dispatch_err:
            logger.warning(
                "detect_contradictions_dispatch_failed_idempotency",
                document_id=doc_id,
                error=str(dispatch_err),
            )

        return {
            "status": "citations_extracted",
            "document_id": doc_id,
            "citations_extracted": citation_check.count,
            "reason": "Idempotency check: citations already exist",
            "job_id": job_id,
        }

    if is_celery_retry and citation_check and citation_check.count and citation_check.count > 0:
        logger.warning(
            "extract_citations_retry_bypassing_idempotency",
            document_id=doc_id,
            retry_number=self.request.retries,
            existing_citation_count=citation_check.count,
            reason="Previous run may have been partial; re-extracting remaining chunks",
        )

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
            # Still dispatch detect_contradictions so the pipeline completes
            act_job_id = prev_result.get("job_id") if prev_result else None
            if act_job_id is None:
                act_job_id = _lookup_job_id_for_document(doc_id)
            try:
                celery_app.send_task(
                    "app.workers.tasks.document_tasks.detect_contradictions",
                    kwargs={
                        "prev_result": {"status": "citations_extracted", "document_id": doc_id, "job_id": act_job_id},
                        "document_id": doc_id,
                    },
                    queue="default",
                )
            except Exception:
                pass
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

        # F1: Try shared chunk cache first (avoids Supabase read)
        from app.services.chunk_service import get_cached_chunks
        chunks = get_cached_chunks(doc_id, chunk_type_filter="child")

        if chunks is None:
            # Cache miss — fall back to Supabase
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
            # Still dispatch detect_contradictions (the terminal task that marks
            # the job as COMPLETED). Without this, documents with 0 chunks
            # never transition to 'completed' status.
            citation_result = {
                "status": "citations_extracted",
                "document_id": doc_id,
                "citations_extracted": 0,
                "job_id": job_id,
            }
            try:
                celery_app.send_task(
                    "app.workers.tasks.document_tasks.detect_contradictions",
                    kwargs={
                        "prev_result": citation_result,
                        "document_id": doc_id,
                    },
                    queue="default",
                )
                logger.debug("detect_contradictions_dispatched_no_chunks", document_id=doc_id)
            except Exception as dispatch_err:
                logger.warning(
                    "detect_contradictions_dispatch_failed_no_chunks",
                    document_id=doc_id,
                    error=str(dispatch_err),
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

        # B1: Determine LLM batch size (citation_batch_size chunks per Gemini call)
        from app.core.config import get_settings as _get_settings
        _citation_settings = _get_settings()
        llm_batch_size = _citation_settings.citation_batch_size if _citation_settings.citation_batching_enabled else 1

        # Process all batches in a single async context
        async def _extract_citations_async():
            nonlocal total_citations, failed_chunks, skipped_chunks

            for i in range(0, len(chunks), CITATION_EXTRACTION_BATCH_SIZE):
                batch = chunks[i : i + CITATION_EXTRACTION_BATCH_SIZE]

                # Filter out already-processed chunks
                pending_chunks = []
                for chunk in batch:
                    chunk_id = chunk["id"]
                    if chunk_id in already_processed:
                        skipped_chunks += 1
                    else:
                        pending_chunks.append(chunk)

                # B1: Process pending chunks in LLM batches of citation_batch_size
                for j in range(0, len(pending_chunks), llm_batch_size):
                    llm_batch = pending_chunks[j : j + llm_batch_size]

                    try:
                        # Extract citations from batch (single Gemini call for N chunks)
                        batch_results = extractor.extract_from_batch_sync(
                            chunks=llm_batch,
                            document_id=doc_id,
                            matter_id=matter_id,
                        )

                        # Process each result
                        for chunk, extraction_result in zip(llm_batch, batch_results):
                            chunk_id = chunk["id"]

                            if extraction_result.citations:
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

                            if stage_progress:
                                stage_progress.mark_processed(chunk_id)

                    except CitationExtractorError as e:
                        for chunk in llm_batch:
                            if stage_progress:
                                stage_progress.mark_failed(chunk["id"], str(e))

                        if e.is_retryable:
                            if progress_tracker and stage_progress:
                                await progress_tracker.save_progress_async(stage_progress, force=True)
                            raise
                        logger.warning(
                            "extract_citations_batch_failed",
                            document_id=doc_id,
                            batch_chunk_count=len(llm_batch),
                            error=str(e),
                        )
                        failed_chunks += len(llm_batch)
                    except Exception as e:
                        logger.warning(
                            "extract_citations_batch_error",
                            document_id=doc_id,
                            batch_chunk_count=len(llm_batch),
                            error=str(e),
                        )
                        failed_chunks += len(llm_batch)
                        for chunk in llm_batch:
                            if stage_progress:
                                stage_progress.mark_failed(chunk["id"], str(e))

                # Persist partial progress periodically
                if progress_tracker and stage_progress:
                    await progress_tracker.save_progress_async(stage_progress)

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
            _run_async(_extract_citations_async(), timeout=540)  # Below soft_time_limit=600
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

        # BUG-015: Mark citation_verification as complete in the pipeline.
        # Citation verification runs asynchronously via validate_acts_for_matter
        # (background task on low-priority queue) and should not block progress.
        _update_job_stage_complete(
            job_id,
            "citation_verification",
            matter_id,
            metadata={"async": True, "note": "runs in background via act validation"},
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

        # Story 6.4: Check analysis_mode before dispatching contradiction detection
        # Quick Scan mode skips contradiction detection for faster processing
        analysis_mode = "deep_analysis"  # Default to deep_analysis
        try:
            matter_result = (
                client.table("matters")
                .select("analysis_mode")
                .eq("id", matter_id)
                .single()
                .execute()
            )
            if matter_result.data:
                analysis_mode = matter_result.data.get("analysis_mode", "deep_analysis")
        except Exception as mode_error:
            logger.warning(
                "analysis_mode_fetch_failed",
                matter_id=matter_id,
                error=str(mode_error),
            )

        # Dispatch contradiction detection task (skip for quick_scan mode per AC 6.4.2)
        if analysis_mode == "quick_scan":
            logger.info(
                "detect_contradictions_skipped_quick_scan",
                document_id=doc_id,
                matter_id=matter_id,
                analysis_mode=analysis_mode,
            )
            # Mark contradiction stage as skipped in job tracking
            _update_job_stage_complete(
                job_id,
                "contradiction_detection",
                matter_id,
                metadata={"skipped": True, "reason": "quick_scan mode"},
            )
        else:
            try:
                celery_app.send_task(
                    "app.workers.tasks.document_tasks.detect_contradictions",
                    kwargs={
                        "prev_result": citation_result,
                        "document_id": doc_id,
                    },
                    queue="default",  # Explicit queue routing - workers listen on default, not celery
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

    except SoftTimeLimitExceeded:
        # Task timeout - mark as failed for retry later
        logger.error(
            "extract_citations_task_timeout",
            document_id=doc_id,
            timeout_seconds=600,
        )
        # Save progress so we can resume from where we left off
        if progress_tracker and stage_progress:
            progress_tracker.save_progress(stage_progress, force=True)
        return {
            "status": "citation_extraction_failed",
            "document_id": doc_id,
            "error_code": "TIMEOUT",
            "error_message": "Citation extraction timeout exceeded (10 minutes)",
            "job_id": job_id,
        }

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
CONTRADICTION_PER_ENTITY_TIMEOUT_SECONDS = 300  # 5 min per entity (25 pairs × 3 batches of 10 × ~10s GPT-4)
CONTRADICTION_CONCURRENCY_LIMIT = 5  # Concurrent entity LLM streams (Phase 3: 3→5, Gemini semaphore(10) is the real throttle)


def _store_comparison_results(
    comparison_response: EntityComparisonsResponse,
    matter_id: str,
    entity_id: str,
    source_document_id: str | None = None,
) -> int:
    """Store comparison results to the statement_comparisons table.

    Follows the same pattern as CitationStorageService - persists detection
    results to database for UI consumption.

    Args:
        comparison_response: The comparison results from the service.
        matter_id: Matter UUID for the comparison.
        entity_id: Entity UUID that was compared.

    Returns:
        Number of records stored (only contradictions are stored).
    """
    from app.services.supabase.client import get_service_client

    comparisons = comparison_response.data.comparisons
    if not comparisons:
        return 0

    # Only store contradictions (other results are not needed for UI)
    contradictions = [
        c for c in comparisons if c.result == ComparisonResult.CONTRADICTION
    ]

    if not contradictions:
        return 0

    client = get_service_client()
    stored = 0

    # Build records for batch insert
    records = []
    for comparison in contradictions:
        # Determine severity based on contradiction type and confidence
        # HIGH: date/amount mismatch with high confidence
        # MEDIUM: factual contradiction or moderate confidence
        # LOW: semantic or low confidence
        severity = "medium"  # default
        if comparison.contradiction_type in ("date_mismatch", "amount_mismatch"):
            severity = "high" if comparison.confidence >= 0.8 else "medium"
        elif comparison.contradiction_type == "factual_contradiction":
            severity = "high" if comparison.confidence >= 0.9 else "medium"
        elif comparison.confidence < 0.7:
            severity = "low"

        # Build evidence JSON from the model
        evidence_json = None
        if comparison.evidence:
            evidence_json = {
                "type": comparison.evidence.type.value if comparison.evidence.type else None,
                "value_a": comparison.evidence.value_a,
                "value_b": comparison.evidence.value_b,
                "page_refs": comparison.evidence.page_refs,
            }

        record = {
            "matter_id": matter_id,
            "entity_id": entity_id,
            "statement_a_id": comparison.statement_a_id,
            "statement_b_id": comparison.statement_b_id,
            "result": comparison.result.value,  # 'contradiction'
            "contradiction_type": comparison.contradiction_type or "semantic_contradiction",
            "severity": severity,
            "reasoning": comparison.reasoning,  # Chain-of-thought from GPT-4
            "explanation": comparison.reasoning,  # Attorney-friendly explanation
            "confidence": comparison.confidence,
            "evidence": evidence_json,
        }
        # Stage 2.3: Track which document triggered this comparison
        if source_document_id:
            record["source_document_id"] = source_document_id
        records.append(record)

    if records:
        try:
            # Use upsert to avoid duplicates (statement_a_id + statement_b_id)
            # Note: This requires a unique constraint on (statement_a_id, statement_b_id)
            # If not available, use insert with on_conflict handling
            result = client.table("statement_comparisons").upsert(
                records,
                on_conflict="matter_id,statement_a_id,statement_b_id",
            ).execute()
            stored = len(result.data) if result.data else 0

            logger.info(
                "contradiction_results_stored",
                matter_id=matter_id,
                entity_id=entity_id,
                contradictions_stored=stored,
            )
        except Exception as e:
            # Log but don't fail the task - detection was successful even if storage fails
            logger.error(
                "contradiction_storage_failed",
                matter_id=matter_id,
                entity_id=entity_id,
                error=str(e),
                error_type=type(e).__name__,
            )

    return stored


@celery_app.task(
    name="app.workers.tasks.document_tasks.detect_contradictions",
    bind=True,
    autoretry_for=(ComparisonServiceError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
    soft_time_limit=1200,  # 20 minutes - typical: ~30 entities finish in <10min
    time_limit=1260,  # 21 minutes - hard kill
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

    matter_id: str | None = None

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

        # Get entities and chunk IDs from this document
        response = (
            client.table("chunks")
            .select("id, entity_ids")
            .eq("document_id", doc_id)
            .not_.is_("entity_ids", "null")
            .execute()
        )

        # Collect unique entity IDs and chunk IDs for this document
        entity_ids: set[str] = set()
        source_chunk_ids: set[str] = set()  # Stage 2.3: for incremental comparison
        for chunk in response.data or []:
            chunk_entities = chunk.get("entity_ids") or []
            entity_ids.update(chunk_entities)
            if chunk.get("id"):
                source_chunk_ids.add(chunk["id"])

        # Stage 2.3: Incremental idempotency check.
        # Instead of checking "does entity have ANY comparisons?", check
        # "has THIS document already been used as source for comparisons?"
        # This ensures uploading doc B triggers cross-document comparisons
        # with doc A's chunks, even if doc A's entities were already compared.
        # On Celery retry, bypass idempotency to allow partial re-detection
        is_celery_retry = self.request.retries > 0
        if entity_ids:
            existing_for_doc = (
                client.table("statement_comparisons")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("source_document_id", doc_id)
                .execute()
            )
            if existing_for_doc.count and existing_for_doc.count > 0 and not is_celery_retry:
                logger.info(
                    "detect_contradictions_idempotency_skip",
                    document_id=doc_id,
                    matter_id=matter_id,
                    existing_comparisons=existing_for_doc.count,
                    reason="This document already has comparisons as source",
                )
                _populate_verification_records(matter_id, doc_id)
                _mark_job_completed(job_id, matter_id, document_id=doc_id)
                return {
                    "status": "contradiction_detection_complete",
                    "document_id": doc_id,
                    "contradictions_found": existing_for_doc.count,
                    "reason": "Idempotency: document already compared as source",
                    "job_id": job_id,
                }

            if is_celery_retry and existing_for_doc.count and existing_for_doc.count > 0:
                logger.warning(
                    "detect_contradictions_retry_bypassing_idempotency",
                    document_id=doc_id,
                    retry_number=self.request.retries,
                    existing_comparison_count=existing_for_doc.count,
                    reason="Previous run may have been partial; re-detecting remaining entities",
                )

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
            # Mark job as COMPLETED even with no entities - this is the final stage
            _populate_verification_records(matter_id, doc_id)
            _mark_job_completed(job_id, matter_id, document_id=doc_id)
            return {
                "status": "contradiction_detection_complete",
                "document_id": doc_id,
                "entities_processed": 0,
                "contradictions_found": 0,
                "reason": "No entities found in document",
                "job_id": job_id,
            }

        # Get canonical_names for entity_ids and group by name (ignoring type)
        # This enables cross-type comparison: "Custodian [PERSON]" and "Custodian [ORG]"
        # will be treated as the same entity for contradiction detection
        entities_resp = (
            client.table("identity_nodes")
            .select("id, canonical_name, entity_type")
            .in_("id", list(entity_ids))
            .execute()
        )

        # Group by canonical_name (the key fix for rigid entity matching)
        canonical_names: set[str] = set()
        name_to_types: dict[str, set[str]] = {}  # For logging cross-type matches
        for entity in entities_resp.data or []:
            name = entity.get("canonical_name")
            etype = entity.get("entity_type")
            if name:
                canonical_names.add(name)
                if name not in name_to_types:
                    name_to_types[name] = set()
                if etype:
                    name_to_types[name].add(etype)

        if not canonical_names:
            logger.info(
                "detect_contradictions_no_canonical_names",
                document_id=doc_id,
                entity_ids_count=len(entity_ids),
            )
            _update_job_stage_complete(
                job_id,
                "contradiction_detection",
                matter_id,
                metadata={"entities_processed": 0, "contradictions_found": 0},
            )
            # Mark job as COMPLETED even with no canonical names - this is the final stage
            _populate_verification_records(matter_id, doc_id)
            _mark_job_completed(job_id, matter_id, document_id=doc_id)
            return {
                "status": "contradiction_detection_complete",
                "document_id": doc_id,
                "entities_processed": 0,
                "contradictions_found": 0,
                "reason": "No canonical names resolved for entities",
                "job_id": job_id,
            }

        # Log cross-type entities (same name, multiple types)
        cross_type_names = [n for n, types in name_to_types.items() if len(types) > 1]
        if cross_type_names:
            logger.info(
                "detect_contradictions_cross_type_entities",
                document_id=doc_id,
                cross_type_count=len(cross_type_names),
                examples=cross_type_names[:5],
            )

        # Limit canonical names for cost control
        names_to_process = list(canonical_names)[:CONTRADICTION_MAX_ENTITIES_PER_RUN]

        logger.info(
            "detect_contradictions_processing",
            document_id=doc_id,
            total_entity_ids=len(entity_ids),
            unique_canonical_names=len(canonical_names),
            names_to_process=len(names_to_process),
        )

        # Process by canonical_name (not entity_id) for cross-type comparison
        total_contradictions = 0
        total_pairs_compared = 0
        total_stored = 0
        entities_processed = 0
        entities_skipped = 0
        total_cost_usd = 0.0

        # Semaphore to limit concurrent LLM calls (avoid rate limiting + Railway resource safety)
        _contradiction_semaphore = asyncio.Semaphore(CONTRADICTION_CONCURRENCY_LIMIT)

        async def _process_single_name(canonical_name: str) -> dict:
            """Process a single canonical name with timeout and concurrency control."""
            import time as _time

            async with _contradiction_semaphore:
                _entity_start = _time.monotonic()
                try:
                    async with asyncio.timeout(CONTRADICTION_PER_ENTITY_TIMEOUT_SECONDS):
                        comparison_result = await compare_service.compare_statements_by_canonical_name(
                            canonical_name=canonical_name,
                            matter_id=matter_id,
                            max_pairs=CONTRADICTION_MAX_PAIRS_PER_ENTITY,
                            confidence_threshold=0.5,
                            source_chunk_ids=source_chunk_ids,  # Stage 2.3: incremental
                        )

                    _entity_elapsed = _time.monotonic() - _entity_start

                    # Store contradictions to database (Epic 5 requirement)
                    stored = 0
                    if comparison_result.meta.contradictions_found > 0:
                        stored = _store_comparison_results(
                            comparison_response=comparison_result,
                            matter_id=matter_id,
                            entity_id=comparison_result.data.entity_id,
                            source_document_id=doc_id,  # Stage 2.3: track source
                        )

                    logger.info(
                        "detect_contradictions_name_complete",
                        document_id=doc_id,
                        canonical_name=canonical_name,
                        contradictions=comparison_result.meta.contradictions_found,
                        pairs_compared=comparison_result.meta.pairs_compared,
                        elapsed_seconds=round(_entity_elapsed, 1),
                        cost_usd=comparison_result.meta.total_cost_usd,
                        stored=stored,
                    )

                    return {
                        "status": "ok",
                        "contradictions": comparison_result.meta.contradictions_found,
                        "pairs_compared": comparison_result.meta.pairs_compared,
                        "cost_usd": comparison_result.meta.total_cost_usd,
                        "stored": stored,
                    }

                except TimeoutError:
                    _entity_elapsed = _time.monotonic() - _entity_start
                    logger.warning(
                        "detect_contradictions_name_timeout",
                        document_id=doc_id,
                        canonical_name=canonical_name,
                        timeout_seconds=CONTRADICTION_PER_ENTITY_TIMEOUT_SECONDS,
                        elapsed_seconds=round(_entity_elapsed, 1),
                    )
                    return {"status": "skipped", "reason": "timeout"}

                except Exception as e:
                    logger.warning(
                        "detect_contradictions_name_failed",
                        document_id=doc_id,
                        canonical_name=canonical_name,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    return {"status": "skipped", "reason": str(e)}

        async def _detect_contradictions_async():
            nonlocal total_contradictions, total_pairs_compared, entities_processed
            nonlocal entities_skipped, total_cost_usd, total_stored

            # Process entities concurrently with semaphore-controlled parallelism
            results = await asyncio.gather(
                *[_process_single_name(name) for name in names_to_process],
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    entities_skipped += 1
                    continue
                if result.get("status") == "ok":
                    total_contradictions += result["contradictions"]
                    total_pairs_compared += result["pairs_compared"]
                    total_cost_usd += result["cost_usd"]
                    total_stored += result.get("stored", 0)
                    entities_processed += 1
                else:
                    entities_skipped += 1

        # Run async comparison (gevent-compatible via _run_async)
        # Pass timeout=1140 (19 min) to stay below soft_time_limit=1200 (20 min).
        # Without this, _run_async defaults to 300s which kills the task prematurely.
        _run_async(_detect_contradictions_async(), timeout=1140)

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
                "contradictions_stored": total_stored,
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

        # Mark the entire job as COMPLETED — contradiction_detection is the final stage
        _populate_verification_records(matter_id, doc_id)
        _dispatch_summary_pregeneration(matter_id)
        _mark_job_completed(job_id, matter_id, document_id=doc_id)

        logger.info(
            "detect_contradictions_task_completed",
            document_id=doc_id,
            entities_processed=entities_processed,
            entities_skipped=entities_skipped,
            contradictions_found=total_contradictions,
            contradictions_stored=total_stored,
            pairs_compared=total_pairs_compared,
            cost_usd=total_cost_usd,
        )

        return {
            "status": "contradictions_detected",
            "document_id": doc_id,
            "entities_processed": entities_processed,
            "entities_skipped": entities_skipped,
            "contradictions_found": total_contradictions,
            "contradictions_stored": total_stored,
            "pairs_compared": total_pairs_compared,
            "cost_usd": total_cost_usd,
            "job_id": job_id,
        }

    except (SoftTimeLimitExceeded, TimeoutError) as timeout_exc:
        # Task timeout - complete pipeline with partial results.
        # Catches both Celery's SoftTimeLimitExceeded (20 min) and
        # _run_async's TimeoutError (19 min) so both follow the graceful path.
        timeout_type = type(timeout_exc).__name__
        logger.error(
            "detect_contradictions_task_timeout",
            document_id=doc_id,
            timeout_type=timeout_type,
            timeout_seconds=1200,
            entities_processed=entities_processed,
            contradictions_found=total_contradictions,
        )
        # Still complete the pipeline — contradiction detection is the final stage.
        # If contradictions were found before timeout, they're already stored.
        if matter_id and doc_id:
            _populate_verification_records(matter_id, doc_id)
            _dispatch_summary_pregeneration(matter_id)
            _mark_job_completed(job_id, matter_id, document_id=doc_id)
        return {
            "status": "contradiction_detection_partial" if total_contradictions > 0 else "contradiction_detection_failed",
            "document_id": doc_id,
            "error_code": "TIMEOUT",
            "error_message": f"Contradiction detection timeout ({timeout_type}). {entities_processed} entities processed, {total_contradictions} contradictions found before timeout.",
            "entities_processed": entities_processed,
            "contradictions_found": total_contradictions,
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
            # BUG-001/002 fix: Complete the pipeline even on comparison failure.
            # Contradiction detection is the final stage — earlier stages
            # (entities, citations, timeline) already succeeded and their
            # results should remain visible. Mark document COMPLETED so the
            # frontend doesn't show a false "failed processing" banner.
            if matter_id and doc_id:
                _populate_verification_records(matter_id, doc_id)
                _dispatch_summary_pregeneration(matter_id)
                _mark_job_completed(job_id, matter_id, document_id=doc_id)
            return {
                "status": "contradiction_detection_failed",
                "document_id": doc_id,
                "error_code": e.code,
                "error_message": e.message,
                "job_id": job_id,
            }

        raise

    except DocumentServiceError as e:
        logger.error(
            "detect_contradictions_document_error",
            document_id=doc_id,
            error=str(e),
        )
        # BUG-001/002 fix: Same as above — complete the pipeline so
        # earlier-stage results stay visible.
        if matter_id and doc_id:
            _populate_verification_records(matter_id, doc_id)
            _dispatch_summary_pregeneration(matter_id)
            _mark_job_completed(job_id, matter_id, document_id=doc_id)
        return {
            "status": "contradiction_detection_failed",
            "document_id": doc_id,
            "error_code": e.code,
            "error_message": e.message,
            "job_id": job_id,
        }

    except Exception as e:
        logger.error(
            "detect_contradictions_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        # BUG-001/002 fix: Mark job COMPLETED (not FAILED) so the frontend
        # doesn't show a false "failed processing" banner. Contradiction
        # detection is the final stage — earlier stages (entities, citations,
        # timeline) already succeeded and their results should stay visible.
        if matter_id and doc_id:
            _populate_verification_records(matter_id, doc_id)
            _dispatch_summary_pregeneration(matter_id)
            _mark_job_completed(job_id, matter_id, document_id=doc_id)
        return {
            "status": "contradiction_detection_failed",
            "document_id": doc_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
            "job_id": job_id,
        }
