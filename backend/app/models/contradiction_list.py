"""Contradiction List API models for Story 14.2.

Story 14.2: Contradictions List API Endpoint

Pydantic models for the GET /api/matters/{matter_id}/contradictions endpoint.
Returns ALL contradictions for a matter grouped by entity.

CRITICAL: Must match frontend TypeScript interface for seamless API integration.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.contradiction import ContradictionType, PaginationMeta, SeverityLevel

# =============================================================================
# Constants
# =============================================================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_EXCERPT_LENGTH = 200


# =============================================================================
# Statement Info Model
# =============================================================================


class StatementInfo(BaseModel):
    """Information about a statement in a contradiction.

    Story 14.2: AC #2 - Statement details for display.
    """

    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(
        ...,
        alias="documentId",
        description="Source document UUID",
    )
    document_name: str = Field(
        ...,
        alias="documentName",
        description="Document filename for display",
    )
    page: int | None = Field(
        None,
        description="Page number (nullable if unknown)",
    )
    excerpt: str = Field(
        ...,
        description="Statement content excerpt (truncated to MAX_EXCERPT_LENGTH)",
    )
    date: str | None = Field(
        None,
        description="Extracted date from statement (nullable)",
    )


# =============================================================================
# Evidence Link Model (for list endpoint)
# =============================================================================


class ContradictionEvidenceLink(BaseModel):
    """Link to source document for evidence viewing.

    Story 14.2: AC #2 - Evidence links for click to view in PDF.
    """

    model_config = ConfigDict(populate_by_name=True)

    statement_id: str = Field(
        ...,
        alias="statementId",
        description="Chunk ID reference",
    )
    document_id: str = Field(
        ...,
        alias="documentId",
        description="Source document UUID",
    )
    document_name: str = Field(
        ...,
        alias="documentName",
        description="Document filename for display",
    )
    page: int | None = Field(
        None,
        description="Page number for navigation",
    )
    bbox_ids: list[str] = Field(
        default_factory=list,
        alias="bboxIds",
        description="Bounding box IDs for PDF overlay",
    )


# =============================================================================
# Contradiction Item Model
# =============================================================================


class ContradictionItem(BaseModel):
    """A single contradiction for display in the list.

    Story 14.2: AC #2 - Full contradiction details for attorney review.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        ...,
        description="Contradiction UUID (statement_comparisons.id)",
    )
    contradiction_type: ContradictionType = Field(
        ...,
        alias="contradictionType",
        description="Type: semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch",
    )
    severity: SeverityLevel = Field(
        ...,
        description="Severity: high, medium, low",
    )
    entity_id: str = Field(
        ...,
        alias="entityId",
        description="Canonical entity UUID",
    )
    entity_name: str = Field(
        ...,
        alias="entityName",
        description="Entity canonical name",
    )
    statement_a: StatementInfo = Field(
        ...,
        alias="statementA",
        description="First statement in the contradiction",
    )
    statement_b: StatementInfo = Field(
        ...,
        alias="statementB",
        description="Second statement in the contradiction",
    )
    explanation: str = Field(
        ...,
        description="Natural language explanation of the contradiction",
    )
    evidence_links: list[ContradictionEvidenceLink] = Field(
        default_factory=list,
        alias="evidenceLinks",
        description="Links to view evidence in PDF",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1)",
    )
    created_at: str = Field(
        ...,
        alias="createdAt",
        description="When contradiction was detected (ISO timestamp)",
    )


# =============================================================================
# Entity Contradictions Model (grouped by entity)
# =============================================================================


class EntityContradictions(BaseModel):
    """Contradictions grouped by entity.

    Story 14.2: AC #2 - Group contradictions by entity with canonical name header.
    """

    model_config = ConfigDict(populate_by_name=True)

    entity_id: str = Field(
        ...,
        alias="entityId",
        description="Canonical entity UUID",
    )
    entity_name: str = Field(
        ...,
        alias="entityName",
        description="Entity canonical name for header display",
    )
    contradictions: list[ContradictionItem] = Field(
        default_factory=list,
        description="Contradictions for this entity",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of contradictions for this entity",
    )


# =============================================================================
# API Response Model
# =============================================================================


class ContradictionsListResponse(BaseModel):
    """API response for contradictions list endpoint.

    Story 14.2: AC #1, #2, #4 - Paginated response with entity-grouped contradictions.
    """

    data: list[EntityContradictions] = Field(
        ...,
        description="Contradictions grouped by entity",
    )
    meta: PaginationMeta = Field(
        ...,
        description="Pagination metadata",
    )


# =============================================================================
# Error Response Model
# =============================================================================


class ContradictionListErrorDetail(BaseModel):
    """Error detail structure for contradiction list API."""

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


class ContradictionListErrorResponse(BaseModel):
    """Error response structure for contradiction list API."""

    error: ContradictionListErrorDetail
