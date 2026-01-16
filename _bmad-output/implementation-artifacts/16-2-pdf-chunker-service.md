# Story 16.2: Implement PDFChunker Service

Status: ready-for-dev

## Story

As a backend developer,
I want a service to split large PDFs into processable chunks,
so that each chunk can be sent to Document AI within the 30-page limit.

## Acceptance Criteria

1. **Split PDF into Chunks**
   - Given 75 pages and chunk_size=25: returns 3 chunks (1-25, 26-50, 51-75)
   - Given 80 pages and chunk_size=25: returns 4 chunks (1-25, 26-50, 51-75, 76-80)
   - Each chunk is a valid PDF bytes object
   - Chunk tuples contain: (chunk_bytes, page_start, page_end) with 1-based page numbers

2. **Should Chunk Decision**
   - `should_chunk(page_count)` returns False for page_count <= 30
   - `should_chunk(page_count)` returns True for page_count > 30

3. **PDF Library Selection (SHARK TANK)**
   - Evaluate PyPDF2, pikepdf, and pymupdf for memory efficiency
   - Document selection rationale in code comments
   - Handle malformed PDFs gracefully

4. **PDF Sandbox (RED TEAM)**
   - Parsing occurs with resource limits
   - Timeout kills parsing if exceeds 30 seconds
   - Malformed PDFs that crash parser handled gracefully

## Tasks / Subtasks

- [ ] Task 1: Create PDFChunker service (AC: #1, #2)
  - [ ] Create `backend/app/services/pdf_chunker.py`
  - [ ] Implement `split_pdf(pdf_bytes, chunk_size=25)` method
  - [ ] Implement `should_chunk(page_count)` method
  - [ ] Return list of (chunk_bytes, page_start, page_end) tuples

- [ ] Task 2: Implement memory-efficient splitting (AC: #1, #3)
  - [ ] Use pypdf for PDF manipulation
  - [ ] Extract page ranges without loading entire document
  - [ ] Write chunks to BytesIO, not temp files
  - [ ] Document library choice rationale

- [ ] Task 3: Implement safety measures (AC: #4)
  - [ ] Add timeout wrapper for split operations
  - [ ] Handle pypdf exceptions gracefully
  - [ ] Log parsing errors with context
  - [ ] Raise `PDFChunkerError` for failures

- [ ] Task 4: Write tests (AC: #1-4)
  - [ ] Create `backend/tests/services/test_pdf_chunker.py`
  - [ ] Test exact multiples (50 pages / 25 = 2 chunks)
  - [ ] Test partial last chunk (51 pages = 3 chunks)
  - [ ] Test single page document
  - [ ] Test empty PDF error handling
  - [ ] Test 1-based page numbering in tuples

## Dev Notes

### Architecture Compliance

**PDFChunker Service Pattern:**
```python
# backend/app/services/pdf_chunker.py
"""PDF Chunker Service for splitting large PDFs.

Library Selection Rationale:
- pypdf chosen over pikepdf (C library, harder to deploy) and pymupdf (GPL license)
- pypdf is pure Python, well-maintained, good memory efficiency for page extraction
- Supports streaming page extraction without loading entire PDF
"""

import signal
from functools import lru_cache
from io import BytesIO

import structlog
import pypdf

logger = structlog.get_logger(__name__)

# Configuration
DEFAULT_CHUNK_SIZE = 25  # Pages per chunk (Document AI limit is 30)
CHUNK_THRESHOLD = 30  # Documents > 30 pages use chunking
SPLIT_TIMEOUT_SECONDS = 30  # Max time for split operation


class PDFChunkerError(Exception):
    """Base exception for PDF chunker operations."""
    def __init__(self, message: str, code: str = "PDF_CHUNKER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class PDFChunker:
    """Service for splitting large PDFs into processable chunks.

    Each chunk stays within Document AI's 30-page limit while
    maintaining valid PDF structure for OCR processing.
    """

    def should_chunk(self, page_count: int) -> bool:
        """Determine if PDF should be split into chunks.

        Args:
            page_count: Total pages in PDF.

        Returns:
            True if page_count > 30, False otherwise.
        """
        return page_count > CHUNK_THRESHOLD

    def split_pdf(
        self,
        pdf_bytes: bytes,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> list[tuple[bytes, int, int]]:
        """Split PDF into chunks of specified size.

        Args:
            pdf_bytes: Source PDF content.
            chunk_size: Maximum pages per chunk (default 25).

        Returns:
            List of tuples: (chunk_bytes, page_start, page_end)
            where page numbers are 1-based.

        Raises:
            PDFChunkerError: If splitting fails.

        Example:
            >>> chunker = PDFChunker()
            >>> chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)
            >>> # For 75-page PDF:
            >>> # [(chunk1_bytes, 1, 25), (chunk2_bytes, 26, 50), (chunk3_bytes, 51, 75)]
        """
        try:
            reader = pypdf.PdfReader(BytesIO(pdf_bytes))
            total_pages = len(reader.pages)

            if total_pages == 0:
                raise PDFChunkerError("PDF has no pages", code="EMPTY_PDF")

            chunks = []
            page_start = 1  # 1-based page numbering

            while page_start <= total_pages:
                page_end = min(page_start + chunk_size - 1, total_pages)

                chunk_bytes = self._extract_page_range(
                    reader,
                    page_start - 1,  # Convert to 0-based for pypdf
                    page_end - 1,
                )

                chunks.append((chunk_bytes, page_start, page_end))

                logger.debug(
                    "chunk_extracted",
                    page_start=page_start,
                    page_end=page_end,
                    chunk_size_bytes=len(chunk_bytes),
                )

                page_start = page_end + 1

            logger.info(
                "pdf_split_complete",
                total_pages=total_pages,
                chunk_count=len(chunks),
                chunk_size=chunk_size,
            )

            return chunks

        except pypdf.errors.PdfReadError as e:
            logger.error("pdf_parse_failed", error=str(e))
            raise PDFChunkerError(f"Failed to parse PDF: {e}", code="PDF_PARSE_ERROR")
        except Exception as e:
            logger.error("pdf_split_failed", error=str(e))
            raise PDFChunkerError(f"Failed to split PDF: {e}")

    def _extract_page_range(
        self,
        reader: pypdf.PdfReader,
        start_index: int,
        end_index: int,
    ) -> bytes:
        """Extract a range of pages as a new PDF.

        Args:
            reader: Source PDF reader.
            start_index: Start page index (0-based).
            end_index: End page index (0-based, inclusive).

        Returns:
            PDF bytes containing only the specified pages.
        """
        writer = pypdf.PdfWriter()

        for page_index in range(start_index, end_index + 1):
            writer.add_page(reader.pages[page_index])

        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def split_pdf_with_timeout(
        self,
        pdf_bytes: bytes,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        timeout_seconds: int = SPLIT_TIMEOUT_SECONDS,
    ) -> list[tuple[bytes, int, int]]:
        """Split PDF with timeout protection.

        Args:
            pdf_bytes: Source PDF content.
            chunk_size: Maximum pages per chunk.
            timeout_seconds: Max time allowed for operation.

        Returns:
            List of chunk tuples.

        Raises:
            PDFChunkerError: If operation times out or fails.
        """
        def timeout_handler(signum, frame):
            raise PDFChunkerError(
                f"PDF split timed out after {timeout_seconds}s",
                code="SPLIT_TIMEOUT",
            )

        # Set up timeout (Unix only - on Windows, use threading)
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)

        try:
            return self.split_pdf(pdf_bytes, chunk_size)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


@lru_cache(maxsize=1)
def get_pdf_chunker() -> PDFChunker:
    """Get singleton PDFChunker instance."""
    return PDFChunker()
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    services/
      pdf_chunker.py         # NEW - Chunker service
  tests/
    services/
      test_pdf_chunker.py    # NEW - Tests
```

**Related Files:**
- [PDFRouter](../../backend/app/services/pdf_router.py) - Uses chunker (Story 16.1)
- [document_tasks.py](../../backend/app/workers/tasks/document_tasks.py) - Integration point

### Technical Requirements

**Dependencies:**
```python
# Already in project from Story 16.1
pypdf>=3.0.0
```

**Memory Efficiency Notes:**
```python
# pypdf loads pages lazily - only the pages being extracted
# are fully loaded into memory at any time

# For a 100MB PDF with 500 pages:
# - Each 25-page chunk extracts ~5MB at a time
# - Peak memory should stay under 50MB (see Story 17.1)
```

**Page Number Convention:**
```
API uses 1-based page numbers (matches PDF viewer, user expectations)
pypdf uses 0-based indices internally

Conversion:
- User-facing page_start/page_end: 1-based
- pypdf reader.pages[index]: 0-based
- page_start=1, page_end=25 -> indices 0-24
```

### Testing Requirements

**Test Cases:**
```python
# tests/services/test_pdf_chunker.py
import pytest
from io import BytesIO

from pypdf import PdfWriter

from app.services.pdf_chunker import (
    PDFChunker,
    PDFChunkerError,
    DEFAULT_CHUNK_SIZE,
    CHUNK_THRESHOLD,
)


@pytest.fixture
def create_pdf():
    """Factory to create test PDFs with specified page count."""
    def _create(page_count: int) -> bytes:
        writer = PdfWriter()
        for _ in range(page_count):
            writer.add_blank_page(width=612, height=792)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    return _create


class TestShouldChunk:
    def test_small_pdf_no_chunk(self):
        chunker = PDFChunker()
        assert chunker.should_chunk(10) is False
        assert chunker.should_chunk(30) is False

    def test_large_pdf_should_chunk(self):
        chunker = PDFChunker()
        assert chunker.should_chunk(31) is True
        assert chunker.should_chunk(100) is True


class TestSplitPdf:
    def test_exact_multiple_of_chunk_size(self, create_pdf):
        # 50 pages / 25 = 2 chunks exactly
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 2
        assert chunks[0][1:] == (1, 25)   # page_start, page_end
        assert chunks[1][1:] == (26, 50)

    def test_partial_last_chunk(self, create_pdf):
        # 80 pages / 25 = 3 full + 1 partial
        pdf_bytes = create_pdf(80)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 4
        assert chunks[0][1:] == (1, 25)
        assert chunks[1][1:] == (26, 50)
        assert chunks[2][1:] == (51, 75)
        assert chunks[3][1:] == (76, 80)  # Only 5 pages

    def test_single_chunk(self, create_pdf):
        # 20 pages fits in one chunk
        pdf_bytes = create_pdf(20)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 1
        assert chunks[0][1:] == (1, 20)

    def test_single_page(self, create_pdf):
        pdf_bytes = create_pdf(1)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 1
        assert chunks[0][1:] == (1, 1)

    def test_422_page_document(self, create_pdf):
        # Matches the original failing document
        pdf_bytes = create_pdf(422)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # 422 / 25 = 16.88 -> 17 chunks
        assert len(chunks) == 17
        assert chunks[0][1:] == (1, 25)
        assert chunks[-1][1:] == (401, 422)  # Last chunk has 22 pages

    def test_empty_pdf_raises_error(self, create_pdf):
        pdf_bytes = create_pdf(0)
        chunker = PDFChunker()

        with pytest.raises(PDFChunkerError) as exc:
            chunker.split_pdf(pdf_bytes)
        assert exc.value.code == "EMPTY_PDF"

    def test_invalid_pdf_raises_error(self):
        chunker = PDFChunker()

        with pytest.raises(PDFChunkerError) as exc:
            chunker.split_pdf(b"Not a valid PDF")
        assert "PDF_PARSE_ERROR" in exc.value.code or "PDF_CHUNKER_ERROR" in exc.value.code

    def test_chunks_are_valid_pdfs(self, create_pdf):
        pdf_bytes = create_pdf(75)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # Each chunk should be a valid PDF
        for chunk_bytes, page_start, page_end in chunks:
            assert chunk_bytes.startswith(b"%PDF-")
            # Verify page count in chunk
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(chunk_bytes))
            expected_pages = page_end - page_start + 1
            assert len(reader.pages) == expected_pages


class TestPageNumberConvention:
    def test_page_numbers_are_one_based(self, create_pdf):
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # First chunk starts at page 1, not 0
        assert chunks[0][1] == 1
        # Second chunk continues from 26
        assert chunks[1][1] == 26
```

### References

- [Source: epic-2-pdf-chunking-parallel-processing.md#Story 2.2] - Full AC
- [Source: project-context.md#Backend] - Python patterns
- [Source: Story 16.1] - Depends on PDFRouter

### Previous Story Intelligence

**From Story 16.1 (PDF Router):**
- pypdf already chosen as PDF library
- Page count threshold is 30
- Chunk size is 25 pages (conservative margin under 30)

### Critical Implementation Notes

**DO NOT:**
- Use 0-based page numbers in return tuples (confusing for users)
- Load entire PDF into memory before splitting
- Ignore timeout for malformed PDFs
- Use synchronous file I/O for temp files

**MUST:**
- Return 1-based page numbers in tuples
- Use BytesIO for memory efficiency
- Handle empty PDFs explicitly
- Validate each chunk is a valid PDF
- Log chunk extraction progress
- Document pypdf usage patterns in code

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

