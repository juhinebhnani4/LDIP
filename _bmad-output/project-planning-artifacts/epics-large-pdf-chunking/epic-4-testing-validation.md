# Epic 4: Testing & Validation

## Story 4.1: Unit Tests for PDFChunker

**As a** developer,
**I want** comprehensive unit tests for PDFChunker,
**So that** I can be confident the splitting logic is correct.

**Acceptance Criteria:**

**Given** test PDFs of various sizes (10, 30, 31, 50, 100, 422 pages)
**When** unit tests run
**Then** all edge cases are covered:
- Exact multiple of chunk_size (50 pages / 25 = 2 chunks)
- One page over (51 pages = 3 chunks with last having 1 page)
- Single page document
- Empty PDF (should raise error)

**Given** split_pdf output
**When** chunk tuples are examined
**Then** page_start and page_end are validated for each chunk
**And** no pages are skipped or duplicated across chunks

---

## Story 4.2: Unit Tests for OCRResultMerger

**As a** developer,
**I want** comprehensive unit tests for OCRResultMerger,
**So that** I can be confident page offset calculations are correct.

**Acceptance Criteria:**

**Given** mock OCR results for 3 chunks
**When** merge_results is called
**Then** all bounding boxes have correct absolute page numbers
**And** reading_order_index is preserved per-page
**And** full_text is correctly concatenated

**Given** various chunk configurations
**When** tests run
**Then** boundary pages are specifically tested:
- Last page of chunk N (e.g., page 25, 50, 75)
- First page of chunk N+1 (e.g., page 26, 51, 76)
- Single-page final chunk

**[PRE-MORTEM - Off-By-One Focus]:**
**Given** boundary page tests
**When** test suite runs
**Then** explicit tests for off-by-one errors at every chunk boundary
**And** test matrix includes: page 24, 25, 26 and 49, 50, 51 specifically
**And** assertion messages clearly identify which boundary failed

---

## Story 4.3: Property-Based Tests for Page Offsets

**As a** developer,
**I want** property-based tests using hypothesis,
**So that** page offset logic is validated across thousands of random cases.

**Acceptance Criteria:**

**Given** hypothesis generates random page counts (1-1000) and chunk sizes (10-30)
**When** property tests run
**Then** the following properties hold for ALL generated cases:
- `merged_bbox.page == original_absolute_page` always
- No page numbers < 1 or > total_pages
- Sum of chunk page counts == total page count
- Bboxes are sorted by (page, reading_order_index)

**Given** 10,000 random test cases
**When** all properties are checked
**Then** zero violations are found

---

## Story 4.4: Integration Tests with Sample Documents

**As a** QA engineer,
**I want** integration tests with real sample documents,
**So that** the full pipeline is validated end-to-end.

**Acceptance Criteria:**

**Given** sample PDFs of 50, 100, 200, and 422 pages
**When** each is processed through the full chunking pipeline
**Then** OCR completes successfully
**And** bounding box count matches expected (roughly 20 per page)
**And** all page numbers are absolute and in range
**And** downstream processing (chunking, embedding) works correctly

**Given** a processed large document
**When** citation highlighting is tested
**Then** the correct text is highlighted on the correct page
**And** navigation to page N shows the expected content

**[PRE-MORTEM - Cross-Chunk Citation Tests]:**
**Given** integration tests with large documents
**When** citations are tested
**Then** specifically test citations that span chunk boundaries
**And** test citation on page 25, then page 26 (chunk 1 to chunk 2)
**And** verify highlighting coordinates are valid in viewer

---

## Story 4.5: Chaos Testing for Worker Failures

**As a** reliability engineer,
**I want** chaos tests that simulate worker failures,
**So that** I know the system recovers gracefully.

**Acceptance Criteria:**

**Given** a document with 10 chunks being processed
**When** a worker is killed mid-processing of chunk 5
**Then** chunks 1-4 remain marked as 'completed'
**And** chunk 5 is marked as 'failed' or 'processing' (detected via timeout)
**And** retry correctly reprocesses only chunk 5+

**Given** the merge operation is interrupted
**When** the system recovers
**Then** either the merge completes or all results are preserved for retry
**And** no partial/corrupt data is saved to bounding_boxes table

---

## Story 4.6: Performance Benchmarks

**As a** performance engineer,
**I want** benchmarks proving the system meets performance requirements,
**So that** we can deploy with confidence.

**Acceptance Criteria:**

**Given** a 422-page PDF (matching the original failing document)
**When** processed with parallel chunking (17 chunks, 5 concurrent, ~45s per chunk)
**Then** total processing time is <4 minutes
**And** results are logged with timing breakdown (split, process, merge)
**And** breakdown: split <10s, parallel OCR ~3min, merge <10s

**Given** 5 concurrent large documents (200+ pages each)
**When** processed simultaneously
**Then** all complete within 5 minutes
**And** no OOM errors on workers with 2GB memory
**And** Document AI rate limits are not exceeded

**[PRE-MORTEM - Memory Benchmark]:**
**Given** performance benchmarks run
**When** memory is profiled
**Then** peak memory per worker is recorded
**And** memory growth over time is tracked (detect leaks)
**And** benchmark fails if memory exceeds 80% of limit

---

## Story 4.7: Structured Logging Validation

**As a** operations engineer,
**I want** structured logging with correlation IDs,
**So that** I can debug issues in production.

**Acceptance Criteria:**

**Given** a large document is processed
**When** logs are examined
**Then** all log entries include document_id and correlation_id
**And** chunk-specific logs include chunk_index

**Given** a failure occurs in chunk processing
**When** logs are searched by correlation_id
**Then** the complete processing history is visible
**And** the exact failure point is identifiable

**Given** performance metrics are logged
**When** logs are aggregated
**Then** processing times per chunk and total are available for monitoring

---

## Story 4.8: RAG Pipeline Integration Tests for Large Documents

**As a** QA engineer,
**I want** integration tests validating the full RAG pipeline works with large documents,
**So that** search and highlighting features work correctly.

**Acceptance Criteria:**

**Given** a 200+ page document processed through OCR chunking
**When** the full pipeline completes (OCR → chunk → embed → entity extraction)
**Then** all chunks have non-empty bbox_ids arrays
**And** all bbox_ids resolve to valid bounding_box records
**And** chunk page_number matches the most common page in bbox_ids

**Given** a processed large document
**When** hybrid search is executed with a query matching page 150 content
**Then** search returns relevant chunks
**And** chunk bbox_ids point to page 150 bounding boxes
**And** highlighting renders correctly in PDF viewer at page 150

**Given** a processed large document with entities extracted
**When** entity mentions are retrieved
**Then** EntityMention.bbox_ids are valid
**And** clicking an entity mention highlights correct text on correct page
**And** entity page_number matches bbox page_number

---

## Story 4.9: Global Search Integration Tests

**As a** QA engineer,
**I want** integration tests validating global search works with large documents,
**So that** users can find content across all their matters.

**Acceptance Criteria:**

**Given** multiple matters with large documents (100+ pages each)
**When** global search is executed
**Then** results include matches from large documents
**And** matched_content snippets are accurate
**And** clicking a result navigates to correct document and page

**Given** a global search result from a large document on page 300
**When** user clicks to view in context
**Then** PDF viewer opens to page 300
**And** search term is highlighted via bbox coordinates
**And** surrounding context chunks are available for expansion

**Given** large document chunks are embedded
**When** semantic search finds a match
**Then** the chunk's bbox_ids enable precise highlighting
**And** hybrid search combines BM25 + semantic scores correctly
**And** matter isolation is maintained (no cross-matter leakage)

---

## Story 4.10: Bbox Linking Performance Tests

**As a** performance engineer,
**I want** benchmarks for bbox fuzzy matching on large documents,
**So that** chunking doesn't become a bottleneck.

**Acceptance Criteria:**

**Given** a 422-page document with ~8,500 bounding boxes
**When** chunk_document task runs with bbox linking
**Then** fuzzy matching completes in <30 seconds
**And** memory usage stays under 200MB during matching
**And** all chunks have bbox_ids populated

**Given** bbox_linker processes 10,000+ bounding boxes
**When** sliding window fuzzy match runs
**Then** matching is batched to prevent O(N²) explosion
**And** progress is logged every 1000 bboxes
**And** timeout at 60 seconds fails gracefully with partial results

**Given** concurrent large documents being chunked
**When** multiple chunk_document tasks run
**Then** bbox matching doesn't create resource contention
**And** each task uses bounded memory independently

---

