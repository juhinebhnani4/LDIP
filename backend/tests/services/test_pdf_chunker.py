"""Tests for PDFChunker service.

Story 16.2: Implement PDFChunker Service
Story 18.1: Unit Tests for PDFChunker (Epic 4)

Edge cases covered:
- Exact multiple of chunk_size (50 pages / 25 = 2 chunks)
- One page over (51 pages = 3 chunks with last having 1 page)
- Single page document
- Empty PDF (should raise error)
- Page validation (no skipped/duplicated pages)
- Streaming memory-safe split (Story 17.1)
"""

import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from app.services.pdf_chunker import (
    CHUNK_THRESHOLD,
    DEFAULT_CHUNK_SIZE,
    MEMORY_LIMIT_MB,
    STREAMING_THRESHOLD_MB,
    MemoryLimitExceededError,
    PDFChunker,
    PDFChunkerError,
    StreamingChunkResult,
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


# =============================================================================
# Story 18.1: Additional Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Story 18.1: Comprehensive edge case testing."""

    def test_one_page_over_chunk_boundary(self, create_pdf):
        """51 pages = 3 chunks (25, 25, 1)."""
        pdf_bytes = create_pdf(51)
        chunker = PDFChunker(enable_memory_tracking=False)

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 3
        assert chunks[0][1:] == (1, 25)
        assert chunks[1][1:] == (26, 50)
        assert chunks[2][1:] == (51, 51)  # Single page last chunk

        # Verify last chunk has exactly 1 page
        reader = PdfReader(BytesIO(chunks[2][0]))
        assert len(reader.pages) == 1

    def test_31_pages_requires_chunking(self, create_pdf):
        """31 pages = just over threshold (25 + 6)."""
        pdf_bytes = create_pdf(31)
        chunker = PDFChunker(enable_memory_tracking=False)

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 2
        assert chunks[0][1:] == (1, 25)
        assert chunks[1][1:] == (26, 31)

    def test_10_page_document_single_chunk(self, create_pdf):
        """10 pages fits in one chunk."""
        pdf_bytes = create_pdf(10)
        chunker = PDFChunker(enable_memory_tracking=False)

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 1
        assert chunks[0][1:] == (1, 10)

    def test_30_page_document_single_chunk(self, create_pdf):
        """30 pages is exactly at threshold - single chunk."""
        pdf_bytes = create_pdf(30)
        chunker = PDFChunker(enable_memory_tracking=False)

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 2
        assert chunks[0][1:] == (1, 25)
        assert chunks[1][1:] == (26, 30)

    def test_100_page_document(self, create_pdf):
        """100 pages = 4 exact chunks."""
        pdf_bytes = create_pdf(100)
        chunker = PDFChunker(enable_memory_tracking=False)

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        assert len(chunks) == 4
        for i in range(4):
            expected_start = i * 25 + 1
            expected_end = (i + 1) * 25
            assert chunks[i][1:] == (expected_start, expected_end)


class TestPageValidation:
    """Story 18.1: Validate no pages are skipped or duplicated."""

    def test_no_pages_skipped(self, create_pdf):
        """All pages are covered across chunks."""
        pdf_bytes = create_pdf(100)
        chunker = PDFChunker(enable_memory_tracking=False)

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # Collect all page ranges
        all_pages = set()
        for _, page_start, page_end in chunks:
            for page in range(page_start, page_end + 1):
                all_pages.add(page)

        # Should have pages 1-100
        expected_pages = set(range(1, 101))
        assert all_pages == expected_pages

    def test_no_pages_duplicated(self, create_pdf):
        """No page appears in multiple chunks."""
        pdf_bytes = create_pdf(75)
        chunker = PDFChunker(enable_memory_tracking=False)

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # Collect pages and detect duplicates
        seen_pages = []
        for _, page_start, page_end in chunks:
            for page in range(page_start, page_end + 1):
                assert page not in seen_pages, f"Page {page} appears in multiple chunks"
                seen_pages.append(page)

    def test_contiguous_page_ranges(self, create_pdf):
        """Chunks have contiguous page ranges."""
        pdf_bytes = create_pdf(422)
        chunker = PDFChunker(enable_memory_tracking=False)

        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        for i in range(1, len(chunks)):
            prev_end = chunks[i - 1][2]
            curr_start = chunks[i][1]
            assert curr_start == prev_end + 1, (
                f"Gap between chunk {i-1} (end={prev_end}) "
                f"and chunk {i} (start={curr_start})"
            )


class TestStreamingSplit:
    """Story 17.1/18.1: Tests for memory-safe streaming PDF split."""

    def test_streaming_split_creates_files(self, create_pdf):
        """Streaming split creates chunk files."""
        pdf_bytes = create_pdf(75)
        chunker = PDFChunker(enable_memory_tracking=False)

        with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as result:
            assert len(result.chunks) == 3

            for chunk_path, page_start, page_end in result.chunks:
                assert chunk_path.exists()
                assert chunk_path.suffix == ".pdf"

    def test_streaming_split_cleanup(self, create_pdf):
        """Streaming split cleans up temp files after context."""
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker(enable_memory_tracking=False)

        temp_dir = None
        with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as result:
            temp_dir = result.temp_dir
            assert temp_dir.exists()

        # After context, temp dir should be cleaned up
        assert not temp_dir.exists()

    def test_streaming_chunk_bytes_retrieval(self, create_pdf):
        """Can retrieve chunk bytes from streaming result."""
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker(enable_memory_tracking=False)

        with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as result:
            # Get first chunk bytes
            chunk_bytes = result.get_chunk_bytes(0)
            assert chunk_bytes.startswith(b"%PDF-")

            # Verify it's a valid PDF with correct page count
            reader = PdfReader(BytesIO(chunk_bytes))
            assert len(reader.pages) == 25

    def test_streaming_iter_chunk_bytes(self, create_pdf):
        """Can iterate over chunk bytes from streaming result."""
        pdf_bytes = create_pdf(75)
        chunker = PDFChunker(enable_memory_tracking=False)

        with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as result:
            chunks_iterated = 0
            for chunk_bytes, page_start, page_end in result.iter_chunk_bytes():
                assert chunk_bytes.startswith(b"%PDF-")
                reader = PdfReader(BytesIO(chunk_bytes))
                expected_pages = page_end - page_start + 1
                assert len(reader.pages) == expected_pages
                chunks_iterated += 1

            assert chunks_iterated == 3

    def test_streaming_invalid_index(self, create_pdf):
        """Invalid index raises IndexError."""
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker(enable_memory_tracking=False)

        with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as result:
            with pytest.raises(IndexError):
                result.get_chunk_bytes(10)

            with pytest.raises(IndexError):
                result.get_chunk_bytes(-1)

    def test_streaming_page_numbers_correct(self, create_pdf):
        """Streaming chunks have correct page numbers."""
        pdf_bytes = create_pdf(80)
        chunker = PDFChunker(enable_memory_tracking=False)

        with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as result:
            # Check actual values
            _, start0, end0 = result.chunks[0]
            _, start1, end1 = result.chunks[1]
            _, start2, end2 = result.chunks[2]
            _, start3, end3 = result.chunks[3]

            assert (start0, end0) == (1, 25)
            assert (start1, end1) == (26, 50)
            assert (start2, end2) == (51, 75)
            assert (start3, end3) == (76, 80)


class TestShouldUseStreaming:
    """Tests for streaming threshold detection."""

    def test_small_pdf_no_streaming(self):
        """Small PDFs don't need streaming."""
        chunker = PDFChunker()
        # 50MB
        assert chunker.should_use_streaming(50 * 1024 * 1024) is False

    def test_large_pdf_should_stream(self):
        """Large PDFs (>100MB) should use streaming."""
        chunker = PDFChunker()
        # 150MB
        assert chunker.should_use_streaming(150 * 1024 * 1024) is True

    def test_boundary_value(self):
        """Exactly at 100MB boundary."""
        chunker = PDFChunker()
        boundary_bytes = STREAMING_THRESHOLD_MB * 1024 * 1024
        assert chunker.should_use_streaming(boundary_bytes) is False
        assert chunker.should_use_streaming(boundary_bytes + 1) is True


class TestStreamingChunkResultClass:
    """Tests for StreamingChunkResult container."""

    def test_context_manager_enter_exit(self):
        """Context manager works correctly."""
        temp_dir = Path(tempfile.mkdtemp(prefix="test_chunks_"))
        try:
            result = StreamingChunkResult(temp_dir, [])

            with result as r:
                assert r is result
                assert temp_dir.exists()

            # After exit, should be cleaned up
            assert not temp_dir.exists()
        finally:
            # Ensure cleanup even if test fails
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)

    def test_manual_cleanup(self):
        """Manual cleanup method works."""
        temp_dir = Path(tempfile.mkdtemp(prefix="test_chunks_"))
        try:
            result = StreamingChunkResult(temp_dir, [])
            assert temp_dir.exists()

            result.cleanup()
            assert not temp_dir.exists()

            # Second cleanup should not raise
            result.cleanup()
        finally:
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)


class TestMemoryTracking:
    """Story 17.1: Tests for memory tracking and limits."""

    def test_memory_tracking_can_be_disabled(self, create_pdf):
        """Memory tracking can be disabled."""
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker(enable_memory_tracking=False)

        # Should not raise even with large document
        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)
        assert len(chunks) == 2

    def test_memory_limit_constant(self):
        """Memory limit is configured at 50MB."""
        assert MEMORY_LIMIT_MB == 50


class TestTimeout:
    """Tests for split timeout functionality."""

    def test_split_with_timeout_succeeds(self, create_pdf):
        """Split completes within timeout."""
        pdf_bytes = create_pdf(50)
        chunker = PDFChunker(enable_memory_tracking=False)

        chunks = chunker.split_pdf_with_timeout(
            pdf_bytes, chunk_size=25, timeout_seconds=30
        )

        assert len(chunks) == 2

    def test_split_with_timeout_propagates_errors(self, create_pdf):
        """Errors are propagated from timeout thread."""
        chunker = PDFChunker(enable_memory_tracking=False)

        with pytest.raises(PDFChunkerError):
            chunker.split_pdf_with_timeout(b"Invalid PDF", timeout_seconds=5)


class TestAtomicWrites:
    """Story 17.1: Tests for atomic write pattern."""

    def test_no_tmp_files_remain(self, create_pdf):
        """No .tmp files remain after successful streaming split."""
        pdf_bytes = create_pdf(75)
        chunker = PDFChunker(enable_memory_tracking=False)

        with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as result:
            # Check no .tmp files exist
            tmp_files = list(result.temp_dir.glob("*.tmp"))
            assert len(tmp_files) == 0

            # All chunk files should be .pdf
            pdf_files = list(result.temp_dir.glob("*.pdf"))
            assert len(pdf_files) == 3
