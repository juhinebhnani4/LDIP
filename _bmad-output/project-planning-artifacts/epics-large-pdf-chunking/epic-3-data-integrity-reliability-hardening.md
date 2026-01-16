# Epic 3: Data Integrity & Reliability Hardening

## Story 3.1: Implement Memory-Safe Streaming PDF Split

**As a** system processing large PDFs,
**I want** to split PDFs using streaming/incremental page reading,
**So that** memory usage stays under 50MB regardless of PDF size.

**Acceptance Criteria:**

**Given** a 100MB PDF (500 pages)
**When** split_pdf is called
**Then** peak memory usage does not exceed 50MB
**And** chunks are written to temporary storage as they are created

**Given** a PDF is being split
**When** each page is processed
**Then** only the current page and output buffer are in memory
**And** previous pages are released after writing to chunk

**Given** an extremely large PDF (1000+ pages)
**When** split_pdf is called
**Then** the operation completes successfully without OOM
**And** temporary chunk files are used if needed

**[CHAOS MONKEY - Atomic Temp Files]:**
**Given** temporary chunk files are being written
**When** the write operation executes
**Then** use atomic write pattern (write to .tmp, then rename)
**And** incomplete files don't corrupt processing on crash
**And** cleanup removes .tmp files on failure

**[PRE-MORTEM - Memory Profiling]:**
**Given** split_pdf is called
**When** processing starts
**Then** memory usage is tracked per operation
**And** warning logged if approaching 75% of memory limit
**And** metrics emitted for monitoring memory consumption patterns

---

## Story 3.2: Implement Circuit Breaker for Document AI

**As a** system making Document AI API calls,
**I want** a circuit breaker to stop processing when the API is failing repeatedly,
**So that** we don't waste resources on doomed requests or hit rate limits harder.

**Acceptance Criteria:**

**Given** 3 consecutive chunk failures with API errors (429, 500, timeout)
**When** the circuit breaker trips
**Then** all remaining chunk tasks are cancelled
**And** the document is marked as 'ocr_failed' with circuit breaker reason
**And** job tracking shows "Processing stopped: API circuit breaker triggered"

**Given** the circuit breaker is open
**When** a new large document upload is attempted
**Then** it is queued for later processing (not immediately failed)
**And** the user sees "High API load - document queued for processing"

**Given** the circuit breaker has been open for 5 minutes
**When** the half-open state is entered
**Then** one test request is allowed through
**And** success closes the breaker, failure keeps it open

---

## Story 3.3: Implement Per-Chunk Timeout and Rate Limiting

**As a** system processing chunks in parallel,
**I want** per-chunk timeouts and rate limiting,
**So that** hung requests don't block processing and we stay within API quotas.

**Acceptance Criteria:**

**Given** a chunk processing task
**When** Document AI call exceeds 60 seconds
**Then** the task is cancelled with timeout error
**And** chunk status is updated to 'failed' with "timeout" error_message

**Given** parallel chunk processing is active
**When** more than 5 chunks are ready to process
**Then** a semaphore limits concurrent Document AI calls to 5
**And** additional chunks wait for a slot to become available

**Given** Document AI returns 429 (rate limited)
**When** the error is handled
**Then** exponential backoff is applied (2s, 4s, 8s, max 30s)
**And** the chunk is retried after backoff

**[PRE-MORTEM - Global Semaphore]:**
**Given** concurrent Document AI requests
**When** rate limiting is active
**Then** global semaphore limits total concurrent API calls across all workers
**And** semaphore is implemented in Redis for cross-worker coordination
**And** prevents scenario where 10 workers each send 5 requests = 50 concurrent

**[PREREQUISITE - Redis Availability]:**
**Given** Redis is required for global semaphore
**When** global semaphore is implemented
**Then** use existing Redis connection from Celery broker (already in infrastructure)
**And** semaphore key pattern: `docai_semaphore:{environment}`
**And** fallback to per-worker semaphore if Redis unavailable (degraded mode)

**[SHARK TANK - Rate Limit Transparency]:**
**Given** rate limiting is being applied
**When** backoff delays processing
**Then** current backoff state is visible in job tracking
**And** estimated delay is shown to user
**And** metrics track rate limit events for capacity planning

---

## Story 3.4: Implement Idempotent Chunk Processing

**As a** system handling retries and reprocessing,
**I want** idempotent chunk processing that deletes before inserting,
**So that** re-running a chunk doesn't create duplicate bounding boxes.

**Acceptance Criteria:**

**Given** a document is being reprocessed (e.g., after partial failure)
**When** bounding boxes are about to be saved
**Then** all existing bounding boxes for that document are deleted first
**And** new bounding boxes are inserted in a single transaction

**Given** the delete-insert transaction fails midway
**When** the transaction rolls back
**Then** the original bounding boxes are preserved (no partial state)

**Given** a document with existing bounding boxes from a previous successful run
**When** reprocessing is triggered
**Then** all old bboxes are removed before new ones are inserted
**And** downstream references (chunks.bbox_ids) are invalidated (handled by CASCADE or subsequent reprocessing)

---

## Story 3.5: Implement Batch Bounding Box Inserts

**As a** system saving large numbers of bounding boxes,
**I want** to batch inserts in groups of 500,
**So that** database transactions don't timeout on large documents.

**Acceptance Criteria:**

**Given** a document with 8,500 bounding boxes to insert
**When** save_bounding_boxes is called
**Then** inserts are batched into groups of 500
**And** each batch is a separate transaction
**And** progress is logged after each batch

**Given** batch 5/17 fails during insert
**When** the error is handled
**Then** batches 1-4 are committed (partial progress saved)
**And** the failure is reported with batch number
**And** retry can resume from batch 5

**Given** all batches complete successfully
**When** the final count is verified
**Then** the total inserted matches the expected count
**And** document status is updated only after all batches succeed

**[CHAOS MONKEY - Explicit Transactions]:**
**Given** batch insert is executing
**When** each batch transaction runs
**Then** explicit BEGIN/COMMIT wraps each batch
**And** isolation level is READ COMMITTED to prevent phantom reads
**And** connection pooler properly handles transaction boundaries

**[CHAOS MONKEY - DB Timestamp Validation]:**
**Given** batches are being inserted
**When** inserts complete
**Then** verify timestamps are set correctly by database
**And** created_at reflects actual insert time (not stale value)
**And** log warning if timestamps are inconsistent

---

## Story 3.6: Implement Page Offset Validation

**As a** system ensuring data integrity,
**I want** validation that all page numbers are absolute (not chunk-relative),
**So that** citation highlighting and navigation work correctly on large documents.

**Acceptance Criteria:**

**Given** merged OCR results
**When** validation runs before saving
**Then** every bounding_box.page is checked to be in range [1, total_page_count]
**And** any out-of-range page number raises a validation error

**Given** a bounding box from chunk 2 (pages 26-50)
**When** merged with page_offset=25
**Then** a relative page 1 becomes absolute page 26
**And** a relative page 25 becomes absolute page 50

**Given** validation fails
**When** the error is raised
**Then** the specific bbox and expected page range are logged
**And** the document is marked as 'ocr_failed' with data integrity error

**[PRE-MORTEM - Boundary Tests]:**
**Given** page offset validation runs
**When** boundary pages are checked (1, N, and chunk boundaries)
**Then** extra attention to page 25, 26, 50, 51, etc. (chunk boundaries)
**And** first and last page of each chunk explicitly validated
**And** off-by-one errors detected before data corruption

---

## Story 3.7: Trigger Downstream RAG Re-Processing After OCR

**As a** system ensuring RAG data consistency,
**I want** to automatically trigger chunk re-linking and embedding after large document OCR completes,
**So that** the RAG pipeline has correct bbox_ids for search highlighting.

**Acceptance Criteria:**

**Given** large document OCR completes successfully with merged bounding boxes
**When** document status transitions to 'ocr_complete'
**Then** the existing `chunk_document` Celery task is triggered
**And** old chunks for this document are deleted before new chunks created
**And** new chunks are fuzzy-matched to the new bounding boxes
**And** `bbox_ids` and `page_number` are populated correctly on each chunk

**Given** chunk_document task runs after large document OCR
**When** fuzzy matching runs against 10,000+ bounding boxes
**Then** bbox_linker processes in batches (500 bboxes at a time)
**And** memory usage stays bounded during matching
**And** matching completes within reasonable time (<30 seconds for 400 pages)

**Given** chunks are successfully re-linked
**When** embedding task runs
**Then** embeddings are generated for child chunks
**And** chunks are searchable via hybrid search
**And** search results include correct bbox_ids for highlighting

**[CRITICAL - Existing Pipeline Integration]:**
**Given** the existing document_tasks.py workflow
**When** large document OCR completes
**Then** workflow continues normally: chunk_document → embed_document → extract_entities
**And** no special handling needed - existing pipeline handles re-processing
**And** idempotent chunk save (delete then insert) prevents duplicates

---

## Story 3.8: Validate Entity Mention and Citation Bbox References

**As a** system ensuring citation and entity highlighting works,
**I want** to validate that entity mentions and citations reference valid bounding boxes,
**So that** click-to-highlight features work correctly on large documents.

**Acceptance Criteria:**

**Given** a large document has been re-processed (OCR → chunks → entities)
**When** entity extraction completes
**Then** EntityMention.bbox_ids references valid bounding_boxes records
**And** EntityMention.page_number matches the bbox page numbers

**Given** citations exist for a re-processed document
**When** citation verification runs
**Then** source_bbox_ids are re-linked to new bounding boxes via text matching
**And** target_bbox_ids (in Act documents) remain unchanged
**And** citations with invalid bbox references are flagged for re-verification

**Given** the frontend requests bboxes for a chunk
**When** GET /api/chunks/{chunk_id}/bboxes is called
**Then** all bbox_ids in the chunk resolve to valid bounding_box records
**And** coordinates are valid for the PDF viewer
**And** page_number in bbox matches the chunk's page_number

**[INTEGRITY CHECK]:**
**Given** document processing completes
**When** final validation runs
**Then** verify: COUNT(chunk.bbox_ids) > 0 for all chunks (no orphan chunks)
**And** verify: all bbox_ids in chunks exist in bounding_boxes table
**And** log warning for any chunks without bbox_ids (edge case)

---
