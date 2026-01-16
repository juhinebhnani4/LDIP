"""Tests for OCRResultMerger service.

Story 16.3: Implement OCR Result Merger Service
Story 17.6: Page Offset Validation
Story 18.2: Unit Tests for OCRResultMerger (Epic 4)

PRE-MORTEM Off-By-One Focus:
- Explicit tests for off-by-one errors at every chunk boundary
- Test matrix includes: page 24, 25, 26 and 49, 50, 51 specifically
- Assertion messages clearly identify which boundary failed

Boundary Cases Covered:
- Last page of chunk N (e.g., page 25, 50, 75)
- First page of chunk N+1 (e.g., page 26, 51, 76)
- Single-page final chunk
"""

import pytest

from app.services.ocr_result_merger import (
    ChunkOCRResult,
    MergeValidationError,
    MergedOCRResult,
    OCRResultMerger,
    get_ocr_result_merger,
)


@pytest.fixture
def sample_chunk_results():
    """Create 3 chunks simulating a 75-page document."""
    return [
        ChunkOCRResult(
            chunk_index=0,
            page_start=1,
            page_end=25,
            bounding_boxes=[
                {"page": 1, "reading_order_index": 0, "text": "Page 1 text"},
                {"page": 25, "reading_order_index": 0, "text": "Page 25 text"},
            ],
            full_text="Chunk 0 text",
            overall_confidence=0.95,
            page_count=25,
        ),
        ChunkOCRResult(
            chunk_index=1,
            page_start=26,
            page_end=50,
            bounding_boxes=[
                {"page": 1, "reading_order_index": 0, "text": "Chunk1 page 1"},  # Relative
                {"page": 5, "reading_order_index": 0, "text": "Chunk1 page 5"},
            ],
            full_text="Chunk 1 text",
            overall_confidence=0.87,
            page_count=25,
        ),
        ChunkOCRResult(
            chunk_index=2,
            page_start=51,
            page_end=75,
            bounding_boxes=[
                {"page": 1, "reading_order_index": 0, "text": "Chunk2 page 1"},
            ],
            full_text="Chunk 2 text",
            overall_confidence=0.92,
            page_count=25,
        ),
    ]


class TestMergeResults:
    """Tests for merge_results method."""

    def test_merges_all_chunks(self, sample_chunk_results):
        """Merges all chunks into single result."""
        merger = OCRResultMerger()
        result = merger.merge_results(sample_chunk_results, "doc-123")

        assert result.chunk_count == 3
        assert result.page_count == 75
        assert result.total_bboxes == 5

    def test_transforms_page_numbers_correctly(self, sample_chunk_results):
        """Page numbers are transformed from chunk-relative to absolute."""
        merger = OCRResultMerger()
        result = merger.merge_results(sample_chunk_results, "doc-123")

        # Check chunk 0 pages (no offset)
        chunk0_bboxes = [b for b in result.bounding_boxes if b["page"] <= 25]
        assert any(b["page"] == 1 for b in chunk0_bboxes)
        assert any(b["page"] == 25 for b in chunk0_bboxes)

        # Check chunk 1 pages (offset=25)
        # Relative page 1 -> absolute page 26
        # Relative page 5 -> absolute page 30
        assert any(b["page"] == 26 for b in result.bounding_boxes)
        assert any(b["page"] == 30 for b in result.bounding_boxes)

        # Check chunk 2 pages (offset=50)
        # Relative page 1 -> absolute page 51
        assert any(b["page"] == 51 for b in result.bounding_boxes)

    def test_sets_document_id(self, sample_chunk_results):
        """Result has correct document_id."""
        merger = OCRResultMerger()
        result = merger.merge_results(sample_chunk_results, "doc-xyz-123")

        assert result.document_id == "doc-xyz-123"

    def test_sorts_chunks_by_index(self, sample_chunk_results):
        """Chunks are sorted by chunk_index before merging."""
        # Shuffle the chunks
        shuffled = [sample_chunk_results[2], sample_chunk_results[0], sample_chunk_results[1]]

        merger = OCRResultMerger()
        result = merger.merge_results(shuffled, "doc-123")

        # Result should still be correct
        assert result.chunk_count == 3
        assert result.page_count == 75

        # Pages should be in order
        pages = [b["page"] for b in result.bounding_boxes]
        # First bbox should be from chunk 0 (page 1)
        assert pages[0] == 1


class TestPageOffsetBoundaries:
    """Tests for chunk boundary page offset calculation."""

    def test_boundary_pages_correct(self):
        """Test pages 25, 26, 50, 51 (chunk boundaries)."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[{"page": 25, "reading_order_index": 0}],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[
                    {"page": 1, "reading_order_index": 0},  # -> 26
                    {"page": 25, "reading_order_index": 0},  # -> 50
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=2,
                page_start=51,
                page_end=75,
                bounding_boxes=[{"page": 1, "reading_order_index": 0}],  # -> 51
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        pages = [b["page"] for b in result.bounding_boxes]
        assert 25 in pages  # Last page of chunk 0
        assert 26 in pages  # First page of chunk 1
        assert 50 in pages  # Last page of chunk 1
        assert 51 in pages  # First page of chunk 2

    def test_chunk_2_page_5_becomes_page_30(self):
        """Spec example: chunk 1 relative page 5 -> absolute page 30."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[
                    {"page": 5, "reading_order_index": 0, "text": "Page 5 in chunk 1"}
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        # Relative page 5 + offset 25 = absolute page 30
        assert result.bounding_boxes[0]["page"] == 30


class TestConfidenceCalculation:
    """Tests for weighted average confidence calculation."""

    def test_weighted_average_confidence(self):
        """Confidence is weighted by page count."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.95,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.85,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        # (0.95*25 + 0.85*25) / 50 = (23.75 + 21.25) / 50 = 0.90
        assert abs(result.overall_confidence - 0.90) < 0.001

    def test_unequal_page_counts_weighted_correctly(self):
        """Chunks with different page counts are weighted properly."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=10,
                bounding_boxes=[],
                full_text="",
                overall_confidence=1.0,  # Perfect confidence
                page_count=10,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=11,
                page_end=50,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.80,  # Lower confidence
                page_count=40,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        # (1.0*10 + 0.80*40) / 50 = (10 + 32) / 50 = 0.84
        assert abs(result.overall_confidence - 0.84) < 0.001


class TestTextMerge:
    """Tests for text concatenation."""

    def test_merges_text_with_separators(self, sample_chunk_results):
        """Full text is concatenated with separators."""
        merger = OCRResultMerger()
        result = merger.merge_results(sample_chunk_results, "doc-123")

        assert "Chunk 0 text" in result.full_text
        assert "Chunk 1 text" in result.full_text
        assert "Chunk 2 text" in result.full_text

    def test_empty_text_handled(self):
        """Empty text chunks don't cause issues."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[],
                full_text="Some text",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        assert result.full_text == "Some text"


class TestValidation:
    """Tests for validation checks."""

    def test_empty_chunks_raises_error(self):
        """Empty chunk list raises EMPTY_CHUNKS error."""
        merger = OCRResultMerger()

        with pytest.raises(MergeValidationError) as exc:
            merger.merge_results([], "doc-123")
        assert exc.value.code == "EMPTY_CHUNKS"

    def test_checksum_mismatch_raises_error(self):
        """Invalid checksum raises CHECKSUM_MISMATCH error."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
                checksum="invalid_checksum",
            ),
        ]

        merger = OCRResultMerger()

        with pytest.raises(MergeValidationError) as exc:
            merger.merge_results(chunks, "doc-123")
        assert exc.value.code == "CHECKSUM_MISMATCH"

    def test_valid_checksum_passes(self):
        """Correct checksum passes validation."""
        merger = OCRResultMerger()

        chunk = ChunkOCRResult(
            chunk_index=0,
            page_start=1,
            page_end=25,
            bounding_boxes=[{"page": 1}],
            full_text="",
            overall_confidence=0.9,
            page_count=25,
        )

        # Compute correct checksum
        checksum = merger.compute_chunk_checksum(chunk)
        chunk.checksum = checksum

        # Should not raise
        result = merger.merge_results([chunk], "doc-123")
        assert result.chunk_count == 1


class TestBboxFieldPreservation:
    """Tests for preserving bbox fields."""

    def test_preserves_all_bbox_fields(self):
        """All bbox fields except page are preserved."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {
                        "page": 1,
                        "reading_order_index": 5,
                        "text": "Hello world",
                        "confidence": 0.98,
                        "x": 100,
                        "y": 200,
                        "width": 300,
                        "height": 50,
                        "custom_field": "preserved",
                    }
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        bbox = result.bounding_boxes[0]
        assert bbox["reading_order_index"] == 5
        assert bbox["text"] == "Hello world"
        assert bbox["confidence"] == 0.98
        assert bbox["x"] == 100
        assert bbox["y"] == 200
        assert bbox["width"] == 300
        assert bbox["height"] == 50
        assert bbox["custom_field"] == "preserved"


class TestComputeChunkChecksum:
    """Tests for checksum computation."""

    def test_computes_consistent_checksum(self):
        """Same chunk produces same checksum."""
        merger = OCRResultMerger()

        chunk = ChunkOCRResult(
            chunk_index=0,
            page_start=1,
            page_end=25,
            bounding_boxes=[{"page": 1}],
            full_text="",
            overall_confidence=0.9,
            page_count=25,
        )

        checksum1 = merger.compute_chunk_checksum(chunk)
        checksum2 = merger.compute_chunk_checksum(chunk)

        assert checksum1 == checksum2

    def test_different_chunks_different_checksums(self):
        """Different chunks have different checksums."""
        merger = OCRResultMerger()

        chunk1 = ChunkOCRResult(
            chunk_index=0,
            page_start=1,
            page_end=25,
            bounding_boxes=[{"page": 1}],
            full_text="",
            overall_confidence=0.9,
            page_count=25,
        )

        chunk2 = ChunkOCRResult(
            chunk_index=1,
            page_start=26,
            page_end=50,
            bounding_boxes=[{"page": 1}],
            full_text="",
            overall_confidence=0.9,
            page_count=25,
        )

        checksum1 = merger.compute_chunk_checksum(chunk1)
        checksum2 = merger.compute_chunk_checksum(chunk2)

        assert checksum1 != checksum2


class TestGetOcrResultMerger:
    """Tests for factory function."""

    def test_returns_singleton(self):
        """Factory returns the same instance."""
        get_ocr_result_merger.cache_clear()

        merger1 = get_ocr_result_merger()
        merger2 = get_ocr_result_merger()

        assert merger1 is merger2

    def test_returns_ocr_result_merger_instance(self):
        """Factory returns OCRResultMerger instance."""
        get_ocr_result_merger.cache_clear()

        merger = get_ocr_result_merger()

        assert isinstance(merger, OCRResultMerger)


# =============================================================================
# Story 18.2: PRE-MORTEM Off-By-One Focus Tests
# =============================================================================


class TestOffByOneBoundaries:
    """Story 18.2: Explicit tests for off-by-one errors at chunk boundaries."""

    def test_page_24_25_26_boundary(self):
        """Test pages 24, 25, 26 at first chunk boundary.

        This is the critical boundary between chunk 0 and chunk 1.
        - Page 24, 25: Last pages of chunk 0 (no offset)
        - Page 26: First page of chunk 1 (after offset 25)
        """
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {"page": 24, "reading_order_index": 0, "text": "Page 24"},
                    {"page": 25, "reading_order_index": 0, "text": "Page 25"},
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[
                    {"page": 1, "reading_order_index": 0, "text": "Chunk1 relative page 1"},
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        pages = {b["page"] for b in result.bounding_boxes}

        assert 24 in pages, "Page 24 (last chunk 0 minus 1) missing from merged result"
        assert 25 in pages, "Page 25 (last page of chunk 0) missing from merged result"
        assert 26 in pages, "Page 26 (first page of chunk 1) missing from merged result"

        # Verify the actual page values
        for bbox in result.bounding_boxes:
            if bbox.get("text") == "Page 24":
                assert bbox["page"] == 24, f"Page 24 has wrong value: {bbox['page']}"
            elif bbox.get("text") == "Page 25":
                assert bbox["page"] == 25, f"Page 25 has wrong value: {bbox['page']}"
            elif bbox.get("text") == "Chunk1 relative page 1":
                assert bbox["page"] == 26, f"Chunk1 page 1 should be 26, got: {bbox['page']}"

    def test_page_49_50_51_boundary(self):
        """Test pages 49, 50, 51 at second chunk boundary.

        - Page 49, 50: Last pages of chunk 1
        - Page 51: First page of chunk 2
        """
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[
                    {"page": 24, "reading_order_index": 0, "text": "Page 49"},  # 24+25=49
                    {"page": 25, "reading_order_index": 0, "text": "Page 50"},  # 25+25=50
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=2,
                page_start=51,
                page_end=75,
                bounding_boxes=[
                    {"page": 1, "reading_order_index": 0, "text": "Page 51"},  # 1+50=51
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        pages = {b["page"] for b in result.bounding_boxes}

        assert 49 in pages, "Page 49 (chunk 1, second to last) missing"
        assert 50 in pages, "Page 50 (last page of chunk 1) missing"
        assert 51 in pages, "Page 51 (first page of chunk 2) missing"

    def test_all_boundary_pages_matrix(self):
        """Comprehensive test of all boundary pages for 100-page document."""
        # 4 chunks: 1-25, 26-50, 51-75, 76-100
        # Boundaries: 25/26, 50/51, 75/76
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {"page": 1, "text": "first"},
                    {"page": 25, "text": "boundary_25"},
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[
                    {"page": 1, "text": "boundary_26"},   # +25 = 26
                    {"page": 25, "text": "boundary_50"},  # +25 = 50
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=2,
                page_start=51,
                page_end=75,
                bounding_boxes=[
                    {"page": 1, "text": "boundary_51"},   # +50 = 51
                    {"page": 25, "text": "boundary_75"},  # +50 = 75
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=3,
                page_start=76,
                page_end=100,
                bounding_boxes=[
                    {"page": 1, "text": "boundary_76"},    # +75 = 76
                    {"page": 25, "text": "boundary_100"},  # +75 = 100
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        # Build lookup by text
        text_to_page = {b.get("text"): b["page"] for b in result.bounding_boxes}

        # Verify all boundary pages
        assert text_to_page["first"] == 1, "First page should be 1"
        assert text_to_page["boundary_25"] == 25, "Boundary at 25 incorrect"
        assert text_to_page["boundary_26"] == 26, "Boundary at 26 incorrect"
        assert text_to_page["boundary_50"] == 50, "Boundary at 50 incorrect"
        assert text_to_page["boundary_51"] == 51, "Boundary at 51 incorrect"
        assert text_to_page["boundary_75"] == 75, "Boundary at 75 incorrect"
        assert text_to_page["boundary_76"] == 76, "Boundary at 76 incorrect"
        assert text_to_page["boundary_100"] == 100, "Boundary at 100 incorrect"


class TestSinglePageFinalChunk:
    """Story 18.2: Tests for single-page final chunks."""

    def test_single_page_last_chunk(self):
        """51 pages = 2 full chunks + 1 single-page chunk."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[{"page": 25, "text": "last of chunk 0"}],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[{"page": 25, "text": "last of chunk 1"}],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=2,
                page_start=51,
                page_end=51,  # Single page!
                bounding_boxes=[{"page": 1, "text": "only page of chunk 2"}],
                full_text="",
                overall_confidence=0.9,
                page_count=1,  # Single page
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        text_to_page = {b.get("text"): b["page"] for b in result.bounding_boxes}

        assert text_to_page["last of chunk 0"] == 25
        assert text_to_page["last of chunk 1"] == 50
        assert text_to_page["only page of chunk 2"] == 51

        assert result.page_count == 51

    def test_two_pages_last_chunk(self):
        """52 pages = 2 full chunks + 2-page final chunk."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=2,
                page_start=51,
                page_end=52,
                bounding_boxes=[
                    {"page": 1, "text": "page 51"},
                    {"page": 2, "text": "page 52"},
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=2,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        text_to_page = {b.get("text"): b["page"] for b in result.bounding_boxes}

        assert text_to_page["page 51"] == 51
        assert text_to_page["page 52"] == 52


class TestReadingOrderPreservation:
    """Story 18.2: Ensure reading_order_index is preserved per-page."""

    def test_reading_order_preserved_within_page(self):
        """reading_order_index values are preserved after merge."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {"page": 10, "reading_order_index": 0, "text": "first"},
                    {"page": 10, "reading_order_index": 1, "text": "second"},
                    {"page": 10, "reading_order_index": 2, "text": "third"},
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        page_10_bboxes = [b for b in result.bounding_boxes if b["page"] == 10]
        page_10_bboxes.sort(key=lambda x: x["reading_order_index"])

        assert len(page_10_bboxes) == 3
        assert page_10_bboxes[0]["text"] == "first"
        assert page_10_bboxes[1]["text"] == "second"
        assert page_10_bboxes[2]["text"] == "third"

    def test_reading_order_independent_across_chunks(self):
        """reading_order_index resets per chunk but pages are offset."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {"page": 25, "reading_order_index": 0, "text": "chunk0_roi0"},
                    {"page": 25, "reading_order_index": 5, "text": "chunk0_roi5"},
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[
                    {"page": 1, "reading_order_index": 0, "text": "chunk1_roi0"},
                    {"page": 1, "reading_order_index": 3, "text": "chunk1_roi3"},
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        # Page 25 (chunk 0)
        page_25 = [b for b in result.bounding_boxes if b["page"] == 25]
        assert len(page_25) == 2
        roi_values_25 = {b["reading_order_index"] for b in page_25}
        assert roi_values_25 == {0, 5}

        # Page 26 (chunk 1, relative page 1)
        page_26 = [b for b in result.bounding_boxes if b["page"] == 26]
        assert len(page_26) == 2
        roi_values_26 = {b["reading_order_index"] for b in page_26}
        assert roi_values_26 == {0, 3}


class TestPageRangeValidation:
    """Story 17.6/18.2: Page range validation tests."""

    def test_non_contiguous_chunks_raises_error(self):
        """Non-contiguous page ranges raise validation error."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=27,  # Gap! Should be 26
                page_end=50,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=24,
            ),
        ]

        merger = OCRResultMerger()

        with pytest.raises(MergeValidationError) as exc:
            merger.merge_results(chunks, "doc-123")
        assert exc.value.code == "PAGE_RANGE_INVALID"

    def test_overlapping_chunks_raises_error(self):
        """Overlapping page ranges raise validation error."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=25,  # Overlap! Should be 26
                page_end=50,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=26,
            ),
        ]

        merger = OCRResultMerger()

        with pytest.raises(MergeValidationError) as exc:
            merger.merge_results(chunks, "doc-123")
        assert exc.value.code == "PAGE_RANGE_INVALID"

    def test_first_chunk_not_starting_at_page_1(self):
        """First chunk must start at page 1."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=2,  # Should be 1!
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=24,
            ),
        ]

        merger = OCRResultMerger()

        with pytest.raises(MergeValidationError) as exc:
            merger.merge_results(chunks, "doc-123")
        assert exc.value.code == "PAGE_RANGE_INVALID"

    def test_page_start_greater_than_page_end(self):
        """page_start > page_end raises error."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=25,  # Swapped!
                page_end=1,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()

        with pytest.raises(MergeValidationError) as exc:
            merger.merge_results(chunks, "doc-123")
        assert exc.value.code == "PAGE_RANGE_INVALID"

    def test_chunk_index_not_sequential(self):
        """Chunk indices must be sequential (0, 1, 2, ...)."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=2,  # Skipped 1!
                page_start=26,
                page_end=50,
                bounding_boxes=[],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()

        with pytest.raises(MergeValidationError) as exc:
            merger.merge_results(chunks, "doc-123")
        assert exc.value.code == "PAGE_RANGE_INVALID"


class TestLargeDocument:
    """Story 18.2: Tests for large document (422 pages)."""

    def test_422_page_document_merge(self):
        """422-page document with 17 chunks merges correctly."""
        chunks = []
        chunk_size = 25
        total_pages = 422

        for i in range(17):
            page_start = i * chunk_size + 1
            page_end = min((i + 1) * chunk_size, total_pages)
            page_count = page_end - page_start + 1

            chunks.append(
                ChunkOCRResult(
                    chunk_index=i,
                    page_start=page_start,
                    page_end=page_end,
                    bounding_boxes=[
                        {"page": 1, "text": f"chunk{i}_first"},
                        {"page": page_count, "text": f"chunk{i}_last"},
                    ],
                    full_text=f"Chunk {i}",
                    overall_confidence=0.9,
                    page_count=page_count,
                )
            )

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-422")

        assert result.chunk_count == 17
        assert result.page_count == 422
        assert result.total_bboxes == 34  # 2 per chunk

        # Verify first and last pages
        text_to_page = {b.get("text"): b["page"] for b in result.bounding_boxes}

        assert text_to_page["chunk0_first"] == 1
        assert text_to_page["chunk0_last"] == 25
        assert text_to_page["chunk16_first"] == 401
        assert text_to_page["chunk16_last"] == 422


class TestPageNumberFieldAliases:
    """Test handling of both 'page' and 'page_number' fields."""

    def test_page_field_used(self):
        """Standard 'page' field is transformed."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[{"page": 5}],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        assert result.bounding_boxes[0]["page"] == 5
        assert result.bounding_boxes[0]["page_number"] == 5  # Alias added

    def test_page_number_field_used(self):
        """Alternative 'page_number' field is also supported."""
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[{"page_number": 10}],  # Using alias
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        # Both fields should be set
        assert result.bounding_boxes[0]["page"] == 10
        assert result.bounding_boxes[0]["page_number"] == 10
