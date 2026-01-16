# Story 17.6: Implement Page Offset Validation

Status: ready-for-dev

## Story

As a system ensuring data integrity,
I want validation that all page numbers are absolute (not chunk-relative),
so that citation highlighting and navigation work correctly on large documents.

## Acceptance Criteria

1. **Range Validation**
   - Every bounding_box.page is in range [1, total_page_count]
   - Out-of-range page number raises validation error
   - Validation runs before saving merged results

2. **Offset Application**
   - Bbox from chunk 2 (pages 26-50) with page_offset=25
   - Relative page 1 becomes absolute page 26
   - Relative page 25 becomes absolute page 50

3. **Failure Handling**
   - Validation failure logs specific bbox and expected range
   - Document marked as 'ocr_failed' with data integrity error
   - Clear error message for debugging

4. **Boundary Tests (PRE-MORTEM)**
   - Extra attention to chunk boundary pages (25, 26, 50, 51)
   - First and last page of each chunk explicitly validated
   - Off-by-one errors detected before data corruption

## Tasks / Subtasks

- [ ] Task 1: Create PageOffsetValidator service (AC: #1, #2)
  - [ ] Create validation methods for merged results
  - [ ] Validate all page numbers in range
  - [ ] Apply and validate page offsets

- [ ] Task 2: Integrate validation before save (AC: #1, #3)
  - [ ] Call validator before saving merged bboxes
  - [ ] Handle validation errors appropriately
  - [ ] Update document status on failure

- [ ] Task 3: Add boundary validation (AC: #4)
  - [ ] Specifically test chunk boundary pages
  - [ ] Validate first/last page of each chunk
  - [ ] Log detailed boundary validation results

- [ ] Task 4: Write tests (AC: #1-4)
  - [ ] Test valid page ranges pass
  - [ ] Test invalid pages caught
  - [ ] Test off-by-one at boundaries

## Dev Notes

### Architecture Compliance

**Page Offset Validator:**
```python
# backend/app/services/page_offset_validator.py
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class PageValidationError(Exception):
    """Raised when page number validation fails."""
    def __init__(self, message: str, bbox_id: str | None = None, page: int | None = None):
        self.message = message
        self.bbox_id = bbox_id
        self.page = page
        super().__init__(message)


class PageOffsetValidator:
    """Validates that all page numbers are absolute and in range."""

    def validate_merged_bboxes(
        self,
        bounding_boxes: list[dict],
        total_pages: int,
    ) -> None:
        """Validate all bbox page numbers are in valid range.

        Args:
            bounding_boxes: Merged bboxes with absolute page numbers.
            total_pages: Total pages in original document.

        Raises:
            PageValidationError: If any page is out of range.
        """
        for i, bbox in enumerate(bounding_boxes):
            page = bbox.get("page", bbox.get("page_number"))
            if page is None:
                logger.warning(
                    "bbox_missing_page",
                    index=i,
                    bbox_id=bbox.get("id"),
                )
                continue

            if page < 1 or page > total_pages:
                logger.error(
                    "page_out_of_range",
                    page=page,
                    valid_range=(1, total_pages),
                    bbox_index=i,
                    bbox_id=bbox.get("id"),
                )
                raise PageValidationError(
                    f"Page {page} out of range [1, {total_pages}]",
                    bbox_id=bbox.get("id"),
                    page=page,
                )

        logger.info(
            "page_validation_passed",
            bbox_count=len(bounding_boxes),
            total_pages=total_pages,
        )

    def validate_chunk_boundaries(
        self,
        bounding_boxes: list[dict],
        chunk_specs: list[dict],
    ) -> None:
        """Extra validation for chunk boundary pages.

        Specifically checks pages at chunk boundaries for off-by-one errors.

        Args:
            bounding_boxes: Merged bboxes.
            chunk_specs: List of {chunk_index, page_start, page_end}.
        """
        # Collect boundary pages
        boundary_pages = set()
        for spec in chunk_specs:
            boundary_pages.add(spec["page_start"])
            boundary_pages.add(spec["page_end"])

        # Check that bboxes exist at boundaries
        bbox_pages = {
            bbox.get("page", bbox.get("page_number"))
            for bbox in bounding_boxes
        }

        for boundary in sorted(boundary_pages):
            if boundary not in bbox_pages:
                logger.warning(
                    "no_bbox_at_boundary",
                    boundary_page=boundary,
                    chunk_specs=chunk_specs,
                )

        logger.info(
            "boundary_validation_complete",
            boundary_pages=sorted(boundary_pages),
            found_count=len(boundary_pages & bbox_pages),
        )
```

### Testing Requirements

```python
class TestPageOffsetValidation:
    def test_valid_pages_pass(self):
        validator = PageOffsetValidator()
        bboxes = [
            {"page": 1}, {"page": 25}, {"page": 26}, {"page": 75}
        ]
        # Should not raise
        validator.validate_merged_bboxes(bboxes, total_pages=75)

    def test_page_below_range_fails(self):
        validator = PageOffsetValidator()
        bboxes = [{"page": 0}]  # Invalid - must be >= 1

        with pytest.raises(PageValidationError) as exc:
            validator.validate_merged_bboxes(bboxes, total_pages=75)
        assert exc.value.page == 0

    def test_page_above_range_fails(self):
        validator = PageOffsetValidator()
        bboxes = [{"page": 76}]  # Invalid - only 75 pages

        with pytest.raises(PageValidationError):
            validator.validate_merged_bboxes(bboxes, total_pages=75)

    def test_boundary_pages_validated(self):
        validator = PageOffsetValidator()
        chunk_specs = [
            {"chunk_index": 0, "page_start": 1, "page_end": 25},
            {"chunk_index": 1, "page_start": 26, "page_end": 50},
        ]
        bboxes = [
            {"page": 1}, {"page": 25}, {"page": 26}, {"page": 50}
        ]
        # Should log boundary validation
        validator.validate_chunk_boundaries(bboxes, chunk_specs)
```

### References

- [Source: epic-3-data-integrity-reliability-hardening.md#Story 3.6] - Full AC

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

