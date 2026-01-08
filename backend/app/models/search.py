"""Search models for Hybrid Search API.

Defines request/response models for the search endpoints.
All search operations are matter-isolated via the API layer.
"""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request model for hybrid search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        examples=["contract termination clause"],
    )
    limit: int = Field(
        20,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )
    bm25_weight: float = Field(
        1.0,
        ge=0.0,
        le=2.0,
        description="Weight for BM25 keyword search (0.0-2.0)",
    )
    semantic_weight: float = Field(
        1.0,
        ge=0.0,
        le=2.0,
        description="Weight for semantic similarity search (0.0-2.0)",
    )


class SearchResultItem(BaseModel):
    """Single search result item."""

    id: str = Field(..., description="Chunk UUID")
    document_id: str = Field(..., description="Source document UUID")
    content: str = Field(..., description="Chunk text content")
    page_number: int | None = Field(None, description="Source page number")
    chunk_type: str = Field(..., description="Chunk type: 'parent' or 'child'")
    token_count: int = Field(..., description="Number of tokens in chunk")
    bm25_rank: int | None = Field(None, description="Rank from BM25 search")
    semantic_rank: int | None = Field(None, description="Rank from semantic search")
    rrf_score: float = Field(..., description="Combined RRF fusion score")


class SearchMeta(BaseModel):
    """Metadata about the search results."""

    query: str = Field(..., description="Original search query")
    matter_id: str = Field(..., description="Matter UUID searched")
    total_candidates: int = Field(..., description="Total candidates before limit")
    bm25_weight: float = Field(..., description="BM25 weight used")
    semantic_weight: float = Field(..., description="Semantic weight used")


class SearchResponse(BaseModel):
    """Response model for hybrid search."""

    data: list[SearchResultItem] = Field(..., description="Search results")
    meta: SearchMeta = Field(..., description="Search metadata")


class BM25SearchRequest(BaseModel):
    """Request model for BM25-only keyword search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        examples=["Section 138 NI Act"],
    )
    limit: int = Field(
        30,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )


class SemanticSearchRequest(BaseModel):
    """Request model for semantic-only vector search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        examples=["breach of contract remedies"],
    )
    limit: int = Field(
        30,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )


class SingleModeSearchMeta(BaseModel):
    """Metadata for single-mode search results."""

    query: str = Field(..., description="Original search query")
    matter_id: str = Field(..., description="Matter UUID searched")
    result_count: int = Field(..., description="Number of results returned")
    search_type: str = Field(..., description="Search type: 'bm25' or 'semantic'")


class SingleModeSearchResponse(BaseModel):
    """Response model for BM25 or semantic-only search."""

    data: list[SearchResultItem] = Field(..., description="Search results")
    meta: SingleModeSearchMeta = Field(..., description="Search metadata")
