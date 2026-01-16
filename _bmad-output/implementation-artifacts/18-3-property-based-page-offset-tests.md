# Story 18.3: Property-Based Tests for Page Offsets

Status: ready-for-dev

## Story

As a developer,
I want property-based tests using hypothesis,
so that page offset logic is validated across thousands of random cases.

## Acceptance Criteria

1. **Hypothesis Test Generation**
   - hypothesis generates random page counts (1-1000) and chunk sizes (10-30)
   - Tests run 10,000+ random cases
   - Seed is logged for reproducibility

2. **Page Offset Properties**
   - `merged_bbox.page == original_absolute_page` always holds
   - No page numbers < 1 or > total_pages
   - Sum of chunk page counts == total page count
   - Bboxes are sorted by (page, reading_order_index)

3. **Zero Violations**
   - All 10,000 test cases pass without violations
   - Property failures are reported with minimal failing case
   - hypothesis shrinks failures to simplest reproduction

## Tasks / Subtasks

- [ ] Task 1: Add hypothesis dependency (AC: #1)
  - [ ] Add `hypothesis` to test dependencies in pyproject.toml
  - [ ] Configure hypothesis profile for CI (max_examples=10000)
  - [ ] Configure hypothesis profile for dev (max_examples=100)

- [ ] Task 2: Create property-based test fixtures (AC: #1)
  - [ ] Create `backend/tests/services/test_page_offset_properties.py`
  - [ ] Create strategy for random page counts (1-1000)
  - [ ] Create strategy for random chunk sizes (10-30)
  - [ ] Create mock bounding box generator

- [ ] Task 3: Implement page offset property tests (AC: #2, #3)
  - [ ] Test: merged page == original absolute page
  - [ ] Test: all pages in valid range
  - [ ] Test: chunk page counts sum correctly
  - [ ] Test: bbox sorting invariant

## Dev Notes

### Architecture Compliance

**Hypothesis Test Structure:**
```python
# tests/services/test_page_offset_properties.py
import pytest
from hypothesis import given, settings, strategies as st, Verbosity

from app.services.ocr_result_merger import OCRResultMerger
from app.models.ocr_chunk import ChunkOCRResult


# Custom strategy for page counts
page_count_strategy = st.integers(min_value=1, max_value=1000)
chunk_size_strategy = st.integers(min_value=10, max_value=30)


@st.composite
def mock_chunk_results(draw, total_pages: int, chunk_size: int):
    """Generate mock chunk results for property testing."""
    chunks = []
    page_offset = 0
    chunk_index = 0

    while page_offset < total_pages:
        pages_in_chunk = min(chunk_size, total_pages - page_offset)
        page_start = page_offset + 1
        page_end = page_offset + pages_in_chunk

        # Generate bboxes with relative page numbers (1-based within chunk)
        bboxes = []
        for relative_page in range(1, pages_in_chunk + 1):
            bboxes.append({
                "page": relative_page,
                "reading_order_index": 0,
                "text": f"Chunk {chunk_index} Page {relative_page}",
                "original_absolute_page": page_offset + relative_page,  # For verification
            })

        chunks.append(ChunkOCRResult(
            chunk_index=chunk_index,
            page_start=page_start,
            page_end=page_end,
            bounding_boxes=bboxes,
            full_text=f"Chunk {chunk_index} text",
            overall_confidence=0.9,
            page_count=pages_in_chunk,
        ))

        page_offset += pages_in_chunk
        chunk_index += 1

    return chunks


class TestPageOffsetProperties:
    @settings(max_examples=10000, verbosity=Verbosity.normal)
    @given(
        total_pages=page_count_strategy,
        chunk_size=chunk_size_strategy,
    )
    def test_merged_page_equals_original_absolute(
        self,
        total_pages: int,
        chunk_size: int,
    ):
        """Property: merged_bbox.page == original_absolute_page always."""
        chunks = mock_chunk_results(total_pages, chunk_size)
        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-test")

        for bbox in result.bounding_boxes:
            # Verify the merged page matches what we expect
            assert bbox["page"] == bbox["original_absolute_page"], (
                f"Page mismatch: merged={bbox['page']}, "
                f"expected={bbox['original_absolute_page']}"
            )

    @settings(max_examples=10000)
    @given(
        total_pages=page_count_strategy,
        chunk_size=chunk_size_strategy,
    )
    def test_all_pages_in_valid_range(
        self,
        total_pages: int,
        chunk_size: int,
    ):
        """Property: No page numbers < 1 or > total_pages."""
        chunks = mock_chunk_results(total_pages, chunk_size)
        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-test")

        for bbox in result.bounding_boxes:
            assert 1 <= bbox["page"] <= total_pages, (
                f"Page {bbox['page']} out of range [1, {total_pages}]"
            )

    @settings(max_examples=10000)
    @given(
        total_pages=page_count_strategy,
        chunk_size=chunk_size_strategy,
    )
    def test_chunk_page_counts_sum_correctly(
        self,
        total_pages: int,
        chunk_size: int,
    ):
        """Property: Sum of chunk page counts == total page count."""
        chunks = mock_chunk_results(total_pages, chunk_size)

        total_from_chunks = sum(chunk.page_count for chunk in chunks)
        assert total_from_chunks == total_pages, (
            f"Chunk sum {total_from_chunks} != total {total_pages}"
        )

    @settings(max_examples=10000)
    @given(
        total_pages=page_count_strategy,
        chunk_size=chunk_size_strategy,
    )
    def test_bboxes_sorted_by_page_and_reading_order(
        self,
        total_pages: int,
        chunk_size: int,
    ):
        """Property: Bboxes are sorted by (page, reading_order_index)."""
        chunks = mock_chunk_results(total_pages, chunk_size)
        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-test")

        prev_page = 0
        prev_reading_order = -1

        for bbox in result.bounding_boxes:
            current_page = bbox["page"]
            current_reading_order = bbox["reading_order_index"]

            if current_page == prev_page:
                assert current_reading_order >= prev_reading_order, (
                    f"Reading order not sorted on page {current_page}"
                )
            else:
                assert current_page > prev_page, (
                    f"Pages not sorted: {prev_page} -> {current_page}"
                )

            prev_page = current_page
            prev_reading_order = current_reading_order
```

### Hypothesis Configuration

```python
# conftest.py or pytest configuration
from hypothesis import settings, Verbosity, Phase

# CI profile - thorough testing
settings.register_profile(
    "ci",
    max_examples=10000,
    verbosity=Verbosity.normal,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
)

# Dev profile - fast feedback
settings.register_profile(
    "dev",
    max_examples=100,
    verbosity=Verbosity.verbose,
)

# Load profile from environment
import os
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))
```

### Testing Requirements

**Test Cases:**
```python
class TestPropertyInvariants:
    def test_single_page_document(self):
        """Edge case: 1 page document."""
        chunks = mock_chunk_results(total_pages=1, chunk_size=25)
        assert len(chunks) == 1
        assert chunks[0].page_count == 1

    def test_exact_chunk_multiple(self):
        """Edge case: pages exactly divisible by chunk_size."""
        chunks = mock_chunk_results(total_pages=50, chunk_size=25)
        assert len(chunks) == 2
        assert all(c.page_count == 25 for c in chunks)

    def test_max_page_count(self):
        """Edge case: maximum allowed pages."""
        chunks = mock_chunk_results(total_pages=1000, chunk_size=25)
        assert len(chunks) == 40
```

### References

- [Source: epic-4-testing-validation.md#Story 4.3] - Full AC
- [Source: Story 18.2] - OCRResultMerger tests
- [hypothesis documentation](https://hypothesis.readthedocs.io/)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

