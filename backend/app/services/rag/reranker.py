"""Cohere Rerank Service for RAG pipeline.

Story 13-2: Circuit breaker protection for Cohere calls

This module implements document reranking using Cohere Rerank v3.5.
The reranker takes top-N candidates from hybrid search and reranks them
by relevance to the query using Cohere's cross-encoder model.

CRITICAL: Implements graceful fallback - if Cohere API fails or circuit
is open, the system falls back to RRF-ranked results from hybrid search.

Key Features:
- 40-70% precision improvement for legal document retrieval
- Circuit breaker protection for resilience
- Graceful fallback to RRF on API failures
- Structured logging via structlog
"""

import asyncio
from dataclasses import dataclass
from typing import Sequence

import cohere
import structlog
from cohere.core.api_error import ApiError as CohereApiError

from app.core.circuit_breaker import (
    CircuitOpenError,
    CircuitService,
    with_circuit_breaker,
)
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

RERANK_MODEL = "rerank-v3.5"
DEFAULT_TOP_N = 3
DEFAULT_HYBRID_LIMIT = 20
RERANK_TIMEOUT_SECONDS = 10


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RerankResultItem:
    """Single reranked document result.

    Attributes:
        index: Original document index in the input list.
        relevance_score: Cohere relevance score (0.0-1.0).
    """
    index: int
    relevance_score: float


@dataclass
class RerankResult:
    """Rerank operation result.

    Attributes:
        results: List of reranked items sorted by relevance_score descending.
        query: Original search query.
        model: Cohere model used for reranking.
        rerank_used: True if Cohere was successfully used, False if fallback.
        fallback_reason: Reason for fallback if rerank_used is False.
    """
    results: list[RerankResultItem]
    query: str
    model: str
    rerank_used: bool
    fallback_reason: str | None


# =============================================================================
# Exceptions
# =============================================================================

class CohereRerankServiceError(Exception):
    """Exception for Cohere rerank service errors.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code for API responses.
        is_retryable: Whether the operation can be retried.
    """

    def __init__(
        self,
        message: str,
        code: str = "RERANK_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


# =============================================================================
# Service Implementation
# =============================================================================

class CohereRerankService:
    """Service for reranking search results using Cohere Rerank v3.5.

    Takes candidate documents from hybrid search and reranks them
    based on relevance to the query using Cohere's cross-encoder model.

    CRITICAL: Implements graceful fallback - if Cohere API fails,
    returns original RRF-ranked results with warning logged.

    Example:
        >>> service = CohereRerankService()
        >>> result = await service.rerank(
        ...     query="contract termination clause",
        ...     documents=["doc1 text", "doc2 text", "doc3 text"],
        ...     top_n=3,
        ... )
        >>> len(result.results)
        3
        >>> result.results[0].relevance_score
        0.987

    Note:
        Cohere Rerank is NOT an LLM - it's a specialized cross-encoder
        model optimized for document relevance scoring. Much cheaper
        than LLM calls (~$0.002 per 1,000 documents).
    """

    def __init__(self):
        """Initialize Cohere rerank service.

        The Cohere client is lazily initialized on first use to avoid
        errors when API key is not configured but service is imported.
        """
        settings = get_settings()
        self._api_key = settings.cohere_api_key
        self._client: cohere.Client | None = None

    @property
    def client(self) -> cohere.Client:
        """Get Cohere client (lazy initialization).

        Returns:
            Configured Cohere client instance.

        Raises:
            CohereRerankServiceError: If API key is not configured.
        """
        if self._client is None:
            if not self._api_key:
                raise CohereRerankServiceError(
                    message="Cohere API key not configured",
                    code="COHERE_NOT_CONFIGURED",
                    is_retryable=False,
                )
            self._client = cohere.Client(api_key=self._api_key)
        return self._client

    def _do_rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> cohere.RerankResponse:
        """Execute synchronous Cohere rerank API call.

        This is a blocking call that should be run via asyncio.to_thread
        to avoid blocking the event loop.

        Args:
            query: Search query for relevance scoring.
            documents: List of document texts to rerank.
            top_n: Number of top results to return.

        Returns:
            Cohere rerank response.

        Raises:
            CohereApiError: On API errors.
        """
        return self.client.rerank(
            model=RERANK_MODEL,
            query=query,
            documents=documents,
            top_n=top_n,
            return_documents=False,  # We have originals, just need scores
        )

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int = DEFAULT_TOP_N,
    ) -> RerankResult:
        """Rerank documents by relevance to query with circuit breaker.

        Uses Cohere Rerank v3.5 to score document relevance.
        Results are returned sorted by relevance_score descending.

        Args:
            query: Search query for relevance scoring.
            documents: List of document texts to rerank.
            top_n: Number of top results to return (default 3).

        Returns:
            RerankResult with sorted results by relevance_score.
            Falls back to original order when circuit is open.

        Example:
            >>> result = await service.rerank(
            ...     query="What is the termination clause?",
            ...     documents=[
            ...         "The contract may be terminated with 30 days notice...",
            ...         "Payment shall be made within 15 business days...",
            ...         "Either party may terminate for material breach...",
            ...     ],
            ...     top_n=3,
            ... )
            >>> result.results[0].index  # Original index of most relevant doc
            2
            >>> result.results[0].relevance_score
            0.987
        """
        # Handle empty documents
        if not documents:
            logger.debug(
                "cohere_rerank_empty_input",
                query_len=len(query),
            )
            return RerankResult(
                results=[],
                query=query,
                model=RERANK_MODEL,
                rerank_used=True,
                fallback_reason=None,
            )

        # Ensure top_n doesn't exceed document count
        effective_top_n = min(top_n, len(documents))

        logger.info(
            "cohere_rerank_start",
            query_len=len(query),
            document_count=len(documents),
            top_n=effective_top_n,
        )

        try:
            # Call Cohere with circuit breaker protection
            response = await self._call_cohere_rerank(
                query, list(documents), effective_top_n
            )

            # Map response to our dataclass
            results = [
                RerankResultItem(
                    index=r.index,
                    relevance_score=r.relevance_score,
                )
                for r in response.results
            ]

            logger.info(
                "cohere_rerank_complete",
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
            # Fallback: return original order (use RRF scores)
            logger.warning(
                "cohere_rerank_circuit_open_fallback",
                query_len=len(query),
                document_count=len(documents),
                circuit_name=e.circuit_name,
                cooldown_remaining=e.cooldown_remaining,
            )
            return self._fallback_result(query, len(documents), effective_top_n,
                                         reason=f"Circuit open, retry after {e.cooldown_remaining:.0f}s")

        except asyncio.TimeoutError:
            logger.warning(
                "cohere_rerank_timeout",
                query_len=len(query),
                timeout=RERANK_TIMEOUT_SECONDS,
            )
            return self._fallback_result(query, len(documents), effective_top_n,
                                         reason=f"Timeout after {RERANK_TIMEOUT_SECONDS}s")

        except CohereApiError as e:
            logger.warning(
                "cohere_rerank_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return self._fallback_result(query, len(documents), effective_top_n,
                                         reason=f"API error: {e}")

        except Exception as e:
            logger.error(
                "cohere_rerank_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return self._fallback_result(query, len(documents), effective_top_n,
                                         reason=f"Unexpected error: {e}")

    @with_circuit_breaker(CircuitService.COHERE_RERANK, timeout_override=RERANK_TIMEOUT_SECONDS)
    async def _call_cohere_rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> cohere.RerankResponse:
        """Call Cohere API with circuit breaker protection.

        Args:
            query: Search query.
            documents: Documents to rerank.
            top_n: Number of results.

        Returns:
            Cohere rerank response.
        """
        # Run synchronous Cohere API call in thread to avoid blocking
        return await asyncio.to_thread(
            self._do_rerank,
            query,
            documents,
            top_n,
        )

    def _fallback_result(
        self,
        query: str,
        doc_count: int,
        top_n: int,
        reason: str,
    ) -> RerankResult:
        """Create fallback result using original document order.

        Args:
            query: Original query.
            doc_count: Total document count.
            top_n: Number of results requested.
            reason: Fallback reason.

        Returns:
            RerankResult with original order preserved.
        """
        # Return first top_n documents in original order
        results = [
            RerankResultItem(
                index=i,
                relevance_score=1.0 - (i * 0.1),  # Decreasing scores
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


# =============================================================================
# Service Factory
# =============================================================================

_rerank_service_instance: CohereRerankService | None = None


def get_cohere_rerank_service() -> CohereRerankService:
    """Get singleton Cohere rerank service instance.

    Returns:
        CohereRerankService instance.

    Note:
        The service uses lazy initialization for the Cohere client,
        so errors about missing API key will only occur on first
        rerank attempt, not on service instantiation.
    """
    global _rerank_service_instance

    if _rerank_service_instance is None:
        _rerank_service_instance = CohereRerankService()
        logger.info("cohere_rerank_service_initialized")

    return _rerank_service_instance
