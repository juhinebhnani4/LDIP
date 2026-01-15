"""RAG (Retrieval-Augmented Generation) services."""

from app.services.rag.embedder import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    MAX_BATCH_SIZE,
    EmbeddingService,
    EmbeddingServiceError,
    get_embedding_service,
)
from app.services.rag.hybrid_search import (
    HybridSearchResult,
    HybridSearchService,
    HybridSearchServiceError,
    RerankedSearchResult,
    RerankedSearchResultItem,
    SearchResult,
    SearchWeights,
    get_hybrid_search_service,
)
from app.services.rag.namespace import (
    MatterNamespaceFilter,
    build_hybrid_search_query,
    build_semantic_search_query,
    build_vector_query_filter,
    get_namespace_filter,
    validate_namespace,
    validate_search_results,
)
from app.services.rag.reranker import (
    RERANK_MODEL,
    CohereRerankService,
    CohereRerankServiceError,
    RerankResult,
    RerankResultItem,
    get_cohere_rerank_service,
)

__all__ = [
    # Namespace utilities
    "get_namespace_filter",
    "validate_namespace",
    "build_vector_query_filter",
    "build_semantic_search_query",
    "build_hybrid_search_query",
    "validate_search_results",
    "MatterNamespaceFilter",
    # Embedding service
    "EmbeddingService",
    "EmbeddingServiceError",
    "get_embedding_service",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "MAX_BATCH_SIZE",
    # Hybrid search service
    "HybridSearchService",
    "HybridSearchServiceError",
    "get_hybrid_search_service",
    "SearchWeights",
    "SearchResult",
    "HybridSearchResult",
    "RerankedSearchResult",
    "RerankedSearchResultItem",
    # Cohere reranker service
    "CohereRerankService",
    "CohereRerankServiceError",
    "get_cohere_rerank_service",
    "RerankResult",
    "RerankResultItem",
    "RERANK_MODEL",
]
