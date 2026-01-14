"""Safety models for query guardrails.

Story 8-1: Regex Pattern Detection Guardrails

These models define the structure of guardrail check results
and violation types. Part of the Safety Layer (Epic 8).

Query Guardrails (this module) block dangerous queries before LLM processing:
- Legal advice requests
- Outcome predictions
- Liability conclusions
- Procedural recommendations
"""

from typing import Literal

from pydantic import BaseModel, Field  # noqa: I001


# =============================================================================
# Story 8-1: Violation Type (AC #4)
# =============================================================================

# Violation types for guardrail checks (Story 8-1: Task 1.2)
#
# Design Note:
#   Using Literal instead of Enum for:
#   1. Performance: Direct string comparison without enum overhead
#   2. Simplicity: No import gymnastics for string values
#   3. Pydantic v2: Native Literal support with automatic validation
ViolationType = Literal[
    "legal_advice_request",  # "Should I file an appeal?"
    "outcome_prediction",  # "Will the judge rule in my favor?"
    "liability_conclusion",  # "Is the defendant guilty?"
    "procedural_recommendation",  # "Should we appeal?"
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
