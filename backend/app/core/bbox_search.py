"""Document-wide bbox search for per-item accuracy.

When chunk bbox linking fails (wrong bboxes linked), this module provides
a fallback by searching ALL document bboxes for specific item text.

This solves Root Cause A: Fuzzy matching failures where chunks get linked
to wrong bboxes due to low match thresholds or unrepresentative samples.

Used by:
- Backfill scripts to fix existing citations with wrong bbox links
- Storage layers as fallback when chunk bboxes don't contain item text
"""

import re
from collections import defaultdict
from collections.abc import Sequence

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Bbox Index for O(1) Word Lookup (F7: N+1 Query Fix)
# =============================================================================


class BboxWordIndex:
    """Pre-computed word index for fast bbox lookup.

    Build once, use many times to avoid O(citations * bboxes) complexity.

    Usage:
        index = BboxWordIndex(bboxes)
        candidates = index.find_candidates("Section 205(C)", min_words=2)
        # Now only search the candidates, not all bboxes
    """

    def __init__(self, bboxes: list[dict]) -> None:
        """Build word-to-bbox index."""
        self.bboxes = bboxes
        self.word_to_indices: dict[str, set[int]] = defaultdict(set)
        self.bbox_text_lower: list[str] = []

        for i, bbox in enumerate(bboxes):
            text = (bbox.get("text") or "").lower()
            self.bbox_text_lower.append(text)
            for word in text.split():
                # Only index words >= 3 chars (skip common words)
                if len(word) >= 3:
                    self.word_to_indices[word].add(i)

    def find_candidates(self, search_text: str, min_words: int = 2) -> list[dict]:
        """Find bboxes that likely contain the search text.

        Returns bboxes that share at least min_words with search_text.
        Much faster than scanning all bboxes.
        """
        search_words = [w for w in search_text.lower().split() if len(w) >= 3]
        if len(search_words) < min_words:
            # Not enough words, return all bboxes
            return self.bboxes

        # Count how many search words appear in each bbox
        candidate_counts: dict[int, int] = defaultdict(int)
        for word in search_words:
            for idx in self.word_to_indices.get(word, []):
                candidate_counts[idx] += 1

        # Return bboxes with at least min_words overlap
        return [
            self.bboxes[idx]
            for idx, count in candidate_counts.items()
            if count >= min_words
        ]


def search_bboxes_for_text(
    search_text: str,
    bboxes: list[dict],
    key_phrase_patterns: Sequence[str] | None = None,
    min_word_overlap: int = 3,
    max_results: int = 10,
) -> tuple[list[str], int | None]:
    """Search bboxes for text and return matching bbox IDs and page.

    Uses 3-tier matching strategy:
    1. Exact substring match (highest confidence)
    2. Key phrase match (for section/act references)
    3. Word overlap scoring (fallback)

    Args:
        search_text: The text to search for (e.g., citation text)
        bboxes: List of bbox dicts with 'id', 'text', 'page_number'
        key_phrase_patterns: Regex patterns to extract key phrases
        min_word_overlap: Minimum words required for overlap match
        max_results: Maximum bbox IDs to return

    Returns:
        Tuple of (list of matching bbox_ids, page_number where found)
        Returns ([], None) if no match found
    """
    if not search_text or not bboxes:
        return [], None

    search_lower = search_text.lower().strip()
    matched_ids: list[str] = []
    seen_ids: set[str] = set()  # F5: Prevent duplicate bbox IDs
    matched_page: int | None = None

    # Strategy 1: Exact substring match
    for bbox in bboxes:
        bbox_text = (bbox.get("text") or "").lower()
        if search_lower in bbox_text:
            bbox_id = bbox.get("id")
            if bbox_id and str(bbox_id) not in seen_ids:
                matched_ids.append(str(bbox_id))
                seen_ids.add(str(bbox_id))
                if matched_page is None:
                    matched_page = bbox.get("page_number")
            if len(matched_ids) >= max_results:
                break

    if matched_ids:
        logger.debug(
            "bbox_search_exact_match",
            search_text=search_text[:50],
            matched_count=len(matched_ids),
            page=matched_page,
        )
        return matched_ids, matched_page

    # Strategy 2: Key phrase matching
    if key_phrase_patterns:
        for pattern in key_phrase_patterns:
            match = re.search(pattern, search_lower, re.IGNORECASE)
            if match:
                phrase = match.group(0)
                for bbox in bboxes:
                    bbox_text = (bbox.get("text") or "").lower()
                    if phrase in bbox_text:
                        bbox_id = bbox.get("id")
                        if bbox_id and str(bbox_id) not in seen_ids:
                            matched_ids.append(str(bbox_id))
                            seen_ids.add(str(bbox_id))
                            if matched_page is None:
                                matched_page = bbox.get("page_number")
                        if len(matched_ids) >= max_results:
                            break

                if matched_ids:
                    logger.debug(
                        "bbox_search_phrase_match",
                        search_text=search_text[:50],
                        phrase=phrase,
                        matched_count=len(matched_ids),
                        page=matched_page,
                    )
                    return matched_ids, matched_page

    # Strategy 3: Word overlap scoring
    search_words = set(search_lower.split())
    if len(search_words) < min_word_overlap:
        return [], None

    scored_bboxes: list[tuple[dict, int]] = []

    for bbox in bboxes:
        bbox_text = (bbox.get("text") or "").lower()
        bbox_words = set(bbox_text.split())
        overlap = len(search_words & bbox_words)

        if overlap >= min_word_overlap:
            scored_bboxes.append((bbox, overlap))

    # Sort by overlap score descending
    scored_bboxes.sort(key=lambda x: x[1], reverse=True)

    for bbox, _score in scored_bboxes[:max_results]:
        bbox_id = bbox.get("id")
        if bbox_id and str(bbox_id) not in seen_ids:
            matched_ids.append(str(bbox_id))
            seen_ids.add(str(bbox_id))
            if matched_page is None:
                matched_page = bbox.get("page_number")

    if matched_ids:
        logger.debug(
            "bbox_search_word_overlap",
            search_text=search_text[:50],
            matched_count=len(matched_ids),
            page=matched_page,
            best_overlap=scored_bboxes[0][1] if scored_bboxes else 0,
        )

    return matched_ids, matched_page


def verify_bbox_contains_text(
    text: str,
    bboxes: list[dict],
    min_word_overlap: int = 2,
) -> bool:
    """Verify that bboxes actually contain the given text.

    Used to detect when source_bbox_ids are linked to wrong bboxes.

    Args:
        text: The text that should be in the bboxes
        bboxes: The bboxes to check

    Returns:
        True if bboxes contain the text, False otherwise
    """
    if not text or not bboxes:
        return False

    text_lower = text.lower().strip()
    text_words = set(text_lower.split())

    # Check for exact substring in any bbox
    for bbox in bboxes:
        bbox_text = (bbox.get("text") or "").lower()
        if text_lower in bbox_text:
            return True

    # Check for word overlap
    all_bbox_text = " ".join((b.get("text") or "") for b in bboxes).lower()
    all_bbox_words = set(all_bbox_text.split())
    overlap = len(text_words & all_bbox_words)

    # Require at least min_word_overlap or 30% of text words
    min_required = max(min_word_overlap, int(len(text_words) * 0.3))
    return overlap >= min_required


def filter_bboxes_for_item(
    item_text: str,
    chunk_bboxes: list[dict],
    key_phrase_patterns: Sequence[str] | None = None,
) -> list[str]:
    """Filter chunk's bboxes to only those containing the item text.

    Solves Root Cause B: Chunk-level aggregation where all items
    get all chunk bboxes instead of just their specific ones.

    Args:
        item_text: The specific item text (citation, event, entity)
        chunk_bboxes: All bboxes linked to the chunk
        key_phrase_patterns: Patterns to extract key phrases for matching

    Returns:
        List of bbox IDs that actually contain the item text
    """
    if not item_text or not chunk_bboxes:
        return []

    matched_ids, _ = search_bboxes_for_text(
        search_text=item_text,
        bboxes=chunk_bboxes,
        key_phrase_patterns=key_phrase_patterns,
        min_word_overlap=2,
        max_results=15,
    )

    return matched_ids
