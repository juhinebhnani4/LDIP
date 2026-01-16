# Story 16.4: Implement Parallel Chunk Processing with Celery

Status: ready-for-dev

## Story

As a system processing large documents,
I want to process PDF chunks in parallel using Celery workers,
so that large documents complete in minutes instead of tens of minutes.

## Acceptance Criteria

1. **Parallel Dispatch**
   - Document with 17 chunks dispatches all chunk tasks simultaneously via Celery `group()`
   - Chunk status updated to 'processing' for each chunk when task starts
   - All chunks process concurrently (limited by worker pool)

2. **Single Chunk Processing Task**
   - `process_single_chunk` task receives chunk bytes and metadata
   - Calls Document AI sync API with chunk bytes
   - Updates chunk status to 'completed' on success
   - Returns OCR result for that chunk

3. **Result Collection and Merge**
   - When all chunk tasks complete, `merge_results` is called
   - Merged result stored via existing bbox_service and doc_service
   - Document status transitions to 'ocr_complete'

4. **Distributed Lock (RED TEAM)**
   - Acquire lock on `chunk:{document_id}:{chunk_index}` before processing
   - Prevents duplicate processing by multiple workers
   - Lock expires after 120 seconds to prevent deadlocks

5. **Store Results in Supabase Storage (DEBATE CLUB)**
   - Completed chunk stores result as JSON in Supabase Storage
   - Path: `ocr-chunks/{document_id}/{chunk_index}.json`
   - Update chunk record with `result_storage_path`
   - Store SHA256 checksum in `result_checksum`

6. **Error Handling (SHARK TANK)**
   - Celery group() catches individual task failures
   - Partial results from successful chunks preserved
   - Document NOT marked as permanently failed (retry possible)

## Tasks / Subtasks

- [ ] Task 1: Create chunked document processing task (AC: #1, #3)
  - [ ] Add `process_document_chunked` task to document_tasks.py
  - [ ] Use Celery `group()` to dispatch all chunks in parallel
  - [ ] Collect results via `GroupResult.get()`
  - [ ] Call OCRResultMerger after all chunks complete

- [ ] Task 2: Create single chunk processing task (AC: #2, #4, #5)
  - [ ] Add `process_single_chunk` task to document_tasks.py
  - [ ] Acquire distributed lock before processing
  - [ ] Call Document AI with chunk bytes
  - [ ] Store result in Supabase Storage
  - [ ] Update chunk status via OCRChunkService

- [ ] Task 3: Implement distributed locking (AC: #4)
  - [ ] Use Redis for distributed locks (existing Celery broker)
  - [ ] Key pattern: `chunk_lock:{document_id}:{chunk_index}`
  - [ ] Lock expiry: 120 seconds
  - [ ] Handle lock acquisition failure gracefully

- [ ] Task 4: Implement result storage (AC: #5)
  - [ ] Store chunk OCR result as JSON in Supabase Storage
  - [ ] Calculate SHA256 checksum of result
  - [ ] Update chunk record with storage path and checksum

- [ ] Task 5: Implement error handling (AC: #6)
  - [ ] Catch individual chunk failures in group
  - [ ] Preserve successful chunk results
  - [ ] Mark failed chunks for retry
  - [ ] Update document status appropriately

- [ ] Task 6: Write tests (AC: #1-6)
  - [ ] Create/update `backend/tests/workers/test_chunked_document_tasks.py`
  - [ ] Test parallel dispatch via group()
  - [ ] Test single chunk processing with mock Document AI
  - [ ] Test distributed locking
  - [ ] Test partial failure handling

## Dev Notes

### Architecture Compliance

**Parallel Chunk Processing Pattern:**
```python
# Add to backend/app/workers/tasks/document_tasks.py
from celery import group, chord
from redis import Redis
from redis.lock import Lock

# Redis lock configuration
CHUNK_LOCK_TIMEOUT = 120  # seconds
CHUNK_LOCK_KEY_PATTERN = "chunk_lock:{document_id}:{chunk_index}"


@celery_app.task(bind=True, name="process_document_chunked")
def process_document_chunked(
    self,
    document_id: str,
    matter_id: str,
    job_id: str | None,
) -> dict:
    """Process large document via parallel chunk processing.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID.
        job_id: Job tracking UUID.

    Returns:
        Processing result dict.
    """
    chunk_service = get_ocr_chunk_service()
    storage_service = get_storage_service()

    # Get all pending chunks for this document
    chunks = _run_async(chunk_service.get_pending_chunks(document_id))

    if not chunks:
        logger.warning("no_pending_chunks", document_id=document_id)
        return {"status": "no_chunks"}

    # Download PDF once (shared across chunks)
    doc_service = get_document_service()
    document = _run_async(doc_service.get_document(document_id))
    pdf_bytes = storage_service.download(document.storage_path)

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

    logger.info(
        "dispatching_parallel_chunks",
        document_id=document_id,
        chunk_count=len(chunk_tasks),
    )

    # Dispatch all chunks in parallel
    chunk_group = group(chunk_tasks)
    group_result = chunk_group.apply_async()

    # Wait for all chunks to complete (with timeout)
    try:
        results = group_result.get(
            timeout=600,  # 10 minute timeout for entire group
            propagate=False,  # Don't raise on individual failures
        )
    except TimeoutError:
        logger.error("chunk_group_timeout", document_id=document_id)
        _update_document_status(document_id, "ocr_failed", "Processing timeout")
        return {"status": "timeout"}

    # Check for failures
    successful_results = []
    failed_chunks = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            failed_chunks.append(chunks[i].chunk_index)
            logger.error(
                "chunk_failed",
                document_id=document_id,
                chunk_index=chunks[i].chunk_index,
                error=str(result),
            )
        else:
            successful_results.append(result)

    if failed_chunks:
        logger.warning(
            "partial_chunk_failures",
            document_id=document_id,
            failed_chunks=failed_chunks,
            successful_count=len(successful_results),
        )
        # Don't mark as permanently failed - allow retry
        return {
            "status": "partial_failure",
            "failed_chunks": failed_chunks,
            "successful_count": len(successful_results),
        }

    # All chunks successful - merge results
    return _merge_and_store_results(
        document_id=document_id,
        matter_id=matter_id,
        chunk_results=successful_results,
        job_id=job_id,
    )


@celery_app.task(bind=True, name="process_single_chunk")
def process_single_chunk(
    self,
    document_id: str,
    matter_id: str,
    chunk_id: str,
    chunk_index: int,
    page_start: int,
    page_end: int,
    job_id: str | None = None,
) -> dict:
    """Process a single PDF chunk through Document AI.

    Args:
        document_id: Parent document UUID.
        matter_id: Matter UUID.
        chunk_id: Chunk record UUID.
        chunk_index: 0-based chunk index.
        page_start: First page (1-based).
        page_end: Last page (1-based).
        job_id: Optional job tracking UUID.

    Returns:
        Chunk OCR result dict.
    """
    chunk_service = get_ocr_chunk_service()
    ocr_processor = get_ocr_processor()
    storage_service = get_storage_service()

    # Acquire distributed lock
    lock_key = CHUNK_LOCK_KEY_PATTERN.format(
        document_id=document_id,
        chunk_index=chunk_index,
    )
    redis_client = get_redis_client()
    lock = Lock(redis_client, lock_key, timeout=CHUNK_LOCK_TIMEOUT)

    if not lock.acquire(blocking=False):
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
        _run_async(
            chunk_service.update_status(chunk_id, ChunkStatus.PROCESSING)
        )

        # Get chunk PDF bytes
        pdf_chunker = get_pdf_chunker()
        document = _run_async(get_document_service().get_document(document_id))
        pdf_bytes = storage_service.download(document.storage_path)

        # Extract just this chunk's pages
        chunk_bytes = pdf_chunker.extract_pages(
            pdf_bytes,
            page_start - 1,  # Convert to 0-based
            page_end - 1,
        )

        # Process through Document AI
        ocr_result = ocr_processor.process_sync(chunk_bytes)

        # Store result in Supabase Storage
        result_path = f"ocr-chunks/{matter_id}/{document_id}/{chunk_index}.json"
        result_json = json.dumps(ocr_result)
        result_checksum = hashlib.sha256(result_json.encode()).hexdigest()

        storage_service.upload(result_path, result_json.encode())

        # Update chunk record
        _run_async(
            chunk_service.update_status(
                chunk_id,
                ChunkStatus.COMPLETED,
                result_storage_path=result_path,
                result_checksum=result_checksum,
            )
        )

        logger.info(
            "chunk_processed_successfully",
            document_id=document_id,
            chunk_index=chunk_index,
            bbox_count=len(ocr_result.get("bounding_boxes", [])),
        )

        return {
            "chunk_index": chunk_index,
            "page_start": page_start,
            "page_end": page_end,
            "result_path": result_path,
            "checksum": result_checksum,
            "bbox_count": len(ocr_result.get("bounding_boxes", [])),
        }

    except Exception as e:
        # Update chunk status to failed
        _run_async(
            chunk_service.update_status(
                chunk_id,
                ChunkStatus.FAILED,
                error_message=str(e),
            )
        )
        raise

    finally:
        lock.release()
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    workers/
      tasks/
        document_tasks.py    # Modify - Add chunked processing
    services/
      redis_client.py        # May need to add for locks
  tests/
    workers/
      test_chunked_document_tasks.py  # NEW or update existing
```

**Related Files:**
- [OCRChunkService](../../backend/app/services/ocr_chunk_service.py) - Chunk state management
- [OCRResultMerger](../../backend/app/services/ocr_result_merger.py) - Merge results (Story 16.3)
- [PDFChunker](../../backend/app/services/pdf_chunker.py) - Extract pages (Story 16.2)
- [celery.py](../../backend/app/workers/celery.py) - Celery config

### Technical Requirements

**Redis Lock Pattern:**
```python
# backend/app/services/redis_client.py
import os
from functools import lru_cache

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    """Get Redis client (same instance as Celery broker)."""
    return redis.from_url(REDIS_URL)
```

**Celery Group Pattern:**
```python
from celery import group

# Create group of tasks
tasks = [process_single_chunk.s(chunk_id=c.id, ...) for c in chunks]
job = group(tasks)

# Execute in parallel
result = job.apply_async()

# Wait for completion (with timeout)
results = result.get(timeout=600, propagate=False)

# propagate=False means exceptions are returned, not raised
for r in results:
    if isinstance(r, Exception):
        handle_failure(r)
```

**Document AI Integration:**
```python
# Existing OCRProcessor handles Document AI calls
# Just pass chunk bytes instead of full document
ocr_result = ocr_processor.process_sync(chunk_bytes)

# Result contains:
# {
#   "bounding_boxes": [...],
#   "full_text": "...",
#   "overall_confidence": 0.95,
#   "page_count": 25,
# }
```

### Testing Requirements

**Test Cases:**
```python
# tests/workers/test_chunked_document_tasks.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.workers.tasks.document_tasks import (
    process_document_chunked,
    process_single_chunk,
)
from app.models.ocr_chunk import ChunkStatus


class TestProcessDocumentChunked:
    @pytest.mark.asyncio
    async def test_dispatches_all_chunks_in_parallel(self):
        # Arrange
        mock_chunks = [
            MagicMock(id="c1", chunk_index=0, page_start=1, page_end=25),
            MagicMock(id="c2", chunk_index=1, page_start=26, page_end=50),
        ]

        with patch("app.workers.tasks.document_tasks.get_ocr_chunk_service") as mock_svc:
            mock_svc.return_value.get_pending_chunks = AsyncMock(return_value=mock_chunks)

            with patch("app.workers.tasks.document_tasks.group") as mock_group:
                mock_group.return_value.apply_async.return_value.get.return_value = [
                    {"status": "success"},
                    {"status": "success"},
                ]

                # Act
                result = process_document_chunked(
                    document_id="doc-123",
                    matter_id="matter-456",
                    job_id="job-789",
                )

                # Assert
                mock_group.assert_called_once()
                # Verify 2 tasks were grouped
                call_args = mock_group.call_args[0][0]
                assert len(call_args) == 2


class TestProcessSingleChunk:
    @pytest.mark.asyncio
    async def test_acquires_lock_before_processing(self):
        with patch("app.workers.tasks.document_tasks.get_redis_client") as mock_redis:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = True
            mock_redis.return_value.lock.return_value = mock_lock

            # ... rest of test
            pass

    @pytest.mark.asyncio
    async def test_updates_chunk_status_on_success(self):
        with patch("app.workers.tasks.document_tasks.get_ocr_chunk_service") as mock_svc:
            mock_svc.return_value.update_status = AsyncMock()

            # Act
            # ... process chunk

            # Assert
            mock_svc.return_value.update_status.assert_called_with(
                "chunk-id",
                ChunkStatus.COMPLETED,
                result_storage_path=pytest.ANY,
                result_checksum=pytest.ANY,
            )


class TestDistributedLock:
    def test_lock_prevents_duplicate_processing(self):
        # First worker acquires lock
        # Second worker fails to acquire
        # Second worker should not process
        pass

    def test_lock_expires_after_timeout(self):
        # Lock should auto-expire after 120 seconds
        # Allows recovery from dead workers
        pass
```

### References

- [Source: epic-2-pdf-chunking-parallel-processing.md#Story 2.4] - Full AC
- [Source: project-context.md#Backend] - Celery patterns
- [Source: Stories 16.1-16.3] - Dependencies

### Previous Story Intelligence

**From Story 16.2 (PDFChunker):**
- `split_pdf()` returns list of (chunk_bytes, page_start, page_end)
- Can also use `extract_pages(pdf_bytes, start, end)` for single chunk

**From Story 16.3 (OCRResultMerger):**
- `merge_results(chunk_results, document_id)` combines all chunks
- Handles page offset transformation

**From Existing Celery Setup:**
- Redis already configured as Celery broker
- Use existing `_run_async()` helper for async in sync context
- Follow existing task naming patterns

### Critical Implementation Notes

**DO NOT:**
- Download PDF separately for each chunk (download once, split in memory)
- Skip distributed locking (causes duplicate processing)
- Let group() propagate individual failures (breaks partial success)
- Store results only in memory (must persist to storage)

**MUST:**
- Use Celery `group()` for true parallel execution
- Acquire Redis lock before processing each chunk
- Store chunk results in Supabase Storage immediately
- Update chunk status throughout processing
- Handle partial failures gracefully
- Set reasonable timeouts (120s lock, 600s group)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

