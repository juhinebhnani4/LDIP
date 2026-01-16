# Story 16.5: Implement Individual Chunk Retry

Status: ready-for-dev

## Story

As a system handling processing failures,
I want to retry failed chunks individually without reprocessing successful chunks,
so that transient failures don't waste processing time and cost.

## Acceptance Criteria

1. **Selective Retry**
   - Given chunks 1-10 completed and chunk 11 failed
   - When retry is triggered for the document
   - Then only chunk 11 is reprocessed
   - And chunks 1-10 results are retrieved from storage (not re-OCR'd)

2. **Retryable Error Detection**
   - Chunk fails with retryable error (network, timeout, 429)
   - Status updated to 'failed' with error_message
   - retry_count is incremented

3. **Retry Limit Enforcement**
   - Chunk with retry_count < 3: can be reprocessed
   - Chunk with retry_count >= 3: marked as permanently failed
   - Document marked as 'ocr_failed' if any chunk permanently fails

4. **Retrieve from Storage on Retry (DEBATE CLUB)**
   - On retry, completed chunk results retrieved from Supabase Storage
   - Storage path from chunk record locates cached results
   - Only failed chunks sent to Document AI

## Tasks / Subtasks

- [ ] Task 1: Add retry methods to OCRChunkService (AC: #1, #2, #3)
  - [ ] Add `reset_failed_chunk(chunk_id)` - reset status to 'pending', increment retry_count
  - [ ] Add `is_retry_allowed(chunk)` - check retry_count < MAX_RETRIES
  - [ ] Add `mark_permanently_failed(chunk_id)` - prevent further retries
  - [ ] Define `MAX_CHUNK_RETRIES = 3` constant

- [ ] Task 2: Create retry document task (AC: #1, #4)
  - [ ] Add `retry_document_chunks` task to document_tasks.py
  - [ ] Load completed chunk results from Supabase Storage
  - [ ] Dispatch only failed chunks for processing
  - [ ] Merge all results (cached + newly processed)

- [ ] Task 3: Implement result retrieval from storage (AC: #4)
  - [ ] Load JSON from `result_storage_path` in chunk record
  - [ ] Validate checksum matches `result_checksum`
  - [ ] Convert to ChunkOCRResult for merger

- [ ] Task 4: Handle permanent failures (AC: #3)
  - [ ] Check retry_count before reprocessing
  - [ ] Mark chunk as permanently failed if limit exceeded
  - [ ] Mark document as 'ocr_failed' if any chunk permanently fails
  - [ ] Provide clear error message with failed chunk details

- [ ] Task 5: Write tests (AC: #1-4)
  - [ ] Create `backend/tests/workers/test_chunk_retry.py`
  - [ ] Test selective retry (only failed chunks)
  - [ ] Test storage retrieval for completed chunks
  - [ ] Test retry limit enforcement
  - [ ] Test permanent failure handling

## Dev Notes

### Architecture Compliance

**Retry Service Pattern:**
```python
# Add to backend/app/services/ocr_chunk_service.py

MAX_CHUNK_RETRIES = 3


class OCRChunkService:
    # ... existing methods ...

    async def reset_failed_chunk(self, chunk_id: str) -> DocumentOCRChunk:
        """Reset failed chunk for retry.

        Increments retry_count and resets status to 'pending'.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            Updated chunk record.

        Raises:
            ChunkNotFoundError: If chunk not found.
            RetryLimitExceededError: If retry_count >= MAX_CHUNK_RETRIES.
        """
        chunk = await self.get_chunk(chunk_id)
        if not chunk:
            raise ChunkNotFoundError(chunk_id)

        if chunk.retry_count >= MAX_CHUNK_RETRIES:
            raise RetryLimitExceededError(
                chunk_id=chunk_id,
                retry_count=chunk.retry_count,
                max_retries=MAX_CHUNK_RETRIES,
            )

        def _update():
            return (
                self.client.table("document_ocr_chunks")
                .update({
                    "status": ChunkStatus.PENDING.value,
                    "retry_count": chunk.retry_count + 1,
                    "error_message": None,
                    "processing_started_at": None,
                    "processing_completed_at": None,
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", chunk_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)
        return self._db_row_to_chunk(response.data[0])

    def is_retry_allowed(self, chunk: DocumentOCRChunk) -> bool:
        """Check if chunk can be retried.

        Args:
            chunk: Chunk record.

        Returns:
            True if retry_count < MAX_CHUNK_RETRIES.
        """
        return chunk.retry_count < MAX_CHUNK_RETRIES

    async def mark_permanently_failed(
        self,
        chunk_id: str,
        reason: str = "Max retries exceeded",
    ) -> DocumentOCRChunk:
        """Mark chunk as permanently failed (no more retries).

        Args:
            chunk_id: Chunk UUID.
            reason: Failure reason.

        Returns:
            Updated chunk record.
        """
        def _update():
            return (
                self.client.table("document_ocr_chunks")
                .update({
                    "status": ChunkStatus.FAILED.value,
                    "error_message": f"PERMANENT: {reason}",
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", chunk_id)
                .execute()
            )

        response = await asyncio.to_thread(_update)
        logger.warning(
            "chunk_permanently_failed",
            chunk_id=chunk_id,
            reason=reason,
        )
        return self._db_row_to_chunk(response.data[0])


class RetryLimitExceededError(OCRChunkServiceError):
    """Raised when chunk retry limit is exceeded."""
    def __init__(self, chunk_id: str, retry_count: int, max_retries: int):
        super().__init__(
            f"Chunk {chunk_id} exceeded retry limit ({retry_count}/{max_retries})",
            code="RETRY_LIMIT_EXCEEDED",
        )
```

**Retry Document Task:**
```python
# Add to backend/app/workers/tasks/document_tasks.py

@celery_app.task(bind=True, name="retry_document_chunks")
def retry_document_chunks(
    self,
    document_id: str,
    matter_id: str,
    job_id: str | None = None,
) -> dict:
    """Retry failed chunks for a document.

    Only reprocesses failed chunks - completed chunks are retrieved
    from Supabase Storage.

    Args:
        document_id: Document UUID.
        matter_id: Matter UUID.
        job_id: Optional job tracking UUID.

    Returns:
        Processing result dict.
    """
    chunk_service = get_ocr_chunk_service()
    storage_service = get_storage_service()
    merger = get_ocr_result_merger()

    # Get all chunks for document
    all_chunks = _run_async(chunk_service.get_chunks_by_document(document_id))

    completed_results = []
    failed_chunks = []

    # Separate completed vs failed chunks
    for chunk in all_chunks:
        if chunk.status == ChunkStatus.COMPLETED:
            # Load result from storage
            result = _load_chunk_result_from_storage(
                chunk,
                storage_service,
            )
            if result:
                completed_results.append(result)
            else:
                # Storage corrupted - need to reprocess
                failed_chunks.append(chunk)
        elif chunk.status == ChunkStatus.FAILED:
            if chunk_service.is_retry_allowed(chunk):
                failed_chunks.append(chunk)
            else:
                # Permanently failed - document cannot complete
                _run_async(
                    chunk_service.mark_permanently_failed(
                        chunk.id,
                        "Max retries exceeded",
                    )
                )
                _update_document_status(
                    document_id,
                    "ocr_failed",
                    f"Chunk {chunk.chunk_index} permanently failed",
                )
                return {
                    "status": "permanent_failure",
                    "failed_chunk": chunk.chunk_index,
                }

    if not failed_chunks:
        # All chunks already completed - just merge
        logger.info(
            "all_chunks_completed_merging",
            document_id=document_id,
            chunk_count=len(completed_results),
        )
        return _merge_and_store_results(
            document_id=document_id,
            matter_id=matter_id,
            chunk_results=completed_results,
            job_id=job_id,
        )

    # Reset failed chunks for retry
    for chunk in failed_chunks:
        _run_async(chunk_service.reset_failed_chunk(chunk.id))

    logger.info(
        "retrying_failed_chunks",
        document_id=document_id,
        failed_count=len(failed_chunks),
        completed_count=len(completed_results),
    )

    # Dispatch only failed chunks
    chunk_tasks = [
        process_single_chunk.s(
            document_id=document_id,
            matter_id=matter_id,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            job_id=job_id,
        )
        for chunk in failed_chunks
    ]

    # Process failed chunks
    chunk_group = group(chunk_tasks)
    group_result = chunk_group.apply_async()

    try:
        new_results = group_result.get(timeout=600, propagate=False)
    except TimeoutError:
        logger.error("retry_timeout", document_id=document_id)
        return {"status": "timeout"}

    # Combine completed results with newly processed
    all_results = completed_results + [r for r in new_results if not isinstance(r, Exception)]

    # Check for new failures
    still_failed = [r for r in new_results if isinstance(r, Exception)]
    if still_failed:
        logger.warning(
            "retry_partial_failure",
            document_id=document_id,
            still_failed_count=len(still_failed),
        )
        return {
            "status": "partial_failure",
            "still_failed_count": len(still_failed),
        }

    # All successful - merge
    return _merge_and_store_results(
        document_id=document_id,
        matter_id=matter_id,
        chunk_results=all_results,
        job_id=job_id,
    )


def _load_chunk_result_from_storage(
    chunk: DocumentOCRChunk,
    storage_service: StorageService,
) -> ChunkOCRResult | None:
    """Load chunk OCR result from Supabase Storage.

    Args:
        chunk: Chunk record with result_storage_path.
        storage_service: Storage service instance.

    Returns:
        ChunkOCRResult if valid, None if corrupted/missing.
    """
    if not chunk.result_storage_path:
        return None

    try:
        result_bytes = storage_service.download(chunk.result_storage_path)
        result_json = json.loads(result_bytes.decode())

        # Validate checksum
        if chunk.result_checksum:
            computed = hashlib.sha256(result_bytes).hexdigest()
            if computed != chunk.result_checksum:
                logger.warning(
                    "chunk_result_checksum_mismatch",
                    chunk_id=chunk.id,
                    expected=chunk.result_checksum,
                    computed=computed,
                )
                return None

        return ChunkOCRResult(
            chunk_index=chunk.chunk_index,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            bounding_boxes=result_json.get("bounding_boxes", []),
            full_text=result_json.get("full_text", ""),
            overall_confidence=result_json.get("overall_confidence", 0.0),
            page_count=chunk.page_end - chunk.page_start + 1,
            checksum=chunk.result_checksum,
        )

    except Exception as e:
        logger.error(
            "chunk_result_load_failed",
            chunk_id=chunk.id,
            path=chunk.result_storage_path,
            error=str(e),
        )
        return None
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    services/
      ocr_chunk_service.py   # Modify - Add retry methods
    workers/
      tasks/
        document_tasks.py    # Add retry_document_chunks task
  tests/
    workers/
      test_chunk_retry.py    # NEW - Retry tests
```

**Related Files:**
- [OCRChunkService](../../backend/app/services/ocr_chunk_service.py) - Retry logic
- [document_tasks.py](../../backend/app/workers/tasks/document_tasks.py) - Retry task
- [StorageService](../../backend/app/services/storage_service.py) - Result retrieval

### Technical Requirements

**Retry Flow:**
```
1. Get all chunks for document
2. For each chunk:
   - COMPLETED: Load from storage
   - FAILED + retry_allowed: Add to retry list
   - FAILED + retry_exceeded: Mark permanent, fail document
3. Reset failed chunks to 'pending'
4. Dispatch only failed chunks via group()
5. Combine cached + new results
6. Merge all and store
```

**Error Classification:**
```python
RETRYABLE_ERRORS = [
    "timeout",
    "network_error",
    "rate_limited",  # 429
    "service_unavailable",  # 503
    "internal_error",  # 500
]

NON_RETRYABLE_ERRORS = [
    "invalid_pdf",
    "corrupted_content",
    "unsupported_format",
]
```

### Testing Requirements

**Test Cases:**
```python
# tests/workers/test_chunk_retry.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.models.ocr_chunk import ChunkStatus, DocumentOCRChunk
from app.services.ocr_chunk_service import (
    OCRChunkService,
    MAX_CHUNK_RETRIES,
    RetryLimitExceededError,
)


class TestResetFailedChunk:
    @pytest.mark.asyncio
    async def test_resets_status_and_increments_retry(self, mock_supabase):
        # Arrange
        chunk = DocumentOCRChunk(
            id="chunk-1",
            status=ChunkStatus.FAILED,
            retry_count=1,
            # ... other fields
        )
        service = OCRChunkService()

        # Act
        result = await service.reset_failed_chunk(chunk.id)

        # Assert
        assert result.status == ChunkStatus.PENDING
        assert result.retry_count == 2
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_raises_when_retry_limit_exceeded(self, mock_supabase):
        # Arrange
        chunk = DocumentOCRChunk(
            id="chunk-1",
            status=ChunkStatus.FAILED,
            retry_count=MAX_CHUNK_RETRIES,  # At limit
            # ... other fields
        )
        service = OCRChunkService()

        # Act & Assert
        with pytest.raises(RetryLimitExceededError):
            await service.reset_failed_chunk(chunk.id)


class TestRetryDocumentChunks:
    @pytest.mark.asyncio
    async def test_only_reprocesses_failed_chunks(self):
        # Arrange - 10 completed, 1 failed
        completed_chunks = [
            MagicMock(
                id=f"c{i}",
                status=ChunkStatus.COMPLETED,
                result_storage_path=f"path/{i}.json",
            )
            for i in range(10)
        ]
        failed_chunk = MagicMock(
            id="c10",
            status=ChunkStatus.FAILED,
            retry_count=0,
        )
        all_chunks = completed_chunks + [failed_chunk]

        # Act
        # ... call retry_document_chunks

        # Assert
        # - 10 chunks loaded from storage
        # - Only 1 chunk dispatched for processing

    @pytest.mark.asyncio
    async def test_loads_completed_from_storage(self):
        # Arrange
        chunk = MagicMock(
            id="c1",
            status=ChunkStatus.COMPLETED,
            result_storage_path="ocr-chunks/m/d/0.json",
            result_checksum="abc123",
        )

        with patch("storage_service.download") as mock_download:
            mock_download.return_value = b'{"bounding_boxes": [], "full_text": ""}'

            # Act
            result = _load_chunk_result_from_storage(chunk, mock_storage)

            # Assert
            assert result is not None
            mock_download.assert_called_once_with("ocr-chunks/m/d/0.json")


class TestPermanentFailure:
    @pytest.mark.asyncio
    async def test_marks_document_failed_on_permanent_chunk_failure(self):
        # Arrange - chunk at retry limit
        chunk = MagicMock(
            id="c1",
            status=ChunkStatus.FAILED,
            retry_count=MAX_CHUNK_RETRIES,
            chunk_index=5,
        )

        # Act
        result = retry_document_chunks("doc-1", "matter-1", None)

        # Assert
        assert result["status"] == "permanent_failure"
        assert result["failed_chunk"] == 5
```

### References

- [Source: epic-2-pdf-chunking-parallel-processing.md#Story 2.5] - Full AC
- [Source: Stories 16.2-16.4] - Dependencies
- [Source: project-context.md#Backend] - Error handling patterns

### Previous Story Intelligence

**From Story 16.4:**
- Chunk results stored in Supabase Storage at `result_storage_path`
- Checksum stored in `result_checksum` for validation
- `process_single_chunk` task handles individual chunk OCR

**From Story 15.2:**
- OCRChunkService has status update methods
- Status enum: PENDING, PROCESSING, COMPLETED, FAILED

### Critical Implementation Notes

**DO NOT:**
- Re-OCR chunks that already have valid results in storage
- Allow infinite retries (max 3)
- Lose successful chunk results on retry
- Skip checksum validation when loading from storage

**MUST:**
- Load completed results from storage (cost savings)
- Validate checksums before using cached results
- Increment retry_count on each retry attempt
- Mark document failed if any chunk permanently fails
- Provide clear logging of retry decisions

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

