# Story 18.1: Unit Tests for PDFChunker

Status: ready-for-dev

## Story

As a developer,
I want comprehensive unit tests for PDFChunker,
so that I can be confident the splitting logic is correct.

## Acceptance Criteria

1. **Edge Case Coverage**
   - Test PDFs of various sizes: 10, 30, 31, 50, 100, 422 pages
   - Exact multiple of chunk_size (50 pages / 25 = 2 chunks)
   - One page over (51 pages = 3 chunks with last having 1 page)
   - Single page document
   - Empty PDF raises error

2. **Page Range Validation**
   - page_start and page_end validated for each chunk
   - No pages skipped or duplicated across chunks
   - All page numbers are 1-based

3. **Chunk Validity**
   - Each chunk is a valid PDF bytes object
   - Each chunk can be opened by PyPDF/Document AI
   - Chunk page counts match expected

## Tasks / Subtasks

- [ ] Task 1: Create test fixtures (AC: #1)
  - [ ] Factory for creating test PDFs
  - [ ] Sample PDFs of various sizes
  - [ ] Invalid PDF samples

- [ ] Task 2: Write edge case tests (AC: #1, #2)
  - [ ] Test exact multiples
  - [ ] Test partial last chunk
  - [ ] Test boundary conditions
  - [ ] Test error cases

- [ ] Task 3: Write chunk validity tests (AC: #3)
  - [ ] Verify chunks are valid PDFs
  - [ ] Verify page counts
  - [ ] Verify content integrity

## Dev Notes

### Test Structure

```python
# tests/services/test_pdf_chunker.py
import pytest
from io import BytesIO
from pypdf import PdfReader, PdfWriter

from app.services.pdf_chunker import (
    PDFChunker,
    PDFChunkerError,
    DEFAULT_CHUNK_SIZE,
)


@pytest.fixture
def create_pdf():
    """Factory to create test PDFs with specified page count."""
    def _create(page_count: int, with_content: bool = False) -> bytes:
        writer = PdfWriter()
        for i in range(page_count):
            page = writer.add_blank_page(612, 792)
            if with_content:
                # Add text annotation for content verification
                pass
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    return _create


class TestSplitPdfEdgeCases:
    @pytest.mark.parametrize("pages,expected_chunks", [
        (10, 1),    # Small - single chunk
        (25, 1),    # Exact chunk size
        (30, 2),    # At threshold
        (31, 2),    # Just over threshold
        (50, 2),    # Exact multiple
        (51, 3),    # One over multiple
        (75, 3),    # 3 full chunks
        (100, 4),   # 4 chunks
        (422, 17),  # Original failing doc
    ])
    def test_chunk_count_for_various_sizes(self, create_pdf, pages, expected_chunks):
        pdf_bytes = create_pdf(pages)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == expected_chunks

    def test_single_page_creates_single_chunk(self, create_pdf):
        pdf_bytes = create_pdf(1)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes)

        assert len(chunks) == 1
        assert chunks[0][1:] == (1, 1)  # page_start, page_end

    def test_empty_pdf_raises_error(self, create_pdf):
        pdf_bytes = create_pdf(0)
        chunker = PDFChunker()

        with pytest.raises(PDFChunkerError) as exc:
            chunker.split_pdf(pdf_bytes)
        assert exc.value.code == "EMPTY_PDF"


class TestPageRangeValidation:
    def test_no_pages_skipped(self, create_pdf):
        pdf_bytes = create_pdf(100)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # Verify continuous page ranges
        all_pages = []
        for _, page_start, page_end in chunks:
            all_pages.extend(range(page_start, page_end + 1))

        assert all_pages == list(range(1, 101))

    def test_no_pages_duplicated(self, create_pdf):
        pdf_bytes = create_pdf(100)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        all_pages = []
        for _, page_start, page_end in chunks:
            all_pages.extend(range(page_start, page_end + 1))

        assert len(all_pages) == len(set(all_pages))

    def test_page_numbers_are_one_based(self, create_pdf):
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # First chunk starts at 1, not 0
        assert chunks[0][1] == 1
        # Last chunk ends at total pages
        assert chunks[-1][2] == 50


class TestChunkValidity:
    def test_chunks_are_valid_pdfs(self, create_pdf):
        pdf_bytes = create_pdf(75)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        for chunk_bytes, page_start, page_end in chunks:
            # Should not raise
            reader = PdfReader(BytesIO(chunk_bytes))
            expected_pages = page_end - page_start + 1
            assert len(reader.pages) == expected_pages

    def test_chunks_start_with_pdf_magic_bytes(self, create_pdf):
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes)

        for chunk_bytes, _, _ in chunks:
            assert chunk_bytes.startswith(b"%PDF-")


class TestErrorHandling:
    def test_invalid_pdf_raises_error(self):
        chunker = PDFChunker()

        with pytest.raises(PDFChunkerError):
            chunker.split_pdf(b"Not a valid PDF")

    def test_corrupted_pdf_raises_error(self):
        chunker = PDFChunker()

        # PDF header but corrupted content
        corrupted = b"%PDF-1.4\ngarbage content"
        with pytest.raises(PDFChunkerError):
            chunker.split_pdf(corrupted)
```

### References

- [Source: epic-4-testing-validation.md#Story 4.1] - Full AC
- [Source: Story 16.2] - PDFChunker implementation

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

