"""Dashboard API routes for aggregated statistics.

Story 14.5: Dashboard Real APIs (Task 5.2)

Provides endpoints for:
- GET /api/dashboard/stats - Get dashboard statistics

CRITICAL: Stats are per-user - aggregated across all matters user has access to.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.rate_limit import READONLY_RATE_LIMIT, limiter
from app.core.security import get_current_user
from app.models.activity import DashboardStatsResponse
from app.models.auth import AuthenticatedUser
from app.services.dashboard_stats_service import (
    DashboardStatsService,
    DashboardStatsServiceError,
    get_dashboard_stats_service,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = structlog.get_logger(__name__)


def _handle_service_error(error: DashboardStatsServiceError) -> HTTPException:
    """Convert service errors to HTTP exceptions."""
    return HTTPException(
        status_code=error.status_code,
        detail={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {},
            }
        },
    )


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get Dashboard Statistics",
    description="""
    Get aggregated dashboard statistics for the authenticated user.

    Returns:
    - activeMatters: Count of non-archived matters the user has access to
    - verifiedFindings: Count of verified findings across all user's matters
    - pendingReviews: Count of findings awaiting verification across all matters

    Performance: Uses efficient SQL aggregation, completes in <500ms.
    Stats update on 30-second polling in the frontend.
    """,
    responses={
        200: {
            "description": "Statistics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "activeMatters": 5,
                            "verifiedFindings": 127,
                            "pendingReviews": 3,
                        }
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_AUTHENTICATED",
                            "message": "Authentication required",
                            "details": {},
                        }
                    }
                }
            },
        },
    },
)
@limiter.limit(READONLY_RATE_LIMIT)
async def get_dashboard_stats(
    request: Request,  # Required for rate limiter
    user: AuthenticatedUser = Depends(get_current_user),
    stats_service: DashboardStatsService = Depends(get_dashboard_stats_service),
) -> DashboardStatsResponse:
    """Get dashboard statistics for the authenticated user.

    Story 14.5: AC #2 - GET /api/dashboard/stats endpoint.

    Args:
        user: Authenticated user (from JWT).
        stats_service: Dashboard stats service instance.

    Returns:
        DashboardStatsResponse with aggregated stats.

    Raises:
        HTTPException: On authentication errors.
    """
    try:
        logger.info(
            "dashboard_stats_request",
            user_id=user.id,
        )

        stats = await stats_service.get_dashboard_stats(user_id=user.id)

        return DashboardStatsResponse(data=stats)

    except DashboardStatsServiceError as e:
        logger.error(
            "dashboard_stats_failed",
            user_id=user.id,
            error=e.message,
            code=e.code,
        )
        raise _handle_service_error(e)
    except Exception as e:
        logger.error(
            "dashboard_stats_unexpected_error",
            user_id=user.id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        ) from e
