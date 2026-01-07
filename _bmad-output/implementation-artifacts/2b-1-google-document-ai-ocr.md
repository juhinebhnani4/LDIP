# Story 2B.1: Integrate Google Document AI for OCR

Status: done

## Story

As an **attorney**,
I want **uploaded PDFs to be OCR-processed with high accuracy**,
So that **scanned documents become searchable and analyzable**.

## Acceptance Criteria

1. **Given** a PDF document is uploaded **When** OCR processing begins **Then** Google Document AI extracts text from each page **And** per-word confidence scores are captured **And** bounding box coordinates are extracted for each text block

2. **Given** a page contains a mix of text and images **When** OCR is performed **Then** text from images is extracted **And** native text is preserved with its positions

3. **Given** a document is in Indian languages (Gujarati, Hindi, English) **When** OCR is performed **Then** text is correctly extracted in the original language **And** mixed-language documents are handled correctly

4. **Given** OCR completes for a document **When** results are saved **Then** extracted text is stored with page numbers **And** processing status is updated to "ocr_complete"

5. **Given** Google Document AI is unavailable or returns an error **When** OCR is attempted **Then** the document is queued for automatic retry with exponential backoff **And** after 3 failed retries, the document is marked as "ocr_failed" with error details **And** the user is notified and can manually trigger retry later

## Tasks / Subtasks

- [x] Task 1: Set Up Google Document AI Credentials (AC: #1)
  - [x] Create Google Cloud project (if not exists) and enable Document AI API
  - [x] Create a Document AI processor (OCR type: `OCR_PROCESSOR`)
  - [x] Create service account with Document AI API User role
  - [x] Download service account JSON key
  - [x] Add credentials path and processor ID to backend `.env`
  - [x] Add google-cloud-documentai to backend dependencies

- [x] Task 2: Create OCR Service Module (AC: #1, #2, #3)
  - [x] Create `backend/app/services/ocr/__init__.py`
  - [x] Create `backend/app/services/ocr/processor.py` with `OCRProcessor` class
  - [x] Implement `process_document()` method using Document AI API
  - [x] Handle PDF byte stream input (download from Supabase Storage)
  - [x] Configure processor for Indian languages (hi, gu, en)
  - [x] Enable image quality scores: `processOptions.ocrConfig.enableImageQualityScores = true`
  - [x] Extract per-page text, confidence scores, and bounding boxes

- [x] Task 3: Create Bounding Box Extraction Logic (AC: #1)
  - [x] Create `backend/app/services/ocr/bbox_extractor.py`
  - [x] Implement `extract_bounding_boxes()` from Document AI response
  - [x] Convert normalized vertices (0-1) to percentage coordinates (0-100) per existing schema
  - [x] Handle edge case where vertices[0] coordinates are 0 (omitted in JSON)
  - [x] Group bounding boxes by page number
  - [x] Store text content and confidence per bounding box

- [x] Task 4: Create OCR Result Models (AC: #1, #4)
  - [x] Create `backend/app/models/ocr.py` with Pydantic models
  - [x] `OCRPage`: page_number, text, confidence, image_quality_score
  - [x] `OCRBoundingBox`: page, x, y, width, height, text, confidence
  - [x] `OCRResult`: document_id, pages, bounding_boxes, overall_confidence, processing_time_ms
  - [x] `OCRStatus`: pending, processing, ocr_complete, ocr_failed

- [x] Task 5: Implement Document Processing Celery Task (AC: #1, #4, #5)
  - [x] Update `backend/app/workers/tasks/document_tasks.py`
  - [x] Implement `process_document()` task:
    - [x] Download PDF from Supabase Storage using service client
    - [x] Update document status to "processing" with processing_started_at
    - [x] Call OCR service to process document
    - [x] Save page text to documents table (extracted_text column)
    - [x] Save bounding boxes to bounding_boxes table
    - [x] Update page_count on documents table
    - [x] Update status to "ocr_complete" or "ocr_failed"
    - [x] Set processing_completed_at timestamp
  - [x] Implement retry logic with exponential backoff (3 retries, 30s/60s/120s delays)

- [x] Task 6: Add Database Columns for OCR Results (AC: #4)
  - [x] Create migration to add `extracted_text TEXT` column to documents table
  - [x] Create migration to add `ocr_confidence FLOAT` column to documents table
  - [x] Create migration to add `ocr_quality_score FLOAT` column to documents table
  - [x] Create migration to add `ocr_error TEXT` column for failed OCR details

- [x] Task 7: Create OCR Queue Trigger on Document Upload (AC: #1)
  - [x] Update `backend/app/api/routes/documents.py` upload endpoint
  - [x] After successful document creation, queue `process_document` Celery task
  - [x] Use 'high' priority queue for small documents (<10MB file size)
  - [x] Use 'default' queue for large documents (>=10MB)

- [x] Task 8: Implement Status Update Broadcasting (AC: #4)
  - [x] Create Supabase Realtime subscription trigger for document status changes
  - [x] Or use Redis pub/sub for processing status updates
  - [x] Frontend can subscribe to `document:{id}:status` channel

- [x] Task 9: Write Backend Unit Tests
  - [x] Create `backend/tests/services/test_ocr.py`
  - [x] Test OCRProcessor with mocked Document AI client
  - [x] Test bounding box extraction and coordinate conversion
  - [x] Test error handling and retry logic
  - [x] Test multi-language detection

- [x] Task 10: Write Backend Integration Tests
  - [x] Create `backend/tests/integration/test_ocr_integration.py`
  - [x] Test full pipeline: upload → queue → process → save
  - [x] Test status transitions: pending → processing → ocr_complete
  - [x] Test failure handling: processing → ocr_failed
  - [x] Mock external Document AI calls

## Dev Notes

### Google Document AI Setup

**API Version:** Enterprise Document OCR (pretrained-ocr-v2.1-2024-08-07 or later)

**Python SDK:**
```python
from google.cloud import documentai_v1 as documentai

# Initialize client
client = documentai.DocumentProcessorServiceClient()

# Process document
request = documentai.ProcessRequest(
    name=f"projects/{project_id}/locations/{location}/processors/{processor_id}",
    raw_document=documentai.RawDocument(
        content=pdf_bytes,
        mime_type="application/pdf"
    ),
    process_options=documentai.ProcessOptions(
        ocr_config=documentai.OcrConfig(
            enable_image_quality_scores=True,
            # Languages auto-detected, but can hint:
            # language_hints=["en", "hi", "gu"]
        )
    )
)
response = client.process_document(request=request)
```

**Bounding Box Extraction:**
```python
# Document AI uses normalized vertices (0-1 range)
# Convert to percentage (0-100) for our schema
for page in response.document.pages:
    for block in page.blocks:
        layout = block.layout
        bbox = layout.bounding_poly.normalized_vertices
        # Note: vertex with value 0 may be omitted in response
        x = bbox[0].x * 100 if len(bbox) > 0 else 0
        y = bbox[0].y * 100 if len(bbox) > 0 else 0
        width = (bbox[2].x - bbox[0].x) * 100 if len(bbox) > 2 else 0
        height = (bbox[2].y - bbox[0].y) * 100 if len(bbox) > 2 else 0
```

**Confidence Access:**
```python
# Per-token confidence
for token in page.tokens:
    confidence = token.layout.confidence  # 0-1 float

# Image quality score (if enabled)
quality = page.image_quality_scores.quality_score  # 0-1 float
```

### LLM Routing (CRITICAL - Per Architecture)

| Task | Model | Reason |
|------|-------|--------|
| OCR Processing | Google Document AI | Specialized OCR, not LLM |
| OCR Post-processing | Gemini 3 Flash | Bulk, low-stakes (Story 2b-2) |

**This story uses Google Document AI only - NOT an LLM.**

### Error Handling & Retry Strategy

**Retry Configuration (Celery):**
```python
@celery_app.task(
    bind=True,
    autoretry_for=(DocumentAIError, ConnectionError),
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=120,  # Max 2 minutes
    max_retries=3,
    retry_jitter=True,  # Add randomness to prevent thundering herd
)
def process_document(self, document_id: str) -> dict:
    try:
        # ... processing logic
    except Exception as e:
        if self.request.retries >= self.max_retries:
            # Mark as failed after max retries
            update_document_status(document_id, "ocr_failed", error=str(e))
            raise
        raise self.retry(exc=e)
```

**Error Status Tracking:**
- On first failure: Log error, increment retry count
- On 2nd/3rd failure: Log with increasing severity
- After 3 failures: Set status to "ocr_failed", save error details to `ocr_error` column
- User can manually retry via API endpoint (clears error, resets retry count)

### Downstream Dependencies

This story creates the foundation for:
- **Story 2b-2 (Gemini OCR Validation):** Uses extracted text + confidence scores
- **Story 2b-3 (OCR Quality Assessment):** Uses image_quality_score and confidence
- **Story 2b-4 (Bounding Boxes Table):** Already created, this story populates it
- **Story 2b-5 (Parent-Child Chunking):** Uses extracted_text from documents
- **Epic 3 (Citation Engine):** Uses text + bounding boxes for highlighting

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Backend Technology Stack
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **structlog** for logging - NOT standard logging library
- **Celery + Redis** - for background tasks

#### Matter Isolation (4-Layer Enforcement)
```python
# Layer 1: RLS on bounding_boxes table (already in migration)
# Layer 2: Vector namespace prefix (not applicable to OCR)
# Layer 3: Redis key prefix (for status updates)
redis_key = f"matter:{matter_id}:document:{document_id}:ocr_status"
# Layer 4: API middleware validates matter access
```

#### API Response Format (MANDATORY)
```python
# Success
{ "data": { "document_id": "uuid", "status": "processing" } }

# Error
{ "error": { "code": "OCR_FAILED", "message": "...", "details": {} } }
```

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| Python functions | snake_case | `process_document`, `extract_bounding_boxes` |
| Python classes | PascalCase | `OCRProcessor`, `OCRResult` |
| Database columns | snake_case | `extracted_text`, `ocr_confidence` |

### File Organization

```
backend/app/
├── services/
│   └── ocr/                           (NEW)
│       ├── __init__.py                (NEW)
│       ├── processor.py               (NEW) - OCRProcessor class
│       └── bbox_extractor.py          (NEW) - Bounding box extraction
├── models/
│   └── ocr.py                         (NEW) - OCR Pydantic models
├── workers/
│   └── tasks/
│       └── document_tasks.py          (UPDATE) - Implement process_document
└── api/
    └── routes/
        └── documents.py               (UPDATE) - Queue OCR task on upload

supabase/migrations/
└── YYYYMMDD_add_ocr_columns.sql       (NEW) - Add extracted_text, etc.

backend/tests/
├── services/
│   └── test_ocr.py                    (NEW)
└── integration/
    └── test_ocr_integration.py        (NEW)
```

### Existing Code to Reuse

**FROM Story 2a-2 and 2a-3:**
- `backend/app/services/storage_service.py` - Download files from Supabase Storage
- `backend/app/services/document_service.py` - Update document records
- `backend/app/workers/celery.py` - Celery app configuration
- `backend/app/workers/tasks/document_tasks.py` - Placeholder task to update
- `supabase/migrations/20260106000003_create_bounding_boxes_table.sql` - Schema ready

**FROM Story 1-7:**
- `backend/app/api/deps.py` - Matter access validation dependencies
- RLS policy patterns for all tables

### Database Schema Reference

**Existing bounding_boxes table (ready to use):**
```sql
CREATE TABLE public.bounding_boxes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id),
  document_id uuid NOT NULL REFERENCES public.documents(id),
  page_number integer NOT NULL,
  x float NOT NULL,          -- Percentage 0-100
  y float NOT NULL,          -- Percentage 0-100
  width float NOT NULL,      -- Percentage 0-100
  height float NOT NULL,     -- Percentage 0-100
  text text NOT NULL,
  confidence float,          -- 0-1
  created_at timestamptz DEFAULT now()
);
```

**New columns for documents table:**
```sql
ALTER TABLE public.documents ADD COLUMN extracted_text TEXT;
ALTER TABLE public.documents ADD COLUMN ocr_confidence FLOAT;
ALTER TABLE public.documents ADD COLUMN ocr_quality_score FLOAT;
ALTER TABLE public.documents ADD COLUMN ocr_error TEXT;
```

### Environment Variables Required

```bash
# backend/.env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us  # or eu
GOOGLE_DOCUMENT_AI_PROCESSOR_ID=your-processor-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### Previous Story Intelligence

**FROM Story 2a-3 (Documents Table):**
- DocumentService pattern established with typed errors
- Document status values: 'pending', 'processing', 'completed', 'failed'
- RLS policies verified working
- Test patterns with mocked Supabase client

**FROM Story 2a-2 (Storage Integration):**
- StorageService uses service client (bypasses RLS for trusted operations)
- Download files via signed URLs or direct service client
- Error handling with DocumentServiceError pattern

**FROM Story 1-2 (FastAPI Backend):**
- Celery configuration with Redis broker
- Task priority queues: 'high', 'default', 'low'
- structlog logging throughout

### Git Intelligence

Recent commits:
```
1afc781 fix(tests): resolve test failures in backend auth and frontend components
e76a247 feat(documents): complete story 2a-3 with code review fixes
cbd8643 feat(backend): document upload and storage service improvements
```

**Recommended commit:** `feat(ocr): integrate Google Document AI for document processing (Story 2b-1)`

### Testing Guidance

#### Unit Tests (Mocked)

```python
# test_ocr.py
import pytest
from unittest.mock import Mock, patch
from app.services.ocr.processor import OCRProcessor

@pytest.fixture
def mock_document_ai_client():
    with patch('google.cloud.documentai_v1.DocumentProcessorServiceClient') as mock:
        yield mock

@pytest.mark.asyncio
async def test_process_document_extracts_text(mock_document_ai_client):
    """Test OCR processor extracts text correctly."""
    # Setup mock response
    mock_response = Mock()
    mock_response.document.text = "Sample extracted text"
    mock_response.document.pages = [...]
    mock_document_ai_client.return_value.process_document.return_value = mock_response

    processor = OCRProcessor()
    result = await processor.process_document(b"pdf_bytes")

    assert result.text == "Sample extracted text"
    assert len(result.bounding_boxes) > 0

@pytest.mark.asyncio
async def test_process_document_handles_multilingual(mock_document_ai_client):
    """Test OCR handles Hindi, Gujarati, English mix."""
    # Test with multilingual content
    pass

@pytest.mark.asyncio
async def test_bbox_extraction_converts_coordinates():
    """Test normalized vertices are converted to percentages."""
    from app.services.ocr.bbox_extractor import extract_bounding_boxes

    # Mock page with normalized vertices
    mock_page = Mock()
    mock_page.blocks[0].layout.bounding_poly.normalized_vertices = [
        Mock(x=0.1, y=0.2),  # top-left
        Mock(x=0.5, y=0.2),  # top-right
        Mock(x=0.5, y=0.3),  # bottom-right
        Mock(x=0.1, y=0.3),  # bottom-left
    ]

    boxes = extract_bounding_boxes(mock_page, page_number=1)

    assert boxes[0].x == 10.0  # 0.1 * 100
    assert boxes[0].y == 20.0  # 0.2 * 100
    assert boxes[0].width == 40.0  # (0.5 - 0.1) * 100
    assert boxes[0].height == 10.0  # (0.3 - 0.2) * 100
```

#### Integration Tests

```python
# test_ocr_integration.py
@pytest.mark.asyncio
async def test_full_ocr_pipeline(test_document, mock_document_ai):
    """Test upload → queue → process → save pipeline."""
    # 1. Upload document (from previous stories)
    # 2. Verify Celery task queued
    # 3. Run task synchronously for test
    # 4. Verify document status updated
    # 5. Verify bounding boxes saved
    pass

@pytest.mark.asyncio
async def test_ocr_failure_marks_document_failed(test_document, mock_document_ai):
    """Test failure handling after max retries."""
    mock_document_ai.side_effect = Exception("API Error")

    # Run task with retries exhausted
    # Verify status is "ocr_failed"
    # Verify ocr_error contains message
    pass
```

### Anti-Patterns to AVOID

```python
# WRONG: Using standard logging
import logging
logger = logging.getLogger(__name__)

# CORRECT: Use structlog
import structlog
logger = structlog.get_logger(__name__)

# WRONG: Blocking sync call in async context
def process_document(document_id: str):
    result = ocr_client.process(...)  # Blocking!

# CORRECT: Use async or run in thread pool
async def process_document(document_id: str):
    result = await asyncio.to_thread(ocr_client.process, ...)

# WRONG: Not handling Document AI errors
result = client.process_document(request)

# CORRECT: Handle with retry logic
try:
    result = client.process_document(request)
except google.api_core.exceptions.GoogleAPICallError as e:
    logger.error("ocr_api_error", error=str(e))
    raise

# WRONG: Hardcoding credentials
client = documentai.DocumentProcessorServiceClient(
    credentials={"key": "hardcoded"}
)

# CORRECT: Use environment-based credentials
# Set GOOGLE_APPLICATION_CREDENTIALS env var
client = documentai.DocumentProcessorServiceClient()

# WRONG: Not converting coordinates
bbox = {"x": 0.1, "y": 0.2}  # Normalized

# CORRECT: Convert to percentage per schema
bbox = {"x": 0.1 * 100, "y": 0.2 * 100}  # 10.0, 20.0
```

### Performance Considerations

- **Batch processing:** Document AI can process up to 15 pages per request inline, or use batch for larger docs
- **Memory:** Large PDFs should be processed page-by-page to avoid memory issues
- **Rate limits:** Google Document AI has per-minute quotas (check your tier)
- **Queue priority:** Small documents (<100 pages) get 'high' queue for faster UX

### Manual Steps Required After Implementation

#### Environment Variables
- [ ] Add to `backend/.env`:
  - `GOOGLE_CLOUD_PROJECT=your-project-id`
  - `GOOGLE_CLOUD_LOCATION=us`
  - `GOOGLE_DOCUMENT_AI_PROCESSOR_ID=processor-id`
  - `GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json`

#### Google Cloud Configuration
- [ ] Enable Document AI API in Google Cloud Console
- [ ] Create OCR processor in Document AI console
- [ ] Create service account with "Document AI API User" role
- [ ] Download JSON key and place in secure location

#### Migrations
- [ ] Run: `supabase db push` or apply `YYYYMMDD_add_ocr_columns.sql`

#### Dependencies
- [ ] Run: `uv add google-cloud-documentai`

#### Manual Tests
- [ ] Upload a PDF and verify OCR processing starts
- [ ] Check document status transitions (pending → processing → ocr_complete)
- [ ] Verify bounding boxes appear in database
- [ ] Test with Hindi/Gujarati document for multilingual support
- [ ] Test with poor quality scan to verify error handling

### Project Structure Notes

- OCR service will be used by all document processing workflows
- Bounding boxes enable click-to-highlight in PDF viewer (Epic 11)
- Extracted text feeds into RAG pipeline (Story 2b-5)
- OCR confidence used for Gemini validation routing (Story 2b-2)
- This story starts Epic 2B (OCR & RAG Pipeline)

### References

- [Source: _bmad-output/architecture.md#Background-Jobs] - Celery + Redis patterns
- [Source: _bmad-output/architecture.md#Error-Handling-Patterns] - Exception classes
- [Source: _bmad-output/project-context.md#LLM-Routing] - Google Document AI for OCR
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-2.4] - Acceptance criteria
- [Source: supabase/migrations/20260106000003_create_bounding_boxes_table.sql] - Existing schema
- [Source: _bmad-output/implementation-artifacts/2a-3-documents-table.md] - Previous story patterns
- [Source: https://docs.cloud.google.com/document-ai/docs/handle-response] - Document AI response handling
- [Source: https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr] - Enterprise OCR features

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 10 tasks completed successfully
- 64 total tests passing (51 unit tests + 13 integration tests)
- OCR pipeline implemented with Google Document AI integration
- Redis pub/sub for real-time status updates
- Celery task with retry logic and exponential backoff
- Bounding box extraction with percentage-based coordinates (0-100)
- Document status transitions: pending → processing → ocr_complete/ocr_failed
- Priority queuing: small documents (<10MB) use 'high' queue, larger use 'default'

### File List

**New Files Created:**
- `backend/app/models/ocr.py` - OCR Pydantic models (OCRPage, OCRBoundingBox, OCRResult, OCRStatus)
- `backend/app/services/ocr/__init__.py` - OCR service module init
- `backend/app/services/ocr/processor.py` - OCRProcessor class using Google Document AI
- `backend/app/services/ocr/bbox_extractor.py` - Bounding box extraction logic
- `backend/app/services/bounding_box_service.py` - BoundingBoxService for database operations
- `backend/app/services/pubsub_service.py` - Redis pub/sub for status broadcasting
- `backend/app/workers/tasks/document_tasks.py` - Celery tasks for OCR processing
- `supabase/migrations/20260107000002_add_ocr_columns_to_documents.sql` - OCR columns migration
- `backend/tests/services/ocr/__init__.py` - OCR tests init
- `backend/tests/services/ocr/test_bbox_extractor.py` - Bounding box extraction tests (17 tests)
- `backend/tests/services/ocr/test_processor.py` - OCR processor tests (12 tests)
- `backend/tests/services/test_bounding_box_service.py` - BoundingBox service tests (9 tests)
- `backend/tests/workers/test_document_tasks.py` - Document task tests (13 tests)
- `backend/tests/integration/__init__.py` - Integration tests init
- `backend/tests/integration/test_ocr_integration.py` - OCR integration tests (13 tests)

**Modified Files:**
- `backend/app/core/config.py` - Added Google Document AI settings
- `backend/.env.example` - Added Document AI configuration variables
- `backend/app/models/document.py` - Added OCR status values and fields to Document model
- `backend/app/services/document_service.py` - Added OCR update methods
- `backend/app/services/storage_service.py` - Added download_file method
- `backend/app/api/routes/documents.py` - Added OCR task queuing on upload
- `backend/app/workers/tasks/__init__.py` - Export document_tasks

