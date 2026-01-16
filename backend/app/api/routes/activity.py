"""Activity Feed API routes for Dashboard.

Story 14.5: Dashboard Real APIs (Task 5.1)

Provides endpoints for:
- GET /api/activity-feed - List activities for current user
- PATCH /api/activity-feed/{id}/read - Mark activity as read

CRITICAL: Activities are per-user (not per-matter). User isolation via RLS.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app.core.rate_limit import READONLY_RATE_LIMIT, STANDARD_RATE_LIMIT, limiter
from app.core.security import get_current_user
from app.models.activity import (
    ActivityListMeta,
    ActivityListResponse,
    ActivityResponse,
)
from app.models.auth import AuthenticatedUser
from app.services.activity_service import (
    ActivityService,
    ActivityServiceError,
    get_activity_service,
)

router = APIRouter(prefix="/activity-feed", tags=["activity"])
logger = structlog.get_logger(__name__)


def _handle_service_error(error: ActivityServiceError) -> HTTPException:
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
    "",
    response_model=ActivityListResponse,
    summary="Get Activity Feed",
    description="""
    Get recent activities for the authenticated user.

    Activities include:
    - processing_complete: Document processing finished successfully
    - processing_started: Document processing began
    - processing_failed: Document processing failed
    - contradictions_found: Contradiction engine found issues
    - verification_needed: Findings require attorney verification
    - matter_opened: User opened/viewed a matter

    Activities are per-user (not per-matter) and show activity across all matters.
    Sorted by timestamp descending (newest first).
    """,
    responses={
        200: {
            "description": "Activities retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "uuid",
                                "matterId": "uuid",
                                "matterName": "Shah v. Mehta",
                                "type": "processing_complete",
                                "description": "Processing complete",
                                "timestamp": "2026-01-16T10:00:00Z",
                                "isRead": False,
                            }
                        ],
                        "meta": {"total": 25},
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
async def get_activities(
    request: Request,  # Required for rate limiter
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Max activities to return (1-50)",
    ),
    matter_id: str | None = Query(
        None,
        alias="matterId",
        description="Optional filter by matter ID",
    ),
    user: AuthenticatedUser = Depends(get_current_user),
    activity_service: ActivityService = Depends(get_activity_service),
) -> ActivityListResponse:
    """Get recent activities for the authenticated user.

    Story 14.5: AC #1 - GET /api/activity-feed endpoint.

    Args:
        limit: Maximum activities to return (default 10, max 50).
        matter_id: Optional filter by matter.
        user: Authenticated user (from JWT).
        activity_service: Activity service instance.

    Returns:
        ActivityListResponse with activities and total count.

    Raises:
        HTTPException: On authentication errors.
    """
    try:
        logger.info(
            "activity_feed_request",
            user_id=user.id,
            limit=limit,
            matter_id=matter_id,
        )

        activities, total = await activity_service.get_activities(
            user_id=user.id,
            limit=limit,
            matter_id=matter_id,
        )

        return ActivityListResponse(
            data=activities,
            meta=ActivityListMeta(total=total),
        )

    except ActivityServiceError as e:
        logger.error(
            "activity_feed_failed",
            user_id=user.id,
            error=e.message,
            code=e.code,
        )
        raise _handle_service_error(e)
    except Exception as e:
        logger.error(
            "activity_feed_unexpected_error",
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


@router.patch(
    "/{activity_id}/read",
    response_model=ActivityResponse,
    summary="Mark Activity as Read",
    description="""
    Mark a single activity as read.

    Used when user views/dismisses an activity notification.
    Only the activity owner can mark their activities as read.
    """,
    responses={
        200: {
            "description": "Activity marked as read",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": "uuid",
                            "matterId": "uuid",
                            "matterName": "Shah v. Mehta",
                            "type": "processing_complete",
                            "description": "Processing complete",
                            "timestamp": "2026-01-16T10:00:00Z",
                            "isRead": True,
                        }
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Activity not found or belongs to another user",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Activity not found",
                            "details": {},
                        }
                    }
                }
            },
        },
    },
)
@limiter.limit(STANDARD_RATE_LIMIT)
async def mark_activity_read(
    request: Request,  # Required for rate limiter
    activity_id: str = Path(..., description="Activity ID to mark as read"),
    user: AuthenticatedUser = Depends(get_current_user),
    activity_service: ActivityService = Depends(get_activity_service),
) -> ActivityResponse:
    """Mark an activity as read.

    Story 14.5: AC #7 - PATCH /api/activity-feed/{id}/read endpoint.

    Args:
        activity_id: Activity UUID to mark as read.
        user: Authenticated user (from JWT).
        activity_service: Activity service instance.

    Returns:
        ActivityResponse with updated activity.

    Raises:
        HTTPException: On authentication errors or activity not found.
    """
    try:
        logger.info(
            "mark_activity_read_request",
            user_id=user.id,
            activity_id=activity_id,
        )

        activity = await activity_service.mark_as_read(
            activity_id=activity_id,
            user_id=user.id,
        )

        if not activity:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Activity not found",
                        "details": {},
                    }
                },
            )

        return ActivityResponse(data=activity)

    except HTTPException:
        raise
    except ActivityServiceError as e:
        logger.error(
            "mark_activity_read_failed",
            user_id=user.id,
            activity_id=activity_id,
            error=e.message,
            code=e.code,
        )
        raise _handle_service_error(e)
    except Exception as e:
        logger.error(
            "mark_activity_read_unexpected_error",
            user_id=user.id,
            activity_id=activity_id,
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
