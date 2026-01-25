"""Per-item page detection from bounding boxes.

When chunks span multiple pages, this finds the exact page where
specific text appears by searching through linked bboxes.

This utility is used by multiple engines:
- Citations: Find exact page for "Section 205(C) of the Companies Act"
- Timeline: Find exact page for events with dates
- Entities: Find exact page for entity mentions
- Contradictions: Find exact page for both statements in a contradiction

Usage:
    from app.core.page_detection import detect_item_page, SECTION_PATTERN

    page = detect_item_page(
        citation_text,
        bboxes,
        key_phrase_patterns=[SECTION_PATTERN, ACT_PATTERN]
    )
"""

import re
from collections.abc import Sequence

# =============================================================================
# Common patterns for different content types
# =============================================================================

# Citation patterns
SECTION_PATTERN = r"section\s+\d+(?:\s*\([^)]+\))?"
# ACT_PATTERN: Limit to 100 chars to prevent ReDoS backtracking (F2)
ACT_PATTERN = r"(?:the\s+)?[\w\s]{1,100}act"

# Timeline patterns
DATE_PATTERN = r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}"


# =============================================================================
# Helper Functions
# =============================================================================


def _validate_page_number(page: object) -> int | None:
    """Validate and return page number, or None if invalid.

    F10: Ensures page_number is a positive integer to prevent
    invalid data from propagating through the system.
    """
    if page is None:
        return None
    if isinstance(page, int) and page > 0:
        return page
    # Try to convert to int if it's a numeric string
    if isinstance(page, str):
        try:
            parsed = int(page)
            return parsed if parsed > 0 else None
        except ValueError:
            return None
    return None


# =============================================================================
# Core detection function
# =============================================================================


def detect_item_page(
    text: str,
    bboxes: list[dict],
    key_phrase_patterns: Sequence[str] | None = None,
    min_word_overlap: int = 3,
) -> int | None:
    """Find the exact page where text appears in bboxes.

    When a chunk spans multiple pages, the chunk's page_number reflects
    where it starts, not where specific content appears. This function
    searches through the linked bboxes to find the exact page where
    the text is located.

    Uses 3-tier matching strategy:
    1. Exact substring match - highest confidence
    2. Key phrase match - for structured content like "Section 205(C)"
    3. Word overlap scoring - fallback for partial matches

    Args:
        text: The text to locate (citation, event description, entity name)
        bboxes: List of bbox dicts with 'text' and 'page_number' keys
        key_phrase_patterns: Optional list of regex patterns for key phrases.
            For citations, use [SECTION_PATTERN, ACT_PATTERN].
            For timeline, use [DATE_PATTERN].
        min_word_overlap: Minimum word overlap for Strategy 3 (default: 3)

    Returns:
        Page number where text appears, or None if not found.
        When None is returned, caller should fall back to chunk.page_number.

    Example:
        >>> bboxes = [
        ...     {"text": "Some text on page 7", "page_number": 7},
        ...     {"text": "Section 205(C) of the Companies Act", "page_number": 8},
        ... ]
        >>> detect_item_page("Section 205(C)", bboxes, [SECTION_PATTERN])
        8
    """
    if not text or not bboxes:
        return None

    text_lower = text.lower().strip()

    # Strategy 1: Exact substring match in single bbox
    for bbox in bboxes:
        bbox_text = (bbox.get("text") or "").lower()
        if text_lower in bbox_text:
            # F10: Validate page_number before returning
            return _validate_page_number(bbox.get("page_number"))

    # Strategy 2: Key phrase matching
    if key_phrase_patterns:
        for pattern in key_phrase_patterns:
            match = re.search(pattern, text_lower)
            if match:
                phrase = match.group(0)
                for bbox in bboxes:
                    bbox_text = (bbox.get("text") or "").lower()
                    if phrase in bbox_text:
                        # F10: Validate page_number before returning
                        return _validate_page_number(bbox.get("page_number"))

    # Strategy 3: Word overlap scoring
    # Find bbox with highest word overlap
    text_words = set(text_lower.split())
    if len(text_words) < min_word_overlap:
        return None

    best_page = None
    best_overlap = 0

    for bbox in bboxes:
        bbox_text = (bbox.get("text") or "").lower()
        bbox_words = set(bbox_text.split())
        overlap = len(text_words & bbox_words)

        if overlap > best_overlap and overlap >= min_word_overlap:
            best_overlap = overlap
            # F10: Validate page_number before storing
            best_page = _validate_page_number(bbox.get("page_number"))

    return best_page
