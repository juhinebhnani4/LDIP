"""OCR Result Merger Service for combining chunked OCR results.

Story 16.3: Implement OCR Result Merger Service
Story 17.6: Page Offset Validation

Transforms chunk-relative page numbers to absolute page numbers
and validates data integrity post-merge.
"""

import hashlib
from functools import lru_cache

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
    """OCR result from a single chunk.

    Contains chunk-relative page numbers in bounding boxes.

    Attributes:
        chunk_index: Zero-based index of this chunk.
        page_start: First page in chunk (1-based, absolute in document).
        page_end: Last page in chunk (1-based, absolute in document).
        bounding_boxes: List of bboxes with chunk-relative page numbers.
        full_text: Extracted text from this chunk.
        overall_confidence: OCR confidence score (0.0-1.0).
        page_count: Number of pages in this chunk.
        checksum: Optional SHA256 checksum for validation.
    """

    chunk_index: int = Field(..., alias="chunkIndex")
    page_start: int = Field(..., alias="pageStart")
    page_end: int = Field(..., alias="pageEnd")
    bounding_boxes: list[dict] = Field(default_factory=list, alias="boundingBoxes")
    full_text: str = Field(default="", alias="fullText")
    overall_confidence: float = Field(..., alias="overallConfidence")
    page_count: int = Field(..., alias="pageCount")
    checksum: str | None = None

    model_config = {"populate_by_name": True}


class MergedOCRResult(BaseModel):
    """Final merged OCR result with absolute page numbers.

    All bounding boxes have been transformed from chunk-relative
    to document-absolute page numbers.

    Attributes:
        document_id: Parent document UUID.
        bounding_boxes: All bboxes with absolute page numbers.
        full_text: Concatenated text from all chunks.
        overall_confidence: Weighted average confidence.
        page_count: Total pages across all chunks.
        chunk_count: Number of chunks merged.
        total_bboxes: Total bounding boxes in result.
    """

    document_id: str = Field(..., alias="documentId")
    bounding_boxes: list[dict] = Field(default_factory=list, alias="boundingBoxes")
    full_text: str = Field(default="", alias="fullText")
    overall_confidence: float = Field(..., alias="overallConfidence")
    page_count: int = Field(..., alias="pageCount")
    chunk_count: int = Field(..., alias="chunkCount")
    total_bboxes: int = Field(..., alias="totalBboxes")

    model_config = {"populate_by_name": True}


class OCRResultMerger:
    """Service for merging chunked OCR results.

    Transforms chunk-relative page numbers to absolute page numbers
    and validates data integrity post-merge.

    Page Offset Calculation:
    - Chunk 0 (pages 1-25): offset=0, bbox page 5 -> absolute page 5
    - Chunk 1 (pages 26-50): offset=25, bbox page 5 -> absolute page 30
    - Chunk 2 (pages 51-75): offset=50, bbox page 5 -> absolute page 55

    Example:
        >>> merger = OCRResultMerger()
        >>> result = merger.merge_results(chunk_results, "doc-123")
        >>> print(f"Merged {result.chunk_count} chunks, {result.total_bboxes} bboxes")
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

        # Story 17.6: Validate page ranges are contiguous and correct
        self._validate_page_ranges(sorted_results)

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
        weighted_confidence = (
            sum(c.overall_confidence * c.page_count for c in sorted_results) / total_pages
            if total_pages > 0
            else 0.0
        )

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

        The bounding boxes come with page numbers relative to the chunk
        (e.g., page 1-25 for chunk 0). This transforms them to absolute
        page numbers in the full document.

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
            # Handle both "page" and "page_number" field names
            relative_page = bbox.get("page", bbox.get("page_number", 1))
            absolute_page = relative_page + page_offset

            new_bbox["page"] = absolute_page
            new_bbox["page_number"] = absolute_page  # Alias for compatibility

            transformed.append(new_bbox)

        return transformed

    def _merge_text(self, chunk_results: list[ChunkOCRResult]) -> str:
        """Merge full text from chunks with page separators.

        Preserves page breaks between chunks to maintain document
        structure in the merged text.

        Args:
            chunk_results: List of chunk results in order.

        Returns:
            Concatenated full text with page separators.
        """
        texts = []
        for chunk in chunk_results:
            if chunk.full_text:
                texts.append(chunk.full_text)
        return "\n\n".join(texts)

    def _validate_page_ranges(self, chunk_results: list[ChunkOCRResult]) -> None:
        """Validate chunk page ranges are contiguous and correct.

        Story 17.6: Page Offset Validation

        Ensures:
        1. Chunk indices are sequential (0, 1, 2, ...)
        2. Page ranges are contiguous (chunk N ends where chunk N+1 starts)
        3. Page numbers are positive
        4. page_start <= page_end within each chunk

        Args:
            chunk_results: List of chunk results sorted by chunk_index.

        Raises:
            MergeValidationError: If page ranges are invalid.
        """
        if not chunk_results:
            return

        errors = []

        # Check first chunk starts at page 1
        first_chunk = chunk_results[0]
        if first_chunk.page_start != 1:
            errors.append(
                f"First chunk starts at page {first_chunk.page_start}, expected 1"
            )

        for i, chunk in enumerate(chunk_results):
            # Validate chunk_index is sequential
            if chunk.chunk_index != i:
                errors.append(
                    f"Chunk at position {i} has chunk_index {chunk.chunk_index}, expected {i}"
                )

            # Validate page_start <= page_end
            if chunk.page_start > chunk.page_end:
                errors.append(
                    f"Chunk {chunk.chunk_index}: page_start ({chunk.page_start}) > "
                    f"page_end ({chunk.page_end})"
                )

            # Validate page numbers are positive
            if chunk.page_start < 1 or chunk.page_end < 1:
                errors.append(
                    f"Chunk {chunk.chunk_index}: invalid page numbers "
                    f"({chunk.page_start}-{chunk.page_end})"
                )

            # Validate page_count matches page range
            expected_page_count = chunk.page_end - chunk.page_start + 1
            if chunk.page_count != expected_page_count:
                logger.warning(
                    "page_count_mismatch",
                    chunk_index=chunk.chunk_index,
                    expected=expected_page_count,
                    actual=chunk.page_count,
                )

            # Validate contiguity with previous chunk
            if i > 0:
                prev_chunk = chunk_results[i - 1]
                expected_start = prev_chunk.page_end + 1
                if chunk.page_start != expected_start:
                    errors.append(
                        f"Chunk {chunk.chunk_index} starts at page {chunk.page_start}, "
                        f"expected {expected_start} (after chunk {prev_chunk.chunk_index} "
                        f"ending at {prev_chunk.page_end})"
                    )

        if errors:
            error_msg = "; ".join(errors)
            logger.error(
                "page_range_validation_failed",
                errors=errors,
                chunk_count=len(chunk_results),
            )
            raise MergeValidationError(
                f"Page range validation failed: {error_msg}",
                code="PAGE_RANGE_INVALID",
            )

        logger.debug(
            "page_ranges_validated",
            chunk_count=len(chunk_results),
            first_page=chunk_results[0].page_start,
            last_page=chunk_results[-1].page_end,
        )

    def _validate_checksum(self, chunk: ChunkOCRResult) -> None:
        """Validate chunk result checksum.

        Recomputes checksum from chunk data and compares with stored value.
        This detects corruption during storage/retrieval.

        Args:
            chunk: Chunk result with checksum.

        Raises:
            MergeValidationError: If checksum doesn't match.
        """
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
        """Validate merged result integrity.

        Performs post-merge validation checks:
        1. Bbox count matches sum of chunk bboxes
        2. Page numbers are reasonable (warns on missing)
        3. No duplicate reading_order_index on same page (warns)

        Args:
            result: Merged OCR result.
            chunk_results: Original chunk results.

        Raises:
            MergeValidationError: If critical validation fails.
        """
        # Validate bbox count
        expected_bboxes = sum(len(c.bounding_boxes) for c in chunk_results)
        if result.total_bboxes != expected_bboxes:
            raise MergeValidationError(
                f"Bbox count mismatch: {result.total_bboxes} != {expected_bboxes}",
                code="BBOX_COUNT_MISMATCH",
            )

        # Validate page numbers are reasonable (warn only, don't fail)
        pages_seen = set()
        for bbox in result.bounding_boxes:
            page = bbox.get("page", bbox.get("page_number"))
            if page is not None:
                pages_seen.add(page)

        if pages_seen:
            expected_pages = set(range(1, result.page_count + 1))
            missing = expected_pages - pages_seen

            # Allow some pages without bboxes (blank pages), but warn if many
            if missing and len(missing) > result.page_count * 0.1:
                logger.warning(
                    "merge_pages_missing",
                    missing_count=len(missing),
                    total_pages=result.page_count,
                )

        # Check for duplicate reading_order_index on same page (warn only)
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

    def compute_chunk_checksum(self, chunk: ChunkOCRResult) -> str:
        """Compute checksum for a chunk result.

        Use this when storing chunk results to enable validation
        during merge.

        Args:
            chunk: Chunk result to checksum.

        Returns:
            SHA256 checksum (first 16 chars).
        """
        data = f"{chunk.chunk_index}:{chunk.page_start}:{chunk.page_end}:{len(chunk.bounding_boxes)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@lru_cache(maxsize=1)
def get_ocr_result_merger() -> OCRResultMerger:
    """Get singleton OCRResultMerger instance.

    Returns:
        OCRResultMerger instance.
    """
    return OCRResultMerger()
