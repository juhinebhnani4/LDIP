"""Layout extraction service using Docling.

Extracts document layout structure (paragraphs, headings, tables, figures, stamps)
to enable layout-aware chunking that respects document structure.

This service runs Docling with OCR disabled since we use Google Document AI
for text extraction. We only use Docling for its layout detection capabilities.

Fix Log:
- Issue #1: Improved text extraction from Docling items
- Issue #4: Uses shared Docling converter via docling_provider
- Issue #8: Added logging for unknown block types
- Issue #10: Added Docling version validation (via docling_provider)
"""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

import structlog

from app.core.config import get_settings
from app.services.table_extraction.docling_provider import (
    DoclingProviderError,
    get_docling_converter,
)
from app.services.table_extraction.models import (
    BoundingBox,
    DocumentLayout,
    LayoutBlock,
)

logger = structlog.get_logger(__name__)


# Map Docling's internal block types to our simplified types
BLOCK_TYPE_MAP = {
    "paragraph": "paragraph",
    "text": "paragraph",
    "heading": "heading",
    "title": "heading",
    "section_header": "heading",
    "table": "table",
    "figure": "figure",
    "picture": "figure",
    "image": "figure",
    "list": "list",
    "list_item": "list",
    "code": "code",
    "caption": "caption",
    "footer": "footer",
    "header": "header",
    "page_header": "header",
    "page_footer": "footer",
    "footnote": "footer",
    # Indian legal document specific
    "stamp": "stamp",
    "seal": "stamp",
    "signature": "stamp",
    "attestation": "stamp",
}


class LayoutExtractorError(Exception):
    """Base exception for layout extraction operations."""

    def __init__(
        self,
        message: str,
        code: str = "LAYOUT_EXTRACTION_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class LayoutExtractor:
    """Extract document layout structure using Docling.

    This service provides layout detection to enable layout-aware chunking:
    1. Detects structural elements (paragraphs, headings, tables, stamps, etc.)
    2. Returns bounding boxes for each element
    3. Provides reading order for proper document flow

    Issue #4 fix: Uses shared Docling converter from docling_provider.

    Example:
        >>> extractor = get_layout_extractor()
        >>> layout = extractor.extract_layout(
        ...     file_path=Path("/path/to/doc.pdf"),
        ...     document_id="doc-456",
        ... )
        >>> for block in layout.blocks:
        ...     print(f"{block.block_type} on page {block.page_number}")
    """

    def __init__(self) -> None:
        """Initialize layout extractor."""
        self._settings = get_settings()

    @property
    def converter(self):
        """Get shared Docling converter from provider.

        Issue #4 fix: Uses shared converter to avoid duplicate ML model loading.

        Returns:
            DocumentConverter from shared provider.

        Raises:
            LayoutExtractorError: If Docling cannot be initialized.
        """
        try:
            return get_docling_converter()
        except DoclingProviderError as e:
            raise LayoutExtractorError(
                e.message,
                code=e.code,
                is_retryable=e.is_retryable,
            ) from e

    def extract_layout(
        self,
        file_path: Path,
        document_id: str,
    ) -> DocumentLayout:
        """Extract layout structure from a document.

        This method extracts all structural blocks (paragraphs, headings,
        tables, figures, stamps) with their positions and reading order.

        Issue #6 fix: Changed from async to sync - no async operations used.

        Args:
            file_path: Path to PDF file.
            document_id: Document UUID for logging and result.

        Returns:
            DocumentLayout with all detected blocks.
            On error, returns empty result with error field set.
        """
        start_time = time.time()

        logger.info(
            "layout_extraction_start",
            document_id=document_id,
            file_path=str(file_path),
        )

        # Check if layout extraction is enabled
        if not self._settings.layout_aware_chunking_enabled:
            logger.debug(
                "layout_extraction_disabled",
                document_id=document_id,
            )
            return DocumentLayout(
                document_id=document_id,
                blocks=[],
                page_count=0,
                error="Layout extraction disabled in config",
            )

        # Verify file exists
        if not file_path.exists():
            logger.warning(
                "layout_extraction_file_not_found",
                document_id=document_id,
                file_path=str(file_path),
            )
            return DocumentLayout(
                document_id=document_id,
                blocks=[],
                page_count=0,
                error=f"File not found: {file_path}",
            )

        try:
            # Convert document using Docling
            result = self.converter.convert(str(file_path))
            doc = result.document

            blocks: list[LayoutBlock] = []
            reading_order = 0

            # Extract blocks from document structure
            # Docling provides different access patterns depending on version
            # Try multiple approaches for compatibility

            # Approach 1: Use doc.texts for text items (paragraphs, headings)
            if hasattr(doc, "texts") and doc.texts:
                for item in doc.texts:
                    block = self._process_text_item(item, reading_order)
                    if block:
                        blocks.append(block)
                        reading_order += 1

            # Approach 2: Use doc.tables for table items
            if hasattr(doc, "tables") and doc.tables:
                for item in doc.tables:
                    block = self._process_table_item(item, reading_order)
                    if block:
                        blocks.append(block)
                        reading_order += 1

            # Approach 3: Use doc.pictures for figure items
            if hasattr(doc, "pictures") and doc.pictures:
                for item in doc.pictures:
                    block = self._process_picture_item(item, reading_order)
                    if block:
                        blocks.append(block)
                        reading_order += 1

            # Approach 4: Use doc.furniture for headers/footers
            if hasattr(doc, "furniture") and doc.furniture:
                for item in doc.furniture:
                    block = self._process_furniture_item(item, reading_order)
                    if block:
                        blocks.append(block)
                        reading_order += 1

            # Sort blocks by reading order (should already be, but ensure)
            blocks.sort(key=lambda b: (b.page_number, b.reading_order))

            # Re-assign reading order after sorting
            for idx, block in enumerate(blocks):
                block.reading_order = idx

            # Get page count
            page_count = len(doc.pages) if hasattr(doc, "pages") else 0

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "layout_extraction_complete",
                document_id=document_id,
                block_count=len(blocks),
                page_count=page_count,
                processing_time_ms=processing_time,
            )

            return DocumentLayout(
                document_id=document_id,
                blocks=blocks,
                page_count=page_count,
                processing_time_ms=processing_time,
            )

        except LayoutExtractorError:
            raise  # Re-raise our own errors

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)

            logger.error(
                "layout_extraction_failed",
                document_id=document_id,
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=processing_time,
            )

            # Return empty result instead of failing - graceful degradation
            return DocumentLayout(
                document_id=document_id,
                blocks=[],
                page_count=0,
                error=str(e),
                processing_time_ms=processing_time,
            )

    def _process_text_item(self, item: object, reading_order: int) -> LayoutBlock | None:
        """Process a text item (paragraph, heading) into LayoutBlock.

        Issue #1 fix: Try multiple attributes to extract text content.
        """
        try:
            # Get item type/label
            item_type = self._get_item_type(item)
            block_type = BLOCK_TYPE_MAP.get(item_type.lower(), None)

            # Issue #8: Log unknown block types
            if block_type is None:
                logger.debug(
                    "unknown_block_type_encountered",
                    item_type=item_type,
                    fallback="paragraph",
                )
                block_type = "paragraph"

            # Get page number and bbox
            page_number, bbox = self._extract_provenance(item)
            if bbox is None:
                return None

            # Issue #1 fix: Try multiple attributes for text content
            text_content = self._extract_text_content(item)

            return LayoutBlock(
                block_type=block_type,
                page_number=page_number,
                bbox=bbox,
                reading_order=reading_order,
                confidence=getattr(item, "score", 0.9) or 0.9,
                text_content=text_content,
            )
        except Exception as e:
            logger.debug("text_item_processing_failed", error=str(e))
            return None

    def _process_table_item(self, item: object, reading_order: int) -> LayoutBlock | None:
        """Process a table item into LayoutBlock.

        Issue #1 fix: Extract table markdown content when available.
        """
        try:
            page_number, bbox = self._extract_provenance(item)
            if bbox is None:
                return None

            # Issue #1 fix: Extract table content as markdown
            text_content = self._extract_table_markdown(item)

            return LayoutBlock(
                block_type="table",
                page_number=page_number,
                bbox=bbox,
                reading_order=reading_order,
                confidence=getattr(item, "score", 0.9) or 0.9,
                text_content=text_content,
            )
        except Exception as e:
            logger.debug("table_item_processing_failed", error=str(e))
            return None

    def _process_picture_item(self, item: object, reading_order: int) -> LayoutBlock | None:
        """Process a picture/figure item into LayoutBlock."""
        try:
            page_number, bbox = self._extract_provenance(item)
            if bbox is None:
                return None

            return LayoutBlock(
                block_type="figure",
                page_number=page_number,
                bbox=bbox,
                reading_order=reading_order,
                confidence=getattr(item, "score", 0.9) or 0.9,
            )
        except Exception as e:
            logger.debug("picture_item_processing_failed", error=str(e))
            return None

    def _process_furniture_item(self, item: object, reading_order: int) -> LayoutBlock | None:
        """Process a furniture item (header, footer) into LayoutBlock."""
        try:
            item_type = self._get_item_type(item)
            block_type = BLOCK_TYPE_MAP.get(item_type.lower(), None)

            # Issue #8: Log unknown block types
            if block_type is None:
                logger.debug(
                    "unknown_block_type_encountered",
                    item_type=item_type,
                    fallback="footer",
                )
                block_type = "footer"

            page_number, bbox = self._extract_provenance(item)
            if bbox is None:
                return None

            # Issue #1 fix: Extract text content
            text_content = self._extract_text_content(item)

            return LayoutBlock(
                block_type=block_type,
                page_number=page_number,
                bbox=bbox,
                reading_order=reading_order,
                confidence=getattr(item, "score", 0.9) or 0.9,
                text_content=text_content,
            )
        except Exception as e:
            logger.debug("furniture_item_processing_failed", error=str(e))
            return None

    def _get_item_type(self, item: object) -> str:
        """Extract item type/label from a Docling item."""
        # Try various attribute names used by different Docling versions
        for attr in ["label", "type", "kind", "category", "name"]:
            val = getattr(item, attr, None)
            if val:
                return str(val)
        return "paragraph"

    def _extract_text_content(self, item: object) -> str | None:
        """Extract text content from a Docling item.

        Issue #1 fix: Try multiple attributes to find text content.

        Args:
            item: Docling item (text, paragraph, heading, etc.)

        Returns:
            Text content or None if not available.
        """
        # Try various attribute names used by different Docling versions
        for attr in ["text", "content", "value", "raw_text"]:
            val = getattr(item, attr, None)
            if val and isinstance(val, str) and val.strip():
                return val.strip()

        # Try to get text from nested structure
        if hasattr(item, "children"):
            children_texts = []
            for child in getattr(item, "children", []):
                child_text = self._extract_text_content(child)
                if child_text:
                    children_texts.append(child_text)
            if children_texts:
                return " ".join(children_texts)

        return None

    def _extract_table_markdown(self, item: object) -> str | None:
        """Extract table content as markdown from a Docling TableItem.

        Docling's TableItem.data is a TableData Pydantic model (not a list)
        containing table_cells, num_rows, num_cols, and a computed grid
        property. We use export_to_markdown() as the primary path, with a
        manual grid fallback.

        Args:
            item: Docling TableItem with a .data (TableData) attribute.

        Returns:
            Markdown table string, or None if the table has no text content.
        """
        try:
            # Primary path: use Docling's built-in markdown export
            # This handles cell spanning, headers, and formatting correctly
            export_fn = getattr(item, "export_to_markdown", None)
            if callable(export_fn):
                markdown = export_fn()
                if markdown and markdown.strip():
                    return markdown.strip()

            # Fallback: manually extract from TableData.grid
            table_data = getattr(item, "data", None)
            if table_data is None:
                return None

            grid = getattr(table_data, "grid", None)
            if not grid or len(grid) < 1:
                return None

            # Convert grid (list[list[TableCell]]) to list[list[str]]
            rows: list[list[str]] = []
            for row in grid:
                cells = []
                for cell in row:
                    text = getattr(cell, "text", None) or ""
                    cells.append(text)
                rows.append(cells)

            # Skip tables where all cells are empty (scanned PDF, no native text)
            has_content = any(cell.strip() for row in rows for cell in row)
            if not has_content:
                return None

            from app.services.table_extraction.formatter import TableFormatter

            formatter = TableFormatter()
            return formatter.to_markdown(rows)
        except Exception as e:
            logger.debug("table_markdown_extraction_failed", error=str(e))
            return None

    def _extract_provenance(self, item: object) -> tuple[int, BoundingBox | None]:
        """Extract page number and bounding box from item provenance.

        Args:
            item: Docling item with provenance info.

        Returns:
            Tuple of (page_number, BoundingBox) or (1, None) if not available.
        """
        prov = getattr(item, "prov", None)
        if not prov or len(prov) == 0:
            return 1, None

        first_prov = prov[0]
        page_number = getattr(first_prov, "page_no", 1) or 1

        bbox_obj = getattr(first_prov, "bbox", None)
        if bbox_obj is None:
            return page_number, None

        try:
            # Docling uses l, t, r, b for left, top, right, bottom (normalized 0-1)
            left = getattr(bbox_obj, "l", 0.0)
            top = getattr(bbox_obj, "t", 0.0)
            right = getattr(bbox_obj, "r", 1.0)
            bottom = getattr(bbox_obj, "b", 1.0)

            return page_number, BoundingBox(
                page=page_number,
                x=left,
                y=top,
                width=right - left,
                height=bottom - top,
            )
        except Exception:
            return page_number, None


@lru_cache(maxsize=1)
def get_layout_extractor() -> LayoutExtractor:
    """Get singleton layout extractor instance.

    Returns:
        LayoutExtractor instance.
    """
    return LayoutExtractor()
