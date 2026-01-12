"""Search API routes with matter-isolated hybrid search.

Provides endpoints for:
- Hybrid search (BM25 + semantic with RRF fusion)
- BM25-only keyword search
- Semantic-only vector search
- Reranked search (hybrid + Cohere Rerank v3.5)
- Alias-expanded search (expands person/org names to include aliases)

All endpoints enforce 4-layer matter isolation via the API layer.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
)
from app.models.search import (
    AliasExpandedSearchMeta,
    AliasExpandedSearchRequest,
    AliasExpandedSearchResponse,
    BM25SearchRequest,
    SearchMeta,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SemanticSearchRequest,
    SingleModeSearchMeta,
    SingleModeSearchResponse,
)
from app.services.mig import MIGGraphService, get_mig_graph_service
from app.models.rerank import (
    RerankRequest,
    RerankedSearchMeta,
    RerankedSearchResponse,
    RerankedSearchResultItem,
)
from app.services.rag.hybrid_search import (
    HybridSearchService,
    HybridSearchServiceError,
    SearchWeights,
    get_hybrid_search_service,
)

router = APIRouter(prefix="/matters/{matter_id}/search", tags=["search"])
logger = structlog.get_logger(__name__)


def _handle_search_error(error: HybridSearchServiceError) -> HTTPException:
    """Convert search service errors to HTTP exceptions."""
    status_map = {
        "INVALID_PARAMETER": status.HTTP_400_BAD_REQUEST,
        "DATABASE_NOT_CONFIGURED": status.HTTP_503_SERVICE_UNAVAILABLE,
        "EMBEDDING_GENERATION_FAILED": status.HTTP_502_BAD_GATEWAY,
    }

    http_status = status_map.get(error.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    return HTTPException(
        status_code=http_status,
        detail={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {},
            }
        },
    )


def _result_to_item(result, relevance_score: float | None = None) -> SearchResultItem:
    """Convert SearchResult to SearchResultItem.

    Args:
        result: SearchResult or RerankedSearchResultItem dataclass.
        relevance_score: Optional relevance score to include.
    """
    return SearchResultItem(
        id=result.id,
        document_id=result.document_id,
        content=result.content,
        page_number=result.page_number,
        chunk_type=result.chunk_type,
        token_count=result.token_count,
        bm25_rank=result.bm25_rank,
        semantic_rank=result.semantic_rank,
        rrf_score=result.rrf_score,
        relevance_score=relevance_score,
    )


def _reranked_result_to_item(result) -> RerankedSearchResultItem:
    """Convert RerankedSearchResultItem dataclass to Pydantic model."""
    return RerankedSearchResultItem(
        id=result.id,
        document_id=result.document_id,
        content=result.content,
        page_number=result.page_number,
        chunk_type=result.chunk_type,
        token_count=result.token_count,
        bm25_rank=result.bm25_rank,
        semantic_rank=result.semantic_rank,
        rrf_score=result.rrf_score,
        relevance_score=result.relevance_score,
    )


@router.post("", response_model=SearchResponse)
async def hybrid_search(
    request: SearchRequest,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> SearchResponse:
    """Execute hybrid search with BM25 + semantic RRF fusion.

    Combines keyword-based BM25 search with semantic similarity search
    using Reciprocal Rank Fusion (RRF) for optimal relevance.

    Set `rerank=true` to enable Cohere Rerank v3.5 for improved precision.
    When enabled, returns top `rerank_top_n` results (default 3) with
    relevance scores from Cohere.

    Best for general-purpose retrieval where both exact terms and
    conceptual similarity matter.

    Args:
        request: Search parameters including query, weights, limit, and rerank options.
        membership: Validated matter membership (ensures access).

    Returns:
        Ranked search results with RRF scores (and relevance_score if rerank=true).

    Example query: "contract termination due to breach"
    """
    logger.info(
        "hybrid_search_request",
        matter_id=membership.matter_id,
        user_id=membership.user_id,
        query_len=len(request.query),
        limit=request.limit,
        bm25_weight=request.bm25_weight,
        semantic_weight=request.semantic_weight,
        rerank=request.rerank,
        rerank_top_n=request.rerank_top_n if request.rerank else None,
    )

    try:
        search_service = get_hybrid_search_service()

        weights = SearchWeights(
            bm25=request.bm25_weight,
            semantic=request.semantic_weight,
        )

        # Use rerank pipeline if requested
        if request.rerank:
            result = await search_service.search_with_rerank(
                query=request.query,
                matter_id=membership.matter_id,
                hybrid_limit=request.limit,
                rerank_top_n=request.rerank_top_n,
                weights=weights,
            )

            items = [
                _result_to_item(r, relevance_score=r.relevance_score)
                for r in result.results
            ]

            return SearchResponse(
                data=items,
                meta=SearchMeta(
                    query=result.query,
                    matter_id=result.matter_id,
                    total_candidates=result.total_candidates,
                    bm25_weight=result.weights.bm25,
                    semantic_weight=result.weights.semantic,
                    rerank_used=result.rerank_used,
                    fallback_reason=result.fallback_reason,
                ),
            )

        # Standard hybrid search (no reranking)
        result = await search_service.search(
            query=request.query,
            matter_id=membership.matter_id,
            limit=request.limit,
            weights=weights,
        )

        items = [_result_to_item(r) for r in result.results]

        return SearchResponse(
            data=items,
            meta=SearchMeta(
                query=result.query,
                matter_id=result.matter_id,
                total_candidates=result.total_candidates,
                bm25_weight=result.weights.bm25,
                semantic_weight=result.weights.semantic,
                rerank_used=None,  # Not requested
                fallback_reason=None,
            ),
        )

    except HybridSearchServiceError as e:
        logger.error(
            "hybrid_search_failed",
            matter_id=membership.matter_id,
            error=e.message,
            error_code=e.code,
        )
        raise _handle_search_error(e)

    except Exception as e:
        logger.error(
            "hybrid_search_unexpected_error",
            matter_id=membership.matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "SEARCH_FAILED",
                    "message": "An unexpected error occurred during search",
                    "details": {},
                }
            },
        )


@router.post("/bm25", response_model=SingleModeSearchResponse)
async def bm25_search(
    request: BM25SearchRequest,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> SingleModeSearchResponse:
    """Execute BM25-only keyword search.

    Uses PostgreSQL full-text search with ts_rank_cd for ranking.
    Best for finding specific terms, legal citations, or exact phrases.

    Args:
        request: Search parameters including query and limit.
        membership: Validated matter membership (ensures access).

    Returns:
        Ranked search results by BM25 score.

    Example query: "Section 138 Negotiable Instruments Act"
    """
    logger.info(
        "bm25_search_request",
        matter_id=membership.matter_id,
        user_id=membership.user_id,
        query_len=len(request.query),
        limit=request.limit,
    )

    try:
        search_service = get_hybrid_search_service()

        results = await search_service.bm25_search(
            query=request.query,
            matter_id=membership.matter_id,
            limit=request.limit,
        )

        items = [_result_to_item(r) for r in results]

        return SingleModeSearchResponse(
            data=items,
            meta=SingleModeSearchMeta(
                query=request.query,
                matter_id=membership.matter_id,
                result_count=len(items),
                search_type="bm25",
            ),
        )

    except HybridSearchServiceError as e:
        logger.error(
            "bm25_search_failed",
            matter_id=membership.matter_id,
            error=e.message,
            error_code=e.code,
        )
        raise _handle_search_error(e)

    except Exception as e:
        logger.error(
            "bm25_search_unexpected_error",
            matter_id=membership.matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "SEARCH_FAILED",
                    "message": "An unexpected error occurred during search",
                    "details": {},
                }
            },
        )


@router.post("/semantic", response_model=SingleModeSearchResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> SingleModeSearchResponse:
    """Execute semantic-only vector search.

    Uses OpenAI embeddings with pgvector HNSW index.
    Best for conceptual similarity, paraphrased queries, and abstract concepts.

    Args:
        request: Search parameters including query and limit.
        membership: Validated matter membership (ensures access).

    Returns:
        Ranked search results by cosine similarity.

    Example query: "remedies available when one party fails to perform obligations"
    """
    logger.info(
        "semantic_search_request",
        matter_id=membership.matter_id,
        user_id=membership.user_id,
        query_len=len(request.query),
        limit=request.limit,
    )

    try:
        search_service = get_hybrid_search_service()

        results = await search_service.semantic_search(
            query=request.query,
            matter_id=membership.matter_id,
            limit=request.limit,
        )

        items = [_result_to_item(r) for r in results]

        return SingleModeSearchResponse(
            data=items,
            meta=SingleModeSearchMeta(
                query=request.query,
                matter_id=membership.matter_id,
                result_count=len(items),
                search_type="semantic",
            ),
        )

    except HybridSearchServiceError as e:
        logger.error(
            "semantic_search_failed",
            matter_id=membership.matter_id,
            error=e.message,
            error_code=e.code,
        )
        raise _handle_search_error(e)

    except Exception as e:
        logger.error(
            "semantic_search_unexpected_error",
            matter_id=membership.matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "SEARCH_FAILED",
                    "message": "An unexpected error occurred during search",
                    "details": {},
                }
            },
        )


@router.post("/rerank", response_model=RerankedSearchResponse)
async def rerank_search(
    request: RerankRequest,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> RerankedSearchResponse:
    """Execute hybrid search with Cohere Rerank v3.5.

    Combines hybrid BM25+semantic search with Cohere reranking.
    The pipeline:
    1. Hybrid search returns top N candidates (default 20)
    2. Cohere Rerank v3.5 scores each candidate by query relevance
    3. Returns top K most relevant results (default 3)

    This approach improves search precision by 40-70% for legal documents.

    FALLBACK: If Cohere API fails, returns RRF-ranked results from
    hybrid search. The `rerank_used` field in meta indicates whether
    Cohere was successfully used.

    Args:
        request: Search parameters including query, limits, and weights.
        membership: Validated matter membership (ensures access).

    Returns:
        Reranked search results with relevance_score from Cohere.

    Example query: "contract termination clause"
    """
    logger.info(
        "rerank_search_request",
        matter_id=membership.matter_id,
        user_id=membership.user_id,
        query_len=len(request.query),
        limit=request.limit,
        top_n=request.top_n,
        bm25_weight=request.bm25_weight,
        semantic_weight=request.semantic_weight,
    )

    try:
        search_service = get_hybrid_search_service()

        weights = SearchWeights(
            bm25=request.bm25_weight,
            semantic=request.semantic_weight,
        )

        result = await search_service.search_with_rerank(
            query=request.query,
            matter_id=membership.matter_id,
            hybrid_limit=request.limit,
            rerank_top_n=request.top_n,
            weights=weights,
        )

        items = [_reranked_result_to_item(r) for r in result.results]

        return RerankedSearchResponse(
            data=items,
            meta=RerankedSearchMeta(
                query=result.query,
                matter_id=result.matter_id,
                total_candidates=result.total_candidates,
                bm25_weight=result.weights.bm25,
                semantic_weight=result.weights.semantic,
                rerank_used=result.rerank_used,
                fallback_reason=result.fallback_reason,
            ),
        )

    except HybridSearchServiceError as e:
        logger.error(
            "rerank_search_failed",
            matter_id=membership.matter_id,
            error=e.message,
            error_code=e.code,
        )
        raise _handle_search_error(e)

    except Exception as e:
        logger.error(
            "rerank_search_unexpected_error",
            matter_id=membership.matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RERANK_FAILED",
                    "message": "An unexpected error occurred during rerank search",
                    "details": {},
                }
            },
        )


@router.post("/alias-expanded", response_model=AliasExpandedSearchResponse)
async def alias_expanded_search(
    request: AliasExpandedSearchRequest,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
) -> AliasExpandedSearchResponse:
    """Execute search with automatic alias expansion.

    Expands entity names in the query to include known aliases from the
    Matter Identity Graph (MIG). For example, searching for "N.D. Jobalia"
    will also match documents containing "Nirav D. Jobalia" or "Mr. Jobalia".

    Process:
    1. Extract potential entity names from the query
    2. Match against MIG entities (by canonical name or alias)
    3. Expand query to include all known aliases
    4. Execute hybrid search with expanded query
    5. Optionally apply Cohere Rerank

    Args:
        request: Search parameters including query and alias expansion options.
        membership: Validated matter membership (ensures access).

    Returns:
        Search results with alias expansion metadata.

    Example query: "N.D. Jobalia contract"
    Expanded query: "(N.D. Jobalia OR Nirav D. Jobalia OR Mr. Jobalia) contract"
    """
    logger.info(
        "alias_expanded_search_request",
        matter_id=membership.matter_id,
        user_id=membership.user_id,
        query_len=len(request.query),
        limit=request.limit,
        expand_aliases=request.expand_aliases,
        rerank=request.rerank,
    )

    try:
        search_service = get_hybrid_search_service()
        mig_service = get_mig_graph_service()

        # Track expansion metadata
        aliases_found: list[str] = []
        entities_matched: list[str] = []
        expanded_query = request.query

        # Expand aliases if enabled
        if request.expand_aliases:
            # Get all entities for this matter
            import asyncio
            entities = await mig_service.get_entities(matter_id=membership.matter_id)

            if entities:
                # Find entity names that appear in the query
                query_lower = request.query.lower()

                for entity in entities:
                    canonical_lower = entity.canonical_name.lower()
                    aliases_list = entity.aliases or []

                    # Check if canonical name or any alias appears in query
                    matched = False
                    matched_name = ""

                    if canonical_lower in query_lower:
                        matched = True
                        matched_name = entity.canonical_name
                    else:
                        for alias in aliases_list:
                            if alias.lower() in query_lower:
                                matched = True
                                matched_name = alias
                                break

                    if matched:
                        entities_matched.append(entity.canonical_name)

                        # Collect all name variants for this entity
                        all_variants = [entity.canonical_name] + (aliases_list or [])

                        # Remove the matched name from variants for expansion
                        other_variants = [v for v in all_variants if v.lower() != matched_name.lower()]

                        if other_variants:
                            aliases_found.extend(other_variants)

                            # Build OR query: replace matched name with (name OR alias1 OR alias2)
                            # Use case-insensitive replacement
                            import re
                            or_clause = f'({matched_name} OR {" OR ".join(other_variants)})'
                            expanded_query = re.sub(
                                re.escape(matched_name),
                                or_clause,
                                expanded_query,
                                flags=re.IGNORECASE,
                                count=1,  # Only replace first occurrence
                            )

        weights = SearchWeights(
            bm25=request.bm25_weight,
            semantic=request.semantic_weight,
        )

        # Execute search (with expanded query for BM25, original for semantic)
        if request.rerank:
            result = await search_service.search_with_rerank(
                query=expanded_query,
                matter_id=membership.matter_id,
                hybrid_limit=request.limit,
                rerank_top_n=request.rerank_top_n,
                weights=weights,
            )

            items = [
                _result_to_item(r, relevance_score=r.relevance_score)
                for r in result.results
            ]

            return AliasExpandedSearchResponse(
                data=items,
                meta=AliasExpandedSearchMeta(
                    query=request.query,
                    expanded_query=expanded_query if expanded_query != request.query else None,
                    matter_id=membership.matter_id,
                    total_candidates=result.total_candidates,
                    bm25_weight=result.weights.bm25,
                    semantic_weight=result.weights.semantic,
                    aliases_found=aliases_found,
                    entities_matched=entities_matched,
                    rerank_used=result.rerank_used,
                    fallback_reason=result.fallback_reason,
                ),
            )

        # Standard hybrid search
        result = await search_service.search(
            query=expanded_query,
            matter_id=membership.matter_id,
            limit=request.limit,
            weights=weights,
        )

        items = [_result_to_item(r) for r in result.results]

        return AliasExpandedSearchResponse(
            data=items,
            meta=AliasExpandedSearchMeta(
                query=request.query,
                expanded_query=expanded_query if expanded_query != request.query else None,
                matter_id=membership.matter_id,
                total_candidates=result.total_candidates,
                bm25_weight=result.weights.bm25,
                semantic_weight=result.weights.semantic,
                aliases_found=aliases_found,
                entities_matched=entities_matched,
                rerank_used=None,
                fallback_reason=None,
            ),
        )

    except HybridSearchServiceError as e:
        logger.error(
            "alias_expanded_search_failed",
            matter_id=membership.matter_id,
            error=e.message,
            error_code=e.code,
        )
        raise _handle_search_error(e)

    except Exception as e:
        logger.error(
            "alias_expanded_search_unexpected_error",
            matter_id=membership.matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ALIAS_SEARCH_FAILED",
                    "message": "An unexpected error occurred during alias-expanded search",
                    "details": {},
                }
            },
        )
