"""Activity models for Dashboard Activity Feed API.

Story 14.5: Dashboard Real APIs

Pydantic models for activity feed and dashboard statistics endpoints.
Activities are per-user (not per-matter) to show all activity across matters.

CRITICAL: Must match frontend TypeScript interface in types/activity.ts.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Story 14.5: Task 2.1 - Activity Type Enum (AC #6)
# =============================================================================


class ActivityTypeEnum(str, Enum):
    """Activity type enum matching frontend types.

    Story 14.5: AC #6 - Activity types for icon/color coding.
    """

    PROCESSING_COMPLETE = "processing_complete"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_FAILED = "processing_failed"
    CONTRADICTIONS_FOUND = "contradictions_found"
    VERIFICATION_NEEDED = "verification_needed"
    MATTER_OPENED = "matter_opened"


# =============================================================================
# Story 14.5: Task 2.1 - Activity Models (AC #1)
# =============================================================================


class ActivityCreate(BaseModel):
    """Internal model for creating activities.

    Story 14.5: Task 3.2 - Used by service layer to create activities.
    """

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(
        ...,
        description="User ID who owns this activity",
    )
    matter_id: str | None = Field(
        None,
        description="Optional matter ID (NULL for non-matter activities)",
    )
    type: ActivityTypeEnum = Field(
        ...,
        description="Activity type",
    )
    description: str = Field(
        ...,
        max_length=500,
        description="Human-readable description (no PII)",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Extra context (doc count, contradiction count, etc.)",
    )


class ActivityRecord(BaseModel):
    """Activity record from database.

    Story 14.5: AC #1 - Activity structure for API response.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        ...,
        description="Activity UUID",
    )
    matter_id: str | None = Field(
        None,
        alias="matterId",
        description="Matter ID (nullable)",
    )
    matter_name: str | None = Field(
        None,
        alias="matterName",
        description="Matter title (joined from matters table)",
    )
    type: ActivityTypeEnum = Field(
        ...,
        description="Activity type for icon/color coding",
    )
    description: str = Field(
        ...,
        description="Human-readable description",
    )
    timestamp: datetime = Field(
        ...,
        description="Activity timestamp (created_at aliased)",
    )
    is_read: bool = Field(
        ...,
        alias="isRead",
        description="Whether user has read/dismissed this activity",
    )


class ActivityResponse(BaseModel):
    """API response for single activity.

    Story 14.5: AC #7 - Single activity response wrapper.
    """

    data: ActivityRecord


# =============================================================================
# Story 14.5: Task 2.1 - Activity List Models (AC #1)
# =============================================================================


class ActivityListMeta(BaseModel):
    """Metadata for activity list response.

    Story 14.5: AC #1 - Pagination/total metadata.
    """

    total: int = Field(
        ...,
        ge=0,
        description="Total activities count (before limit)",
    )


class ActivityListResponse(BaseModel):
    """API response for activity list.

    Story 14.5: AC #1 - Activity feed response wrapper.
    """

    data: list[ActivityRecord] = Field(
        ...,
        description="List of activities",
    )
    meta: ActivityListMeta = Field(
        ...,
        description="Response metadata with total count",
    )


# =============================================================================
# Story 14.5: Task 2.1 - Dashboard Stats Models (AC #2)
# =============================================================================


class DashboardStats(BaseModel):
    """Dashboard statistics for authenticated user.

    Story 14.5: AC #2 - Aggregated stats across all user's matters.
    """

    model_config = ConfigDict(populate_by_name=True)

    active_matters: int = Field(
        ...,
        alias="activeMatters",
        ge=0,
        description="Count of non-archived matters",
    )
    verified_findings: int = Field(
        ...,
        alias="verifiedFindings",
        ge=0,
        description="Count of verified findings across matters",
    )
    pending_reviews: int = Field(
        ...,
        alias="pendingReviews",
        ge=0,
        description="Count of findings awaiting verification",
    )


class DashboardStatsResponse(BaseModel):
    """API response for dashboard stats.

    Story 14.5: AC #2 - Dashboard stats response wrapper.
    """

    data: DashboardStats


# =============================================================================
# Story 14.5: Error Response Models
# =============================================================================


class ActivityErrorDetail(BaseModel):
    """Error detail structure for activity API.

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


class ActivityErrorResponse(BaseModel):
    """Error response structure for activity API.

    Follows project API error pattern from project-context.md.
    """

    error: ActivityErrorDetail
