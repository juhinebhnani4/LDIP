"""Activity Service for managing user activity feed.

Story 14.5: Dashboard Real APIs (Task 3)

Provides CRUD operations for activities.
Activities are per-user (not per-matter) - users see activities from all their matters.

CRITICAL: All operations respect user isolation via RLS policies.
"""

import asyncio
from functools import lru_cache

import structlog

from app.models.activity import ActivityCreate, ActivityRecord, ActivityTypeEnum
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 14.5: Exceptions
# =============================================================================


class ActivityServiceError(Exception):
    """Base exception for activity service."""

    def __init__(
        self,
        message: str,
        code: str = "ACTIVITY_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ActivityNotFoundError(ActivityServiceError):
    """Raised when an activity is not found."""

    def __init__(self, message: str = "Activity not found"):
        super().__init__(message, code="ACTIVITY_NOT_FOUND", status_code=404)


# =============================================================================
# Story 14.5: Activity Service (Task 3.1 - 3.5)
# =============================================================================


class ActivityService:
    """Service for managing user activities.

    Story 14.5: Implements AC #1, #5, #6, #7 for activity operations.

    Features:
    - Create activities when key events occur
    - Get activities for a user with optional matter filter
    - Mark activities as read
    - Get unread count for badge display

    Example:
        >>> service = ActivityService()
        >>> activity = await service.create_activity(
        ...     user_id="user-uuid",
        ...     matter_id="matter-uuid",
        ...     type=ActivityTypeEnum.PROCESSING_COMPLETE,
        ...     description="Document processing complete",
        ...     metadata={"doc_count": 5}
        ... )
    """

    def __init__(self) -> None:
        """Initialize activity service."""
        self._supabase_client = None

    @property
    def supabase(self):
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            ActivityServiceError: If Supabase is not configured.
        """
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
            if self._supabase_client is None:
                raise ActivityServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                    status_code=503,
                )
        return self._supabase_client

    # =========================================================================
    # Task 3.2: Create Activity
    # =========================================================================

    async def create_activity(
        self,
        user_id: str,
        type: ActivityTypeEnum,
        description: str,
        matter_id: str | None = None,
        metadata: dict | None = None,
    ) -> ActivityRecord:
        """Create a new activity for a user.

        Story 14.5: AC #6 - Create activity when key events occur.

        Args:
            user_id: User ID who owns this activity.
            type: Activity type enum.
            description: Human-readable description (no PII).
            matter_id: Optional matter ID for matter-specific activities.
            metadata: Optional extra context (doc count, contradiction count, etc.).

        Returns:
            ActivityRecord with created activity.

        Raises:
            ActivityServiceError: If operation fails.
        """
        try:
            data = {
                "user_id": user_id,
                "matter_id": matter_id,
                "type": type.value,
                "description": description,
                "metadata": metadata or {},
            }

            result = await asyncio.to_thread(
                lambda: self.supabase.table("activities").insert(data).execute()
            )

            if not result.data:
                raise ActivityServiceError(
                    "Failed to create activity",
                    code="INSERT_FAILED",
                    status_code=500,
                )

            row = result.data[0]

            logger.info(
                "activity_created",
                user_id=user_id,
                matter_id=matter_id,
                type=type.value,
                activity_id=row["id"],
            )

            return ActivityRecord(
                id=str(row["id"]),
                matter_id=row.get("matter_id"),
                matter_name=None,  # Not joined on insert
                type=ActivityTypeEnum(row["type"]),
                description=row["description"],
                timestamp=row["created_at"],
                is_read=row["is_read"],
            )

        except ActivityServiceError:
            raise
        except Exception as e:
            logger.error(
                "create_activity_failed",
                user_id=user_id,
                type=type.value,
                error=str(e),
            )
            raise ActivityServiceError(
                f"Failed to create activity: {e}",
                code="CREATE_FAILED",
                status_code=500,
            ) from e

    # =========================================================================
    # Task 3.3: Get Activities
    # =========================================================================

    async def get_activities(
        self,
        user_id: str,
        limit: int = 10,
        matter_id: str | None = None,
    ) -> tuple[list[ActivityRecord], int]:
        """Get activities for a user.

        Story 14.5: AC #1 - Query activities with filtering.

        Args:
            user_id: User ID to get activities for.
            limit: Maximum activities to return (default 10, max 50).
            matter_id: Optional filter by matter.

        Returns:
            Tuple of (activities list, total count).
        """
        try:
            # Clamp limit to valid range
            limit = min(max(1, limit), 50)

            # Build query with matter join for matter_name
            # Query activities with left join to matters to get matter_name
            query = (
                self.supabase.table("activities")
                .select("*, matters!left(title)")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
            )

            if matter_id:
                query = query.eq("matter_id", matter_id)

            result = await asyncio.to_thread(lambda: query.execute())

            # Get total count in a separate query
            count_query = (
                self.supabase.table("activities")
                .select("id", count="exact")
                .eq("user_id", user_id)
            )
            if matter_id:
                count_query = count_query.eq("matter_id", matter_id)

            count_result = await asyncio.to_thread(lambda: count_query.execute())
            total = count_result.count or 0

            activities = []
            for row in result.data or []:
                # Extract matter name from joined data
                matter_name = None
                if row.get("matters") and row["matters"].get("title"):
                    matter_name = row["matters"]["title"]

                activities.append(
                    ActivityRecord(
                        id=str(row["id"]),
                        matter_id=row.get("matter_id"),
                        matter_name=matter_name,
                        type=ActivityTypeEnum(row["type"]),
                        description=row["description"],
                        timestamp=row["created_at"],
                        is_read=row["is_read"],
                    )
                )

            logger.debug(
                "activities_queried",
                user_id=user_id,
                matter_id=matter_id,
                limit=limit,
                count=len(activities),
                total=total,
            )

            return activities, total

        except Exception as e:
            logger.error(
                "get_activities_failed",
                user_id=user_id,
                error=str(e),
            )
            # Return empty list on error to be graceful
            return [], 0

    # =========================================================================
    # Task 3.4: Mark as Read
    # =========================================================================

    async def mark_as_read(
        self,
        activity_id: str,
        user_id: str,
    ) -> ActivityRecord | None:
        """Mark an activity as read.

        Story 14.5: AC #7 - Update is_read to true.

        Args:
            activity_id: Activity UUID to mark as read.
            user_id: User ID (for ownership verification).

        Returns:
            Updated ActivityRecord if found, None if not found or unauthorized.

        Raises:
            ActivityNotFoundError: If activity not found or belongs to another user.
        """
        try:
            # Update activity and verify ownership via RLS
            result = await asyncio.to_thread(
                lambda: self.supabase.table("activities")
                .update({"is_read": True})
                .eq("id", activity_id)
                .eq("user_id", user_id)  # Verify ownership
                .select("*, matters!left(title)")
                .execute()
            )

            if not result.data:
                logger.debug(
                    "activity_not_found_for_mark_read",
                    activity_id=activity_id,
                    user_id=user_id,
                )
                return None

            row = result.data[0]

            # Extract matter name from joined data
            matter_name = None
            if row.get("matters") and row["matters"].get("title"):
                matter_name = row["matters"]["title"]

            logger.info(
                "activity_marked_read",
                activity_id=activity_id,
                user_id=user_id,
            )

            return ActivityRecord(
                id=str(row["id"]),
                matter_id=row.get("matter_id"),
                matter_name=matter_name,
                type=ActivityTypeEnum(row["type"]),
                description=row["description"],
                timestamp=row["created_at"],
                is_read=row["is_read"],
            )

        except Exception as e:
            logger.error(
                "mark_as_read_failed",
                activity_id=activity_id,
                user_id=user_id,
                error=str(e),
            )
            return None

    # =========================================================================
    # Task 3.5: Get Unread Count
    # =========================================================================

    async def get_unread_count(self, user_id: str) -> int:
        """Get count of unread activities for a user.

        Story 14.5: For notification badge display.

        Args:
            user_id: User ID.

        Returns:
            Count of unread activities.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("activities")
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
    # Task 6: Create Activities for Matter Members
    # =========================================================================

    async def create_activity_for_matter_members(
        self,
        matter_id: str,
        type: ActivityTypeEnum,
        description: str,
        metadata: dict | None = None,
    ) -> int:
        """Create activities for all members of a matter.

        Story 14.5: AC #6 - Create activity when key events occur.
        Since background jobs don't have user context, this creates
        activities for all matter members.

        Args:
            matter_id: Matter ID to get members from.
            type: Activity type enum.
            description: Human-readable description (no PII).
            metadata: Optional extra context.

        Returns:
            Number of activities created.
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
                    "no_matter_members_for_activity",
                    matter_id=matter_id,
                    type=type.value,
                )
                return 0

            user_ids = [row["user_id"] for row in result.data]

            # Create activities for all members
            activities_data = [
                {
                    "user_id": user_id,
                    "matter_id": matter_id,
                    "type": type.value,
                    "description": description,
                    "metadata": metadata or {},
                }
                for user_id in user_ids
            ]

            insert_result = await asyncio.to_thread(
                lambda: self.supabase.table("activities")
                .insert(activities_data)
                .execute()
            )

            created_count = len(insert_result.data) if insert_result.data else 0

            logger.info(
                "activities_created_for_matter_members",
                matter_id=matter_id,
                type=type.value,
                member_count=len(user_ids),
                created_count=created_count,
            )

            return created_count

        except Exception as e:
            logger.error(
                "create_activity_for_matter_members_failed",
                matter_id=matter_id,
                type=type.value,
                error=str(e),
            )
            return 0


# =============================================================================
# Story 14.5: Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_activity_service() -> ActivityService:
    """Get singleton activity service instance.

    Returns:
        ActivityService instance.
    """
    return ActivityService()
