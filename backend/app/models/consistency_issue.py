"""Pydantic models for cross-engine consistency issues.

Story 5.4: Cross-Engine Consistency Checking

Models for tracking and displaying data inconsistencies
between different analysis engines (timeline, entity, citation, etc.).
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IssueType(str, Enum):
    """Types of consistency issues detected."""

    DATE_MISMATCH = "date_mismatch"
    ENTITY_NAME_MISMATCH = "entity_name_mismatch"
    AMOUNT_DISCREPANCY = "amount_discrepancy"
    CITATION_CONFLICT = "citation_conflict"
    TIMELINE_GAP = "timeline_gap"
    DUPLICATE_EVENT = "duplicate_event"


class IssueSeverity(str, Enum):
    """Severity levels for consistency issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IssueStatus(str, Enum):
    """Resolution status for consistency issues."""

    OPEN = "open"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class EngineType(str, Enum):
    """Analysis engine types."""

    TIMELINE = "timeline"
    ENTITY = "entity"
    CITATION = "citation"
    CONTRADICTION = "contradiction"
    RAG = "rag"


class ConsistencyIssue(BaseModel):
    """A cross-engine consistency issue.

    Story 5.4: Core model for consistency tracking.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Issue UUID")
    matter_id: str = Field(..., alias="matterId", description="Matter UUID")

    # Issue classification
    issue_type: IssueType = Field(..., alias="issueType", description="Type of issue")
    severity: IssueSeverity = Field(
        default=IssueSeverity.WARNING, description="Issue severity"
    )

    # Source reference
    source_engine: EngineType = Field(
        ..., alias="sourceEngine", description="Engine where original data was found"
    )
    source_id: str | None = Field(
        None, alias="sourceId", description="ID of the source record"
    )
    source_value: str | None = Field(
        None, alias="sourceValue", description="Value from source engine"
    )

    # Conflicting reference
    conflicting_engine: EngineType = Field(
        ..., alias="conflictingEngine", description="Engine with conflicting data"
    )
    conflicting_id: str | None = Field(
        None, alias="conflictingId", description="ID of conflicting record"
    )
    conflicting_value: str | None = Field(
        None, alias="conflictingValue", description="Conflicting value"
    )

    # Details
    description: str = Field(..., description="Human-readable description of the issue")
    document_id: str | None = Field(
        None, alias="documentId", description="Related document UUID"
    )
    document_name: str | None = Field(
        None, alias="documentName", description="Related document name"
    )

    # Resolution
    status: IssueStatus = Field(default=IssueStatus.OPEN, description="Resolution status")
    resolved_by: str | None = Field(
        None, alias="resolvedBy", description="User who resolved"
    )
    resolved_at: datetime | None = Field(
        None, alias="resolvedAt", description="When resolved"
    )
    resolution_notes: str | None = Field(
        None, alias="resolutionNotes", description="Resolution notes"
    )

    # Timestamps
    detected_at: datetime = Field(..., alias="detectedAt", description="When detected")
    created_at: datetime = Field(..., alias="createdAt", description="Created timestamp")
    updated_at: datetime = Field(..., alias="updatedAt", description="Updated timestamp")

    # Metadata
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class ConsistencyIssueCreate(BaseModel):
    """Request model for creating a consistency issue."""

    model_config = ConfigDict(populate_by_name=True)

    matter_id: str = Field(..., alias="matterId")
    issue_type: IssueType = Field(..., alias="issueType")
    severity: IssueSeverity = Field(default=IssueSeverity.WARNING)
    source_engine: EngineType = Field(..., alias="sourceEngine")
    source_id: str | None = Field(None, alias="sourceId")
    source_value: str | None = Field(None, alias="sourceValue")
    conflicting_engine: EngineType = Field(..., alias="conflictingEngine")
    conflicting_id: str | None = Field(None, alias="conflictingId")
    conflicting_value: str | None = Field(None, alias="conflictingValue")
    description: str
    document_id: str | None = Field(None, alias="documentId")
    document_name: str | None = Field(None, alias="documentName")
    metadata: dict = Field(default_factory=dict)


class ConsistencyIssueUpdate(BaseModel):
    """Request model for updating issue status."""

    model_config = ConfigDict(populate_by_name=True)

    status: IssueStatus | None = None
    resolution_notes: str | None = Field(None, alias="resolutionNotes")


class ConsistencyIssueSummary(BaseModel):
    """Summary counts for consistency issues."""

    model_config = ConfigDict(populate_by_name=True)

    total_count: int = Field(..., alias="totalCount", description="Total issues")
    open_count: int = Field(..., alias="openCount", description="Open issues")
    warning_count: int = Field(..., alias="warningCount", description="Warning-level open")
    error_count: int = Field(..., alias="errorCount", description="Error-level open")


class ConsistencyIssueListResponse(BaseModel):
    """API response for listing consistency issues."""

    model_config = ConfigDict(populate_by_name=True)

    data: list[ConsistencyIssue]
    meta: dict = Field(default_factory=dict)


class ConsistencyIssueSummaryResponse(BaseModel):
    """API response for issue summary."""

    data: ConsistencyIssueSummary


# =============================================================================
# Issue Type Labels and Descriptions
# =============================================================================

ISSUE_TYPE_LABELS = {
    IssueType.DATE_MISMATCH: "Date Mismatch",
    IssueType.ENTITY_NAME_MISMATCH: "Entity Name Mismatch",
    IssueType.AMOUNT_DISCREPANCY: "Amount Discrepancy",
    IssueType.CITATION_CONFLICT: "Citation Conflict",
    IssueType.TIMELINE_GAP: "Timeline Gap",
    IssueType.DUPLICATE_EVENT: "Duplicate Event",
}

ISSUE_TYPE_DESCRIPTIONS = {
    IssueType.DATE_MISMATCH: "Different dates found for the same event in timeline and entity data",
    IssueType.ENTITY_NAME_MISMATCH: "Entity name variations between MIG and citations",
    IssueType.AMOUNT_DISCREPANCY: "Monetary or numeric values differ between extractions",
    IssueType.CITATION_CONFLICT: "Citation information conflicts with document content",
    IssueType.TIMELINE_GAP: "Missing events in timeline that are referenced elsewhere",
    IssueType.DUPLICATE_EVENT: "Same event appears multiple times with different details",
}

SEVERITY_LABELS = {
    IssueSeverity.INFO: "Info",
    IssueSeverity.WARNING: "Warning",
    IssueSeverity.ERROR: "Error",
}
