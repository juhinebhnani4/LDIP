# Epic List

## Epic 1: Infrastructure & Chunk State Management

**Goal:** Enable the system to track the processing state of large documents, providing visibility into OCR progress and enabling failure recovery for individual chunks.

**User Outcome:** Users uploading large documents can see processing progress and the system can recover from partial failures without restarting from scratch.

**FRs Covered:** FR4, FR11, FR12

**Deliverables:**
- `document_ocr_chunks` database table with RLS policies
- **Supabase Storage bucket `ocr-chunks` with matter-scoped RLS**
- OCRChunkService for CRUD operations on chunk records
- Integration with existing JobTrackingService for progress visibility
- Cleanup mechanism for temporary chunk data

---

## Epic 2: PDF Chunking & Parallel Processing

**Goal:** Enable processing of PDFs of any size by splitting them into manageable chunks and processing in parallel using the existing Celery infrastructure.

**User Outcome:** Users can upload PDFs of 100, 200, 400+ pages and have them processed successfully. Small documents (≤30 pages) continue using the existing fast sync path.

**FRs Covered:** FR1, FR2, FR3, FR5, FR8

**NFRs Addressed:** NFR8, NFR9

**Deliverables:**
- PDFChunker service for splitting large PDFs into 25-page chunks
- OCRResultMerger service for combining chunk results with page offset adjustment
- Updated `process_document` Celery task with routing logic
- `process_single_chunk` Celery task for parallel execution
- Celery `group()` orchestration for parallel chunk processing
- Individual chunk retry mechanism

---

## Epic 3: Data Integrity & Reliability Hardening

**Goal:** Ensure large document OCR maintains perfect data integrity (correct page numbers, valid references) and handles failures gracefully with production-ready reliability patterns.

**User Outcome:** Large documents are processed reliably without data corruption, memory issues, or cascading failures. All highlighting and citation features work correctly on large documents.

**FRs Covered:** FR6, FR7, FR9, FR10

**NFRs Addressed:** NFR2, NFR3, NFR4, NFR5, NFR6, NFR7

**Deliverables:**
- Streaming PDF split (memory-safe, max 50MB regardless of PDF size)
- Circuit breaker pattern for Document AI API failures
- Per-chunk timeout handling (60 seconds)
- Rate limiting (max 5 concurrent API calls, global Redis semaphore)
- Idempotent chunk processing (delete before re-insert)
- Batch bbox inserts (500 per transaction)
- Page offset validation ensuring absolute page numbers
- **Downstream RAG pipeline trigger after OCR completes**
- **Entity mention and citation bbox reference validation**

---

## Epic 4: Testing & Validation

**Goal:** Ensure confidence that large document processing works correctly across all edge cases with comprehensive automated test coverage.

**User Outcome:** Development team has confidence in the feature's correctness and can safely deploy to production.

**NFRs Addressed:** NFR1, NFR10

**Deliverables:**
- Unit tests for PDFChunker (split logic, edge cases)
- Unit tests for OCRResultMerger (page offset calculations)
- Property-based tests for page offset correctness (hypothesis)
- Integration tests with sample 100, 200, 400+ page documents
- Chaos testing for worker failure during chunk processing
- Performance benchmarks (422 pages in <4 minutes)
- Structured logging validation with correlation IDs
- **RAG pipeline integration tests (bbox linking, search, highlighting)**
- **Global search integration tests for large documents**
- **Bbox linking performance tests (fuzzy match benchmarks)**

---
