"""Rerank models for Cohere Rerank API.

Defines request/response models for the rerank endpoints.
These models extend the existing search models with relevance_score
from Cohere Rerank v3.5.
"""

from pydantic import BaseModel, Field


class RerankRequest(BaseModel):
    """Request model for rerank search.

    Uses hybrid search internally to get candidates, then reranks
    with Cohere Rerank v3.5.
    """

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
        description="Number of hybrid search candidates (before reranking)",
    )
    top_n: int = Field(
        3,
        ge=1,
        le=20,
        description="Number of top results to return after reranking",
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


class RerankedSearchResultItem(BaseModel):
    """Single reranked search result item.

    Extends SearchResultItem with relevance_score from Cohere.
    """

    id: str = Field(..., description="Chunk UUID")
    document_id: str = Field(..., description="Source document UUID")
    content: str = Field(..., description="Chunk text content")
    page_number: int | None = Field(None, description="Source page number")
    chunk_type: str = Field(..., description="Chunk type: 'parent' or 'child'")
    token_count: int = Field(..., description="Number of tokens in chunk")
    bm25_rank: int | None = Field(None, description="Rank from BM25 search")
    semantic_rank: int | None = Field(None, description="Rank from semantic search")
    rrf_score: float = Field(..., description="Combined RRF fusion score")
    relevance_score: float | None = Field(
        None,
        description="Cohere relevance score (0.0-1.0). None if fallback to RRF.",
    )


class RerankedSearchMeta(BaseModel):
    """Metadata about reranked search results."""

    query: str = Field(..., description="Original search query")
    matter_id: str = Field(..., description="Matter UUID searched")
    total_candidates: int = Field(
        ...,
        description="Total candidates from hybrid search before reranking",
    )
    bm25_weight: float = Field(..., description="BM25 weight used")
    semantic_weight: float = Field(..., description="Semantic weight used")
    rerank_used: bool = Field(
        ...,
        description="True if Cohere reranking was successful, False if fallback to RRF",
    )
    fallback_reason: str | None = Field(
        None,
        description="Reason for fallback if rerank_used is False",
    )


class RerankedSearchResponse(BaseModel):
    """Response model for reranked search.

    Returns top-N most relevant documents after Cohere reranking.
    If Cohere API fails, falls back to top-N RRF-ranked results.
    """

    data: list[RerankedSearchResultItem] = Field(..., description="Reranked results")
    meta: RerankedSearchMeta = Field(..., description="Search metadata")
