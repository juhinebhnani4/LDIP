"""Quote detection for language policing.

Story 8-3: Language Policing (AC #6)

Detects and marks protected regions in text that should NOT be sanitized:
- Double-quoted text: "exact quote from document"
- Single-quoted text: 'exact quote'
- Citation references: As stated in [Document, p. X]

Design Philosophy:
- Preserve: Direct quotes from source documents must remain verbatim
- Attribute: Track source document and page when available
- Overlap-free: Handle nested/overlapping quotes gracefully
"""

from __future__ import annotations

import re
from typing import NamedTuple

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 8-3: Protected Region Definition
# =============================================================================


class ProtectedRegion(NamedTuple):
    """Region of text protected from sanitization.

    Story 8-3: AC #6 - Quote preservation.

    Attributes:
        start: Start position in the text.
        end: End position in the text.
        text: The actual text content.
        source: Document name if citation detected.
        page: Page number if citation detected.
    """

    start: int
    end: int
    text: str
    source: str | None
    page: int | None


# =============================================================================
# Story 8-3: QuoteDetector Service (Task 3.1-3.5)
# =============================================================================


class QuoteDetector:
    """Detect and protect quoted text from sanitization.

    Story 8-3: AC #6 - Preserve direct quotes from documents.

    This service identifies regions of text that should NOT be modified
    during language policing because they are direct quotes from source
    documents.

    Patterns detected:
    - Double-quoted text: "exact quote from document"
    - Single-quoted text: 'exact quote'
    - Citation references: As stated in [Document, p. X]

    Example:
        >>> detector = QuoteDetector()
        >>> regions = detector.detect_protected_regions(
        ...     'The witness stated "defendant violated the agreement" in court.'
        ... )
        >>> len(regions)
        1
        >>> regions[0].text
        '"defendant violated the agreement"'
    """

    # Double-quoted text pattern
    # Matches text within double quotes, non-greedy
    DOUBLE_QUOTE_PATTERN = re.compile(r'"([^"]+)"')

    # Single-quoted text pattern (for apostrophe-style quotes)
    # Only match if surrounded by non-word characters to avoid contractions
    SINGLE_QUOTE_PATTERN = re.compile(r"(?<!\w)'([^']+)'(?!\w)")

    # Citation reference patterns
    # Matches patterns like:
    # - "as stated in [Document Name, p. 5]"
    # - "according to (Exhibit A, page 12)"
    # - "per Contract Agreement, p. 3"
    # - "see Exhibit B, page 10"
    CITATION_PATTERN = re.compile(
        r"(?:as\s+stated\s+in|according\s+to|per|see)\s+"
        r"(?:"
        r"\[([^\]]+?)(?:,\s*p(?:age)?\.?\s*(\d+))?\]"  # [Document, p. X]
        r"|"
        r"\(([^)]+?)(?:,\s*p(?:age)?\.?\s*(\d+))?\)"  # (Document, p. X)
        r"|"
        r"([A-Z][A-Za-z\s]+?)(?:,\s*p(?:age)?\.?\s*(\d+))"  # Document Name, p. X
        r")",
        re.IGNORECASE,
    )

    # Block quote pattern (indented or formatted blocks)
    # Matches text prefixed with ">" (markdown-style quotes)
    BLOCK_QUOTE_PATTERN = re.compile(r"^>\s*(.+)$", re.MULTILINE)

    def __init__(self) -> None:
        """Initialize quote detector.

        Story 8-3: Task 3.1 - Service initialization.
        """
        logger.debug("quote_detector_initialized")

    def detect_protected_regions(self, text: str) -> list[ProtectedRegion]:
        """Find all regions that should be protected from sanitization.

        Story 8-3: Task 3.4 - Mark protected regions.

        Args:
            text: Full text to analyze.

        Returns:
            List of ProtectedRegion objects marking quote boundaries,
            sorted by start position.
        """
        regions: list[ProtectedRegion] = []

        # Detect double-quoted text
        regions.extend(self._detect_double_quotes(text))

        # Detect single-quoted text
        regions.extend(self._detect_single_quotes(text))

        # Detect citation references
        regions.extend(self._detect_citations(text))

        # Detect block quotes
        regions.extend(self._detect_block_quotes(text))

        # Remove overlapping regions (keep longer ones)
        regions = self._remove_overlaps(regions)

        # Sort by start position
        regions.sort(key=lambda r: r.start)

        logger.debug(
            "quote_detection_complete",
            region_count=len(regions),
        )

        return regions

    def _detect_double_quotes(self, text: str) -> list[ProtectedRegion]:
        """Detect double-quoted text.

        Story 8-3: Task 3.2 - Find quoted text.

        Args:
            text: Text to analyze.

        Returns:
            List of protected regions for double-quoted text.
        """
        regions: list[ProtectedRegion] = []

        for match in self.DOUBLE_QUOTE_PATTERN.finditer(text):
            regions.append(
                ProtectedRegion(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                    source=None,
                    page=None,
                )
            )

        return regions

    def _detect_single_quotes(self, text: str) -> list[ProtectedRegion]:
        """Detect single-quoted text.

        Story 8-3: Task 3.2 - Find quoted text.

        Args:
            text: Text to analyze.

        Returns:
            List of protected regions for single-quoted text.
        """
        regions: list[ProtectedRegion] = []

        for match in self.SINGLE_QUOTE_PATTERN.finditer(text):
            # Skip very short matches (likely contractions like don't)
            if len(match.group(1)) < 10:
                continue

            regions.append(
                ProtectedRegion(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                    source=None,
                    page=None,
                )
            )

        return regions

    def _detect_citations(self, text: str) -> list[ProtectedRegion]:
        """Detect citation references with source attribution.

        Story 8-3: Task 3.3 - Find explicit citation references.

        Args:
            text: Text to analyze.

        Returns:
            List of protected regions with source/page attribution.
        """
        regions: list[ProtectedRegion] = []

        for match in self.CITATION_PATTERN.finditer(text):
            # Extract source and page from the match groups
            # Groups: (1,2) for [brackets], (3,4) for (parens), (5,6) for bare name
            source = match.group(1) or match.group(3) or match.group(5)
            page_str = match.group(2) or match.group(4) or match.group(6)

            page = int(page_str) if page_str else None

            regions.append(
                ProtectedRegion(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                    source=source.strip() if source else None,
                    page=page,
                )
            )

        return regions

    def _detect_block_quotes(self, text: str) -> list[ProtectedRegion]:
        """Detect markdown-style block quotes.

        Story 8-3: Task 3.2 - Find block quoted text.

        Args:
            text: Text to analyze.

        Returns:
            List of protected regions for block quotes.
        """
        regions: list[ProtectedRegion] = []

        for match in self.BLOCK_QUOTE_PATTERN.finditer(text):
            regions.append(
                ProtectedRegion(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                    source=None,
                    page=None,
                )
            )

        return regions

    def _remove_overlaps(
        self, regions: list[ProtectedRegion]
    ) -> list[ProtectedRegion]:
        """Remove overlapping regions, keeping longer ones.

        Story 8-3: Task 3.5 - Handle nested quotes.

        Args:
            regions: List of potentially overlapping regions.

        Returns:
            List of non-overlapping regions.
        """
        if not regions:
            return regions

        # Sort by start position, then by length (descending)
        sorted_regions = sorted(regions, key=lambda r: (r.start, -(r.end - r.start)))

        result: list[ProtectedRegion] = []
        current_end = -1

        for region in sorted_regions:
            # Skip if this region is contained within a previous one
            if region.start < current_end:
                continue

            result.append(region)
            current_end = region.end

        return result

    def format_quote_attribution(self, region: ProtectedRegion) -> str:
        """Format attribution note for a preserved quote.

        Story 8-3: Task 3.5 - Format quote attribution.

        Args:
            region: Protected region with optional source info.

        Returns:
            Attribution string like "Direct quote from [Document, p. X]"
        """
        if region.source and region.page:
            return f"Direct quote from [{region.source}, p. {region.page}]"
        elif region.source:
            return f"Direct quote from [{region.source}]"
        else:
            return "Direct quote preserved verbatim"


# =============================================================================
# Story 8-3: Module-level Functions
# =============================================================================


def detect_quotes(text: str) -> list[ProtectedRegion]:
    """Convenience function to detect quotes in text.

    Story 8-3: Task 3.2 - Module-level accessor.

    Args:
        text: Text to analyze.

    Returns:
        List of protected regions.
    """
    detector = QuoteDetector()
    return detector.detect_protected_regions(text)
