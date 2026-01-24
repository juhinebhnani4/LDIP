"""Chunk models for parent-child document chunking.

Pydantic models for chunk creation, storage, and API responses.
Supports the hierarchical parent-child chunking strategy for RAG.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChunkType(str, Enum):
    """Chunk type in the parent-child hierarchy.

    Types:
    - parent: Larger chunks (1500-2000 tokens) for context
    - child: Smaller chunks (400-700 tokens) for retrieval
    """

    PARENT = "parent"
    CHILD = "child"


class ChunkBase(BaseModel):
    """Base chunk properties."""

    content: str = Field(..., description="Text content of the chunk")
    chunk_type: ChunkType = Field(..., description="Type: parent or child")
    chunk_index: int = Field(..., ge=0, description="Order within document")
    token_count: int = Field(..., ge=0, description="Number of tokens")


class ChunkCreate(ChunkBase):
    """Model for creating a chunk record."""

    matter_id: str = Field(..., description="Matter UUID for isolation")
    document_id: str = Field(..., description="Source document UUID")
    parent_chunk_id: str | None = Field(None, description="Parent chunk UUID (for child chunks)")
    page_number: int | None = Field(None, description="Primary page number")
    bbox_ids: list[str] | None = Field(None, description="Linked bounding box UUIDs")


class Chunk(ChunkBase):
    """Complete chunk model returned from API."""

    id: str = Field(..., description="Chunk UUID")
    matter_id: str = Field(..., description="Matter UUID")
    document_id: str = Field(..., description="Source document UUID")
    parent_chunk_id: str | None = Field(None, description="Parent chunk UUID")
    page_number: int | None = Field(None, description="Primary page number")
    bbox_ids: list[str] | None = Field(None, description="Linked bounding box UUIDs")
    entity_ids: list[str] | None = Field(None, description="Extracted entity UUIDs")
    created_at: datetime = Field(..., description="Creation timestamp")


class ChunkListItem(BaseModel):
    """Chunk item for list responses (subset of Chunk)."""

    id: str = Field(..., description="Chunk UUID")
    document_id: str = Field(..., description="Source document UUID")
    chunk_type: ChunkType = Field(..., description="Type: parent or child")
    chunk_index: int = Field(..., description="Order within document")
    token_count: int = Field(..., description="Number of tokens")
    parent_chunk_id: str | None = Field(None, description="Parent chunk UUID")
    page_number: int | None = Field(None, description="Primary page number")
    bbox_ids: list[str] | None = Field(None, description="Linked bounding box UUIDs")


class ChunkWithContent(ChunkListItem):
    """Chunk with full content for retrieval."""

    content: str = Field(..., description="Text content")


# =============================================================================
# API Response Models
# =============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class ChunkStatsMeta(BaseModel):
    """Chunk statistics metadata."""

    total: int = Field(..., ge=0, description="Total number of chunks")
    parent_count: int = Field(..., ge=0, description="Number of parent chunks")
    child_count: int = Field(..., ge=0, description="Number of child chunks")


class ChunkListResponse(BaseModel):
    """API response for chunk list endpoints."""

    data: list[ChunkWithContent]
    meta: ChunkStatsMeta


class ChunkResponse(BaseModel):
    """API response for single chunk retrieval."""

    data: Chunk


class ChunkContextResponse(BaseModel):
    """API response for chunk with surrounding context."""

    data: dict = Field(
        ...,
        description="Contains: chunk, parent (if child), siblings (adjacent chunks)",
    )


# =============================================================================
# Internal Models
# =============================================================================


class ChunkingStatus(str, Enum):
    """Document chunking status.

    Extends document status with chunking-specific states.
    """

    PENDING = "pending"
    CHUNKING = "chunking"
    CHUNKED = "chunked"
    FAILED = "failed"
