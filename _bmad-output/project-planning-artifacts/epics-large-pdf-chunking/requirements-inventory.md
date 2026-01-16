# Requirements Inventory

## Functional Requirements

```
FR1: System SHALL detect PDF page count before processing and route to appropriate processing path (sync for ≤30 pages, chunked for >30 pages)

FR2: System SHALL split large PDFs into chunks of 25 pages each (safe margin below 30-page limit)

FR3: System SHALL process PDF chunks in parallel using Celery worker pool with controlled concurrency (max 5 simultaneous)

FR4: System SHALL track individual chunk processing status (pending, processing, completed, failed) in database

FR5: System SHALL merge OCR results from all chunks with correct page offset adjustment (chunk-relative → absolute page numbers)

FR6: System SHALL preserve bounding box coordinates (x, y, width, height) unchanged during merge

FR7: System SHALL maintain reading_order_index as per-page sequential values (not global)

FR8: System SHALL support retry of individual failed chunks without reprocessing successful chunks

FR9: System SHALL delete existing bounding boxes for a document before re-inserting (idempotent processing)

FR10: System SHALL batch insert bounding boxes (500 per transaction) to avoid timeout

FR11: System SHALL provide progress visibility for large document processing via job tracking

FR12: System SHALL clean up temporary chunk data after successful merge
```

## Non-Functional Requirements

```
NFR1: PERFORMANCE - Large document (422 pages) SHALL complete OCR in <2 minutes with parallel processing

NFR2: MEMORY - PDF splitting SHALL use streaming/incremental approach, max 50MB memory regardless of PDF size

NFR3: RELIABILITY - Circuit breaker SHALL stop all chunk processing after 3 consecutive failures

NFR4: RELIABILITY - Per-chunk timeout of 60 seconds to prevent hung workers

NFR5: RATE LIMITING - Max 5 concurrent Document AI API calls to stay within 120 req/min quota

NFR6: DATA INTEGRITY - All bounding_boxes.page_number values SHALL be absolute (1-N), never chunk-relative

NFR7: DATA INTEGRITY - All downstream references (chunks.bbox_ids[], entity_mentions.bbox_ids[]) SHALL remain valid after merge

NFR8: COST - No additional cloud services (GCS) - use existing Supabase + Celery infrastructure

NFR9: BACKWARD COMPATIBILITY - Documents ≤30 pages SHALL use existing sync processing path unchanged

NFR10: OBSERVABILITY - Structured logging with correlation IDs for debugging chunk processing
```

## Additional Requirements (from Architecture Analysis)

```
- Database: New table `document_ocr_chunks` for tracking chunk state
- Database: RLS policies for new table matching existing matter isolation pattern
- Celery: New task `process_single_chunk` for parallel execution
- Celery: Use `group()` for parallel dispatch, not `chain()`
- Service: PDFChunker class using PyPDF2 for splitting
- Service: OCRResultMerger class for combining results with offset adjustment
- Service: Circuit breaker pattern for Document AI API failures
- Testing: Property-based tests for page offset calculations
- Testing: Chaos testing for worker failure during chunk processing
- Migration: Backward compatible - no changes to existing document processing for small docs
```

## FR Coverage Map

```
FR1:  Epic 2 - Route based on page count (sync ≤30, chunked >30)
FR2:  Epic 2 - Split PDFs into 25-page chunks
FR3:  Epic 2 - Parallel Celery processing (max 5 concurrent)
FR4:  Epic 1 - Track chunk status in database
FR5:  Epic 2 - Merge results with page offset adjustment
FR6:  Epic 3 - Preserve bounding box coordinates unchanged
FR7:  Epic 3 - Per-page reading order (not global)
FR8:  Epic 2 - Individual chunk retry support
FR9:  Epic 3 - Idempotent processing (delete before insert)
FR10: Epic 3 - Batch insert bounding boxes (500/transaction)
FR11: Epic 1 - Progress visibility via job tracking
FR12: Epic 1 - Cleanup temporary chunk data

NFR1:  Epic 4 - Performance testing (<2 min for 422 pages)
NFR2:  Epic 3 - Memory streaming (max 50MB)
NFR3:  Epic 3 - Circuit breaker (stop after 3 failures)
NFR4:  Epic 3 - Per-chunk timeout (60 seconds)
NFR5:  Epic 3 - Rate limiting (max 5 concurrent API calls)
NFR6:  Epic 3 - Absolute page numbers in all bboxes
NFR7:  Epic 3 - Valid bbox references in downstream tables
NFR8:  Epic 2 - No GCS required (Supabase only)
NFR9:  Epic 2 - Backward compatible for small docs
NFR10: Epic 4 - Structured logging with correlation IDs
```
