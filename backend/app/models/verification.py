"""Verification models for attorney finding verification workflow.

Story 8-4: Implement Finding Verifications Table
Epic 8: Safety Layer (Guardrails, Policing, Verification)

These models define the structure for the attorney verification workflow:
- VerificationDecision: Attorney decision enum (pending, approved, rejected, flagged)
- VerificationRequirement: Tier enum based on confidence (optional, suggested, required)
- FindingVerificationCreate: Model for creating new verification records
- FindingVerificationUpdate: Model for updating verification decisions
- FindingVerification: Complete verification record from database
- VerificationQueueItem: Optimized model for queue UI display
- VerificationStats: Aggregate statistics for dashboard

Implements:
- FR10: Attorney Verification Workflow
- NFR23: Court-defensible verification workflow with forensic trail
- ADR-004: Verification Tier Thresholds (>90% optional, 70-90% suggested, <70% required)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Story 8-4: Verification Enums (Task 3.2, 3.3)
# =============================================================================


class VerificationDecision(str, Enum):
    """Attorney verification decision.

    Story 8-4: AC #2 - Decision options for finding verification.
    """

    PENDING = "pending"  # Awaiting attorney review
    APPROVED = "approved"  # Attorney verified finding is correct
    REJECTED = "rejected"  # Attorney marked finding as incorrect
    FLAGGED = "flagged"  # Attorney flagged for further review


class VerificationRequirement(str, Enum):
    """Verification requirement based on confidence.

    Story 8-4: AC #3-5 - Implements ADR-004 tiered verification.

    Thresholds:
    - OPTIONAL: Confidence > 90% (export allowed, verification informational)
    - SUGGESTED: Confidence 70-90% (export warning shown, verification suggested)
    - REQUIRED: Confidence < 70% (export blocked until verified)
    """

    OPTIONAL = "optional"  # Confidence > 90%
    SUGGESTED = "suggested"  # Confidence 70-90%
    REQUIRED = "required"  # Confidence < 70%


# =============================================================================
# Story 8-4: Verification Create/Update Models (Task 3.4, 3.5)
# =============================================================================


class FindingVerificationCreate(BaseModel):
    """Create verification record when finding is generated.

    Story 8-4: AC #1 - Created automatically when finding generated.
    Called by ResultAggregator after each finding is created.
    """

    model_config = ConfigDict(populate_by_name=True)

    matter_id: str = Field(..., alias="matterId", description="Matter UUID")
    finding_id: str = Field(..., alias="findingId", description="Finding UUID")
    finding_type: str = Field(
        ...,
        alias="findingType",
        description="Type: citation_mismatch, timeline_anomaly, contradiction, etc.",
    )
    finding_summary: str = Field(
        ...,
        max_length=500,
        alias="findingSummary",
        description="Brief description for queue display (truncated to 500 chars)",
    )
    confidence_before: float = Field(
        ...,
        ge=0,
        le=100,
        alias="confidenceBefore",
        description="Confidence at creation (0-100 scale)",
    )


class FindingVerificationUpdate(BaseModel):
    """Update verification with attorney decision.

    Story 8-4: AC #2 - Attorney approval/rejection.
    """

    model_config = ConfigDict(populate_by_name=True)

    decision: VerificationDecision = Field(..., description="Attorney decision")
    confidence_after: float | None = Field(
        None,
        ge=0,
        le=100,
        alias="confidenceAfter",
        description="Attorney-adjusted confidence (optional)",
    )
    notes: str | None = Field(
        None,
        max_length=2000,
        description="Attorney notes explaining decision",
    )


# =============================================================================
# Story 8-4: Complete Verification Model (Task 3.6)
# =============================================================================


class FindingVerification(BaseModel):
    """Complete verification record from database.

    Story 8-4: Full verification record with all fields.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Verification UUID")
    matter_id: str = Field(..., alias="matterId", description="Matter UUID")
    finding_id: str | None = Field(
        None,
        alias="findingId",
        description="Finding UUID (nullable if finding was deleted)",
    )
    finding_type: str = Field(..., alias="findingType", description="Finding type snapshot")
    finding_summary: str = Field(..., alias="findingSummary", description="Finding summary snapshot")
    confidence_before: float = Field(
        ...,
        ge=0,
        le=100,
        alias="confidenceBefore",
        description="Original confidence at finding creation",
    )
    decision: VerificationDecision = Field(..., description="Current verification decision")
    verified_by: str | None = Field(None, alias="verifiedBy", description="Verifier user UUID")
    verified_at: datetime | None = Field(None, alias="verifiedAt", description="Verification timestamp")
    confidence_after: float | None = Field(
        None,
        ge=0,
        le=100,
        alias="confidenceAfter",
        description="Attorney-adjusted confidence",
    )
    notes: str | None = Field(None, description="Attorney notes")
    created_at: datetime = Field(..., alias="createdAt", description="Record creation timestamp")
    updated_at: datetime = Field(..., alias="updatedAt", description="Last update timestamp")

    # Computed field - set by service based on confidence_before
    verification_requirement: VerificationRequirement = Field(
        ...,
        alias="verificationRequirement",
        description="OPTIONAL/SUGGESTED/REQUIRED based on confidence (ADR-004)",
    )


# =============================================================================
# Story 8-4: Queue and Stats Models (Task 3.7, 3.8)
# =============================================================================


class VerificationQueueItem(BaseModel):
    """Item in verification queue for UI.

    Story 8-4: Optimized for Story 8-5 queue display.
    Includes finding context for attorney prioritization.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Verification UUID")
    finding_id: str | None = Field(None, alias="findingId", description="Finding UUID")
    finding_type: str = Field(..., alias="findingType", description="Finding type for filtering")
    finding_summary: str = Field(..., alias="findingSummary", description="Summary for queue display")
    confidence: float = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence percentage",
    )
    requirement: VerificationRequirement = Field(
        ...,
        description="Verification requirement tier",
    )
    decision: VerificationDecision = Field(..., description="Current decision status")
    created_at: datetime = Field(..., alias="createdAt", description="When finding was created")

    # Context for queue prioritization
    source_document: str | None = Field(
        None,
        alias="sourceDocument",
        description="Primary source document name",
    )
    engine: str = Field(
        ...,
        description="Source engine (citation, timeline, contradiction)",
    )


class VerificationStats(BaseModel):
    """Verification statistics for dashboard.

    Story 8-4: Aggregate stats for matter verification status.
    Used by dashboard to show verification progress.
    """

    model_config = ConfigDict(populate_by_name=True)

    total_verifications: int = Field(0, ge=0, alias="totalVerifications", description="Total verification records")
    pending_count: int = Field(0, ge=0, alias="pendingCount", description="Awaiting review")
    approved_count: int = Field(0, ge=0, alias="approvedCount", description="Approved by attorney")
    rejected_count: int = Field(0, ge=0, alias="rejectedCount", description="Rejected by attorney")
    flagged_count: int = Field(0, ge=0, alias="flaggedCount", description="Flagged for further review")

    # By requirement tier (pending only)
    required_pending: int = Field(
        0,
        ge=0,
        alias="requiredPending",
        description="< 70% confidence, pending (blocks export)",
    )
    suggested_pending: int = Field(
        0,
        ge=0,
        alias="suggestedPending",
        description="70-90% confidence, pending",
    )
    optional_pending: int = Field(
        0,
        ge=0,
        alias="optionalPending",
        description="> 90% confidence, pending",
    )

    # Export eligibility
    export_blocked: bool = Field(
        False,
        alias="exportBlocked",
        description="True if has unverified findings < 70% confidence",
    )
    blocking_count: int = Field(
        0,
        ge=0,
        alias="blockingCount",
        description="Count of findings blocking export",
    )


# =============================================================================
# Story 8-4: API Response Models
# =============================================================================


class VerificationListResponse(BaseModel):
    """Response for verification list endpoint.

    Story 8-4: Follows project API response pattern with data wrapper.
    """

    data: list[FindingVerification] = Field(
        default_factory=list,
        description="List of verification records",
    )


class VerificationQueueResponse(BaseModel):
    """Response for verification queue endpoint.

    Story 8-4: Optimized for Story 8-5 queue UI.
    """

    data: list[VerificationQueueItem] = Field(
        default_factory=list,
        description="Pending verification items",
    )
    meta: dict = Field(
        default_factory=dict,
        description="Pagination and filter metadata",
    )


class VerificationStatsResponse(BaseModel):
    """Response for verification stats endpoint.

    Story 8-4: Dashboard statistics.
    """

    data: VerificationStats = Field(..., description="Verification statistics")


class VerificationResponse(BaseModel):
    """Response for single verification record.

    Story 8-4: Follows project API response pattern.
    """

    data: FindingVerification = Field(..., description="Verification record")


# =============================================================================
# Story 8-4: Action Request Models (Code Review Fix)
# =============================================================================


class ApproveVerificationRequest(BaseModel):
    """Request body for approving a verification.

    Story 8-4: Code Review Fix - Use request body instead of query params.
    """

    model_config = ConfigDict(populate_by_name=True)

    notes: str | None = Field(
        None,
        max_length=2000,
        description="Optional approval notes",
    )
    confidence_after: float | None = Field(
        None,
        ge=0,
        le=100,
        alias="confidenceAfter",
        description="Optional adjusted confidence score",
    )


class RejectVerificationRequest(BaseModel):
    """Request body for rejecting a verification.

    Story 8-4: Code Review Fix - Use request body instead of query params.
    """

    notes: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Required rejection notes",
    )


class FlagVerificationRequest(BaseModel):
    """Request body for flagging a verification.

    Story 8-4: Code Review Fix - Use request body instead of query params.
    """

    notes: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Required flagging notes",
    )


class BulkVerificationRequest(BaseModel):
    """Request for bulk verification operations.

    Story 8-4: Task 4.8 - Bulk approve/reject for Story 8-5 queue UI.
    """

    model_config = ConfigDict(populate_by_name=True)

    verification_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        alias="verificationIds",
        description="List of verification UUIDs to update (max 100)",
    )
    decision: VerificationDecision = Field(
        ...,
        description="Decision to apply to all",
    )
    notes: str | None = Field(
        None,
        max_length=2000,
        description="Optional notes for all verifications",
    )


class BulkVerificationResponse(BaseModel):
    """Response for bulk verification operations.

    Story 8-4: Task 4.8 - Results of bulk operation.
    """

    model_config = ConfigDict(populate_by_name=True)

    data: dict = Field(
        default_factory=dict,
        description="Bulk operation results",
    )
    updated_count: int = Field(0, ge=0, alias="updatedCount", description="Number of records updated")
    failed_ids: list[str] = Field(
        default_factory=list,
        alias="failedIds",
        description="IDs that failed to update",
    )


# =============================================================================
# Story 8-4: Export Eligibility Models (Task 8)
# =============================================================================


class ExportBlockingFinding(BaseModel):
    """Finding that blocks export.

    Story 8-4: AC #5 - Details of finding blocking export.
    """

    model_config = ConfigDict(populate_by_name=True)

    verification_id: str = Field(..., alias="verificationId", description="Verification UUID")
    finding_id: str | None = Field(None, alias="findingId", description="Finding UUID")
    finding_type: str = Field(..., alias="findingType", description="Finding type")
    finding_summary: str = Field(..., alias="findingSummary", description="Finding summary")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score")


class ExportWarningFinding(BaseModel):
    """Finding that shows warning but doesn't block export.

    Story 12-3: AC #2 - Findings with 70-90% confidence show warning.
    """

    model_config = ConfigDict(populate_by_name=True)

    verification_id: str = Field(..., alias="verificationId", description="Verification UUID")
    finding_id: str | None = Field(None, alias="findingId", description="Finding UUID")
    finding_type: str = Field(..., alias="findingType", description="Finding type")
    finding_summary: str = Field(..., alias="findingSummary", description="Finding summary")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score")


class ExportEligibilityResult(BaseModel):
    """Result of export eligibility check.

    Story 8-4: AC #5 - Export blocked if < 70% confidence findings unverified.
    Story 12-3: AC #2 - Warnings for 70-90% confidence unverified findings.
    Story 3.2: Includes verification_mode for UI display.
    """

    model_config = ConfigDict(populate_by_name=True)

    eligible: bool = Field(..., description="True if export is allowed")
    verification_mode: str = Field(
        default="advisory",
        alias="verificationMode",
        description="Matter's verification mode: 'advisory' or 'required' (Story 3.2)",
    )
    blocking_findings: list[ExportBlockingFinding] = Field(
        default_factory=list,
        alias="blockingFindings",
        description="Findings blocking export (< 70% confidence, unverified in advisory; all pending in required)",
    )
    blocking_count: int = Field(0, ge=0, alias="blockingCount", description="Number of blocking findings")
    warning_findings: list[ExportWarningFinding] = Field(
        default_factory=list,
        alias="warningFindings",
        description="Findings with warnings (70-90% confidence, unverified) - empty in required mode",
    )
    warning_count: int = Field(0, ge=0, alias="warningCount", description="Number of warning findings")
    message: str = Field(
        "",
        description="Human-readable eligibility message",
    )
