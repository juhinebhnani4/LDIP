# Epic 2: PDF Chunking & Parallel Processing

## Story 2.1: Implement PDF Page Count Detection and Routing

**As a** system processing uploaded documents,
**I want** to detect PDF page count and route to the appropriate processing path,
**So that** small documents use fast sync processing and large documents use chunked processing.

**Acceptance Criteria:**

**Given** a PDF document is uploaded
**When** the process_document task starts
**Then** the page count is read from the PDF without loading full content into memory

**Given** a PDF with ≤30 pages
**When** the routing decision is made
**Then** the document is processed using the existing sync Document AI call
**And** no chunk records are created

**Given** a PDF with >30 pages
**When** the routing decision is made
**Then** the document is routed to the chunked processing path
**And** chunk records are created before processing begins

**[RED TEAM - Malicious PDF Defense]:**
**Given** a PDF claims to have 1,000,000 pages (malicious header)
**When** page count is validated
**Then** actual page enumeration confirms the count before processing
**And** maximum page limit (10,000) is enforced to prevent resource exhaustion
**And** suspicious discrepancies are logged for security monitoring

---

## Story 2.2: Implement PDFChunker Service

**As a** backend developer,
**I want** a service to split large PDFs into processable chunks,
**So that** each chunk can be sent to Document AI within the 30-page limit.

**Acceptance Criteria:**

**Given** a PDF with 75 pages and chunk_size=25
**When** I call `split_pdf(pdf_content)`
**Then** I receive 3 chunks: (pages 1-25), (pages 26-50), (pages 51-75)
**And** each chunk is a valid PDF bytes object

**Given** a PDF with 80 pages and chunk_size=25
**When** I call `split_pdf(pdf_content)`
**Then** I receive 4 chunks: (pages 1-25), (pages 26-50), (pages 51-75), (pages 76-80)
**And** the last chunk contains only 5 pages

**Given** any chunk returned by split_pdf
**When** I examine the chunk tuple
**Then** it contains (chunk_bytes, page_start, page_end) where page numbers are 1-based

**Given** `should_chunk(page_count)` is called with page_count ≤30
**When** the method returns
**Then** it returns False

**Given** `should_chunk(page_count)` is called with page_count >30
**When** the method returns
**Then** it returns True

**[RED TEAM - PDF Sandbox]:**
**Given** a PDF is being parsed
**When** PyPDF2/pikepdf operations execute
**Then** parsing occurs in isolated subprocess with resource limits
**And** timeout kills parsing if it exceeds 30 seconds
**And** malformed PDFs that crash parser are handled gracefully

**[SHARK TANK - PDF Library Evaluation]:**
**Given** PDFChunker needs a PDF library
**When** implementing the service
**Then** evaluate PyPDF2, pikepdf, and pymupdf for:
- Memory efficiency on large files
- Handling of malformed PDFs
- Streaming page extraction support
**And** document the selection rationale in code comments

---

## Story 2.3: Implement OCR Result Merger Service

**As a** backend developer,
**I want** a service to merge OCR results from multiple chunks with correct page offsets,
**So that** the final result has absolute page numbers matching the original document.

**Acceptance Criteria:**

**Given** chunk results from pages 1-25, 26-50, 51-75
**When** I call `merge_results(chunk_results, document_id)`
**Then** all bounding boxes have absolute page numbers (1-75)
**And** a bbox from chunk 2, relative page 5 has absolute page 30

**Given** merged results
**When** I examine bounding_boxes
**Then** reading_order_index values restart at 0 for each page (per-page, not global)

**Given** merged results
**When** I examine the full_text
**Then** text from all chunks is concatenated with page breaks preserved

**Given** merged results
**When** I examine overall_confidence
**Then** it is the weighted average of chunk confidences (weighted by page count)

**Given** merged results
**When** I examine page_count
**Then** it equals the sum of pages across all chunks

**[CHAOS MONKEY - Result Validation]:**
**Given** chunk results are retrieved from storage for merging
**When** results are loaded
**Then** SHA256 checksum is validated against stored `result_checksum`
**And** corrupted results trigger re-processing of that chunk
**And** validation failures are logged with details

**[PRE-MORTEM - Post-Merge Validation]:**
**Given** merge operation completes
**When** final result is ready
**Then** validate: total_bboxes == sum(chunk_bboxes)
**And** validate: page_numbers are continuous from 1 to N
**And** validate: no duplicate reading_order_index on same page
**And** failure triggers detailed error logging before save

---

## Story 2.4: Implement Parallel Chunk Processing with Celery

**As a** system processing large documents,
**I want** to process PDF chunks in parallel using Celery workers,
**So that** large documents complete in minutes instead of tens of minutes.

**Acceptance Criteria:**

**Given** a document split into 17 chunks
**When** parallel processing is initiated
**Then** a Celery `group()` dispatches all chunk tasks simultaneously
**And** chunk status is updated to 'processing' for each chunk

**Given** a `process_single_chunk` task receives chunk data
**When** the task executes
**Then** it calls Document AI sync API with the chunk bytes
**And** updates chunk status to 'completed' on success
**And** returns the OCR result for that chunk

**Given** all chunk tasks complete
**When** results are collected
**Then** merge_results is called with all chunk results and their page offsets
**And** the merged result is stored using existing bbox_service and doc_service

**[RED TEAM - Distributed Lock]:**
**Given** parallel chunks are being processed
**When** chunk task starts
**Then** acquire distributed lock on `chunk:{document_id}:{chunk_index}`
**And** prevent duplicate processing of same chunk by multiple workers
**And** lock expires after 120 seconds to prevent deadlocks

**[DEBATE CLUB - Store Results in Supabase Storage]:**
**Given** a chunk completes OCR processing
**When** the result is ready
**Then** store result as JSON in Supabase Storage at `ocr-chunks/{document_id}/{chunk_index}.json`
**And** update chunk record with `result_storage_path`
**And** calculate and store SHA256 checksum in `result_checksum` column

**[SHARK TANK - Global Backpressure]:**
**Given** system-wide queue depth exceeds threshold (e.g., 100 pending chunks)
**When** new large document upload is received
**Then** document is queued with lower priority
**And** user sees "High load - processing may be delayed"
**And** metrics are emitted for monitoring backpressure state

**[SHARK TANK - Celery Error Handling]:**
**Given** Celery group() task executes
**When** any chunk task fails
**Then** exception is caught and logged with full context
**And** partial results from successful chunks are preserved
**And** document is NOT marked as permanently failed (retry possible)

---

## Story 2.5: Implement Individual Chunk Retry

**As a** system handling processing failures,
**I want** to retry failed chunks individually without reprocessing successful chunks,
**So that** transient failures don't waste processing time and cost.

**Acceptance Criteria:**

**Given** chunks 1-10 completed and chunk 11 failed
**When** retry is triggered for the document
**Then** only chunk 11 is reprocessed
**And** chunks 1-10 results are retrieved from cache/storage

**Given** a chunk fails with a retryable error (network, timeout, 429)
**When** the chunk task handles the error
**Then** it updates chunk status to 'failed' with error_message
**And** increments retry_count

**Given** a chunk has retry_count < 3
**When** retry is triggered
**Then** the chunk is reprocessed

**Given** a chunk has retry_count >= 3
**When** retry is triggered
**Then** the chunk is marked as permanently failed
**And** the document is marked as 'ocr_failed'

**[DEBATE CLUB - Retrieve from Storage on Retry]:**
**Given** a retry is triggered for a document with some completed chunks
**When** retry begins
**Then** completed chunk results are retrieved from Supabase Storage (not re-OCR'd)
**And** only failed chunks are sent to Document AI
**And** storage path from chunk record is used to locate cached results

---
