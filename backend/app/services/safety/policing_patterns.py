"""Regex patterns for language policing output sanitization.

Story 8-3: Language Policing (AC #1-4)

Contains pre-compiled regex patterns for sanitizing LLM outputs:
- Legal conclusions (AC #1): "violated Section X" → "affected by Section X"
- Guilt patterns (AC #2): "defendant is guilty" → "defendant's liability regarding"
- Prediction patterns (AC #3): "the court will rule" → "the court may consider"
- Proof patterns (AC #4): "proves that" → "suggests that"
- Definitive patterns: "clearly shows" → "appears to show"
- Liability patterns: "is liable for" → "regarding potential liability for"

Design Philosophy:
- Transform: Replace definitive language with tentative language
- Preserve meaning: Keep the factual content, remove legal conclusions
- Fast: Pre-compiled regex, < 5ms performance target
- Traceable: Each replacement has a unique rule_id for audit
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from re import Pattern


# =============================================================================
# Story 8-3: Compiled Policing Pattern Dataclass
# =============================================================================


@dataclass
class CompiledPolicingPattern:
    """Compiled regex pattern for output sanitization.

    Story 8-3: Task 2.8 - Pattern with metadata for audit.
    """

    rule_id: str
    regex: Pattern[str]
    replacement: str
    explanation: str


# =============================================================================
# Story 8-3: Category 1 - Legal Conclusion Patterns (AC #1, Task 2.2-2.3)
# =============================================================================

CONCLUSION_PATTERNS: list[tuple[str, str, str, str]] = [
    # "violated Section X" → "affected by Section X"
    (
        "conclusion_violated_section",
        r"violated\s+(section|act|rule|regulation|clause)\s+(\d+[A-Za-z]*)",
        r"affected by \1 \2",
        "Replaces definitive 'violated' with neutral 'affected by'",
    ),
    # "breached the contract" → "regarding the contract terms"
    (
        "conclusion_breached_contract",
        r"breached\s+(the\s+)?(contract|agreement|terms)",
        r"regarding \1\2 terms",
        "Replaces definitive 'breached' with neutral 'regarding'",
    ),
    # "violated the agreement" → "regarding the agreement terms"
    (
        "conclusion_violated_agreement",
        r"violated\s+(the\s+)?(agreement|contract|terms)",
        r"regarding \1\2 terms",
        "Replaces definitive 'violated' with neutral 'regarding'",
    ),
]


# =============================================================================
# Story 8-3: Category 2 - Guilt/Liability Patterns (AC #2, Task 2.3)
# =============================================================================

GUILT_PATTERNS: list[tuple[str, str, str, str]] = [
    # "defendant is guilty" → "defendant's liability regarding"
    (
        "guilt_defendant_guilty",
        r"(defendant|accused|respondent)\s+is\s+guilty(\s+of)?",
        r"\1's liability regarding",
        "Replaces guilt conclusion with liability observation",
    ),
    # "plaintiff is entitled" → "plaintiff's potential entitlement"
    (
        "guilt_plaintiff_entitled",
        r"(plaintiff|petitioner|claimant)\s+is\s+entitled(\s+to)?",
        r"\1's potential entitlement to",
        "Replaces entitlement conclusion with potential entitlement",
    ),
    # "party is at fault" → "party's potential responsibility"
    (
        "guilt_party_fault",
        r"(defendant|plaintiff|party|accused)\s+is\s+at\s+fault",
        r"\1's potential responsibility",
        "Replaces fault conclusion with responsibility observation",
    ),
]


# =============================================================================
# Story 8-3: Category 3 - Prediction Patterns (AC #3, Task 2.4)
# =============================================================================

PREDICTION_PATTERNS: list[tuple[str, str, str, str]] = [
    # "the court will rule/decide/hold" → "the court may consider"
    (
        "prediction_court_will",
        r"(the\s+)?court\s+will\s+(rule|decide|hold|find|grant|deny|dismiss)",
        r"\1court may consider",
        "Replaces court prediction with consideration observation",
    ),
    # "judge will likely" → "judge may"
    (
        "prediction_judge_likely",
        r"(the\s+)?judge\s+will\s+(likely\s+)?(rule|decide|find|hold|grant|deny)",
        r"\1judge may",
        "Replaces judge prediction with possibility",
    ),
    # "tribunal will" → "tribunal may"
    (
        "prediction_tribunal_will",
        r"(the\s+)?tribunal\s+will\s+(rule|decide|hold|find|grant|deny)",
        r"\1tribunal may consider",
        "Replaces tribunal prediction with consideration",
    ),
]


# =============================================================================
# Story 8-3: Category 4 - Proof/Evidence Patterns (AC #4, Task 2.5)
# =============================================================================

PROOF_PATTERNS: list[tuple[str, str, str, str]] = [
    # "proves that" → "suggests that"
    (
        "proof_proves_that",
        r"proves\s+that",
        r"suggests that",
        "Replaces 'proves' with 'suggests'",
    ),
    # "establishes that" → "indicates that"
    (
        "proof_establishes_that",
        r"establishes\s+that",
        r"indicates that",
        "Replaces 'establishes' with 'indicates'",
    ),
    # "demonstrates that" → "may indicate that"
    (
        "proof_demonstrates_that",
        r"demonstrates\s+that",
        r"may indicate that",
        "Replaces 'demonstrates' with 'may indicate'",
    ),
    # "clearly shows" → "appears to show"
    (
        "proof_clearly_shows",
        r"clearly\s+shows",
        r"appears to show",
        "Replaces 'clearly shows' with 'appears to show'",
    ),
    # "conclusively demonstrates" → "may suggest"
    (
        "proof_conclusively_demonstrates",
        r"conclusively\s+(demonstrates|shows|proves)",
        r"may suggest",
        "Replaces conclusive language with tentative",
    ),
]


# =============================================================================
# Story 8-3: Category 5 - Definitive Statement Patterns (Task 2.6)
# =============================================================================

DEFINITIVE_PATTERNS: list[tuple[str, str, str, str]] = [
    # "is liable for" → "regarding potential liability for"
    (
        "definitive_is_liable",
        r"is\s+liable\s+for",
        r"regarding potential liability for",
        "Replaces liability conclusion with observation",
    ),
    # "is responsible for" → "regarding responsibility for"
    (
        "definitive_is_responsible",
        r"is\s+responsible\s+for",
        r"regarding responsibility for",
        "Replaces responsibility conclusion with observation",
    ),
    # "must pay" → "may be required to pay"
    (
        "definitive_must_pay",
        r"must\s+pay",
        r"may be required to pay",
        "Replaces mandatory payment with potential requirement",
    ),
    # "is obligated to" → "may have obligations regarding"
    (
        "definitive_is_obligated",
        r"is\s+obligated\s+to",
        r"may have obligations regarding",
        "Replaces obligation conclusion with potential",
    ),
    # "is bound by" → "may be subject to"
    (
        "definitive_is_bound",
        r"is\s+bound\s+by",
        r"may be subject to",
        "Replaces binding conclusion with potential",
    ),
]


# =============================================================================
# Story 8-3: Category 6 - Additional Liability Patterns (Task 2.7)
# =============================================================================

LIABILITY_PATTERNS: list[tuple[str, str, str, str]] = [
    # "owes damages" → "regarding potential damages"
    (
        "liability_owes_damages",
        r"owes\s+(damages|compensation|payment)",
        r"regarding potential \1",
        "Replaces damages conclusion with observation",
    ),
    # "is negligent" → "regarding potential negligence"
    (
        "liability_is_negligent",
        r"is\s+negligent",
        r"regarding potential negligence",
        "Replaces negligence conclusion with observation",
    ),
    # "committed fraud" → "regarding potential fraud"
    (
        "liability_committed_fraud",
        r"committed\s+(fraud|breach|misconduct|negligence)",
        r"regarding potential \1",
        "Replaces misconduct conclusion with observation",
    ),
    # "in breach of" → "regarding compliance with"
    (
        "liability_in_breach",
        r"in\s+breach\s+of",
        r"regarding compliance with",
        "Replaces breach conclusion with compliance observation",
    ),
]


# =============================================================================
# Story 8-3: Pattern Registry Builder
# =============================================================================


def _build_policing_patterns() -> list[CompiledPolicingPattern]:
    """Build list of compiled policing patterns.

    Story 8-3: Task 2.1 - Compile all patterns at module load.

    Returns:
        List of CompiledPolicingPattern objects ready for matching.
    """
    patterns: list[CompiledPolicingPattern] = []

    # All pattern categories
    all_pattern_groups = [
        CONCLUSION_PATTERNS,
        GUILT_PATTERNS,
        PREDICTION_PATTERNS,
        PROOF_PATTERNS,
        DEFINITIVE_PATTERNS,
        LIABILITY_PATTERNS,
    ]

    for pattern_group in all_pattern_groups:
        for rule_id, pattern_str, replacement, explanation in pattern_group:
            compiled = CompiledPolicingPattern(
                rule_id=rule_id,
                regex=re.compile(pattern_str, re.IGNORECASE),
                replacement=replacement,
                explanation=explanation,
            )
            patterns.append(compiled)

    return patterns


# Pre-compile patterns at module load (Story 8-3: Performance target < 5ms for regex policing)
COMPILED_POLICING_PATTERNS: list[CompiledPolicingPattern] = _build_policing_patterns()


def get_policing_patterns() -> list[CompiledPolicingPattern]:
    """Get all compiled language policing patterns.

    Story 8-3: Task 2.1 - Pattern registry accessor.

    Returns:
        List of all compiled patterns for language policing.
    """
    return COMPILED_POLICING_PATTERNS


def get_policing_pattern_count() -> int:
    """Get the total number of policing patterns.

    Returns:
        Number of patterns in the registry.
    """
    return len(COMPILED_POLICING_PATTERNS)
