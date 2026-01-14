"""Hybrid Search Service combining BM25 and semantic search with RRF fusion.

This module implements the hybrid search pattern for the RAG pipeline:
1. BM25 keyword search via PostgreSQL tsvector
2. Semantic search via pgvector HNSW index
3. Reciprocal Rank Fusion (RRF) for result merging
4. Optional Cohere Rerank v3.5 for top-N refinement

CRITICAL: All search operations enforce 4-layer matter isolation.
The matter_id parameter is MANDATORY for every search query.
"""

from dataclasses import dataclass
from functools import lru_cache

import structlog

from app.services.rag.embedder import EmbeddingService, get_embedding_service
from app.services.rag.namespace import validate_namespace, validate_search_results
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)

# Default limits for rerank pipeline
DEFAULT_HYBRID_LIMIT = 20
DEFAULT_RERANK_TOP_N = 3


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SearchWeights:
    """Weights for hybrid search components.

    Attributes:
        bm25: Weight for BM25 keyword search results (0.0-2.0).
        semantic: Weight for semantic similarity results (0.0-2.0).

    Example:
        >>> weights = SearchWeights(bm25=1.0, semantic=1.5)
        >>> weights.bm25
        1.0
    """
    bm25: float = 1.0
    semantic: float = 1.0

    def __post_init__(self) -> None:
        """Validate weight values after initialization."""
        if not 0 <= self.bm25 <= 2:
            raise ValueError("bm25 weight must be between 0 and 2")
        if not 0 <= self.semantic <= 2:
            raise ValueError("semantic weight must be between 0 and 2")


@dataclass
class SearchResult:
    """Single hybrid search result.

    Attributes:
        id: Chunk UUID.
        matter_id: Matter UUID (for isolation verification).
        document_id: Source document UUID.
        content: Chunk text content.
        page_number: Source page number (for highlighting).
        chunk_type: 'parent' or 'child'.
        token_count: Number of tokens in chunk.
        bm25_rank: Rank from BM25 search (None if not in BM25 results).
        semantic_rank: Rank from semantic search (None if not in semantic results).
        rrf_score: Combined RRF fusion score.
    """
    id: str
    matter_id: str
    document_id: str
    content: str
    page_number: int | None
    chunk_type: str
    token_count: int
    bm25_rank: int | None
    semantic_rank: int | None
    rrf_score: float


@dataclass
class HybridSearchResult:
    """Hybrid search response container.

    Attributes:
        results: List of ranked search results.
        query: Original search query.
        matter_id: Matter UUID for isolation verification.
        weights: Weights used for this search.
        total_candidates: Total number of candidates before limit.
    """
    results: list[SearchResult]
    query: str
    matter_id: str
    weights: SearchWeights
    total_candidates: int


@dataclass
class RerankedSearchResultItem:
    """Single reranked search result.

    Extends SearchResult with Cohere relevance_score.

    Attributes:
        id: Chunk UUID.
        matter_id: Matter UUID (for isolation verification).
        document_id: Source document UUID.
        content: Chunk text content.
        page_number: Source page number (for highlighting).
        chunk_type: 'parent' or 'child'.
        token_count: Number of tokens in chunk.
        bm25_rank: Rank from BM25 search (None if not in BM25 results).
        semantic_rank: Rank from semantic search (None if not in semantic results).
        rrf_score: Combined RRF fusion score.
        relevance_score: Cohere relevance score (None if fallback to RRF).
    """
    id: str
    matter_id: str
    document_id: str
    content: str
    page_number: int | None
    chunk_type: str
    token_count: int
    bm25_rank: int | None
    semantic_rank: int | None
    rrf_score: float
    relevance_score: float | None


@dataclass
class RerankedSearchResult:
    """Reranked search response container.

    Attributes:
        results: List of reranked search results with relevance_score.
        query: Original search query.
        matter_id: Matter UUID for isolation verification.
        weights: Weights used for hybrid search.
        total_candidates: Total candidates from hybrid search before reranking.
        rerank_used: True if Cohere reranking was successful.
        fallback_reason: Reason for fallback if rerank_used is False.
    """
    results: list[RerankedSearchResultItem]
    query: str
    matter_id: str
    weights: SearchWeights
    total_candidates: int
    rerank_used: bool
    fallback_reason: str | None


class HybridSearchServiceError(Exception):
    """Exception for hybrid search service errors."""

    def __init__(
        self,
        message: str,
        code: str = "SEARCH_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


# =============================================================================
# Hybrid Search Service
# =============================================================================

class HybridSearchService:
    """Service for hybrid BM25 + semantic search with RRF fusion.

    Combines keyword-based BM25 search with vector similarity search
    using Reciprocal Rank Fusion to merge results. This provides
    the best of both worlds:
    - BM25: Exact term matching (e.g., "Section 138 NI Act")
    - Semantic: Conceptual similarity (e.g., "contract breach remedies")

    CRITICAL: All searches are matter-isolated. The matter_id
    parameter is validated and enforced at multiple layers.

    Example:
        >>> service = HybridSearchService()
        >>> result = await service.search(
        ...     query="contract termination clause",
        ...     matter_id="abc-123-def-456",
        ...     limit=20,
        ... )
        >>> len(result.results) <= 20
        True
    """

    def __init__(
        self,
        embedder: EmbeddingService | None = None,
    ):
        """Initialize hybrid search service.

        Args:
            embedder: Optional EmbeddingService instance. Uses default if not provided.
        """
        self.embedder = embedder or get_embedding_service()

    async def search(
        self,
        query: str,
        matter_id: str,
        limit: int = 20,
        weights: SearchWeights | None = None,
        rrf_k: int = 60,
    ) -> HybridSearchResult:
        """Execute hybrid search with RRF fusion.

        Combines BM25 keyword search with semantic similarity search
        using Reciprocal Rank Fusion. Returns top N candidates
        suitable for downstream reranking (e.g., Cohere Rerank).

        Args:
            query: Search query text.
            matter_id: REQUIRED - matter UUID for isolation.
            limit: Max results to return (default 20 for reranking).
            weights: Optional custom weights for BM25/semantic.
            rrf_k: RRF smoothing constant (default 60, industry standard).

        Returns:
            HybridSearchResult with ranked results.

        Raises:
            HybridSearchServiceError: If search fails.
            ValueError: If matter_id is invalid.

        Example:
            >>> result = await service.search(
            ...     "Section 138 negotiable instrument",
            ...     matter_id="abc-123",
            ...     weights=SearchWeights(bm25=1.5, semantic=1.0),
            ... )
        """
        # CRITICAL: Validate matter_id first (Layer 2 enforcement)
        try:
            validate_namespace(matter_id)
        except ValueError as e:
            raise HybridSearchServiceError(
                message=str(e),
                code="INVALID_PARAMETER",
                is_retryable=False,
            ) from e

        weights = weights or SearchWeights()

        logger.info(
            "hybrid_search_start",
            query_len=len(query),
            matter_id=matter_id,
            limit=limit,
            bm25_weight=weights.bm25,
            semantic_weight=weights.semantic,
            rrf_k=rrf_k,
        )

        try:
            # Generate query embedding for semantic search
            query_embedding = await self.embedder.embed_text(query)

            # Execute hybrid search via RPC
            supabase = get_supabase_client()
            if supabase is None:
                raise HybridSearchServiceError(
                    message="Database client not configured",
                    code="DATABASE_NOT_CONFIGURED",
                    is_retryable=False,
                )

            response = supabase.rpc(
                "hybrid_search_chunks",
                {
                    "query_text": query,
                    "query_embedding": query_embedding,
                    "filter_matter_id": matter_id,
                    "match_count": limit,
                    "full_text_weight": weights.bm25,
                    "semantic_weight": weights.semantic,
                    "rrf_k": rrf_k,
                }
            ).execute()

            if response.data is None:
                logger.warning(
                    "hybrid_search_no_results",
                    matter_id=matter_id,
                    query_len=len(query),
                )
                return HybridSearchResult(
                    results=[],
                    query=query,
                    matter_id=matter_id,
                    weights=weights,
                    total_candidates=0,
                )

            # Validate results (defense in depth - Layer 2)
            validated = validate_search_results(response.data, matter_id)

            # Map to typed results
            results = [
                SearchResult(
                    id=str(r["id"]),
                    matter_id=str(r["matter_id"]),
                    document_id=str(r["document_id"]),
                    content=r["content"],
                    page_number=r.get("page_number"),
                    chunk_type=r["chunk_type"],
                    token_count=r.get("token_count") or 0,
                    bm25_rank=r.get("bm25_rank"),
                    semantic_rank=r.get("semantic_rank"),
                    rrf_score=r["rrf_score"],
                )
                for r in validated
            ]

            logger.info(
                "hybrid_search_complete",
                matter_id=matter_id,
                result_count=len(results),
                top_score=results[0].rrf_score if results else 0,
            )

            return HybridSearchResult(
                results=results,
                query=query,
                matter_id=matter_id,
                weights=weights,
                total_candidates=len(response.data),
            )

        except HybridSearchServiceError:
            raise
        except ValueError as e:
            raise HybridSearchServiceError(
                message=str(e),
                code="INVALID_PARAMETER",
                is_retryable=False,
            ) from e
        except Exception as e:
            logger.error(
                "hybrid_search_failed",
                matter_id=matter_id,
                query_len=len(query),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HybridSearchServiceError(
                message=f"Hybrid search failed: {e!s}",
                code="SEARCH_FAILED",
                is_retryable=True,
            ) from e

    async def bm25_search(
        self,
        query: str,
        matter_id: str,
        limit: int = 30,
    ) -> list[SearchResult]:
        """Execute BM25-only keyword search.

        Useful for debugging and comparing search approaches.

        Args:
            query: Search query text.
            matter_id: REQUIRED - matter UUID for isolation.
            limit: Max results to return.

        Returns:
            List of search results ranked by BM25 score.

        Raises:
            HybridSearchServiceError: If search fails.
        """
        validate_namespace(matter_id)

        logger.info(
            "bm25_search_start",
            query_len=len(query),
            matter_id=matter_id,
            limit=limit,
        )

        try:
            supabase = get_supabase_client()
            if supabase is None:
                raise HybridSearchServiceError(
                    message="Database client not configured",
                    code="DATABASE_NOT_CONFIGURED",
                    is_retryable=False,
                )

            response = supabase.rpc(
                "bm25_search_chunks",
                {
                    "query_text": query,
                    "filter_matter_id": matter_id,
                    "match_count": limit,
                }
            ).execute()

            if not response.data:
                return []

            # Validate results
            validated = validate_search_results(response.data, matter_id)

            return [
                SearchResult(
                    id=str(r["id"]),
                    matter_id=str(r["matter_id"]),
                    document_id=str(r["document_id"]),
                    content=r["content"],
                    page_number=r.get("page_number"),
                    chunk_type=r["chunk_type"],
                    token_count=r.get("token_count") or 0,
                    bm25_rank=r.get("row_num"),
                    semantic_rank=None,
                    rrf_score=r.get("rank") or 0,
                )
                for r in validated
            ]

        except HybridSearchServiceError:
            raise
        except Exception as e:
            logger.error(
                "bm25_search_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise HybridSearchServiceError(
                message=f"BM25 search failed: {e!s}",
                code="BM25_SEARCH_FAILED",
                is_retryable=True,
            ) from e

    async def semantic_search(
        self,
        query: str,
        matter_id: str,
        limit: int = 30,
    ) -> list[SearchResult]:
        """Execute semantic-only vector search.

        Useful for debugging and comparing search approaches.

        Args:
            query: Search query text.
            matter_id: REQUIRED - matter UUID for isolation.
            limit: Max results to return.

        Returns:
            List of search results ranked by semantic similarity.

        Raises:
            HybridSearchServiceError: If search fails.
        """
        validate_namespace(matter_id)

        logger.info(
            "semantic_search_start",
            query_len=len(query),
            matter_id=matter_id,
            limit=limit,
        )

        try:
            # Generate query embedding
            query_embedding = await self.embedder.embed_text(query)

            supabase = get_supabase_client()
            if supabase is None:
                raise HybridSearchServiceError(
                    message="Database client not configured",
                    code="DATABASE_NOT_CONFIGURED",
                    is_retryable=False,
                )

            response = supabase.rpc(
                "semantic_search_chunks",
                {
                    "query_embedding": query_embedding,
                    "filter_matter_id": matter_id,
                    "match_count": limit,
                }
            ).execute()

            if not response.data:
                return []

            # Validate results
            validated = validate_search_results(response.data, matter_id)

            return [
                SearchResult(
                    id=str(r["id"]),
                    matter_id=str(r["matter_id"]),
                    document_id=str(r["document_id"]),
                    content=r["content"],
                    page_number=r.get("page_number"),
                    chunk_type=r["chunk_type"],
                    token_count=r.get("token_count") or 0,
                    bm25_rank=None,
                    semantic_rank=r.get("row_num"),
                    rrf_score=r.get("similarity") or 0,
                )
                for r in validated
            ]

        except HybridSearchServiceError:
            raise
        except Exception as e:
            logger.error(
                "semantic_search_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise HybridSearchServiceError(
                message=f"Semantic search failed: {e!s}",
                code="SEMANTIC_SEARCH_FAILED",
                is_retryable=True,
            ) from e

    async def search_with_rerank(
        self,
        query: str,
        matter_id: str,
        hybrid_limit: int = DEFAULT_HYBRID_LIMIT,
        rerank_top_n: int = DEFAULT_RERANK_TOP_N,
        weights: SearchWeights | None = None,
    ) -> RerankedSearchResult:
        """Execute hybrid search with Cohere reranking.

        Pipeline: hybrid_search(limit=20) -> rerank(top_n=3)

        CRITICAL: Implements graceful fallback - if Cohere API fails,
        returns top-N results from RRF-ranked hybrid search instead.

        Args:
            query: Search query text.
            matter_id: REQUIRED - matter UUID for isolation.
            hybrid_limit: Candidates from hybrid search (default 20).
            rerank_top_n: Final results after reranking (default 3).
            weights: Optional custom weights for hybrid search.

        Returns:
            RerankedSearchResult with relevance_score from Cohere.
            If Cohere fails, relevance_score will be None and
            rerank_used will be False.

        Raises:
            HybridSearchServiceError: If hybrid search fails.

        Example:
            >>> result = await service.search_with_rerank(
            ...     query="contract termination clause",
            ...     matter_id="abc-123-def-456",
            ... )
            >>> result.rerank_used
            True
            >>> result.results[0].relevance_score
            0.987
        """
        # Import here to avoid circular dependency
        from app.services.rag.reranker import (
            CohereRerankServiceError,
            get_cohere_rerank_service,
        )

        # Step 1: Get candidates from hybrid search
        hybrid_result = await self.search(
            query=query,
            matter_id=matter_id,
            limit=hybrid_limit,
            weights=weights,
        )

        weights = weights or SearchWeights()

        # Handle no results
        if not hybrid_result.results:
            logger.debug(
                "search_with_rerank_no_candidates",
                matter_id=matter_id,
                query_len=len(query),
            )
            return RerankedSearchResult(
                results=[],
                query=query,
                matter_id=matter_id,
                weights=weights,
                total_candidates=0,
                rerank_used=False,
                fallback_reason="No hybrid search results",
            )

        # Step 2: Extract content for reranking
        documents = [r.content for r in hybrid_result.results]

        # Step 3: Attempt reranking with fallback
        try:
            reranker = get_cohere_rerank_service()
            rerank_result = await reranker.rerank(
                query=query,
                documents=documents,
                top_n=rerank_top_n,
            )

            # Step 4: Map reranked indices back to original results
            reranked_results = []
            for item in rerank_result.results:
                original = hybrid_result.results[item.index]
                reranked_results.append(
                    RerankedSearchResultItem(
                        id=original.id,
                        matter_id=original.matter_id,
                        document_id=original.document_id,
                        content=original.content,
                        page_number=original.page_number,
                        chunk_type=original.chunk_type,
                        token_count=original.token_count,
                        bm25_rank=original.bm25_rank,
                        semantic_rank=original.semantic_rank,
                        rrf_score=original.rrf_score,
                        relevance_score=item.relevance_score,
                    )
                )

            logger.info(
                "search_with_rerank_complete",
                matter_id=matter_id,
                query_len=len(query),
                candidates=len(hybrid_result.results),
                reranked=len(reranked_results),
                top_relevance=reranked_results[0].relevance_score if reranked_results else 0,
            )

            return RerankedSearchResult(
                results=reranked_results,
                query=query,
                matter_id=matter_id,
                weights=weights,
                total_candidates=hybrid_result.total_candidates,
                rerank_used=True,
                fallback_reason=None,
            )

        except CohereRerankServiceError as e:
            # Graceful fallback to RRF-ranked results
            logger.warning(
                "search_with_rerank_fallback",
                matter_id=matter_id,
                query_len=len(query),
                error=e.message,
                error_code=e.code,
            )

            # Return top N from RRF results
            fallback_results = [
                RerankedSearchResultItem(
                    id=r.id,
                    matter_id=r.matter_id,
                    document_id=r.document_id,
                    content=r.content,
                    page_number=r.page_number,
                    chunk_type=r.chunk_type,
                    token_count=r.token_count,
                    bm25_rank=r.bm25_rank,
                    semantic_rank=r.semantic_rank,
                    rrf_score=r.rrf_score,
                    relevance_score=None,  # No Cohere score
                )
                for r in hybrid_result.results[:rerank_top_n]
            ]

            return RerankedSearchResult(
                results=fallback_results,
                query=query,
                matter_id=matter_id,
                weights=weights,
                total_candidates=hybrid_result.total_candidates,
                rerank_used=False,
                fallback_reason=e.message,
            )


@lru_cache(maxsize=1)
def get_hybrid_search_service() -> HybridSearchService:
    """Get singleton hybrid search service instance.

    Returns:
        HybridSearchService instance.
    """
    return HybridSearchService()
