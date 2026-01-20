"""Notification Service for managing user notifications.

Story 14.10: Notifications Backend & Frontend Wiring

Provides CRUD operations for notifications.
Notifications are per-user (not per-matter) - users see notifications from all their matters.

CRITICAL: All operations respect user isolation via RLS policies.
"""

import asyncio
from functools import lru_cache

import structlog

from app.models.notification import (
    NotificationPriorityEnum,
    NotificationRecord,
    NotificationTypeEnum,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 14.10: Exceptions
# =============================================================================


class NotificationServiceError(Exception):
    """Base exception for notification service."""

    def __init__(
        self,
        message: str,
        code: str = "NOTIFICATION_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotificationNotFoundError(NotificationServiceError):
    """Raised when a notification is not found."""

    def __init__(self, message: str = "Notification not found"):
        super().__init__(message, code="NOT_FOUND", status_code=404)


# =============================================================================
# Story 14.10: Notification Service (Task 3.1 - 3.6)
# =============================================================================


class NotificationService:
    """Service for managing user notifications.

    Story 14.10: Implements AC #2, #3, #4, #6 for notification operations.

    Features:
    - Get notifications for a user with filtering options
    - Mark notifications as read
    - Mark all notifications as read
    - Create notifications when key events occur

    Example:
        >>> service = NotificationService()
        >>> notifications, unread_count = await service.get_notifications(
        ...     user_id="user-uuid",
        ...     limit=20,
        ...     unread_only=False
        ... )
    """

    def __init__(self) -> None:
        """Initialize notification service."""
        self._supabase_client = None

    @property
    def supabase(self):
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            NotificationServiceError: If Supabase is not configured.
        """
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
            if self._supabase_client is None:
                raise NotificationServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                    status_code=503,
                )
        return self._supabase_client

    # =========================================================================
    # Task 3.2: Get Notifications (AC #2)
    # =========================================================================

    async def get_notifications(
        self,
        user_id: str,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[NotificationRecord], int]:
        """Get notifications for a user.

        Story 14.10: AC #2 - Query notifications with filtering.

        Args:
            user_id: User ID to get notifications for.
            limit: Maximum notifications to return (default 20, max 50).
            unread_only: If True, only return unread notifications.

        Returns:
            Tuple of (notifications list, unread count).
        """
        try:
            # Clamp limit to valid range
            limit = min(max(1, limit), 50)

            # Build query with matter join for matter_title
            # DEBUG: Log the query attempt
            logger.info(
                "notifications_query_starting",
                user_id=user_id,
                limit=limit,
                unread_only=unread_only,
            )

            query = (
                self.supabase.table("notifications")
                .select("*, matters!left(title)")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
            )

            if unread_only:
                query = query.eq("is_read", False)

            result = await asyncio.to_thread(lambda: query.execute())

            # Get unread count for badge display (always regardless of filter)
            unread_count = await self.get_unread_count(user_id)

            notifications = []
            for row in result.data or []:
                # Extract matter title from joined data
                matter_title = None
                if row.get("matters") and row["matters"].get("title"):
                    matter_title = row["matters"]["title"]

                notifications.append(
                    NotificationRecord(
                        id=str(row["id"]),
                        type=NotificationTypeEnum(row["type"]),
                        title=row["title"],
                        message=row["message"],
                        matter_id=row.get("matter_id"),
                        matter_title=matter_title,
                        is_read=row["is_read"],
                        created_at=row["created_at"],
                        priority=NotificationPriorityEnum(row["priority"]),
                    )
                )

            logger.debug(
                "notifications_queried",
                user_id=user_id,
                limit=limit,
                unread_only=unread_only,
                count=len(notifications),
                unread_count=unread_count,
            )

            return notifications, unread_count

        except Exception as e:
            logger.error(
                "get_notifications_failed",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,  # Include full traceback
            )
            # Re-raise to let API return proper error - don't swallow silently
            raise NotificationServiceError(
                f"Failed to get notifications: {e}",
                code="QUERY_FAILED",
                status_code=500,
            )

    # =========================================================================
    # Task 3.3: Get Unread Count (AC #2)
    # =========================================================================

    async def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications for a user.

        Story 14.10: AC #2 - For badge display.

        Args:
            user_id: User ID.

        Returns:
            Count of unread notifications.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("notifications")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("is_read", False)
                .execute()
            )

            return result.count or 0

        except Exception as e:
            logger.error(
                "get_unread_count_failed",
                user_id=user_id,
                error=str(e),
            )
            return 0

    # =========================================================================
    # Task 3.4: Mark as Read (AC #3)
    # =========================================================================

    async def mark_as_read(
        self,
        notification_id: str,
        user_id: str,
    ) -> NotificationRecord | None:
        """Mark a notification as read.

        Story 14.10: AC #3 - Update is_read to true.

        Args:
            notification_id: Notification UUID to mark as read.
            user_id: User ID (for ownership verification via RLS).

        Returns:
            Updated NotificationRecord if found, None if not found or unauthorized.
        """
        try:
            # Update notification and verify ownership via RLS
            result = await asyncio.to_thread(
                lambda: self.supabase.table("notifications")
                .update({"is_read": True})
                .eq("id", notification_id)
                .eq("user_id", user_id)  # Verify ownership
                .select("*, matters!left(title)")
                .execute()
            )

            if not result.data:
                logger.debug(
                    "notification_not_found_for_mark_read",
                    notification_id=notification_id,
                    user_id=user_id,
                )
                return None

            row = result.data[0]

            # Extract matter title from joined data
            matter_title = None
            if row.get("matters") and row["matters"].get("title"):
                matter_title = row["matters"]["title"]

            logger.info(
                "notification_marked_read",
                notification_id=notification_id,
                user_id=user_id,
            )

            return NotificationRecord(
                id=str(row["id"]),
                type=NotificationTypeEnum(row["type"]),
                title=row["title"],
                message=row["message"],
                matter_id=row.get("matter_id"),
                matter_title=matter_title,
                is_read=row["is_read"],
                created_at=row["created_at"],
                priority=NotificationPriorityEnum(row["priority"]),
            )

        except Exception as e:
            logger.error(
                "mark_as_read_failed",
                notification_id=notification_id,
                user_id=user_id,
                error=str(e),
            )
            return None

    # =========================================================================
    # Task 3.5: Mark All as Read (AC #4)
    # =========================================================================

    async def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user.

        Story 14.10: AC #4 - Update all is_read to true.

        Args:
            user_id: User ID.

        Returns:
            Count of notifications marked as read.
        """
        try:
            # First count unread notifications to return count
            count_result = await asyncio.to_thread(
                lambda: self.supabase.table("notifications")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("is_read", False)
                .execute()
            )

            unread_count = count_result.count or 0

            if unread_count == 0:
                logger.debug("no_unread_notifications", user_id=user_id)
                return 0

            # Update all unread notifications
            await asyncio.to_thread(
                lambda: self.supabase.table("notifications")
                .update({"is_read": True})
                .eq("user_id", user_id)
                .eq("is_read", False)
                .execute()
            )

            logger.info(
                "all_notifications_marked_read",
                user_id=user_id,
                count=unread_count,
            )

            return unread_count

        except Exception as e:
            logger.error(
                "mark_all_as_read_failed",
                user_id=user_id,
                error=str(e),
            )
            return 0

    # =========================================================================
    # Task 3.6: Create Notification (AC #6)
    # =========================================================================

    async def create_notification(
        self,
        user_id: str,
        type: NotificationTypeEnum,
        title: str,
        message: str,
        matter_id: str | None = None,
        priority: NotificationPriorityEnum = NotificationPriorityEnum.MEDIUM,
    ) -> NotificationRecord | None:
        """Create a new notification for a user.

        Story 14.10: AC #6 - Create notification when key events occur.

        Args:
            user_id: User ID who will receive this notification.
            type: Notification type enum.
            title: Short notification title.
            message: Detailed notification message.
            matter_id: Optional matter ID for matter-specific notifications.
            priority: Priority level (default: medium).

        Returns:
            NotificationRecord with created notification, None on error.
        """
        try:
            data = {
                "user_id": user_id,
                "matter_id": matter_id,
                "type": type.value,
                "title": title,
                "message": message,
                "priority": priority.value,
            }

            result = await asyncio.to_thread(
                lambda: self.supabase.table("notifications").insert(data).execute()
            )

            if not result.data:
                logger.error(
                    "notification_insert_failed",
                    user_id=user_id,
                    type=type.value,
                )
                return None

            row = result.data[0]

            logger.info(
                "notification_created",
                user_id=user_id,
                matter_id=matter_id,
                type=type.value,
                notification_id=row["id"],
            )

            return NotificationRecord(
                id=str(row["id"]),
                type=NotificationTypeEnum(row["type"]),
                title=row["title"],
                message=row["message"],
                matter_id=row.get("matter_id"),
                matter_title=None,  # Not joined on insert
                is_read=row["is_read"],
                created_at=row["created_at"],
                priority=NotificationPriorityEnum(row["priority"]),
            )

        except Exception as e:
            logger.error(
                "create_notification_failed",
                user_id=user_id,
                type=type.value,
                error=str(e),
            )
            return None

    # =========================================================================
    # Create Notifications for Matter Members
    # =========================================================================

    async def create_notification_for_matter_members(
        self,
        matter_id: str,
        type: NotificationTypeEnum,
        title: str,
        message: str,
        priority: NotificationPriorityEnum = NotificationPriorityEnum.MEDIUM,
    ) -> int:
        """Create notifications for all members of a matter.

        Story 14.10: AC #6 - Create notifications when key events occur.
        Since background jobs don't have user context, this creates
        notifications for all matter members.

        Args:
            matter_id: Matter ID to get members from.
            type: Notification type enum.
            title: Short notification title.
            message: Detailed notification message.
            priority: Priority level.

        Returns:
            Number of notifications created.
        """
        try:
            # Get all members of the matter
            result = await asyncio.to_thread(
                lambda: self.supabase.table("matter_attorneys")
                .select("user_id")
                .eq("matter_id", matter_id)
                .execute()
            )

            if not result.data:
                logger.warning(
                    "no_matter_members_for_notification",
                    matter_id=matter_id,
                    type=type.value,
                )
                return 0

            user_ids = [row["user_id"] for row in result.data]

            # Create notifications for all members
            notifications_data = [
                {
                    "user_id": user_id,
                    "matter_id": matter_id,
                    "type": type.value,
                    "title": title,
                    "message": message,
                    "priority": priority.value,
                }
                for user_id in user_ids
            ]

            insert_result = await asyncio.to_thread(
                lambda: self.supabase.table("notifications")
                .insert(notifications_data)
                .execute()
            )

            created_count = len(insert_result.data) if insert_result.data else 0

            logger.info(
                "notifications_created_for_matter_members",
                matter_id=matter_id,
                type=type.value,
                member_count=len(user_ids),
                created_count=created_count,
            )

            return created_count

        except Exception as e:
            logger.error(
                "create_notification_for_matter_members_failed",
                matter_id=matter_id,
                type=type.value,
                error=str(e),
            )
            return 0


# =============================================================================
# Story 14.10: Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_notification_service() -> NotificationService:
    """Get singleton notification service instance.

    Returns:
        NotificationService instance.
    """
    return NotificationService()
