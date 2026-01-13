"""Contradiction API routes for entity statement querying.

Story 5-1: Entity-Grouped Statement Querying

Provides endpoints for:
- GET /api/contradictions/entities/{entity_id}/statements - Get statements about an entity

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
    EntityStatementsResponse,
    PaginationMeta,
)
from app.services.contradiction import (
    StatementQueryService,
    get_statement_query_service,
)
from app.services.contradiction.statement_query import (
    EntityNotFoundError,
    StatementQueryError,
)

router = APIRouter(
    prefix="/matters/{matter_id}/contradictions",
    tags=["contradictions"],
)
logger = structlog.get_logger(__name__)


def _get_statement_service() -> StatementQueryService:
    """Get statement query service instance."""
    return get_statement_query_service()


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
