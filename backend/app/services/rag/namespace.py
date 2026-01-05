"""Vector namespace utilities for Layer 2 of 4-layer matter isolation.

This module implements the vector namespace pattern that ensures:
1. All vector queries are scoped to a specific matter
2. No cross-matter embedding retrieval is possible
3. Namespace injection attacks are prevented

CRITICAL: All vector/embedding operations MUST use these functions.
Never construct vector queries without matter_id filtering.

The namespace pattern uses matter_id as a mandatory filter in all
pgvector queries, ensuring that semantic similarity searches only
return results from the authorized matter.
"""

import re
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# UUID Validation
# =============================================================================

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE
)


def _validate_uuid(value: str, name: str) -> None:
    """Validate that a value is a valid UUID.

    Args:
        value: The value to validate.
        name: Name of the parameter (for error messages).

    Raises:
        ValueError: If the value is not a valid UUID.
    """
    if not value or not UUID_PATTERN.match(value):
        logger.warning(
            "invalid_uuid_in_vector_namespace",
            parameter=name,
            value=value[:50] if value else None,
        )
        raise ValueError(f"Invalid UUID for {name}: potential namespace injection attempt")


# =============================================================================
# Namespace Filter Data Class
# =============================================================================

@dataclass
class MatterNamespaceFilter:
    """Represents a matter namespace filter for vector queries.

    This class ensures that all vector queries include the mandatory
    matter_id filter for security isolation.

    Attributes:
        matter_id: The UUID of the matter to filter by.
        document_ids: Optional list of document IDs to further filter.
        chunk_type: Optional chunk type filter ('parent' or 'child').
        entity_ids: Optional list of entity IDs to filter by.
    """
    matter_id: str
    document_ids: list[str] | None = None
    chunk_type: str | None = None
    entity_ids: list[str] | None = None

    def __post_init__(self) -> None:
        """Validate the namespace filter after initialization."""
        _validate_uuid(self.matter_id, "matter_id")

        if self.document_ids:
            for doc_id in self.document_ids:
                _validate_uuid(doc_id, "document_id")

        if self.entity_ids:
            for entity_id in self.entity_ids:
                _validate_uuid(entity_id, "entity_id")

        if self.chunk_type and self.chunk_type not in ("parent", "child"):
            raise ValueError("chunk_type must be 'parent' or 'child'")


# =============================================================================
# Namespace Filter Functions
# =============================================================================

def get_namespace_filter(
    matter_id: str,
    document_ids: list[str] | None = None,
    chunk_type: str | None = None,
    entity_ids: list[str] | None = None,
) -> MatterNamespaceFilter:
    """Create a namespace filter for vector queries with validation.

    This is the primary function for creating matter-isolated vector queries.
    It validates all inputs and returns a typed filter object.

    Args:
        matter_id: The matter UUID (REQUIRED - cannot be None).
        document_ids: Optional list of document UUIDs to filter.
        chunk_type: Optional chunk type ('parent' or 'child').
        entity_ids: Optional list of entity UUIDs to filter.

    Returns:
        MatterNamespaceFilter object for use in vector queries.

    Raises:
        ValueError: If matter_id is invalid or missing.

    Example:
        >>> filter = get_namespace_filter(
        ...     matter_id="abc-123",
        ...     document_ids=["doc-1", "doc-2"],
        ...     chunk_type="parent"
        ... )
        >>> filter.matter_id
        'abc-123'
    """
    if not matter_id:
        logger.error("vector_query_without_matter_id")
        raise ValueError("matter_id is REQUIRED for all vector queries - security violation")

    return MatterNamespaceFilter(
        matter_id=matter_id,
        document_ids=document_ids,
        chunk_type=chunk_type,
        entity_ids=entity_ids,
    )


def validate_namespace(matter_id: str) -> str:
    """Validate and return a matter_id for use in namespace filtering.

    This is a simple validation function for cases where only
    matter_id is needed without additional filters.

    Args:
        matter_id: The matter UUID to validate.

    Returns:
        The validated matter_id.

    Raises:
        ValueError: If the matter_id is invalid.

    Example:
        >>> validated_id = validate_namespace("abc-123-def-456")
        >>> validated_id
        'abc-123-def-456'
    """
    _validate_uuid(matter_id, "matter_id")
    return matter_id


def build_vector_query_filter(
    namespace_filter: MatterNamespaceFilter,
) -> dict[str, Any]:
    """Build a filter dictionary for pgvector queries.

    This function converts a MatterNamespaceFilter into a dictionary
    suitable for use with Supabase's RPC or query builder.

    Args:
        namespace_filter: The validated namespace filter.

    Returns:
        Dictionary of filter parameters for the vector query.

    Example:
        >>> filter = get_namespace_filter("abc-123", chunk_type="parent")
        >>> params = build_vector_query_filter(filter)
        >>> params
        {'filter_matter_id': 'abc-123', 'filter_chunk_type': 'parent'}
    """
    params: dict[str, Any] = {
        "filter_matter_id": namespace_filter.matter_id,  # ALWAYS included
    }

    if namespace_filter.document_ids:
        params["filter_document_ids"] = namespace_filter.document_ids

    if namespace_filter.chunk_type:
        params["filter_chunk_type"] = namespace_filter.chunk_type

    # Note: entity_ids filtering is handled separately via array overlap

    logger.debug(
        "built_vector_query_filter",
        matter_id=namespace_filter.matter_id,
        has_document_filter=bool(namespace_filter.document_ids),
        has_chunk_type_filter=bool(namespace_filter.chunk_type),
        has_entity_filter=bool(namespace_filter.entity_ids),
    )

    return params


# =============================================================================
# Query Builders
# =============================================================================

def build_semantic_search_query(
    namespace_filter: MatterNamespaceFilter,
    query_embedding: list[float],
    limit: int = 10,
    similarity_threshold: float = 0.5,
) -> dict[str, Any]:
    """Build parameters for the match_chunks RPC function.

    This function prepares all parameters needed to call the
    match_chunks PostgreSQL function with proper matter isolation.

    Args:
        namespace_filter: The validated namespace filter.
        query_embedding: The query embedding vector (1536 dimensions).
        limit: Maximum number of results to return.
        similarity_threshold: Minimum similarity score (0-1).

    Returns:
        Dictionary of parameters for the match_chunks RPC call.

    Raises:
        ValueError: If parameters are invalid.

    Example:
        >>> filter = get_namespace_filter("abc-123")
        >>> embedding = [0.1] * 1536  # Example embedding
        >>> params = build_semantic_search_query(filter, embedding, limit=5)
        >>> params["filter_matter_id"]
        'abc-123'
    """
    # Validate embedding dimensions
    if not query_embedding or len(query_embedding) != 1536:
        raise ValueError(f"query_embedding must have 1536 dimensions, got {len(query_embedding) if query_embedding else 0}")

    if not 0 <= similarity_threshold <= 1:
        raise ValueError("similarity_threshold must be between 0 and 1")

    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    params = build_vector_query_filter(namespace_filter)
    params.update({
        "query_embedding": query_embedding,
        "match_count": limit,
        "similarity_threshold": similarity_threshold,
    })

    return params


def build_hybrid_search_query(
    namespace_filter: MatterNamespaceFilter,
    query_embedding: list[float],
    keyword_query: str,
    vector_weight: float = 0.5,
    limit: int = 10,
) -> dict[str, Any]:
    """Build parameters for hybrid (vector + keyword) search.

    Combines semantic similarity with BM25 keyword matching.

    Args:
        namespace_filter: The validated namespace filter.
        query_embedding: The query embedding vector.
        keyword_query: The keyword search query.
        vector_weight: Weight for vector similarity (0-1, remainder for BM25).
        limit: Maximum number of results.

    Returns:
        Dictionary of parameters for hybrid search RPC.

    Example:
        >>> filter = get_namespace_filter("abc-123")
        >>> params = build_hybrid_search_query(
        ...     filter,
        ...     [0.1] * 1536,
        ...     "contract termination",
        ...     vector_weight=0.7
        ... )
    """
    if not 0 <= vector_weight <= 1:
        raise ValueError("vector_weight must be between 0 and 1")

    # Sanitize keyword query to prevent injection
    sanitized_query = _sanitize_keyword_query(keyword_query)

    params = build_semantic_search_query(namespace_filter, query_embedding, limit)
    params.update({
        "keyword_query": sanitized_query,
        "vector_weight": vector_weight,
        "keyword_weight": 1 - vector_weight,
    })

    return params


def _sanitize_keyword_query(query: str) -> str:
    """Sanitize a keyword query for safe use in text search.

    Args:
        query: The raw keyword query.

    Returns:
        Sanitized query string.
    """
    if not query:
        return ""

    # Remove potentially dangerous characters for tsquery
    # Allow only alphanumeric, spaces, and basic punctuation
    sanitized = re.sub(r"[^\w\s\-.,']", " ", query)

    # Collapse multiple spaces
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    # Limit length
    return sanitized[:500]


# =============================================================================
# Namespace Validation for Results
# =============================================================================

def validate_search_results(
    results: list[dict[str, Any]],
    authorized_matter_id: str,
) -> list[dict[str, Any]]:
    """Validate that all search results belong to the authorized matter.

    This is a defense-in-depth check that runs after query execution
    to ensure no cross-matter data leakage.

    Args:
        results: List of search result dictionaries.
        authorized_matter_id: The matter ID the user is authorized for.

    Returns:
        Filtered list containing only results from the authorized matter.

    Raises:
        ValueError: If authorized_matter_id is invalid.
    """
    _validate_uuid(authorized_matter_id, "authorized_matter_id")

    validated_results = []
    violations = 0

    for result in results:
        result_matter_id = result.get("matter_id")

        if result_matter_id == authorized_matter_id:
            validated_results.append(result)
        else:
            violations += 1
            logger.error(
                "cross_matter_result_detected",
                authorized_matter_id=authorized_matter_id,
                result_matter_id=result_matter_id,
                result_id=result.get("id"),
            )

    if violations > 0:
        logger.critical(
            "cross_matter_data_leakage_prevented",
            violations=violations,
            authorized_matter_id=authorized_matter_id,
            total_results=len(results),
        )

    return validated_results
