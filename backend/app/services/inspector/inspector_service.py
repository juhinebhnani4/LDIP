"""Inspector service for RAG pipeline debugging.

Story: RAG Production Gaps - Feature 3: Inspector Mode
Wraps search services to capture detailed timing and scoring information.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import structlog

from app.core.config import get_settings
from app.models.inspector import (
    ChunkDebugInfo,
    SearchDebugInfo,
    TimingBreakdown,
)
from app.services.rag.embedder import get_embedding_service
from app.services.rag.hybrid_search import (
    HybridSearchService,
    SearchWeights,
    get_hybrid_search_service,
)
from app.services.supabase.client import get_supabase_client

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class InspectorServiceError(Exception):
    """Error in inspector service."""

    def __init__(self, message: str, code: str = "INSPECTOR_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class InspectorService:
    """Service for debugging RAG search pipeline.

    Wraps the hybrid search service to capture detailed timing
    and scoring information for each stage of the pipeline.

    Example:
        >>> service = get_inspector_service()
        >>> debug_info = await service.search_with_debug(
        ...     query="contract termination",
        ...     matter_id="matter-123",
        ... )
        >>> print(debug_info.timing.total_ms)
        125.5
    """

    def __init__(
        self,
        search_service: HybridSearchService | None = None,
    ) -> None:
        """Initialize inspector service.

        Args:
            search_service: Optional HybridSearchService (for testing).
        """
        self._search_service = search_service
        self._settings = get_settings()

    @property
    def search_service(self) -> HybridSearchService:
        """Lazy-load search service."""
        if self._search_service is None:
            self._search_service = get_hybrid_search_service()
        return self._search_service

    async def search_with_debug(
        self,
        query: str,
        matter_id: str,
        limit: int = 20,
        bm25_weight: float = 1.0,
        semantic_weight: float = 1.0,
        rerank: bool = True,
        rerank_top_n: int = 5,
        expand_aliases: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], SearchDebugInfo]:
        """Execute search with full debug information.

        Args:
            query: Search query.
            matter_id: Matter UUID.
            limit: Max hybrid results.
            bm25_weight: BM25 weight (0-2).
            semantic_weight: Semantic weight (0-2).
            rerank: Whether to rerank.
            rerank_top_n: Top N after reranking.
            expand_aliases: Expand entity aliases.

        Returns:
            Tuple of (results, meta, debug_info).
        """
        start_time = time.perf_counter()

        # Track timing for each stage
        timing = {
            "embedding_ms": None,
            "bm25_search_ms": None,
            "semantic_search_ms": None,
            "rrf_fusion_ms": None,
            "rerank_ms": None,
        }

        weights = SearchWeights(bm25=bm25_weight, semantic=semantic_weight)

        # Step 1: Expand aliases if enabled
        expanded_query = query
        if expand_aliases:
            # This would integrate with MIG alias service
            # For now, pass through
            pass

        # Step 2: Generate embedding (with timing)
        embedding_start = time.perf_counter()
        embedder = get_embedding_service()
        query_embedding = await embedder.embed_text(query)
        timing["embedding_ms"] = (time.perf_counter() - embedding_start) * 1000

        # Step 3: Execute BM25 search (with timing)
        bm25_start = time.perf_counter()
        bm25_results = await self._execute_bm25_search(query, matter_id, limit)
        timing["bm25_search_ms"] = (time.perf_counter() - bm25_start) * 1000

        # Step 4: Execute semantic search (with timing)
        semantic_start = time.perf_counter()
        semantic_results = await self._execute_semantic_search(
            query_embedding, matter_id, limit
        )
        timing["semantic_search_ms"] = (time.perf_counter() - semantic_start) * 1000

        # Step 5: RRF fusion (with timing)
        fusion_start = time.perf_counter()
        fused_results, fusion_meta = self._rrf_fusion(
            bm25_results,
            semantic_results,
            weights,
            limit,
        )
        timing["rrf_fusion_ms"] = (time.perf_counter() - fusion_start) * 1000

        # Step 6: Reranking (with timing)
        final_results = fused_results
        rerank_used = False
        rerank_fallback_reason = None

        if rerank and fused_results:
            rerank_start = time.perf_counter()
            try:
                from app.services.rag.reranker import get_cohere_rerank_service

                reranker = get_cohere_rerank_service()
                documents = [r["content"] for r in fused_results]

                rerank_result = await reranker.rerank(
                    query=query,
                    documents=documents,
                    top_n=rerank_top_n,
                )

                # Apply rerank scores to results
                final_results = []
                for idx, item in enumerate(rerank_result.results):
                    original = fused_results[item.index]
                    original["rerank_score"] = item.relevance_score
                    original["rerank_rank"] = idx + 1
                    final_results.append(original)

                rerank_used = True
                timing["rerank_ms"] = (time.perf_counter() - rerank_start) * 1000

            except Exception as e:
                logger.warning(
                    "inspector_rerank_failed",
                    matter_id=matter_id,
                    error=str(e),
                )
                rerank_fallback_reason = str(e)
                final_results = fused_results[:rerank_top_n]
                timing["rerank_ms"] = (time.perf_counter() - rerank_start) * 1000

        total_ms = (time.perf_counter() - start_time) * 1000

        # Build debug info
        chunks_debug = [
            ChunkDebugInfo(
                chunk_id=r["id"],
                document_id=r["document_id"],
                document_name=r.get("document_name"),
                page_number=r.get("page_number"),
                chunk_type=r.get("chunk_type", "unknown"),
                bm25_rank=r.get("bm25_rank"),
                bm25_score=r.get("bm25_score"),
                semantic_rank=r.get("semantic_rank"),
                semantic_score=r.get("semantic_score"),
                rrf_score=r.get("rrf_score", 0),
                rrf_rank=r.get("rrf_rank", 0),
                rerank_score=r.get("rerank_score"),
                rerank_rank=r.get("rerank_rank"),
                content_preview=r.get("content", "")[:200],
                token_count=r.get("token_count", 0),
            )
            for r in final_results
        ]

        debug_info = SearchDebugInfo(
            timing=TimingBreakdown(
                embedding_ms=timing["embedding_ms"],
                bm25_search_ms=timing["bm25_search_ms"],
                semantic_search_ms=timing["semantic_search_ms"],
                rrf_fusion_ms=timing["rrf_fusion_ms"],
                rerank_ms=timing["rerank_ms"],
                total_ms=total_ms,
            ),
            query=query,
            expanded_query=expanded_query if expanded_query != query else None,
            embedding_model=self._settings.openai_embedding_model,
            bm25_weight=bm25_weight,
            semantic_weight=semantic_weight,
            top_k_bm25=limit,
            top_k_semantic=limit,
            k_constant=60,
            rerank_requested=rerank,
            rerank_used=rerank_used,
            rerank_model="rerank-v3.5" if rerank_used else None,
            rerank_top_n=rerank_top_n if rerank else None,
            rerank_fallback_reason=rerank_fallback_reason,
            bm25_results_count=len(bm25_results),
            semantic_results_count=len(semantic_results),
            fused_results_count=len(fused_results),
            final_results_count=len(final_results),
            chunks=chunks_debug,
        )

        # Build standard response format
        data = [
            {
                "id": r["id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "page_number": r.get("page_number"),
                "chunk_type": r.get("chunk_type"),
                "token_count": r.get("token_count", 0),
                "bm25_rank": r.get("bm25_rank"),
                "semantic_rank": r.get("semantic_rank"),
                "rrf_score": r.get("rrf_score", 0),
                "relevance_score": r.get("rerank_score"),
            }
            for r in final_results
        ]

        meta = {
            "query": query,
            "matter_id": matter_id,
            "total_candidates": len(fused_results),
            "bm25_weight": bm25_weight,
            "semantic_weight": semantic_weight,
            "rerank_used": rerank_used,
            "fallback_reason": rerank_fallback_reason,
        }

        return data, meta, debug_info

    async def _execute_bm25_search(
        self,
        query: str,
        matter_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Execute BM25 search and return raw results."""
        try:
            supabase = get_supabase_client()
            if supabase is None:
                return []

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

            # Add rank info
            results = []
            for idx, r in enumerate(response.data):
                r["bm25_rank"] = idx + 1
                r["bm25_score"] = r.get("rank", 0)
                results.append(r)

            return results

        except Exception as e:
            logger.warning("inspector_bm25_search_failed", error=str(e))
            return []

    async def _execute_semantic_search(
        self,
        embedding: list[float] | None,
        matter_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Execute semantic search and return raw results."""
        if embedding is None:
            return []

        try:
            supabase = get_supabase_client()
            if supabase is None:
                return []

            response = supabase.rpc(
                "semantic_search_chunks",
                {
                    "query_embedding": embedding,
                    "filter_matter_id": matter_id,
                    "match_count": limit,
                }
            ).execute()

            if not response.data:
                return []

            # Add rank info
            results = []
            for idx, r in enumerate(response.data):
                r["semantic_rank"] = idx + 1
                r["semantic_score"] = r.get("similarity", 0)
                results.append(r)

            return results

        except Exception as e:
            logger.warning("inspector_semantic_search_failed", error=str(e))
            return []

    def _rrf_fusion(
        self,
        bm25_results: list[dict[str, Any]],
        semantic_results: list[dict[str, Any]],
        weights: SearchWeights,
        limit: int,
        k: int = 60,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Perform RRF fusion of BM25 and semantic results.

        Args:
            bm25_results: Results from BM25 search.
            semantic_results: Results from semantic search.
            weights: Search weights.
            limit: Max results.
            k: RRF constant (default 60).

        Returns:
            Tuple of (fused_results, fusion_meta).
        """
        # Build score map by chunk ID
        scores: dict[str, dict[str, Any]] = {}

        # Add BM25 scores
        for idx, r in enumerate(bm25_results):
            chunk_id = str(r["id"])
            if chunk_id not in scores:
                scores[chunk_id] = {
                    "id": chunk_id,
                    "document_id": str(r.get("document_id", "")),
                    "content": r.get("content", ""),
                    "page_number": r.get("page_number"),
                    "chunk_type": r.get("chunk_type", "unknown"),
                    "token_count": r.get("token_count", 0),
                    "bm25_rank": None,
                    "bm25_score": None,
                    "semantic_rank": None,
                    "semantic_score": None,
                    "rrf_score": 0.0,
                }

            scores[chunk_id]["bm25_rank"] = idx + 1
            scores[chunk_id]["bm25_score"] = r.get("rank", r.get("bm25_score", 0))
            # RRF score contribution
            scores[chunk_id]["rrf_score"] += weights.bm25 / (k + idx + 1)

        # Add semantic scores
        for idx, r in enumerate(semantic_results):
            chunk_id = str(r["id"])
            if chunk_id not in scores:
                scores[chunk_id] = {
                    "id": chunk_id,
                    "document_id": str(r.get("document_id", "")),
                    "content": r.get("content", ""),
                    "page_number": r.get("page_number"),
                    "chunk_type": r.get("chunk_type", "unknown"),
                    "token_count": r.get("token_count", 0),
                    "bm25_rank": None,
                    "bm25_score": None,
                    "semantic_rank": None,
                    "semantic_score": None,
                    "rrf_score": 0.0,
                }

            scores[chunk_id]["semantic_rank"] = idx + 1
            scores[chunk_id]["semantic_score"] = r.get("similarity", r.get("semantic_score", 0))
            # RRF score contribution
            scores[chunk_id]["rrf_score"] += weights.semantic / (k + idx + 1)

        # Sort by RRF score
        fused = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)

        # Add RRF rank
        for idx, r in enumerate(fused):
            r["rrf_rank"] = idx + 1

        meta = {
            "bm25_count": len(bm25_results),
            "semantic_count": len(semantic_results),
            "unique_count": len(scores),
            "k_constant": k,
        }

        return fused[:limit], meta


@lru_cache(maxsize=1)
def get_inspector_service() -> InspectorService:
    """Get singleton inspector service instance.

    Returns:
        InspectorService instance.
    """
    return InspectorService()
