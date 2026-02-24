"""Search models for Hybrid Search API.

Defines request/response models for the search endpoints.
All search operations are matter-isolated via the API layer.
"""

from pydantic import BaseModel, Field, model_validator


# Valid document types matching the documents table CHECK constraint
VALID_DOCUMENT_TYPES = frozenset({"case_file", "act", "annexure", "other"})


class SearchFilters(BaseModel):
    """Metadata filters for scoping search results.

    Gap 4: All fields are optional — None means "no filter".
    Filters are applied at the SQL level in all 3 search RPC functions.

    Examples:
        Search only affidavits: filters={"document_types": ["case_file"]}
        Search pages 10-30: filters={"page_min": 10, "page_max": 30}
        Search specific docs: filters={"document_ids": ["uuid1", "uuid2"]}
    """

    document_ids: list[str] | None = Field(
        None,
        description="Filter to specific document UUIDs",
    )
    document_types: list[str] | None = Field(
        None,
        description="Filter by document type: 'case_file', 'act', 'annexure', 'other'",
    )
    page_min: int | None = Field(
        None,
        ge=1,
        description="Minimum page number (inclusive)",
    )
    page_max: int | None = Field(
        None,
        ge=1,
        description="Maximum page number (inclusive)",
    )
    entity_ids: list[str] | None = Field(
        None,
        description="Filter to chunks associated with specific entity UUIDs (overlap match)",
    )

    @model_validator(mode="after")
    def validate_filters(self) -> "SearchFilters":
        """Validate filter consistency."""
        # Validate document_types are from allowed set
        if self.document_types:
            invalid = set(self.document_types) - VALID_DOCUMENT_TYPES
            if invalid:
                raise ValueError(
                    f"Invalid document_types: {invalid}. "
                    f"Must be one of: {sorted(VALID_DOCUMENT_TYPES)}"
                )

        # Validate page range consistency
        if self.page_min is not None and self.page_max is not None:
            if self.page_min > self.page_max:
                raise ValueError(
                    f"page_min ({self.page_min}) must be <= page_max ({self.page_max})"
                )

        return self

    @property
    def is_empty(self) -> bool:
        """True if no effective filters are set (all None or empty lists)."""
        return (
            not self.document_ids  # None or []
            and not self.document_types  # None or []
            and self.page_min is None
            and self.page_max is None
            and not self.entity_ids  # None or []
        )

    def to_rpc_params(self) -> dict:
        """Convert to SQL RPC parameter dict.

        Only includes non-None, non-empty values. An empty list []
        is treated as "no filter" (same as None), not "match nothing".
        """
        params: dict = {}
        if self.document_ids:  # truthy: non-None AND non-empty
            params["filter_document_ids"] = self.document_ids
        if self.document_types:  # truthy: non-None AND non-empty
            params["filter_document_types"] = self.document_types
        if self.page_min is not None:
            params["filter_page_min"] = self.page_min
        if self.page_max is not None:
            params["filter_page_max"] = self.page_max
        if self.entity_ids:  # truthy: non-None AND non-empty
            params["filter_entity_ids"] = self.entity_ids
        return params


class SearchRequest(BaseModel):
    """Request model for hybrid search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        examples=["contract termination clause"],
    )
    limit: int = Field(
        20,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )
    bm25_weight: float = Field(
        1.0,
        ge=0.0,
        le=2.0,
        description="Weight for BM25 keyword search (0.0-2.0)",
    )
    semantic_weight: float = Field(
        1.0,
        ge=0.0,
        le=2.0,
        description="Weight for semantic similarity search (0.0-2.0)",
    )
    rerank: bool = Field(
        False,
        description="Apply Cohere Rerank v3.5 to refine results (default: false)",
    )
    rerank_top_n: int = Field(
        3,
        ge=1,
        le=20,
        description="Number of top results after reranking (only used when rerank=true)",
    )
    filters: SearchFilters | None = Field(
        None,
        description="Optional metadata filters to scope search results",
    )


class SearchResultItem(BaseModel):
    """Single search result item."""

    id: str = Field(..., description="Chunk UUID")
    document_id: str = Field(..., description="Source document UUID")
    content: str = Field(..., description="Chunk text content")
    page_number: int | None = Field(None, description="Source page number")
    chunk_type: str = Field(..., description="Chunk type: 'parent' or 'child'")
    token_count: int = Field(..., description="Number of tokens in chunk")
    bm25_rank: int | None = Field(None, description="Rank from BM25 search")
    semantic_rank: int | None = Field(None, description="Rank from semantic search")
    rrf_score: float = Field(..., description="Combined RRF fusion score")
    relevance_score: float | None = Field(
        None,
        description="Cohere relevance score (0.0-1.0). Only present when rerank=true.",
    )


class SearchMeta(BaseModel):
    """Metadata about the search results."""

    query: str = Field(..., description="Original search query")
    matter_id: str = Field(..., description="Matter UUID searched")
    total_candidates: int = Field(..., description="Total candidates before limit")
    bm25_weight: float = Field(..., description="BM25 weight used")
    semantic_weight: float = Field(..., description="Semantic weight used")
    rerank_used: bool | None = Field(
        None,
        description="True if Cohere reranking was used. None if rerank was not requested.",
    )
    fallback_reason: str | None = Field(
        None,
        description="Reason for fallback if rerank_used is False.",
    )


class SearchResponse(BaseModel):
    """Response model for hybrid search."""

    data: list[SearchResultItem] = Field(..., description="Search results")
    meta: SearchMeta = Field(..., description="Search metadata")


class BM25SearchRequest(BaseModel):
    """Request model for BM25-only keyword search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        examples=["Section 138 NI Act"],
    )
    limit: int = Field(
        30,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )


class SemanticSearchRequest(BaseModel):
    """Request model for semantic-only vector search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        examples=["breach of contract remedies"],
    )
    limit: int = Field(
        30,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )


class SingleModeSearchMeta(BaseModel):
    """Metadata for single-mode search results."""

    query: str = Field(..., description="Original search query")
    matter_id: str = Field(..., description="Matter UUID searched")
    result_count: int = Field(..., description="Number of results returned")
    search_type: str = Field(..., description="Search type: 'bm25' or 'semantic'")


class SingleModeSearchResponse(BaseModel):
    """Response model for BM25 or semantic-only search."""

    data: list[SearchResultItem] = Field(..., description="Search results")
    meta: SingleModeSearchMeta = Field(..., description="Search metadata")


# =============================================================================
# Alias-Expanded Search Models (Story 2c-2)
# =============================================================================


class AliasExpandedSearchRequest(BaseModel):
    """Request model for alias-expanded search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text (entity names will be expanded with aliases)",
        examples=["N.D. Jobalia contract"],
    )
    limit: int = Field(
        20,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )
    expand_aliases: bool = Field(
        True,
        description="Expand entity names in query to include known aliases",
    )
    bm25_weight: float = Field(
        1.0,
        ge=0.0,
        le=2.0,
        description="Weight for BM25 keyword search (0.0-2.0)",
    )
    semantic_weight: float = Field(
        1.0,
        ge=0.0,
        le=2.0,
        description="Weight for semantic similarity search (0.0-2.0)",
    )
    rerank: bool = Field(
        False,
        description="Apply Cohere Rerank v3.5 to refine results (default: false)",
    )
    rerank_top_n: int = Field(
        3,
        ge=1,
        le=20,
        description="Number of top results after reranking (only used when rerank=true)",
    )


class FuzzyMatchInfo(BaseModel):
    """Information about a fuzzy entity match."""

    query_term: str = Field(..., description="The term from the query that was matched")
    matched_entity: str = Field(..., description="The canonical entity name that was matched")
    match_score: float = Field(..., description="Match confidence score (0-100)")
    is_exact: bool = Field(..., description="True if exact match, False if fuzzy")


class AliasExpandedSearchMeta(BaseModel):
    """Metadata for alias-expanded search results."""

    query: str = Field(..., description="Original search query")
    expanded_query: str | None = Field(
        None, description="Query after alias expansion (if expansion was applied)"
    )
    matter_id: str = Field(..., description="Matter UUID searched")
    total_candidates: int = Field(..., description="Total candidates before limit")
    bm25_weight: float = Field(..., description="BM25 weight used")
    semantic_weight: float = Field(..., description="Semantic weight used")
    aliases_found: list[str] = Field(
        default_factory=list,
        description="List of aliases that were expanded",
    )
    entities_matched: list[str] = Field(
        default_factory=list,
        description="Entity names from query that matched MIG entities",
    )
    fuzzy_matches: list[FuzzyMatchInfo] = Field(
        default_factory=list,
        description="Details of fuzzy matches used (empty if all exact matches)",
    )
    rerank_used: bool | None = Field(
        None,
        description="True if Cohere reranking was used. None if not requested.",
    )
    fallback_reason: str | None = Field(
        None, description="Reason for fallback if rerank_used is False."
    )


class AliasExpandedSearchResponse(BaseModel):
    """Response model for alias-expanded search."""

    data: list[SearchResultItem] = Field(..., description="Search results")
    meta: AliasExpandedSearchMeta = Field(..., description="Search metadata")
