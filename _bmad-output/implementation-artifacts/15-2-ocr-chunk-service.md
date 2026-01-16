# Story 15.2: Implement OCR Chunk Service

Status: done

## Story

As a backend developer,
I want a service to manage OCR chunk records,
so that I can create, update, and query chunk processing state.

## Acceptance Criteria

1. **Create Chunk Operation**
   - `create_chunk(document_id, matter_id, chunk_index, page_start, page_end)` creates a new chunk record
   - Status defaults to 'pending'
   - chunk_index is validated as unique per document (DB enforces, service handles error gracefully)
   - Returns `DocumentOCRChunk` Pydantic model

2. **Update Status Operation**
   - `update_status(chunk_id, status, error_message=None)` updates chunk status
   - `processing_started_at` is set when status changes to 'processing'
   - `processing_completed_at` is set when status changes to 'completed' or 'failed'
   - Validates status transition is valid (e.g., cannot go from 'completed' back to 'pending')

3. **Query Operations**
   - `get_chunks_by_document(document_id)` returns all chunks ordered by chunk_index
   - `get_failed_chunks(document_id)` returns only chunks with status 'failed'
   - `get_chunk(chunk_id)` returns single chunk or None
   - `get_pending_chunks(document_id)` returns chunks ready for processing

4. **Heartbeat Detection (CHAOS MONKEY)**
   - Chunks in 'processing' status for >90 seconds without heartbeat are stale
   - `detect_stale_chunks()` finds chunks that exceed timeout threshold
   - `mark_chunk_stale(chunk_id)` marks chunk as 'failed' with "worker_timeout" error
   - Stale chunks become eligible for retry via existing retry mechanisms
   - `update_heartbeat(chunk_id)` updates `processing_started_at` to current time (heartbeat signal)

5. **Batch Operations**
   - `create_chunks_for_document(document_id, matter_id, chunk_specs: list)` creates multiple chunks in one transaction
   - `get_chunk_progress(document_id)` returns summary: {total, pending, processing, completed, failed}

## Tasks / Subtasks

- [x] Task 1: Create Pydantic models for OCR chunks (AC: #1, #2, #3)
  - [x] Create `backend/app/models/ocr_chunk.py`
  - [x] Define `ChunkStatus` enum matching DB constraint (pending, processing, completed, failed)
  - [x] Define `DocumentOCRChunk` model with all columns from migration
  - [x] Define `DocumentOCRChunkCreate` model for input validation
  - [x] Define `DocumentOCRChunkUpdate` model for status updates
  - [x] Define `ChunkProgress` model for progress summary
  - [x] Add camelCase aliases for frontend compatibility (Field alias pattern)

- [x] Task 2: Create OCRChunkService class (AC: #1, #2, #3, #4, #5)
  - [x] Create `backend/app/services/ocr_chunk_service.py`
  - [x] Implement `__init__` with Supabase client lazy loading
  - [x] Follow JobTrackingService pattern for async operations
  - [x] Use `asyncio.to_thread()` for sync Supabase calls

- [x] Task 3: Implement CRUD operations (AC: #1, #2, #3)
  - [x] `create_chunk()` - insert single chunk with validation
  - [x] `get_chunk()` - get by ID
  - [x] `update_status()` - update with timestamp logic
  - [x] `get_chunks_by_document()` - ordered list query
  - [x] `get_failed_chunks()` - filtered query
  - [x] `get_pending_chunks()` - filtered query for retry/processing

- [x] Task 4: Implement heartbeat detection (AC: #4)
  - [x] `update_heartbeat()` - update processing_started_at timestamp
  - [x] `detect_stale_chunks()` - find chunks exceeding 90s threshold
  - [x] `mark_chunk_stale()` - mark as failed with worker_timeout error
  - [x] Add `STALE_CHUNK_THRESHOLD_SECONDS = 90` constant

- [x] Task 5: Implement batch operations (AC: #5)
  - [x] `create_chunks_for_document()` - bulk insert
  - [x] `get_chunk_progress()` - aggregated status counts

- [x] Task 6: Write comprehensive tests (AC: #1-5)
  - [x] Create `backend/tests/services/test_ocr_chunk_service.py`
  - [x] Test create_chunk with valid data
  - [x] Test create_chunk handles unique constraint violation gracefully
  - [x] Test update_status sets correct timestamps
  - [x] Test update_status validates transitions
  - [x] Test get_chunks_by_document ordering
  - [x] Test heartbeat detection with mocked timestamps
  - [x] Test batch operations
  - [x] Test get_chunk_progress aggregation

## Dev Notes

### Architecture Compliance

**Service Pattern (MANDATORY - Follow JobTrackingService exactly):**
```python
# backend/app/services/ocr_chunk_service.py
import asyncio
from functools import lru_cache

import structlog
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)

class OCRChunkService:
    """Service for managing OCR chunk records.

    All async methods use asyncio.to_thread() to run synchronous
    Supabase client calls without blocking the event loop.
    """

    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = get_supabase_client()
            if self._client is None:
                raise OCRChunkServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                )
        return self._client

@lru_cache(maxsize=1)
def get_ocr_chunk_service() -> OCRChunkService:
    return OCRChunkService()
```

**Exception Pattern (MANDATORY):**
```python
class OCRChunkServiceError(Exception):
    """Base exception for OCR chunk service operations."""
    def __init__(self, message: str, code: str = "OCR_CHUNK_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)

class ChunkNotFoundError(OCRChunkServiceError):
    def __init__(self, chunk_id: str):
        super().__init__(f"Chunk {chunk_id} not found", code="CHUNK_NOT_FOUND")

class InvalidStatusTransitionError(OCRChunkServiceError):
    def __init__(self, current: str, target: str):
        super().__init__(
            f"Invalid status transition from {current} to {target}",
            code="INVALID_STATUS_TRANSITION"
        )
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    models/
      ocr_chunk.py           # NEW - Pydantic models
    services/
      ocr_chunk_service.py   # NEW - Service implementation
  tests/
    services/
      test_ocr_chunk_service.py  # NEW - Tests
```

**Related Files to Reference:**
- [JobTrackingService](../../backend/app/services/job_tracking/tracker.py) - Pattern to follow for async operations
- [OCR models](../../backend/app/models/ocr.py) - Existing OCR-related models
- [document_ocr_chunks migration](../../supabase/migrations/20260117100001_create_document_ocr_chunks_table.sql) - DB schema reference

### Technical Requirements

**Python 3.12+ Type Hints (MANDATORY):**
```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class ChunkStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentOCRChunk(BaseModel):
    """OCR chunk record from database."""
    id: str = Field(..., alias="id")
    matter_id: str = Field(..., alias="matterId")
    document_id: str = Field(..., alias="documentId")
    chunk_index: int = Field(..., ge=0, alias="chunkIndex")
    page_start: int = Field(..., ge=1, alias="pageStart")
    page_end: int = Field(..., ge=1, alias="pageEnd")
    status: ChunkStatus
    error_message: str | None = Field(None, alias="errorMessage")
    result_storage_path: str | None = Field(None, alias="resultStoragePath")
    result_checksum: str | None = Field(None, alias="resultChecksum")
    processing_started_at: datetime | None = Field(None, alias="processingStartedAt")
    processing_completed_at: datetime | None = Field(None, alias="processingCompletedAt")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = {"populate_by_name": True}
```

**Heartbeat Detection Logic:**
```python
from datetime import UTC, datetime, timedelta

STALE_CHUNK_THRESHOLD_SECONDS = 90

async def detect_stale_chunks(self) -> list[DocumentOCRChunk]:
    """Find chunks stuck in 'processing' for >90 seconds."""
    threshold = datetime.now(UTC) - timedelta(seconds=STALE_CHUNK_THRESHOLD_SECONDS)

    def _query():
        return (
            self.client.table("document_ocr_chunks")
            .select("*")
            .eq("status", ChunkStatus.PROCESSING.value)
            .lt("processing_started_at", threshold.isoformat())
            .execute()
        )

    response = await asyncio.to_thread(_query)
    return [self._db_row_to_chunk(row) for row in (response.data or [])]
```

**Status Transition Validation:**
```python
VALID_STATUS_TRANSITIONS = {
    ChunkStatus.PENDING: {ChunkStatus.PROCESSING},
    ChunkStatus.PROCESSING: {ChunkStatus.COMPLETED, ChunkStatus.FAILED},
    ChunkStatus.FAILED: {ChunkStatus.PENDING},  # Retry resets to pending
    ChunkStatus.COMPLETED: set(),  # Terminal state
}

def _validate_status_transition(self, current: ChunkStatus, target: ChunkStatus) -> None:
    if target not in VALID_STATUS_TRANSITIONS.get(current, set()):
        raise InvalidStatusTransitionError(current.value, target.value)
```

### Testing Requirements

**Backend Testing (pytest):**
```python
# tests/services/test_ocr_chunk_service.py
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, UTC

from app.models.ocr_chunk import ChunkStatus, DocumentOCRChunk
from app.services.ocr_chunk_service import OCRChunkService, get_ocr_chunk_service

@pytest.fixture
def mock_supabase():
    with patch("app.services.ocr_chunk_service.get_supabase_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client

@pytest.fixture
def service(mock_supabase):
    return OCRChunkService()

class TestCreateChunk:
    @pytest.mark.asyncio
    async def test_create_chunk_success(self, service, mock_supabase):
        # Arrange
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            "id": "chunk-123",
            "matter_id": "matter-456",
            "document_id": "doc-789",
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 25,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }]

        # Act
        result = await service.create_chunk(
            document_id="doc-789",
            matter_id="matter-456",
            chunk_index=0,
            page_start=1,
            page_end=25,
        )

        # Assert
        assert result.status == ChunkStatus.PENDING
        assert result.chunk_index == 0

class TestHeartbeatDetection:
    @pytest.mark.asyncio
    async def test_detect_stale_chunks(self, service, mock_supabase):
        # Arrange - chunk started 120 seconds ago (stale)
        stale_time = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value.data = [{
            "id": "stale-chunk",
            "status": "processing",
            "processing_started_at": stale_time,
            # ... other fields
        }]

        # Act
        stale = await service.detect_stale_chunks()

        # Assert
        assert len(stale) == 1
        assert stale[0].id == "stale-chunk"
```

### References

- [Source: architecture.md#Service Patterns] - Async service pattern with asyncio.to_thread()
- [Source: project-context.md#Backend] - Python 3.12+ type hints, Pydantic v2
- [Source: epic-1-infrastructure-chunk-state-management.md#Story 1.2] - Full acceptance criteria
- [Source: 20260117100001_create_document_ocr_chunks_table.sql] - DB schema and constraints
- [Source: 15-1-document-ocr-chunks-table.md] - Previous story context

### Previous Story Intelligence

**From Story 15.1 (Document OCR Chunks Table):**
- DB table is `document_ocr_chunks` with snake_case columns
- Status enum: 'pending', 'processing', 'completed', 'failed'
- chunk_index is 0-indexed (CHECK constraint enforces >= 0)
- page_start and page_end are 1-indexed (CHECK constraint enforces >= 1)
- UNIQUE constraint on (document_id, chunk_index) prevents duplicates
- RLS policies follow 4-layer matter isolation pattern
- Storage bucket `ocr-chunks` created for result caching

**From Epic 2B (OCR Pipeline) and JobTrackingService:**
- Use `asyncio.to_thread()` for sync Supabase calls
- Include structlog logging for all operations
- Heartbeat pattern already exists in JobTrackingService - follow same pattern
- Error handling follows `{Service}Error` base class pattern

### Git Intelligence Summary

**Recent Commit Patterns:**
- `fix(db):` prefix for database-related fixes
- `feat(db):` prefix for new database features
- Pydantic models use `Field(alias=...)` for camelCase frontend compatibility
- `model_config = {"populate_by_name": True}` enables both snake_case and camelCase

**Code Review Patterns to Follow:**
- No unused imports
- All destructured values must be consumed
- Use `| None` syntax instead of `Optional[]`
- Include docstrings for public methods

### Critical Implementation Notes

**DO NOT:**
- Use `Optional[]` - use `| None` instead (Python 3.12+)
- Call Supabase client directly from async methods - wrap in `asyncio.to_thread()`
- Skip validation of status transitions
- Forget camelCase aliases for frontend compatibility

**MUST:**
- Follow JobTrackingService pattern exactly
- Include comprehensive structlog logging
- Handle unique constraint violations gracefully (return error, don't crash)
- Validate page_start <= page_end in service layer as defense-in-depth
- Use `datetime.now(UTC)` not `datetime.utcnow()` (deprecated)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - all tests passing.

### Completion Notes List

- Implemented OCRChunkService following JobTrackingService pattern exactly
- Created Pydantic models with camelCase aliases for frontend compatibility
- All 56 tests passing (create_chunk, update_status, update_result, heartbeat detection, batch operations)
- Status transition validation enforces valid state machine transitions
- Heartbeat detection uses 90-second threshold for stale worker identification
- Defense-in-depth validation for page_start <= page_end
- Comprehensive exception handling with typed errors (ChunkNotFoundError, DuplicateChunkError, etc.)
- Lint-clean code with ruff

**Code Review Fixes Applied (2026-01-17):**
- Added `update_result()` method for setting result_storage_path and result_checksum after OCR completes
- Added `get_processing_chunks()` method for monitoring active work
- Fixed missing return type on `client` property
- Fixed misleading docstring claim about matter_id validation (now accurately states RLS reliance)
- Added `_parse_timestamp_required()` for type-safe parsing of required timestamp fields
- Added warning logging for timestamp parse failures
- Clarified docstrings for unused Pydantic models (reserved for API routes)

### File List

- backend/app/models/ocr_chunk.py (NEW)
- backend/app/services/ocr_chunk_service.py (NEW)
- backend/tests/services/test_ocr_chunk_service.py (NEW)

### Change Log

- 2026-01-17: Story 15.2 implementation complete - OCRChunkService with CRUD, heartbeat detection, and batch operations
- 2026-01-17: Code review fixes applied - added update_result(), get_processing_chunks(), improved type safety

