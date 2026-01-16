"""Integration Tests for Large PDF Chunking Pipeline.

Story 18.4: Integration Tests with Sample Documents (Epic 4)

Tests the full pipeline from PDF splitting through OCR merging,
validating:
- OCR completion for documents of various sizes
- Bounding box count validation (roughly 20 per page)
- Absolute page numbers are in valid range
- Cross-chunk citation highlighting works correctly
"""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pypdf import PdfWriter

from app.services.pdf_chunker import PDFChunker
from app.services.ocr_result_merger import ChunkOCRResult, OCRResultMerger


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def create_test_pdf():
    """Factory to create test PDFs with specified page count."""

    def _create(page_count: int, with_text: bool = False) -> bytes:
        writer = PdfWriter()
        for i in range(page_count):
            page = writer.add_blank_page(width=612, height=792)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    return _create


@pytest.fixture
def mock_ocr_chunk_result():
    """Factory to create mock OCR results for a chunk."""

    def _create(
        chunk_index: int,
        page_start: int,
        page_end: int,
        bboxes_per_page: int = 20,
    ) -> ChunkOCRResult:
        page_count = page_end - page_start + 1
        bboxes = []

        for relative_page in range(1, page_count + 1):
            for roi in range(bboxes_per_page):
                bboxes.append({
                    "page": relative_page,
                    "reading_order_index": roi,
                    "text": f"Text block {roi} on relative page {relative_page}",
                    "x": 72 + (roi % 5) * 100,
                    "y": 72 + (roi // 5) * 100,
                    "width": 90,
                    "height": 20,
                    "confidence": 0.95,
                })

        return ChunkOCRResult(
            chunk_index=chunk_index,
            page_start=page_start,
            page_end=page_end,
            bounding_boxes=bboxes,
            full_text=f"Full text for chunk {chunk_index}",
            overall_confidence=0.92,
            page_count=page_count,
        )

    return _create


# =============================================================================
# Story 18.4: Integration Tests with Sample Documents
# =============================================================================


class TestFullPipelineIntegration:
    """Integration tests for the full chunking pipeline."""

    @pytest.mark.parametrize("page_count", [50, 100, 200, 422])
    def test_full_pipeline_various_sizes(
        self, create_test_pdf, mock_ocr_chunk_result, page_count
    ):
        """Test full pipeline for documents of 50, 100, 200, and 422 pages."""
        # Create test PDF
        pdf_bytes = create_test_pdf(page_count)

        # Split PDF
        chunker = PDFChunker(enable_memory_tracking=False)
        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # Simulate OCR for each chunk
        ocr_results = []
        for chunk_bytes, page_start, page_end in chunks:
            chunk_index = len(ocr_results)
            ocr_result = mock_ocr_chunk_result(
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
                bboxes_per_page=20,
            )
            ocr_results.append(ocr_result)

        # Merge OCR results
        merger = OCRResultMerger()
        merged = merger.merge_results(ocr_results, f"doc-{page_count}")

        # Verify results
        assert merged.page_count == page_count
        assert merged.total_bboxes == page_count * 20  # 20 bboxes per page

        # Verify all page numbers are absolute and in range
        for bbox in merged.bounding_boxes:
            assert 1 <= bbox["page"] <= page_count, (
                f"Page {bbox['page']} out of range [1, {page_count}]"
            )

    def test_422_page_document_matches_spec(self, create_test_pdf, mock_ocr_chunk_result):
        """422-page document (original failing document) processes correctly."""
        page_count = 422
        pdf_bytes = create_test_pdf(page_count)

        # Split
        chunker = PDFChunker(enable_memory_tracking=False)
        chunks = chunker.split_pdf(pdf_bytes, chunk_size=25)

        # Should produce 17 chunks: 16 full (25 pages) + 1 partial (22 pages)
        assert len(chunks) == 17

        # Verify chunk boundaries
        expected_ranges = [
            (1, 25), (26, 50), (51, 75), (76, 100),
            (101, 125), (126, 150), (151, 175), (176, 200),
            (201, 225), (226, 250), (251, 275), (276, 300),
            (301, 325), (326, 350), (351, 375), (376, 400),
            (401, 422),  # Last chunk has 22 pages
        ]

        for i, (_, page_start, page_end) in enumerate(chunks):
            expected_start, expected_end = expected_ranges[i]
            assert page_start == expected_start, f"Chunk {i} start mismatch"
            assert page_end == expected_end, f"Chunk {i} end mismatch"


class TestCrossChunkBoundaries:
    """PRE-MORTEM: Tests for citations spanning chunk boundaries."""

    def test_citation_at_chunk_boundary_page_25(self, mock_ocr_chunk_result):
        """Citation on page 25 (end of chunk 0) highlights correctly."""
        # Create OCR results with specific bbox on page 25
        chunk0 = ChunkOCRResult(
            chunk_index=0,
            page_start=1,
            page_end=25,
            bounding_boxes=[
                {
                    "page": 25,  # Last page of chunk
                    "reading_order_index": 0,
                    "text": "Important citation on page 25",
                    "x": 100,
                    "y": 200,
                    "width": 300,
                    "height": 20,
                },
            ],
            full_text="Chunk 0",
            overall_confidence=0.9,
            page_count=25,
        )
        chunk1 = ChunkOCRResult(
            chunk_index=1,
            page_start=26,
            page_end=50,
            bounding_boxes=[],
            full_text="Chunk 1",
            overall_confidence=0.9,
            page_count=25,
        )

        merger = OCRResultMerger()
        result = merger.merge_results([chunk0, chunk1], "doc-test")

        # Find the citation bbox
        citation_bbox = result.bounding_boxes[0]
        assert citation_bbox["page"] == 25, "Citation page should be 25"
        assert citation_bbox["text"] == "Important citation on page 25"
        assert citation_bbox["x"] == 100
        assert citation_bbox["y"] == 200

    def test_citation_at_chunk_boundary_page_26(self, mock_ocr_chunk_result):
        """Citation on page 26 (start of chunk 1) highlights correctly."""
        chunk0 = ChunkOCRResult(
            chunk_index=0,
            page_start=1,
            page_end=25,
            bounding_boxes=[],
            full_text="Chunk 0",
            overall_confidence=0.9,
            page_count=25,
        )
        chunk1 = ChunkOCRResult(
            chunk_index=1,
            page_start=26,
            page_end=50,
            bounding_boxes=[
                {
                    "page": 1,  # Relative page 1 in chunk -> absolute page 26
                    "reading_order_index": 0,
                    "text": "Citation on first page of chunk 1",
                    "x": 150,
                    "y": 300,
                    "width": 250,
                    "height": 25,
                },
            ],
            full_text="Chunk 1",
            overall_confidence=0.9,
            page_count=25,
        )

        merger = OCRResultMerger()
        result = merger.merge_results([chunk0, chunk1], "doc-test")

        citation_bbox = result.bounding_boxes[0]
        assert citation_bbox["page"] == 26, "Citation page should be 26 (not 1)"
        assert citation_bbox["x"] == 150
        assert citation_bbox["y"] == 300

    def test_citations_spanning_multiple_chunks(self, mock_ocr_chunk_result):
        """Citations on pages 25, 26, 50, 51 all have correct coordinates."""
        chunk0 = ChunkOCRResult(
            chunk_index=0,
            page_start=1,
            page_end=25,
            bounding_boxes=[
                {"page": 25, "reading_order_index": 0, "text": "Page 25", "x": 100, "y": 100},
            ],
            full_text="",
            overall_confidence=0.9,
            page_count=25,
        )
        chunk1 = ChunkOCRResult(
            chunk_index=1,
            page_start=26,
            page_end=50,
            bounding_boxes=[
                {"page": 1, "reading_order_index": 0, "text": "Page 26", "x": 200, "y": 200},
                {"page": 25, "reading_order_index": 0, "text": "Page 50", "x": 300, "y": 300},
            ],
            full_text="",
            overall_confidence=0.9,
            page_count=25,
        )
        chunk2 = ChunkOCRResult(
            chunk_index=2,
            page_start=51,
            page_end=75,
            bounding_boxes=[
                {"page": 1, "reading_order_index": 0, "text": "Page 51", "x": 400, "y": 400},
            ],
            full_text="",
            overall_confidence=0.9,
            page_count=25,
        )

        merger = OCRResultMerger()
        result = merger.merge_results([chunk0, chunk1, chunk2], "doc-test")

        # Build lookup
        text_to_bbox = {b["text"]: b for b in result.bounding_boxes}

        # Verify page numbers and coordinates preserved
        assert text_to_bbox["Page 25"]["page"] == 25
        assert text_to_bbox["Page 25"]["x"] == 100

        assert text_to_bbox["Page 26"]["page"] == 26
        assert text_to_bbox["Page 26"]["x"] == 200

        assert text_to_bbox["Page 50"]["page"] == 50
        assert text_to_bbox["Page 50"]["x"] == 300

        assert text_to_bbox["Page 51"]["page"] == 51
        assert text_to_bbox["Page 51"]["x"] == 400


class TestBoundingBoxCountValidation:
    """Tests validating roughly 20 bboxes per page."""

    def test_bbox_count_per_page(self, mock_ocr_chunk_result):
        """Verify approximately 20 bboxes per page after merge."""
        # Create 75-page document with 20 bboxes per page
        chunks = []
        for i in range(3):
            page_start = i * 25 + 1
            page_end = (i + 1) * 25
            chunks.append(mock_ocr_chunk_result(i, page_start, page_end, bboxes_per_page=20))

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-75")

        # Total should be 75 * 20 = 1500
        assert result.total_bboxes == 1500

        # Count bboxes per page
        page_bbox_counts: dict[int, int] = {}
        for bbox in result.bounding_boxes:
            page = bbox["page"]
            page_bbox_counts[page] = page_bbox_counts.get(page, 0) + 1

        # Every page should have exactly 20 bboxes
        for page, count in page_bbox_counts.items():
            assert count == 20, f"Page {page} has {count} bboxes, expected 20"

        # All pages 1-75 should be present
        assert set(page_bbox_counts.keys()) == set(range(1, 76))


class TestHighlightingCoordinates:
    """Tests validating bbox coordinates for highlighting."""

    def test_coordinates_preserved_after_merge(self):
        """Bbox x, y, width, height preserved during merge."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {
                        "page": 10,
                        "reading_order_index": 0,
                        "text": "Test text",
                        "x": 72.5,
                        "y": 144.25,
                        "width": 523.75,
                        "height": 12.5,
                        "confidence": 0.97,
                    },
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-test")

        bbox = result.bounding_boxes[0]
        assert bbox["page"] == 10
        assert bbox["x"] == 72.5
        assert bbox["y"] == 144.25
        assert bbox["width"] == 523.75
        assert bbox["height"] == 12.5
        assert bbox["confidence"] == 0.97

    def test_viewer_navigation_coordinates(self):
        """Test that coordinates are valid for PDF viewer navigation."""
        # Standard PDF page dimensions: 612 x 792 points (8.5 x 11 inches at 72 DPI)
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {
                        "page": 15,
                        "x": 0,  # Left edge
                        "y": 0,  # Bottom edge
                        "width": 100,
                        "height": 20,
                    },
                    {
                        "page": 15,
                        "x": 512,  # Near right edge (612 - 100)
                        "y": 772,  # Near top edge (792 - 20)
                        "width": 100,
                        "height": 20,
                    },
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-test")

        # Both bboxes should be on page 15
        for bbox in result.bounding_boxes:
            assert bbox["page"] == 15
            # Coordinates should be valid for PDF viewer
            assert bbox["x"] >= 0
            assert bbox["y"] >= 0


class TestStreamingPipelineIntegration:
    """Integration tests using streaming PDF split."""

    def test_streaming_split_integration(self, create_test_pdf, mock_ocr_chunk_result):
        """Full pipeline using streaming split for large documents."""
        page_count = 100
        pdf_bytes = create_test_pdf(page_count)

        chunker = PDFChunker(enable_memory_tracking=False)

        # Use streaming split
        with chunker.split_pdf_streaming(pdf_bytes, chunk_size=25) as stream_result:
            assert len(stream_result.chunks) == 4

            # Simulate OCR for each chunk
            ocr_results = []
            for i, (chunk_path, page_start, page_end) in enumerate(stream_result.chunks):
                # Read chunk bytes (in real scenario, would send to Document AI)
                chunk_bytes = chunk_path.read_bytes()
                assert chunk_bytes.startswith(b"%PDF-")

                # Create mock OCR result
                ocr_result = mock_ocr_chunk_result(
                    chunk_index=i,
                    page_start=page_start,
                    page_end=page_end,
                    bboxes_per_page=15,
                )
                ocr_results.append(ocr_result)

            # Merge results
            merger = OCRResultMerger()
            merged = merger.merge_results(ocr_results, "doc-streaming")

            assert merged.page_count == 100
            assert merged.total_bboxes == 100 * 15

        # After context, temp files should be cleaned up
        assert not stream_result.temp_dir.exists()
