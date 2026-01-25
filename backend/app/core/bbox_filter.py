"""Unified bbox filtering for all engines.

This module provides a single function that all engines can use to get
filtered bbox_ids for specific item text. It handles:
1. Fetching bbox data from IDs (cached per document)
2. Filtering to only bboxes containing the item text
3. Returning filtered IDs and detected page

This solves the "chunk-level aggregation" problem where all items
in a chunk get all the chunk's bboxes.

Usage (any engine):
    filtered_ids, page = await get_filtered_bbox_ids(
        item_text="Section 205(C) of the Act",
        chunk_bbox_ids=["uuid1", "uuid2", ...],
        document_id="doc-uuid",
    )

Story 6.1: Citation page detection logging added for accuracy tracking.
"""

import threading
from collections.abc import Sequence

import structlog

from app.core.bbox_search import search_bboxes_for_text
from app.core.page_detection import ACT_PATTERN, SECTION_PATTERN
from app.core.reliability_logging import log_citation_page_detection, log_citation_page_fallback

logger = structlog.get_logger(__name__)

# In-memory cache for bbox data per document (cleared after processing)
# Thread-safe access via _bbox_cache_lock
# F3: Limited to MAX_CACHE_SIZE documents with LRU eviction
_bbox_cache: dict[str, list[dict]] = {}
_bbox_cache_lock = threading.Lock()
MAX_CACHE_SIZE = 50  # Max documents to cache before eviction


def _evict_oldest_if_needed() -> None:
    """Evict oldest cache entries if cache exceeds max size.

    Must be called while holding _bbox_cache_lock.
    """
    while len(_bbox_cache) > MAX_CACHE_SIZE:
        # Python 3.7+ dicts maintain insertion order, so first key is oldest
        oldest_key = next(iter(_bbox_cache))
        del _bbox_cache[oldest_key]
        logger.debug("bbox_cache_evicted", document_id=oldest_key[:8] if oldest_key else None)


def set_document_bboxes(document_id: str, bboxes: list[dict]) -> None:
    """Pre-load bbox data for a document (call once per chunk batch).

    Args:
        document_id: Document UUID
        bboxes: List of bbox dicts with 'id', 'text', 'page_number'
    """
    with _bbox_cache_lock:
        _bbox_cache[document_id] = bboxes
        _evict_oldest_if_needed()


def clear_document_bboxes(document_id: str) -> None:
    """Clear cached bbox data for a document."""
    with _bbox_cache_lock:
        _bbox_cache.pop(document_id, None)


def get_filtered_bbox_ids(
    item_text: str,
    chunk_bbox_ids: list[str],
    document_id: str | None = None,
    chunk_bboxes: list[dict] | None = None,
    key_patterns: Sequence[str] | None = None,
    matter_id: str | None = None,
    event_id: str | None = None,
    citation_id: str | None = None,
    log_reliability: bool = False,
) -> tuple[list[str], int | None]:
    """Get filtered bbox IDs for a specific item.

    Filters chunk's bbox_ids to only those containing the item's text.
    Falls back to all chunk_bbox_ids if no match found.

    Story 6.1: Added reliability logging for citation page accuracy tracking.

    Args:
        item_text: The item text to match (citation, event, entity text)
        chunk_bbox_ids: All bbox IDs from the chunk
        document_id: Optional document ID for cache lookup
        chunk_bboxes: Optional pre-fetched bbox data (preferred)
        key_patterns: Optional regex patterns for key phrase matching
        matter_id: Optional matter ID for reliability logging
        event_id: Optional event ID for reliability logging
        citation_id: Optional citation ID for reliability logging
        log_reliability: If True, log citation page accuracy metrics

    Returns:
        Tuple of (filtered_bbox_ids, detected_page_number)
        Returns (chunk_bbox_ids, None) if filtering fails
    """
    if not item_text or not chunk_bbox_ids:
        return chunk_bbox_ids or [], None

    # Get bbox data (thread-safe cache access)
    bboxes = chunk_bboxes
    if not bboxes and document_id:
        with _bbox_cache_lock:
            bboxes = _bbox_cache.get(document_id)

    if not bboxes:
        # No bbox data available, can't filter - return original
        # Story 6.1: Log fallback due to no bbox data
        if log_reliability and document_id and matter_id:
            log_citation_page_fallback(
                matter_id=matter_id,
                document_id=document_id,
                event_id=event_id,
                reason="no_bbox_data",
                chunk_page=None,
            )
            # Log chunk detection for accurate COUNT(*) denominator
            log_citation_page_detection(
                matter_id=matter_id,
                document_id=document_id,
                detection_method="chunk",
                page_number=None,
                event_id=event_id,
                citation_id=citation_id,
            )
        return chunk_bbox_ids, None

    # Filter to only bboxes in chunk_bbox_ids
    chunk_bbox_id_set = set(chunk_bbox_ids)
    relevant_bboxes = [b for b in bboxes if b.get("id") in chunk_bbox_id_set]

    if not relevant_bboxes:
        # Story 6.1: Log fallback due to no relevant bboxes
        if log_reliability and document_id and matter_id:
            log_citation_page_fallback(
                matter_id=matter_id,
                document_id=document_id,
                event_id=event_id,
                reason="no_relevant_bboxes",
                chunk_page=None,
            )
            # Log chunk detection for accurate COUNT(*) denominator
            log_citation_page_detection(
                matter_id=matter_id,
                document_id=document_id,
                detection_method="chunk",
                page_number=None,
                event_id=event_id,
                citation_id=citation_id,
            )
        return chunk_bbox_ids, None

    # Use patterns based on content type
    patterns = key_patterns
    if patterns is None:
        # Auto-detect patterns based on text content
        patterns = []
        if any(p in item_text.lower() for p in ["section", "article", "clause"]):
            patterns.append(SECTION_PATTERN)
        if "act" in item_text.lower():
            patterns.append(ACT_PATTERN)

    # Search for matches
    matched_ids, page = search_bboxes_for_text(
        search_text=item_text,
        bboxes=relevant_bboxes,
        key_phrase_patterns=patterns,
        min_word_overlap=2,
        max_results=15,
    )

    if matched_ids:
        # Story 6.1: Log successful bbox-based page detection
        if log_reliability and document_id and matter_id:
            log_citation_page_detection(
                matter_id=matter_id,
                document_id=document_id,
                detection_method="bbox",
                page_number=page,
                event_id=event_id,
                citation_id=citation_id,
                bbox_id=matched_ids[0] if matched_ids else None,
            )
        return matched_ids, page

    # No match found, return original chunk bbox_ids
    # Story 6.1: Log fallback to chunk-level page detection
    if log_reliability and document_id and matter_id:
        # Try to get chunk page from any bbox
        chunk_page = None
        if relevant_bboxes:
            chunk_page = relevant_bboxes[0].get("page_number")
        log_citation_page_fallback(
            matter_id=matter_id,
            document_id=document_id,
            event_id=event_id,
            reason="no_bbox_match",
            chunk_page=chunk_page,
        )
        # Story 6.1: Also log the chunk detection for accurate COUNT(*) denominator
        # This ensures Accuracy = COUNT(bbox) / COUNT(*) can be calculated correctly
        if chunk_page is not None:
            log_citation_page_detection(
                matter_id=matter_id,
                document_id=document_id,
                detection_method="chunk",
                page_number=chunk_page,
                event_id=event_id,
                citation_id=citation_id,
                chunk_id=chunk_bbox_ids[0] if chunk_bbox_ids else None,
            )
    return chunk_bbox_ids, None


async def fetch_and_cache_bboxes(document_id: str) -> list[dict]:
    """Fetch all bboxes for a document and cache them.

    Call this once at the start of processing a document's chunks.

    Args:
        document_id: Document UUID

    Returns:
        List of bbox dicts
    """
    # Thread-safe cache check
    with _bbox_cache_lock:
        if document_id in _bbox_cache:
            return _bbox_cache[document_id]

    try:
        from app.services.bounding_box_service import get_bounding_box_service

        bbox_service = get_bounding_box_service()

        # Fetch all bboxes (paginated) with max iterations guard (F4)
        all_bboxes = []
        page = 1
        batch_size = 1000
        max_iterations = 500  # Safety limit: 500 * 1000 = 500K bboxes max

        while page <= max_iterations:
            batch, total = bbox_service.get_bounding_boxes_for_document(
                document_id=document_id,
                page=page,
                per_page=batch_size,
            )
            all_bboxes.extend(batch)
            if len(all_bboxes) >= total or not batch:
                break
            page += 1

        if page > max_iterations:
            logger.warning(
                "bbox_cache_max_iterations_reached",
                document_id=document_id[:8],
                iterations=max_iterations,
            )

        # Thread-safe cache write with eviction check (F3)
        with _bbox_cache_lock:
            _bbox_cache[document_id] = all_bboxes
            _evict_oldest_if_needed()
        logger.debug(
            "bbox_cache_loaded",
            document_id=document_id[:8],
            bbox_count=len(all_bboxes),
        )
        return all_bboxes

    except Exception as e:
        logger.warning(
            "bbox_cache_load_failed",
            document_id=document_id[:8],
            error=str(e),
        )
        return []
