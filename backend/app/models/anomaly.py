"""Anomaly models for Timeline Anomaly Detection.

Pydantic models for anomaly detection, storage, and API responses.
Supports the Timeline Construction Engine for flagging unusual
patterns in legal timelines.

Story 4-4: Timeline Anomaly Detection
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# =============================================================================
# Anomaly Type and Severity Enums
# =============================================================================


class AnomalyType(str, Enum):
    """Types of timeline anomalies that can be detected."""

    GAP = "gap"  # Unusual time gap between related events
    SEQUENCE_VIOLATION = "sequence_violation"  # Events out of expected legal order
    DUPLICATE = "duplicate"  # Potential duplicate events
    OUTLIER = "outlier"  # Statistically anomalous dates


class AnomalySeverity(str, Enum):
    """Severity levels for detected anomalies."""

    LOW = "low"  # Minor issue, informational
    MEDIUM = "medium"  # Should be reviewed
    HIGH = "high"  # Likely needs attention
    CRITICAL = "critical"  # Urgent attention required


# =============================================================================
# Base and Create Models
# =============================================================================


class AnomalyBase(BaseModel):
    """Base model with common anomaly fields."""

    anomaly_type: AnomalyType = Field(..., description="Type of anomaly detected")
    severity: AnomalySeverity = Field(..., description="Severity level")
    title: str = Field(..., description="Short description for UI display")
    explanation: str = Field(
        ..., description="Detailed explanation with suggested causes"
    )
    event_ids: list[str] = Field(..., description="UUIDs of involved events")
    expected_order: list[str] | None = Field(
        None, description="Expected event type order (for sequence violations)"
    )
    actual_order: list[str] | None = Field(
        None, description="Actual event type order (for sequence violations)"
    )
    gap_days: int | None = Field(
        None, description="Number of days in gap (for gap anomalies)"
    )
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Detection confidence"
    )


class AnomalyCreate(AnomalyBase):
    """Model for creating a new anomaly."""

    matter_id: str = Field(..., description="Matter UUID")


class Anomaly(AnomalyBase):
    """Full anomaly model from database."""

    id: str = Field(..., description="Anomaly UUID")
    matter_id: str = Field(..., description="Matter UUID")
    verified: bool = Field(
        default=False, description="Whether attorney confirmed this is a real issue"
    )
    dismissed: bool = Field(
        default=False, description="Whether attorney dismissed as not an issue"
    )
    verified_by: str | None = Field(None, description="User who verified/dismissed")
    verified_at: datetime | None = Field(
        None, description="Timestamp of verification/dismissal"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# =============================================================================
# List and Response Models
# =============================================================================


class AnomalyListItem(BaseModel):
    """Anomaly item for list responses."""

    id: str = Field(..., description="Anomaly UUID")
    anomaly_type: str = Field(..., description="Type of anomaly")
    severity: str = Field(..., description="Severity level")
    title: str = Field(..., description="Short description")
    explanation: str = Field(..., description="Detailed explanation")
    event_ids: list[str] = Field(..., description="Involved event UUIDs")
    gap_days: int | None = Field(None, description="Gap days (if applicable)")
    confidence: float = Field(..., description="Detection confidence")
    verified: bool = Field(default=False, description="Attorney verified")
    dismissed: bool = Field(default=False, description="Attorney dismissed")
    created_at: datetime = Field(..., description="Creation timestamp")


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class AnomaliesListResponse(BaseModel):
    """API response for anomalies list endpoint.

    GET /api/matters/{matter_id}/anomalies
    """

    data: list[AnomalyListItem]
    meta: PaginationMeta


class AnomalyDetailResponse(BaseModel):
    """API response for single anomaly retrieval.

    GET /api/matters/{matter_id}/anomalies/{anomaly_id}
    """

    data: Anomaly


# =============================================================================
# Summary and Update Models
# =============================================================================


class AnomalySummaryData(BaseModel):
    """Summary counts for attention banner display."""

    total: int = Field(..., description="Total number of anomalies")
    by_severity: dict[str, int] = Field(
        default_factory=dict, description="Count by severity level"
    )
    by_type: dict[str, int] = Field(
        default_factory=dict, description="Count by anomaly type"
    )
    unreviewed: int = Field(
        ..., description="Anomalies not yet verified or dismissed"
    )
    verified: int = Field(..., description="Anomalies verified as real issues")
    dismissed: int = Field(..., description="Anomalies dismissed as not issues")


class AnomalySummaryResponse(BaseModel):
    """API response for anomaly summary endpoint.

    GET /api/matters/{matter_id}/anomalies/summary
    """

    data: AnomalySummaryData


class AnomalyUpdateRequest(BaseModel):
    """Request body for updating anomaly status (dismiss/verify)."""

    # No fields needed - action is determined by endpoint path
    pass


class AnomalyUpdateResponse(BaseModel):
    """Response for anomaly update operations."""

    data: Anomaly


# =============================================================================
# Detection Job Models
# =============================================================================


class AnomalyDetectionJobData(BaseModel):
    """Job data for anomaly detection."""

    job_id: str = Field(..., description="Job UUID for progress tracking")
    status: str = Field(default="queued", description="Job status")
    events_to_analyze: int = Field(..., description="Number of events to analyze")


class AnomalyDetectionJobResponse(BaseModel):
    """API response for anomaly detection job trigger.

    POST /api/matters/{matter_id}/anomalies/detect
    """

    data: AnomalyDetectionJobData


# =============================================================================
# Error Models
# =============================================================================


class AnomalyErrorDetail(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict = Field(default_factory=dict, description="Additional error context")


class AnomalyErrorResponse(BaseModel):
    """Error response structure."""

    error: AnomalyErrorDetail


# Forward reference resolution
AnomaliesListResponse.model_rebuild()
AnomalySummaryResponse.model_rebuild()
AnomalyDetectionJobResponse.model_rebuild()
