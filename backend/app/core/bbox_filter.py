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
"""

from functools import lru_cache
from typing import Sequence

import structlog

from app.core.bbox_search import search_bboxes_for_text
from app.core.page_detection import SECTION_PATTERN, ACT_PATTERN, DATE_PATTERN

logger = structlog.get_logger(__name__)

# In-memory cache for bbox data per document (cleared after processing)
_bbox_cache: dict[str, list[dict]] = {}


def set_document_bboxes(document_id: str, bboxes: list[dict]) -> None:
    """Pre-load bbox data for a document (call once per chunk batch).

    Args:
        document_id: Document UUID
        bboxes: List of bbox dicts with 'id', 'text', 'page_number'
    """
    _bbox_cache[document_id] = bboxes


def clear_document_bboxes(document_id: str) -> None:
    """Clear cached bbox data for a document."""
    _bbox_cache.pop(document_id, None)


def get_filtered_bbox_ids(
    item_text: str,
    chunk_bbox_ids: list[str],
    document_id: str | None = None,
    chunk_bboxes: list[dict] | None = None,
    key_patterns: Sequence[str] | None = None,
) -> tuple[list[str], int | None]:
    """Get filtered bbox IDs for a specific item.

    Filters chunk's bbox_ids to only those containing the item's text.
    Falls back to all chunk_bbox_ids if no match found.

    Args:
        item_text: The item text to match (citation, event, entity text)
        chunk_bbox_ids: All bbox IDs from the chunk
        document_id: Optional document ID for cache lookup
        chunk_bboxes: Optional pre-fetched bbox data (preferred)
        key_patterns: Optional regex patterns for key phrase matching

    Returns:
        Tuple of (filtered_bbox_ids, detected_page_number)
        Returns (chunk_bbox_ids, None) if filtering fails
    """
    if not item_text or not chunk_bbox_ids:
        return chunk_bbox_ids or [], None

    # Get bbox data
    bboxes = chunk_bboxes
    if not bboxes and document_id:
        bboxes = _bbox_cache.get(document_id)

    if not bboxes:
        # No bbox data available, can't filter - return original
        return chunk_bbox_ids, None

    # Filter to only bboxes in chunk_bbox_ids
    chunk_bbox_id_set = set(chunk_bbox_ids)
    relevant_bboxes = [b for b in bboxes if b.get("id") in chunk_bbox_id_set]

    if not relevant_bboxes:
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
        return matched_ids, page

    # No match found, return original chunk bbox_ids
    return chunk_bbox_ids, None


async def fetch_and_cache_bboxes(document_id: str) -> list[dict]:
    """Fetch all bboxes for a document and cache them.

    Call this once at the start of processing a document's chunks.

    Args:
        document_id: Document UUID

    Returns:
        List of bbox dicts
    """
    if document_id in _bbox_cache:
        return _bbox_cache[document_id]

    try:
        from app.services.bounding_box_service import get_bounding_box_service

        bbox_service = get_bounding_box_service()

        # Fetch all bboxes (paginated)
        all_bboxes = []
        page = 1
        batch_size = 1000

        while True:
            batch, total = bbox_service.get_bounding_boxes_for_document(
                document_id=document_id,
                page=page,
                per_page=batch_size,
            )
            all_bboxes.extend(batch)
            if len(all_bboxes) >= total or not batch:
                break
            page += 1

        _bbox_cache[document_id] = all_bboxes
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
