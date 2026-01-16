"""Export models for document generation.

Story 12-3: Export Verification Check and Format Generation
Epic 12: Export Builder

These models define the structure for export generation:
- ExportFormat: Enum for supported export formats (PDF, Word, PowerPoint)
- ExportStatus: Enum for export generation status
- ExportRequest: Request model for export generation
- ExportRecord: Complete export record from database
- ExportResponse: API response wrapper

Implements:
- AC #3: Support PDF, Word, and PowerPoint formats
- AC #4: Include verification status in exports
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# =============================================================================
# Story 12-3: Export Enums (Task 2.4)
# =============================================================================


class ExportFormat(str, Enum):
    """Supported export formats.

    Story 12-3: AC #3 - Multiple export format support.
    """

    PDF = "pdf"
    WORD = "word"
    POWERPOINT = "powerpoint"


class ExportStatus(str, Enum):
    """Export generation status.

    Story 12-3: Status tracking for async generation.
    """

    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Story 12-3: Export Request/Response Models (Task 2.4)
# =============================================================================


class ExportSectionEdit(BaseModel):
    """Edit state for a single section.

    Story 12-3: Preserves client-side edits from ExportBuilder.
    """

    text_content: str | None = Field(
        None,
        description="Modified text content for text-based sections",
    )
    removed_item_ids: list[str] = Field(
        default_factory=list,
        description="IDs of removed items in list sections",
    )
    added_notes: list[str] = Field(
        default_factory=list,
        description="Notes added to section",
    )


class ExportRequest(BaseModel):
    """Request model for export generation.

    Story 12-3: AC #3 - Export request with format and sections.
    """

    format: ExportFormat = Field(..., description="Export format (pdf, word, powerpoint)")
    sections: list[str] = Field(
        ...,
        min_length=1,
        description="Section IDs to include in export, in order",
    )
    section_edits: dict[str, ExportSectionEdit] = Field(
        default_factory=dict,
        description="Map of section ID to edit state",
    )
    include_verification_status: bool = Field(
        True,
        description="Include verification status summary in export",
    )


class ExportRecord(BaseModel):
    """Complete export record from database.

    Story 12-3: Full export record with all fields.
    """

    id: str = Field(..., description="Export UUID")
    matter_id: str = Field(..., description="Matter UUID")
    format: ExportFormat = Field(..., description="Export format")
    status: ExportStatus = Field(..., description="Current generation status")
    file_path: str | None = Field(None, description="Storage path for generated file")
    download_url: str | None = Field(None, description="Signed download URL (when completed)")
    file_name: str = Field(..., description="Generated filename")
    sections_included: list[str] = Field(
        default_factory=list,
        description="Sections included in export",
    )
    verification_summary: dict = Field(
        default_factory=dict,
        description="Verification status summary at time of export",
    )
    created_by: str = Field(..., description="User UUID who created export")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: datetime | None = Field(None, description="Completion timestamp")
    error_message: str | None = Field(None, description="Error message if failed")


class ExportResponse(BaseModel):
    """Response for export generation.

    Story 12-3: Follows project API response pattern.
    """

    data: ExportRecord = Field(..., description="Export record")


class ExportGenerationResponse(BaseModel):
    """Response for export generation initiation.

    Story 12-3: Immediate response when export is started.
    """

    export_id: str = Field(..., description="Export UUID for tracking")
    status: ExportStatus = Field(..., description="Current status")
    download_url: str | None = Field(None, description="Download URL (when completed)")
    file_name: str = Field(..., description="Target filename")
    message: str = Field("", description="Status message")


# =============================================================================
# Story 12-3: Verification Summary Model (Task 2.4)
# =============================================================================


class VerificationSummaryForExport(BaseModel):
    """Verification summary to include in exports.

    Story 12-3: AC #4 - Include verification status in exports.
    """

    export_date: datetime = Field(..., description="When export was generated")
    total_findings: int = Field(0, description="Total findings in matter")
    verified_count: int = Field(0, description="Approved by attorney")
    pending_count: int = Field(0, description="Still pending verification")
    warnings_dismissed: int = Field(0, description="Warnings that were dismissed for export")
    exported_by_name: str = Field(..., description="User name who generated export")
    exported_by_email: str = Field(..., description="User email")
