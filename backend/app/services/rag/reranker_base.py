"""Base class and enum for reranker services.

Provides a common interface so CohereRerankService and VoyageRerankService
can be used interchangeably via the reranker_factory.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum

from app.services.rag.reranker import RerankResult


class RerankProvider(str, Enum):
    """Supported reranking providers."""

    COHERE = "cohere"
    VOYAGE = "voyage"


class BaseRerankService(ABC):
    """Abstract base class for reranker services."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g. 'cohere', 'voyage')."""
        ...

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int = 3,
        matter_id: str | None = None,
    ) -> RerankResult:
        """Rerank documents by relevance to query.

        Args:
            query: Search query for relevance scoring.
            documents: List of document texts to rerank.
            top_n: Number of top results to return.
            matter_id: Optional matter UUID for cost attribution.

        Returns:
            RerankResult with sorted results.
        """
        ...
