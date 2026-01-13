# Story 2C.3: Implement Background Job Status Tracking and Retry

Status: complete

## Story

As an **attorney**,
I want **to see the status of document processing jobs and retry failed ones**,
So that **I know if something went wrong and can recover without losing work**.

## Acceptance Criteria

1. **Given** a document processing job is running **When** I view the matter or dashboard **Then** I see the current job status (queued, processing, stage X of Y, completed, failed) **And** I see estimated time remaining for large jobs

2. **Given** a processing job fails at any stage (OCR, chunking, entity extraction, etc.) **When** the failure occurs **Then** the job is automatically retried up to 3 times with exponential backoff **And** partial progress is preserved (completed pages are not reprocessed) **And** the failure reason is logged

3. **Given** a job has failed after all retry attempts **When** I view the Documents tab **Then** the document shows "Processing Failed" status with error details **And** I see a "Retry" button to manually trigger reprocessing **And** I see a "Skip" option to proceed without this document

4. **Given** I am an admin or matter owner **When** I view processing status **Then** I can see all jobs in the queue for my matters **And** I can prioritize or cancel pending jobs

5. **Given** documents are still processing (OCR, chunking, or entity extraction in progress) **When** I click "Enter Workspace" on the matter **Then** I can access the workspace with partially available data **And** tabs show what's ready vs. still processing (e.g., "Timeline (12 events)" vs. "Citations (processing...)") **And** a banner indicates "Analysis in progress - some features updating" **And** data updates in real-time as processing completes

## Tasks / Subtasks

- [x] Task 1: Create Database Schema for Job Tracking (AC: #1, #2)
  - [x] Create Supabase migration for `processing_jobs` table
    - Columns: `id` (UUID PK), `matter_id` (FK), `document_id` (FK nullable), `job_type` (enum), `status` (enum), `celery_task_id` (text), `current_stage` (text), `total_stages` (int), `completed_stages` (int), `progress_pct` (int 0-100), `estimated_completion` (timestamptz), `error_message` (text), `error_code` (text), `retry_count` (int default 0), `max_retries` (int default 3), `metadata` (JSONB), `started_at` (timestamptz), `completed_at` (timestamptz), `created_at`, `updated_at`
    - Add index on `(matter_id, status)` for dashboard queries
    - Add index on `(document_id, status)` for document-specific queries
    - Add index on `celery_task_id` for task correlation
  - [x] Create Supabase migration for `job_stage_history` table
    - Columns: `id` (UUID PK), `job_id` (FK), `stage_name` (text), `status` (enum), `started_at`, `completed_at`, `error_message`, `metadata` (JSONB)
    - Track granular stage progress for partial recovery
  - [x] Implement RLS policies for both tables (matter isolation)

- [x] Task 2: Create Job Status Pydantic Models (AC: #1, #2, #3)
  - [x] Create `backend/app/models/job.py`
    - Define `JobType` enum: DOCUMENT_PROCESSING, OCR, VALIDATION, CHUNKING, EMBEDDING, ENTITY_EXTRACTION, ALIAS_RESOLUTION
    - Define `JobStatus` enum: QUEUED, PROCESSING, COMPLETED, FAILED, CANCELLED, PAUSED
    - Define `StageStatus` enum: PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
    - Define `ProcessingJob` Pydantic model for API responses
    - Define `ProcessingJobCreate`, `ProcessingJobUpdate` models
    - Define `JobStageHistory` model for stage tracking
    - Define `JobQueueStats` model for dashboard summary
  - [x] Update `backend/app/models/__init__.py` with exports

- [x] Task 3: Create Job Tracking Service (AC: #1, #2)
  - [x] Create `backend/app/services/job_tracking/__init__.py`
  - [x] Create `backend/app/services/job_tracking/tracker.py`
    - Implement `JobTrackingService` class
    - Method: `create_job(matter_id, document_id, job_type) -> ProcessingJob`
    - Method: `update_job_status(job_id, status, stage, progress_pct, error) -> ProcessingJob`
    - Method: `record_stage_start(job_id, stage_name) -> JobStageHistory`
    - Method: `record_stage_complete(job_id, stage_name) -> JobStageHistory`
    - Method: `record_stage_failure(job_id, stage_name, error) -> JobStageHistory`
    - Method: `get_job(job_id) -> ProcessingJob | None`
    - Method: `get_jobs_by_matter(matter_id, status) -> list[ProcessingJob]`
    - Method: `get_jobs_by_document(document_id) -> list[ProcessingJob]`
    - Method: `calculate_estimated_completion(job_id) -> datetime | None`
    - Use RLS-enforced Supabase client

- [x] Task 4: Create Estimated Time Calculation Service (AC: #1)
  - [x] Create `backend/app/services/job_tracking/time_estimator.py`
    - Implement `TimeEstimator` class
    - Method: `estimate_ocr_time(page_count: int) -> timedelta`
    - Method: `estimate_chunking_time(text_length: int) -> timedelta`
    - Method: `estimate_embedding_time(chunk_count: int) -> timedelta`
    - Method: `estimate_entity_extraction_time(chunk_count: int) -> timedelta`
    - Method: `estimate_total_time(document_id) -> timedelta`
    - Base estimates on historical data or reasonable defaults
    - Consider queue position for more accurate estimates

- [x] Task 5: Integrate Job Tracking into Document Processing Pipeline (AC: #1, #2)
  - [x] Update `backend/app/workers/tasks/document_tasks.py`
    - Modify each task to create/update job tracking records
    - Add stage start/complete recording for granular progress
    - Update estimated completion time after each stage
    - Record partial progress for recovery (track completed pages/chunks)
  - [x] Create job tracking wrapper for Celery tasks
    - Automatically record task start/complete/failure
    - Link Celery task ID to job record

- [x] Task 6: Implement Partial Progress Preservation (AC: #2)
  - [x] Create `backend/app/services/job_tracking/partial_progress.py`
    - `StageProgress` dataclass for tracking per-stage progress
    - `PartialProgressTracker` class for managing progress across stages
    - Persists progress to job metadata for durability
  - [x] Update embedding task to skip already-embedded chunks
    - Tracks processed chunk IDs in job metadata
    - On retry, skips chunks marked as processed
    - Saves progress periodically (every 10 items) and on failure
  - [x] Update entity extraction to skip processed chunks
    - Same pattern as embedding task
    - Track `chunks_processed` and `skipped_chunks` in results
  - [x] Create unit tests for partial progress module
    - `backend/tests/services/job_tracking/test_partial_progress.py`

- [x] Task 7: Create Manual Retry and Skip API Endpoints (AC: #3, #4)
  - [x] Create `backend/app/api/routes/jobs.py`
    - `GET /api/matters/{matter_id}/jobs` - List all jobs for matter
      - Query params: `status`, `job_type`, `page`, `per_page`
      - Response: paginated job list with progress details
    - `GET /api/matters/{matter_id}/jobs/{job_id}` - Get single job details
      - Include: stage history, error details, retry count
    - `POST /api/matters/{matter_id}/jobs/{job_id}/retry` - Manually retry failed job
      - Resets retry count and requeues for processing
      - Only allowed for failed jobs
    - `POST /api/matters/{matter_id}/jobs/{job_id}/cancel` - Cancel pending/processing job
      - Revokes Celery task if possible
      - Marks job as CANCELLED
    - `POST /api/matters/{matter_id}/jobs/{job_id}/skip` - Skip failed job
      - Marks job as SKIPPED without retrying
      - Updates document status to indicate incomplete processing
    - `GET /api/matters/{matter_id}/jobs/stats` - Get queue statistics
      - Returns counts by status, average processing times
  - [x] Register routes in `backend/app/main.py`
  - [x] Add auth dependency (matter access validation)

- [x] Task 8: Create Real-Time Status Broadcasting (AC: #1, #5)
  - [x] Update `backend/app/services/pubsub_service.py`
    - Add `broadcast_job_progress(matter_id, job_id, progress)` function
    - Add `broadcast_job_status_change(matter_id, job_id, old_status, new_status)` function
    - Add `broadcast_processing_summary(matter_id, stats)` function
  - [x] Create job progress channel: `processing:{matter_id}`
    - Sends: job_id, stage, progress_pct, estimated_completion

- [x] Task 9: Create Frontend Types and API Client (AC: #1, #3, #4)
  - [x] Create `frontend/src/types/job.ts`
    - Define `JobType`, `JobStatus`, `StageStatus` enums
    - Define `ProcessingJob` interface with all fields
    - Define `JobStageHistory` interface
    - Define `JobQueueStats` interface
    - Define `JobsResponse` paginated response type
  - [x] Create `frontend/src/lib/api/jobs.ts`
    - `getJobs(matterId, options): Promise<JobsResponse>`
    - `getJob(matterId, jobId): Promise<ProcessingJob>`
    - `retryJob(matterId, jobId): Promise<ProcessingJob>`
    - `cancelJob(matterId, jobId): Promise<ProcessingJob>`
    - `skipJob(matterId, jobId): Promise<ProcessingJob>`
    - `getJobStats(matterId): Promise<JobQueueStats>`

- [x] Task 10: Create Processing Status Zustand Store (AC: #1, #5)
  - [x] Create `frontend/src/stores/processingStore.ts`
    - State: `jobs`, `jobsByDocument`, `matterStats`, `isLoading`
    - Actions: `setJobs`, `updateJob`, `setMatterStats`
    - Selectors for: active jobs, failed jobs, matter processing state
  - [x] Implement real-time updates via Supabase Realtime
    - Subscribe to `processing:{matter_id}` channel
    - Update store on job progress events

- [x] Task 11: Create Processing Status UI Components (AC: #1, #3, #5)
  - [x] Create `frontend/src/components/features/processing/ProcessingStatusBanner.tsx`
    - Shows banner when documents are processing
    - Displays: "Processing X documents - Y% complete"
    - Click to expand for details
  - [x] Create `frontend/src/components/features/processing/JobProgressCard.tsx`
    - Shows individual job progress
    - Visual progress bar with stage indicators
    - Estimated time remaining
  - [x] Create `frontend/src/components/features/processing/FailedJobCard.tsx`
    - Shows failed job with error message
    - "Retry" and "Skip" buttons
    - Retry count indicator
  - [x] Create `frontend/src/components/features/processing/ProcessingQueue.tsx`
    - List of all jobs for matter
    - Filter by status
    - Bulk actions (retry all failed, cancel all pending)

- [x] Task 12: Update Document List with Processing Status (AC: #3, #5)
  - [x] Update `frontend/src/components/features/document/DocumentList.tsx`
    - Add processing status indicator for each document
    - Show stage icons: OCR ✓, Chunking ⏳, etc.
    - Add "Processing Failed" badge with retry/skip actions
  - [x] Create `frontend/src/components/features/document/DocumentProcessingStatus.tsx`
    - Mini progress indicator for inline use
    - Expandable to show current stage details

- [x] Task 13: Update Matter Workspace for Partial Data (AC: #5)
  - [x] Update workspace layout to show processing banner
    - Created `MatterWorkspaceWrapper` client component
    - Integrated `ProcessingStatusBanner` in matter layout
  - [ ] Update tab headers to show partial data status (deferred to Story 10A.2 - AC added there)
    - E.g., "Timeline (12 events - 3 docs processing)"
    - E.g., "Entities (45 found - processing...)"
  - [ ] Add loading placeholders for tabs still receiving data (deferred to Story 10A.2 - AC added there)
  - [x] Implement real-time data refresh as processing completes
    - Store supports real-time event handlers (handleProgressEvent, handleStatusChangeEvent)
    - Supabase Realtime subscription implemented in MatterWorkspaceWrapper

- [x] Task 14: Write Backend Unit Tests
  - [x] Create `backend/tests/services/job_tracking/test_tracker.py`
    - Test job creation and status updates
    - Test stage recording
    - Test partial progress tracking
    - Test matter isolation
  - [x] Create `backend/tests/services/job_tracking/test_time_estimator.py`
    - Test time estimation calculations
    - Test queue position consideration
  - [x] Create `backend/tests/api/routes/test_jobs.py`
    - Test list jobs endpoint
    - Test retry endpoint
    - Test cancel endpoint
    - Test skip endpoint
    - Test authorization

- [x] Task 15: Write Integration Tests
  - [x] Create `backend/tests/integration/test_job_tracking_integration.py`
    - Test full job lifecycle: create -> process -> complete
    - Test failure and retry flow
    - Test partial progress preservation
    - Test matter isolation
    - Test real-time status updates

## Dev Notes

### CRITICAL: Existing Infrastructure to Use

**From Story 2c-1 & 2c-2 (MIG):**
- Document processing pipeline in `backend/app/workers/tasks/document_tasks.py`
- Pipeline chain: OCR -> Validation -> Confidence -> Chunking -> Embedding -> Entity Extraction -> Alias Resolution
- Celery task pattern with retry logic already implemented
- `broadcast_document_status` function in `backend/app/services/pubsub_service.py`

**From Architecture (Background Jobs):**
- Celery + Redis (Upstash) for job queue
- Priority queues: `high` (small matters), `default`, `low` (batch ops)
- Progress reporting via Redis pub/sub and Supabase Realtime

### Architecture Requirements (MANDATORY)

**From [architecture.md](../_bmad-output/architecture.md):**

#### Background Jobs Design
From architecture:
```
**Queue Configuration:**
| Queue | Priority | Use Case |
|-------|----------|----------|
| `high` | 1 | Small matters (<100 pages), user-initiated queries |
| `default` | 5 | Standard document processing |
| `low` | 10 | Batch operations, pre-computation |

**Progress Reporting:**
- Redis pub/sub for real-time status
- `processing_status` table for persistent state
- Supabase Realtime broadcasts to connected clients
```

#### 4-Layer Matter Isolation (MUST IMPLEMENT)
```
Layer 1: RLS policies on processing_jobs, job_stage_history
Layer 2: N/A (no vectors in job tracking)
Layer 3: Redis key prefix `matter:{id}:jobs:` for pub/sub
Layer 4: API middleware validates matter access
```

### Processing Pipeline Stages

**Current Pipeline (from document_tasks.py):**
```
Stage 1: process_document (OCR)
   └── Downloads PDF, processes with Document AI, saves bounding boxes
Stage 2: validate_ocr
   └── Pattern corrections + Gemini validation
Stage 3: calculate_confidence
   └── Updates confidence metrics
Stage 4: chunk_document
   └── Creates parent-child chunks
Stage 5: embed_chunks
   └── Generates embeddings with OpenAI
Stage 6: extract_entities
   └── MIG entity extraction with Gemini
Stage 7: resolve_aliases
   └── Links entity name variants
```

**Job Status State Machine:**
```
QUEUED ─────┬────────────────> PROCESSING ──┬──> COMPLETED
            │                              │
            └─> CANCELLED                  └──> FAILED ──┬──> QUEUED (retry)
                                                         └──> SKIPPED
```

### Previous Story Intelligence

**FROM Story 2c-2 (Alias Resolution):**
- Celery task chaining pattern
- Async-to-sync wrapper pattern for async operations in Celery
- `broadcast_document_status` usage pattern
- structlog logging patterns

**Key files to reference:**
- [backend/app/workers/tasks/document_tasks.py](backend/app/workers/tasks/document_tasks.py) - Pipeline tasks
- [backend/app/services/pubsub_service.py](backend/app/services/pubsub_service.py) - Broadcasting
- [backend/app/models/document.py](backend/app/models/document.py) - DocumentStatus enum pattern

### Git Intelligence

Recent commits:
```
7685652 feat(mig): implement alias resolution for entity name variants (Story 2c-2)
f48a00e fix(mig): address code review issues for Story 2c-1
71b4fa9 feat(mig): implement entity extraction and MIG storage (Story 2c-1)
```

**Recommended commit message:** `feat(jobs): implement background job status tracking and retry (Story 2c-3)`

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Backend Technology Stack
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **structlog** for logging - NOT standard logging library
- **Celery** with Redis broker - use priority queues

#### API Response Format (MANDATORY)
```python
# Success - job list
{
  "data": [
    {
      "id": "uuid",
      "matter_id": "uuid",
      "document_id": "uuid",
      "job_type": "DOCUMENT_PROCESSING",
      "status": "PROCESSING",
      "current_stage": "embedding",
      "progress_pct": 65,
      "estimated_completion": "2026-01-12T15:30:00Z",
      "retry_count": 0
    }
  ],
  "meta": {
    "total": 5,
    "page": 1,
    "per_page": 20
  }
}

# Success - job stats
{
  "data": {
    "queued": 3,
    "processing": 2,
    "completed": 45,
    "failed": 1,
    "avg_processing_time_ms": 125000
  }
}

# Error
{ "error": { "code": "JOB_NOT_FOUND", "message": "...", "details": {} } }
```

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| Database tables | snake_case | `processing_jobs`, `job_stage_history` |
| Database columns | snake_case | `job_type`, `progress_pct`, `estimated_completion` |
| TypeScript variables | camelCase | `progressPct`, `estimatedCompletion` |
| Python functions | snake_case | `create_job`, `update_progress` |
| Python classes | PascalCase | `JobTrackingService`, `TimeEstimator` |
| API endpoints | plural nouns | `/api/matters/{matter_id}/jobs` |

#### RLS Policy Template (MANDATORY)
```sql
CREATE POLICY "Users can only access jobs in their matters"
ON processing_jobs FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM matter_members
    WHERE user_id = auth.uid()
  )
);
```

### File Organization

```
backend/app/
├── services/
│   └── job_tracking/
│       ├── __init__.py                     (NEW) - Module exports
│       ├── tracker.py                      (NEW) - Job tracking service
│       └── time_estimator.py               (NEW) - Time estimation
├── api/
│   └── routes/
│       ├── __init__.py                     (UPDATE - add jobs router)
│       └── jobs.py                         (NEW) - Job API endpoints
├── models/
│   ├── __init__.py                         (UPDATE - export job models)
│   └── job.py                              (NEW) - Job Pydantic models
├── workers/
│   └── tasks/
│       └── document_tasks.py               (UPDATE - add job tracking)

frontend/src/
├── types/
│   └── job.ts                              (NEW) - Job TypeScript types
├── lib/
│   └── api/
│       └── jobs.ts                         (NEW) - Job API client
├── stores/
│   └── processingStore.ts                  (NEW) - Processing state
└── components/
    └── features/
        ├── processing/
        │   ├── ProcessingStatusBanner.tsx  (NEW)
        │   ├── JobProgressCard.tsx         (NEW)
        │   ├── FailedJobCard.tsx           (NEW)
        │   └── ProcessingQueue.tsx         (NEW)
        └── document/
            └── DocumentProcessingStatus.tsx (NEW)

supabase/migrations/
├── xxx_create_processing_jobs.sql          (NEW)
└── xxx_create_job_stage_history.sql        (NEW)

backend/tests/
├── services/
│   └── job_tracking/
│       ├── test_tracker.py                 (NEW)
│       └── test_time_estimator.py          (NEW)
├── api/
│   └── test_jobs.py                        (NEW)
└── integration/
    └── test_job_tracking_integration.py    (NEW)
```

### Database Schema Design

```sql
-- processing_jobs table
CREATE TABLE processing_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  job_type TEXT NOT NULL CHECK (job_type IN (
    'DOCUMENT_PROCESSING', 'OCR', 'VALIDATION', 'CHUNKING',
    'EMBEDDING', 'ENTITY_EXTRACTION', 'ALIAS_RESOLUTION'
  )),
  status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN (
    'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED', 'PAUSED'
  )),
  celery_task_id TEXT,
  current_stage TEXT,
  total_stages INT DEFAULT 7,
  completed_stages INT DEFAULT 0,
  progress_pct INT DEFAULT 0 CHECK (progress_pct >= 0 AND progress_pct <= 100),
  estimated_completion TIMESTAMPTZ,
  error_message TEXT,
  error_code TEXT,
  retry_count INT DEFAULT 0,
  max_retries INT DEFAULT 3,
  metadata JSONB DEFAULT '{}',
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_processing_jobs_matter_status ON processing_jobs(matter_id, status);
CREATE INDEX idx_processing_jobs_document ON processing_jobs(document_id, status);
CREATE INDEX idx_processing_jobs_celery ON processing_jobs(celery_task_id);

-- job_stage_history table
CREATE TABLE job_stage_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
  stage_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN (
    'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'SKIPPED'
  )),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  error_message TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_job_stage_history_job ON job_stage_history(job_id, stage_name);
```

### Time Estimation Approach

**Base estimates (configurable via env vars):**
```python
ESTIMATE_OCR_MS_PER_PAGE = 3000  # 3 seconds per page
ESTIMATE_CHUNK_MS_PER_1K_CHARS = 100  # 0.1 seconds per 1K chars
ESTIMATE_EMBED_MS_PER_CHUNK = 200  # 0.2 seconds per chunk
ESTIMATE_ENTITY_MS_PER_CHUNK = 500  # 0.5 seconds per chunk
ESTIMATE_ALIAS_FIXED_MS = 5000  # 5 seconds for alias resolution

def estimate_total(page_count: int, chunk_count: int) -> timedelta:
    ocr_ms = page_count * ESTIMATE_OCR_MS_PER_PAGE
    chunk_ms = chunk_count * ESTIMATE_CHUNK_MS_PER_1K_CHARS
    embed_ms = chunk_count * ESTIMATE_EMBED_MS_PER_CHUNK
    entity_ms = chunk_count * ESTIMATE_ENTITY_MS_PER_CHUNK
    alias_ms = ESTIMATE_ALIAS_FIXED_MS

    total_ms = ocr_ms + chunk_ms + embed_ms + entity_ms + alias_ms
    return timedelta(milliseconds=total_ms)
```

### Partial Progress Preservation

**OCR partial progress:**
```python
# Store in job metadata
{
  "completed_pages": [1, 2, 3, 4, 5],
  "total_pages": 100,
  "last_completed_page": 5
}

# On retry, skip completed pages
def process_document_with_recovery(document_id: str):
    job = get_job_for_document(document_id)
    completed_pages = job.metadata.get("completed_pages", [])

    for page_num in range(1, total_pages + 1):
        if page_num in completed_pages:
            continue  # Skip already processed
        process_page(page_num)
        update_job_metadata(job.id, {"completed_pages": completed_pages + [page_num]})
```

### Testing Guidance

#### Unit Tests - Job Tracking

```python
# backend/tests/services/job_tracking/test_tracker.py

import pytest
from datetime import datetime, timedelta
from app.services.job_tracking.tracker import JobTrackingService
from app.models.job import JobType, JobStatus, StageStatus


@pytest.fixture
def tracker():
    return JobTrackingService()


class TestJobCreation:
    """Test job creation and status updates."""

    @pytest.mark.asyncio
    async def test_create_job(self, tracker, test_matter):
        job = await tracker.create_job(
            matter_id=test_matter.id,
            document_id=None,
            job_type=JobType.DOCUMENT_PROCESSING,
        )

        assert job.id is not None
        assert job.status == JobStatus.QUEUED
        assert job.progress_pct == 0

    @pytest.mark.asyncio
    async def test_update_job_progress(self, tracker, test_job):
        updated = await tracker.update_job_status(
            job_id=test_job.id,
            status=JobStatus.PROCESSING,
            stage="chunking",
            progress_pct=45,
        )

        assert updated.status == JobStatus.PROCESSING
        assert updated.current_stage == "chunking"
        assert updated.progress_pct == 45


class TestStageTracking:
    """Test granular stage tracking."""

    @pytest.mark.asyncio
    async def test_record_stage_complete(self, tracker, test_job):
        await tracker.record_stage_start(test_job.id, "ocr")
        await tracker.record_stage_complete(test_job.id, "ocr")

        history = await tracker.get_stage_history(test_job.id)
        ocr_stage = next(s for s in history if s.stage_name == "ocr")

        assert ocr_stage.status == StageStatus.COMPLETED
        assert ocr_stage.completed_at is not None

    @pytest.mark.asyncio
    async def test_record_stage_failure(self, tracker, test_job):
        await tracker.record_stage_start(test_job.id, "embedding")
        await tracker.record_stage_failure(
            test_job.id, "embedding", "OpenAI rate limit exceeded"
        )

        history = await tracker.get_stage_history(test_job.id)
        embed_stage = next(s for s in history if s.stage_name == "embedding")

        assert embed_stage.status == StageStatus.FAILED
        assert "rate limit" in embed_stage.error_message.lower()
```

#### Integration Tests

```python
# backend/tests/integration/test_job_tracking_integration.py

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_job_lifecycle(
    client: AsyncClient,
    test_matter_with_document: Matter,
    auth_headers: dict,
):
    """Test job from creation through completion."""
    # Upload document triggers job creation
    # ... document upload code ...

    # Check job was created
    response = await client.get(
        f"/api/matters/{test_matter_with_document.id}/jobs",
        headers=auth_headers,
    )
    assert response.status_code == 200
    jobs = response.json()["data"]
    assert len(jobs) >= 1

    job = jobs[0]
    assert job["status"] in ["QUEUED", "PROCESSING"]


@pytest.mark.asyncio
async def test_retry_failed_job(
    client: AsyncClient,
    test_failed_job: ProcessingJob,
    auth_headers: dict,
):
    """Test manual retry of failed job."""
    response = await client.post(
        f"/api/matters/{test_failed_job.matter_id}/jobs/{test_failed_job.id}/retry",
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["status"] == "QUEUED"
    assert data["retry_count"] == test_failed_job.retry_count + 1


@pytest.mark.asyncio
async def test_matter_isolation_for_jobs(
    client: AsyncClient,
    test_matter_a: Matter,
    test_matter_b: Matter,
    user_a_headers: dict,
    user_b_headers: dict,
):
    """Test jobs from one matter cannot be accessed from another."""
    # Create job in matter A
    # ...

    # User B should NOT see matter A jobs
    response = await client.get(
        f"/api/matters/{test_matter_a.id}/jobs",
        headers=user_b_headers,
    )
    assert response.status_code == 403
```

### Anti-Patterns to AVOID

```python
# WRONG: Not tracking partial progress
def process_all_pages(document_id):
    for page in get_pages(document_id):
        process_page(page)  # On failure, all progress lost!

# CORRECT: Track progress for recovery
def process_all_pages(document_id, job_id):
    job = get_job(job_id)
    completed = job.metadata.get("completed_pages", [])

    for page in get_pages(document_id):
        if page.number in completed:
            continue  # Skip already done
        process_page(page)
        update_job_metadata(job_id, completed + [page.number])


# WRONG: Blocking UI while checking job status
const status = await fetchJobStatus();  // Blocks render
setStatus(status);

// CORRECT: Use real-time subscriptions
useEffect(() => {
  const channel = supabase.channel(`processing:${matterId}`)
    .on('broadcast', { event: 'job_progress' }, (payload) => {
      updateJobInStore(payload.job_id, payload);
    })
    .subscribe();

  return () => channel.unsubscribe();
}, [matterId]);


# WRONG: Not considering queue position for estimates
def estimate_completion(job_id):
    return now() + timedelta(seconds=estimated_processing_time)

# CORRECT: Account for queue position
def estimate_completion(job_id):
    queue_position = get_queue_position(job_id)
    queue_wait = queue_position * AVG_JOB_DURATION
    processing_time = estimate_processing_time(job_id)
    return now() + queue_wait + processing_time
```

### Performance Considerations

- **Batch job status updates:** Update multiple jobs in single DB call when processing batch
- **Efficient polling fallback:** If WebSocket disconnects, poll at 5-second intervals
- **Index optimization:** Composite indexes on (matter_id, status) for dashboard queries
- **Metadata size limits:** Cap job metadata at 1MB to prevent bloat
- **Stage history cleanup:** Archive stage history older than 30 days

### Dependencies to Add

```bash
# No new dependencies needed - uses existing Celery and Supabase infrastructure
```

### Environment Variables Required

```bash
# Optional - tune time estimates (defaults shown)
JOB_ESTIMATE_OCR_MS_PER_PAGE=3000
JOB_ESTIMATE_EMBED_MS_PER_CHUNK=200
JOB_ESTIMATE_ENTITY_MS_PER_CHUNK=500
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] Run: `supabase migration up` for processing_jobs and job_stage_history tables

#### Environment Variables
- [ ] Optionally tune time estimate variables in backend `.env`

#### Dashboard Configuration
- [ ] No dashboard changes required

#### Manual Tests
- [ ] Upload a document and verify job is created in processing_jobs table
- [ ] Verify job status updates as document progresses through pipeline
- [ ] Force a failure (e.g., invalid PDF) and verify retry behavior
- [ ] Test manual retry via API
- [ ] Test skip functionality for failed jobs
- [ ] Verify real-time status updates reach frontend
- [ ] Test partial progress - interrupt and retry, verify no duplicate work
- [ ] Test matter isolation - ensure jobs from other matters are inaccessible

### Downstream Dependencies

This story enables:
- **Epic 9 (Dashboard):** Processing status on matter cards
- **Epic 10A (Workspace Shell):** Processing banner in workspace
- **All future processing tasks:** Consistent job tracking pattern

### Project Structure Notes

- Job tracking is PostgreSQL-only (per ADR-001) - no separate job queue DB
- Uses existing Celery infrastructure with added tracking
- Real-time updates via Supabase Realtime (already used for document status)
- RLS enforces matter isolation at database level

### References

- [Source: architecture.md#Background-Jobs] - Celery + Redis design
- [Source: architecture.md#Progress-Reporting] - Real-time status updates
- [Source: project-context.md#Story-Completion] - Manual steps format
- [Source: epics.md#Story-2.12] - Story requirements
- [Source: 2c-1-mig-entity-extraction.md] - Pipeline integration pattern
- [Source: 2c-2-alias-resolution.md] - Celery task patterns

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

**Code Review Fixes (2026-01-13):**
1. Populated empty File List section in story
2. Added job_id propagation and stage tracking to calculate_confidence and chunk_document tasks
3. Created backend/tests/api/routes/test_jobs.py with unit tests for all job API endpoints
4. Implemented Supabase Realtime subscription in MatterWorkspaceWrapper
5. Removed redundant json imports from pubsub_service.py
6. Fixed datetime import placement (moved to module level)
7. Verified StageStatus enum matches database schema (PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED)

### File List

#### Backend - Models
- backend/app/models/job.py (NEW)
- backend/app/models/__init__.py (UPDATED)

#### Backend - Services
- backend/app/services/job_tracking/__init__.py (NEW)
- backend/app/services/job_tracking/tracker.py (NEW)
- backend/app/services/job_tracking/time_estimator.py (NEW)
- backend/app/services/job_tracking/partial_progress.py (NEW)
- backend/app/services/pubsub_service.py (UPDATED)

#### Backend - API
- backend/app/api/routes/jobs.py (NEW)
- backend/app/main.py (UPDATED)

#### Backend - Workers
- backend/app/workers/tasks/document_tasks.py (UPDATED)

#### Backend - Tests
- backend/tests/services/job_tracking/__init__.py (NEW)
- backend/tests/services/job_tracking/test_tracker.py (NEW)
- backend/tests/services/job_tracking/test_time_estimator.py (NEW)
- backend/tests/services/job_tracking/test_partial_progress.py (NEW)
- backend/tests/api/routes/test_jobs.py (NEW)
- backend/tests/integration/test_job_tracking_integration.py (NEW)

#### Frontend - Types
- frontend/src/types/job.ts (NEW)
- frontend/src/types/index.ts (UPDATED)

#### Frontend - API
- frontend/src/lib/api/jobs.ts (NEW)

#### Frontend - Stores
- frontend/src/stores/processingStore.ts (NEW)
- frontend/src/stores/index.ts (UPDATED)

#### Frontend - Components
- frontend/src/components/features/processing/index.ts (NEW)
- frontend/src/components/features/processing/ProcessingStatusBanner.tsx (NEW)
- frontend/src/components/features/processing/JobProgressCard.tsx (NEW)
- frontend/src/components/features/processing/FailedJobCard.tsx (NEW)
- frontend/src/components/features/processing/ProcessingQueue.tsx (NEW)
- frontend/src/components/features/document/DocumentProcessingStatus.tsx (NEW)
- frontend/src/components/features/matter/MatterWorkspaceWrapper.tsx (NEW)
- frontend/src/app/(matter)/[matterId]/layout.tsx (UPDATED)

#### Database
- supabase/migrations/20260114000001_create_processing_jobs_table.sql (NEW)

