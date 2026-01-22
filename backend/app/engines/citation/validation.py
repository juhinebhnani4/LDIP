"""Act Validation Service for automatic validation and garbage detection.

This module provides services for:
1. Detecting garbage act extractions (sentence fragments, etc.)
2. Validating act names against known acts
3. Caching validation results globally

Part of Act Validation and Auto-Fetching feature.
"""

import re
from dataclasses import dataclass
from enum import Enum

from app.core.config import get_settings
from app.core.data_loader import (
    get_garbage_patterns,
    get_generic_terms,
    get_valid_act_keywords,
    get_valid_act_suffixes,
)
from app.core.logging import get_logger
from app.engines.citation.abbreviations import (
    ACT_ABBREVIATIONS,
    clean_act_name,
    get_canonical_name,
    normalize_act_name,
)

logger = get_logger(__name__)


# =============================================================================
# Enums
# =============================================================================


class ValidationStatus(str, Enum):
    """Validation status for act names."""

    VALID = "valid"  # Confirmed valid Central Act
    INVALID = "invalid"  # Garbage extraction (sentence fragment, etc.)
    STATE_ACT = "state_act"  # Valid but a State Act (not on India Code)
    NOT_ON_INDIACODE = "not_on_indiacode"  # Valid but not available online
    UNKNOWN = "unknown"  # Not yet validated


class ValidationSource(str, Enum):
    """Source of validation result."""

    ABBREVIATIONS = "abbreviations"  # Matched in abbreviations.py
    INDIA_CODE = "india_code"  # Found on India Code
    GARBAGE_DETECTION = "garbage_detection"  # Detected as garbage
    MANUAL = "manual"  # Manual validation


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ActValidationResult:
    """Result of validating an act name."""

    act_name_original: str
    act_name_cleaned: str
    act_name_normalized: str
    act_name_canonical: str | None
    act_year: int | None
    validation_status: ValidationStatus
    validation_source: ValidationSource
    confidence: float  # 0.0 to 1.0
    garbage_patterns_matched: list[str]  # Patterns that triggered garbage detection
    is_known_act: bool  # Whether act is in abbreviations dictionary


# =============================================================================
# Validation Service
# =============================================================================


class ActValidationService:
    """Service for validating act names and detecting garbage extractions.

    This service provides:
    1. Garbage detection using heuristics
    2. Validation against known acts (abbreviations.py)
    3. Normalization and canonicalization of act names

    Configuration is loaded from settings (config.py).
    Patterns and rules are loaded from JSON data files.

    Example usage:
        service = ActValidationService()
        result = service.validate("the Torts Act. By not marking copies...")
        print(result.validation_status)  # ValidationStatus.INVALID
        print(result.garbage_patterns_matched)  # ['Period followed by capital']
    """

    def __init__(self):
        """Initialize the validation service."""
        self._known_act_names: set[str] = self._build_known_acts_set()
        self._settings = get_settings()

        # Load patterns from JSON (or use defaults)
        self._garbage_patterns: list[tuple[re.Pattern, str]] | None = None
        self._valid_suffixes: tuple[str, ...] | None = None
        self._valid_keywords: set[str] | None = None

    def _build_known_acts_set(self) -> set[str]:
        """Build a set of known act names for quick lookup."""
        known = set()
        for key, (name, _) in ACT_ABBREVIATIONS.items():
            known.add(key.lower())
            known.add(name.lower())
        return known

    def _get_garbage_patterns(self) -> list[tuple[re.Pattern, str]]:
        """Get garbage patterns, loading from JSON if needed."""
        if self._garbage_patterns is None:
            patterns = get_garbage_patterns()
            if patterns:
                self._garbage_patterns = patterns
            else:
                # Fallback to basic built-in patterns
                self._garbage_patterns = [
                    (re.compile(r"\.\s+[A-Z]", re.IGNORECASE), "Period followed by capital"),
                    (re.compile(r"\.\s+[a-z]"), "Period followed by lowercase"),
                    (re.compile(r"\s+accordingly\s+", re.IGNORECASE), "Legal continuation"),
                    (re.compile(r"\s+Respondent\s+", re.IGNORECASE), "Legal party reference"),
                    (re.compile(r"\s+Petitioner\s+", re.IGNORECASE), "Legal party reference"),
                ]
        return self._garbage_patterns

    def _get_valid_suffixes(self) -> tuple[str, ...]:
        """Get valid act suffixes, loading from JSON if needed."""
        if self._valid_suffixes is None:
            suffixes = get_valid_act_suffixes()
            if suffixes:
                self._valid_suffixes = suffixes
            else:
                # Fallback to basic built-in suffixes
                self._valid_suffixes = (
                    "act", "code", "rules", "regulations", "ordinance",
                    "order", "bill", "amendment", "notification",
                )
        return self._valid_suffixes

    def _get_valid_keywords(self) -> set[str]:
        """Get valid act keywords, loading from JSON if needed."""
        if self._valid_keywords is None:
            keywords = get_valid_act_keywords()
            if keywords:
                self._valid_keywords = keywords
            else:
                # Fallback to basic built-in keywords
                self._valid_keywords = {
                    "act", "code", "rules", "regulations", "ordinance",
                    "amendment", "indian", "central", "state", "prevention",
                    "protection", "enforcement", "regulation", "development",
                    "welfare", "management", "control",
                }
        return self._valid_keywords

    def validate(self, act_name: str) -> ActValidationResult:
        """Validate an act name.

        This method:
        1. Cleans the act name (removes garbage suffixes)
        2. Checks if it's a known act (abbreviations.py)
        3. Runs garbage detection heuristics
        4. Returns validation result with status and confidence

        Args:
            act_name: Raw act name as extracted from document.

        Returns:
            ActValidationResult with validation status and metadata.
        """
        settings = self._settings

        if not act_name or not act_name.strip():
            return ActValidationResult(
                act_name_original=act_name or "",
                act_name_cleaned="",
                act_name_normalized="",
                act_name_canonical=None,
                act_year=None,
                validation_status=ValidationStatus.INVALID,
                validation_source=ValidationSource.GARBAGE_DETECTION,
                confidence=1.0,
                garbage_patterns_matched=["Empty act name"],
                is_known_act=False,
            )

        # Step 1: Clean the act name
        cleaned = clean_act_name(act_name)

        # Step 2: Check for garbage patterns (on original AND cleaned name)
        garbage_patterns = self._detect_garbage_patterns(act_name)
        # Also check garbage patterns on cleaned name (catches post-truncation garbage)
        cleaned_garbage = self._detect_garbage_patterns(cleaned)
        garbage_patterns.extend([p for p in cleaned_garbage if p not in garbage_patterns])

        # Step 2b: Check if cleaned result is a generic term (always invalid)
        is_generic_term = self._is_generic_term(cleaned)
        if is_generic_term:
            garbage_patterns.append("Generic term after cleaning")

        is_garbage = len(garbage_patterns) > 0 or self._is_structurally_garbage(cleaned)

        # Step 3: Check if it's a known act (but not for generic terms)
        canonical_result = None
        is_known = False
        if not is_generic_term:
            canonical_result = get_canonical_name(cleaned)
            is_known = canonical_result is not None

        # Step 4: Normalize the name
        normalized = normalize_act_name(cleaned)

        # Step 5: Determine validation status using configurable confidence
        # Generic terms are ALWAYS invalid, even if they match abbreviations
        if is_generic_term:
            status = ValidationStatus.INVALID
            source = ValidationSource.GARBAGE_DETECTION
            confidence = 0.95  # High confidence for generic terms
        elif is_garbage and not is_known:
            status = ValidationStatus.INVALID
            source = ValidationSource.GARBAGE_DETECTION
            base_confidence = settings.validation_garbage_base_confidence
            increment = settings.validation_garbage_increment
            confidence = min(base_confidence + len(garbage_patterns) * increment, 0.99)
        elif is_known:
            status = ValidationStatus.VALID
            source = ValidationSource.ABBREVIATIONS
            confidence = settings.validation_known_act_confidence
        else:
            # Unknown - needs further validation (India Code lookup)
            status = ValidationStatus.UNKNOWN
            source = ValidationSource.GARBAGE_DETECTION
            confidence = settings.validation_unknown_act_confidence

        # Extract canonical name and year
        canonical_name = None
        year = None
        if canonical_result:
            canonical_name = f"{canonical_result[0]}, {canonical_result[1]}" if canonical_result[1] else canonical_result[0]
            year = canonical_result[1]

        return ActValidationResult(
            act_name_original=act_name,
            act_name_cleaned=cleaned,
            act_name_normalized=normalized,
            act_name_canonical=canonical_name,
            act_year=year,
            validation_status=status,
            validation_source=source,
            confidence=confidence,
            garbage_patterns_matched=garbage_patterns,
            is_known_act=is_known,
        )

    def _is_generic_term(self, act_name: str) -> bool:
        """Check if act name is a generic term that should always be invalid.

        These are terms that are too vague to be useful, even if they match
        in the abbreviations dictionary via fuzzy matching.

        Generic terms are loaded from validation_rules.json.

        Args:
            act_name: The cleaned act name.

        Returns:
            True if it's a generic term that should be invalid.
        """
        if not act_name:
            return True

        lower = act_name.lower().strip()
        # Remove year suffix
        lower = re.sub(r",?\s*\d{4}\s*$", "", lower).strip()

        # Get generic terms from JSON config
        generic_terms = get_generic_terms()

        return lower in generic_terms

    def _detect_garbage_patterns(self, act_name: str) -> list[str]:
        """Detect garbage patterns in an act name.

        Args:
            act_name: The act name to check.

        Returns:
            List of pattern descriptions that matched.
        """
        matched = []
        for pattern, description in self._get_garbage_patterns():
            if pattern.search(act_name):
                matched.append(description)
        return matched

    def _is_structurally_garbage(self, act_name: str) -> bool:
        """Check if act name is structurally invalid.

        Checks:
        - Length limits (from config)
        - Minimum word count (at least 2 meaningful words)
        - Generic terms like "the Act" or "Ordinance" alone
        - Must end with valid suffix (act, code, rules, etc.)
        - Must contain valid keywords

        Args:
            act_name: The cleaned act name.

        Returns:
            True if structurally invalid (garbage).
        """
        settings = self._settings

        # Check length using configurable limits
        if len(act_name) < settings.act_name_min_length:
            return True

        if len(act_name) > settings.act_name_max_length:
            return True

        # Normalize for checking
        lower_name = act_name.lower().strip()

        # Remove year suffix for checking
        lower_name_no_year = re.sub(r",?\s*\d{4}\s*$", "", lower_name).strip()

        # Check for generic terms that are too vague
        generic_terms = {
            "the act", "act", "the code", "code", "the ordinance", "ordinance",
            "the rules", "rules", "the regulations", "regulations",
            "the bill", "bill", "the amendment", "amendment",
        }
        if lower_name_no_year in generic_terms:
            return True

        # Check minimum word count (at least 2 meaningful words excluding articles)
        words = [w for w in re.findall(r"\w+", lower_name_no_year) if w not in ("the", "of", "and", "for", "to", "in", "on", "a", "an")]
        if len(words) < 2:
            # Exception: Known abbreviations like "IPC", "CrPC"
            if lower_name_no_year in self._known_act_names:
                return False
            return True

        # Must end with valid suffix
        valid_suffixes = self._get_valid_suffixes()
        has_valid_suffix = any(
            lower_name_no_year.endswith(suffix) for suffix in valid_suffixes
        )

        if not has_valid_suffix:
            # Exception: Some acts are referred to without suffix (e.g., "IPC", "CrPC")
            # Check if it's a known abbreviation
            if lower_name_no_year in self._known_act_names:
                return False
            return True

        # Must contain at least one valid keyword
        valid_keywords = self._get_valid_keywords()
        words_set = set(re.findall(r"\w+", lower_name))
        has_valid_keyword = bool(words_set & valid_keywords)

        if not has_valid_keyword:
            # Exception: Short act names that are abbreviations
            if len(lower_name_no_year) < 20:
                return False
            return True

        return False

    def is_likely_garbage(self, act_name: str) -> bool:
        """Quick check if an act name is likely garbage.

        This is a fast heuristic check without full validation.
        Use validate() for complete validation with confidence scores.

        Args:
            act_name: The act name to check.

        Returns:
            True if likely garbage, False otherwise.
        """
        result = self.validate(act_name)
        return result.validation_status == ValidationStatus.INVALID

    def batch_validate(self, act_names: list[str]) -> dict[str, ActValidationResult]:
        """Validate multiple act names.

        Args:
            act_names: List of act names to validate.

        Returns:
            Dict mapping original act name to validation result.
        """
        results = {}
        for name in act_names:
            results[name] = self.validate(name)
        return results

    def filter_valid_acts(self, act_names: list[str]) -> list[str]:
        """Filter a list of act names to only valid ones.

        Args:
            act_names: List of act names to filter.

        Returns:
            List of act names that are valid or unknown (needs further validation).
        """
        valid = []
        for name in act_names:
            result = self.validate(name)
            if result.validation_status != ValidationStatus.INVALID:
                valid.append(name)
        return valid


# =============================================================================
# Module-level convenience functions
# =============================================================================

_validation_service: ActValidationService | None = None


def get_validation_service() -> ActValidationService:
    """Get the singleton validation service instance."""
    global _validation_service
    if _validation_service is None:
        _validation_service = ActValidationService()
    return _validation_service


def validate_act_name(act_name: str) -> ActValidationResult:
    """Validate an act name.

    Convenience function that uses the singleton service.

    Args:
        act_name: Raw act name as extracted from document.

    Returns:
        ActValidationResult with validation status and metadata.
    """
    return get_validation_service().validate(act_name)


def is_garbage_act_name(act_name: str) -> bool:
    """Check if an act name is garbage.

    Convenience function that uses the singleton service.

    Args:
        act_name: The act name to check.

    Returns:
        True if garbage, False otherwise.
    """
    return get_validation_service().is_likely_garbage(act_name)


def is_validation_enabled() -> bool:
    """Check if act validation is enabled.

    Returns:
        True if enabled, False otherwise.
    """
    return get_settings().act_validation_enabled
