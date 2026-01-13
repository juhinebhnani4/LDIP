"""Contradiction engine models for statement querying and analysis.

Pydantic models for:
- Statement retrieval and grouping (Story 5-1)
- Statement comparison (Story 5-2)
- Contradiction classification (Story 5-3)
- Severity scoring (Story 5-4)

Part of the Contradiction Engine pipeline in Epic 5.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Enums
# =============================================================================


class ComparisonResult(str, Enum):
    """Result of comparing two statements for contradiction.

    Story 5-2: Statement Pair Comparison

    Values:
        CONTRADICTION: Statements directly conflict with each other
        CONSISTENT: Statements are compatible/agree
        UNCERTAIN: Cannot determine with confidence
        UNRELATED: Statements discuss different topics/aspects
    """

    CONTRADICTION = "contradiction"
    CONSISTENT = "consistent"
    UNCERTAIN = "uncertain"
    UNRELATED = "unrelated"


class EvidenceType(str, Enum):
    """Type of evidence supporting a contradiction finding.

    Story 5-2: Categorizes the nature of the conflict.
    """

    DATE_MISMATCH = "date_mismatch"
    AMOUNT_MISMATCH = "amount_mismatch"
    FACTUAL_CONFLICT = "factual_conflict"
    SEMANTIC_CONFLICT = "semantic_conflict"
    NONE = "none"


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


# =============================================================================
# Statement Comparison Models (Story 5-2)
# =============================================================================


class ContradictionEvidence(BaseModel):
    """Evidence supporting a contradiction finding.

    Story 5-2: Captures the specific conflicting values and source references.

    Example:
        >>> evidence = ContradictionEvidence(
        ...     type=EvidenceType.AMOUNT_MISMATCH,
        ...     value_a="500000",
        ...     value_b="800000",
        ...     page_refs={"statement_a": 5, "statement_b": 12}
        ... )
    """

    model_config = ConfigDict(populate_by_name=True)

    type: EvidenceType = Field(
        ..., description="Type of evidence (date_mismatch, amount_mismatch, etc.)"
    )
    value_a: str | None = Field(
        None, alias="valueA", description="Extracted value from statement A (if applicable)"
    )
    value_b: str | None = Field(
        None, alias="valueB", description="Extracted value from statement B (if applicable)"
    )
    page_refs: dict[str, int | None] = Field(
        default_factory=dict,
        alias="pageRefs",
        description="Page references: {statement_a: page, statement_b: page}",
    )


class StatementPairComparison(BaseModel):
    """Result of comparing two statements for contradiction.

    Story 5-2: Captures the GPT-4 chain-of-thought comparison result.
    Story 5-3: Extended with contradiction_type for classification.

    Contains:
    - References to the compared statements
    - Comparison result (contradiction, consistent, uncertain, unrelated)
    - Chain-of-thought reasoning from GPT-4 (AC #4)
    - Confidence score
    - Evidence of conflict if applicable
    - Contradiction type classification (Story 5-3)
    """

    model_config = ConfigDict(populate_by_name=True)

    statement_a_id: str = Field(
        ..., alias="statementAId", description="UUID of first statement (chunk_id)"
    )
    statement_b_id: str = Field(
        ..., alias="statementBId", description="UUID of second statement (chunk_id)"
    )
    statement_a_content: str = Field(
        ..., alias="statementAContent", description="Content of first statement"
    )
    statement_b_content: str = Field(
        ..., alias="statementBContent", description="Content of second statement"
    )
    result: ComparisonResult = Field(
        ..., description="Comparison result classification"
    )
    reasoning: str = Field(
        ..., description="Chain-of-thought reasoning from GPT-4 (AC #4)"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0-1)"
    )
    evidence: ContradictionEvidence = Field(
        ..., description="Evidence supporting the finding"
    )
    document_a_id: str = Field(
        ..., alias="documentAId", description="Source document UUID for statement A"
    )
    document_b_id: str = Field(
        ..., alias="documentBId", description="Source document UUID for statement B"
    )
    page_a: int | None = Field(
        None, alias="pageA", description="Page number for statement A"
    )
    page_b: int | None = Field(
        None, alias="pageB", description="Page number for statement B"
    )
    # Story 5-3: Classification fields (populated after comparison)
    contradiction_type: str | None = Field(
        None,
        alias="contradictionType",
        description="Classification type: semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch. NULL for non-contradictions.",
    )
    extracted_values: dict | None = Field(
        None,
        alias="extractedValues",
        description="Structured values for attorney display: {value_a: {original, normalized}, value_b: {original, normalized}}",
    )


class EntityComparisons(BaseModel):
    """All comparison results for an entity's statements.

    Story 5-2: Groups comparisons by entity for API response.
    """

    model_config = ConfigDict(populate_by_name=True)

    entity_id: str = Field(..., alias="entityId", description="Entity UUID")
    entity_name: str = Field(..., alias="entityName", description="Entity canonical name")
    comparisons: list[StatementPairComparison] = Field(
        default_factory=list, description="All pairwise comparisons"
    )
    contradictions_found: int = Field(
        default=0, alias="contradictionsFound", description="Count of contradictions"
    )
    total_pairs_compared: int = Field(
        default=0, alias="totalPairsCompared", description="Total pairs compared"
    )


class ComparisonMeta(BaseModel):
    """Metadata for comparison operation."""

    model_config = ConfigDict(populate_by_name=True)

    pairs_compared: int = Field(
        ..., alias="pairsCompared", description="Number of pairs compared"
    )
    contradictions_found: int = Field(
        ..., alias="contradictionsFound", description="Number of contradictions detected"
    )
    total_cost_usd: float = Field(
        ..., alias="totalCostUsd", ge=0.0, description="Total GPT-4 API cost in USD"
    )
    processing_time_ms: int = Field(
        ..., alias="processingTimeMs", ge=0, description="Total processing time in milliseconds"
    )


class EntityComparisonsResponse(BaseModel):
    """API response for entity statement comparison."""

    data: EntityComparisons
    meta: ComparisonMeta


class ComparisonJobResponse(BaseModel):
    """API response when async processing is triggered (>100 statements).

    Story 5-2: For large entity statement sets, returns job_id for tracking.
    """

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(..., alias="jobId", description="Background job UUID")
    message: str = Field(
        default="Comparison job started. Poll /jobs/{job_id} for status.",
        description="Status message",
    )
    estimated_pairs: int = Field(
        ..., alias="estimatedPairs", description="Estimated number of pairs to compare"
    )


# =============================================================================
# Contradiction Classification Models (Story 5-3)
# =============================================================================


class ContradictionType(str, Enum):
    """Classification of contradiction type for attorney prioritization.

    Story 5-3: Attorneys can prioritize factual contradictions over semantic ones.

    Values:
        SEMANTIC_CONTRADICTION: Statements mean opposite things when analyzed
        FACTUAL_CONTRADICTION: Direct factual disagreement (e.g., ownership conflict)
        DATE_MISMATCH: Same event/fact has different dates
        AMOUNT_MISMATCH: Same transaction/value has different amounts
    """

    SEMANTIC_CONTRADICTION = "semantic_contradiction"
    FACTUAL_CONTRADICTION = "factual_contradiction"
    DATE_MISMATCH = "date_mismatch"
    AMOUNT_MISMATCH = "amount_mismatch"


class ExtractedValue(BaseModel):
    """Extracted value with original and normalized forms for attorney display.

    Story 5-3: Both dates and amounts are displayed with their original format
    and normalized value for comparison.

    Example:
        >>> ExtractedValue(original="15/01/2024", normalized="2024-01-15")
        >>> ExtractedValue(original="5 lakhs", normalized="500000")
    """

    original: str = Field(..., description="Original text as found in statement")
    normalized: str = Field(
        ..., description="Normalized value (ISO date or numeric amount)"
    )


class ExtractedValues(BaseModel):
    """Structured conflicting values for attorney display.

    Story 5-3: Contains the extracted values from both statements
    for side-by-side comparison.
    """

    model_config = ConfigDict(populate_by_name=True)

    value_a: ExtractedValue | None = Field(
        None, alias="valueA", description="Extracted value from statement A"
    )
    value_b: ExtractedValue | None = Field(
        None, alias="valueB", description="Extracted value from statement B"
    )


class ClassifiedContradiction(BaseModel):
    """A contradiction with classification metadata.

    Story 5-3: Extends StatementPairComparison with classification details
    for attorney prioritization.

    Contains:
    - Reference to the original comparison
    - Contradiction type classification
    - Structured extracted values for display
    - Enhanced explanation for semantic conflicts
    """

    model_config = ConfigDict(populate_by_name=True)

    comparison_id: str = Field(
        ...,
        alias="comparisonId",
        description="Reference to the original StatementPairComparison (statement_a_id + statement_b_id)",
    )
    statement_a_id: str = Field(
        ..., alias="statementAId", description="UUID of first statement (chunk_id)"
    )
    statement_b_id: str = Field(
        ..., alias="statementBId", description="UUID of second statement (chunk_id)"
    )
    contradiction_type: ContradictionType = Field(
        ..., alias="contradictionType", description="Classification of contradiction"
    )
    extracted_values: ExtractedValues | None = Field(
        None,
        alias="extractedValues",
        description="Structured values for date/amount display",
    )
    explanation: str = Field(
        ..., description="Explanation of the conflict (enhanced for semantic)"
    )
    classification_method: str = Field(
        default="rule_based",
        alias="classificationMethod",
        description="How classification was determined: rule_based or llm_fallback",
    )


class ClassificationResult(BaseModel):
    """API response model for classification operation.

    Story 5-3: Contains classification results with metadata.
    """

    model_config = ConfigDict(populate_by_name=True)

    classified_contradiction: ClassifiedContradiction = Field(
        ..., alias="classifiedContradiction", description="The classified contradiction"
    )
    llm_cost_usd: float = Field(
        default=0.0,
        alias="llmCostUsd",
        ge=0.0,
        description="LLM API cost if fallback was used (0 for rule-based)",
    )
    processing_time_ms: int = Field(
        ..., alias="processingTimeMs", ge=0, description="Processing time in milliseconds"
    )
