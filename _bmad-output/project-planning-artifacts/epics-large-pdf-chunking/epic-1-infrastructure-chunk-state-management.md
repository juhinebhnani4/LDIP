# Epic 1: Infrastructure & Chunk State Management

## Story 1.1: Create Document OCR Chunks Database Table

**As a** system administrator,
**I want** a database table to track OCR chunk processing state,
**So that** the system can manage large document processing with granular status tracking.

**Acceptance Criteria:**

**Given** the database migration is applied
**When** a new document_ocr_chunks record is created
**Then** it stores document_id, matter_id, chunk_index, page_start, page_end, and status
**And** the status defaults to 'pending'
**And** RLS policies enforce matter isolation matching existing patterns
**And** indexes exist on (document_id) and (document_id, status)
**And** UNIQUE constraint exists on (document_id, chunk_index)
**And** CHECK constraints ensure page_start <= page_end and page_start >= 1

**[DEBATE CLUB - Caching Architecture]:**
**And** includes `result_storage_path` column (TEXT, nullable) for Supabase Storage path
**And** includes `result_checksum` column (TEXT, nullable) for SHA256 validation of stored results

**[INFRASTRUCTURE - Supabase Storage Bucket]:**
**And** Supabase Storage bucket `ocr-chunks` is created
**And** bucket RLS policies allow authenticated users to read/write within their matter scope
**And** bucket path structure: `ocr-chunks/{matter_id}/{document_id}/{chunk_index}.json`

---

## Story 1.2: Implement OCR Chunk Service

**As a** backend developer,
**I want** a service to manage OCR chunk records,
**So that** I can create, update, and query chunk processing state.

**Acceptance Criteria:**

**Given** a document_id, matter_id, and chunk details
**When** I call `create_chunk(document_id, matter_id, chunk_index, page_start, page_end)`
**Then** a new chunk record is created with status 'pending'
**And** the chunk_index is unique per document

**Given** a chunk record exists
**When** I call `update_status(chunk_id, status, error_message=None)`
**Then** the status is updated and processing timestamps are set appropriately
**And** processing_started_at is set when status changes to 'processing'
**And** processing_completed_at is set when status changes to 'completed' or 'failed'

**Given** a document_id
**When** I call `get_chunks_by_document(document_id)`
**Then** all chunks for that document are returned ordered by chunk_index

**Given** a document_id with some failed chunks
**When** I call `get_failed_chunks(document_id)`
**Then** only chunks with status 'failed' are returned

**[CHAOS MONKEY - Heartbeat Detection]:**
**Given** a chunk has been in 'processing' status for >90 seconds without heartbeat
**When** the stale chunk detector runs
**Then** the chunk is marked as 'failed' with "worker_timeout" error
**And** it becomes eligible for retry

---

## Story 1.3: Integrate Chunk Progress with Job Tracking

**As a** user uploading a large document,
**I want** to see progress updates during chunk processing,
**So that** I know the system is working and can estimate completion time.

**Acceptance Criteria:**

**Given** a large document is being processed in chunks
**When** a chunk completes processing
**Then** the JobTrackingService is updated with chunk progress (e.g., "Processing chunk 5/17")
**And** the overall percentage is calculated based on completed chunks

**Given** all chunks complete successfully
**When** the merge operation begins
**Then** the job status shows "Merging OCR results"

**Given** a chunk fails
**When** the failure is recorded
**Then** the job status shows the error with chunk details (chunk_index, page_range)

---

## Story 1.4: Implement Chunk Cleanup Mechanism

**As a** system,
**I want** to clean up temporary chunk data after successful processing,
**So that** database resources are not wasted on completed work.

**Acceptance Criteria:**

**Given** a document has completed OCR processing successfully (status = 'ocr_complete')
**When** the cleanup is triggered after merge
**Then** all chunk records for that document are deleted

**Given** a document has failed chunks
**When** cleanup is attempted
**Then** chunk records are preserved for debugging and retry

**Given** chunk records older than 7 days with document status 'completed' or 'failed'
**When** the scheduled cleanup job runs
**Then** those records are automatically deleted

**[PRE-MORTEM - Orphan Cleanup]:**
**Given** Supabase Storage contains chunk result files
**When** cleanup deletes chunk records
**Then** corresponding storage files are also deleted
**And** orphan detection runs to find storage files without matching records

**[SHARK TANK - Configurable Retention]:**
**Given** retention policy is configurable
**When** admin sets retention to N days
**Then** cleanup respects the configured retention period
**And** default remains 7 days if not configured

---
