"""Bounding box linker for chunks.

Links chunks to their source bounding boxes using fuzzy text matching.
This enables click-to-highlight functionality in the PDF viewer.
"""

from collections import Counter
from uuid import UUID

import structlog
from rapidfuzz import fuzz

from app.services.bounding_box_service import BoundingBoxService
from app.services.chunking.parent_child_chunker import ChunkData

logger = structlog.get_logger(__name__)

# Threshold for fuzzy text matching (0-100)
# 80 allows for minor OCR differences while avoiding false matches
MATCH_THRESHOLD = 80

# Maximum number of bounding boxes to check per chunk
MAX_BBOX_WINDOW = 100


def _normalize_text(text: str) -> str:
    """Normalize text for matching.

    Args:
        text: Text to normalize.

    Returns:
        Normalized lowercase text.
    """
    return " ".join(text.lower().split())


async def link_chunk_to_bboxes(
    chunk: ChunkData,
    document_id: str,
    all_bboxes: list[dict],
) -> tuple[list[UUID], int | None]:
    """Find bounding boxes that contain the chunk's text.

    Uses fuzzy matching to handle OCR artifacts and minor text differences.

    Args:
        chunk: Chunk to find bounding boxes for.
        document_id: Document UUID for logging.
        all_bboxes: All bounding boxes for the document (ordered by reading order).

    Returns:
        Tuple of (list of bbox_ids, most common page_number).
    """
    if not all_bboxes or not chunk.content:
        return [], None

    chunk_text_normalized = _normalize_text(chunk.content)

    # Use first portion of chunk for matching (more reliable)
    chunk_sample = chunk_text_normalized[:500]

    matched_bbox_ids: list[UUID] = []
    page_counts: Counter[int] = Counter()

    # Build concatenated text from bboxes in reading order
    # We'll use a sliding window to find where the chunk appears
    best_match_score = 0
    best_match_start = -1

    # Pre-compute normalized bbox texts
    bbox_texts = [_normalize_text(bbox.get("text", "")) for bbox in all_bboxes]

    # Sliding window search
    window_size = min(MAX_BBOX_WINDOW, len(all_bboxes))

    for start_idx in range(len(all_bboxes) - window_size + 1):
        # Build window text
        window_text = " ".join(bbox_texts[start_idx : start_idx + window_size])

        # Quick check: if chunk sample not roughly in window, skip
        match_score = fuzz.partial_ratio(chunk_sample, window_text[:1500])

        if match_score > best_match_score:
            best_match_score = match_score
            best_match_start = start_idx

        # Early exit if we found a great match
        if match_score >= 95:
            break

    # If we found a good match, extract the specific bboxes
    if best_match_score >= MATCH_THRESHOLD and best_match_start >= 0:
        # Get words from chunk for fine-grained matching
        chunk_words = set(chunk_text_normalized.split()[:50])

        # Check bboxes in the matched window
        for idx in range(best_match_start, min(best_match_start + window_size, len(all_bboxes))):
            bbox = all_bboxes[idx]
            bbox_text = bbox_texts[idx]

            # Check if bbox text overlaps with chunk words
            bbox_words = set(bbox_text.split())
            overlap = chunk_words & bbox_words

            if overlap and len(overlap) >= min(2, len(bbox_words)):
                bbox_id = bbox.get("id")
                if bbox_id:
                    try:
                        matched_bbox_ids.append(UUID(bbox_id) if isinstance(bbox_id, str) else bbox_id)
                        page = bbox.get("page_number")
                        if page is not None:
                            page_counts[page] += 1
                    except (ValueError, TypeError):
                        pass

            # Stop if we've matched enough bboxes
            if len(matched_bbox_ids) >= 50:
                break

    # Determine most common page
    most_common_page = page_counts.most_common(1)[0][0] if page_counts else None

    logger.debug(
        "chunk_bbox_linking_complete",
        document_id=document_id,
        chunk_index=chunk.chunk_index,
        chunk_type=chunk.chunk_type,
        bbox_count=len(matched_bbox_ids),
        page=most_common_page,
        match_score=best_match_score,
    )

    return matched_bbox_ids, most_common_page


async def link_chunks_to_bboxes(
    chunks: list[ChunkData],
    document_id: str,
    bbox_service: BoundingBoxService,
) -> None:
    """Link all chunks to their source bounding boxes.

    Modifies chunks in place, setting bbox_ids and page_number.

    Args:
        chunks: List of chunks to link (modified in place).
        document_id: Document UUID.
        bbox_service: BoundingBoxService for retrieving bboxes.
    """
    logger.info(
        "linking_chunks_to_bboxes_start",
        document_id=document_id,
        chunk_count=len(chunks),
    )

    if not chunks:
        return

    # Get all bounding boxes for the document using pagination to avoid OOM
    all_bboxes = []
    bbox_page = 1
    batch_size = 500

    while True:
        bboxes_batch, total = bbox_service.get_bounding_boxes_for_document(
            document_id=document_id,
            page=bbox_page,
            per_page=batch_size,
        )
        all_bboxes.extend(bboxes_batch)

        if len(all_bboxes) >= total or not bboxes_batch:
            break
        bbox_page += 1

    if not all_bboxes:
        logger.warning(
            "no_bboxes_for_document",
            document_id=document_id,
        )
        return

    logger.info(
        "loaded_bboxes_for_linking",
        document_id=document_id,
        bbox_count=len(all_bboxes),
    )

    # Link each chunk
    linked_count = 0
    for chunk in chunks:
        bbox_ids, page_number = await link_chunk_to_bboxes(
            chunk=chunk,
            document_id=document_id,
            all_bboxes=all_bboxes,
        )

        # Update chunk with results
        chunk.bbox_ids = bbox_ids
        chunk.page_number = page_number

        if bbox_ids:
            linked_count += 1

    logger.info(
        "linking_chunks_to_bboxes_complete",
        document_id=document_id,
        total_chunks=len(chunks),
        linked_chunks=linked_count,
    )
