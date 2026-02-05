"""Table extraction and layout detection data models.

Pydantic models for table extraction results, layout detection, and metadata.
"""

from uuid import UUID, uuid4

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


# Layout detection models for layout-aware chunking


class LayoutBlock(BaseModel):
    """A structural block detected by Docling's layout analysis.

    Represents a single semantic element (paragraph, heading, table, etc.)
    with its position and type information.
    """

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this block (used for source tracking in chunks)",
    )
    block_type: str = Field(
        ...,
        description="Type of block: paragraph, heading, table, figure, stamp, caption, list, code, footer, header",
    )
    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    bbox: BoundingBox = Field(..., description="Bounding box of the block")
    text_start: int | None = Field(
        None, ge=0, description="Character offset start in full document text"
    )
    text_end: int | None = Field(
        None, ge=0, description="Character offset end in full document text"
    )
    reading_order: int = Field(
        ..., ge=0, description="Reading order index within document"
    )
    confidence: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Detection confidence score"
    )
    text_content: str | None = Field(
        None, description="Text content of this block (if extracted by Docling)"
    )


class DocumentLayout(BaseModel):
    """Layout map for a document extracted by Docling.

    Contains all detected structural blocks with their positions,
    enabling layout-aware chunking that respects document structure.
    """

    document_id: str = Field(..., description="UUID of the source document")
    blocks: list[LayoutBlock] = Field(
        default_factory=list, description="All detected layout blocks"
    )
    page_count: int = Field(default=0, ge=0, description="Total number of pages")
    processing_time_ms: int | None = Field(
        None, description="Time taken for layout extraction in milliseconds"
    )
    error: str | None = Field(
        None, description="Error message if extraction failed"
    )

    @property
    def success(self) -> bool:
        """Check if layout extraction completed without errors."""
        return self.error is None

    @property
    def has_blocks(self) -> bool:
        """Check if any blocks were detected."""
        return len(self.blocks) > 0

    def get_blocks_for_page(self, page_number: int) -> list[LayoutBlock]:
        """Get all blocks on a specific page."""
        return [b for b in self.blocks if b.page_number == page_number]

    def get_blocks_by_type(self, block_type: str) -> list[LayoutBlock]:
        """Get all blocks of a specific type."""
        return [b for b in self.blocks if b.block_type == block_type]
