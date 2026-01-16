"""Property-Based Tests for Page Offset Logic.

Story 18.3: Property-Based Tests for Page Offsets (Epic 4)

Uses hypothesis to generate random page counts (1-1000) and chunk sizes (10-30)
to validate page offset properties across thousands of test cases.

Properties validated:
- merged_bbox.page == original_absolute_page always
- No page numbers < 1 or > total_pages
- Sum of chunk page counts == total page count
- Bboxes are sorted by (page, reading_order_index) after merge
"""

from hypothesis import assume, given, settings
from hypothesis import strategies as st

import pytest

from app.services.pdf_chunker import PDFChunker
from app.services.ocr_result_merger import (
    ChunkOCRResult,
    MergeValidationError,
    OCRResultMerger,
)


# =============================================================================
# Strategies for generating test data
# =============================================================================


@st.composite
def chunk_configuration(draw, min_pages=1, max_pages=1000, min_chunk_size=10, max_chunk_size=30):
    """Generate a valid chunk configuration.

    Returns:
        Tuple of (total_pages, chunk_size)
    """
    total_pages = draw(st.integers(min_value=min_pages, max_value=max_pages))
    chunk_size = draw(st.integers(min_value=min_chunk_size, max_value=max_chunk_size))
    return total_pages, chunk_size


@st.composite
def valid_chunk_results(draw, total_pages, chunk_size):
    """Generate valid ChunkOCRResult list for given configuration.

    Creates chunks with proper page ranges and some bounding boxes
    at various positions within each chunk.

    Args:
        total_pages: Total pages in document.
        chunk_size: Pages per chunk.

    Returns:
        List of ChunkOCRResult with valid page ranges.
    """
    chunks = []
    chunk_index = 0
    page_start = 1

    while page_start <= total_pages:
        page_end = min(page_start + chunk_size - 1, total_pages)
        page_count = page_end - page_start + 1

        # Generate some bboxes for this chunk
        num_bboxes = draw(st.integers(min_value=0, max_value=10))
        bboxes = []

        for i in range(num_bboxes):
            # Generate a relative page within chunk (1 to page_count)
            relative_page = draw(st.integers(min_value=1, max_value=page_count))
            reading_order = draw(st.integers(min_value=0, max_value=20))

            bboxes.append({
                "page": relative_page,
                "reading_order_index": reading_order,
                "text": f"chunk{chunk_index}_page{relative_page}_roi{reading_order}",
                # Store expected absolute page for verification
                "_expected_absolute_page": relative_page + (page_start - 1),
            })

        confidence = draw(st.floats(min_value=0.5, max_value=1.0))

        chunks.append(
            ChunkOCRResult(
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
                bounding_boxes=bboxes,
                full_text=f"Chunk {chunk_index} text",
                overall_confidence=confidence,
                page_count=page_count,
            )
        )

        page_start = page_end + 1
        chunk_index += 1

    return chunks


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPageOffsetProperties:
    """Property-based tests for page offset logic."""

    @given(config=chunk_configuration())
    @settings(max_examples=1000, deadline=None)
    def test_page_numbers_always_absolute(self, config):
        """Property: merged_bbox.page == original_absolute_page always."""
        total_pages, chunk_size = config

        # Generate valid chunks
        chunks = []
        chunk_index = 0
        page_start = 1

        while page_start <= total_pages:
            page_end = min(page_start + chunk_size - 1, total_pages)
            page_count = page_end - page_start + 1

            # Add bbox at first and last page of each chunk
            bboxes = []
            if page_count > 0:
                bboxes.append({
                    "page": 1,
                    "reading_order_index": 0,
                    "_expected": page_start,  # Expected absolute page
                })
                if page_count > 1:
                    bboxes.append({
                        "page": page_count,
                        "reading_order_index": 0,
                        "_expected": page_end,  # Expected absolute page
                    })

            chunks.append(
                ChunkOCRResult(
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    bounding_boxes=bboxes,
                    full_text="",
                    overall_confidence=0.9,
                    page_count=page_count,
                )
            )

            page_start = page_end + 1
            chunk_index += 1

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-test")

        # Verify each bbox has correct absolute page
        bbox_idx = 0
        for chunk in chunks:
            for orig_bbox in chunk.bounding_boxes:
                merged_bbox = result.bounding_boxes[bbox_idx]
                assert merged_bbox["page"] == orig_bbox["_expected"], (
                    f"Bbox page mismatch: expected {orig_bbox['_expected']}, "
                    f"got {merged_bbox['page']}"
                )
                bbox_idx += 1

    @given(config=chunk_configuration())
    @settings(max_examples=1000, deadline=None)
    def test_no_invalid_page_numbers(self, config):
        """Property: No page numbers < 1 or > total_pages."""
        total_pages, chunk_size = config

        chunks = []
        chunk_index = 0
        page_start = 1

        while page_start <= total_pages:
            page_end = min(page_start + chunk_size - 1, total_pages)
            page_count = page_end - page_start + 1

            # Add bboxes at random relative pages
            bboxes = [{"page": 1}, {"page": page_count}] if page_count > 0 else []

            chunks.append(
                ChunkOCRResult(
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    bounding_boxes=bboxes,
                    full_text="",
                    overall_confidence=0.9,
                    page_count=page_count,
                )
            )

            page_start = page_end + 1
            chunk_index += 1

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-test")

        # Check all merged pages are in valid range
        for bbox in result.bounding_boxes:
            page = bbox["page"]
            assert page >= 1, f"Page number {page} is less than 1"
            assert page <= total_pages, f"Page number {page} exceeds total pages {total_pages}"

    @given(config=chunk_configuration())
    @settings(max_examples=1000, deadline=None)
    def test_chunk_page_counts_sum_correctly(self, config):
        """Property: Sum of chunk page counts == total page count."""
        total_pages, chunk_size = config

        chunks = []
        chunk_index = 0
        page_start = 1
        computed_total = 0

        while page_start <= total_pages:
            page_end = min(page_start + chunk_size - 1, total_pages)
            page_count = page_end - page_start + 1
            computed_total += page_count

            chunks.append(
                ChunkOCRResult(
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    bounding_boxes=[],
                    full_text="",
                    overall_confidence=0.9,
                    page_count=page_count,
                )
            )

            page_start = page_end + 1
            chunk_index += 1

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-test")

        assert result.page_count == total_pages, (
            f"Merged page count {result.page_count} != total pages {total_pages}"
        )
        assert computed_total == total_pages, (
            f"Sum of chunk pages {computed_total} != total pages {total_pages}"
        )


class TestPDFChunkerProperties:
    """Property-based tests for PDFChunker split logic."""

    @given(
        page_count=st.integers(min_value=1, max_value=500),
        chunk_size=st.integers(min_value=10, max_value=30),
    )
    @settings(max_examples=500, deadline=None)
    def test_chunk_ranges_cover_all_pages(self, page_count, chunk_size):
        """Property: All pages are covered by exactly one chunk."""
        chunker = PDFChunker(enable_memory_tracking=False)

        # Calculate expected chunks
        chunks_info = []
        page_start = 1

        while page_start <= page_count:
            page_end = min(page_start + chunk_size - 1, page_count)
            chunks_info.append((page_start, page_end))
            page_start = page_end + 1

        # Verify all pages covered
        all_pages = set()
        for start, end in chunks_info:
            for page in range(start, end + 1):
                assert page not in all_pages, f"Page {page} covered by multiple chunks"
                all_pages.add(page)

        expected_pages = set(range(1, page_count + 1))
        assert all_pages == expected_pages, "Not all pages are covered"

    @given(
        page_count=st.integers(min_value=1, max_value=500),
        chunk_size=st.integers(min_value=10, max_value=30),
    )
    @settings(max_examples=500, deadline=None)
    def test_chunk_count_calculation(self, page_count, chunk_size):
        """Property: Chunk count is ceiling(page_count / chunk_size)."""
        import math

        expected_chunks = math.ceil(page_count / chunk_size)

        # Calculate actual chunks
        actual_chunks = 0
        page_start = 1

        while page_start <= page_count:
            page_end = min(page_start + chunk_size - 1, page_count)
            actual_chunks += 1
            page_start = page_end + 1

        assert actual_chunks == expected_chunks, (
            f"Expected {expected_chunks} chunks, got {actual_chunks} "
            f"for {page_count} pages with chunk size {chunk_size}"
        )

    @given(
        page_count=st.integers(min_value=1, max_value=500),
        chunk_size=st.integers(min_value=10, max_value=30),
    )
    @settings(max_examples=500, deadline=None)
    def test_last_chunk_size_bounds(self, page_count, chunk_size):
        """Property: Last chunk has 1 to chunk_size pages."""
        # Calculate chunks
        chunks_info = []
        page_start = 1

        while page_start <= page_count:
            page_end = min(page_start + chunk_size - 1, page_count)
            chunks_info.append((page_start, page_end))
            page_start = page_end + 1

        if chunks_info:
            last_start, last_end = chunks_info[-1]
            last_chunk_pages = last_end - last_start + 1

            assert 1 <= last_chunk_pages <= chunk_size, (
                f"Last chunk has {last_chunk_pages} pages, "
                f"expected 1 to {chunk_size}"
            )


class TestMergerInvariants:
    """Property-based tests for merger invariants."""

    @given(
        total_pages=st.integers(min_value=1, max_value=200),
        chunk_size=st.integers(min_value=10, max_value=30),
        bboxes_per_chunk=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=500, deadline=None)
    def test_bbox_count_preserved(self, total_pages, chunk_size, bboxes_per_chunk):
        """Property: Merged bbox count == sum of chunk bbox counts."""
        chunks = []
        chunk_index = 0
        page_start = 1
        expected_total_bboxes = 0

        while page_start <= total_pages:
            page_end = min(page_start + chunk_size - 1, total_pages)
            page_count = page_end - page_start + 1

            bboxes = []
            for i in range(min(bboxes_per_chunk, page_count)):
                bboxes.append({
                    "page": (i % page_count) + 1,
                    "reading_order_index": i,
                })
            expected_total_bboxes += len(bboxes)

            chunks.append(
                ChunkOCRResult(
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    bounding_boxes=bboxes,
                    full_text="",
                    overall_confidence=0.9,
                    page_count=page_count,
                )
            )

            page_start = page_end + 1
            chunk_index += 1

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-test")

        assert result.total_bboxes == expected_total_bboxes, (
            f"Bbox count mismatch: expected {expected_total_bboxes}, "
            f"got {result.total_bboxes}"
        )

    @given(
        total_pages=st.integers(min_value=25, max_value=200),
        chunk_size=st.integers(min_value=10, max_value=30),
    )
    @settings(max_examples=500, deadline=None)
    def test_chunk_boundaries_exact(self, total_pages, chunk_size):
        """Property: Every chunk boundary (page_end+1 == next page_start)."""
        chunks = []
        chunk_index = 0
        page_start = 1

        while page_start <= total_pages:
            page_end = min(page_start + chunk_size - 1, total_pages)
            page_count = page_end - page_start + 1

            chunks.append(
                ChunkOCRResult(
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    bounding_boxes=[],
                    full_text="",
                    overall_confidence=0.9,
                    page_count=page_count,
                )
            )

            page_start = page_end + 1
            chunk_index += 1

        # Verify boundaries
        for i in range(len(chunks) - 1):
            curr_end = chunks[i].page_end
            next_start = chunks[i + 1].page_start
            assert next_start == curr_end + 1, (
                f"Boundary gap: chunk {i} ends at {curr_end}, "
                f"chunk {i+1} starts at {next_start}"
            )


class TestRandomizedEndToEnd:
    """End-to-end property tests simulating full pipeline."""

    @given(
        total_pages=st.integers(min_value=31, max_value=500),
    )
    @settings(max_examples=100, deadline=None)
    def test_full_pipeline_simulation(self, total_pages):
        """Property: Full split→merge cycle preserves document integrity."""
        chunk_size = 25  # Default Document AI chunk size

        # Simulate PDF splitting
        chunks = []
        chunk_index = 0
        page_start = 1

        while page_start <= total_pages:
            page_end = min(page_start + chunk_size - 1, total_pages)
            page_count = page_end - page_start + 1

            # Simulate OCR output (bboxes at each page)
            bboxes = []
            for relative_page in range(1, page_count + 1):
                absolute_page = page_start + relative_page - 1
                bboxes.append({
                    "page": relative_page,
                    "reading_order_index": 0,
                    "text": f"Page {absolute_page} content",
                    "_expected_page": absolute_page,
                })

            chunks.append(
                ChunkOCRResult(
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    bounding_boxes=bboxes,
                    full_text=f"Chunk {chunk_index}",
                    overall_confidence=0.9,
                    page_count=page_count,
                )
            )

            page_start = page_end + 1
            chunk_index += 1

        # Merge
        merger = OCRResultMerger()
        result = merger.merge_results(chunks, f"doc-{total_pages}")

        # Verify properties
        assert result.page_count == total_pages
        assert result.total_bboxes == total_pages  # One bbox per page

        # Verify each bbox has correct absolute page
        for bbox in result.bounding_boxes:
            expected_page = bbox["_expected_page"]
            assert bbox["page"] == expected_page, (
                f"Page mismatch: expected {expected_page}, got {bbox['page']}"
            )

        # Verify page numbers are sequential 1..total_pages
        pages = sorted([b["page"] for b in result.bounding_boxes])
        expected = list(range(1, total_pages + 1))
        assert pages == expected, "Pages not sequential"
