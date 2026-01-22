"""Table extraction Pydantic models.

Story: RAG Production Gaps - Feature 1: Table Extraction
API response models for table endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TableBoundingBox(BaseModel):
    """Bounding box for table location in document."""

    page: int = Field(..., description="Page number (1-indexed)")
    x: float = Field(..., description="Left coordinate (normalized 0-1)")
    y: float = Field(..., description="Top coordinate (normalized 0-1)")
    width: float = Field(..., description="Width (normalized 0-1)")
    height: float = Field(..., description="Height (normalized 0-1)")


class TableData(BaseModel):
    """Table data from database."""

    id: str = Field(..., description="Table UUID")
    document_id: str = Field(..., description="Source document UUID")
    matter_id: str = Field(..., description="Matter UUID for isolation")
    table_index: int = Field(..., description="Index of table in document (0-based)")
    page_number: int | None = Field(None, description="Page where table appears")
    markdown_content: str = Field(..., description="Table in Markdown format")
    json_content: list[dict[str, Any]] | None = Field(
        None, description="JSON representation (list of row dicts)"
    )
    row_count: int = Field(..., description="Number of rows including header")
    col_count: int = Field(..., description="Number of columns")
    confidence: float = Field(..., description="Extraction confidence (0-1)")
    bounding_box: TableBoundingBox | None = Field(
        None, description="Location for citation highlighting"
    )
    caption: str | None = Field(None, description="Table caption if detected")
    created_at: datetime = Field(..., description="Extraction timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class TableListMeta(BaseModel):
    """Pagination metadata for table list."""

    total: int = Field(..., description="Total number of tables")
    page: int = Field(..., description="Current page (1-indexed)")
    per_page: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


class TableListResponse(BaseModel):
    """Response for table list endpoint."""

    data: list[dict[str, Any]] = Field(..., description="List of tables")
    meta: TableListMeta = Field(..., description="Pagination metadata")


class TableResponse(BaseModel):
    """Response for single table endpoint."""

    data: dict[str, Any] = Field(..., description="Table data")


class TableStats(BaseModel):
    """Table extraction statistics for a matter."""

    total_tables: int = Field(..., description="Total tables extracted")
    documents_with_tables: int = Field(..., description="Documents containing tables")
    avg_confidence: float = Field(..., description="Average extraction confidence")
    avg_rows: float = Field(..., description="Average rows per table")
    avg_cols: float = Field(..., description="Average columns per table")
    low_confidence_count: int = Field(..., description="Tables with confidence < 0.7")
