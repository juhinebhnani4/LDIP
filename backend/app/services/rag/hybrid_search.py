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
# NOTE: Increased from 20 to 50 for better recall (Issue #5 from code review)
# Reranking 50 items is still fast (~100ms) and significantly improves
# "needle in haystack" performance where the best result might be ranked
# 25-30 by BM25/semantic but would be top-3 after reranking
DEFAULT_HYBRID_LIMIT = 50
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
        bbox_ids: Bounding box UUIDs for precise source highlighting.
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
    bbox_ids: list[str] | None
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
        search_mode: Search mode used - "hybrid", "bm25_only", or "bm25_fallback".
        embedding_completion_pct: Percentage of chunks with embeddings (0-100).
        fallback_reason: Human-readable reason if fallback was used.
    """
    results: list[SearchResult]
    query: str
    matter_id: str
    weights: SearchWeights
    total_candidates: int
    search_mode: str = "hybrid"
    embedding_completion_pct: float | None = None
    fallback_reason: str | None = None


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
        bbox_ids: Bounding box UUIDs for precise source highlighting.
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
    bbox_ids: list[str] | None
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
        search_mode: Search mode used - "hybrid", "bm25_only", or "bm25_fallback".
        embedding_completion_pct: Percentage of chunks with embeddings (0-100).
    """
    results: list[RerankedSearchResultItem]
    query: str
    matter_id: str
    weights: SearchWeights
    total_candidates: int
    rerank_used: bool
    fallback_reason: str | None
    search_mode: str = "hybrid"
    embedding_completion_pct: float | None = None


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

    async def _check_embedding_status(self, matter_id: str) -> tuple[int, int, float]:
        """Check embedding completion status for a matter.

        Used for optimistic RAG - allows search to work with partial embeddings
        by falling back to BM25 when embeddings are incomplete.

        Args:
            matter_id: Matter UUID to check.

        Returns:
            Tuple of (total_chunks, embedded_chunks, completion_percentage).
            Returns (0, 0, 0.0) if no chunks exist.
        """
        try:
            supabase = get_supabase_client()
            if supabase is None:
                return 0, 0, 0.0

            # Count total chunks for this matter
            total_resp = (
                supabase.table("chunks")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )
            total_count = total_resp.count or 0

            if total_count == 0:
                return 0, 0, 0.0

            # Count chunks with embeddings
            embedded_resp = (
                supabase.table("chunks")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .not_.is_("embedding", "null")
                .execute()
            )
            embedded_count = embedded_resp.count or 0

            completion_pct = (embedded_count / total_count * 100) if total_count > 0 else 0.0

            logger.debug(
                "embedding_status_checked",
                matter_id=matter_id,
                total_chunks=total_count,
                embedded_chunks=embedded_count,
                completion_pct=round(completion_pct, 1),
            )

            return total_count, embedded_count, completion_pct

        except Exception as e:
            logger.warning(
                "embedding_status_check_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return 0, 0, 0.0

    async def get_embedding_status(self, matter_id: str) -> dict:
        """Get embedding completion status for a matter.

        Public API for checking embedding progress. Used by search routes
        to inform users about indexing status.

        Args:
            matter_id: Matter UUID to check.

        Returns:
            Dict with:
                - total_chunks: Total number of chunks for this matter.
                - embedded_chunks: Number of chunks with embeddings.
                - completion_pct: Percentage complete (0-100).
                - is_fully_indexed: True if all chunks have embeddings.
        """
        total, embedded, pct = await self._check_embedding_status(matter_id)
        return {
            "total_chunks": total,
            "embedded_chunks": embedded,
            "completion_pct": pct,
            "is_fully_indexed": total == 0 or embedded >= total,
        }

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

            # Handle embedding service failure (returns None when circuit is open or API fails)
            if query_embedding is None:
                logger.warning(
                    "embedding_service_unavailable_falling_back_to_bm25",
                    matter_id=matter_id,
                    query_len=len(query),
                )
                # Fall back to BM25-only search when embeddings unavailable
                bm25_results = await self._bm25_search_internal(query, matter_id, limit=limit)
                return HybridSearchResult(
                    results=bm25_results,
                    query=query,
                    matter_id=matter_id,
                    weights=weights,
                    total_candidates=len(bm25_results),
                    search_mode="bm25_fallback",
                    embedding_completion_pct=None,
                    fallback_reason="Embedding service unavailable",
                )

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

            if response.data is None or len(response.data) == 0:
                # Check if embeddings are incomplete (optimistic RAG)
                total_chunks, embedded_chunks, completion_pct = await self._check_embedding_status(matter_id)

                if total_chunks > 0 and embedded_chunks < total_chunks:
                    # Embeddings incomplete - fall back to BM25-only for optimistic search
                    logger.info(
                        "optimistic_bm25_fallback",
                        matter_id=matter_id,
                        query_len=len(query),
                        total_chunks=total_chunks,
                        embedded_chunks=embedded_chunks,
                        completion_pct=round(completion_pct, 1),
                    )
                    bm25_results = await self._bm25_search_internal(query, matter_id, limit=limit)
                    return HybridSearchResult(
                        results=bm25_results,
                        query=query,
                        matter_id=matter_id,
                        weights=weights,
                        total_candidates=len(bm25_results),
                        search_mode="bm25_only",
                        embedding_completion_pct=completion_pct,
                        fallback_reason=f"Embeddings {int(completion_pct)}% complete",
                    )

                # No chunks or all embedded but still no results
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
                    bbox_ids=[str(b) for b in r.get("bbox_ids") or []],
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

    async def _bm25_search_internal(
        self,
        query: str,
        matter_id: str,
        limit: int = 30,
    ) -> list[SearchResult]:
        """Internal BM25 search returning raw results.

        Used by optimistic fallback and public bm25_search method.

        Args:
            query: Search query text.
            matter_id: matter UUID for isolation.
            limit: Max results to return.

        Returns:
            List of search results ranked by BM25 score.
        """
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
                    bbox_ids=[str(b) for b in r.get("bbox_ids") or []],
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
                "bm25_search_internal_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise HybridSearchServiceError(
                message=f"BM25 search failed: {e!s}",
                code="BM25_SEARCH_FAILED",
                is_retryable=True,
            ) from e

    async def bm25_search(
        self,
        query: str,
        matter_id: str,
        limit: int = 30,
    ) -> HybridSearchResult:
        """Execute BM25-only keyword search.

        Useful for debugging and comparing search approaches.

        Args:
            query: Search query text.
            matter_id: REQUIRED - matter UUID for isolation.
            limit: Max results to return.

        Returns:
            HybridSearchResult with BM25-only results.

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

        results = await self._bm25_search_internal(query, matter_id, limit)

        return HybridSearchResult(
            results=results,
            query=query,
            matter_id=matter_id,
            weights=SearchWeights(),
            total_candidates=len(results),
            search_mode="bm25_only",
            embedding_completion_pct=None,
            fallback_reason=None,
        )

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

            # Handle embedding service failure
            if query_embedding is None:
                logger.warning(
                    "semantic_search_embedding_unavailable",
                    matter_id=matter_id,
                    query_len=len(query),
                )
                raise HybridSearchServiceError(
                    message="Semantic search unavailable - embedding service is not responding",
                    code="EMBEDDING_SERVICE_UNAVAILABLE",
                    is_retryable=True,
                )

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
                    bbox_ids=[str(b) for b in r.get("bbox_ids") or []],
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
                search_mode=hybrid_result.search_mode,
                embedding_completion_pct=hybrid_result.embedding_completion_pct,
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
                        bbox_ids=original.bbox_ids,
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
                search_mode=hybrid_result.search_mode,
                embedding_completion_pct=hybrid_result.embedding_completion_pct,
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
                    bbox_ids=r.bbox_ids,
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
                search_mode=hybrid_result.search_mode,
                embedding_completion_pct=hybrid_result.embedding_completion_pct,
            )


@lru_cache(maxsize=1)
def get_hybrid_search_service() -> HybridSearchService:
    """Get singleton hybrid search service instance.

    Returns:
        HybridSearchService instance.
    """
    return HybridSearchService()
