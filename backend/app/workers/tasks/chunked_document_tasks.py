"""Celery tasks for parallel chunk processing of large documents.

Story 16.4: Implement Parallel Chunk Processing with Celery
Story 16.5: Implement Individual Chunk Retry
Story 17.3: Per-Chunk Timeout and Rate Limiting

Processes large PDFs (>30 pages) by splitting into chunks and
processing each chunk in parallel using Celery group().
"""

import asyncio
import hashlib
import json
import signal
import time
from io import BytesIO

import pypdf
import structlog
from celery import group

from app.core.circuit_breaker import CircuitOpenError
from app.models.document import DocumentStatus
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
from app.services.storage_service import (
    StorageService,
    get_storage_service,
)
from app.workers.celery import celery_app

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
    return asyncio.run(coro)


# =============================================================================
# Chunked Document Processing Task
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.chunked_document_tasks.process_document_chunked",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
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
        document = docs_svc.get_document_by_id(document_id)
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

        # Dispatch all chunks in parallel using Celery group()
        chunk_group = group(chunk_tasks)
        group_result = chunk_group.apply_async()

        # Wait for all chunks to complete (with timeout)
        try:
            results = group_result.get(
                timeout=CHUNK_GROUP_TIMEOUT,
                propagate=False,  # Don't raise on individual failures
            )
        except TimeoutError:
            logger.error("chunk_group_timeout", document_id=document_id)
            docs_svc.update_ocr_status(
                document_id=document_id,
                status=DocumentStatus.OCR_FAILED,
            )
            broadcast_document_status(
                matter_id=matter_id,
                document_id=document_id,
                status="ocr_failed",
                error_message="Processing timeout",
            )
            return {
                "status": "timeout",
                "document_id": document_id,
                "message": "Chunk processing timed out",
            }

        # Analyze results - separate successes from failures
        successful_results = []
        failed_chunks = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_chunks.append({
                    "chunk_index": chunks[i].chunk_index,
                    "error": str(result),
                })
                logger.error(
                    "chunk_failed",
                    document_id=document_id,
                    chunk_index=chunks[i].chunk_index,
                    error=str(result),
                )
            elif isinstance(result, dict) and result.get("status") == "success":
                successful_results.append(result)
            else:
                # Unexpected result format
                failed_chunks.append({
                    "chunk_index": chunks[i].chunk_index,
                    "error": f"Unexpected result: {result}",
                })

        # If any chunks failed, document is not fully processed
        if failed_chunks:
            logger.warning(
                "partial_chunk_failures",
                document_id=document_id,
                failed_count=len(failed_chunks),
                successful_count=len(successful_results),
            )

            # Update progress with failure info
            if job_id:
                _run_async(
                    progress_tracker.report_chunk_failure(
                        job_id=job_id,
                        document_id=document_id,
                        matter_id=matter_id,
                        chunk_index=failed_chunks[0]["chunk_index"],
                        page_start=chunks[failed_chunks[0]["chunk_index"]].page_start,
                        page_end=chunks[failed_chunks[0]["chunk_index"]].page_end,
                        error_message=failed_chunks[0]["error"],
                    )
                )

            return {
                "status": "partial_failure",
                "document_id": document_id,
                "failed_chunks": failed_chunks,
                "successful_count": len(successful_results),
                "message": f"{len(failed_chunks)} chunks failed, retry possible",
            }

        # All chunks successful - merge results
        return _merge_and_store_results(
            document_id=document_id,
            matter_id=matter_id,
            successful_results=successful_results,
            job_id=job_id,
        )

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

            # Get document storage path
            document = docs_svc.get_document_by_id(document_id)
            if not document or not document.storage_path:
                raise ChunkProcessingError(
                    "Document not found or missing storage path",
                    code="DOCUMENT_NOT_FOUND",
                )

            # Download full PDF
            pdf_bytes = storage.download_file(document.storage_path)

            # Extract just this chunk's pages
            chunk_result = chunker.split_pdf(pdf_bytes, chunk_size=page_end - page_start + 1)

            # Find the chunk bytes for our page range
            chunk_bytes = None
            for c_bytes, c_start, c_end in chunk_result:
                if c_start == page_start and c_end == page_end:
                    chunk_bytes = c_bytes
                    break

            if chunk_bytes is None:
                # If exact match not found, extract directly
                reader = pypdf.PdfReader(BytesIO(pdf_bytes))
                writer = pypdf.PdfWriter()
                for page_idx in range(page_start - 1, page_end):  # Convert to 0-based
                    writer.add_page(reader.pages[page_idx])
                buffer = BytesIO()
                writer.write(buffer)
                chunk_bytes = buffer.getvalue()

            # Process through Document AI (with circuit breaker - Story 17.2)
            ocr_result = ocr.process_document(
                pdf_content=chunk_bytes,
                document_id=f"{document_id}_chunk_{chunk_index}",
            )

            # Prepare result for storage
            result_data = {
                "chunk_index": chunk_index,
                "page_start": page_start,
                "page_end": page_end,
                "bounding_boxes": [
                    bbox.model_dump() if hasattr(bbox, "model_dump") else bbox
                    for bbox in ocr_result.bounding_boxes
                ],
                "full_text": ocr_result.full_text,
                "overall_confidence": ocr_result.overall_confidence,
                "page_count": ocr_result.page_count,
            }

            # Store result in Supabase Storage
            result_json = json.dumps(result_data)
            result_checksum = hashlib.sha256(result_json.encode()).hexdigest()

            # Storage path for chunk result
            result_path = f"{matter_id}/chunks/{document_id}/{chunk_index}.json"
            storage.upload_file(
                matter_id=matter_id,
                subfolder="chunks",
                file_content=result_json.encode(),
                filename=f"{document_id}_{chunk_index}.json",
                content_type="application/json",
            )

            # Update chunk record with completion info
            _run_async(
                chunks_svc.update_result(
                    chunk_id=chunk_id,
                    result_storage_path=result_path,
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

            return {
                "status": "success",
                "chunk_index": chunk_index,
                "page_start": page_start,
                "page_end": page_end,
                "result_path": result_path,
                "checksum": result_checksum,
                "bbox_count": len(ocr_result.bounding_boxes),
                "confidence": ocr_result.overall_confidence,
                "page_count": ocr_result.page_count,
                "full_text": ocr_result.full_text,
                "bounding_boxes": result_data["bounding_boxes"],
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
# RAG Re-Processing Trigger (Story 17.7)
# =============================================================================


def _trigger_rag_reprocessing(
    document_id: str,
    matter_id: str,
    full_text: str,
    page_count: int,
) -> None:
    """Trigger downstream RAG pipeline re-processing after OCR completes.

    Story 17.7: Ensures the RAG pipeline (chunking, embedding, vector store)
    is updated with the newly OCR'd document text.

    This dispatches a Celery task to:
    1. Re-chunk the document text for embedding
    2. Generate embeddings for each chunk
    3. Upsert to Pinecone vector store

    If the RAG task queue is unavailable, logs warning but doesn't fail
    the OCR completion (graceful degradation).

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID for namespace isolation.
        full_text: Extracted OCR text.
        page_count: Total pages in document.
    """
    try:
        # Import here to avoid circular dependency
        from app.workers.tasks.rag_tasks import process_document_for_rag

        # Calculate text metrics for logging
        text_length = len(full_text) if full_text else 0
        word_count = len(full_text.split()) if full_text else 0

        logger.info(
            "rag_reprocessing_triggered",
            document_id=document_id,
            matter_id=matter_id,
            page_count=page_count,
            text_length=text_length,
            word_count=word_count,
        )

        # Dispatch RAG processing task
        process_document_for_rag.delay(
            document_id=document_id,
            matter_id=matter_id,
            extracted_text=full_text,
            reprocess=True,  # Indicates this is a re-processing from chunked OCR
        )

    except ImportError:
        logger.warning(
            "rag_task_not_available",
            document_id=document_id,
            message="RAG tasks not configured, skipping re-processing",
        )
    except Exception as e:
        # Don't fail OCR completion if RAG trigger fails
        logger.warning(
            "rag_trigger_failed",
            document_id=document_id,
            error=str(e),
            message="OCR completed but RAG re-processing could not be triggered",
        )


# =============================================================================
# Retry Failed Chunks Task (Story 16.5)
# =============================================================================


@celery_app.task(
    name="app.workers.tasks.chunked_document_tasks.retry_failed_chunks",
    bind=True,
    max_retries=1,
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
        process_document_chunked.delay(
            document_id=document_id,
            matter_id=matter_id,
            job_id=job_id,
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
