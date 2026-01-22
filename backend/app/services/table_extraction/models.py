"""Table extraction data models.

Pydantic models for table extraction results and metadata.
"""

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box for table location in document."""

    page: int = Field(..., description="Page number (1-indexed)")
    x: float = Field(..., description="Left coordinate (normalized 0-1)")
    y: float = Field(..., description="Top coordinate (normalized 0-1)")
    width: float = Field(..., description="Width (normalized 0-1)")
    height: float = Field(..., description="Height (normalized 0-1)")


class ExtractedTable(BaseModel):
    """A single extracted table from a document."""

    table_index: int = Field(..., description="Index of table in document (0-based)")
    page_number: int | None = Field(None, description="Page where table appears")
    markdown_content: str = Field(..., description="Table in Markdown format")
    row_count: int = Field(..., ge=0, description="Number of rows including header")
    col_count: int = Field(..., ge=0, description="Number of columns")
    confidence: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Extraction confidence score"
    )
    bounding_box: BoundingBox | None = Field(
        None, description="Location in document for citation highlighting"
    )
    caption: str | None = Field(None, description="Table caption if detected")


class TableExtractionResult(BaseModel):
    """Result of table extraction for a document."""

    document_id: str = Field(..., description="UUID of the source document")
    matter_id: str = Field(..., description="UUID of the matter for isolation")
    tables: list[ExtractedTable] = Field(
        default_factory=list, description="All extracted tables"
    )
    total_tables: int = Field(default=0, description="Count of tables found")
    error: str | None = Field(
        None, description="Error message if extraction failed"
    )
    processing_time_ms: int | None = Field(
        None, description="Time taken for extraction in milliseconds"
    )

    @property
    def has_tables(self) -> bool:
        """Check if any tables were extracted."""
        return self.total_tables > 0

    @property
    def success(self) -> bool:
        """Check if extraction completed without errors."""
        return self.error is None
