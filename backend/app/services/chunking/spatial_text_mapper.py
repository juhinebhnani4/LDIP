"""Spatial text mapper — bridges Docling layout blocks with Document AI text.

Maps Document AI bounding boxes (with OCR text and character offsets) to
Docling layout blocks (with structural types and reading order) using
Intersection-over-Self (IoS) spatial matching.

This is the standard industry approach (used by Docling's LayoutPostprocessor
and Unstructured.io's merge_inferred_with_extracted_layout) for two-tool
pipelines where one tool provides layout structure and another provides text.

Architecture:
    Google Document AI  →  text + bounding boxes (paragraph-level)
    Docling             →  layout blocks (heading, table, paragraph, figure, stamp)
    SpatialTextMapper   →  merges both by matching bbox overlaps per page

Coordinate systems:
    Document AI bboxes: percentage (0-100) for x, y, width, height
    Docling LayoutBlock.bbox: normalized (0-1) for x, y, width, height
    All IoS calculations use normalized (0-1) coordinates internally.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.services.table_extraction.models import (
    BoundingBox,
    DocumentLayout,
    LayoutBlock,
)

logger = structlog.get_logger(__name__)

# Minimum IoS to assign a Document AI bbox to a layout block.
# 0.5 means at least half the bbox's area must be inside the block.
# This is the standard threshold used by Docling's LayoutPostprocessor.
IOS_THRESHOLD = 0.5

# Block types that are NOT expected to contain searchable text.
# We skip spatial matching for these — they should remain textless.
NON_TEXT_BLOCK_TYPES = frozenset({"figure", "stamp", "picture", "seal", "signature"})


@dataclass(frozen=True, slots=True)
class Rect:
    """Axis-aligned rectangle in normalized (0-1) coordinates."""

    x1: float  # left
    y1: float  # top
    x2: float  # right
    y2: float  # bottom

    @property
    def area(self) -> float:
        w = max(0.0, self.x2 - self.x1)
        h = max(0.0, self.y2 - self.y1)
        return w * h

    def intersection_area(self, other: Rect) -> float:
        xi1 = max(self.x1, other.x1)
        yi1 = max(self.y1, other.y1)
        xi2 = min(self.x2, other.x2)
        yi2 = min(self.y2, other.y2)
        w = max(0.0, xi2 - xi1)
        h = max(0.0, yi2 - yi1)
        return w * h


def _layout_bbox_to_rect(bbox: BoundingBox) -> Rect:
    """Convert a Docling LayoutBlock BoundingBox (0-1) to Rect."""
    return Rect(
        x1=bbox.x,
        y1=bbox.y,
        x2=bbox.x + bbox.width,
        y2=bbox.y + bbox.height,
    )


def _docai_bbox_to_rect(bbox_dict: dict) -> Rect:
    """Convert a Document AI bbox dict (0-100 percentage) to Rect (0-1).

    Document AI bboxes use percentage coordinates (0-100).
    We normalize to (0-1) for comparison with Docling blocks.
    """
    x = bbox_dict.get("x", 0.0) / 100.0
    y = bbox_dict.get("y", 0.0) / 100.0
    w = bbox_dict.get("width", 0.0) / 100.0
    h = bbox_dict.get("height", 0.0) / 100.0
    return Rect(x1=x, y1=y, x2=x + w, y2=y + h)


def _compute_ios(text_rect: Rect, block_rect: Rect) -> float:
    """Compute Intersection-over-Self for a text bbox against a layout block.

    IoS = intersection_area(text, block) / area(text)

    This metric answers: "What fraction of the text bbox is inside the block?"
    A small text bbox fully inside a large block will have IoS ≈ 1.0.
    IoS is preferred over IoU for this use case (Docling paper, arXiv:2509.11720).
    """
    text_area = text_rect.area
    if text_area <= 0:
        return 0.0
    return text_rect.intersection_area(block_rect) / text_area


def enrich_layout_with_text(
    layout: DocumentLayout,
    docai_bboxes: list[dict],
    full_text: str,
) -> DocumentLayout:
    """Map Document AI text to Docling layout blocks using IoS spatial matching.

    For each layout block that lacks text_content, finds overlapping Document AI
    bounding boxes on the same page, computes IoS scores, and assigns text from
    bboxes with IoS >= threshold. Also populates text_start / text_end offsets
    for deterministic downstream bbox linking.

    Orphan bboxes (not assigned to any block) are added as synthetic paragraph
    blocks to ensure no text is lost.

    Args:
        layout: DocumentLayout from Docling (blocks may lack text_content).
        docai_bboxes: All Document AI bounding boxes for the document.
            Each dict has: page_number, x, y, width, height, text,
            text_start_offset, text_end_offset, reading_order_index.
        full_text: Full extracted text from Document AI.

    Returns:
        The same DocumentLayout, mutated in place, with text_content and
        text_start/text_end populated on blocks. Additional synthetic
        blocks may be appended for orphan text.
    """
    if not layout.blocks or not docai_bboxes:
        return layout

    # --- Step 1: Index Document AI bboxes by page ---
    bboxes_by_page: dict[int, list[dict]] = {}
    for bbox in docai_bboxes:
        page = bbox.get("page_number")
        if page is not None:
            bboxes_by_page.setdefault(page, []).append(bbox)

    # Sort bboxes within each page by reading order
    for page_bboxes in bboxes_by_page.values():
        page_bboxes.sort(key=lambda b: b.get("reading_order_index", 0) or 0)

    # --- Step 2: Index layout blocks by page ---
    blocks_by_page: dict[int, list[LayoutBlock]] = {}
    for block in layout.blocks:
        blocks_by_page.setdefault(block.page_number, []).append(block)

    # Pre-compute Rect for each block
    block_rects: dict[int, Rect] = {}
    for block in layout.blocks:
        block_rects[id(block)] = _layout_bbox_to_rect(block.bbox)

    # Track which bboxes get assigned (by their index in docai_bboxes)
    assigned_bbox_indices: set[int] = set()

    # Build a global bbox index for quick lookup
    bbox_global_index: dict[int, int] = {}  # id(bbox_dict) -> index in docai_bboxes
    for i, bbox in enumerate(docai_bboxes):
        bbox_global_index[id(bbox)] = i

    # --- Step 3: For each block without text, find matching bboxes ---
    blocks_enriched = 0
    blocks_skipped_has_text = 0
    blocks_skipped_non_text = 0

    for block in layout.blocks:
        # Skip blocks that already have text from Docling (e.g., headings, or
        # tables that Layer 1 successfully extracted via export_to_markdown)
        if block.text_content and block.text_content.strip():
            blocks_skipped_has_text += 1
            # Still try to set text_start/text_end if missing
            if block.text_start is None and full_text:
                _set_offsets_from_text_content(block, full_text)
            continue

        # Skip non-text blocks (figures, stamps) — they shouldn't have text
        if block.block_type in NON_TEXT_BLOCK_TYPES:
            blocks_skipped_non_text += 1
            continue

        # Get bboxes on the same page
        page_bboxes = bboxes_by_page.get(block.page_number, [])
        if not page_bboxes:
            continue

        block_rect = block_rects[id(block)]

        # Compute IoS for each bbox against this block
        matched_bboxes: list[dict] = []
        for bbox in page_bboxes:
            bbox_rect = _docai_bbox_to_rect(bbox)
            ios = _compute_ios(bbox_rect, block_rect)
            if ios >= IOS_THRESHOLD:
                matched_bboxes.append(bbox)
                # Mark as assigned
                global_idx = bbox_global_index.get(id(bbox))
                if global_idx is not None:
                    assigned_bbox_indices.add(global_idx)

        if not matched_bboxes:
            continue

        # Sort matched bboxes by reading order for correct text sequence
        matched_bboxes.sort(key=lambda b: b.get("reading_order_index", 0) or 0)

        # Concatenate text from matched bboxes
        texts = [b.get("text", "") for b in matched_bboxes if b.get("text")]
        if not texts:
            continue

        block.text_content = "\n".join(texts)

        # Set character offsets from matched bboxes for deterministic linking
        offsets = [
            (b.get("text_start_offset"), b.get("text_end_offset"))
            for b in matched_bboxes
            if b.get("text_start_offset") is not None
            and b.get("text_end_offset") is not None
        ]
        if offsets:
            block.text_start = min(s for s, _ in offsets)
            block.text_end = max(e for _, e in offsets)

        blocks_enriched += 1

    # --- Step 4: Handle orphan bboxes (not assigned to any block) ---
    orphan_bboxes: list[dict] = []
    for i, bbox in enumerate(docai_bboxes):
        if i not in assigned_bbox_indices:
            text = bbox.get("text", "")
            if text and text.strip():
                orphan_bboxes.append(bbox)

    orphan_blocks_created = 0
    if orphan_bboxes:
        orphan_blocks_created = _create_orphan_blocks(layout, orphan_bboxes, full_text)

    logger.info(
        "spatial_text_mapping_complete",
        document_id=layout.document_id,
        total_blocks=len(layout.blocks),
        blocks_enriched=blocks_enriched,
        blocks_already_had_text=blocks_skipped_has_text,
        blocks_non_text_skipped=blocks_skipped_non_text,
        total_bboxes=len(docai_bboxes),
        assigned_bboxes=len(assigned_bbox_indices),
        orphan_bboxes=len(orphan_bboxes),
        orphan_blocks_created=orphan_blocks_created,
    )

    return layout


def _set_offsets_from_text_content(block: LayoutBlock, full_text: str) -> None:
    """Try to find text_start/text_end for a block that already has text_content.

    Uses exact substring search. Only sets offsets if the text appears exactly once
    to avoid ambiguity (e.g., repeated headings).
    """
    text = block.text_content
    if not text:
        return

    pos = full_text.find(text)
    if pos < 0:
        return

    # Check for uniqueness — only set offsets if the text appears once
    second_pos = full_text.find(text, pos + 1)
    if second_pos >= 0:
        return  # Ambiguous — text appears multiple times

    block.text_start = pos
    block.text_end = pos + len(text)


def _create_orphan_blocks(
    layout: DocumentLayout,
    orphan_bboxes: list[dict],
    full_text: str,
) -> int:
    """Create synthetic paragraph blocks for orphan bboxes.

    Groups orphan bboxes by page and creates one paragraph block per
    contiguous group (adjacent reading order indices) to avoid fragmenting
    text into tiny blocks.

    Args:
        layout: DocumentLayout to append blocks to (mutated in place).
        orphan_bboxes: Bboxes not assigned to any layout block.
        full_text: Full document text for offset reference.

    Returns:
        Number of synthetic blocks created.
    """
    # Group orphans by page
    by_page: dict[int, list[dict]] = {}
    for bbox in orphan_bboxes:
        page = bbox.get("page_number")
        if page is not None:
            by_page.setdefault(page, []).append(bbox)

    created = 0
    max_reading_order = max((b.reading_order for b in layout.blocks), default=-1)

    for page, page_orphans in sorted(by_page.items()):
        # Sort by reading order
        page_orphans.sort(key=lambda b: b.get("reading_order_index", 0) or 0)

        # Group contiguous orphans into blocks
        groups: list[list[dict]] = []
        current_group: list[dict] = [page_orphans[0]]

        for i in range(1, len(page_orphans)):
            prev_order = current_group[-1].get("reading_order_index", 0) or 0
            curr_order = page_orphans[i].get("reading_order_index", 0) or 0

            # If reading order gap > 2, start a new group
            # (allows for small gaps from figures/stamps between paragraphs)
            if curr_order - prev_order > 2:
                groups.append(current_group)
                current_group = [page_orphans[i]]
            else:
                current_group.append(page_orphans[i])

        groups.append(current_group)

        for group in groups:
            texts = [b.get("text", "") for b in group if b.get("text")]
            if not texts:
                continue

            text_content = "\n".join(texts)

            # Compute bounding box that encompasses the group
            all_x1 = [b.get("x", 0.0) / 100.0 for b in group]
            all_y1 = [b.get("y", 0.0) / 100.0 for b in group]
            all_x2 = [(b.get("x", 0.0) + b.get("width", 0.0)) / 100.0 for b in group]
            all_y2 = [(b.get("y", 0.0) + b.get("height", 0.0)) / 100.0 for b in group]

            merged_x = min(all_x1)
            merged_y = min(all_y1)
            merged_x2 = max(all_x2)
            merged_y2 = max(all_y2)

            # Character offsets from the group
            offsets = [
                (b.get("text_start_offset"), b.get("text_end_offset"))
                for b in group
                if b.get("text_start_offset") is not None
                and b.get("text_end_offset") is not None
            ]
            text_start = min(s for s, _ in offsets) if offsets else None
            text_end = max(e for _, e in offsets) if offsets else None

            max_reading_order += 1

            orphan_block = LayoutBlock(
                block_type="paragraph",
                page_number=page,
                bbox=BoundingBox(
                    page=page,
                    x=merged_x,
                    y=merged_y,
                    width=merged_x2 - merged_x,
                    height=merged_y2 - merged_y,
                ),
                text_start=text_start,
                text_end=text_end,
                reading_order=max_reading_order,
                confidence=0.8,  # Slightly lower — synthetic, not model-detected
                text_content=text_content,
            )
            layout.blocks.append(orphan_block)
            created += 1

    return created


def fetch_all_bboxes_for_document(bbox_service, document_id: str) -> list[dict]:
    """Fetch all bounding boxes for a document using paginated queries.

    Reuses the same pagination pattern as bbox_linker.link_chunks_to_bboxes.

    Args:
        bbox_service: BoundingBoxService instance.
        document_id: Document UUID.

    Returns:
        All bounding boxes as a list of dicts.
    """
    all_bboxes: list[dict] = []
    page = 1
    batch_size = 500

    while True:
        batch, total = bbox_service.get_bounding_boxes_for_document(
            document_id=document_id,
            page=page,
            per_page=batch_size,
            include_text=True,
        )
        all_bboxes.extend(batch)

        if len(all_bboxes) >= total or not batch:
            break
        page += 1

    return all_bboxes
