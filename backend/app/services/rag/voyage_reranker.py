"""Voyage AI Rerank Service for RAG pipeline.

Mirrors CohereRerankService structure but uses Voyage AI rerank-2.5 model.
Implements graceful fallback to RRF scores on API failures.
"""

import asyncio
from collections.abc import Sequence

import structlog

from app.core.circuit_breaker import (
    CircuitOpenError,
    CircuitService,
    with_circuit_breaker,
)
from app.core.config import get_settings
from app.core.cost_tracking import CostTracker, persist_cost
from app.core.cost_tracking import LLMProvider as CostLLMProvider
from app.services.rag.reranker import RerankResult, RerankResultItem

logger = structlog.get_logger(__name__)

RERANK_MODEL = "rerank-2.5"
DEFAULT_TOP_K = 3
RERANK_TIMEOUT_SECONDS = 10


class VoyageRerankService:
    """Service for reranking search results using Voyage AI rerank-2.5.

    Implements the same interface as CohereRerankService for use
    with the reranker_factory.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.voyage_api_key
        self._client = None

    @property
    def provider_name(self) -> str:
        return "voyage"

    @property
    def client(self):
        """Get Voyage client (lazy initialization)."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("Voyage API key not configured")
            import voyageai

            self._client = voyageai.Client(api_key=self._api_key)
        return self._client

    def _do_rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int,
    ):
        """Execute synchronous Voyage rerank API call."""
        return self.client.rerank(
            model=RERANK_MODEL,
            query=query,
            documents=documents,
            top_k=top_k,
        )

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int = DEFAULT_TOP_K,
        matter_id: str | None = None,
    ) -> RerankResult:
        """Rerank documents by relevance to query using Voyage AI.

        Args:
            query: Search query for relevance scoring.
            documents: List of document texts to rerank.
            top_n: Number of top results to return.
            matter_id: Optional matter UUID for cost attribution.

        Returns:
            RerankResult with sorted results by relevance_score.
        """
        if not documents:
            return RerankResult(
                results=[],
                query=query,
                model=RERANK_MODEL,
                rerank_used=True,
                fallback_reason=None,
            )

        effective_top_k = min(top_n, len(documents))

        logger.info(
            "voyage_rerank_start",
            query_len=len(query),
            document_count=len(documents),
            top_k=effective_top_k,
        )

        try:
            response = await self._call_voyage_rerank(
                query, list(documents), effective_top_k, matter_id=matter_id,
            )

            results = [
                RerankResultItem(
                    index=r.index,
                    relevance_score=r.relevance_score,
                )
                for r in response.results
            ]

            # Track cost
            tracker = CostTracker(
                provider=CostLLMProvider.VOYAGE_RERANK_2_5,
                operation="search_rerank",
                matter_id=matter_id,
            )
            tracker.add_units(1)
            tracker.log_cost()
            await persist_cost(tracker)

            logger.info(
                "voyage_rerank_complete",
                query_len=len(query),
                top_score=results[0].relevance_score if results else 0,
                result_count=len(results),
            )

            return RerankResult(
                results=results,
                query=query,
                model=RERANK_MODEL,
                rerank_used=True,
                fallback_reason=None,
            )

        except CircuitOpenError as e:
            logger.warning(
                "voyage_rerank_circuit_open_fallback",
                circuit_name=e.circuit_name,
                cooldown_remaining=e.cooldown_remaining,
            )
            return self._fallback_result(
                query, len(documents), effective_top_k,
                reason=f"Circuit open, retry after {e.cooldown_remaining:.0f}s",
            )

        except TimeoutError:
            logger.warning("voyage_rerank_timeout", timeout=RERANK_TIMEOUT_SECONDS)
            return self._fallback_result(
                query, len(documents), effective_top_k,
                reason=f"Timeout after {RERANK_TIMEOUT_SECONDS}s",
            )

        except Exception as e:
            logger.error(
                "voyage_rerank_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return self._fallback_result(
                query, len(documents), effective_top_k,
                reason=f"API error: {e}",
            )

    @with_circuit_breaker(CircuitService.VOYAGE_RERANK, timeout_override=RERANK_TIMEOUT_SECONDS)
    async def _call_voyage_rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int,
        matter_id: str | None = None,
    ):
        """Call Voyage API with circuit breaker protection."""
        return await asyncio.to_thread(
            self._do_rerank, query, documents, top_k,
        )

    def _fallback_result(
        self,
        query: str,
        doc_count: int,
        top_n: int,
        reason: str,
    ) -> RerankResult:
        """Create fallback result using original document order."""
        results = [
            RerankResultItem(
                index=i,
                relevance_score=1.0 - (i * 0.1),
            )
            for i in range(min(top_n, doc_count))
        ]
        return RerankResult(
            results=results,
            query=query,
            model=RERANK_MODEL,
            rerank_used=False,
            fallback_reason=reason,
        )
