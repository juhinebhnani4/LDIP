"""Summary models for Matter Executive Summary API.

Story 14.1: Summary API Endpoint
Story 14.6: Summary Frontend Integration (Citation models)

Pydantic models matching the frontend TypeScript interface in types/summary.ts.
These models define the structure for AI-generated executive summaries of matters.

CRITICAL: Must match frontend types exactly for seamless API integration.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# =============================================================================
# Story 14.1: Enums (Task 1.2)
# =============================================================================


class AttentionItemType(str, Enum):
    """Type of attention item requiring user action.

    Story 14.1: AC #5 - Dynamically computed attention items.
    """

    CONTRADICTION = "contradiction"
    CITATION_ISSUE = "citation_issue"
    TIMELINE_GAP = "timeline_gap"


class PartyRole(str, Enum):
    """Party role in the matter.

    Story 14.1: AC #6 - Parties extracted from MIG.
    """

    PETITIONER = "petitioner"
    RESPONDENT = "respondent"
    OTHER = "other"


class KeyIssueVerificationStatus(str, Enum):
    """Verification status for key issues.

    Story 14.1: AC #2 - Key issues with verification status.
    """

    VERIFIED = "verified"
    PENDING = "pending"
    FLAGGED = "flagged"


# =============================================================================
# Story 14.1: Component Models (Task 1.3)
# =============================================================================


class AttentionItem(BaseModel):
    """Attention item - issues needing user action.

    Story 14.1: AC #5 - Dynamically computed from database tables.
    """

    type: AttentionItemType = Field(
        ...,
        description="Type of attention item",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of items of this type",
    )
    label: str = Field(
        ...,
        description="Human-readable label",
    )
    target_tab: str = Field(
        ...,
        alias="targetTab",
        description="Tab to navigate to for resolution",
    )

    model_config = {"populate_by_name": True}


class PartyInfo(BaseModel):
    """Party information - key parties in the matter.

    Story 14.1: AC #6 - Parties extracted from MIG.
    Story 14.6: AC #9 - Include citation data for CitationLink.
    """

    entity_id: str = Field(
        ...,
        alias="entityId",
        description="Unique entity ID",
    )
    entity_name: str = Field(
        ...,
        alias="entityName",
        description="Display name of the entity",
    )
    role: PartyRole = Field(
        ...,
        description="Role in the matter",
    )
    source_document: str = Field(
        ...,
        alias="sourceDocument",
        description="Source document name",
    )
    source_page: int = Field(
        ...,
        alias="sourcePage",
        ge=1,
        description="Source page number",
    )
    is_verified: bool = Field(
        False,
        alias="isVerified",
        description="Whether the party has been verified",
    )
    # Story 14.6: Citation data for CitationLink components
    citation: Citation | None = Field(
        None,
        description="Citation for party source (Story 14.6)",
    )

    model_config = {"populate_by_name": True}


class SubjectMatterSource(BaseModel):
    """Subject matter source reference.

    Story 14.1: AC #2 - Source citations for subject matter.
    """

    document_name: str = Field(
        ...,
        alias="documentName",
        description="Document name",
    )
    page_range: str = Field(
        ...,
        alias="pageRange",
        description="Page range (e.g., '1-3')",
    )

    model_config = {"populate_by_name": True}


class SubjectMatter(BaseModel):
    """Subject matter - what the case is about.

    Story 14.1: AC #3 - GPT-4 generated description.
    Story 14.6: AC #9 - Include citation data for CitationLink.
    """

    description: str = Field(
        ...,
        description="AI-generated description",
    )
    sources: list[SubjectMatterSource] = Field(
        default_factory=list,
        description="Source citations",
    )
    is_verified: bool = Field(
        False,
        alias="isVerified",
        description="Whether subject matter has been verified",
    )
    # Story 14.6: Citation data for CitationLink components
    edited_content: str | None = Field(
        None,
        alias="editedContent",
        description="User-edited content (if modified)",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citation links for factual claims (Story 14.6)",
    )

    model_config = {"populate_by_name": True}


class CurrentStatus(BaseModel):
    """Current status - latest order and proceedings.

    Story 14.1: AC #2 - Current status of the matter.
    Story 14.6: AC #9 - Include citation data for CitationLink.
    """

    last_order_date: str = Field(
        ...,
        alias="lastOrderDate",
        description="Date of last order (ISO format)",
    )
    description: str = Field(
        ...,
        description="Description of last order",
    )
    source_document: str = Field(
        ...,
        alias="sourceDocument",
        description="Source document name",
    )
    source_page: int = Field(
        ...,
        alias="sourcePage",
        ge=1,
        description="Source page number",
    )
    is_verified: bool = Field(
        False,
        alias="isVerified",
        description="Whether status has been verified",
    )
    # Story 14.6: Citation data for CitationLink components
    edited_content: str | None = Field(
        None,
        alias="editedContent",
        description="User-edited content (if modified)",
    )
    citation: Citation | None = Field(
        None,
        description="Citation for source reference (Story 14.6)",
    )

    model_config = {"populate_by_name": True}


class KeyIssue(BaseModel):
    """Key issue in the matter.

    Story 14.1: AC #3 - GPT-4 extracted key issues.
    """

    id: str = Field(
        ...,
        description="Unique ID",
    )
    number: int = Field(
        ...,
        ge=1,
        description="Issue number for display",
    )
    title: str = Field(
        ...,
        description="Issue title/description",
    )
    verification_status: KeyIssueVerificationStatus = Field(
        KeyIssueVerificationStatus.PENDING,
        alias="verificationStatus",
        description="Verification status",
    )

    model_config = {"populate_by_name": True}


class MatterStats(BaseModel):
    """Matter statistics.

    Story 14.1: AC #7 - Stats computed from actual database tables.
    """

    total_pages: int = Field(
        0,
        alias="totalPages",
        ge=0,
        description="Total pages across all documents",
    )
    entities_found: int = Field(
        0,
        alias="entitiesFound",
        ge=0,
        description="Number of entities extracted",
    )
    events_extracted: int = Field(
        0,
        alias="eventsExtracted",
        ge=0,
        description="Number of events extracted",
    )
    citations_found: int = Field(
        0,
        alias="citationsFound",
        ge=0,
        description="Number of citations found",
    )
    verification_percent: float = Field(
        0.0,
        alias="verificationPercent",
        ge=0,
        le=100,
        description="Verification completion percentage (0-100)",
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Story 14.1: Main Summary Model (Task 1.3)
# =============================================================================


class MatterSummary(BaseModel):
    """Complete matter summary data.

    Story 14.1: AC #2 - Summary data structure matches frontend TypeScript interface.
    """

    matter_id: str = Field(
        ...,
        alias="matterId",
        description="Matter ID",
    )
    attention_items: list[AttentionItem] = Field(
        default_factory=list,
        alias="attentionItems",
        description="Items requiring attention",
    )
    parties: list[PartyInfo] = Field(
        default_factory=list,
        description="Key parties in the matter",
    )
    subject_matter: SubjectMatter = Field(
        ...,
        alias="subjectMatter",
        description="Subject matter description",
    )
    current_status: CurrentStatus = Field(
        ...,
        alias="currentStatus",
        description="Current status of proceedings",
    )
    key_issues: list[KeyIssue] = Field(
        default_factory=list,
        alias="keyIssues",
        description="Key issues identified",
    )
    stats: MatterStats = Field(
        ...,
        description="Matter statistics",
    )
    generated_at: str = Field(
        ...,
        alias="generatedAt",
        description="When summary was generated (ISO timestamp)",
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Story 14.1: API Response Model (Task 1.4)
# =============================================================================


class MatterSummaryResponse(BaseModel):
    """API response wrapper for matter summary.

    Story 14.1: AC #1 - Follows project API response pattern with data wrapper.
    """

    data: MatterSummary = Field(
        ...,
        description="Summary data",
    )


# =============================================================================
# Story 14.1: Error Response Model
# =============================================================================


class SummaryErrorDetail(BaseModel):
    """Error detail structure.

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


class SummaryErrorResponse(BaseModel):
    """Error response structure.

    Follows project API error pattern from project-context.md.
    """

    error: SummaryErrorDetail


# =============================================================================
# Story 14.4: Summary Verification Models (Task 3)
# =============================================================================


class SummaryVerificationDecisionEnum(str, Enum):
    """Summary section verification decision.

    Story 14.4: AC #1 - Verification decision types.
    """

    VERIFIED = "verified"
    FLAGGED = "flagged"


class SummarySectionTypeEnum(str, Enum):
    """Summary section types that can be verified.

    Story 14.4: AC #4 - Section type enum matching database.
    """

    PARTIES = "parties"
    SUBJECT_MATTER = "subject_matter"
    CURRENT_STATUS = "current_status"
    KEY_ISSUE = "key_issue"


class SummaryVerificationCreate(BaseModel):
    """Request to create/update summary verification.

    Story 14.4: AC #1 - POST /summary/verify request body.
    """

    section_type: SummarySectionTypeEnum = Field(
        ...,
        alias="sectionType",
        description="Type of section being verified",
    )
    section_id: str = Field(
        ...,
        alias="sectionId",
        description="Entity ID for parties, 'main' for other sections, issue ID for key_issue",
    )
    decision: SummaryVerificationDecisionEnum = Field(
        ...,
        description="Verification decision: verified or flagged",
    )
    notes: str | None = Field(
        None,
        max_length=2000,
        description="Optional notes",
    )

    model_config = {"populate_by_name": True}


class SummaryVerificationRecord(BaseModel):
    """Summary verification record from database.

    Story 14.4: AC #3 - Verification record response.
    """

    id: str = Field(
        ...,
        description="Verification record ID",
    )
    matter_id: str = Field(
        ...,
        alias="matterId",
        description="Matter ID",
    )
    section_type: SummarySectionTypeEnum = Field(
        ...,
        alias="sectionType",
        description="Section type",
    )
    section_id: str = Field(
        ...,
        alias="sectionId",
        description="Section ID",
    )
    decision: SummaryVerificationDecisionEnum = Field(
        ...,
        description="Verification decision",
    )
    notes: str | None = Field(
        None,
        description="Optional notes",
    )
    verified_by: str = Field(
        ...,
        alias="verifiedBy",
        description="User ID who verified",
    )
    verified_at: str = Field(
        ...,
        alias="verifiedAt",
        description="Verification timestamp (ISO)",
    )

    model_config = {"populate_by_name": True}


class SummaryNoteCreate(BaseModel):
    """Request to create summary note.

    Story 14.4: AC #2 - POST /summary/notes request body.
    """

    section_type: SummarySectionTypeEnum = Field(
        ...,
        alias="sectionType",
        description="Type of section",
    )
    section_id: str = Field(
        ...,
        alias="sectionId",
        description="Section ID",
    )
    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Note text content",
    )

    model_config = {"populate_by_name": True}


class SummaryNoteRecord(BaseModel):
    """Summary note record from database.

    Story 14.4: AC #5 - Note record response.
    """

    id: str = Field(
        ...,
        description="Note ID",
    )
    matter_id: str = Field(
        ...,
        alias="matterId",
        description="Matter ID",
    )
    section_type: SummarySectionTypeEnum = Field(
        ...,
        alias="sectionType",
        description="Section type",
    )
    section_id: str = Field(
        ...,
        alias="sectionId",
        description="Section ID",
    )
    text: str = Field(
        ...,
        description="Note text",
    )
    created_by: str = Field(
        ...,
        alias="createdBy",
        description="User ID who created",
    )
    created_at: str = Field(
        ...,
        alias="createdAt",
        description="Creation timestamp (ISO)",
    )

    model_config = {"populate_by_name": True}


class SummaryVerificationResponse(BaseModel):
    """API response for single verification.

    Story 14.4: AC #1 - Single verification response wrapper.
    """

    data: SummaryVerificationRecord


class SummaryVerificationsListResponse(BaseModel):
    """API response for verification list.

    Story 14.4: AC #3 - List verification response wrapper.
    """

    data: list[SummaryVerificationRecord]
    meta: dict = Field(default_factory=dict)


class SummaryNoteResponse(BaseModel):
    """API response for single note.

    Story 14.4: AC #2 - Single note response wrapper.
    """

    data: SummaryNoteRecord


# =============================================================================
# Story 14.6: Summary Edit Models (Task 1.1, 1.2)
# =============================================================================


class Citation(BaseModel):
    """Citation reference for source verification.

    Story 14.6: AC #9 - Citation data for navigation to PDF viewer.
    """

    document_id: str = Field(
        ...,
        alias="documentId",
        description="Document UUID",
    )
    document_name: str = Field(
        ...,
        alias="documentName",
        description="Display name of document",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Page number",
    )
    excerpt: str | None = Field(
        None,
        description="Optional text excerpt",
    )

    model_config = {"populate_by_name": True}


class SummaryEditCreate(BaseModel):
    """Request to save summary edit.

    Story 14.6: AC #7 - PUT /summary/sections/{section_type} request body.
    """

    section_id: str = Field(
        ...,
        alias="sectionId",
        description="Section ID ('main' for subject_matter/current_status, entity_id for parties)",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Edited text content",
    )
    original_content: str = Field(
        ...,
        alias="originalContent",
        description="Original AI-generated content",
    )

    model_config = {"populate_by_name": True}


class SummaryEditRecord(BaseModel):
    """Summary edit record from database.

    Story 14.6: AC #7 - Edit record response.
    """

    id: str = Field(
        ...,
        description="Edit record ID",
    )
    matter_id: str = Field(
        ...,
        alias="matterId",
        description="Matter ID",
    )
    section_type: SummarySectionTypeEnum = Field(
        ...,
        alias="sectionType",
        description="Section type",
    )
    section_id: str = Field(
        ...,
        alias="sectionId",
        description="Section ID",
    )
    original_content: str = Field(
        ...,
        alias="originalContent",
        description="Original AI-generated content",
    )
    edited_content: str = Field(
        ...,
        alias="editedContent",
        description="User-edited content",
    )
    edited_by: str = Field(
        ...,
        alias="editedBy",
        description="User ID who edited",
    )
    edited_at: str = Field(
        ...,
        alias="editedAt",
        description="Edit timestamp (ISO)",
    )

    model_config = {"populate_by_name": True}


class SummaryEditResponse(BaseModel):
    """API response for edit operation.

    Story 14.6: AC #7 - Single edit response wrapper.
    """

    data: SummaryEditRecord


class SummaryRegenerateRequest(BaseModel):
    """Request to regenerate summary section.

    Story 14.6: AC #8 - POST /summary/regenerate request body.
    """

    section_type: SummarySectionTypeEnum = Field(
        ...,
        alias="sectionType",
        description="Section type to regenerate",
    )

    model_config = {"populate_by_name": True}
