"""Pattern-based OCR correction for common errors.

Implements deterministic regex-based corrections for common OCR mistakes
like O/0 confusion, l/1 confusion, and date/currency format errors.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

import structlog

from app.models.ocr_validation import (
    CorrectionType,
    LowConfidenceWord,
    ValidationResult,
)

logger = structlog.get_logger(__name__)


@dataclass
class PatternRule:
    """A pattern correction rule."""

    name: str
    pattern: str
    replacement: str
    description: str


# Common OCR error patterns for legal documents
# Order matters: more specific patterns should come first
COMMON_OCR_PATTERNS: list[PatternRule] = [
    # Letter O vs Zero in numbers (most common OCR error)
    # Handle Indian number format with commas (e.g., 1O,OOO -> 10,000)
    PatternRule(
        name="digit_comma_ooo",
        pattern=r"(\d),OOO",
        replacement=r"\g<1>,000",
        description="OOO confused with 000 in Indian format",
    ),
    PatternRule(
        name="digit_comma_oo",
        pattern=r"(\d),OO",
        replacement=r"\g<1>,00",
        description="OO confused with 00 in Indian format",
    ),
    PatternRule(
        name="digit_o_middle",
        pattern=r"(\d+)O(\d+)",
        replacement=r"\g<1>0\g<2>",
        description="O confused with 0 in number",
    ),
    PatternRule(
        name="digit_o_start",
        pattern=r"^O(\d)",
        replacement=r"0\g<1>",
        description="O confused with 0 at start",
    ),
    PatternRule(
        name="digit_o_end",
        pattern=r"(\d)O$",
        replacement=r"\g<1>0",
        description="O confused with 0 at end",
    ),
    PatternRule(
        name="digit_o_surrounded",
        pattern=r"(\d)O",
        replacement=r"\g<1>0",
        description="O confused with 0 after digit",
    ),
    PatternRule(
        name="o_before_digit",
        pattern=r"O(\d)",
        replacement=r"0\g<1>",
        description="O confused with 0 before digit",
    ),

    # Letter l vs digit 1 in numeric contexts
    PatternRule(
        name="digit_l_middle",
        pattern=r"(\d)l(\d)",
        replacement=r"\g<1>1\g<2>",
        description="l confused with 1 in number",
    ),
    PatternRule(
        name="l_after_digit",
        pattern=r"(\d)l",
        replacement=r"\g<1>1",
        description="l confused with 1 after digit",
    ),

    # Letter I vs digit 1 in numeric contexts
    PatternRule(
        name="digit_I_middle",
        pattern=r"(\d)I(\d)",
        replacement=r"\g<1>1\g<2>",
        description="I confused with 1 in number",
    ),

    # S vs 5 in amounts
    PatternRule(
        name="rs_s_amount",
        pattern=r"Rs\.\s*S(\d)",
        replacement=r"Rs. 5\g<1>",
        description="S confused with 5 in currency",
    ),

    # B vs 8 in numeric contexts
    PatternRule(
        name="digit_B_number",
        pattern=r"(\d)B(\d)",
        replacement=r"\g<1>8\g<2>",
        description="B confused with 8 in number",
    ),

    # Date format corrections (DD/MM/YYYY with O instead of 0)
    PatternRule(
        name="date_o_day",
        pattern=r"^O(\d)[/\-]",
        replacement=r"0\g<1>/",
        description="O confused with 0 in day",
    ),
    PatternRule(
        name="date_o_month",
        pattern=r"[/\-]O(\d)[/\-]",
        replacement=r"/0\g<1>/",
        description="O confused with 0 in month",
    ),
    PatternRule(
        name="date_full_o_fix",
        pattern=r"(\d{1,2})[/\-]O(\d)",
        replacement=r"\g<1>/0\g<2>",
        description="O confused with 0 in date",
    ),

    # Indian currency patterns
    PatternRule(
        name="rs_l_amount",
        pattern=r"Rs\.\s*l(\d)",
        replacement=r"Rs. 1\g<1>",
        description="l confused with 1 in currency",
    ),
    PatternRule(
        name="rs_I_amount",
        pattern=r"Rs\.\s*I(\d)",
        replacement=r"Rs. 1\g<1>",
        description="I confused with 1 in currency",
    ),

    # Section reference patterns
    PatternRule(
        name="section_o_paren",
        pattern=r"Section\s+(\d+)\s*O\s*\)",
        replacement=r"Section \g<1>()",
        description="O confused with () in section",
    ),
]

# Patterns for identifying critical content types
CRITICAL_CONTENT_PATTERNS = {
    "date": re.compile(r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}"),
    "amount": re.compile(r"Rs\.?\s*[\d,lIO]+"),
    "section": re.compile(r"Section\s+\d+"),
    "year": re.compile(r"(19|20)\d{2}"),
}


class PatternCorrector:
    """Service for pattern-based OCR correction.

    Applies deterministic regex corrections for common OCR errors.
    Pattern corrections are applied before Gemini validation to reduce
    API costs and improve accuracy.
    """

    def __init__(self) -> None:
        """Initialize pattern corrector with compiled patterns."""
        self.patterns = [
            (re.compile(rule.pattern), rule.replacement, rule.name, rule.description)
            for rule in COMMON_OCR_PATTERNS
        ]

    def correct(self, text: str) -> ValidationResult | None:
        """Apply pattern corrections to text.

        Applies patterns iteratively until no more changes occur,
        to handle chained corrections (e.g., 1O,OOO -> 10,000).

        Args:
            text: Text to correct.

        Returns:
            ValidationResult if correction was applied, None otherwise.
        """
        if not text:
            return None

        corrected = text
        applied_rules: list[str] = []
        max_iterations = 10  # Safety limit to prevent infinite loops

        for _ in range(max_iterations):
            changed = False
            for pattern, replacement, _name, description in self.patterns:
                new_text = pattern.sub(replacement, corrected)
                if new_text != corrected:
                    if description not in applied_rules:
                        applied_rules.append(description)
                    corrected = new_text
                    changed = True

            if not changed:
                break

        if corrected == text:
            return None

        # Return result with high confidence since pattern corrections are deterministic
        return ValidationResult(
            bbox_id="",  # Will be filled by caller
            original=text,
            corrected=corrected,
            old_confidence=0.0,  # Will be filled by caller
            new_confidence=0.95,  # High confidence for pattern corrections
            correction_type=CorrectionType.PATTERN,
            reasoning="; ".join(applied_rules),
            was_corrected=True,
        )

    def correct_word(self, word: LowConfidenceWord) -> ValidationResult:
        """Apply pattern corrections to a low-confidence word.

        Args:
            word: LowConfidenceWord to correct.

        Returns:
            ValidationResult with correction details.
        """
        result = self.correct(word.text)

        if result is None:
            # No pattern correction applied
            return ValidationResult(
                bbox_id=word.bbox_id,
                original=word.text,
                corrected=word.text,
                old_confidence=word.confidence,
                new_confidence=word.confidence,
                correction_type=None,
                reasoning=None,
                was_corrected=False,
            )

        # Fill in the word-specific fields
        result.bbox_id = word.bbox_id
        result.old_confidence = word.confidence
        return result

    def is_critical_content(self, text: str) -> str | None:
        """Check if text contains critical content patterns.

        Critical content (dates, amounts, sections) should be prioritized
        for validation.

        Args:
            text: Text to check.

        Returns:
            Content type if critical, None otherwise.
        """
        for content_type, pattern in CRITICAL_CONTENT_PATTERNS.items():
            if pattern.search(text):
                return content_type
        return None


def apply_pattern_corrections(
    words: list[LowConfidenceWord],
) -> tuple[list[ValidationResult], list[LowConfidenceWord]]:
    """Apply pattern corrections to a list of words.

    Separates words into those corrected by patterns and those
    still needing Gemini validation.

    Args:
        words: List of low-confidence words.

    Returns:
        Tuple of (corrected_results, remaining_words).
        corrected_results: Words fixed by pattern correction.
        remaining_words: Words still needing Gemini validation.
    """
    corrector = PatternCorrector()
    corrected: list[ValidationResult] = []
    remaining: list[LowConfidenceWord] = []

    for word in words:
        result = corrector.correct_word(word)

        if result.was_corrected:
            corrected.append(result)
            logger.debug(
                "pattern_correction_applied",
                original=result.original,
                corrected=result.corrected,
                reasoning=result.reasoning,
            )
        else:
            remaining.append(word)

    logger.info(
        "pattern_corrections_complete",
        total_words=len(words),
        corrected=len(corrected),
        remaining=len(remaining),
    )

    return corrected, remaining


@lru_cache(maxsize=1)
def get_pattern_corrector() -> PatternCorrector:
    """Get singleton pattern corrector instance.

    Uses lru_cache to maintain consistent factory pattern with other
    OCR validation services (gemini_validator, human_review_service,
    validation_extractor).

    Returns:
        PatternCorrector instance.
    """
    return PatternCorrector()
