"""Regex-based language policing service.

Story 8-3: Language Policing (AC #1-4)

Fast-path regex replacement service that sanitizes LLM outputs by:
1. Detecting protected regions (quotes)
2. Applying regex replacements to unprotected text
3. Tracking all replacements for audit

This is Phase 1 of the output sanitization pipeline.

Performance Target: < 5ms for regex policing (excludes LLM phase).
"""

from __future__ import annotations

import threading
import time

import structlog

from app.models.safety import (
    LanguagePolicingResult,
    QuotePreservation,
    ReplacementRecord,
)
from app.services.safety.policing_patterns import (
    CompiledPolicingPattern,
    get_policing_patterns,
)
from app.services.safety.quote_detector import ProtectedRegion, QuoteDetector

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 8-3: LanguagePolicingService (Task 4.1-4.6)
# =============================================================================


class LanguagePolicingService:
    """Regex-based language policing for LLM outputs.

    Story 8-3: Fast-path regex replacement of legal conclusions.

    This is Phase 1 of output sanitization:
    1. Detect and mark protected regions (quotes)
    2. Apply regex replacements to unprotected text
    3. Combine with protected regions
    4. Return sanitized text with replacement records

    Example:
        >>> service = get_language_policing_service()
        >>> result = service.sanitize_text(
        ...     "The evidence proves that defendant violated Section 138."
        ... )
        >>> result.sanitized_text
        "The evidence suggests that defendant affected by Section 138."
    """

    def __init__(self) -> None:
        """Initialize language policing service.

        Story 8-3: Task 4.2 - Service initialization with lazy pattern loading.
        """
        self._patterns: list[CompiledPolicingPattern] = []
        self._quote_detector = QuoteDetector()
        self._load_patterns()

        logger.info(
            "language_policing_service_initialized",
            pattern_count=len(self._patterns),
        )

    def _load_patterns(self) -> None:
        """Load compiled regex patterns.

        Story 8-3: Task 4.2 - Pattern loading.
        """
        self._patterns = get_policing_patterns()

    def sanitize_text(self, text: str) -> LanguagePolicingResult:
        """Apply regex sanitization to text.

        Story 8-3: AC #1-4, Task 4.3 - Main sanitization method.

        This method:
        1. Detects protected regions (quotes) that should not be modified
        2. Applies regex replacements to unprotected text
        3. Returns result with timing metrics and replacement records

        Args:
            text: LLM output text to sanitize.

        Returns:
            LanguagePolicingResult with sanitized text and metadata.
        """
        start_time = time.perf_counter()

        # Handle empty input
        if not text or not text.strip():
            return LanguagePolicingResult(
                original_text=text,
                sanitized_text=text,
                replacements_made=[],
                quotes_preserved=[],
                llm_policing_applied=False,
                sanitization_time_ms=0.0,
            )

        # Step 1: Detect protected regions (quotes)
        protected_regions = self._quote_detector.detect_protected_regions(text)

        # Step 2: Apply replacements to unprotected text
        sanitized_text, replacements = self._apply_replacements(text, protected_regions)

        # Step 3: Convert protected regions to QuotePreservation models
        quotes_preserved = [
            QuotePreservation(
                quoted_text=region.text,
                source_document=region.source,
                page_number=region.page,
                start_pos=region.start,
                end_pos=region.end,
            )
            for region in protected_regions
        ]

        check_time_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            "text_sanitized",
            original_length=len(text),
            sanitized_length=len(sanitized_text),
            replacements_made=len(replacements),
            quotes_preserved=len(quotes_preserved),
            sanitization_time_ms=round(check_time_ms, 3),
        )

        return LanguagePolicingResult(
            original_text=text,
            sanitized_text=sanitized_text,
            replacements_made=replacements,
            quotes_preserved=quotes_preserved,
            llm_policing_applied=False,
            sanitization_time_ms=check_time_ms,
        )

    def _apply_replacements(
        self,
        text: str,
        protected_regions: list[ProtectedRegion],
    ) -> tuple[str, list[ReplacementRecord]]:
        """Apply regex replacements avoiding protected regions.

        Story 8-3: Task 4.4 - Apply patterns with protection.

        Args:
            text: Original text.
            protected_regions: Regions to skip (quotes).

        Returns:
            Tuple of (sanitized_text, replacement_records).
        """
        replacements: list[ReplacementRecord] = []

        # Build set of protected positions for O(1) lookup
        protected_positions: set[int] = set()
        for region in protected_regions:
            for i in range(region.start, region.end):
                protected_positions.add(i)

        # Collect all matches first to handle position shifts correctly
        all_matches: list[tuple[CompiledPolicingPattern, int, int, str]] = []

        for pattern in self._patterns:
            for match in pattern.regex.finditer(text):
                # Check if match overlaps with protected region
                match_positions = set(range(match.start(), match.end()))
                if match_positions & protected_positions:
                    # Skip matches that overlap with protected regions
                    continue

                all_matches.append((pattern, match.start(), match.end(), match.group(0)))

        # Sort matches by position (descending) so we can replace from end to start
        # This avoids position shift issues
        all_matches.sort(key=lambda x: x[1], reverse=True)

        # Apply replacements from end to start
        result_text = text
        for pattern, start, end, matched_text in all_matches:
            # Get replacement text
            replacement_text = pattern.regex.sub(pattern.replacement, matched_text)

            # Apply replacement
            result_text = result_text[:start] + replacement_text + result_text[end:]

            # Record the replacement (use original positions for audit)
            replacements.append(
                ReplacementRecord(
                    original_phrase=matched_text,
                    replacement_phrase=replacement_text,
                    position_start=start,
                    position_end=end,
                    rule_id=pattern.rule_id,
                )
            )

        # Reverse replacements list to match original text order
        replacements.reverse()

        return result_text, replacements

    def get_pattern_count(self) -> int:
        """Get number of loaded policing patterns.

        Returns:
            Number of patterns in the registry.
        """
        return len(self._patterns)


# =============================================================================
# Story 8-3: Singleton Factory (Task 4.6)
# =============================================================================

# Singleton instance (thread-safe)
_policing_service: LanguagePolicingService | None = None
_service_lock = threading.Lock()


def get_language_policing_service() -> LanguagePolicingService:
    """Get singleton language policing service instance.

    Story 8-3: Task 4.6 - Factory function with thread-safe initialization.

    Returns:
        LanguagePolicingService singleton instance.
    """
    global _policing_service  # noqa: PLW0603

    if _policing_service is None:
        with _service_lock:
            # Double-check locking pattern
            if _policing_service is None:
                _policing_service = LanguagePolicingService()

    return _policing_service


def reset_language_policing_service() -> None:
    """Reset singleton for testing.

    Story 8-3: Reset function for test isolation.

    Note:
        This creates a fresh instance on next get_language_policing_service() call.
    """
    global _policing_service  # noqa: PLW0603

    with _service_lock:
        _policing_service = None

    logger.debug("language_policing_service_reset")
