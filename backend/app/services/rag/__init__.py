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

__all__ = [
    "get_namespace_filter",
    "validate_namespace",
    "build_vector_query_filter",
    "build_semantic_search_query",
    "build_hybrid_search_query",
    "validate_search_results",
    "MatterNamespaceFilter",
]
