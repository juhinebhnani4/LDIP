# Story 16.1: Implement PDF Page Count Detection and Routing

Status: ready-for-dev

## Story

As a system processing uploaded documents,
I want to detect PDF page count and route to the appropriate processing path,
so that small documents use fast sync processing and large documents use chunked processing.

## Acceptance Criteria

1. **Page Count Detection**
   - PDF page count read from file without loading full content into memory
   - Uses PyPDF2 or pikepdf for lightweight page counting
   - Returns page count before any OCR processing begins

2. **Routing Decision (<=30 pages)**
   - PDFs with 30 or fewer pages processed using existing sync Document AI call
   - No chunk records created for small documents
   - Existing `process_document` flow unchanged for small PDFs

3. **Routing Decision (>30 pages)**
   - PDFs with more than 30 pages routed to chunked processing path
   - Chunk records created BEFORE processing begins (via OCRChunkService)
   - Processing continues via parallel chunk pipeline (Story 16.4)

4. **Malicious PDF Defense (RED TEAM)**
   - Validates actual page count vs claimed count in PDF header
   - Maximum page limit of 10,000 enforced to prevent resource exhaustion
   - Suspicious discrepancies logged for security monitoring
   - Malformed PDFs handled gracefully with clear error messages

## Tasks / Subtasks

- [ ] Task 1: Create PDFRouter service (AC: #1, #2, #3)
  - [ ] Create `backend/app/services/pdf_router.py`
  - [ ] Implement `get_page_count(pdf_bytes)` - memory-efficient counting
  - [ ] Implement `should_use_chunked_processing(page_count)` - routing decision
  - [ ] Define `PAGE_COUNT_THRESHOLD = 30` constant
  - [ ] Define `MAX_PAGE_COUNT = 10000` constant

- [ ] Task 2: Implement malicious PDF validation (AC: #4)
  - [ ] Validate PDF magic bytes before parsing
  - [ ] Compare claimed vs actual page count
  - [ ] Enforce MAX_PAGE_COUNT limit
  - [ ] Log security warnings for suspicious PDFs
  - [ ] Raise `MaliciousPDFError` for violations

- [ ] Task 3: Integrate routing into document_tasks.py (AC: #2, #3)
  - [ ] Add routing decision at start of `process_document` task
  - [ ] For small PDFs: continue existing flow
  - [ ] For large PDFs: create chunk records, dispatch to parallel pipeline
  - [ ] Update document status appropriately for each path

- [ ] Task 4: Create chunk records for large documents (AC: #3)
  - [ ] Calculate chunk boundaries (25 pages per chunk)
  - [ ] Use `OCRChunkService.create_chunks_for_document()` batch create
  - [ ] Store chunk specs before processing begins

- [ ] Task 5: Write tests (AC: #1-4)
  - [ ] Create `backend/tests/services/test_pdf_router.py`
  - [ ] Test page count detection accuracy
  - [ ] Test routing threshold (30 pages)
  - [ ] Test malicious PDF detection (fake header)
  - [ ] Test MAX_PAGE_COUNT enforcement

## Dev Notes

### Architecture Compliance

**PDFRouter Service Pattern:**
```python
# backend/app/services/pdf_router.py
import structlog
from functools import lru_cache
from io import BytesIO

import pypdf

logger = structlog.get_logger(__name__)

# Routing thresholds
PAGE_COUNT_THRESHOLD = 30  # Documents > 30 pages use chunked processing
MAX_PAGE_COUNT = 10000  # Security limit
CHUNK_SIZE = 25  # Pages per chunk


class PDFRouterError(Exception):
    """Base exception for PDF routing errors."""
    def __init__(self, message: str, code: str = "PDF_ROUTER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class MaliciousPDFError(PDFRouterError):
    """Raised when PDF appears malicious or malformed."""
    def __init__(self, message: str):
        super().__init__(message, code="MALICIOUS_PDF_DETECTED")


class PDFRouter:
    """Service for PDF page count detection and routing decisions.

    Determines whether a PDF should use sync processing (<=30 pages)
    or chunked parallel processing (>30 pages).
    """

    def get_page_count(self, pdf_bytes: bytes) -> int:
        """Get PDF page count without loading full content.

        Args:
            pdf_bytes: PDF file content.

        Returns:
            Number of pages in the PDF.

        Raises:
            PDFRouterError: If PDF cannot be parsed.
            MaliciousPDFError: If PDF appears malicious.
        """
        self._validate_pdf_magic_bytes(pdf_bytes)

        try:
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            claimed_count = len(reader.pages)

            # Validate count is reasonable
            if claimed_count > MAX_PAGE_COUNT:
                logger.warning(
                    "pdf_page_count_exceeded_max",
                    claimed_count=claimed_count,
                    max_allowed=MAX_PAGE_COUNT,
                )
                raise MaliciousPDFError(
                    f"PDF claims {claimed_count} pages, exceeds max {MAX_PAGE_COUNT}"
                )

            # Validate by actually enumerating pages (defense against header spoofing)
            actual_count = self._count_actual_pages(reader, claimed_count)

            if actual_count != claimed_count:
                logger.warning(
                    "pdf_page_count_mismatch",
                    claimed=claimed_count,
                    actual=actual_count,
                )

            return actual_count

        except pypdf.errors.PdfReadError as e:
            logger.error("pdf_parse_failed", error=str(e))
            raise PDFRouterError(f"Failed to parse PDF: {e}")

    def _validate_pdf_magic_bytes(self, pdf_bytes: bytes) -> None:
        """Validate PDF starts with correct magic bytes."""
        if not pdf_bytes.startswith(b"%PDF-"):
            raise PDFRouterError(
                "File does not appear to be a valid PDF",
                code="INVALID_PDF_FORMAT",
            )

    def _count_actual_pages(
        self,
        reader: pypdf.PdfReader,
        claimed_count: int,
    ) -> int:
        """Count actual pages by enumeration (limited for performance).

        For performance, only fully validates if claimed count is suspicious.
        """
        # For reasonable claims, trust the count
        if claimed_count <= MAX_PAGE_COUNT:
            # Spot check: verify first and last page exist
            try:
                _ = reader.pages[0]
                if claimed_count > 1:
                    _ = reader.pages[claimed_count - 1]
                return claimed_count
            except IndexError:
                pass  # Fall through to full count

        # Full enumeration for suspicious cases
        actual = 0
        for _ in reader.pages:
            actual += 1
            if actual > MAX_PAGE_COUNT:
                break
        return actual

    def should_use_chunked_processing(self, page_count: int) -> bool:
        """Determine if PDF should use chunked processing.

        Args:
            page_count: Number of pages in PDF.

        Returns:
            True if PDF should be chunked, False for sync processing.
        """
        return page_count > PAGE_COUNT_THRESHOLD

    def calculate_chunk_specs(
        self,
        total_pages: int,
        chunk_size: int = CHUNK_SIZE,
    ) -> list[dict]:
        """Calculate chunk boundaries for a document.

        Args:
            total_pages: Total pages in document.
            chunk_size: Pages per chunk (default 25).

        Returns:
            List of chunk specs: [{"chunk_index": 0, "page_start": 1, "page_end": 25}, ...]
        """
        chunks = []
        chunk_index = 0
        page_start = 1

        while page_start <= total_pages:
            page_end = min(page_start + chunk_size - 1, total_pages)
            chunks.append({
                "chunk_index": chunk_index,
                "page_start": page_start,
                "page_end": page_end,
            })
            chunk_index += 1
            page_start = page_end + 1

        return chunks


@lru_cache(maxsize=1)
def get_pdf_router() -> PDFRouter:
    """Get singleton PDFRouter instance."""
    return PDFRouter()
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    services/
      pdf_router.py          # NEW - Routing service
    workers/
      tasks/
        document_tasks.py    # Modify - Add routing
  tests/
    services/
      test_pdf_router.py     # NEW - Tests
```

**Related Files:**
- [document_tasks.py](../../backend/app/workers/tasks/document_tasks.py) - Integration point
- [OCRChunkService](../../backend/app/services/ocr_chunk_service.py) - Create chunk records
- [OCRProcessor](../../backend/app/services/ocr) - Existing OCR service

### Technical Requirements

**Dependencies:**
```python
# pyproject.toml or requirements.txt
pypdf>=3.0.0  # Lightweight PDF library for page counting
```

**Integration in document_tasks.py:**
```python
from app.services.pdf_router import (
    PDFRouter,
    get_pdf_router,
    PAGE_COUNT_THRESHOLD,
)
from app.services.ocr_chunk_service import get_ocr_chunk_service

@celery_app.task(bind=True, name="process_document")
def process_document(
    self,
    document_id: str,
    matter_id: str,
    file_path: str,
) -> dict:
    """Process a document through OCR pipeline."""
    # Get PDF content
    storage = get_storage_service()
    pdf_bytes = storage.download(file_path)

    # Route based on page count
    router = get_pdf_router()
    page_count = router.get_page_count(pdf_bytes)

    if router.should_use_chunked_processing(page_count):
        # Large document: create chunks and dispatch parallel processing
        return _process_large_document(
            self,
            document_id=document_id,
            matter_id=matter_id,
            pdf_bytes=pdf_bytes,
            page_count=page_count,
        )
    else:
        # Small document: existing sync processing
        return _process_small_document(
            self,
            document_id=document_id,
            matter_id=matter_id,
            pdf_bytes=pdf_bytes,
        )


def _process_large_document(
    task,
    document_id: str,
    matter_id: str,
    pdf_bytes: bytes,
    page_count: int,
) -> dict:
    """Route large documents to chunked processing pipeline."""
    router = get_pdf_router()
    chunk_service = get_ocr_chunk_service()

    # Calculate chunk boundaries
    chunk_specs = router.calculate_chunk_specs(page_count)

    # Create chunk records in database
    _run_async(
        chunk_service.create_chunks_for_document(
            document_id=document_id,
            matter_id=matter_id,
            chunk_specs=chunk_specs,
        )
    )

    logger.info(
        "large_document_routed_to_chunked",
        document_id=document_id,
        page_count=page_count,
        chunk_count=len(chunk_specs),
    )

    # Dispatch to parallel processing (Story 16.4)
    # process_document_chunked.delay(document_id, matter_id, pdf_bytes)
    ...
```

### Testing Requirements

**Test Cases:**
```python
# tests/services/test_pdf_router.py
import pytest
from io import BytesIO
from unittest.mock import MagicMock, patch

from app.services.pdf_router import (
    PDFRouter,
    PDFRouterError,
    MaliciousPDFError,
    PAGE_COUNT_THRESHOLD,
    MAX_PAGE_COUNT,
    CHUNK_SIZE,
)


class TestGetPageCount:
    def test_counts_pages_correctly(self, sample_10_page_pdf):
        router = PDFRouter()
        count = router.get_page_count(sample_10_page_pdf)
        assert count == 10

    def test_rejects_non_pdf(self):
        router = PDFRouter()
        with pytest.raises(PDFRouterError) as exc:
            router.get_page_count(b"Not a PDF file")
        assert exc.value.code == "INVALID_PDF_FORMAT"

    def test_enforces_max_page_limit(self):
        # Mock PDF claiming excessive pages
        router = PDFRouter()
        with patch.object(router, "_count_actual_pages", return_value=MAX_PAGE_COUNT + 1):
            with pytest.raises(MaliciousPDFError):
                # Would need mock PDF with spoofed header
                pass


class TestShouldUseChunkedProcessing:
    def test_small_document_uses_sync(self):
        router = PDFRouter()
        assert router.should_use_chunked_processing(10) is False
        assert router.should_use_chunked_processing(30) is False

    def test_large_document_uses_chunked(self):
        router = PDFRouter()
        assert router.should_use_chunked_processing(31) is True
        assert router.should_use_chunked_processing(100) is True
        assert router.should_use_chunked_processing(422) is True


class TestCalculateChunkSpecs:
    def test_exact_multiple(self):
        router = PDFRouter()
        specs = router.calculate_chunk_specs(50, chunk_size=25)

        assert len(specs) == 2
        assert specs[0] == {"chunk_index": 0, "page_start": 1, "page_end": 25}
        assert specs[1] == {"chunk_index": 1, "page_start": 26, "page_end": 50}

    def test_partial_last_chunk(self):
        router = PDFRouter()
        specs = router.calculate_chunk_specs(75, chunk_size=25)

        assert len(specs) == 3
        assert specs[2] == {"chunk_index": 2, "page_start": 51, "page_end": 75}

    def test_single_chunk(self):
        router = PDFRouter()
        specs = router.calculate_chunk_specs(20, chunk_size=25)

        assert len(specs) == 1
        assert specs[0] == {"chunk_index": 0, "page_start": 1, "page_end": 20}

    def test_422_page_document(self):
        router = PDFRouter()
        specs = router.calculate_chunk_specs(422, chunk_size=25)

        assert len(specs) == 17  # 422 / 25 = 16.88 -> 17 chunks
        assert specs[0]["page_start"] == 1
        assert specs[-1]["page_end"] == 422


@pytest.fixture
def sample_10_page_pdf():
    """Create a minimal 10-page PDF for testing."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(10):
        writer.add_blank_page(width=612, height=792)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
```

### References

- [Source: epic-2-pdf-chunking-parallel-processing.md#Story 2.1] - Full AC
- [Source: project-context.md#Backend] - Python patterns
- [Source: document_tasks.py] - Existing OCR pipeline

### Previous Story Intelligence

**From Epic 2B (OCR Pipeline):**
- Existing `process_document` task handles small PDFs
- PDF magic bytes validation exists: `PDF_MAGIC_BYTES = b"%PDF-"`
- Use `_run_async()` helper for async in Celery

**From Story 15.2:**
- `OCRChunkService.create_chunks_for_document()` for batch chunk creation
- Chunk specs include: chunk_index, page_start, page_end

### Critical Implementation Notes

**DO NOT:**
- Load entire PDF into memory for page counting
- Skip validation of PDF magic bytes
- Allow page counts > 10,000 (denial of service risk)
- Modify existing sync processing for small documents

**MUST:**
- Use pypdf for lightweight page counting
- Validate PDF before processing
- Create chunk records BEFORE dispatching parallel processing
- Log routing decisions with page_count for debugging
- Handle malformed PDFs gracefully with clear errors

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

