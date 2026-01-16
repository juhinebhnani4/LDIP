# Story 16.3: Implement OCR Result Merger Service

Status: done

## Story

As a backend developer,
I want a service to merge OCR results from multiple chunks with correct page offsets,
so that the final result has absolute page numbers matching the original document.

## Acceptance Criteria

1. **Page Offset Calculation**
   - Chunk results from pages 1-25, 26-50, 51-75 merge correctly
   - All bounding boxes have absolute page numbers (1-75, not chunk-relative)
   - Bbox from chunk 2, relative page 5 becomes absolute page 30

2. **Reading Order Index**
   - `reading_order_index` values restart at 0 for each page (per-page, not global)
   - Order is preserved within each page

3. **Text Concatenation**
   - Full text from all chunks concatenated with page breaks preserved
   - No text loss at chunk boundaries

4. **Confidence Calculation**
   - `overall_confidence` is weighted average of chunk confidences
   - Weighted by page count per chunk

5. **Page Count Validation**
   - `page_count` equals sum of pages across all chunks
   - Validates no pages skipped or duplicated

6. **Result Validation (CHAOS MONKEY)**
   - SHA256 checksum validated against stored `result_checksum`
   - Corrupted results trigger re-processing of that chunk

7. **Post-Merge Validation (PRE-MORTEM)**
   - Validate: total_bboxes == sum(chunk_bboxes)
   - Validate: page numbers are continuous from 1 to N
   - Validate: no duplicate reading_order_index on same page

## Tasks / Subtasks

- [ ] Task 1: Create OCRResultMerger service (AC: #1, #2, #3)
  - [ ] Create `backend/app/services/ocr_result_merger.py`
  - [ ] Implement `merge_results(chunk_results, document_id)` method
  - [ ] Define `ChunkOCRResult` model for chunk results
  - [ ] Define `MergedOCRResult` model for final output

- [ ] Task 2: Implement page offset transformation (AC: #1)
  - [ ] Calculate page offset for each chunk based on previous chunks
  - [ ] Transform all bbox page numbers: `absolute = relative + offset`
  - [ ] Preserve all other bbox fields unchanged

- [ ] Task 3: Implement reading order preservation (AC: #2)
  - [ ] Keep reading_order_index per-page (restart at 0 each page)
  - [ ] Sort bboxes by (page, reading_order_index)

- [ ] Task 4: Implement text and confidence merge (AC: #3, #4, #5)
  - [ ] Concatenate full_text with page markers
  - [ ] Calculate weighted average confidence
  - [ ] Sum page counts for validation

- [ ] Task 5: Implement validation checks (AC: #6, #7)
  - [ ] Validate checksum before merge
  - [ ] Validate post-merge: bbox count, page continuity, no duplicate indices
  - [ ] Raise `MergeValidationError` on failures

- [ ] Task 6: Write tests (AC: #1-7)
  - [ ] Create `backend/tests/services/test_ocr_result_merger.py`
  - [ ] Test page offset calculation (chunk 2, page 5 -> page 30)
  - [ ] Test boundary pages (25, 26, 50, 51)
  - [ ] Test confidence weighted average
  - [ ] Test validation catches corruption

## Dev Notes

### Architecture Compliance

**OCRResultMerger Service Pattern:**
```python
# backend/app/services/ocr_result_merger.py
import hashlib
from functools import lru_cache
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class MergeValidationError(Exception):
    """Raised when merge validation fails."""
    def __init__(self, message: str, code: str = "MERGE_VALIDATION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ChunkOCRResult(BaseModel):
    """OCR result from a single chunk."""
    chunk_index: int
    page_start: int  # 1-based
    page_end: int    # 1-based
    bounding_boxes: list[dict]
    full_text: str
    overall_confidence: float
    page_count: int
    checksum: str | None = None  # SHA256 of original result

    model_config = {"populate_by_name": True}


class MergedOCRResult(BaseModel):
    """Final merged OCR result with absolute page numbers."""
    document_id: str
    bounding_boxes: list[dict]
    full_text: str
    overall_confidence: float
    page_count: int
    chunk_count: int
    total_bboxes: int

    model_config = {"populate_by_name": True}


class OCRResultMerger:
    """Service for merging chunked OCR results.

    Transforms chunk-relative page numbers to absolute page numbers
    and validates data integrity post-merge.
    """

    def merge_results(
        self,
        chunk_results: list[ChunkOCRResult],
        document_id: str,
    ) -> MergedOCRResult:
        """Merge OCR results from multiple chunks.

        Args:
            chunk_results: List of chunk OCR results, ordered by chunk_index.
            document_id: Parent document UUID.

        Returns:
            MergedOCRResult with absolute page numbers.

        Raises:
            MergeValidationError: If validation fails.
        """
        if not chunk_results:
            raise MergeValidationError("No chunk results to merge", code="EMPTY_CHUNKS")

        # Sort by chunk_index to ensure correct order
        sorted_results = sorted(chunk_results, key=lambda x: x.chunk_index)

        # Validate checksums before merge
        for chunk in sorted_results:
            if chunk.checksum:
                self._validate_checksum(chunk)

        # Merge bounding boxes with page offset transformation
        merged_bboxes = []
        page_offset = 0

        for chunk in sorted_results:
            transformed = self._transform_bboxes(chunk.bounding_boxes, page_offset)
            merged_bboxes.extend(transformed)
            page_offset += chunk.page_count

        # Merge full text
        merged_text = self._merge_text(sorted_results)

        # Calculate weighted average confidence
        total_pages = sum(c.page_count for c in sorted_results)
        weighted_confidence = sum(
            c.overall_confidence * c.page_count for c in sorted_results
        ) / total_pages if total_pages > 0 else 0.0

        result = MergedOCRResult(
            document_id=document_id,
            bounding_boxes=merged_bboxes,
            full_text=merged_text,
            overall_confidence=weighted_confidence,
            page_count=total_pages,
            chunk_count=len(sorted_results),
            total_bboxes=len(merged_bboxes),
        )

        # Post-merge validation
        self._validate_merged_result(result, sorted_results)

        logger.info(
            "ocr_results_merged",
            document_id=document_id,
            chunk_count=len(sorted_results),
            total_pages=total_pages,
            total_bboxes=len(merged_bboxes),
            confidence=round(weighted_confidence, 2),
        )

        return result

    def _transform_bboxes(
        self,
        bboxes: list[dict],
        page_offset: int,
    ) -> list[dict]:
        """Transform bbox page numbers from chunk-relative to absolute.

        Args:
            bboxes: Bounding boxes with chunk-relative page numbers.
            page_offset: Page offset to add (sum of previous chunks' pages).

        Returns:
            Bounding boxes with absolute page numbers.
        """
        transformed = []
        for bbox in bboxes:
            new_bbox = bbox.copy()
            # Transform page number: relative -> absolute
            relative_page = bbox.get("page", bbox.get("page_number", 1))
            new_bbox["page"] = relative_page + page_offset
            new_bbox["page_number"] = new_bbox["page"]  # Alias
            transformed.append(new_bbox)
        return transformed

    def _merge_text(self, chunk_results: list[ChunkOCRResult]) -> str:
        """Merge full text from chunks with page separators."""
        texts = []
        for chunk in chunk_results:
            if chunk.full_text:
                texts.append(chunk.full_text)
        return "\n\n".join(texts)

    def _validate_checksum(self, chunk: ChunkOCRResult) -> None:
        """Validate chunk result checksum."""
        if not chunk.checksum:
            return

        # Recompute checksum from chunk data
        data = f"{chunk.chunk_index}:{chunk.page_start}:{chunk.page_end}:{len(chunk.bounding_boxes)}"
        computed = hashlib.sha256(data.encode()).hexdigest()[:16]

        if computed != chunk.checksum:
            logger.warning(
                "chunk_checksum_mismatch",
                chunk_index=chunk.chunk_index,
                expected=chunk.checksum,
                computed=computed,
            )
            raise MergeValidationError(
                f"Chunk {chunk.chunk_index} checksum mismatch",
                code="CHECKSUM_MISMATCH",
            )

    def _validate_merged_result(
        self,
        result: MergedOCRResult,
        chunk_results: list[ChunkOCRResult],
    ) -> None:
        """Validate merged result integrity."""
        # Validate bbox count
        expected_bboxes = sum(len(c.bounding_boxes) for c in chunk_results)
        if result.total_bboxes != expected_bboxes:
            raise MergeValidationError(
                f"Bbox count mismatch: {result.total_bboxes} != {expected_bboxes}",
                code="BBOX_COUNT_MISMATCH",
            )

        # Validate page numbers are continuous
        pages_seen = set()
        for bbox in result.bounding_boxes:
            page = bbox.get("page", bbox.get("page_number"))
            if page is not None:
                pages_seen.add(page)

        if pages_seen:
            expected_pages = set(range(1, result.page_count + 1))
            missing = expected_pages - pages_seen
            if missing and len(missing) > result.page_count * 0.1:
                # Allow some pages without bboxes (blank pages), but not too many
                logger.warning(
                    "merge_pages_missing",
                    missing_count=len(missing),
                    total_pages=result.page_count,
                )

        # Validate no duplicate reading_order_index on same page
        page_indices: dict[int, set[int]] = {}
        for bbox in result.bounding_boxes:
            page = bbox.get("page", bbox.get("page_number", 0))
            roi = bbox.get("reading_order_index", 0)
            if page not in page_indices:
                page_indices[page] = set()
            if roi in page_indices[page]:
                logger.warning(
                    "duplicate_reading_order_index",
                    page=page,
                    reading_order_index=roi,
                )
            page_indices[page].add(roi)


@lru_cache(maxsize=1)
def get_ocr_result_merger() -> OCRResultMerger:
    """Get singleton OCRResultMerger instance."""
    return OCRResultMerger()
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    services/
      ocr_result_merger.py   # NEW - Merger service
  tests/
    services/
      test_ocr_result_merger.py  # NEW - Tests
```

**Related Files:**
- [PDFChunker](../../backend/app/services/pdf_chunker.py) - Produces chunks (Story 16.2)
- [BoundingBoxService](../../backend/app/services/bounding_box_service.py) - Stores merged results
- [document_tasks.py](../../backend/app/workers/tasks/document_tasks.py) - Integration

### Technical Requirements

**Page Offset Calculation Example:**
```
Document: 75 pages, 3 chunks of 25 pages each

Chunk 0: pages 1-25, offset=0
  bbox.page=5 -> absolute_page = 5 + 0 = 5

Chunk 1: pages 26-50, offset=25
  bbox.page=5 -> absolute_page = 5 + 25 = 30

Chunk 2: pages 51-75, offset=50
  bbox.page=5 -> absolute_page = 5 + 50 = 55
```

**Weighted Confidence Example:**
```python
# 3 chunks: 25 pages each
chunk_confidences = [0.95, 0.87, 0.92]
page_counts = [25, 25, 25]

weighted_avg = (0.95*25 + 0.87*25 + 0.92*25) / (25+25+25)
             = (23.75 + 21.75 + 23.0) / 75
             = 68.5 / 75
             = 0.913
```

### Testing Requirements

**Test Cases:**
```python
# tests/services/test_ocr_result_merger.py
import pytest

from app.services.ocr_result_merger import (
    OCRResultMerger,
    ChunkOCRResult,
    MergedOCRResult,
    MergeValidationError,
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
    def test_merges_all_chunks(self, sample_chunk_results):
        merger = OCRResultMerger()
        result = merger.merge_results(sample_chunk_results, "doc-123")

        assert result.chunk_count == 3
        assert result.page_count == 75
        assert result.total_bboxes == 5

    def test_transforms_page_numbers_correctly(self, sample_chunk_results):
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


class TestPageOffsetBoundaries:
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
                    {"page": 25, "reading_order_index": 0}, # -> 50
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
        assert 25 in pages   # Last page of chunk 0
        assert 26 in pages   # First page of chunk 1
        assert 50 in pages   # Last page of chunk 1
        assert 51 in pages   # First page of chunk 2


class TestConfidenceCalculation:
    def test_weighted_average_confidence(self):
        chunks = [
            ChunkOCRResult(
                chunk_index=0, page_start=1, page_end=25,
                bounding_boxes=[], full_text="",
                overall_confidence=0.95, page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1, page_start=26, page_end=50,
                bounding_boxes=[], full_text="",
                overall_confidence=0.85, page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(chunks, "doc-123")

        # (0.95*25 + 0.85*25) / 50 = (23.75 + 21.25) / 50 = 0.90
        assert abs(result.overall_confidence - 0.90) < 0.001


class TestValidation:
    def test_empty_chunks_raises_error(self):
        merger = OCRResultMerger()
        with pytest.raises(MergeValidationError) as exc:
            merger.merge_results([], "doc-123")
        assert exc.value.code == "EMPTY_CHUNKS"

    def test_checksum_mismatch_raises_error(self):
        chunks = [
            ChunkOCRResult(
                chunk_index=0, page_start=1, page_end=25,
                bounding_boxes=[], full_text="",
                overall_confidence=0.9, page_count=25,
                checksum="invalid_checksum",
            ),
        ]

        merger = OCRResultMerger()
        with pytest.raises(MergeValidationError) as exc:
            merger.merge_results(chunks, "doc-123")
        assert exc.value.code == "CHECKSUM_MISMATCH"
```

### References

- [Source: epic-2-pdf-chunking-parallel-processing.md#Story 2.3] - Full AC
- [Source: project-context.md#Backend] - Python patterns
- [Source: Story 16.2] - Depends on PDFChunker

### Previous Story Intelligence

**From Story 16.2:**
- Chunks have 1-based page_start and page_end
- Chunk tuples: (chunk_bytes, page_start, page_end)

**From Existing OCR Pipeline:**
- Bounding boxes have `page` or `page_number` field
- `reading_order_index` is per-page (starts at 0 each page)
- OCR results include `full_text` and `overall_confidence`

### Critical Implementation Notes

**DO NOT:**
- Assume page numbers are 0-based (they are 1-based)
- Modify reading_order_index during merge
- Skip validation for corrupted chunks
- Use global reading_order_index (must be per-page)

**MUST:**
- Sort chunks by chunk_index before merging
- Validate checksums before processing
- Calculate page offset correctly (sum of previous chunks' page counts)
- Preserve all bbox fields except page number
- Log merge statistics for debugging

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

