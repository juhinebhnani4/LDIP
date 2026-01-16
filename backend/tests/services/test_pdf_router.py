"""Tests for PDFRouter service.

Story 16.1: PDF Page Count Detection and Routing
"""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.services.pdf_router import (
    CHUNK_SIZE,
    MAX_PAGE_COUNT,
    PAGE_COUNT_THRESHOLD,
    MaliciousPDFError,
    PDFRouter,
    PDFRouterError,
    get_pdf_router,
)


@pytest.fixture
def sample_pdf_10_pages():
    """Create a minimal 10-page PDF for testing."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(10):
        writer.add_blank_page(width=612, height=792)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def sample_pdf_50_pages():
    """Create a 50-page PDF for testing chunked processing."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(50):
        writer.add_blank_page(width=612, height=792)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def sample_pdf_1_page():
    """Create a single-page PDF for testing."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class TestGetPageCount:
    """Tests for page count detection."""

    def test_counts_10_pages_correctly(self, sample_pdf_10_pages):
        """Accurately counts a 10-page PDF."""
        router = PDFRouter()
        count = router.get_page_count(sample_pdf_10_pages)
        assert count == 10

    def test_counts_50_pages_correctly(self, sample_pdf_50_pages):
        """Accurately counts a 50-page PDF."""
        router = PDFRouter()
        count = router.get_page_count(sample_pdf_50_pages)
        assert count == 50

    def test_counts_single_page_correctly(self, sample_pdf_1_page):
        """Accurately counts a single-page PDF."""
        router = PDFRouter()
        count = router.get_page_count(sample_pdf_1_page)
        assert count == 1

    def test_rejects_non_pdf(self):
        """Rejects files without PDF magic bytes."""
        router = PDFRouter()
        with pytest.raises(PDFRouterError) as exc:
            router.get_page_count(b"Not a PDF file at all")
        assert exc.value.code == "INVALID_PDF_FORMAT"

    def test_rejects_empty_file(self):
        """Rejects empty files."""
        router = PDFRouter()
        with pytest.raises(PDFRouterError) as exc:
            router.get_page_count(b"")
        assert exc.value.code == "EMPTY_FILE"

    def test_rejects_jpeg_file(self):
        """Rejects JPEG masquerading as PDF."""
        # JPEG magic bytes
        fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
        router = PDFRouter()
        with pytest.raises(PDFRouterError) as exc:
            router.get_page_count(fake_jpeg)
        assert exc.value.code == "INVALID_PDF_FORMAT"


class TestMaliciousPDFValidation:
    """Tests for malicious PDF detection."""

    def test_enforces_max_page_limit(self):
        """Rejects PDFs claiming excessive page count."""
        router = PDFRouter()

        # Create a mock reader that claims too many pages
        with patch("app.services.pdf_router.pypdf.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.pages = list(range(MAX_PAGE_COUNT + 1))  # Exceed limit
            mock_reader_class.return_value = mock_reader

            with pytest.raises(MaliciousPDFError) as exc:
                router.get_page_count(b"%PDF-1.4 fake content")
            assert "exceeds max" in str(exc.value).lower()

    def test_logs_page_count_mismatch(self, sample_pdf_10_pages):
        """Logs warning when claimed vs actual page count differs."""
        router = PDFRouter()

        # Mock to simulate mismatch (would require corrupted PDF in real scenario)
        with patch.object(router, "_count_actual_pages", return_value=8):
            with patch("app.services.pdf_router.logger") as mock_logger:
                router.get_page_count(sample_pdf_10_pages)
                mock_logger.warning.assert_called()


class TestShouldUseChunkedProcessing:
    """Tests for routing decision logic."""

    def test_small_document_uses_sync(self):
        """Documents with <=30 pages use sync processing."""
        router = PDFRouter()
        assert router.should_use_chunked_processing(1) is False
        assert router.should_use_chunked_processing(10) is False
        assert router.should_use_chunked_processing(30) is False

    def test_large_document_uses_chunked(self):
        """Documents with >30 pages use chunked processing."""
        router = PDFRouter()
        assert router.should_use_chunked_processing(31) is True
        assert router.should_use_chunked_processing(50) is True
        assert router.should_use_chunked_processing(100) is True
        assert router.should_use_chunked_processing(422) is True

    def test_boundary_values(self):
        """Boundary at exactly 30 pages uses sync, 31 uses chunked."""
        router = PDFRouter()
        assert router.should_use_chunked_processing(PAGE_COUNT_THRESHOLD) is False
        assert router.should_use_chunked_processing(PAGE_COUNT_THRESHOLD + 1) is True


class TestCalculateChunkSpecs:
    """Tests for chunk boundary calculation."""

    def test_exact_multiple(self):
        """50 pages divides evenly into 2 chunks of 25."""
        router = PDFRouter()
        specs = router.calculate_chunk_specs(50, chunk_size=25)

        assert len(specs) == 2
        assert specs[0].chunk_index == 0
        assert specs[0].page_start == 1
        assert specs[0].page_end == 25
        assert specs[1].chunk_index == 1
        assert specs[1].page_start == 26
        assert specs[1].page_end == 50

    def test_partial_last_chunk(self):
        """75 pages creates 3 chunks, last has 25 pages."""
        router = PDFRouter()
        specs = router.calculate_chunk_specs(75, chunk_size=25)

        assert len(specs) == 3
        assert specs[0].page_end == 25
        assert specs[1].page_start == 26
        assert specs[1].page_end == 50
        assert specs[2].page_start == 51
        assert specs[2].page_end == 75

    def test_small_remainder(self):
        """60 pages creates 3 chunks: 25, 25, 10."""
        router = PDFRouter()
        specs = router.calculate_chunk_specs(60, chunk_size=25)

        assert len(specs) == 3
        assert specs[2].page_start == 51
        assert specs[2].page_end == 60

    def test_single_chunk_small_document(self):
        """20 pages creates single chunk."""
        router = PDFRouter()
        specs = router.calculate_chunk_specs(20, chunk_size=25)

        assert len(specs) == 1
        assert specs[0].chunk_index == 0
        assert specs[0].page_start == 1
        assert specs[0].page_end == 20

    def test_422_page_document(self):
        """422 pages creates 17 chunks (matching spec)."""
        router = PDFRouter()
        specs = router.calculate_chunk_specs(422, chunk_size=25)

        # 422 / 25 = 16.88 -> 17 chunks
        assert len(specs) == 17

        # First chunk
        assert specs[0].chunk_index == 0
        assert specs[0].page_start == 1
        assert specs[0].page_end == 25

        # Last chunk (pages 401-422 = 22 pages)
        assert specs[-1].chunk_index == 16
        assert specs[-1].page_start == 401
        assert specs[-1].page_end == 422

    def test_returns_chunk_spec_models(self):
        """Returns ChunkSpec Pydantic models."""
        from app.models.ocr_chunk import ChunkSpec

        router = PDFRouter()
        specs = router.calculate_chunk_specs(50)

        assert all(isinstance(s, ChunkSpec) for s in specs)

    def test_custom_chunk_size(self):
        """Respects custom chunk size parameter."""
        router = PDFRouter()
        specs = router.calculate_chunk_specs(100, chunk_size=10)

        assert len(specs) == 10
        assert all(s.page_end - s.page_start + 1 == 10 for s in specs)


class TestGetPdfRouter:
    """Tests for PDFRouter factory."""

    def test_returns_singleton(self):
        """Factory returns the same instance."""
        # Clear the cache first
        get_pdf_router.cache_clear()

        router1 = get_pdf_router()
        router2 = get_pdf_router()

        assert router1 is router2

    def test_returns_pdf_router_instance(self):
        """Factory returns PDFRouter instance."""
        get_pdf_router.cache_clear()

        router = get_pdf_router()

        assert isinstance(router, PDFRouter)


class TestConstants:
    """Tests for routing constants."""

    def test_page_count_threshold(self):
        """PAGE_COUNT_THRESHOLD is 30 as per spec."""
        assert PAGE_COUNT_THRESHOLD == 30

    def test_max_page_count(self):
        """MAX_PAGE_COUNT is 10000 for security."""
        assert MAX_PAGE_COUNT == 10000

    def test_chunk_size(self):
        """CHUNK_SIZE is 25 pages per chunk."""
        assert CHUNK_SIZE == 25
