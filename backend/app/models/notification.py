"""Notification models for Notifications API.

Story 14.10: Notifications Backend & Frontend Wiring

Pydantic models for notification CRUD endpoints.
Notifications are per-user (not per-matter) to allow cross-matter notifications.

CRITICAL: Must match frontend TypeScript interface in types/notification.ts.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Story 14.10: Task 2.2 - Notification Type Enum (AC #2)
# =============================================================================


class NotificationTypeEnum(str, Enum):
    """Notification type enum matching frontend NotificationType.

    Story 14.10: AC #2 - Types for icon/color coding.
    """

    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    IN_PROGRESS = "in_progress"


# =============================================================================
# Story 14.10: Task 2.3 - Notification Priority Enum (AC #2)
# =============================================================================


class NotificationPriorityEnum(str, Enum):
    """Notification priority enum matching frontend NotificationPriority.

    Story 14.10: AC #2 - Priority levels for sorting and display.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# Story 14.10: Task 2.4 - Notification Record Model (AC #2)
# =============================================================================


class NotificationRecord(BaseModel):
    """Notification record from database.

    Story 14.10: AC #2 - Notification structure for API response.
    Uses camelCase aliases to match frontend Notification interface exactly.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        ...,
        description="Notification UUID",
    )
    type: NotificationTypeEnum = Field(
        ...,
        description="Notification type: success, info, warning, error, in_progress",
    )
    title: str = Field(
        ...,
        description="Short notification title",
    )
    message: str = Field(
        ...,
        description="Detailed notification message",
    )
    matter_id: str | None = Field(
        None,
        alias="matterId",
        description="Matter ID (nullable)",
    )
    matter_title: str | None = Field(
        None,
        alias="matterTitle",
        description="Matter title (joined from matters table)",
    )
    is_read: bool = Field(
        ...,
        alias="isRead",
        description="Whether user has read this notification",
    )
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="Notification timestamp",
    )
    priority: NotificationPriorityEnum = Field(
        ...,
        description="Priority level: high, medium, low",
    )


# =============================================================================
# Story 14.10: Task 2.5 - Notification List Response Model (AC #2)
# =============================================================================


class NotificationListResponse(BaseModel):
    """API response for notification list.

    Story 14.10: AC #2 - Notification list response with unread count.
    """

    model_config = ConfigDict(populate_by_name=True)

    data: list[NotificationRecord] = Field(
        ...,
        description="List of notifications",
    )
    unread_count: int = Field(
        ...,
        alias="unreadCount",
        ge=0,
        description="Count of unread notifications for badge display",
    )


# =============================================================================
# Story 14.10: Task 3.6 - Notification Create Model
# =============================================================================


class NotificationCreate(BaseModel):
    """Internal model for creating notifications.

    Story 14.10: Task 3.6 - Used by service layer to create notifications.
    """

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(
        ...,
        description="User ID who will receive this notification",
    )
    matter_id: str | None = Field(
        None,
        description="Optional matter ID (NULL for non-matter notifications)",
    )
    type: NotificationTypeEnum = Field(
        ...,
        description="Notification type",
    )
    title: str = Field(
        ...,
        max_length=200,
        description="Short notification title",
    )
    message: str = Field(
        ...,
        max_length=500,
        description="Detailed notification message",
    )
    priority: NotificationPriorityEnum = Field(
        default=NotificationPriorityEnum.MEDIUM,
        description="Priority level",
    )


# =============================================================================
# Story 14.10: Single Notification Response
# =============================================================================


class NotificationResponse(BaseModel):
    """API response for single notification.

    Story 14.10: AC #3 - Response for mark as read.
    """

    data: NotificationRecord


# =============================================================================
# Story 14.10: Mark All As Read Response
# =============================================================================


class MarkAllReadResponse(BaseModel):
    """API response for mark all as read.

    Story 14.10: AC #4 - Returns count of notifications marked as read.
    """

    count: int = Field(
        ...,
        ge=0,
        description="Number of notifications marked as read",
    )


# =============================================================================
# Story 14.10: Error Response Models
# =============================================================================


class NotificationErrorDetail(BaseModel):
    """Error detail structure for notification API.

    Follows project API error pattern from project-context.md.
    """

    code: str = Field(
        ...,
        description="Machine-readable error code",
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
    details: dict = Field(
        default_factory=dict,
        description="Additional error context",
    )


class NotificationErrorResponse(BaseModel):
    """Error response structure for notification API.

    Follows project API error pattern from project-context.md.
    """

    error: NotificationErrorDetail
