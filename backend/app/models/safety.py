"""Safety models for query guardrails and language policing.

Story 8-1: Regex Pattern Detection Guardrails
Story 8-2: GPT-4o-mini Subtle Violation Detection
Story 8-3: Language Policing Output Sanitization

These models define the structure of guardrail check results,
violation types, and language policing results. Part of the Safety Layer (Epic 8).

Query Guardrails block dangerous queries before LLM processing:
- Legal advice requests (regex - Story 8-1)
- Outcome predictions (regex - Story 8-1)
- Liability conclusions (regex - Story 8-1)
- Procedural recommendations (regex - Story 8-1)
- Implicit conclusion requests (LLM - Story 8-2)
- Indirect outcome seeking (LLM - Story 8-2)
- Hypothetical legal advice (LLM - Story 8-2)

Language Policing sanitizes LLM outputs before user display:
- Regex replacements for legal conclusions (Story 8-3)
- LLM polishing for subtle conclusions (Story 8-3)
- Quote preservation for direct document quotes (Story 8-3)
"""

from typing import Literal

from pydantic import BaseModel, Field  # noqa: I001

# =============================================================================
# Story 8-1: Violation Type (AC #4)
# =============================================================================

# Violation types for guardrail checks (Story 8-1: Task 1.2, Story 8-2: Task 1.2-1.3)
#
# Design Note:
#   Using Literal instead of Enum for:
#   1. Performance: Direct string comparison without enum overhead
#   2. Simplicity: No import gymnastics for string values
#   3. Pydantic v2: Native Literal support with automatic validation
ViolationType = Literal[
    # Story 8-1: Regex-detected violations (fast-path)
    "legal_advice_request",  # "Should I file an appeal?"
    "outcome_prediction",  # "Will the judge rule in my favor?"
    "liability_conclusion",  # "Is the defendant guilty?"
    "procedural_recommendation",  # "Should we appeal?"
    # Story 8-2: LLM-detected subtle violations (second-pass)
    "implicit_conclusion_request",  # "Based on this evidence, is it clear that..."
    "indirect_outcome_seeking",  # "Would you say the defendant is..."
    "hypothetical_legal_advice",  # "If I were to argue that..."
]


# =============================================================================
# Story 8-1: GuardrailCheck Model (AC #4)
# =============================================================================


class GuardrailCheck(BaseModel):
    """Result of query guardrail check.

    Story 8-1: AC #4 - Response includes is_safe, violation_type,
    explanation, suggested_rewrite.

    This is returned by GuardrailService.check_query() for every query.
    If is_safe=False, the query should be blocked before LLM processing.
    """

    is_safe: bool = Field(
        description="True if query passes guardrail check and can proceed to LLM",
    )
    violation_type: ViolationType | None = Field(
        default=None,
        description="Type of violation detected (if blocked)",
    )
    pattern_matched: str | None = Field(
        default=None,
        description="Pattern ID that matched (for debugging/audit)",
    )
    explanation: str = Field(
        default="",
        description="User-friendly explanation of why query was blocked",
    )
    suggested_rewrite: str = Field(
        default="",
        description="Suggested safe alternative query",
    )
    check_time_ms: float = Field(
        default=0.0,
        ge=0,
        description="Time taken for guardrail check in milliseconds",
    )


# =============================================================================
# Story 8-1: GuardrailPattern Model (AC #1-3)
# =============================================================================


class GuardrailPattern(BaseModel):
    """Configuration for a single guardrail pattern.

    Story 8-1: Task 1.3 - Pattern definition with metadata.

    Used by the pattern registry to define patterns and their
    associated violation types, explanations, and rewrite templates.
    """

    pattern_id: str = Field(
        description="Unique identifier for this pattern (e.g., 'legal_advice_should_i')",
    )
    pattern: str = Field(
        description="Regex pattern string (will be compiled at registration)",
    )
    violation_type: ViolationType = Field(
        description="Type of violation this pattern detects",
    )
    explanation_template: str = Field(
        description="Template for user-facing explanation when pattern matches",
    )
    rewrite_template: str = Field(
        description="Template for suggested safe alternative query",
    )


# =============================================================================
# Story 8-2: SubtleViolationCheck Model (AC #1-4)
# =============================================================================


class SubtleViolationCheck(BaseModel):
    """Result of GPT-4o-mini subtle violation detection.

    Story 8-2: AC #1-4 - LLM-based detection result.

    This is returned by SubtleViolationDetector.detect_violation() for queries
    that pass the fast-path regex check but may contain subtle violations.

    Example:
        >>> check = SubtleViolationCheck(
        ...     is_safe=False,
        ...     violation_detected=True,
        ...     violation_type="implicit_conclusion_request",
        ...     explanation="Query seeks implicit legal conclusion about liability",
        ...     suggested_rewrite="What evidence exists regarding the contract terms?",
        ...     confidence=0.92,
        ...     llm_cost_usd=0.0003,
        ...     check_time_ms=450.5,
        ... )
    """

    is_safe: bool = Field(
        description="True if query passes LLM safety check",
    )
    violation_detected: bool = Field(
        default=False,
        description="True if subtle violation was detected",
    )
    violation_type: ViolationType | None = Field(
        default=None,
        description="Type of subtle violation detected (if blocked)",
    )
    explanation: str = Field(
        default="",
        description="LLM explanation for why query was blocked or allowed",
    )
    suggested_rewrite: str = Field(
        default="",
        description="Contextual safe alternative query (AC #3)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="LLM confidence in detection (0.0-1.0)",
    )
    llm_cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost of this LLM call in USD",
    )
    check_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time taken for LLM check in milliseconds",
    )


# =============================================================================
# Story 8-2: SafetyCheckResult Model (Task 1.4)
# =============================================================================


class SafetyCheckResult(BaseModel):
    """Combined result from regex + LLM safety checks.

    Story 8-2: Task 1.4 - Two-phase safety pipeline result.

    This is the final result returned by SafetyGuard.check_query().
    It combines results from both the fast-path regex check (Story 8-1)
    and the LLM-based subtle detection (Story 8-2).

    Pipeline:
    1. Regex check (< 5ms) - blocks obvious violations
    2. LLM check (~500-2000ms) - catches subtle violations (if regex passes)

    Example:
        >>> result = SafetyCheckResult(
        ...     is_safe=False,
        ...     blocked_by="llm",
        ...     violation_type="implicit_conclusion_request",
        ...     explanation="This query implicitly seeks a legal conclusion...",
        ...     suggested_rewrite="What facts are documented about...",
        ...     regex_check_ms=2.5,
        ...     llm_check_ms=850.3,
        ...     llm_cost_usd=0.0003,
        ... )
    """

    is_safe: bool = Field(
        description="True if query passes ALL safety checks",
    )
    blocked_by: Literal["regex", "llm"] | None = Field(
        default=None,
        description="Which phase blocked the query (if blocked)",
    )
    violation_type: ViolationType | None = Field(
        default=None,
        description="Type of violation detected (if blocked)",
    )
    explanation: str = Field(
        default="",
        description="User-friendly explanation (if blocked)",
    )
    suggested_rewrite: str = Field(
        default="",
        description="Safe alternative query suggestion",
    )
    regex_check_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time for regex check (always runs)",
    )
    llm_check_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time for LLM check (if regex passed)",
    )
    llm_cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost of LLM call in USD",
    )
    llm_check_failed: bool = Field(
        default=False,
        description="True if LLM check failed (query allowed anyway - fail open)",
    )


# =============================================================================
# Story 8-3: Language Policing Models (AC #1-6)
# =============================================================================


class ReplacementRecord(BaseModel):
    """Record of a single regex replacement during language policing.

    Story 8-3: Task 1.2 - Track each replacement for audit trail.

    Each replacement made during the sanitization process is recorded
    with its original text, replacement text, position, and the rule
    that triggered it.

    Example:
        >>> record = ReplacementRecord(
        ...     original_phrase="violated Section 138",
        ...     replacement_phrase="affected by Section 138",
        ...     position_start=25,
        ...     position_end=46,
        ...     rule_id="conclusion_violated_section",
        ... )
    """

    original_phrase: str = Field(
        description="The original text that was replaced",
    )
    replacement_phrase: str = Field(
        description="The replacement text that was inserted",
    )
    position_start: int = Field(
        ge=0,
        description="Start position of the replacement in the original text",
    )
    position_end: int = Field(
        ge=0,
        description="End position of the replacement in the original text",
    )
    rule_id: str = Field(
        description="Identifier of the pattern rule that triggered this replacement",
    )


class QuotePreservation(BaseModel):
    """Record of a preserved quote that was protected from sanitization.

    Story 8-3: Task 1.3, AC #6 - Track preserved direct quotes.

    Direct quotes from source documents must be preserved verbatim
    during language policing. This model records what was preserved
    and its source attribution.

    Example:
        >>> preservation = QuotePreservation(
        ...     quoted_text='"The defendant violated the agreement"',
        ...     source_document="Exhibit A",
        ...     page_number=5,
        ...     start_pos=100,
        ...     end_pos=145,
        ...     attribution_note="Direct quote from [Exhibit A, p. 5]",
        ... )
    """

    quoted_text: str = Field(
        description="The preserved quoted text including quotation marks",
    )
    source_document: str | None = Field(
        default=None,
        description="Document name if citation reference was detected",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="Page number if citation reference was detected",
    )
    start_pos: int = Field(
        ge=0,
        description="Start position of the quote in the ORIGINAL text",
    )
    end_pos: int = Field(
        ge=0,
        description="End position of the quote in the ORIGINAL text",
    )
    attribution_note: str = Field(
        default="Direct quote preserved verbatim",
        description="AC #6: Attribution note like 'Direct quote from [document name, page X]'",
    )


class LanguagePolicingResult(BaseModel):
    """Result of language policing on LLM output.

    Story 8-3: Task 1.1, AC #1-6 - Complete policing result.

    This is the final result returned by the language policing pipeline.
    It combines regex-based replacements (Phase 1) and optional LLM-based
    polishing (Phase 2) into a single sanitized output.

    Pipeline:
    1. Quote detection and protection (AC #6)
    2. Regex replacements for obvious conclusions (AC #1-4)
    3. LLM polish for subtle conclusions (AC #5)

    Example:
        >>> result = LanguagePolicingResult(
        ...     original_text="The evidence proves defendant violated Section 138.",
        ...     sanitized_text="The evidence suggests defendant affected by Section 138.",
        ...     replacements_made=[...],
        ...     quotes_preserved=[],
        ...     llm_policing_applied=False,
        ...     sanitization_time_ms=2.5,
        ... )
    """

    original_text: str = Field(
        description="The original unsanitized text",
    )
    sanitized_text: str = Field(
        description="The sanitized text with legal conclusions removed/replaced",
    )
    replacements_made: list[ReplacementRecord] = Field(
        default_factory=list,
        description="List of all replacements made during sanitization",
    )
    quotes_preserved: list[QuotePreservation] = Field(
        default_factory=list,
        description="List of direct quotes that were protected from sanitization",
    )
    llm_policing_applied: bool = Field(
        default=False,
        description="True if LLM-based subtle policing was applied",
    )
    sanitization_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total time for sanitization in milliseconds",
    )
    llm_cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost of LLM policing call in USD (if applied)",
    )
    text_truncated: bool = Field(
        default=False,
        description="M1 fix: True if text was truncated before LLM policing (>8000 chars)",
    )
    original_length: int = Field(
        default=0,
        ge=0,
        description="Original text length (useful when text_truncated=True)",
    )
