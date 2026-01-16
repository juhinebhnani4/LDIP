# Story 15.3: Integrate Chunk Progress with Job Tracking

Status: done

## Story

As a user uploading a large document,
I want to see progress updates during chunk processing,
so that I know the system is working and can estimate completion time.

## Acceptance Criteria

1. **Chunk Progress Updates**
   - When a chunk completes processing, JobTrackingService is updated with chunk progress
   - Progress message format: "Processing chunk 5/17"
   - Overall percentage calculated as: `(completed_chunks / total_chunks) * 100`

2. **Merge Stage Indication**
   - When all chunks complete successfully, job status shows "Merging OCR results"
   - Merge stage is a distinct stage in job progress tracking

3. **Failure Reporting**
   - When a chunk fails, job status shows error with chunk details
   - Error message includes: chunk_index, page_range (page_start-page_end)
   - Format: "Chunk 5 (pages 101-125) failed: {error_message}"

4. **Integration with OCRChunkService**
   - Uses `get_chunk_progress(document_id)` to calculate overall progress
   - Progress updates broadcast via SSE to frontend (existing pubsub_service)
   - Heartbeat sent for long-running chunk operations

## Tasks / Subtasks

- [ ] Task 1: Create ChunkProgressTracker class (AC: #1, #2, #3)
  - [ ] Create `backend/app/services/job_tracking/chunk_progress.py`
  - [ ] Define `ChunkProgressTracker` class that wraps JobTrackingService + OCRChunkService
  - [ ] Implement `update_chunk_progress(document_id, chunk_id)` method
  - [ ] Implement `start_merge_stage(document_id, job_id)` method
  - [ ] Implement `report_chunk_failure(chunk_id, error_message)` method

- [ ] Task 2: Integrate with existing document_tasks.py pipeline (AC: #1, #4)
  - [ ] Add chunk progress stage to PIPELINE_STAGES constant
  - [ ] Call `update_chunk_progress()` after each chunk OCR completes
  - [ ] Update `_update_job_stage_start()` to handle chunk progress
  - [ ] Ensure heartbeat is called during chunk processing

- [ ] Task 3: Update progress message formatting (AC: #1, #2, #3)
  - [ ] Create human-readable progress messages
  - [ ] Include chunk index and total in job metadata
  - [ ] Format failure messages with page range context

- [ ] Task 4: Broadcast chunk progress via SSE (AC: #4)
  - [ ] Use existing `broadcast_job_progress()` from pubsub_service
  - [ ] Include chunk_index, total_chunks, current_page_range in broadcast
  - [ ] Ensure frontend receives granular progress updates

- [ ] Task 5: Write tests (AC: #1-4)
  - [ ] Create `backend/tests/services/job_tracking/test_chunk_progress.py`
  - [ ] Test progress calculation: 5/17 chunks = ~29%
  - [ ] Test merge stage transition
  - [ ] Test failure message formatting with page ranges
  - [ ] Test broadcast calls are made with correct data

## Dev Notes

### Architecture Compliance

**Integration Pattern (MANDATORY):**
```python
# backend/app/services/job_tracking/chunk_progress.py
import structlog

from app.models.job import JobStatus
from app.services.job_tracking.tracker import (
    JobTrackingService,
    get_job_tracking_service,
)
from app.services.ocr_chunk_service import (
    OCRChunkService,
    get_ocr_chunk_service,
)
from app.services.pubsub_service import broadcast_job_progress

logger = structlog.get_logger(__name__)


class ChunkProgressTracker:
    """Tracks chunk processing progress and updates job status.

    Integrates OCRChunkService with JobTrackingService to provide
    granular progress updates during large document processing.
    """

    def __init__(
        self,
        job_tracker: JobTrackingService | None = None,
        chunk_service: OCRChunkService | None = None,
    ) -> None:
        self._job_tracker = job_tracker
        self._chunk_service = chunk_service

    @property
    def job_tracker(self) -> JobTrackingService:
        if self._job_tracker is None:
            self._job_tracker = get_job_tracking_service()
        return self._job_tracker

    @property
    def chunk_service(self) -> OCRChunkService:
        if self._chunk_service is None:
            self._chunk_service = get_ocr_chunk_service()
        return self._chunk_service

    async def update_chunk_progress(
        self,
        job_id: str,
        document_id: str,
        matter_id: str,
    ) -> None:
        """Update job progress based on chunk completion status."""
        progress = await self.chunk_service.get_chunk_progress(document_id)

        completed = progress.completed
        total = progress.total
        progress_pct = int((completed / total) * 100) if total > 0 else 0

        stage_message = f"Processing chunk {completed}/{total}"

        await self.job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            stage=stage_message,
            progress_pct=progress_pct,
        )

        # Broadcast to frontend
        broadcast_job_progress(
            matter_id=matter_id,
            job_id=job_id,
            progress_pct=progress_pct,
            stage=stage_message,
            metadata={
                "chunks_completed": completed,
                "chunks_total": total,
                "chunks_failed": progress.failed,
            },
        )

        logger.info(
            "chunk_progress_updated",
            job_id=job_id,
            document_id=document_id,
            completed=completed,
            total=total,
            progress_pct=progress_pct,
        )
```

**Failure Message Format:**
```python
def format_chunk_failure_message(
    chunk_index: int,
    page_start: int,
    page_end: int,
    error_message: str,
) -> str:
    """Format chunk failure for user display."""
    return f"Chunk {chunk_index + 1} (pages {page_start}-{page_end}) failed: {error_message}"
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    services/
      job_tracking/
        __init__.py          # Update exports
        chunk_progress.py    # NEW - ChunkProgressTracker
        tracker.py           # Existing JobTrackingService
  tests/
    services/
      job_tracking/
        test_chunk_progress.py  # NEW - Tests
```

**Related Files:**
- [JobTrackingService](../../backend/app/services/job_tracking/tracker.py) - Existing job tracking
- [OCRChunkService](../../backend/app/services/ocr_chunk_service.py) - Chunk state management (Story 15.2)
- [pubsub_service](../../backend/app/services/pubsub_service.py) - SSE broadcasting
- [document_tasks.py](../../backend/app/workers/tasks/document_tasks.py) - Integration point

### Technical Requirements

**Progress Calculation:**
```python
# From OCRChunkService.get_chunk_progress():
# Returns ChunkProgress(total=17, pending=5, processing=1, completed=10, failed=1)

# Calculate percentage based on completed + failed (both are done processing)
done = progress.completed + progress.failed
percentage = int((done / progress.total) * 100) if progress.total > 0 else 0
```

**Job Metadata Structure:**
```python
metadata = {
    "chunk_processing": {
        "total_chunks": 17,
        "completed_chunks": 10,
        "failed_chunks": 1,
        "current_chunk_index": 11,
        "current_page_range": {"start": 276, "end": 300},
    }
}
```

### Testing Requirements

**Test Cases:**
```python
# tests/services/job_tracking/test_chunk_progress.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.ocr_chunk import ChunkProgress
from app.services.job_tracking.chunk_progress import ChunkProgressTracker


@pytest.fixture
def mock_chunk_service():
    service = MagicMock()
    service.get_chunk_progress = AsyncMock()
    return service


@pytest.fixture
def mock_job_tracker():
    tracker = MagicMock()
    tracker.update_job_status = AsyncMock()
    return tracker


class TestChunkProgressTracker:
    @pytest.mark.asyncio
    async def test_update_chunk_progress_calculates_percentage(
        self,
        mock_chunk_service,
        mock_job_tracker,
    ):
        # Arrange
        mock_chunk_service.get_chunk_progress.return_value = ChunkProgress(
            total=17,
            pending=5,
            processing=1,
            completed=10,
            failed=1,
        )
        tracker = ChunkProgressTracker(
            job_tracker=mock_job_tracker,
            chunk_service=mock_chunk_service,
        )

        # Act
        await tracker.update_chunk_progress(
            job_id="job-123",
            document_id="doc-456",
            matter_id="matter-789",
        )

        # Assert - 10 completed out of 17 = 58%
        mock_job_tracker.update_job_status.assert_called_once()
        call_args = mock_job_tracker.update_job_status.call_args
        assert call_args.kwargs["progress_pct"] == 58
        assert "10/17" in call_args.kwargs["stage"]


class TestFormatChunkFailure:
    def test_formats_failure_with_page_range(self):
        from app.services.job_tracking.chunk_progress import format_chunk_failure_message

        result = format_chunk_failure_message(
            chunk_index=4,  # 0-indexed
            page_start=101,
            page_end=125,
            error_message="Document AI timeout",
        )

        assert result == "Chunk 5 (pages 101-125) failed: Document AI timeout"
```

### References

- [Source: epic-1-infrastructure-chunk-state-management.md#Story 1.3] - Full AC
- [Source: 15-2-ocr-chunk-service.md] - OCRChunkService dependency
- [Source: architecture.md#Job Tracking] - Job tracking patterns
- [Source: project-context.md#Backend] - Python patterns

### Previous Story Intelligence

**From Story 15.2 (OCR Chunk Service):**
- `get_chunk_progress(document_id)` returns `ChunkProgress` model
- ChunkProgress has: total, pending, processing, completed, failed counts
- Service uses `asyncio.to_thread()` for async Supabase calls
- Follow same exception and logging patterns

**From Story 2C-3 (Background Job Tracking):**
- JobTrackingService has `update_job_status()` with stage and progress_pct
- `broadcast_job_progress()` sends SSE updates to frontend
- Use `_run_async()` helper for sync Celery task integration

### Critical Implementation Notes

**DO NOT:**
- Create new job tracking table - use existing processing_jobs
- Bypass JobTrackingService - always use the service layer
- Skip SSE broadcasts - frontend depends on real-time updates
- Use global variables for progress state - use database

**MUST:**
- Use existing `broadcast_job_progress()` for SSE
- Include chunk_index and page_range in failure messages
- Calculate progress from OCRChunkService, not local state
- Send heartbeat during long-running chunk operations
- Handle case where job_id is None (graceful degradation)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

