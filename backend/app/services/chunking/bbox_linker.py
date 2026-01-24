"""Bounding box linker for chunks.

Links chunks to their source bounding boxes using fuzzy text matching.
This enables click-to-highlight functionality in the PDF viewer.

Story 6.1: Optimized from O(n²) to O(n) by pre-indexing bboxes by page.
"""

from collections import Counter, defaultdict
from uuid import UUID

import structlog
from rapidfuzz import fuzz

from app.services.bounding_box_service import BoundingBoxService
from app.services.chunking.parent_child_chunker import ChunkData

logger = structlog.get_logger(__name__)

# Threshold for fuzzy text matching (0-100)
# 50 allows for OCR errors, multilingual text, and formatting differences
# while still avoiding false matches. Higher thresholds caused many chunks
# to have NULL page_number which breaks citation/timeline source links.
MATCH_THRESHOLD = 50

# Maximum number of bounding boxes to check per chunk
MAX_BBOX_WINDOW = 100


class BboxPageIndex:
    """Pre-indexed bounding boxes by page number for O(n) lookup.

    Story 6.1: Instead of scanning all 29K bboxes for each chunk,
    we index by page and only search relevant pages.
    """

    def __init__(self, all_bboxes: list[dict]) -> None:
        """Build page index from all bboxes.

        Args:
            all_bboxes: All bounding boxes (already sorted by reading order).
        """
        self.by_page: dict[int, list[dict]] = defaultdict(list)
        self.bbox_texts_by_page: dict[int, list[str]] = defaultdict(list)
        self.all_pages: list[int] = []

        # Index bboxes by page
        for bbox in all_bboxes:
            page = bbox.get("page_number")
            if page is not None:
                self.by_page[page].append(bbox)
                self.bbox_texts_by_page[page].append(
                    _normalize_text(bbox.get("text", ""))
                )

        self.all_pages = sorted(self.by_page.keys())

    def get_bboxes_for_pages(
        self, pages: list[int]
    ) -> tuple[list[dict], list[str]]:
        """Get bboxes and their normalized texts for specific pages.

        Args:
            pages: List of page numbers to retrieve.

        Returns:
            Tuple of (bboxes, normalized_texts) for the requested pages.
        """
        bboxes = []
        texts = []
        for page in sorted(pages):
            bboxes.extend(self.by_page.get(page, []))
            texts.extend(self.bbox_texts_by_page.get(page, []))
        return bboxes, texts

    def estimate_pages_for_chunk(
        self, chunk_text: str, sample_pages: int = 3
    ) -> list[int]:
        """Estimate which pages a chunk likely belongs to.

        Uses quick fuzzy matching against first bbox of each page.

        Args:
            chunk_text: Normalized chunk text sample.
            sample_pages: Number of candidate pages to return.

        Returns:
            List of likely page numbers (sorted by match score).
        """
        if not self.all_pages:
            return []

        # Quick match against concatenated text of each page
        page_scores: list[tuple[int, float]] = []

        for page in self.all_pages:
            page_texts = self.bbox_texts_by_page.get(page, [])
            if not page_texts:
                continue

            # Sample the page text (first 2000 chars)
            page_sample = " ".join(page_texts)[:2000]
            score = fuzz.partial_ratio(chunk_text[:200], page_sample)
            page_scores.append((page, score))

        # Sort by score descending
        page_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top candidate pages
        return [p for p, _ in page_scores[:sample_pages]]


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
    page_index: BboxPageIndex | None = None,
) -> tuple[list[UUID], int | None]:
    """Find bounding boxes that contain the chunk's text.

    Uses fuzzy matching to handle OCR artifacts and minor text differences.

    Story 6.1: When page_index is provided, uses optimized O(n) page-based
    lookup instead of O(n²) full scan.

    Args:
        chunk: Chunk to find bounding boxes for.
        document_id: Document UUID for logging.
        all_bboxes: All bounding boxes for the document (ordered by reading order).
        page_index: Optional pre-built page index for O(n) lookup.

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

    # Story 6.1: Use page index for optimized lookup if available
    if page_index is not None:
        return await _link_chunk_with_page_index(
            chunk=chunk,
            document_id=document_id,
            page_index=page_index,
            chunk_text_normalized=chunk_text_normalized,
            chunk_sample=chunk_sample,
        )

    # Fallback to original O(n²) algorithm if no page index
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


async def _link_chunk_with_page_index(
    chunk: ChunkData,
    document_id: str,
    page_index: BboxPageIndex,
    chunk_text_normalized: str,
    chunk_sample: str,
) -> tuple[list[UUID], int | None]:
    """Optimized chunk linking using page index.

    Story 6.1: O(n) complexity by only searching relevant pages.

    Args:
        chunk: Chunk to link.
        document_id: Document UUID for logging.
        page_index: Pre-built page index.
        chunk_text_normalized: Normalized full chunk text.
        chunk_sample: First 500 chars of normalized chunk text.

    Returns:
        Tuple of (list of bbox_ids, most common page_number).
    """
    matched_bbox_ids: list[UUID] = []
    page_counts: Counter[int] = Counter()

    # Find candidate pages (typically 1-3 pages per chunk)
    candidate_pages = page_index.estimate_pages_for_chunk(chunk_sample)

    if not candidate_pages:
        return [], None

    # Get bboxes only for candidate pages
    page_bboxes, page_texts = page_index.get_bboxes_for_pages(candidate_pages)

    if not page_bboxes:
        return [], None

    # Now do sliding window search on the reduced set
    best_match_score = 0
    best_match_start = -1
    window_size = min(MAX_BBOX_WINDOW, len(page_bboxes))

    # Optimized: search with larger step size initially
    step_size = max(1, window_size // 4)

    for start_idx in range(0, len(page_bboxes) - window_size + 1, step_size):
        window_text = " ".join(page_texts[start_idx : start_idx + window_size])
        match_score = fuzz.partial_ratio(chunk_sample, window_text[:1500])

        if match_score > best_match_score:
            best_match_score = match_score
            best_match_start = start_idx

        if match_score >= 95:
            break

    # If coarse search found something, do fine search around it
    if best_match_score >= MATCH_THRESHOLD - 10 and best_match_start >= 0:
        fine_start = max(0, best_match_start - step_size)
        fine_end = min(len(page_bboxes) - window_size + 1, best_match_start + step_size)

        for start_idx in range(fine_start, fine_end):
            window_text = " ".join(page_texts[start_idx : start_idx + window_size])
            match_score = fuzz.partial_ratio(chunk_sample, window_text[:1500])

            if match_score > best_match_score:
                best_match_score = match_score
                best_match_start = start_idx

            if match_score >= 95:
                break

    # Extract matched bboxes
    if best_match_score >= MATCH_THRESHOLD and best_match_start >= 0:
        chunk_words = set(chunk_text_normalized.split()[:50])

        for idx in range(best_match_start, min(best_match_start + window_size, len(page_bboxes))):
            bbox = page_bboxes[idx]
            bbox_text = page_texts[idx]

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

            if len(matched_bbox_ids) >= 50:
                break

    most_common_page = page_counts.most_common(1)[0][0] if page_counts else None

    logger.debug(
        "chunk_bbox_linking_complete",
        document_id=document_id,
        chunk_index=chunk.chunk_index,
        chunk_type=chunk.chunk_type,
        bbox_count=len(matched_bbox_ids),
        page=most_common_page,
        match_score=best_match_score,
        optimized=True,
        candidate_pages=candidate_pages,
    )

    return matched_bbox_ids, most_common_page


async def link_chunks_to_bboxes(
    chunks: list[ChunkData],
    document_id: str,
    bbox_service: BoundingBoxService,
    use_optimized: bool = True,
) -> None:
    """Link all chunks to their source bounding boxes.

    Modifies chunks in place, setting bbox_ids and page_number.

    Story 6.1: Uses optimized O(n) page-indexed lookup by default.

    Args:
        chunks: List of chunks to link (modified in place).
        document_id: Document UUID.
        bbox_service: BoundingBoxService for retrieving bboxes.
        use_optimized: If True, use page-indexed O(n) algorithm. Default True.
    """
    import time

    start_time = time.time()

    logger.info(
        "linking_chunks_to_bboxes_start",
        document_id=document_id,
        chunk_count=len(chunks),
        optimized=use_optimized,
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

    load_time = time.time() - start_time

    logger.info(
        "loaded_bboxes_for_linking",
        document_id=document_id,
        bbox_count=len(all_bboxes),
        load_time_seconds=round(load_time, 2),
    )

    # Story 6.1: Build page index for O(n) lookup
    page_index = BboxPageIndex(all_bboxes) if use_optimized else None

    if page_index:
        logger.info(
            "bbox_page_index_built",
            document_id=document_id,
            page_count=len(page_index.all_pages),
            pages=page_index.all_pages[:10],  # Log first 10 pages
        )

    # Link each chunk
    linked_count = 0
    link_start_time = time.time()

    for chunk in chunks:
        bbox_ids, page_number = await link_chunk_to_bboxes(
            chunk=chunk,
            document_id=document_id,
            all_bboxes=all_bboxes,
            page_index=page_index,
        )

        # Update chunk with results
        chunk.bbox_ids = bbox_ids
        chunk.page_number = page_number

        if bbox_ids:
            linked_count += 1

    link_time = time.time() - link_start_time
    total_time = time.time() - start_time

    logger.info(
        "linking_chunks_to_bboxes_complete",
        document_id=document_id,
        total_chunks=len(chunks),
        linked_chunks=linked_count,
        link_time_seconds=round(link_time, 2),
        total_time_seconds=round(total_time, 2),
        optimized=use_optimized,
        avg_per_chunk_ms=round((link_time / len(chunks)) * 1000, 1) if chunks else 0,
    )
