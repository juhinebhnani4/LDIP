"""Citation models for Act Citation Extraction.

Pydantic models for citation extraction, storage, and API responses.
Supports the Citation Verification Engine for tracking Act references
in legal documents (Story 3-1).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Enums
# =============================================================================


class VerificationStatus(str, Enum):
    """Citation verification status.

    Status values:
    - PENDING: Citation extracted but not yet verified
    - VERIFIED: Citation verified against uploaded Act
    - MISMATCH: Citation text does not match Act section
    - SECTION_NOT_FOUND: Section not found in Act document
    - ACT_UNAVAILABLE: Act document not yet uploaded
    """

    PENDING = "pending"
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    SECTION_NOT_FOUND = "section_not_found"
    ACT_UNAVAILABLE = "act_unavailable"


class ActResolutionStatus(str, Enum):
    """Act document resolution status.

    Status values:
    - AVAILABLE: Act document uploaded and available
    - MISSING: Act document not yet uploaded
    - SKIPPED: User chose to skip uploading this Act
    """

    AVAILABLE = "available"
    MISSING = "missing"
    SKIPPED = "skipped"


class UserAction(str, Enum):
    """User action on Act resolution.

    Actions:
    - UPLOADED: User uploaded the Act document
    - SKIPPED: User chose to skip this Act
    - PENDING: Awaiting user action
    """

    UPLOADED = "uploaded"
    SKIPPED = "skipped"
    PENDING = "pending"


# =============================================================================
# Citation Models
# =============================================================================


class CitationBase(BaseModel):
    """Base citation properties."""

    act_name: str = Field(..., description="Normalized Act name")
    section_number: str = Field(..., description="Section number (e.g., '138', '13(2)')")
    subsection: str | None = Field(
        None, description="Subsection if present (e.g., '(1)')"
    )
    clause: str | None = Field(None, description="Clause if present (e.g., '(a)')")


class CitationCreate(CitationBase):
    """Model for creating a citation record."""

    matter_id: str = Field(..., description="Matter UUID for isolation")
    document_id: str = Field(..., description="Source document UUID")
    source_page: int = Field(..., ge=1, description="Page number where citation appears")
    source_bbox_ids: list[str] = Field(
        default_factory=list, description="Bounding box UUIDs for highlighting"
    )
    act_name_original: str | None = Field(
        None, description="Original Act name before normalization"
    )
    raw_citation_text: str = Field(
        ..., description="Exact citation text extracted from document"
    )
    quoted_text: str | None = Field(
        None, description="Any text quoted from the Act in the document"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Extraction confidence (0-100)"
    )
    extraction_metadata: dict = Field(
        default_factory=dict,
        description="Extraction metadata (model, patterns, timestamps)",
    )


class CitationUpdate(BaseModel):
    """Model for updating a citation record."""

    verification_status: VerificationStatus | None = None
    target_act_document_id: str | None = None
    target_page: int | None = None
    target_bbox_ids: list[str] | None = None
    confidence: float | None = Field(None, ge=0.0, le=100.0)


class Citation(CitationBase):
    """Complete citation model returned from API."""

    id: str = Field(..., description="Citation UUID")
    matter_id: str = Field(..., description="Matter UUID")
    document_id: str = Field(..., description="Source document UUID")
    source_page: int = Field(..., description="Page number in source document")
    source_bbox_ids: list[str] = Field(
        default_factory=list, description="Bounding box UUIDs"
    )
    act_name_original: str | None = Field(
        None, description="Original Act name before normalization"
    )
    raw_citation_text: str | None = Field(None, description="Exact citation text")
    quoted_text: str | None = Field(None, description="Quoted Act text")
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.PENDING, description="Verification status"
    )
    target_act_document_id: str | None = Field(
        None, description="Matched Act document UUID"
    )
    target_page: int | None = Field(None, description="Page in Act document")
    target_bbox_ids: list[str] = Field(
        default_factory=list, description="Bounding boxes in Act document"
    )
    confidence: float = Field(default=0.0, description="Extraction/verification confidence")
    extraction_metadata: dict = Field(
        default_factory=dict, description="Extraction metadata"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Populated in list views for convenience
    document_name: str | None = Field(None, description="Source document name")


# =============================================================================
# Act Resolution Models
# =============================================================================


class ActResolutionBase(BaseModel):
    """Base Act resolution properties."""

    act_name_normalized: str = Field(
        ..., description="Normalized Act name for matching (lowercase, no punctuation)"
    )
    act_name_display: str | None = Field(
        None, description="Display name (e.g., 'Negotiable Instruments Act, 1881')"
    )


class ActResolutionCreate(ActResolutionBase):
    """Model for creating an Act resolution record."""

    matter_id: str = Field(..., description="Matter UUID for isolation")


class ActResolutionUpdate(BaseModel):
    """Model for updating an Act resolution record."""

    act_document_id: str | None = None
    resolution_status: ActResolutionStatus | None = None
    user_action: UserAction | None = None
    citation_count: int | None = None


class ActResolution(ActResolutionBase):
    """Complete Act resolution model returned from API."""

    id: str = Field(..., description="Resolution UUID")
    matter_id: str = Field(..., description="Matter UUID")
    act_document_id: str | None = Field(None, description="Uploaded Act document UUID")
    resolution_status: ActResolutionStatus = Field(
        default=ActResolutionStatus.MISSING, description="Resolution status"
    )
    user_action: UserAction = Field(
        default=UserAction.PENDING, description="User action on resolution"
    )
    citation_count: int = Field(
        default=0, description="Number of citations referencing this Act"
    )
    first_seen_at: datetime | None = Field(
        None, description="When Act was first referenced"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# =============================================================================
# Extraction Result Models
# =============================================================================


class ExtractedCitation(BaseModel):
    """Single citation extracted from text (Gemini extraction output)."""

    act_name: str = Field(..., description="Act name as extracted")
    section: str = Field(..., description="Section reference (e.g., '138')")
    subsection: str | None = Field(None, description="Subsection if present")
    clause: str | None = Field(None, description="Clause if present")
    raw_text: str = Field(..., description="Exact citation text")
    quoted_text: str | None = Field(None, description="Quoted Act text if any")
    confidence: float = Field(
        default=80.0, ge=0.0, le=100.0, description="Extraction confidence"
    )


class CitationExtractionResult(BaseModel):
    """Complete extraction result from citation extractor.

    Contains all citations extracted from a document or chunk.
    """

    citations: list[ExtractedCitation] = Field(
        default_factory=list, description="Extracted citations"
    )
    unique_acts: list[str] = Field(
        default_factory=list, description="Unique Act names found"
    )
    source_document_id: str | None = Field(None, description="Source document UUID")
    source_chunk_id: str | None = Field(None, description="Source chunk UUID")
    page_number: int | None = Field(None, description="Page number if available")
    extraction_timestamp: datetime | None = Field(
        None, description="When extraction occurred"
    )


# =============================================================================
# Act Discovery Models
# =============================================================================


class ActDiscoverySummary(BaseModel):
    """Summary of an Act for the Act Discovery Report."""

    act_name: str = Field(..., description="Display name of Act")
    act_name_normalized: str = Field(..., description="Normalized name for matching")
    citation_count: int = Field(..., description="Number of citations referencing this Act")
    resolution_status: ActResolutionStatus = Field(
        ..., description="Current resolution status"
    )
    user_action: UserAction = Field(..., description="User action status")
    act_document_id: str | None = Field(None, description="Uploaded Act document UUID")


# =============================================================================
# API Response Models
# =============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")
    total_pages: int | None = Field(None, ge=0, description="Total number of pages")


class CitationListItem(BaseModel):
    """Citation item for list responses (subset of Citation)."""

    id: str = Field(..., description="Citation UUID")
    act_name: str = Field(..., description="Normalized Act name")
    section_number: str = Field(..., description="Section number")
    subsection: str | None = Field(None, description="Subsection if present")
    raw_citation_text: str | None = Field(None, description="Exact citation text")
    source_page: int = Field(..., description="Page number in source document")
    verification_status: VerificationStatus = Field(..., description="Verification status")
    confidence: float = Field(..., description="Extraction confidence")
    document_id: str = Field(..., description="Source document UUID")
    document_name: str | None = Field(None, description="Source document name")


class CitationsListResponse(BaseModel):
    """API response for citation list endpoints."""

    data: list[CitationListItem]
    meta: PaginationMeta


class CitationResponse(BaseModel):
    """API response for single citation retrieval."""

    data: Citation


class CitationSummaryItem(BaseModel):
    """Citation count summary by Act."""

    model_config = ConfigDict(populate_by_name=True)

    act_name: str = Field(..., alias="actName", description="Act name")
    citation_count: int = Field(..., alias="citationCount", description="Number of citations")
    verified_count: int = Field(default=0, alias="verifiedCount", description="Number verified")
    pending_count: int = Field(default=0, alias="pendingCount", description="Number pending")


class CitationSummaryResponse(BaseModel):
    """API response for citation summary endpoint."""

    data: list[CitationSummaryItem]


class ActDiscoveryResponse(BaseModel):
    """API response for Act Discovery Report endpoint."""

    data: list[ActDiscoverySummary]


# =============================================================================
# Error Models
# =============================================================================


class CitationErrorDetail(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict = Field(default_factory=dict, description="Additional error context")


class CitationErrorResponse(BaseModel):
    """Error response structure."""

    error: CitationErrorDetail
