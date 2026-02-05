"""Celery tasks for parallel chunk processing of large documents.

Story 16.4: Implement Parallel Chunk Processing with Celery
Story 16.5: Implement Individual Chunk Retry
Story 17.3: Per-Chunk Timeout and Rate Limiting

Processes large PDFs (>30 pages) by splitting into chunks and
processing each chunk in parallel using Celery group().
"""

import hashlib
import json
import signal
import time
from io import BytesIO

import pypdf
import structlog
from celery import chord, group
from celery.exceptions import SoftTimeLimitExceeded

from app.core.circuit_breaker import CircuitOpenError
from app.models.document import DocumentStatus
from app.models.job import JobStatus
from app.models.ocr_chunk import ChunkStatus
from app.services.bounding_box_service import get_bounding_box_service
from app.services.chunk_cleanup_service import get_chunk_cleanup_service
from app.services.distributed_lock import acquire_chunk_lock
from app.services.document_service import (
    DocumentService,
    get_document_service,
)
from app.services.job_tracking import get_chunk_progress_tracker
from app.services.ocr import OCRProcessor, get_ocr_processor
from app.services.ocr.processor import OCRCircuitOpenError
from app.services.ocr_chunk_service import (
    OCRChunkService,
    get_ocr_chunk_service,
)
from app.services.ocr_result_merger import (
    ChunkOCRResult,
    MergeValidationError,
    get_ocr_result_merger,
)
from app.services.pdf_chunker import (
    PDFChunker,
    get_pdf_chunker,
)
from app.services.pubsub_service import broadcast_document_status
from app.services.security.injection_detector import (
    scan_document_for_injection,
)
from app.services.storage_service import (
    StorageService,
    get_storage_service,
)
from app.workers.celery import celery_app
from app.workers.utils import run_async

logger = structlog.get_logger(__name__)

# Configuration
CHUNK_GROUP_TIMEOUT = 600  # 10 minute timeout for entire group
CHUNK_LOCK_TIMEOUT = 120  # 2 minute lock expiry

# Story 17.3: Per-Chunk Timeout and Rate Limiting
CHUNK_OCR_TIMEOUT = 120  # 2 minutes per chunk OCR
RATE_LIMIT_WINDOW_SECONDS = 60  # Rate limit window
MAX_CHUNKS_PER_WINDOW = 30  # Max chunks per minute (Document AI limit)


# =============================================================================
# Rate Limiter for Document AI (Story 17.3)
# =============================================================================


class ChunkRateLimiter:
    """Token bucket rate limiter for chunk processing.

    Story 17.3: Prevents exceeding Document AI API quotas.
    Uses Redis for distributed rate limiting across workers.
    """

    def __init__(
        self,
        max_tokens: int = MAX_CHUNKS_PER_WINDOW,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ):
        """Initialize rate limiter.

        Args:
            max_tokens: Maximum requests per window.
            window_seconds: Time window in seconds.
        """
        self.max_tokens = max_tokens
        self.window_seconds = window_seconds
        self._rate_limit_key = "docai_chunk_rate_limit"

    def acquire(self) -> tuple[bool, float]:
        """Try to acquire a rate limit token.

        Returns:
            Tuple of (acquired, wait_time).
            If not acquired, wait_time is seconds to wait.
        """
        try:
            from app.services.distributed_lock import get_sync_redis_client

            redis_client = get_sync_redis_client()
            current_time = time.time()
            window_start = current_time - self.window_seconds

            # Use sorted set for sliding window
            key = self._rate_limit_key

            # Remove old entries outside window
            redis_client.zremrangebyscore(key, "-inf", window_start)

            # Count current entries in window
            current_count = redis_client.zcard(key)

            if current_count < self.max_tokens:
                # Add new entry with current timestamp as score
                redis_client.zadd(key, {f"{current_time}:{id(self)}": current_time})
                redis_client.expire(key, self.window_seconds * 2)  # Auto cleanup
                return True, 0.0
            else:
                # Calculate wait time until oldest entry expires
                oldest = redis_client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = oldest[0][1]
                    wait_time = (oldest_time + self.window_seconds) - current_time
                    return False, max(0.1, wait_time)
                return False, 1.0

        except Exception as e:
            # Fail open on Redis errors
            logger.warning(
                "rate_limiter_redis_error",
                error=str(e),
            )
            return True, 0.0

    def wait_for_token(self, max_wait: float = 60.0) -> bool:
        """Wait for a rate limit token with backoff.

        Args:
            max_wait: Maximum seconds to wait.

        Returns:
            True if token acquired, False if timeout.
        """
        total_waited = 0.0

        while total_waited < max_wait:
            acquired, wait_time = self.acquire()

            if acquired:
                return True

            if total_waited + wait_time > max_wait:
                return False

            logger.info(
                "rate_limiter_waiting",
                wait_seconds=round(wait_time, 2),
                total_waited=round(total_waited, 2),
            )
            time.sleep(wait_time)
            total_waited += wait_time

        return False


# Global rate limiter instance
_chunk_rate_limiter: ChunkRateLimiter | None = None


def get_chunk_rate_limiter() -> ChunkRateLimiter:
    """Get singleton rate limiter instance."""
    global _chunk_rate_limiter
    if _chunk_rate_limiter is None:
        _chunk_rate_limiter = ChunkRateLimiter()
    return _chunk_rate_limiter


# =============================================================================
# Timeout Handler (Story 17.3)
# =============================================================================


class ChunkTimeoutError(Exception):
    """Raised when chunk processing times out."""

    def __init__(self, chunk_index: int, timeout_seconds: int):
        self.chunk_index = chunk_index
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Chunk {chunk_index} processing timed out after {timeout_seconds}s"
        )


class ChunkRateLimitError(Exception):
    """Raised when rate limit prevents chunk processing."""

    def __init__(self, chunk_index: int, wait_time: float):
        self.chunk_index = chunk_index
        self.wait_time = wait_time
        super().__init__(
            f"Chunk {chunk_index} rate limited, would need to wait {wait_time:.1f}s"
        )


class ChunkProcessingError(Exception):
    """Raised when chunk processing fails."""

    def __init__(self, message: str, code: str = "CHUNK_PROCESSING_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


def _run_async(coro):
    """Run async coroutine in sync context for Celery tasks."""
    return run_async(coro)


def _run_injection_scan(
    document_id: str,
    full_text: str,
    doc_service: DocumentService,
) -> bool:
    """Run injection detection scan on document text.

    Story 1.2: Add LLM Detection for Suspicious Documents

    Scans the extracted text for prompt injection patterns using
    a lightweight LLM check (~$0.001/doc). High-risk documents are
    flagged for manual review and processing is halted.

    Args:
        document_id: Document UUID.
        full_text: OCR-extracted text content.
        doc_service: Document service instance.

    Returns:
        True if processing should continue, False if document requires
        manual review (high injection risk) and processing should halt.
    """
    try:
        # Run async scan in sync context
        scan_result = _run_async(
            scan_document_for_injection(
                text=full_text,
                document_id=document_id,
                use_llm=True,
            )
        )

        # Update document with scan results
        doc_service.update_injection_scan(
            document_id=document_id,
            injection_risk=scan_result.risk_level.value,
            scan_result=scan_result.to_dict(),
        )

        if scan_result.requires_review:
            logger.warning(
                "document_high_injection_risk_halting",
                document_id=document_id,
                risk_level=scan_result.risk_level.value,
                patterns_found=scan_result.patterns_found[:5],
            )
            # Story 1.2 AC: High-risk documents require manual review before processing
            # Halt further processing - document stays in pending_review state
            return False

        return True

    except Exception as e:
        # Log error but don't fail processing - injection scan is optional
        logger.error(
            "injection_scan_failed",
            document_id=document_id,
            error=str(e),
        )
        # Set risk to none on failure - document can still proceed
        try:
            doc_service.update_injection_scan(
                document_id=document_id,
                injection_risk="none",
                scan_result={"error": str(e), "scan_completed": False},
            )
        except Exception:
            pass  # Already logged, don't fail on update error
        return True  # Continue processing on scan failure


# =============================================================================
# Chunked Document Processing Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.chunked_document_tasks.process_document_chunked",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=1800,  # 30 minutes - orchestrating many chunks
    time_limit=2100,  # 35 minutes - hard kill
)
def process_document_chunked(
    self,
    document_id: str,
    matter_id: str,
    job_id: str | None = None,
    storage_service: StorageService | None = None,
    chunk_service: OCRChunkService | None = None,
    doc_service: DocumentService | None = None,
) -> dict:
    """Process large document via parallel chunk processing.

    Dispatches all chunks for parallel processing using Celery group(),
    waits for completion, then merges results.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID.
        job_id: Optional job tracking UUID.
        storage_service: Optional storage service (for testing).
        chunk_service: Optional chunk service (for testing).
        doc_service: Optional document service (for testing).

    Returns:
        Processing result dict with status and statistics.
    """
    # Initialize services
    # Note: storage_service kept for testing DI but used via get_storage_service() in sub-tasks
    chunks_svc = chunk_service or get_ocr_chunk_service()
    docs_svc = doc_service or get_document_service()
    progress_tracker = get_chunk_progress_tracker()

    logger.info(
        "process_document_chunked_started",
        document_id=document_id,
        matter_id=matter_id,
        job_id=job_id,
    )

    try:
        # Get pending chunks for this document
        chunks = _run_async(chunks_svc.get_pending_chunks(document_id))

        if not chunks:
            logger.warning("no_pending_chunks", document_id=document_id)
            return {
                "status": "no_chunks",
                "document_id": document_id,
                "message": "No pending chunks found",
            }

        logger.info(
            "dispatching_parallel_chunks",
            document_id=document_id,
            chunk_count=len(chunks),
        )

        # Download PDF once (will be split by each chunk task)
        document = docs_svc.get_document(document_id)
        if not document or not document.storage_path:
            raise ChunkProcessingError(
                "Document not found or missing storage path",
                code="DOCUMENT_NOT_FOUND",
            )

        # Create task signature for each chunk
        chunk_tasks = []
        for chunk in chunks:
            task = process_single_chunk.s(
                document_id=document_id,
                matter_id=matter_id,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                job_id=job_id,
            )
            chunk_tasks.append(task)

        # Dispatch all chunks in parallel using Celery chord()
        # The callback (finalize_chunked_document) runs after all chunks complete
        # This avoids the anti-pattern of calling result.get() within a task
        callback = finalize_chunked_document.s(
            document_id=document_id,
            matter_id=matter_id,
            job_id=job_id,
        )

        # Use chord: group of chunk tasks -> finalize callback
        # The callback receives chunk results as first argument
        result = chord(chunk_tasks)(callback)

        logger.info(
            "chunk_chord_dispatched",
            document_id=document_id,
            chunk_count=len(chunks),
            chord_id=result.id,
        )

        return {
            "status": "dispatched",
            "document_id": document_id,
            "chunk_count": len(chunks),
            "chord_id": result.id,
            "message": "Chunks dispatched for parallel processing, finalize will run on completion",
        }

    except SoftTimeLimitExceeded:
        # Task timeout - mark document as failed so it can be recovered
        logger.error(
            "process_document_chunked_timeout",
            document_id=document_id,
            matter_id=matter_id,
            timeout_seconds=1800,  # soft_time_limit value
        )

        # Mark document as failed with timeout error
        if doc_service is None:
            doc_service = get_document_service()
        try:
            doc_service.update_ocr_status(
                document_id=document_id,
                status=DocumentStatus.OCR_FAILED,
                ocr_error="Chunked processing timeout exceeded (30 minutes) - document may be too large",
            )
        except Exception as update_error:
            logger.error(
                "timeout_status_update_failed",
                document_id=document_id,
                error=str(update_error),
            )

        # Mark job as failed
        if job_id:
            try:
                from app.services.job_tracking import get_job_tracking_service
                job_svc = get_job_tracking_service()
                job_svc.fail_job(
                    job_id=job_id,
                    error_message="Processing timeout exceeded (30 minutes)",
                    error_code="TIMEOUT",
                )
            except Exception:
                pass  # Already logged

        return {
            "status": "ocr_failed",
            "document_id": document_id,
            "error_code": "TIMEOUT",
            "error_message": "Chunked processing timeout exceeded (30 minutes)",
        }

    except Exception as e:
        logger.error(
            "process_document_chunked_failed",
            document_id=document_id,
            error=str(e),
        )
        raise


# =============================================================================
# Single Chunk Processing Task (Story 17.3: with timeout and rate limiting)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.chunked_document_tasks.process_single_chunk",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=CHUNK_OCR_TIMEOUT,  # Story 17.3: Soft timeout
    time_limit=CHUNK_OCR_TIMEOUT + 30,  # Hard timeout with buffer
)
def process_single_chunk(
    self,
    document_id: str,
    matter_id: str,
    chunk_id: str,
    chunk_index: int,
    page_start: int,
    page_end: int,
    job_id: str | None = None,
    storage_service: StorageService | None = None,
    chunk_service: OCRChunkService | None = None,
    doc_service: DocumentService | None = None,
    ocr_processor: OCRProcessor | None = None,
    pdf_chunker: PDFChunker | None = None,
    rate_limiter: ChunkRateLimiter | None = None,
) -> dict:
    """Process a single PDF chunk through Document AI.

    Story 17.3: Enhanced with per-chunk timeout and rate limiting.
    - Soft timeout of 2 minutes per chunk (CHUNK_OCR_TIMEOUT)
    - Rate limiting to prevent exceeding Document AI quotas
    - Circuit breaker integration (Story 17.2) via OCR processor

    Acquires a distributed lock, extracts the page range,
    sends to Document AI, and stores the result.

    Args:
        document_id: Parent document UUID.
        matter_id: Matter UUID.
        chunk_id: Chunk record UUID.
        chunk_index: 0-based chunk index.
        page_start: First page (1-based).
        page_end: Last page (1-based).
        job_id: Optional job tracking UUID.
        storage_service: Optional storage service (for testing).
        chunk_service: Optional chunk service (for testing).
        doc_service: Optional document service (for testing).
        ocr_processor: Optional OCR processor (for testing).
        pdf_chunker: Optional PDF chunker (for testing).
        rate_limiter: Optional rate limiter (for testing).

    Returns:
        Chunk result dict with status and OCR data.
    """
    start_time = time.time()

    # Initialize services
    storage = storage_service or get_storage_service()
    chunks_svc = chunk_service or get_ocr_chunk_service()
    docs_svc = doc_service or get_document_service()
    ocr = ocr_processor or get_ocr_processor()
    chunker = pdf_chunker or get_pdf_chunker()
    progress_tracker = get_chunk_progress_tracker()
    limiter = rate_limiter or get_chunk_rate_limiter()

    logger.info(
        "process_single_chunk_started",
        document_id=document_id,
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        page_start=page_start,
        page_end=page_end,
    )

    # Story 17.4: Idempotency check - skip if already processed
    already_processed, cached_result = _run_async(
        chunks_svc.check_chunk_already_processed(chunk_id)
    )
    if already_processed and cached_result:
        logger.info(
            "chunk_already_processed_skipping",
            document_id=document_id,
            chunk_index=chunk_index,
            chunk_id=chunk_id,
            result_path=cached_result.get("result_storage_path"),
        )
        # Return cached result info so merge can proceed
        return {
            "status": "success",
            "chunk_index": chunk_index,
            "page_start": page_start,
            "page_end": page_end,
            "result_path": cached_result.get("result_storage_path"),
            "checksum": cached_result.get("result_checksum"),
            "from_cache": True,
            "processing_time_seconds": 0,
        }

    # Story 17.3: Rate limiting before processing
    if not limiter.wait_for_token(max_wait=30.0):
        logger.warning(
            "chunk_rate_limited",
            document_id=document_id,
            chunk_index=chunk_index,
        )
        # Retry with backoff instead of failing immediately
        raise self.retry(
            exc=ChunkRateLimitError(chunk_index, 30.0),
            countdown=30,  # Wait 30 seconds before retry
        )

    # Acquire distributed lock to prevent duplicate processing
    with acquire_chunk_lock(document_id, chunk_index) as locked:
        if not locked:
            logger.warning(
                "chunk_lock_not_acquired",
                document_id=document_id,
                chunk_index=chunk_index,
            )
            raise ChunkProcessingError(
                f"Could not acquire lock for chunk {chunk_index}",
                code="LOCK_FAILED",
            )

        try:
            # Update status to processing
            _run_async(chunks_svc.update_status(chunk_id, ChunkStatus.PROCESSING))

            # Story 19.1: Update heartbeat to indicate active processing
            _run_async(chunks_svc.update_heartbeat(chunk_id))

            # Get document storage path
            document = docs_svc.get_document(document_id)
            if not document or not document.storage_path:
                raise ChunkProcessingError(
                    "Document not found or missing storage path",
                    code="DOCUMENT_NOT_FOUND",
                )

            # Download full PDF
            pdf_bytes = storage.download_file(document.storage_path)

            # Story 19.1: Update heartbeat after download
            _run_async(chunks_svc.update_heartbeat(chunk_id))

            # Extract just this chunk's pages directly using pypdf (more memory efficient)
            # The split_pdf method processes ALL pages which exceeds memory limits for large PDFs
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            writer = pypdf.PdfWriter()
            for page_idx in range(page_start - 1, page_end):  # Convert to 0-based
                writer.add_page(reader.pages[page_idx])
            buffer = BytesIO()
            writer.write(buffer)
            chunk_bytes = buffer.getvalue()

            # Clear references to free memory
            del reader
            del writer
            del pdf_bytes

            # Story 19.1: Update heartbeat before OCR (long operation)
            _run_async(chunks_svc.update_heartbeat(chunk_id))

            # Process through Document AI (with circuit breaker - Story 17.2)
            ocr_result = ocr.process_document(
                pdf_content=chunk_bytes,
                document_id=f"{document_id}_chunk_{chunk_index}",
            )

            # Story 19.1: Update heartbeat after OCR completes
            _run_async(chunks_svc.update_heartbeat(chunk_id))

            # Store bounding boxes in database (same as non-chunked processing)
            # Adjust page numbers to be relative to the full document, not the chunk
            # The BoundingBox objects have a 'page' attribute that needs adjustment
            for bbox in ocr_result.bounding_boxes:
                # Adjust page number: chunk's page 1 = document's page_start
                bbox.page = bbox.page + page_start - 1

            # Store bounding boxes using the bounding box service
            # Note: save_bounding_boxes is synchronous, not async
            bbox_svc = get_bounding_box_service()
            bbox_svc.save_bounding_boxes(
                document_id=document_id,
                matter_id=matter_id,
                bounding_boxes=ocr_result.bounding_boxes,
            )

            # Calculate checksum of results for idempotency
            result_json = json.dumps({
                "full_text": ocr_result.full_text,
                "overall_confidence": ocr_result.overall_confidence,
                "page_count": ocr_result.page_count,
            })
            result_checksum = hashlib.sha256(result_json.encode()).hexdigest()

            # Update chunk record with completion info (no storage path needed)
            _run_async(
                chunks_svc.update_result(
                    chunk_id=chunk_id,
                    result_storage_path=None,  # Not using storage
                    result_checksum=result_checksum,
                )
            )

            # Update chunk progress
            if job_id:
                _run_async(
                    progress_tracker.update_chunk_progress(
                        job_id=job_id,
                        document_id=document_id,
                        matter_id=matter_id,
                    )
                )

            processing_time = time.time() - start_time

            logger.info(
                "chunk_processed_successfully",
                document_id=document_id,
                chunk_index=chunk_index,
                bbox_count=len(ocr_result.bounding_boxes),
                confidence=ocr_result.overall_confidence,
                processing_time_seconds=round(processing_time, 2),
            )

            # =================================================================
            # AUTO-FINALIZATION: Check if all chunks are complete
            # This handles the case where chunks are processed individually
            # (not via chord) and finalization never gets triggered.
            # =================================================================
            try:
                progress = _run_async(chunks_svc.get_chunk_progress(document_id))
                if progress.is_complete and not progress.has_failures:
                    logger.info(
                        "all_chunks_complete_triggering_finalization",
                        document_id=document_id,
                        completed=progress.completed,
                        total=progress.total,
                    )
                    # Trigger finalization asynchronously
                    finalize_chunked_document.delay(
                        document_id=document_id,
                        matter_id=matter_id,
                        job_id=job_id,
                        chunk_results=[],  # Empty - will query DB for results
                    )
                elif progress.is_complete and progress.has_failures:
                    logger.warning(
                        "all_chunks_complete_but_has_failures",
                        document_id=document_id,
                        completed=progress.completed,
                        failed=progress.failed,
                        total=progress.total,
                    )
                    # Still trigger finalization to handle partial success
                    finalize_chunked_document.delay(
                        document_id=document_id,
                        matter_id=matter_id,
                        job_id=job_id,
                        chunk_results=[],
                    )
            except Exception as finalize_check_error:
                # Don't fail the chunk if finalization check fails
                logger.warning(
                    "auto_finalization_check_failed",
                    document_id=document_id,
                    error=str(finalize_check_error),
                )

            return {
                "status": "success",
                "chunk_index": chunk_index,
                "page_start": page_start,
                "page_end": page_end,
                "checksum": result_checksum,
                "bbox_count": len(ocr_result.bounding_boxes),
                "confidence": ocr_result.overall_confidence,
                "page_count": ocr_result.page_count,
                "full_text": ocr_result.full_text,
                "processing_time_seconds": round(processing_time, 2),
            }

        except OCRCircuitOpenError as e:
            # Circuit breaker is open - retry later (Story 17.2 + 17.3)
            logger.warning(
                "chunk_circuit_open_retry",
                document_id=document_id,
                chunk_index=chunk_index,
                cooldown_remaining=e.cooldown_remaining,
            )
            raise self.retry(
                exc=e,
                countdown=int(e.cooldown_remaining) + 5,  # Wait for circuit to close
            )

        except Exception as e:
            # Update chunk status to failed
            _run_async(
                chunks_svc.update_status(
                    chunk_id,
                    ChunkStatus.FAILED,
                    error_message=str(e),
                )
            )

            # Report failure to progress tracker
            if job_id:
                _run_async(
                    progress_tracker.report_chunk_failure(
                        job_id=job_id,
                        document_id=document_id,
                        matter_id=matter_id,
                        chunk_index=chunk_index,
                        page_start=page_start,
                        page_end=page_end,
                        error_message=str(e),
                    )
                )

            logger.error(
                "chunk_processing_failed",
                document_id=document_id,
                chunk_index=chunk_index,
                error=str(e),
            )
            raise


# =============================================================================
# Result Merge and Storage
# =============================================================================


def _merge_and_store_results(
    document_id: str,
    matter_id: str,
    successful_results: list[dict],
    job_id: str | None = None,
) -> dict:
    """Merge chunk results and store final document data.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID.
        successful_results: List of successful chunk results.
        job_id: Optional job tracking UUID.

    Returns:
        Final processing result dict.
    """
    merger = get_ocr_result_merger()
    bbox_service = get_bounding_box_service()
    doc_service = get_document_service()
    cleanup_service = get_chunk_cleanup_service()
    progress_tracker = get_chunk_progress_tracker()

    logger.info(
        "merging_chunk_results",
        document_id=document_id,
        chunk_count=len(successful_results),
    )

    try:
        # Indicate merge stage starting
        if job_id:
            _run_async(
                progress_tracker.start_merge_stage(
                    job_id=job_id,
                    document_id=document_id,
                    matter_id=matter_id,
                )
            )

        # Convert results to ChunkOCRResult models
        chunk_results = []
        for result in sorted(successful_results, key=lambda x: x["chunk_index"]):
            chunk_results.append(
                ChunkOCRResult(
                    chunk_index=result["chunk_index"],
                    page_start=result["page_start"],
                    page_end=result["page_end"],
                    bounding_boxes=result.get("bounding_boxes", []),
                    full_text=result.get("full_text", ""),
                    overall_confidence=result.get("confidence", 0.0),
                    page_count=result.get("page_count", 0),
                    checksum=result.get("checksum"),
                )
            )

        # Merge results
        merged = merger.merge_results(chunk_results, document_id)

        # Delete existing bboxes (in case of reprocessing)
        bbox_service.delete_bounding_boxes(document_id)

        # Save merged bounding boxes
        saved_count = bbox_service.save_bounding_boxes(
            document_id=document_id,
            matter_id=matter_id,
            bounding_boxes=merged.bounding_boxes,
        )

        # Update document with OCR results
        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.OCR_COMPLETE,
            extracted_text=merged.full_text,
            page_count=merged.page_count,
            ocr_confidence=merged.overall_confidence,
        )

        # Broadcast completion
        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="ocr_complete",
            page_count=merged.page_count,
            ocr_confidence=merged.overall_confidence,
        )

        # Story 1.2: Scan for prompt injection patterns
        # High-risk documents require manual review before further processing
        should_continue = _run_injection_scan(
            document_id=document_id,
            full_text=merged.full_text,
            doc_service=doc_service,
        )

        if not should_continue:
            # Story 1.2 AC: High-risk documents halt processing for manual review
            # Update status to indicate document needs review
            doc_service.update_status(document_id, DocumentStatus.PENDING_REVIEW)
            broadcast_document_status(
                matter_id=matter_id,
                document_id=document_id,
                status="pending_review",
                page_count=merged.page_count,
                ocr_confidence=merged.overall_confidence,
            )

            logger.info(
                "document_halted_for_injection_review",
                document_id=document_id,
                chunk_count=merged.chunk_count,
                page_count=merged.page_count,
            )

            return {
                "status": "pending_review",
                "document_id": document_id,
                "chunk_count": merged.chunk_count,
                "page_count": merged.page_count,
                "bbox_count": saved_count,
                "overall_confidence": merged.overall_confidence,
                "job_id": job_id,
                "halted_reason": "high_injection_risk",
                "rag_triggered": False,
            }

        # Clean up chunk records (Story 15.4)
        _run_async(cleanup_service.cleanup_document_chunks(document_id))

        # Story 17.7: Trigger downstream RAG re-processing
        _trigger_rag_reprocessing(
            document_id=document_id,
            matter_id=matter_id,
            full_text=merged.full_text,
            page_count=merged.page_count,
        )

        logger.info(
            "document_chunked_processing_complete",
            document_id=document_id,
            chunk_count=merged.chunk_count,
            page_count=merged.page_count,
            bbox_count=saved_count,
            confidence=merged.overall_confidence,
        )

        return {
            "status": "ocr_complete",
            "document_id": document_id,
            "chunk_count": merged.chunk_count,
            "page_count": merged.page_count,
            "bbox_count": saved_count,
            "overall_confidence": merged.overall_confidence,
            "job_id": job_id,
            "rag_triggered": True,  # Story 17.7
        }

    except MergeValidationError as e:
        logger.error(
            "merge_validation_failed",
            document_id=document_id,
            error=str(e),
            code=e.code,
        )

        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.OCR_FAILED,
        )

        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="ocr_failed",
            error_message=f"Merge failed: {e.message}",
        )

        return {
            "status": "merge_failed",
            "document_id": document_id,
            "error": e.message,
            "code": e.code,
        }


# =============================================================================
# Parallel Processing Trigger (Story 2.1 - Pipeline Improvements)
# =============================================================================


def _trigger_parallel_processing(
    document_id: str,
    matter_id: str,
    full_text: str,
    page_count: int,
    job_id: str | None = None,
) -> dict[str, list[str]]:
    """Trigger unified post-OCR processing chain after OCR completes.

    Uses the same unified chain as small documents, ensuring feature parity:
        validate_ocr → calculate_confidence → chunk_document → embed_chunks
        → extract_entities → resolve_aliases → (dispatch citations + dates)

    This replaces the previous parallel chain approach which caused:
    - Duplicate task dispatch (extract_citations ran twice)
    - No Docling for large docs (now runs in chunk_document)
    - Different code paths for small vs large docs

    The unified chain ensures:
    - Same processing as small documents
    - Docling layout-aware chunking for all documents
    - No duplicate task execution
    - Proper task sequencing

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID for namespace isolation.
        full_text: Extracted OCR text (used for logging only now).
        page_count: Total pages in document (used for logging only now).
        job_id: Optional job tracking UUID.

    Returns:
        Dict with lists of triggered and failed task names.
    """
    # Calculate text metrics for logging
    text_length = len(full_text) if full_text else 0
    word_count = len(full_text.split()) if full_text else 0

    logger.info(
        "unified_chain_triggered",
        document_id=document_id,
        matter_id=matter_id,
        page_count=page_count,
        text_length=text_length,
        word_count=word_count,
    )

    triggered_tasks: list[str] = []
    failed_tasks: list[str] = []

    # ==========================================================================
    # Unified Post-OCR Chain (same as small documents)
    # This ensures feature parity between small and large document processing.
    # Docling runs synchronously in chunk_document (fast: 2-4 sec for 400 pages).
    # ==========================================================================
    try:
        from app.workers.tasks.pipeline_chains import create_post_ocr_chain

        # Create unified chain - same as small docs
        # skip_downstream_dispatch=False means resolve_aliases will dispatch
        # extract_citations + extract_dates when it completes
        unified_chain = create_post_ocr_chain(
            document_id=document_id,
            matter_id=matter_id,
            job_id=job_id,
            skip_downstream_dispatch=False,  # Let resolve_aliases dispatch downstream
        )

        # Explicit queue routing - task_routes don't apply to chains dispatched from workers
        unified_chain.apply_async(queue="default")

        triggered_tasks.extend([
            "validate_ocr",
            "calculate_confidence",
            "chunk_document",
            "embed_chunks",
            "extract_entities",
            "resolve_aliases",
            # These are dispatched by resolve_aliases:
            "extract_citations",
            "extract_dates_from_document",
            "detect_contradictions",
        ])

        logger.info(
            "unified_chain_dispatched",
            document_id=document_id,
            chain="validate_ocr → calculate_confidence → chunk_document → embed_chunks → extract_entities → resolve_aliases → (citations + dates)",
        )

    except Exception as e:
        failed_tasks.extend([
            "validate_ocr",
            "calculate_confidence",
            "chunk_document",
            "embed_chunks",
            "extract_entities",
            "resolve_aliases",
        ])
        logger.error(
            "unified_chain_dispatch_failed",
            document_id=document_id,
            error=str(e),
        )

    logger.info(
        "post_ocr_processing_triggered",
        document_id=document_id,
        triggered=triggered_tasks,
        failed=failed_tasks,
        total_triggered=len(triggered_tasks),
        total_failed=len(failed_tasks),
    )

    return {
        "triggered": triggered_tasks,
        "failed": failed_tasks,
    }


def _trigger_rag_reprocessing(
    document_id: str,
    matter_id: str,
    full_text: str,
    page_count: int,
) -> None:
    """DEPRECATED: Use _trigger_parallel_processing instead.

    Kept for backward compatibility. Calls _trigger_parallel_processing.
    """
    _trigger_parallel_processing(
        document_id=document_id,
        matter_id=matter_id,
        full_text=full_text,
        page_count=page_count,
    )


# =============================================================================
# Retry Failed Chunks Task (Story 16.5)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.chunked_document_tasks.retry_failed_chunks",
    bind=True,
    max_retries=1,
    soft_time_limit=900,  # 15 minutes - retrying multiple chunks
    time_limit=960,  # 16 minutes - hard kill
)
def retry_failed_chunks(
    self,
    document_id: str,
    matter_id: str,
    job_id: str | None = None,
    chunk_service: OCRChunkService | None = None,
) -> dict:
    """Retry processing for failed chunks only.

    Story 16.5: Individual Chunk Retry

    Gets failed chunks from database, resets them to pending,
    and dispatches for reprocessing.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID.
        job_id: Optional job tracking UUID.
        chunk_service: Optional chunk service (for testing).

    Returns:
        Retry result dict.
    """
    chunks_svc = chunk_service or get_ocr_chunk_service()

    logger.info(
        "retry_failed_chunks_started",
        document_id=document_id,
    )

    try:
        # Get failed chunks
        failed_chunks = _run_async(chunks_svc.get_failed_chunks(document_id))

        if not failed_chunks:
            logger.info("no_failed_chunks_to_retry", document_id=document_id)
            return {
                "status": "no_failed_chunks",
                "document_id": document_id,
                "message": "No failed chunks to retry",
            }

        # Reset failed chunks to pending
        for chunk in failed_chunks:
            _run_async(
                chunks_svc.reset_chunk_for_retry(chunk.id)
            )

        logger.info(
            "failed_chunks_reset",
            document_id=document_id,
            chunk_count=len(failed_chunks),
        )

        # Dispatch chunked processing again
        process_document_chunked.apply_async(
            kwargs={
                "document_id": document_id,
                "matter_id": matter_id,
                "job_id": job_id,
            },
            queue="default",  # Explicit queue routing - workers listen on default, not celery
        )

        return {
            "status": "retry_dispatched",
            "document_id": document_id,
            "chunks_reset": len(failed_chunks),
        }

    except Exception as e:
        logger.error(
            "retry_failed_chunks_error",
            document_id=document_id,
            error=str(e),
        )
        raise


# =============================================================================
# Finalize Chunked Document Task (Story 19.2)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.chunked_document_tasks.finalize_chunked_document",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=300,  # 5 minutes - finalization
    time_limit=360,  # 6 minutes - hard kill
)
def finalize_chunked_document(
    self,
    chunk_results: list[dict] | None = None,
    document_id: str | None = None,
    matter_id: str | None = None,
    job_id: str | None = None,
) -> dict:
    """Finalize a chunked document by completing OCR stage.

    Story 19.2: Auto-merge trigger safety net.

    This task is triggered either:
    1. By chord callback after all chunks complete (receives chunk_results)
    2. By the periodic merge trigger as a safety net (no chunk_results)

    When called via chord, chunk_results contains the results from all
    process_single_chunk tasks, including full_text for proper merging.

    Since bounding boxes are already saved by process_single_chunk,
    this task:
    1. Merges full_text from chunk results (if provided)
    2. Updates document with extracted_text and OCR status
    3. Triggers downstream RAG processing
    4. Cleans up chunk records

    Uses idempotency check to prevent double processing.

    Args:
        chunk_results: Results from chord callback (list of chunk dicts).
        document_id: Document UUID.
        matter_id: Matter UUID.
        job_id: Optional job tracking UUID.

    Returns:
        Dict with finalization status.
    """
    chunks_svc = get_ocr_chunk_service()
    doc_service = get_document_service()
    cleanup_service = get_chunk_cleanup_service()

    logger.info(
        "finalize_chunked_document_started",
        document_id=document_id,
        matter_id=matter_id,
        job_id=job_id,
        has_chunk_results=chunk_results is not None,
        chunk_results_count=len(chunk_results) if chunk_results else 0,
    )

    # Idempotency check - skip if already finalized
    document = doc_service.get_document(document_id)
    if not document:
        logger.error(
            "finalize_document_not_found",
            document_id=document_id,
        )
        return {
            "status": "error",
            "document_id": document_id,
            "error": "Document not found",
        }

    if document.status in (
        DocumentStatus.OCR_COMPLETE,
        DocumentStatus.COMPLETED,
    ):
        # Check if document has chunks - if not, downstream may have failed
        # and we should trigger it again (recovery mechanism)
        from app.services.supabase.client import get_service_client
        client = get_service_client()
        chunk_count_response = (
            client.table("chunks")
            .select("id", count="exact")
            .eq("document_id", document_id)
            .execute()
        )
        chunk_count = chunk_count_response.count or 0

        if chunk_count == 0:
            # Document is OCR_COMPLETE but has 0 chunks - trigger downstream recovery
            logger.warning(
                "finalize_triggering_downstream_recovery",
                document_id=document_id,
                status=document.status.value,
                chunk_count=0,
                reason="Document has OCR_COMPLETE status but 0 chunks - likely downstream failed",
            )
            # Trigger downstream processing to recover
            recovery_result = _trigger_parallel_processing(
                document_id=document_id,
                matter_id=matter_id,
                full_text=document.extracted_text or "",
                page_count=document.page_count or 0,
                job_id=job_id,
            )
            return {
                "status": "recovery_triggered",
                "document_id": document_id,
                "current_status": document.status.value,
                "triggered_tasks": recovery_result["triggered"],
                "failed_tasks": recovery_result["failed"],
            }

        logger.info(
            "finalize_chunked_document_already_done",
            document_id=document_id,
            status=document.status.value,
            chunk_count=chunk_count,
        )
        return {
            "status": "already_complete",
            "document_id": document_id,
            "current_status": document.status.value,
            "chunk_count": chunk_count,
        }

    # Analyze chunk results if provided (from chord callback)
    successful_results = []
    failed_chunks = []

    if chunk_results:
        for i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                failed_chunks.append({
                    "chunk_index": i,
                    "error": str(result),
                })
                logger.error(
                    "chunk_failed_in_finalize",
                    document_id=document_id,
                    chunk_index=i,
                    error=str(result),
                )
            elif isinstance(result, dict) and result.get("status") == "success":
                successful_results.append(result)
            else:
                failed_chunks.append({
                    "chunk_index": i,
                    "error": f"Unexpected result: {result}",
                })

        if failed_chunks:
            logger.warning(
                "finalize_has_failed_chunk_results",
                document_id=document_id,
                failed_count=len(failed_chunks),
                successful_count=len(successful_results),
            )
            return {
                "status": "partial_failure",
                "document_id": document_id,
                "failed_chunks": failed_chunks,
                "successful_count": len(successful_results),
                "message": f"{len(failed_chunks)} chunks failed, retry possible",
            }
    else:
        # Fallback: check chunk progress from DB (for safety net trigger)
        progress = _run_async(chunks_svc.get_chunk_progress(document_id))

        if not progress.is_complete:
            logger.warning(
                "finalize_called_with_incomplete_chunks",
                document_id=document_id,
                completed=progress.completed,
                total=progress.total,
                pending=progress.pending,
                processing=progress.processing,
            )
            return {
                "status": "not_ready",
                "document_id": document_id,
                "message": f"Chunks not complete: {progress.completed}/{progress.total}",
                "pending": progress.pending,
                "processing": progress.processing,
            }

        if progress.has_failures:
            logger.warning(
                "finalize_has_failed_chunks",
                document_id=document_id,
                failed=progress.failed,
            )
            return {
                "status": "has_failures",
                "document_id": document_id,
                "failed_count": progress.failed,
                "message": f"{progress.failed} chunk(s) failed - use retry_failed_chunks to recover",
            }

    # Get all completed chunks to aggregate stats
    chunks = _run_async(chunks_svc.get_chunks_by_document(document_id))

    # Calculate aggregate stats from chunks
    total_page_count = 0
    for chunk in chunks:
        total_page_count += (chunk.page_end - chunk.page_start + 1)

    # Count bounding boxes from database
    from app.services.bounding_box_service import get_bounding_box_service
    bbox_service = get_bounding_box_service()
    bboxes, bbox_count = bbox_service.get_bounding_boxes_for_document(document_id)

    # Merge full_text from chunk results (if provided) or from bboxes
    if successful_results:
        # Sort by chunk_index and merge full_text
        sorted_results = sorted(successful_results, key=lambda x: x.get("chunk_index", 0))
        full_text = "\n\n".join(
            result.get("full_text", "") for result in sorted_results if result.get("full_text")
        )
        # Calculate confidence as weighted average
        total_pages = sum(r.get("page_count", 0) for r in sorted_results)
        if total_pages > 0:
            overall_confidence = sum(
                r.get("confidence", 0) * r.get("page_count", 0) for r in sorted_results
            ) / total_pages
        else:
            overall_confidence = sum(r.get("confidence", 0) for r in sorted_results) / len(sorted_results)

        logger.info(
            "merged_chunk_text",
            document_id=document_id,
            chunk_count=len(sorted_results),
            text_length=len(full_text),
            overall_confidence=round(overall_confidence, 4),
        )
    else:
        # Fallback: Get full text from bounding boxes
        full_text = " ".join(bbox["text"] for bbox in bboxes if bbox.get("text"))
        overall_confidence = None

    # Update document status to OCR_COMPLETE with extracted text
    update_kwargs = {
        "document_id": document_id,
        "status": DocumentStatus.OCR_COMPLETE,
        "extracted_text": full_text,
        "page_count": total_page_count,
    }
    if overall_confidence is not None:
        update_kwargs["ocr_confidence"] = overall_confidence

    doc_service.update_ocr_status(**update_kwargs)

    # =========================================================================
    # CRITICAL: Trigger downstream processing IMMEDIATELY after setting status
    # This prevents a race condition where:
    # - OCR_COMPLETE is set
    # - Non-critical operations below fail (broadcast, cleanup, etc.)
    # - Task retries, finds OCR_COMPLETE, returns early without triggering
    # - Document is stuck with 0 chunks
    # =========================================================================
    parallel_result = _trigger_parallel_processing(
        document_id=document_id,
        matter_id=matter_id,
        full_text=full_text,
        page_count=total_page_count,
        job_id=job_id,
    )

    # =========================================================================
    # Non-critical operations below - wrapped in try/except to prevent
    # failures from affecting the main processing pipeline
    # =========================================================================

    # Broadcast status update (non-critical - UI convenience)
    try:
        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="ocr_complete",
            page_count=total_page_count,
        )
    except Exception as e:
        logger.warning(
            "finalize_broadcast_failed",
            document_id=document_id,
            error=str(e),
        )

    # Update job tracking if available (non-critical - progress tracking)
    try:
        if job_id:
            from app.services.job_tracking import get_job_tracking_service
            from app.models.job import ProcessingJobUpdate
            job_tracker = get_job_tracking_service()
            update = ProcessingJobUpdate(
                status=JobStatus.PROCESSING,
                current_stage="ocr_complete",
                progress_pct=100,
                completed_stages=1,
            )
            _run_async(job_tracker.update_job(job_id, update))
    except Exception as e:
        logger.warning(
            "finalize_job_tracking_failed",
            document_id=document_id,
            job_id=job_id,
            error=str(e),
        )

    # Clean up chunk records (non-critical - storage optimization)
    try:
        _run_async(cleanup_service.cleanup_document_chunks(document_id))
    except Exception as e:
        logger.warning(
            "finalize_chunk_cleanup_failed",
            document_id=document_id,
            error=str(e),
        )

    logger.info(
        "finalize_chunked_document_complete",
        document_id=document_id,
        chunk_count=len(chunks),
        page_count=total_page_count,
        bbox_count=bbox_count,
        text_length=len(full_text),
        triggered_tasks=parallel_result["triggered"],
    )

    return {
        "status": "ocr_complete",
        "document_id": document_id,
        "chunk_count": len(chunks),
        "page_count": total_page_count,
        "bbox_count": bbox_count,
        "text_length": len(full_text),
        "job_id": job_id,
        "parallel_tasks_triggered": parallel_result["triggered"],
        "parallel_tasks_failed": parallel_result["failed"],
    }
