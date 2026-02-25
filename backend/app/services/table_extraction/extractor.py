"""Table extraction service using Docling.

Story: RAG Production Gaps - Feature 1
Extracts tables from PDF documents, converts to Markdown,
and links to parent chunks for retrieval.

CRITICAL: This service is designed to NOT fail document ingestion.
If table extraction fails, it returns an empty result with error info.

Fix Log:
- Issue #4: Uses shared Docling converter via docling_provider
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
from app.services.table_extraction.formatter import TableFormatter
from app.services.table_extraction.models import (
    BoundingBox,
    ExtractedTable,
    TableExtractionResult,
)

logger = structlog.get_logger(__name__)


class TableExtractorError(Exception):
    """Base exception for table extraction operations."""

    def __init__(
        self,
        message: str,
        code: str = "TABLE_EXTRACTION_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class TableExtractor:
    """Extract tables from documents using Docling.

    This service integrates with the document ingestion pipeline to:
    1. Extract tables from PDFs using Docling's ML-based detection
    2. Convert tables to Markdown format for LLM consumption
    3. Preserve bounding box info for citation highlighting

    Example:
        >>> extractor = get_table_extractor()
        >>> result = await extractor.extract_tables(
        ...     file_path=Path("/path/to/doc.pdf"),
        ...     matter_id="matter-123",
        ...     document_id="doc-456",
        ... )
        >>> for table in result.tables:
        ...     print(table.markdown_content)
    """

    def __init__(self) -> None:
        """Initialize table extractor."""
        self._formatter = TableFormatter()
        self._settings = get_settings()

    @property
    def converter(self):
        """Get shared Docling converter from provider.

        Issue #4 fix: Uses shared converter to avoid duplicate ML model loading.

        Returns:
            DocumentConverter from shared provider.

        Raises:
            TableExtractorError: If Docling cannot be initialized.
        """
        try:
            return get_docling_converter()
        except DoclingProviderError as e:
            raise TableExtractorError(
                e.message,
                code=e.code,
                is_retryable=e.is_retryable,
            ) from e

    async def extract_tables(
        self,
        file_path: Path,
        matter_id: str,
        document_id: str,
    ) -> TableExtractionResult:
        """Extract all tables from a document.

        This method is designed to be fault-tolerant. If extraction fails,
        it returns an empty result with error information rather than
        raising an exception that would fail the entire ingestion.

        Args:
            file_path: Path to PDF file.
            matter_id: Matter UUID for isolation and logging.
            document_id: Document UUID for linkage.

        Returns:
            TableExtractionResult with all extracted tables.
            On error, returns empty result with error field set.
        """
        start_time = time.time()

        logger.info(
            "table_extraction_start",
            matter_id=matter_id,
            document_id=document_id,
            file_path=str(file_path),
        )

        # Check if table extraction is enabled
        if not self._settings.table_extraction_enabled:
            logger.debug(
                "table_extraction_disabled",
                matter_id=matter_id,
                document_id=document_id,
            )
            return TableExtractionResult(
                document_id=document_id,
                matter_id=matter_id,
                tables=[],
                total_tables=0,
            )

        # Verify file exists
        if not file_path.exists():
            logger.warning(
                "table_extraction_file_not_found",
                matter_id=matter_id,
                document_id=document_id,
                file_path=str(file_path),
            )
            return TableExtractionResult(
                document_id=document_id,
                matter_id=matter_id,
                tables=[],
                total_tables=0,
                error=f"File not found: {file_path}",
            )

        try:
            # Convert document using Docling
            result = self.converter.convert(str(file_path))
            doc = result.document

            tables: list[ExtractedTable] = []

            # Extract each table
            for idx, table in enumerate(doc.tables):
                try:
                    extracted = self._process_table(table, idx)
                    if extracted is not None:
                        tables.append(extracted)
                except Exception as e:
                    logger.warning(
                        "table_processing_failed",
                        matter_id=matter_id,
                        document_id=document_id,
                        table_index=idx,
                        error=str(e),
                    )
                    # Continue with other tables

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "table_extraction_complete",
                matter_id=matter_id,
                document_id=document_id,
                table_count=len(tables),
                processing_time_ms=processing_time,
            )

            return TableExtractionResult(
                document_id=document_id,
                matter_id=matter_id,
                tables=tables,
                total_tables=len(tables),
                processing_time_ms=processing_time,
            )

        except TableExtractorError:
            raise  # Re-raise our own errors

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)

            logger.error(
                "table_extraction_failed",
                matter_id=matter_id,
                document_id=document_id,
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=processing_time,
            )

            # Return empty result instead of failing ingestion
            return TableExtractionResult(
                document_id=document_id,
                matter_id=matter_id,
                tables=[],
                total_tables=0,
                error=str(e),
                processing_time_ms=processing_time,
            )

    def _process_table(self, table: object, idx: int) -> ExtractedTable | None:
        """Process a single Docling TableItem into ExtractedTable.

        Docling's TableItem.data is a TableData Pydantic model containing
        table_cells, num_rows, num_cols, and a computed grid property.

        Args:
            table: Docling TableItem with .data (TableData) and optional
                   .export_to_markdown() method.
            idx: Table index in document.

        Returns:
            ExtractedTable or None if table is empty/invalid.
        """
        # Extract markdown using Docling's export or manual grid extraction
        markdown = None
        num_rows = 0
        num_cols = 0

        # Primary path: Docling's built-in markdown export
        export_fn = getattr(table, "export_to_markdown", None)
        if callable(export_fn):
            try:
                md = export_fn()
                if md and md.strip():
                    markdown = md.strip()
            except Exception:
                pass  # Fall through to grid-based extraction

        # Fallback: extract from TableData.grid manually
        if not markdown:
            table_data = getattr(table, "data", None)
            if table_data is None:
                return None

            grid = getattr(table_data, "grid", None)
            if not grid or len(grid) < 2:  # Need at least header + 1 row
                return None

            # Convert grid (list[list[TableCell]]) to list[list[str]]
            rows: list[list[str]] = []
            for row in grid:
                cells = [getattr(cell, "text", None) or "" for cell in row]
                rows.append(cells)

            # Skip tables where all cells are empty
            if not any(cell.strip() for row in rows for cell in row):
                return None

            markdown = self._formatter.to_markdown(rows)
            if not markdown:
                return None

        # Get row/col counts from TableData if available
        table_data = getattr(table, "data", None)
        if table_data:
            num_rows = getattr(table_data, "num_rows", 0) or 0
            num_cols = getattr(table_data, "num_cols", 0) or 0

        # Extract bounding box if available
        bbox = self._extract_bbox(table)

        # Get page number
        page_number = None
        prov = getattr(table, "prov", None)
        if prov and len(prov) > 0:
            page_number = getattr(prov[0], "page_no", None)

        # Get confidence score
        confidence = getattr(table, "score", 0.9)
        if confidence is None:
            confidence = 0.9

        # Get caption if available
        caption = getattr(table, "caption", None)

        return ExtractedTable(
            table_index=idx,
            page_number=page_number,
            markdown_content=markdown,
            row_count=num_rows,
            col_count=num_cols,
            confidence=confidence,
            bounding_box=bbox,
            caption=caption,
        )

    def _extract_bbox(self, table: object) -> BoundingBox | None:
        """Extract bounding box from table provenance.

        Args:
            table: Docling Table object.

        Returns:
            BoundingBox or None if not available.
        """
        prov = getattr(table, "prov", None)
        if not prov or len(prov) == 0:
            return None

        first_prov = prov[0]
        bbox_obj = getattr(first_prov, "bbox", None)
        if bbox_obj is None:
            return None

        try:
            return BoundingBox(
                page=getattr(first_prov, "page_no", 1) or 1,
                x=getattr(bbox_obj, "l", 0.0),
                y=getattr(bbox_obj, "t", 0.0),
                width=getattr(bbox_obj, "r", 1.0) - getattr(bbox_obj, "l", 0.0),
                height=getattr(bbox_obj, "b", 1.0) - getattr(bbox_obj, "t", 0.0),
            )
        except Exception:
            return None


@lru_cache(maxsize=1)
def get_table_extractor() -> TableExtractor:
    """Get singleton table extractor instance.

    Returns:
        TableExtractor instance.
    """
    return TableExtractor()
