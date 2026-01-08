"""RAG (Retrieval-Augmented Generation) services."""

from app.services.rag.namespace import (
    get_namespace_filter,
    validate_namespace,
    build_vector_query_filter,
    build_semantic_search_query,
    build_hybrid_search_query,
    validate_search_results,
    MatterNamespaceFilter,
)
from app.services.rag.embedder import (
    EmbeddingService,
    EmbeddingServiceError,
    get_embedding_service,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    MAX_BATCH_SIZE,
)
from app.services.rag.hybrid_search import (
    HybridSearchService,
    HybridSearchServiceError,
    get_hybrid_search_service,
    SearchWeights,
    SearchResult,
    HybridSearchResult,
    RerankedSearchResult,
    RerankedSearchResultItem,
)
from app.services.rag.reranker import (
    CohereRerankService,
    CohereRerankServiceError,
    get_cohere_rerank_service,
    RerankResult,
    RerankResultItem,
    RERANK_MODEL,
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
