"""Contradiction API routes for entity statement querying and comparison.

Story 5-1: Entity-Grouped Statement Querying
Story 5-2: Statement Pair Comparison

Provides endpoints for:
- GET /api/contradictions/entities/{entity_id}/statements - Get statements about an entity
- POST /api/contradictions/entities/{entity_id}/compare - Compare statement pairs for contradictions

Part of Epic 5: Consistency & Contradiction Engine.
"""

from math import ceil
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
)
from app.models.contradiction import (
    ContradictionErrorResponse,
    EntityComparisonsResponse,
    EntityStatementsResponse,
    PaginationMeta,
)
from app.services.contradiction import (
    StatementQueryService,
    get_statement_query_service,
    StatementComparisonService,
    get_statement_comparison_service,
)
from app.services.contradiction.statement_query import (
    EntityNotFoundError,
    StatementQueryError,
)
from app.services.contradiction.comparator import (
    ComparisonServiceError,
    TooManyStatementsError,
)

router = APIRouter(
    prefix="/matters/{matter_id}/contradictions",
    tags=["contradictions"],
)
logger = structlog.get_logger(__name__)


def _get_statement_service() -> StatementQueryService:
    """Get statement query service instance."""
    return get_statement_query_service()


def _get_comparison_service() -> StatementComparisonService:
    """Get statement comparison service instance (Story 5-2).

    Returns:
        StatementComparisonService: Singleton service for GPT-4 statement comparison.
    """
    return get_statement_comparison_service()


# =============================================================================
# Entity Statements Endpoint
# =============================================================================


@router.get(
    "/entities/{entity_id}/statements",
    response_model=EntityStatementsResponse,
    responses={
        404: {"model": ContradictionErrorResponse, "description": "Entity not found"},
        500: {"model": ContradictionErrorResponse, "description": "Internal error"},
    },
)
async def get_entity_statements(
    matter_id: Annotated[str, Path(description="Matter UUID")],
    entity_id: Annotated[str, Path(description="Entity UUID")],
    include_aliases: Annotated[
        bool,
        Query(
            alias="includeAliases",
            description="Include statements from entity aliases (AC #2)",
        ),
    ] = True,
    document_ids: Annotated[
        list[str] | None,
        Query(
            alias="documentIds",
            description="Filter by document UUIDs (comma-separated)",
        ),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[
        int,
        Query(ge=1, le=100, alias="perPage", description="Items per page"),
    ] = 50,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    service: StatementQueryService = Depends(_get_statement_service),
) -> EntityStatementsResponse:
    """Get all statements about an entity, grouped by document.

    Retrieves all chunks mentioning the specified entity (by canonical_id
    or aliases) and groups them by document source. Each statement includes
    extracted dates and amounts for comparison.

    **Acceptance Criteria:**
    - AC #1: Retrieves chunks mentioning entity, grouped by document
    - AC #2: When includeAliases=true, includes mentions of all aliases
    - AC #3: Extracts dates/amounts from each statement
    - AC #4: Returns empty result (not error) when no statements exist

    **Query Parameters:**
    - includeAliases: If true (default), include statements from entity aliases
    - documentIds: Optional filter to specific documents
    - page/perPage: Pagination controls

    Args:
        matter_id: Matter UUID.
        entity_id: Entity UUID to query.
        include_aliases: Include alias entity matches.
        document_ids: Optional document ID filter.
        page: Page number (1-indexed).
        per_page: Items per page.
        membership: Validated matter membership.
        service: Statement query service.

    Returns:
        EntityStatementsResponse with grouped statements and pagination.

    Raises:
        HTTPException 404: If entity not found in matter.
        HTTPException 500: If query fails.
    """
    logger.info(
        "get_entity_statements_api_request",
        matter_id=matter_id,
        entity_id=entity_id,
        include_aliases=include_aliases,
        document_ids=document_ids,
        page=page,
        per_page=per_page,
        user_id=membership.user_id,
    )

    try:
        response = await service.get_entity_statements(
            entity_id=entity_id,
            matter_id=matter_id,
            include_aliases=include_aliases,
            document_ids=document_ids,
            page=page,
            per_page=per_page,
        )

        logger.info(
            "get_entity_statements_api_success",
            matter_id=matter_id,
            entity_id=entity_id,
            total_statements=response.data.total_statements,
            document_count=len(response.data.documents),
        )

        return response

    except EntityNotFoundError as e:
        logger.warning(
            "get_entity_statements_api_not_found",
            matter_id=matter_id,
            entity_id=entity_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ENTITY_NOT_FOUND",
                    "message": f"Entity {entity_id} not found in matter {matter_id}",
                    "details": {},
                }
            },
        ) from e

    except StatementQueryError as e:
        logger.error(
            "get_entity_statements_api_query_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        ) from e

    except Exception as e:
        logger.error(
            "get_entity_statements_api_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve entity statements",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Entity Statement Comparison Endpoint (Story 5-2)
# =============================================================================


@router.post(
    "/entities/{entity_id}/compare",
    response_model=EntityComparisonsResponse,
    responses={
        404: {"model": ContradictionErrorResponse, "description": "Entity not found"},
        422: {"model": ContradictionErrorResponse, "description": "Too many statements for sync processing"},
        500: {"model": ContradictionErrorResponse, "description": "Internal error"},
    },
)
async def compare_entity_statements(
    matter_id: Annotated[str, Path(description="Matter UUID")],
    entity_id: Annotated[str, Path(description="Entity UUID")],
    max_pairs: Annotated[
        int,
        Query(
            alias="maxPairs",
            ge=1,
            le=200,
            description="Maximum pairs to compare (cost control, default 50)",
        ),
    ] = 50,
    confidence_threshold: Annotated[
        float,
        Query(
            alias="confidenceThreshold",
            ge=0.0,
            le=1.0,
            description="Minimum confidence to include (default 0.5)",
        ),
    ] = 0.5,
    include_aliases: Annotated[
        bool,
        Query(
            alias="includeAliases",
            description="Include statements from entity aliases",
        ),
    ] = True,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    service: StatementComparisonService = Depends(_get_comparison_service),
) -> EntityComparisonsResponse:
    """Compare statement pairs for an entity to detect contradictions.

    Uses GPT-4 chain-of-thought reasoning to analyze statement pairs
    and identify contradictions. Returns reasoning for attorney review.

    **Acceptance Criteria:**
    - AC #1: Each unique pair of statements is compared
    - AC #2: Contradictions with amount/date mismatches are detected
    - AC #3: Consistent pairs are marked as "consistent"
    - AC #4: Chain-of-thought reasoning is recorded for review

    **Query Parameters:**
    - maxPairs: Maximum pairs to compare (default 50, max 200) for cost control
    - confidenceThreshold: Minimum confidence to include results (default 0.5)
    - includeAliases: If true (default), include statements from entity aliases

    **Cost Control:**
    - Each GPT-4 comparison costs ~$0.03-0.05
    - maxPairs=50 limits cost to ~$2.50 per entity
    - Use GET /statements first to check statement count

    **Async Processing:**
    - Entities with >100 statements return 422 with instruction to use async endpoint

    Args:
        matter_id: Matter UUID.
        entity_id: Entity UUID to compare statements for.
        max_pairs: Maximum pairs to compare.
        confidence_threshold: Minimum confidence filter.
        include_aliases: Include alias entity matches.
        membership: Validated matter membership (EDITOR or OWNER required).
        service: Statement comparison service.

    Returns:
        EntityComparisonsResponse with comparison results and cost metadata.

    Raises:
        HTTPException 404: If entity not found in matter.
        HTTPException 422: If >100 statements (use async processing).
        HTTPException 500: If comparison fails.
    """
    logger.info(
        "compare_entity_statements_api_request",
        matter_id=matter_id,
        entity_id=entity_id,
        max_pairs=max_pairs,
        confidence_threshold=confidence_threshold,
        include_aliases=include_aliases,
        user_id=membership.user_id,
    )

    try:
        response = await service.compare_entity_statements(
            entity_id=entity_id,
            matter_id=matter_id,
            max_pairs=max_pairs,
            confidence_threshold=confidence_threshold,
            include_aliases=include_aliases,
        )

        logger.info(
            "compare_entity_statements_api_success",
            matter_id=matter_id,
            entity_id=entity_id,
            pairs_compared=response.meta.pairs_compared,
            contradictions_found=response.meta.contradictions_found,
            total_cost_usd=response.meta.total_cost_usd,
        )

        return response

    except EntityNotFoundError as e:
        logger.warning(
            "compare_entity_statements_api_not_found",
            matter_id=matter_id,
            entity_id=entity_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ENTITY_NOT_FOUND",
                    "message": f"Entity {entity_id} not found in matter {matter_id}",
                    "details": {},
                }
            },
        ) from e

    except TooManyStatementsError as e:
        logger.warning(
            "compare_entity_statements_api_too_many",
            matter_id=matter_id,
            entity_id=entity_id,
            statement_count=e.statement_count,
            threshold=e.threshold,
        )
        raise HTTPException(
            status_code=422,  # Unprocessable Content
            detail={
                "error": {
                    "code": "TOO_MANY_STATEMENTS",
                    "message": e.message,
                    "details": {
                        "statementCount": e.statement_count,
                        "threshold": e.threshold,
                        "hint": "Use async processing endpoint for large entities",
                    },
                }
            },
        ) from e

    except ComparisonServiceError as e:
        logger.error(
            "compare_entity_statements_api_service_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        ) from e

    except Exception as e:
        logger.error(
            "compare_entity_statements_api_error",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to compare entity statements",
                    "details": {},
                }
            },
        ) from e
