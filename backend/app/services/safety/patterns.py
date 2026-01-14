"""Pattern registry for query guardrails.

Story 8-1: Regex Pattern Detection Guardrails (AC #1-3)

Contains pre-compiled regex patterns for detecting dangerous queries:
- Legal advice requests (AC #1): "Should I file an appeal?"
- Outcome predictions (AC #2): "Will the judge rule in my favor?"
- Probability/chances (AC #3): "What are my chances of winning?"
- Liability conclusions: "Is the defendant guilty?"

Design Philosophy:
- Conservative: Block obvious requests, allow borderline cases
- Fast: Pre-compiled regex, no external calls
- Explainable: Each block includes clear user explanation
- Recoverable: Suggest safe rewrite for blocked queries
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from re import Pattern

    from app.models.safety import ViolationType


# =============================================================================
# Story 8-1: Compiled Pattern Dataclass
# =============================================================================


@dataclass
class CompiledPattern:
    """Compiled regex pattern with metadata.

    Story 8-1: Task 2.1 - Pattern registry entry.
    """

    pattern_id: str
    regex: Pattern[str]
    violation_type: str  # ViolationType literal
    explanation_template: str
    rewrite_template: str

    def get_explanation(self, query: str) -> str:  # noqa: ARG002
        """Generate user-friendly explanation for blocked query.

        Story 8-1: Task 3.3 - Explanation generation.

        Args:
            query: The blocked query (unused, but available for future templating).

        Returns:
            Explanation string for the user.

        """
        return self.explanation_template

    def get_rewrite(self, query: str) -> str:  # noqa: ARG002
        """Generate suggested rewrite for blocked query.

        Story 8-1: Task 3.4 - Rewrite suggestion.

        Args:
            query: The blocked query (unused, but available for future templating).

        Returns:
            Suggested safe alternative query.

        """
        return self.rewrite_template


# =============================================================================
# Story 8-1: Explanation Templates (Task 2.7)
# =============================================================================

EXPLANATION_TEMPLATES: dict[str, str] = {
    "legal_advice_request": (
        "This query appears to request legal advice about what action to take. "
        "LDIP analyzes documents and extracts facts - it cannot provide "
        "legal recommendations. Try asking about the facts or documents instead."
    ),
    "outcome_prediction": (
        "This query asks for a prediction about how a court will rule or your "
        "chances of success. LDIP cannot predict judicial outcomes. "
        "Try asking about relevant precedents or document contents instead."
    ),
    "liability_conclusion": (
        "This query asks for a conclusion about liability or guilt. "
        "LDIP identifies factual observations - only attorneys can draw "
        "legal conclusions. Try asking what the documents say about the events."
    ),
    "procedural_recommendation": (
        "This query asks what procedural step to take next. "
        "LDIP cannot recommend legal procedures. "
        "Try asking about deadlines or requirements mentioned in the documents."
    ),
}

REWRITE_TEMPLATES: dict[str, str] = {
    "legal_advice_request": "What do the documents say about [topic]?",
    "outcome_prediction": "What precedents or rulings are cited in the documents?",
    "liability_conclusion": "What evidence is mentioned regarding [party]'s actions?",
    "procedural_recommendation": "What procedural requirements are mentioned?",
}


# =============================================================================
# Story 8-1: Pattern Definitions (Tasks 2.2-2.6)
# =============================================================================

# Category 1: Direct Legal Advice Requests (AC #1, Task 2.2)
LEGAL_ADVICE_PATTERNS: list[tuple[str, str]] = [
    (
        "legal_advice_should_i",
        r"should\s+(i|we|the\s+client|my\s+client)\s+(file|appeal|settle|sue|proceed|respond|submit)",
    ),
    (
        "legal_advice_recommend",
        r"do\s+you\s+(recommend|advise|suggest)\s+(filing|appealing|settling|suing|proceeding)",
    ),
    (
        "legal_advice_what_should",
        r"what\s+should\s+(i|we)\s+do\s+(next|now|about)",
    ),
]

# Category 2: Outcome Predictions (AC #2, Task 2.3)
OUTCOME_PREDICTION_PATTERNS: list[tuple[str, str]] = [
    (
        "outcome_will_judge",
        r"will\s+(the\s+)?(judge|court|tribunal|bench)\s+(rule|decide|hold|find|grant|deny|dismiss)",
    ),
    (
        "outcome_what_will",
        r"(what|how)\s+will\s+(the\s+)?(judge|court)\s+(rule|decide)",
    ),
    (
        "outcome_court_likely",
        r"is\s+the\s+court\s+(likely|going)\s+to",
    ),
]

# Category 3: Probability/Chances (AC #3, Task 2.4)
CHANCES_PATTERNS: list[tuple[str, str]] = [
    (
        "chances_what_are",
        r"what\s+are\s+(my|our|the|client'?s?)\s+chances",
    ),
    (
        "chances_likelihood",
        r"(what|how\s+high)\s+is\s+the\s+(likelihood|probability|chance)\s+of",
    ),
    (
        "chances_will_win",
        r"(will|can)\s+(i|we|they)\s+(win|succeed|prevail)",
    ),
]

# Category 4: Liability Conclusions (Task 2.5)
LIABILITY_PATTERNS: list[tuple[str, str]] = [
    (
        "liability_is_party",
        r"is\s+(the\s+)?(defendant|plaintiff|accused|client)\s+(guilty|liable|responsible|at\s+fault)",
    ),
    (
        "liability_did_party",
        r"(did|has)\s+(the\s+)?(defendant|plaintiff)\s+(violate|breach|commit)",
    ),
]

# Category 5: Procedural Recommendations (Task 2.6)
PROCEDURAL_PATTERNS: list[tuple[str, str]] = [
    (
        "procedural_should_we",
        r"should\s+we\s+(appeal|file|submit|respond|withdraw)",
    ),
]


# =============================================================================
# Story 8-1: Pattern Registry Builder
# =============================================================================


def _build_patterns() -> list[CompiledPattern]:
    """Build list of compiled patterns.

    Story 8-1: Task 2.1 - Compile all patterns at module load.

    Returns:
        List of CompiledPattern objects ready for matching.

    """
    patterns: list[CompiledPattern] = []

    # Build pattern definitions with their violation types
    pattern_definitions: list[tuple[list[tuple[str, str]], str]] = [
        (LEGAL_ADVICE_PATTERNS, "legal_advice_request"),
        (OUTCOME_PREDICTION_PATTERNS, "outcome_prediction"),
        (CHANCES_PATTERNS, "outcome_prediction"),  # Chances = outcome prediction
        (LIABILITY_PATTERNS, "liability_conclusion"),
        (PROCEDURAL_PATTERNS, "procedural_recommendation"),
    ]

    for pattern_list, violation_type in pattern_definitions:
        for pattern_id, pattern_str in pattern_list:
            compiled = CompiledPattern(
                pattern_id=pattern_id,
                regex=re.compile(pattern_str, re.IGNORECASE),
                violation_type=violation_type,
                explanation_template=EXPLANATION_TEMPLATES[violation_type],
                rewrite_template=REWRITE_TEMPLATES[violation_type],
            )
            patterns.append(compiled)

    return patterns


# Pre-compile patterns at module load (Story 8-1: AC #6 - < 5ms check time)
COMPILED_PATTERNS: list[CompiledPattern] = _build_patterns()


def get_patterns() -> list[CompiledPattern]:
    """Get all compiled guardrail patterns.

    Story 8-1: Task 2.1 - Pattern registry accessor.

    Returns:
        List of all compiled patterns for guardrail checking.

    """
    return COMPILED_PATTERNS
