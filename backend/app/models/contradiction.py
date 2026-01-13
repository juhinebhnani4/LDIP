"""Contradiction engine models for statement querying and analysis.

Pydantic models for:
- Statement retrieval and grouping (Story 5-1)
- Statement comparison (Story 5-2)
- Contradiction classification (Story 5-3)
- Severity scoring (Story 5-4)

Part of the Contradiction Engine pipeline in Epic 5.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Enums
# =============================================================================


class StatementValueType(str, Enum):
    """Types of extractable values from statements.

    Used for comparing factual claims across documents.
    """

    DATE = "DATE"
    AMOUNT = "AMOUNT"
    QUANTITY = "QUANTITY"


# =============================================================================
# Value Extraction Models (Story 5-1)
# =============================================================================


class StatementValue(BaseModel):
    """Extracted value from a statement (date, amount, or quantity).

    Supports Indian formats for dates and amounts.

    Examples:
        - Date: "15/01/2024" → StatementValue(type=DATE, raw_text="15/01/2024", normalized="2024-01-15")
        - Amount: "Rs. 5 lakhs" → StatementValue(type=AMOUNT, raw_text="Rs. 5 lakhs", normalized="500000")
    """

    type: StatementValueType = Field(..., description="Value type classification")
    raw_text: str = Field(..., description="Original text as found in statement")
    normalized: str = Field(
        ..., description="Normalized value for comparison (ISO date, numeric amount)"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence"
    )


# =============================================================================
# Statement Models (Story 5-1)
# =============================================================================


class Statement(BaseModel):
    """A statement about an entity extracted from a document chunk.

    Represents a piece of content that makes claims about an entity,
    with extracted dates and amounts for comparison.
    """

    model_config = ConfigDict(populate_by_name=True)

    entity_id: str = Field(..., alias="entityId", description="Canonical entity UUID")
    chunk_id: str = Field(..., alias="chunkId", description="Source chunk UUID")
    document_id: str = Field(..., alias="documentId", description="Source document UUID")
    content: str = Field(..., description="Statement text content")
    dates: list[StatementValue] = Field(
        default_factory=list, description="Extracted dates from statement"
    )
    amounts: list[StatementValue] = Field(
        default_factory=list, description="Extracted amounts from statement"
    )
    page_number: int | None = Field(
        None, alias="pageNumber", description="Source page number"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Statement extraction confidence"
    )


class DocumentStatements(BaseModel):
    """Statements grouped by document source.

    Groups all statements about an entity from a single document.
    """

    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(..., alias="documentId", description="Document UUID")
    document_name: str | None = Field(
        None, alias="documentName", description="Document filename"
    )
    statements: list[Statement] = Field(
        default_factory=list, description="Statements from this document"
    )
    statement_count: int = Field(
        default=0, alias="statementCount", description="Number of statements"
    )


class EntityStatements(BaseModel):
    """All statements about an entity, grouped by document.

    Response model for entity statement queries (AC #1).
    """

    model_config = ConfigDict(populate_by_name=True)

    entity_id: str = Field(..., alias="entityId", description="Canonical entity UUID")
    entity_name: str = Field(..., alias="entityName", description="Entity canonical name")
    total_statements: int = Field(
        default=0, alias="totalStatements", description="Total statement count"
    )
    documents: list[DocumentStatements] = Field(
        default_factory=list, description="Statements grouped by document"
    )
    aliases_included: list[str] = Field(
        default_factory=list,
        alias="aliasesIncluded",
        description="Aliases that were searched (AC #2)",
    )


# =============================================================================
# API Response Models
# =============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    model_config = ConfigDict(populate_by_name=True)

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., alias="perPage", ge=1, description="Items per page")
    total_pages: int = Field(..., alias="totalPages", ge=0, description="Total pages")


class EntityStatementsResponse(BaseModel):
    """API response for entity statements query."""

    data: EntityStatements
    meta: PaginationMeta


class StatementsEmptyResponse(BaseModel):
    """API response when no statements exist for an entity (AC #4)."""

    model_config = ConfigDict(populate_by_name=True)

    data: EntityStatements
    meta: PaginationMeta
    message: str = Field(
        default="No statements found for this entity",
        description="Informational message",
    )


# =============================================================================
# Error Models
# =============================================================================


class ContradictionErrorDetail(BaseModel):
    """Error detail structure for contradiction API."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict = Field(default_factory=dict, description="Additional error context")


class ContradictionErrorResponse(BaseModel):
    """Error response structure for contradiction API."""

    error: ContradictionErrorDetail
