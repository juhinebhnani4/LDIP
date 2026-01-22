"""Inspector/Debug mode models for RAG pipeline debugging.

Story: RAG Production Gaps - Feature 3: Inspector Mode
Provides detailed timing and scoring information for search debugging.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Debug Info Models
# =============================================================================


class TimingBreakdown(BaseModel):
    """Detailed timing breakdown for search operations."""

    embedding_ms: float | None = Field(None, description="Time to generate query embedding")
    bm25_search_ms: float | None = Field(None, description="BM25 search time")
    semantic_search_ms: float | None = Field(None, description="Semantic/vector search time")
    rrf_fusion_ms: float | None = Field(None, description="RRF score fusion time")
    rerank_ms: float | None = Field(None, description="Cohere reranking time")
    total_ms: float = Field(..., description="Total search time")


class ChunkDebugInfo(BaseModel):
    """Debug information for a single chunk result."""

    chunk_id: str = Field(..., description="Chunk UUID")
    document_id: str = Field(..., description="Document UUID")
    document_name: str | None = Field(None, description="Document filename")
    page_number: int | None = Field(None, description="Page number")
    chunk_type: str = Field(..., description="parent or child")

    # Ranking info
    bm25_rank: int | None = Field(None, description="Position in BM25 results (1-indexed)")
    bm25_score: float | None = Field(None, description="Raw BM25 score")
    semantic_rank: int | None = Field(None, description="Position in semantic results (1-indexed)")
    semantic_score: float | None = Field(None, description="Cosine similarity score (0-1)")
    rrf_score: float = Field(..., description="Combined RRF score")
    rrf_rank: int = Field(..., description="Position after RRF fusion (1-indexed)")

    # Reranker info (if used)
    rerank_score: float | None = Field(None, description="Cohere relevance score (0-1)")
    rerank_rank: int | None = Field(None, description="Position after reranking (1-indexed)")

    # Content preview
    content_preview: str = Field(..., description="First 200 chars of content")
    token_count: int = Field(..., description="Number of tokens")


class SearchDebugInfo(BaseModel):
    """Debug information for a complete search operation."""

    timing: TimingBreakdown = Field(..., description="Timing breakdown")
    query: str = Field(..., description="Original query")
    expanded_query: str | None = Field(None, description="Query after alias expansion")
    embedding_model: str = Field(..., description="Embedding model used")

    # Search config
    bm25_weight: float = Field(..., description="BM25 weight")
    semantic_weight: float = Field(..., description="Semantic weight")
    top_k_bm25: int = Field(..., description="Top K for BM25")
    top_k_semantic: int = Field(..., description="Top K for semantic")
    k_constant: int = Field(60, description="RRF k constant")

    # Reranking
    rerank_requested: bool = Field(..., description="Was reranking requested")
    rerank_used: bool = Field(..., description="Was reranking actually used")
    rerank_model: str | None = Field(None, description="Reranking model")
    rerank_top_n: int | None = Field(None, description="Top N after reranking")
    rerank_fallback_reason: str | None = Field(None, description="Why reranking failed/skipped")

    # Results
    bm25_results_count: int = Field(..., description="Results from BM25")
    semantic_results_count: int = Field(..., description="Results from semantic")
    fused_results_count: int = Field(..., description="Results after fusion")
    final_results_count: int = Field(..., description="Final results returned")

    # Per-chunk debug
    chunks: list[ChunkDebugInfo] = Field(..., description="Debug info per chunk")


# =============================================================================
# Inspector API Response Models
# =============================================================================


class InspectorSearchRequest(BaseModel):
    """Request for inspector search with full debug output."""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    limit: int = Field(20, ge=1, le=100, description="Max results")
    bm25_weight: float = Field(1.0, ge=0.0, le=2.0, description="BM25 weight")
    semantic_weight: float = Field(1.0, ge=0.0, le=2.0, description="Semantic weight")
    rerank: bool = Field(True, description="Use Cohere reranking")
    rerank_top_n: int = Field(5, ge=1, le=20, description="Top N after reranking")
    expand_aliases: bool = Field(True, description="Expand entity aliases")


class InspectorSearchResponse(BaseModel):
    """Response with full debug information."""

    data: list[dict[str, Any]] = Field(..., description="Search results (standard format)")
    meta: dict[str, Any] = Field(..., description="Search metadata")
    debug: SearchDebugInfo = Field(..., description="Full debug information")


# =============================================================================
# Dashboard/History Models
# =============================================================================


class SearchHistoryItem(BaseModel):
    """Historical search record for inspector dashboard."""

    id: str = Field(..., description="Search log UUID")
    matter_id: str = Field(..., description="Matter UUID")
    query: str = Field(..., description="Search query")
    result_count: int = Field(..., description="Number of results")
    total_time_ms: float = Field(..., description="Total search time")
    rerank_used: bool = Field(..., description="Was reranking used")
    created_at: datetime = Field(..., description="When search was performed")

    # Optional expanded info
    timing: TimingBreakdown | None = Field(None, description="Timing breakdown")


class InspectorDashboardStats(BaseModel):
    """Aggregate stats for inspector dashboard."""

    total_searches: int = Field(..., description="Total searches performed")
    avg_latency_ms: float = Field(..., description="Average search latency")
    p95_latency_ms: float = Field(..., description="95th percentile latency")
    rerank_usage_rate: float = Field(..., description="% of searches using reranking")
    avg_results_per_query: float = Field(..., description="Average results returned")

    # Breakdown by type
    searches_last_hour: int = Field(..., description="Searches in last hour")
    searches_last_day: int = Field(..., description="Searches in last 24 hours")
