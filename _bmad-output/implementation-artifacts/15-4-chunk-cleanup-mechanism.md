# Story 15.4: Implement Chunk Cleanup Mechanism

Status: ready-for-dev

## Story

As a system,
I want to clean up temporary chunk data after successful processing,
so that database resources are not wasted on completed work.

## Acceptance Criteria

1. **Post-Success Cleanup**
   - When document status transitions to 'ocr_complete', all chunk records are deleted
   - Cleanup triggered automatically after successful merge operation
   - Corresponding Supabase Storage files are deleted (`ocr-chunks/{matter_id}/{document_id}/`)

2. **Failure Preservation**
   - When document has failed chunks, chunk records are preserved for debugging
   - Failed chunks remain until explicit retry or manual cleanup
   - Provides visibility into what failed and why

3. **Scheduled Cleanup Job**
   - Celery beat task runs daily to clean stale chunk records
   - Deletes chunk records older than configurable retention period (default: 7 days)
   - Only cleans chunks where parent document status is 'completed' or 'failed'

4. **Orphan Detection (PRE-MORTEM)**
   - Detects Supabase Storage files without matching chunk records
   - Logs orphan files for monitoring
   - Optionally deletes orphan files older than retention period

5. **Configurable Retention (SHARK TANK)**
   - Retention period configurable via environment variable
   - Default: 7 days (`CHUNK_RETENTION_DAYS=7`)
   - Admin can override per-environment

## Tasks / Subtasks

- [ ] Task 1: Add cleanup methods to OCRChunkService (AC: #1, #2)
  - [ ] Add `delete_chunks_for_document(document_id)` method
  - [ ] Add `delete_chunk_storage_files(matter_id, document_id)` method
  - [ ] Return count of deleted records for logging

- [ ] Task 2: Create ChunkCleanupService (AC: #1, #3, #4, #5)
  - [ ] Create `backend/app/services/chunk_cleanup_service.py`
  - [ ] Implement `cleanup_completed_document(document_id)` - post-success cleanup
  - [ ] Implement `cleanup_stale_chunks(retention_days)` - scheduled cleanup
  - [ ] Implement `detect_orphan_storage_files()` - orphan detection
  - [ ] Add `CHUNK_RETENTION_DAYS` config with default 7

- [ ] Task 3: Create Celery beat task for scheduled cleanup (AC: #3)
  - [ ] Add `cleanup_stale_chunks` task to `backend/app/workers/tasks/maintenance_tasks.py`
  - [ ] Configure daily schedule in Celery beat
  - [ ] Log cleanup results with counts

- [ ] Task 4: Integrate cleanup into document processing pipeline (AC: #1)
  - [ ] Call `cleanup_completed_document()` after successful OCR merge
  - [ ] Ensure cleanup only runs on 'ocr_complete' status
  - [ ] Handle cleanup errors gracefully (don't fail document processing)

- [ ] Task 5: Write tests (AC: #1-5)
  - [ ] Create `backend/tests/services/test_chunk_cleanup_service.py`
  - [ ] Test post-success cleanup deletes all chunks
  - [ ] Test failed documents preserve chunks
  - [ ] Test stale chunk detection with mocked timestamps
  - [ ] Test orphan detection logic
  - [ ] Test configurable retention period

## Dev Notes

### Architecture Compliance

**ChunkCleanupService Pattern:**
```python
# backend/app/services/chunk_cleanup_service.py
import os
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import structlog

from app.services.ocr_chunk_service import (
    OCRChunkService,
    get_ocr_chunk_service,
)
from app.services.storage_service import (
    StorageService,
    get_storage_service,
)

logger = structlog.get_logger(__name__)

# Configurable retention period
CHUNK_RETENTION_DAYS = int(os.getenv("CHUNK_RETENTION_DAYS", "7"))


class ChunkCleanupService:
    """Service for cleaning up temporary chunk data.

    Handles:
    - Post-success cleanup after document OCR completes
    - Scheduled cleanup of stale chunk records
    - Orphan storage file detection and cleanup
    """

    def __init__(
        self,
        chunk_service: OCRChunkService | None = None,
        storage_service: StorageService | None = None,
    ) -> None:
        self._chunk_service = chunk_service
        self._storage_service = storage_service

    @property
    def chunk_service(self) -> OCRChunkService:
        if self._chunk_service is None:
            self._chunk_service = get_ocr_chunk_service()
        return self._chunk_service

    @property
    def storage_service(self) -> StorageService:
        if self._storage_service is None:
            self._storage_service = get_storage_service()
        return self._storage_service

    async def cleanup_completed_document(
        self,
        document_id: str,
        matter_id: str,
    ) -> dict:
        """Clean up chunk data after successful document processing.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID for storage path.

        Returns:
            Dict with cleanup results: {records_deleted, files_deleted}
        """
        results = {"records_deleted": 0, "files_deleted": 0}

        # Delete chunk records
        try:
            records_deleted = await self.chunk_service.delete_chunks_for_document(
                document_id
            )
            results["records_deleted"] = records_deleted
            logger.info(
                "chunk_records_deleted",
                document_id=document_id,
                count=records_deleted,
            )
        except Exception as e:
            logger.warning(
                "chunk_records_delete_failed",
                document_id=document_id,
                error=str(e),
            )

        # Delete storage files
        try:
            storage_path = f"ocr-chunks/{matter_id}/{document_id}"
            files_deleted = await self._delete_storage_folder(storage_path)
            results["files_deleted"] = files_deleted
            logger.info(
                "chunk_storage_deleted",
                document_id=document_id,
                path=storage_path,
                count=files_deleted,
            )
        except Exception as e:
            logger.warning(
                "chunk_storage_delete_failed",
                document_id=document_id,
                error=str(e),
            )

        return results

    async def cleanup_stale_chunks(
        self,
        retention_days: int | None = None,
    ) -> dict:
        """Clean up stale chunk records older than retention period.

        Only cleans chunks where parent document is completed or failed.

        Args:
            retention_days: Override retention period (default from env).

        Returns:
            Dict with cleanup results.
        """
        days = retention_days or CHUNK_RETENTION_DAYS
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Implementation calls database to find and delete stale chunks
        # Returns: {documents_cleaned, records_deleted, files_deleted}
        ...
```

**Celery Beat Task:**
```python
# Add to backend/app/workers/tasks/maintenance_tasks.py
from app.services.chunk_cleanup_service import (
    ChunkCleanupService,
    get_chunk_cleanup_service,
)

@celery_app.task(name="cleanup_stale_chunks")
def cleanup_stale_chunks_task() -> dict:
    """Daily task to clean up stale chunk records.

    Runs via Celery beat schedule.
    """
    service = get_chunk_cleanup_service()
    results = _run_async(service.cleanup_stale_chunks())

    logger.info(
        "stale_chunks_cleanup_complete",
        documents_cleaned=results.get("documents_cleaned", 0),
        records_deleted=results.get("records_deleted", 0),
    )

    return results


# Add to celery beat schedule in celery.py:
# "cleanup-stale-chunks": {
#     "task": "cleanup_stale_chunks",
#     "schedule": crontab(hour=3, minute=0),  # Run at 3 AM daily
# },
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    services/
      chunk_cleanup_service.py   # NEW - Cleanup service
      ocr_chunk_service.py       # Add delete methods
    workers/
      tasks/
        maintenance_tasks.py     # Add cleanup task
    celery.py                    # Add beat schedule
  tests/
    services/
      test_chunk_cleanup_service.py  # NEW - Tests
```

**Related Files:**
- [OCRChunkService](../../backend/app/services/ocr_chunk_service.py) - Add delete methods
- [StorageService](../../backend/app/services/storage_service.py) - Delete storage files
- [maintenance_tasks.py](../../backend/app/workers/tasks/maintenance_tasks.py) - Celery tasks
- [celery.py](../../backend/app/workers/celery.py) - Beat schedule

### Technical Requirements

**Delete Methods for OCRChunkService:**
```python
# Add to ocr_chunk_service.py
async def delete_chunks_for_document(self, document_id: str) -> int:
    """Delete all chunk records for a document.

    Args:
        document_id: Document UUID.

    Returns:
        Number of records deleted.
    """
    def _delete():
        response = (
            self.client.table("document_ocr_chunks")
            .delete()
            .eq("document_id", document_id)
            .execute()
        )
        return len(response.data) if response.data else 0

    count = await asyncio.to_thread(_delete)
    logger.info("chunks_deleted", document_id=document_id, count=count)
    return count
```

**Stale Chunk Query:**
```sql
-- Find stale chunks for cleanup
SELECT doc.document_id, doc.matter_id, COUNT(*) as chunk_count
FROM document_ocr_chunks doc
JOIN documents d ON doc.document_id = d.id
WHERE doc.created_at < :cutoff_date
  AND d.status IN ('ocr_complete', 'ocr_failed')
GROUP BY doc.document_id, doc.matter_id;
```

**Storage Path Convention:**
```
ocr-chunks/
  {matter_id}/
    {document_id}/
      0.json    # Chunk 0 results
      1.json    # Chunk 1 results
      ...
```

### Testing Requirements

**Test Cases:**
```python
# tests/services/test_chunk_cleanup_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, UTC

from app.services.chunk_cleanup_service import (
    ChunkCleanupService,
    CHUNK_RETENTION_DAYS,
)


@pytest.fixture
def mock_chunk_service():
    service = MagicMock()
    service.delete_chunks_for_document = AsyncMock(return_value=5)
    service.get_stale_chunk_documents = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_storage_service():
    service = MagicMock()
    service.delete_folder = AsyncMock(return_value=5)
    service.list_files = AsyncMock(return_value=[])
    return service


class TestCleanupCompletedDocument:
    @pytest.mark.asyncio
    async def test_deletes_chunks_and_storage(
        self,
        mock_chunk_service,
        mock_storage_service,
    ):
        # Arrange
        cleanup = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
        )

        # Act
        results = await cleanup.cleanup_completed_document(
            document_id="doc-123",
            matter_id="matter-456",
        )

        # Assert
        assert results["records_deleted"] == 5
        mock_chunk_service.delete_chunks_for_document.assert_called_once_with(
            "doc-123"
        )
        mock_storage_service.delete_folder.assert_called_once()


class TestCleanupStaleChunks:
    @pytest.mark.asyncio
    async def test_uses_configurable_retention(
        self,
        mock_chunk_service,
        mock_storage_service,
    ):
        # Arrange
        cleanup = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
        )

        # Act
        await cleanup.cleanup_stale_chunks(retention_days=3)

        # Assert - verify cutoff date calculation
        ...


class TestOrphanDetection:
    @pytest.mark.asyncio
    async def test_detects_orphan_storage_files(
        self,
        mock_chunk_service,
        mock_storage_service,
    ):
        # Arrange - storage has files, db has no matching records
        mock_storage_service.list_files.return_value = [
            "ocr-chunks/matter-1/doc-orphan/0.json",
        ]
        mock_chunk_service.get_chunks_by_document.return_value = []

        cleanup = ChunkCleanupService(
            chunk_service=mock_chunk_service,
            storage_service=mock_storage_service,
        )

        # Act
        orphans = await cleanup.detect_orphan_storage_files()

        # Assert
        assert len(orphans) == 1
```

### References

- [Source: epic-1-infrastructure-chunk-state-management.md#Story 1.4] - Full AC
- [Source: 15-2-ocr-chunk-service.md] - OCRChunkService base
- [Source: architecture.md#Storage] - Supabase Storage patterns
- [Source: maintenance_tasks.py] - Existing Celery tasks

### Previous Story Intelligence

**From Story 15.1 & 15.2:**
- Chunk records in `document_ocr_chunks` table
- Storage path: `ocr-chunks/{matter_id}/{document_id}/{chunk_index}.json`
- OCRChunkService has async methods with `asyncio.to_thread()`

**From Existing Maintenance Tasks:**
- Use `_run_async()` helper for sync Celery context
- Follow existing task naming and logging patterns
- Celery beat schedule in `celery.py`

### Critical Implementation Notes

**DO NOT:**
- Delete chunks for documents still being processed
- Delete chunks if any are still in 'processing' status
- Hard-delete without logging what was deleted
- Fail document processing if cleanup fails

**MUST:**
- Verify document status is 'ocr_complete' before cleanup
- Delete storage files AFTER database records (can reconstruct from storage)
- Use transactions for batch deletes where possible
- Log all cleanup operations with document_id and counts
- Handle partial cleanup failures gracefully
- Make retention period configurable via env var

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

