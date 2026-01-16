"""Tests for OCRResultMerger service.

Story 16.3: Implement OCR Result Merger Service
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
