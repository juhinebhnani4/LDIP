"""Tests for PDFChunker service.

Story 16.2: Implement PDFChunker Service
"""

from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from app.services.pdf_chunker import (
    CHUNK_THRESHOLD,
    DEFAULT_CHUNK_SIZE,
    PDFChunker,
    PDFChunkerError,
    get_pdf_chunker,
)


@pytest.fixture
def create_pdf():
    """Factory to create test PDFs with specified page count."""

    def _create(page_count: int) -> bytes:
        writer = PdfWriter()
        for i in range(page_count):
            # Add page number text for debugging
            writer.add_blank_page(width=612, height=792)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    return _create


class TestShouldChunk:
    """Tests for should_chunk method."""

    def test_small_pdf_no_chunk(self):
        """PDFs with <=30 pages should not be chunked."""
        chunker = PDFChunker()
        assert chunker.should_chunk(1) is False
        assert chunker.should_chunk(10) is False
        assert chunker.should_chunk(30) is False

    def test_large_pdf_should_chunk(self):
        """PDFs with >30 pages should be chunked."""
        chunker = PDFChunker()
        assert chunker.should_chunk(31) is True
        assert chunker.should_chunk(50) is True
        assert chunker.should_chunk(100) is True
        assert chunker.should_chunk(422) is True

    def test_boundary_value(self):
        """Boundary at 30 uses sync, 31 uses chunked."""
        chunker = PDFChunker()
        assert chunker.should_chunk(CHUNK_THRESHOLD) is False
        assert chunker.should_chunk(CHUNK_THRESHOLD + 1) is True


class TestSplitPdf:
    """Tests for split_pdf method."""

    def test_exact_multiple_of_chunk_size(self, create_pdf):
        """50 pages / 25 = 2 chunks exactly."""
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 2
        assert chunks[0][1:] == (1, 25)  # page_start, page_end
        assert chunks[1][1:] == (26, 50)

    def test_partial_last_chunk(self, create_pdf):
        """80 pages / 25 = 3 full + 1 partial."""
        pdf_bytes = create_pdf(80)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 4
        assert chunks[0][1:] == (1, 25)
        assert chunks[1][1:] == (26, 50)
        assert chunks[2][1:] == (51, 75)
        assert chunks[3][1:] == (76, 80)  # Only 5 pages

    def test_75_pages_three_chunks(self, create_pdf):
        """75 pages / 25 = exactly 3 chunks."""
        pdf_bytes = create_pdf(75)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 3
        assert chunks[0][1:] == (1, 25)
        assert chunks[1][1:] == (26, 50)
        assert chunks[2][1:] == (51, 75)

    def test_single_chunk_small_document(self, create_pdf):
        """20 pages fits in one chunk."""
        pdf_bytes = create_pdf(20)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 1
        assert chunks[0][1:] == (1, 20)

    def test_single_page(self, create_pdf):
        """Single page PDF produces one chunk."""
        pdf_bytes = create_pdf(1)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 1
        assert chunks[0][1:] == (1, 1)

    def test_422_page_document(self, create_pdf):
        """422 pages creates 17 chunks (matches original failing document)."""
        pdf_bytes = create_pdf(422)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # 422 / 25 = 16.88 -> 17 chunks
        assert len(chunks) == 17
        assert chunks[0][1:] == (1, 25)
        assert chunks[-1][1:] == (401, 422)  # Last chunk has 22 pages

    def test_chunks_are_valid_pdfs(self, create_pdf):
        """Each chunk is a valid PDF with correct page count."""
        pdf_bytes = create_pdf(75)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        for chunk_bytes, page_start, page_end in chunks:
            # Each chunk should start with PDF magic bytes
            assert chunk_bytes.startswith(b"%PDF-")

            # Verify page count in chunk
            reader = PdfReader(BytesIO(chunk_bytes))
            expected_pages = page_end - page_start + 1
            assert len(reader.pages) == expected_pages

    def test_custom_chunk_size(self, create_pdf):
        """Respects custom chunk size parameter."""
        pdf_bytes = create_pdf(100)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=10)

        assert len(chunks) == 10
        for i, (_, page_start, page_end) in enumerate(chunks):
            expected_start = i * 10 + 1
            expected_end = (i + 1) * 10
            assert page_start == expected_start
            assert page_end == expected_end


class TestPageNumberConvention:
    """Tests for 1-based page numbering."""

    def test_page_numbers_are_one_based(self, create_pdf):
        """Return tuples use 1-based page numbers."""
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # First chunk starts at page 1, not 0
        assert chunks[0][1] == 1
        # Second chunk continues from 26
        assert chunks[1][1] == 26

    def test_page_range_is_inclusive(self, create_pdf):
        """page_end is inclusive (pages 1-25 means 25 pages)."""
        pdf_bytes = create_pdf(25)
        chunker = PDFChunker()

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        _, page_start, page_end = chunks[0]
        assert page_start == 1
        assert page_end == 25
        # Chunk should have exactly 25 pages
        reader = PdfReader(BytesIO(chunks[0][0]))
        assert len(reader.pages) == 25


class TestErrorHandling:
    """Tests for error handling."""

    def test_empty_pdf_raises_error(self):
        """Empty PDF raises EMPTY_PDF error."""
        writer = PdfWriter()
        buffer = BytesIO()
        writer.write(buffer)
        empty_pdf = buffer.getvalue()

        chunker = PDFChunker()

        with pytest.raises(PDFChunkerError) as exc:
            chunker.split_pdf(empty_pdf)
        assert exc.value.code == "EMPTY_PDF"

    def test_invalid_pdf_raises_error(self):
        """Invalid PDF content raises error."""
        chunker = PDFChunker()

        with pytest.raises(PDFChunkerError):
            chunker.split_pdf(b"Not a valid PDF at all")

    def test_corrupted_pdf_raises_error(self):
        """Truncated/corrupted PDF raises error."""
        chunker = PDFChunker()

        # PDF header but truncated
        truncated_pdf = b"%PDF-1.4 corrupted content"

        with pytest.raises(PDFChunkerError):
            chunker.split_pdf(truncated_pdf)


class TestConstants:
    """Tests for configuration constants."""

    def test_default_chunk_size(self):
        """DEFAULT_CHUNK_SIZE is 25 (under Document AI limit of 30)."""
        assert DEFAULT_CHUNK_SIZE == 25

    def test_chunk_threshold(self):
        """CHUNK_THRESHOLD is 30 pages."""
        assert CHUNK_THRESHOLD == 30


class TestGetPdfChunker:
    """Tests for factory function."""

    def test_returns_singleton(self):
        """Factory returns the same instance."""
        get_pdf_chunker.cache_clear()

        chunker1 = get_pdf_chunker()
        chunker2 = get_pdf_chunker()

        assert chunker1 is chunker2

    def test_returns_pdf_chunker_instance(self):
        """Factory returns PDFChunker instance."""
        get_pdf_chunker.cache_clear()

        chunker = get_pdf_chunker()

        assert isinstance(chunker, PDFChunker)
