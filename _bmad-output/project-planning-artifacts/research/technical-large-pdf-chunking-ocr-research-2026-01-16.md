---
stepsCompleted: ['internal-analysis', 'external-research', 'architecture-design']
inputDocuments: ['backend/app/services/ocr/processor.py', 'backend/supabase/migrations/*.sql']
workflowType: 'research'
lastStep: 4
research_type: 'technical'
research_topic: 'Large PDF Chunking for Google Document AI with Data Integrity Preservation'
research_goals: 'Design robust industry-level solution for processing 400+ page PDFs while preserving linked data relationships'
user_name: 'Juhi'
date: '2026-01-16'
web_research_enabled: true
source_verification: true
---

# Technical Research Report: Large PDF Chunking for Google Document AI

**Date:** 2026-01-16
**Author:** Juhi (with Mary, Business Analyst)
**Research Type:** Technical Architecture
**Confidence Level:** HIGH (verified against codebase + industry sources)

---

## Executive Summary

This research addresses the critical limitation where LDIP's OCR pipeline sends entire PDFs to Google Document AI in a single API call, causing failures for documents exceeding 30 pages (synchronous) or requiring special handling for 100+ page documents.

**Key Finding:** Google Document AI supports **batch/async processing for documents up to 1,000 pages**, but your current implementation only uses synchronous processing. The recommended solution combines:

1. **Batch Processing API** for large documents (>30 pages)
2. **PDF Page Chunking** with offset tracking for data integrity
3. **Coordinate Recalculation** to maintain absolute page references
4. **Staged Processing** with intermediate state tracking

---

## Table of Contents

1. [Current Architecture Analysis](#1-current-architecture-analysis)
2. [Google Document AI Capabilities](#2-google-document-ai-capabilities)
3. [Industry Best Practices](#3-industry-best-practices)
4. [Data Integrity Requirements](#4-data-integrity-requirements)
5. [Recommended Architecture](#5-recommended-architecture)
6. [Implementation Approach](#6-implementation-approach)
7. [Risk Assessment](#7-risk-assessment)
8. [Sources](#8-sources)

---

## 1. Current Architecture Analysis

### 1.1 Current OCR Pipeline Flow

```
PDF Upload → Supabase Storage → Celery Task → Document AI (SINGLE CALL) → Store Results
```

**File:** `backend/app/services/ocr/processor.py`

The current implementation:
- Sends entire PDF content to `DocumentProcessorServiceClient.process_document()`
- No page-level chunking
- No handling for Document AI's page limits
- Fails silently for large documents after 3 retries

### 1.2 Database Schema Relationships (Critical for Chunking)

```
DOCUMENTS (matter_id, document_id)
    │
    ├── BOUNDING_BOXES
    │   ├── page_number (1-indexed, absolute)
    │   ├── reading_order_index (0-indexed, per-page)
    │   ├── x, y, width, height (percentage 0-100)
    │   └── text, confidence
    │
    ├── CHUNKS (RAG)
    │   ├── page_number (primary page)
    │   ├── bbox_ids[] (array referencing bounding_boxes)
    │   └── parent_chunk_id (hierarchical)
    │
    ├── ENTITY_MENTIONS
    │   ├── page_number
    │   └── bbox_ids[]
    │
    ├── CITATIONS
    │   ├── source_page
    │   ├── source_bbox_ids[]
    │   └── target_bbox_ids[]
    │
    └── FINDINGS
        ├── source_pages[]
        └── source_bbox_ids[]
```

**Critical Insight:** All downstream data structures use **absolute page numbers**. Any chunking solution MUST recalculate page offsets when merging results.

### 1.3 Current Limitations

| Limitation | Impact |
|------------|--------|
| No batch processing | Documents >30 pages fail |
| Single API call | No progress tracking for large docs |
| No page offset handling | Cannot merge chunked results |
| No partial failure recovery | All-or-nothing processing |

---

## 2. Google Document AI Capabilities

### 2.1 Processing Limits (Verified 2025-2026)

| Method | Page Limit | File Size | Use Case |
|--------|------------|-----------|----------|
| **Synchronous** (`process_document`) | 30 pages | 40 MB | Small documents |
| **Synchronous with imageless_mode** | 30 pages | 40 MB | Text-only extraction |
| **Batch/Async** (`batch_process_documents`) | **1,000 pages** | 50 MB | Large documents |
| **Custom Document Splitter** | 1,000 pages | 50 MB | Multi-class documents |

**Source:** [Google Cloud Document AI Limits](https://cloud.google.com/document-ai/limits)

### 2.2 Batch Processing API

```python
from google.cloud import documentai_v1 as documentai

def batch_process_documents(
    project_id: str,
    location: str,
    processor_id: str,
    gcs_input_uri: str,      # Must be in GCS
    gcs_output_uri: str,     # Results written here
    timeout: int = 400,      # Seconds
) -> documentai.BatchProcessMetadata:
    """
    Asynchronous batch processing for large documents.
    - Supports up to 1,000 pages per document
    - Results stored in Cloud Storage
    - Returns Long Running Operation (LRO)
    """
```

**Key Requirements:**
1. Input PDF must be in Google Cloud Storage (not Supabase directly)
2. Output is written to GCS bucket
3. Polling required for completion status
4. Results are sharded per page in output

**Source:** [Google Document AI Batch Processing](https://docs.cloud.google.com/document-ai/docs/samples/documentai-batch-process-document)

### 2.3 Coordinate System

Document AI returns normalized coordinates:
- `normalizedVertices`: Range [0, 1] relative to page dimensions
- `vertices`: Absolute pixel coordinates
- **Page indexing is 0-based** in API response

Your system uses:
- Percentage coordinates (0-100) - derived from normalizedVertices × 100
- **Page numbering is 1-based** in database

**Transformation Required:**
```python
# API response (0-based)
api_page = bounding_poly.page_ref.page  # 0, 1, 2...

# Database storage (1-based)
db_page = api_page + 1  # 1, 2, 3...

# For chunked processing with offset:
db_page = api_page + 1 + chunk_page_offset
```

---

## 3. Industry Best Practices

### 3.1 PDF Chunking Strategies

**Approach 1: Fixed Page Chunks**
- Split PDF into N-page chunks (e.g., 25 pages each)
- Simple but may split tables/content mid-page
- **Recommended for OCR** where page boundaries are natural breaks

**Approach 2: Semantic Chunking**
- Use AI to detect logical document boundaries
- Better for RAG but complex for OCR
- Overkill for initial OCR extraction

**Approach 3: Hybrid (Recommended)**
- Use fixed page chunks for OCR processing
- Apply semantic chunking AFTER OCR for RAG chunks
- Your current parent-child chunking handles this well

**Source:** [Weaviate Chunking Strategies](https://weaviate.io/blog/chunking-strategies-for-rag)

### 3.2 Enterprise Solutions Comparison

| Solution | Page Limit | Approach | Cost |
|----------|------------|----------|------|
| Google Document AI Batch | 1,000 pages | Async + GCS | Per-page pricing |
| Amazon Textract | 3,000 pages | Async + S3 | Per-page pricing |
| Azure Form Recognizer | 2,000 pages | Async + Blob | Per-page pricing |
| DeepSeek-OCR (Open) | Unlimited | Self-hosted | Compute only |

**Source:** [V7 Labs Document Processing Comparison](https://www.v7labs.com/blog/document-processing-platform)

### 3.3 Page Boundary Handling

**Challenge:** Multi-page tables, sentences spanning pages, reading order continuity.

**Solution from Industry:**
1. Process each page independently for bounding boxes
2. Maintain page-level metadata during processing
3. Merge results with offset adjustment post-processing
4. Handle cross-page content in downstream processing (RAG chunking)

**Source:** [Azure AI Search Chunking](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents)

---

## 4. Data Integrity Requirements

### 4.1 Must Preserve

| Data Element | Integrity Requirement |
|--------------|----------------------|
| `bounding_boxes.page_number` | Absolute page (1-422), NOT relative to chunk |
| `bounding_boxes.reading_order_index` | Sequential within page, reset per page |
| `chunks.page_number` | Absolute page reference |
| `chunks.bbox_ids[]` | Must reference correct bounding_box records |
| `entity_mentions.page_number` | Absolute page reference |
| `citations.source_page` | Absolute page reference |

### 4.2 Chunk Processing State Machine

```
DOCUMENT STATES:
  pending → chunking_pdf → processing_chunks → merging_results → ocr_complete

CHUNK TRACKING (new table needed):
  document_id, chunk_index, page_start, page_end, status, gcs_path, result_path
```

### 4.3 Failure Recovery Requirements

- **Partial Success:** If chunk 3/10 fails, retry only chunk 3
- **Idempotency:** Re-processing a chunk should not duplicate data
- **Rollback:** If merge fails, clean up partial bounding boxes

---

## 5. Recommended Architecture

### 5.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                     LARGE DOCUMENT OCR PIPELINE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────┐                │
│  │  PDF     │───▶│  PDF        │───▶│  Upload to   │                │
│  │  Upload  │    │  Analyzer   │    │  GCS Bucket  │                │
│  └──────────┘    │  (pages,    │    └──────┬───────┘                │
│                  │   size)     │           │                         │
│                  └─────────────┘           ▼                         │
│                                   ┌──────────────────┐              │
│                                   │  Decision Logic  │              │
│                                   │  pages <= 30?    │              │
│                                   └────────┬─────────┘              │
│                            ┌───────────────┴───────────────┐        │
│                            ▼                               ▼        │
│                   ┌────────────────┐            ┌──────────────────┐│
│                   │  SYNC PATH     │            │  BATCH PATH      ││
│                   │  (<=30 pages)  │            │  (>30 pages)     ││
│                   │                │            │                  ││
│                   │  process_doc() │            │  1. Split PDF    ││
│                   │  direct call   │            │  2. batch_proc() ││
│                   │                │            │  3. Poll LRO     ││
│                   │                │            │  4. Fetch results││
│                   └───────┬────────┘            └────────┬─────────┘│
│                           │                              │          │
│                           └──────────────┬───────────────┘          │
│                                          ▼                          │
│                              ┌──────────────────────┐               │
│                              │  RESULT MERGER       │               │
│                              │                      │               │
│                              │  - Adjust page nums  │               │
│                              │  - Merge bbox lists  │               │
│                              │  - Concat full_text  │               │
│                              │  - Avg confidence    │               │
│                              └──────────┬───────────┘               │
│                                         │                           │
│                                         ▼                           │
│                              ┌──────────────────────┐               │
│                              │  Store to Database   │               │
│                              │  (existing flow)     │               │
│                              └──────────────────────┘               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 New Database Table: `document_ocr_chunks`

```sql
CREATE TABLE public.document_ocr_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    matter_id uuid NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,           -- 0, 1, 2...
    page_start integer NOT NULL,            -- First page in chunk (1-based)
    page_end integer NOT NULL,              -- Last page in chunk (1-based)
    status text NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    gcs_input_path text,                    -- GCS path for input chunk PDF
    gcs_output_path text,                   -- GCS path for output JSON
    error_message text,
    retry_count integer DEFAULT 0,
    processing_started_at timestamptz,
    processing_completed_at timestamptz,
    created_at timestamptz DEFAULT now(),

    UNIQUE (document_id, chunk_index),
    CHECK (page_start <= page_end),
    CHECK (page_start >= 1)
);

CREATE INDEX idx_doc_ocr_chunks_document ON document_ocr_chunks(document_id);
CREATE INDEX idx_doc_ocr_chunks_status ON document_ocr_chunks(document_id, status);
```

### 5.3 PDF Chunker Service

```python
# backend/app/services/ocr/pdf_chunker.py

from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO

class PDFChunker:
    """Split large PDFs into processable chunks."""

    DEFAULT_CHUNK_SIZE = 25  # pages per chunk (safe margin below 30)

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE):
        self.chunk_size = chunk_size

    def get_page_count(self, pdf_content: bytes) -> int:
        """Get total page count from PDF."""
        reader = PdfReader(BytesIO(pdf_content))
        return len(reader.pages)

    def should_chunk(self, page_count: int) -> bool:
        """Determine if PDF needs chunking."""
        return page_count > 30  # Document AI sync limit

    def split_pdf(self, pdf_content: bytes) -> list[tuple[bytes, int, int]]:
        """
        Split PDF into chunks.

        Returns:
            List of (chunk_bytes, page_start, page_end) tuples.
            page_start and page_end are 1-based.
        """
        reader = PdfReader(BytesIO(pdf_content))
        total_pages = len(reader.pages)
        chunks = []

        for chunk_start in range(0, total_pages, self.chunk_size):
            chunk_end = min(chunk_start + self.chunk_size, total_pages)

            writer = PdfWriter()
            for page_idx in range(chunk_start, chunk_end):
                writer.add_page(reader.pages[page_idx])

            output = BytesIO()
            writer.write(output)
            output.seek(0)

            # Convert to 1-based page numbers
            chunks.append((
                output.read(),
                chunk_start + 1,      # page_start (1-based)
                chunk_end,            # page_end (1-based)
            ))

        return chunks
```

### 5.4 Result Merger Service

```python
# backend/app/services/ocr/result_merger.py

from app.models.ocr import OCRResult, OCRBoundingBox, OCRPage

class OCRResultMerger:
    """Merge chunked OCR results with page offset adjustment."""

    def merge_results(
        self,
        chunk_results: list[tuple[OCRResult, int]],  # (result, page_offset)
        document_id: str,
    ) -> OCRResult:
        """
        Merge multiple OCR results into single result.

        Args:
            chunk_results: List of (OCRResult, page_offset) tuples
                          page_offset is 0 for first chunk, chunk_size for second, etc.
        """
        all_pages: list[OCRPage] = []
        all_bboxes: list[OCRBoundingBox] = []
        all_text_parts: list[str] = []
        total_confidence = 0.0
        confidence_count = 0

        for ocr_result, page_offset in chunk_results:
            # Adjust page numbers for pages
            for page in ocr_result.pages:
                adjusted_page = OCRPage(
                    page_number=page.page_number + page_offset,
                    text=page.text,
                    confidence=page.confidence,
                    image_quality_score=page.image_quality_score,
                )
                all_pages.append(adjusted_page)

            # Adjust page numbers for bounding boxes
            for bbox in ocr_result.bounding_boxes:
                adjusted_bbox = OCRBoundingBox(
                    page=bbox.page + page_offset,  # CRITICAL: offset adjustment
                    x=bbox.x,
                    y=bbox.y,
                    width=bbox.width,
                    height=bbox.height,
                    text=bbox.text,
                    confidence=bbox.confidence,
                    reading_order_index=bbox.reading_order_index,  # Stays per-page
                )
                all_bboxes.append(adjusted_bbox)

            # Accumulate text (with page breaks)
            all_text_parts.append(ocr_result.full_text)

            # Accumulate confidence
            if ocr_result.overall_confidence:
                total_confidence += ocr_result.overall_confidence * len(ocr_result.pages)
                confidence_count += len(ocr_result.pages)

        # Sort pages and bboxes by page number
        all_pages.sort(key=lambda p: p.page_number)
        all_bboxes.sort(key=lambda b: (b.page, b.reading_order_index or 0))

        return OCRResult(
            document_id=document_id,
            pages=all_pages,
            bounding_boxes=all_bboxes,
            full_text="\n\n".join(all_text_parts),
            overall_confidence=total_confidence / confidence_count if confidence_count else None,
            processing_time_ms=sum(r.processing_time_ms or 0 for r, _ in chunk_results),
            page_count=len(all_pages),
        )
```

### 5.5 Updated Celery Task

```python
# backend/app/workers/tasks/document_tasks.py (updated)

from app.services.ocr.pdf_chunker import PDFChunker
from app.services.ocr.result_merger import OCRResultMerger
from app.services.storage.gcs_service import GCSService

@celery_app.task(name="process_document", bind=True, ...)
def process_document(self, document_id: str) -> dict:
    """Process document through OCR pipeline with chunking support."""

    # 1. Get document and download PDF
    storage_path, matter_id = doc_service.get_document_for_processing(document_id)
    pdf_content = store_service.download_file(storage_path)
    _validate_pdf_content(pdf_content, document_id)

    # 2. Analyze PDF and decide on processing path
    chunker = PDFChunker()
    page_count = chunker.get_page_count(pdf_content)

    if not chunker.should_chunk(page_count):
        # SYNC PATH: Small document, process directly
        ocr_result = ocr.process_document(pdf_content, document_id)
    else:
        # BATCH PATH: Large document, chunk and process
        ocr_result = _process_large_document(
            document_id=document_id,
            matter_id=matter_id,
            pdf_content=pdf_content,
            page_count=page_count,
        )

    # 3. Save results (existing flow)
    bbox_service.save_bounding_boxes(document_id, matter_id, ocr_result.bounding_boxes)
    doc_service.update_ocr_status(
        document_id=document_id,
        status=DocumentStatus.OCR_COMPLETE,
        extracted_text=ocr_result.full_text,
        page_count=ocr_result.page_count,
        ocr_confidence=ocr_result.overall_confidence,
    )

    return {"status": "ocr_complete", "page_count": page_count, ...}


def _process_large_document(
    document_id: str,
    matter_id: str,
    pdf_content: bytes,
    page_count: int,
) -> OCRResult:
    """Process large document using batch API with chunking."""

    chunker = PDFChunker()
    gcs = GCSService()
    merger = OCRResultMerger()

    # 1. Split PDF into chunks
    chunks = chunker.split_pdf(pdf_content)
    logger.info(f"Split document {document_id} into {len(chunks)} chunks")

    # 2. Create chunk tracking records
    chunk_records = []
    for idx, (chunk_bytes, page_start, page_end) in enumerate(chunks):
        record = ocr_chunk_service.create_chunk(
            document_id=document_id,
            matter_id=matter_id,
            chunk_index=idx,
            page_start=page_start,
            page_end=page_end,
        )
        chunk_records.append(record)

    # 3. Upload chunks to GCS and start batch processing
    operations = []
    for record, (chunk_bytes, _, _) in zip(chunk_records, chunks):
        gcs_input = gcs.upload_chunk(document_id, record.chunk_index, chunk_bytes)
        gcs_output = f"gs://{BUCKET}/ocr-output/{document_id}/chunk-{record.chunk_index}/"

        operation = ocr.batch_process_document(
            gcs_input_uri=gcs_input,
            gcs_output_uri=gcs_output,
        )
        operations.append((record, operation, gcs_output))

        ocr_chunk_service.update_status(record.id, "processing", gcs_input, gcs_output)

    # 4. Poll for completion (with timeout)
    chunk_results = []
    for record, operation, gcs_output in operations:
        try:
            result = _wait_for_operation(operation, timeout=600)
            ocr_result = _parse_batch_result(gcs_output)

            # Calculate page offset for this chunk
            page_offset = record.page_start - 1  # Convert to 0-based offset
            chunk_results.append((ocr_result, page_offset))

            ocr_chunk_service.update_status(record.id, "completed")
        except Exception as e:
            ocr_chunk_service.update_status(record.id, "failed", error=str(e))
            raise

    # 5. Merge all results with page offset adjustment
    merged_result = merger.merge_results(chunk_results, document_id)

    # 6. Cleanup GCS (optional, can be async)
    gcs.cleanup_document_chunks(document_id)

    return merged_result
```

---

## 6. Implementation Approach

### 6.1 Phased Rollout

**Phase 1: Infrastructure (Week 1)**
- Add `document_ocr_chunks` table migration
- Implement `PDFChunker` service
- Add GCS integration for batch processing
- Unit tests for chunking logic

**Phase 2: Batch Processing (Week 2)**
- Implement batch API integration
- Add LRO polling with timeout handling
- Implement `OCRResultMerger` with offset adjustment
- Integration tests with sample large documents

**Phase 3: Task Updates (Week 3)**
- Update `process_document` task with decision logic
- Add chunk status tracking and progress reporting
- Implement retry logic for individual chunks
- Update job tracking for chunked processing

**Phase 4: Validation (Week 4)**
- End-to-end testing with 100, 200, 400+ page documents
- Verify bounding box page numbers are correct
- Verify downstream processing (chunking, embedding, entity extraction)
- Performance benchmarking

### 6.2 Testing Strategy

```python
# Test cases for page offset correctness
def test_bbox_page_numbers_after_merge():
    """Ensure bounding boxes have correct absolute page numbers."""
    # Given: 3 chunks of 25 pages each (75 total)
    # Chunk 1: pages 1-25, Chunk 2: pages 26-50, Chunk 3: pages 51-75

    # When: Merged
    result = merger.merge_results([...])

    # Then: BBox from chunk 2, page 5 (relative) should be page 30 (absolute)
    assert result.bounding_boxes[...].page == 30

def test_reading_order_preserved_per_page():
    """Ensure reading order index is per-page, not global."""
    result = merger.merge_results([...])

    # Each page should have reading_order starting from 0
    page_30_bboxes = [b for b in result.bounding_boxes if b.page == 30]
    assert page_30_bboxes[0].reading_order_index == 0
```

### 6.3 Rollback Plan

If issues discovered post-deployment:
1. Feature flag to disable chunking (process all docs sync, fail >30 pages)
2. Chunk records marked with version for debugging
3. Can reprocess specific documents through admin endpoint

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GCS integration complexity | Medium | High | Reuse existing Supabase storage patterns |
| Batch API latency | Low | Medium | Implement polling with exponential backoff |
| Page offset bugs | Medium | High | Extensive unit tests, manual QA on sample docs |
| Cost increase (GCS + batch) | Low | Low | Batch API same price, GCS minimal for temp storage |
| Celery task timeout | Medium | Medium | Increase timeout for large docs, chunk-level retry |

---

## 8. Sources

### Google Documentation
- [Google Cloud Document AI Limits](https://cloud.google.com/document-ai/limits) - Official page limits
- [Document AI Batch Processing](https://docs.cloud.google.com/document-ai/docs/samples/documentai-batch-process-document) - Batch API reference
- [Document Splitters Behavior](https://cloud.google.com/document-ai/docs/splitters) - Splitter capabilities
- [Handle Processing Response](https://cloud.google.com/document-ai/docs/handle-response) - Coordinate systems

### Industry Best Practices
- [Weaviate Chunking Strategies](https://weaviate.io/blog/chunking-strategies-for-rag) - RAG chunking approaches
- [Azure AI Search Chunking](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents) - Enterprise chunking
- [V7 Labs Document Processing](https://www.v7labs.com/blog/document-processing-platform) - Platform comparison
- [LlamaIndex PDF Parsing](https://www.llamaindex.ai/blog/beyond-ocr-how-llms-are-revolutionizing-pdf-parsing) - Modern approaches

### Community Discussions
- [Google Dev Forum: Large PDFs](https://discuss.google.dev/t/how-to-handle-big-pdf-file-more-than-15-pages-in-document-ai-to-process/172868) - Community solutions
- [Google Dev Forum: Document Splitting](https://discuss.google.dev/t/how-to-split-a-large-document-into-multiple-document-based-on-page-number-using-document-ai/164502/2) - Splitting approaches

---

## Conclusion

The recommended solution uses Google Document AI's **batch processing API** combined with **intelligent PDF chunking** to handle documents of any size while preserving data integrity through careful **page offset management**.

This approach:
- Supports documents up to 1,000 pages (Google's batch limit)
- Maintains backward compatibility with existing small document flow
- Preserves all linked data relationships (bounding boxes, chunks, entities, citations)
- Provides granular progress tracking and failure recovery
- Uses industry-standard patterns from enterprise document processing

**Next Steps:**
1. Review and approve this architecture
2. Create implementation stories in sprint backlog
3. Begin Phase 1 infrastructure work

---

*Research conducted by Mary (Business Analyst Agent) for LDIP Project*
*Generated: 2026-01-16*
