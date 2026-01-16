"""Global Search API route for cross-matter search.

Provides a single endpoint for searching across ALL matters the user has access to.
This endpoint is NOT matter-scoped (no {matter_id} in path) since it searches
across all accessible matters.

CRITICAL: Matter isolation is enforced by the GlobalSearchService which queries
matter_attorneys to determine accessible matters.

Story 8-1/8-2 Code Review Fix: SafetyGuard integration added to prevent
bypassing guardrails via global search queries.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.global_search import GlobalSearchResponse
from app.services.global_search_service import (
    GlobalSearchService,
    GlobalSearchServiceError,
    get_global_search_service,
)
from app.services.safety import SafetyGuard, get_safety_guard

router = APIRouter(prefix="/search", tags=["search"])
logger = structlog.get_logger(__name__)


def _handle_search_error(error: GlobalSearchServiceError) -> HTTPException:
    """Convert global search service errors to HTTP exceptions."""
    status_map = {
        "DATABASE_NOT_CONFIGURED": status.HTTP_503_SERVICE_UNAVAILABLE,
        "DATABASE_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "INVALID_QUERY": status.HTTP_400_BAD_REQUEST,
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


@router.get("", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(
        ...,
        min_length=2,
        max_length=500,
        description="Search query (minimum 2 characters)",
    ),
    limit: int = Query(
        20,
        ge=1,
        le=50,
        description="Maximum number of results (default 20, max 50)",
    ),
    user: AuthenticatedUser = Depends(get_current_user),
    search_service: GlobalSearchService = Depends(get_global_search_service),
    safety_guard: SafetyGuard = Depends(get_safety_guard),
) -> GlobalSearchResponse:
    """Search across all matters the user has access to.

    This endpoint performs hybrid search (BM25 + semantic) across all matters
    the authenticated user can access. Results are merged using Reciprocal
    Rank Fusion (RRF) and include both matter title matches and document
    content matches.

    Results include:
    - **Matter matches**: Matters with titles matching the query
    - **Document matches**: Document chunks matching the query

    Each result includes:
    - id: Unique identifier (matter ID or chunk ID)
    - type: 'matter' or 'document'
    - title: Result title
    - matterId: The matter this result belongs to
    - matterTitle: Title of the matter
    - matchedContent: Snippet of matched content

    Args:
        q: Search query (2-500 characters).
        limit: Max results to return (1-50, default 20).
        user: Authenticated user (from JWT token).
        search_service: Global search service instance.

    Returns:
        GlobalSearchResponse with search results and metadata.

    Example:
        GET /api/search?q=contract%20breach&limit=10

    Response:
        {
            "data": [
                {
                    "id": "uuid",
                    "type": "matter",
                    "title": "Smith vs. Jones Contract Dispute",
                    "matterId": "uuid",
                    "matterTitle": "Smith vs. Jones Contract Dispute",
                    "matchedContent": "Contract breach regarding..."
                },
                ...
            ],
            "meta": {
                "query": "contract breach",
                "total": 10
            }
        }
    """
    # Story 8-1/8-2 Code Review Fix: Check query safety before search
    safety_result = await safety_guard.check_query(q)
    if not safety_result.is_safe:
        logger.info(
            "global_search_query_blocked_by_safety",
            user_id=user.id,
            blocked_by=safety_result.blocked_by,
            violation_type=safety_result.violation_type,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "SAFETY_VIOLATION",
                    "message": safety_result.explanation or "Query blocked by safety guard",
                    "details": {
                        "violation_type": safety_result.violation_type,
                        "suggested_rewrite": safety_result.suggested_rewrite,
                    },
                }
            },
        )

    logger.info(
        "global_search_request",
        user_id=user.id,
        query_len=len(q),
        limit=limit,
    )

    try:
        result = await search_service.search_across_matters(
            user_id=user.id,
            query=q,
            limit=limit,
        )

        logger.info(
            "global_search_response",
            user_id=user.id,
            result_count=len(result.data),
        )

        return result

    except GlobalSearchServiceError as e:
        logger.error(
            "global_search_failed",
            user_id=user.id,
            error=e.message,
            error_code=e.code,
        )
        raise _handle_search_error(e)

    except Exception as e:
        logger.error(
            "global_search_unexpected_error",
            user_id=user.id,
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
