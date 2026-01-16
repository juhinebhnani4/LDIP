# Story 18.2: Unit Tests for OCRResultMerger

Status: ready-for-dev

## Story

As a developer,
I want comprehensive unit tests for OCRResultMerger,
so that I can be confident page offset calculations are correct.

## Acceptance Criteria

1. **Page Offset Correctness**
   - Mock OCR results for 3 chunks merge with correct absolute page numbers
   - reading_order_index preserved per-page
   - full_text correctly concatenated

2. **Boundary Page Testing**
   - Test last page of chunk N (pages 25, 50, 75)
   - Test first page of chunk N+1 (pages 26, 51, 76)
   - Test single-page final chunk

3. **Off-By-One Focus (PRE-MORTEM)**
   - Explicit tests for off-by-one errors at every chunk boundary
   - Test matrix includes pages 24, 25, 26 and 49, 50, 51
   - Assertion messages clearly identify which boundary failed

## Tasks / Subtasks

- [ ] Task 1: Create test fixtures for OCR results (AC: #1)
  - [ ] Mock ChunkOCRResult objects
  - [ ] Sample bounding boxes with various page numbers
  - [ ] Different confidence values

- [ ] Task 2: Write page offset tests (AC: #1, #2)
  - [ ] Test 3-chunk merge
  - [ ] Test boundary pages explicitly
  - [ ] Test reading order preservation

- [ ] Task 3: Write off-by-one prevention tests (AC: #3)
  - [ ] Test page 24, 25, 26 boundary
  - [ ] Test page 49, 50, 51 boundary
  - [ ] Clear assertion messages

## Dev Notes

### Test Structure

```python
# tests/services/test_ocr_result_merger.py
import pytest

from app.services.ocr_result_merger import (
    OCRResultMerger,
    ChunkOCRResult,
    MergeValidationError,
)


@pytest.fixture
def chunk_results_75_pages():
    """3 chunks representing a 75-page document."""
    return [
        ChunkOCRResult(
            chunk_index=0,
            page_start=1,
            page_end=25,
            bounding_boxes=[
                {"page": 1, "reading_order_index": 0, "text": "Page 1"},
                {"page": 24, "reading_order_index": 0, "text": "Page 24"},
                {"page": 25, "reading_order_index": 0, "text": "Page 25"},
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
                {"page": 1, "reading_order_index": 0, "text": "Chunk1 relative page 1"},
                {"page": 24, "reading_order_index": 0, "text": "Chunk1 relative page 24"},
                {"page": 25, "reading_order_index": 0, "text": "Chunk1 relative page 25"},
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
                {"page": 1, "reading_order_index": 0, "text": "Chunk2 relative page 1"},
                {"page": 25, "reading_order_index": 0, "text": "Chunk2 relative page 25"},
            ],
            full_text="Chunk 2 text",
            overall_confidence=0.92,
            page_count=25,
        ),
    ]


class TestPageOffsetCalculation:
    def test_chunk_0_pages_unchanged(self, chunk_results_75_pages):
        merger = OCRResultMerger()
        result = merger.merge_results(chunk_results_75_pages, "doc-1")

        # Chunk 0 pages (offset=0) should be unchanged
        chunk0_bboxes = [b for b in result.bounding_boxes if b["page"] <= 25]
        pages = {b["page"] for b in chunk0_bboxes}
        assert 1 in pages, "Page 1 should exist in merged result"
        assert 24 in pages, "Page 24 should exist in merged result"
        assert 25 in pages, "Page 25 should exist in merged result"

    def test_chunk_1_pages_offset_by_25(self, chunk_results_75_pages):
        merger = OCRResultMerger()
        result = merger.merge_results(chunk_results_75_pages, "doc-1")

        # Chunk 1 pages (offset=25): relative 1 -> 26, relative 25 -> 50
        pages = {b["page"] for b in result.bounding_boxes}
        assert 26 in pages, "Relative page 1 of chunk 1 should become page 26"
        assert 49 in pages, "Relative page 24 of chunk 1 should become page 49"
        assert 50 in pages, "Relative page 25 of chunk 1 should become page 50"

    def test_chunk_2_pages_offset_by_50(self, chunk_results_75_pages):
        merger = OCRResultMerger()
        result = merger.merge_results(chunk_results_75_pages, "doc-1")

        pages = {b["page"] for b in result.bounding_boxes}
        assert 51 in pages, "Relative page 1 of chunk 2 should become page 51"
        assert 75 in pages, "Relative page 25 of chunk 2 should become page 75"


class TestBoundaryPages:
    """Explicitly test chunk boundary pages for off-by-one errors."""

    def test_boundary_24_25_26(self, chunk_results_75_pages):
        """Test pages at first chunk boundary."""
        merger = OCRResultMerger()
        result = merger.merge_results(chunk_results_75_pages, "doc-1")

        pages = [b["page"] for b in result.bounding_boxes]

        # Page 24: last page before boundary (chunk 0)
        assert 24 in pages, "Page 24 (end of chunk 0 - 1) missing"

        # Page 25: last page of chunk 0
        assert 25 in pages, "Page 25 (end of chunk 0) missing"

        # Page 26: first page of chunk 1 (relative page 1 + offset 25)
        assert 26 in pages, "Page 26 (start of chunk 1) missing"

    def test_boundary_49_50_51(self, chunk_results_75_pages):
        """Test pages at second chunk boundary."""
        merger = OCRResultMerger()
        result = merger.merge_results(chunk_results_75_pages, "doc-1")

        pages = [b["page"] for b in result.bounding_boxes]

        # Page 49: relative page 24 + offset 25
        assert 49 in pages, "Page 49 (end of chunk 1 - 1) missing"

        # Page 50: relative page 25 + offset 25
        assert 50 in pages, "Page 50 (end of chunk 1) missing"

        # Page 51: relative page 1 + offset 50
        assert 51 in pages, "Page 51 (start of chunk 2) missing"


class TestOffByOneMatrix:
    """Matrix of off-by-one tests with clear failure messages."""

    @pytest.mark.parametrize("chunk_index,relative_page,expected_absolute", [
        # Chunk 0 (offset 0)
        (0, 1, 1),
        (0, 24, 24),
        (0, 25, 25),
        # Chunk 1 (offset 25)
        (1, 1, 26),
        (1, 24, 49),
        (1, 25, 50),
        # Chunk 2 (offset 50)
        (2, 1, 51),
        (2, 24, 74),
        (2, 25, 75),
    ])
    def test_page_offset_calculation(self, chunk_index, relative_page, expected_absolute):
        # Create minimal chunk result
        chunks = [
            ChunkOCRResult(
                chunk_index=i,
                page_start=i * 25 + 1,
                page_end=(i + 1) * 25,
                bounding_boxes=[{"page": relative_page, "reading_order_index": 0}]
                if i == chunk_index else [],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            )
            for i in range(3)
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-1")

        if result.bounding_boxes:
            actual_page = result.bounding_boxes[0]["page"]
            assert actual_page == expected_absolute, (
                f"Chunk {chunk_index}, relative page {relative_page}: "
                f"expected absolute {expected_absolute}, got {actual_page}"
            )


class TestReadingOrderPreservation:
    def test_reading_order_preserved_per_page(self):
        chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[
                    {"page": 1, "reading_order_index": 0, "text": "First"},
                    {"page": 1, "reading_order_index": 1, "text": "Second"},
                    {"page": 1, "reading_order_index": 2, "text": "Third"},
                ],
                full_text="",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-1")

        # Order should be preserved
        page1_bboxes = [b for b in result.bounding_boxes if b["page"] == 1]
        texts = [b["text"] for b in page1_bboxes]
        assert texts == ["First", "Second", "Third"]
```

### References

- [Source: epic-4-testing-validation.md#Story 4.2] - Full AC
- [Source: Story 16.3] - OCRResultMerger implementation

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

