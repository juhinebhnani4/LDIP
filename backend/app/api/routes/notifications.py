"""Notification API routes for Dashboard.

Story 14.10: Notifications Backend & Frontend Wiring (Task 4)

Provides endpoints for:
- GET /api/notifications - List notifications for current user
- PATCH /api/notifications/{id}/read - Mark notification as read
- POST /api/notifications/read-all - Mark all notifications as read

CRITICAL: Notifications are per-user (not per-matter). User isolation via RLS.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.notification import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
)
from app.services.notification_service import (
    NotificationService,
    NotificationServiceError,
    get_notification_service,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = structlog.get_logger(__name__)


def _handle_service_error(error: NotificationServiceError) -> HTTPException:
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


# =============================================================================
# Task 4.2: GET /api/notifications (AC #2)
# =============================================================================


@router.get(
    "",
    response_model=NotificationListResponse,
    response_model_by_alias=True,
    summary="Get Notifications",
    description="""
    Get notifications for the authenticated user.

    Notifications include:
    - success: Processing complete, verification done
    - info: Login, opened matter
    - in_progress: Upload started, processing
    - warning: Contradictions found, verification needed
    - error: Processing failed, upload error

    Notifications are per-user (not per-matter) and show across all matters.
    Sorted by created_at descending (newest first).
    """,
    responses={
        200: {
            "description": "Notifications retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "uuid",
                                "type": "success",
                                "title": "Processing Complete",
                                "message": "Document 'Contract.pdf' has been processed.",
                                "matterId": "uuid",
                                "matterTitle": "Shah v. Mehta",
                                "isRead": False,
                                "createdAt": "2026-01-16T10:00:00Z",
                                "priority": "medium",
                            }
                        ],
                        "unreadCount": 5,
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
async def get_notifications(
    limit: int = Query(
        20,
        ge=1,
        le=50,
        description="Max notifications to return (1-50)",
    ),
    unread_only: bool = Query(
        False,
        alias="unread_only",
        description="If true, only return unread notifications",
    ),
    user: AuthenticatedUser = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    """Get notifications for the authenticated user.

    Story 14.10: AC #2 - GET /api/notifications endpoint.

    Args:
        limit: Maximum notifications to return (default 20, max 50).
        unread_only: If true, only return unread notifications.
        user: Authenticated user (from JWT).
        notification_service: Notification service instance.

    Returns:
        NotificationListResponse with notifications and unread count.

    Raises:
        HTTPException: On authentication errors.
    """
    try:
        logger.info(
            "notifications_request",
            user_id=user.id,
            limit=limit,
            unread_only=unread_only,
        )

        notifications, unread_count = await notification_service.get_notifications(
            user_id=user.id,
            limit=limit,
            unread_only=unread_only,
        )

        return NotificationListResponse(
            data=notifications,
            unread_count=unread_count,
        )

    except NotificationServiceError as e:
        logger.error(
            "notifications_request_failed",
            user_id=user.id,
            error=e.message,
            code=e.code,
        )
        raise _handle_service_error(e) from e
    except Exception as e:
        logger.error(
            "notifications_request_unexpected_error",
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


# =============================================================================
# Task 4.3: PATCH /api/notifications/{id}/read (AC #3)
# =============================================================================


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    response_model_by_alias=True,
    summary="Mark Notification as Read",
    description="""
    Mark a single notification as read.

    Used when user views/dismisses a notification.
    Only the notification owner can mark their notifications as read.
    """,
    responses={
        200: {
            "description": "Notification marked as read",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": "uuid",
                            "type": "success",
                            "title": "Processing Complete",
                            "message": "Document 'Contract.pdf' has been processed.",
                            "matterId": "uuid",
                            "matterTitle": "Shah v. Mehta",
                            "isRead": True,
                            "createdAt": "2026-01-16T10:00:00Z",
                            "priority": "medium",
                        }
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Notification not found or belongs to another user",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Notification not found",
                            "details": {},
                        }
                    }
                }
            },
        },
    },
)
async def mark_notification_read(
    notification_id: str = Path(..., description="Notification ID to mark as read"),
    user: AuthenticatedUser = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationResponse:
    """Mark a notification as read.

    Story 14.10: AC #3 - PATCH /api/notifications/{id}/read endpoint.

    Args:
        notification_id: Notification UUID to mark as read.
        user: Authenticated user (from JWT).
        notification_service: Notification service instance.

    Returns:
        NotificationResponse with updated notification.

    Raises:
        HTTPException: On authentication errors or notification not found.
    """
    try:
        logger.info(
            "mark_notification_read_request",
            user_id=user.id,
            notification_id=notification_id,
        )

        notification = await notification_service.mark_as_read(
            notification_id=notification_id,
            user_id=user.id,
        )

        if not notification:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Notification not found",
                        "details": {},
                    }
                },
            )

        return NotificationResponse(data=notification)

    except HTTPException:
        raise
    except NotificationServiceError as e:
        logger.error(
            "mark_notification_read_failed",
            user_id=user.id,
            notification_id=notification_id,
            error=e.message,
            code=e.code,
        )
        raise _handle_service_error(e) from e
    except Exception as e:
        logger.error(
            "mark_notification_read_unexpected_error",
            user_id=user.id,
            notification_id=notification_id,
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


# =============================================================================
# Task 4.4: POST /api/notifications/read-all (AC #4)
# =============================================================================


@router.post(
    "/read-all",
    response_model=MarkAllReadResponse,
    summary="Mark All Notifications as Read",
    description="""
    Mark all unread notifications as read for the authenticated user.

    Used when user clicks "Mark all as read" button.
    Returns count of notifications that were marked as read.
    """,
    responses={
        200: {
            "description": "All notifications marked as read",
            "content": {
                "application/json": {
                    "example": {
                        "count": 5,
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
        },
    },
)
async def mark_all_notifications_read(
    user: AuthenticatedUser = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> MarkAllReadResponse:
    """Mark all notifications as read.

    Story 14.10: AC #4 - POST /api/notifications/read-all endpoint.

    Args:
        user: Authenticated user (from JWT).
        notification_service: Notification service instance.

    Returns:
        MarkAllReadResponse with count of notifications marked as read.

    Raises:
        HTTPException: On authentication errors.
    """
    try:
        logger.info(
            "mark_all_notifications_read_request",
            user_id=user.id,
        )

        count = await notification_service.mark_all_as_read(user_id=user.id)

        return MarkAllReadResponse(count=count)

    except NotificationServiceError as e:
        logger.error(
            "mark_all_notifications_read_failed",
            user_id=user.id,
            error=e.message,
            code=e.code,
        )
        raise _handle_service_error(e) from e
    except Exception as e:
        logger.error(
            "mark_all_notifications_read_unexpected_error",
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
