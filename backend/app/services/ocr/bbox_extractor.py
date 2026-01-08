"""Bounding box extraction from Google Document AI responses.

Extracts and converts bounding box coordinates from Document AI's
normalized vertices (0-1) to percentage coordinates (0-100).
Includes reading order calculation for proper text flow.
"""

from typing import TYPE_CHECKING

import structlog

from app.models.ocr import OCRBoundingBox

if TYPE_CHECKING:
    from google.cloud.documentai_v1 import Document

logger = structlog.get_logger(__name__)


def calculate_reading_order(
    bounding_boxes: list[OCRBoundingBox],
    y_tolerance: float = 2.0,
) -> list[OCRBoundingBox]:
    """Calculate reading order for bounding boxes.

    Algorithm:
    1. Sort by y (top to bottom)
    2. Group boxes at similar y-levels into "lines"
    3. Within each line, sort by x (left to right)
    4. Assign reading_order_index to each box

    Args:
        bounding_boxes: List of OCRBoundingBox to order.
        y_tolerance: Percentage of y-coordinate tolerance for same line (default 2.0).

    Returns:
        List of OCRBoundingBox with reading_order_index assigned.
    """
    if not bounding_boxes:
        return []

    # Group boxes by approximate y-position (within tolerance)
    lines: list[list[OCRBoundingBox]] = []

    sorted_by_y = sorted(bounding_boxes, key=lambda b: b.y)

    current_line: list[OCRBoundingBox] = [sorted_by_y[0]]
    current_y = sorted_by_y[0].y

    for bbox in sorted_by_y[1:]:
        if abs(bbox.y - current_y) <= y_tolerance:
            current_line.append(bbox)
        else:
            # Sort current line by x (left to right) and add to lines
            lines.append(sorted(current_line, key=lambda b: b.x))
            current_line = [bbox]
            current_y = bbox.y

    # Don't forget the last line
    if current_line:
        lines.append(sorted(current_line, key=lambda b: b.x))

    # Flatten and assign reading order
    ordered: list[OCRBoundingBox] = []
    for line in lines:
        for bbox in line:
            bbox.reading_order_index = len(ordered)
            ordered.append(bbox)

    logger.debug(
        "reading_order_calculated",
        total_boxes=len(ordered),
        total_lines=len(lines),
    )

    return ordered


def _get_vertex_coordinate(
    vertices: list, index: int, attr: str, default: float = 0.0
) -> float:
    """Safely extract a coordinate from normalized vertices.

    Document AI may omit vertices with value 0, so we handle missing data.

    Args:
        vertices: List of normalized vertices from Document AI.
        index: Vertex index (0-3 for rectangle corners).
        attr: Attribute name ('x' or 'y').
        default: Default value if vertex or attribute is missing.

    Returns:
        Coordinate value (0-1 range).
    """
    if index >= len(vertices):
        return default
    vertex = vertices[index]
    return getattr(vertex, attr, default) or default


def _extract_bbox_from_layout(
    layout: "Document.Page.Layout",  # type: ignore[name-defined]
    page_number: int,
) -> OCRBoundingBox | None:
    """Extract bounding box from a Document AI layout element.

    Args:
        layout: Layout element containing bounding polygon.
        page_number: Page number (1-indexed).

    Returns:
        OCRBoundingBox with percentage coordinates, or None if invalid.
    """
    if not layout or not layout.bounding_poly:
        return None

    vertices = list(layout.bounding_poly.normalized_vertices)
    if len(vertices) < 4:
        return None

    # Extract corners (top-left, top-right, bottom-right, bottom-left)
    x1 = _get_vertex_coordinate(vertices, 0, "x")
    y1 = _get_vertex_coordinate(vertices, 0, "y")
    x2 = _get_vertex_coordinate(vertices, 2, "x")
    y2 = _get_vertex_coordinate(vertices, 2, "y")

    # Convert normalized (0-1) to percentage (0-100)
    x = x1 * 100
    y = y1 * 100
    width = (x2 - x1) * 100
    height = (y2 - y1) * 100

    # Skip invalid boxes
    if width <= 0 or height <= 0:
        return None

    # Get text content
    text = ""
    if hasattr(layout, "text_anchor") and layout.text_anchor:
        # Text will be extracted separately from full document text
        pass

    # Get confidence
    confidence = layout.confidence if hasattr(layout, "confidence") else None

    return OCRBoundingBox(
        page=page_number,
        x=x,
        y=y,
        width=width,
        height=height,
        text=text,  # Text filled in by caller
        confidence=confidence,
    )


def extract_bounding_boxes(
    document: "Document",  # type: ignore[name-defined]
    page_number: int | None = None,
    apply_reading_order: bool = True,
) -> list[OCRBoundingBox]:
    """Extract all bounding boxes from a Document AI response.

    Extracts bounding boxes from document blocks (paragraphs/lines) and
    converts coordinates to percentage-based system (0-100).

    Args:
        document: Document AI response document.
        page_number: Optional specific page number (1-indexed).
                    If None, extracts from all pages.
        apply_reading_order: Whether to calculate and assign reading order (default True).

    Returns:
        List of OCRBoundingBox with text, coordinates, and reading order.
    """
    bounding_boxes: list[OCRBoundingBox] = []

    if not document or not document.pages:
        return bounding_boxes

    full_text = document.text or ""

    for page in document.pages:
        current_page = page.page_number  # 1-indexed in Document AI

        # Skip if filtering by specific page
        if page_number is not None and current_page != page_number:
            continue

        # Collect page-level boxes for reading order calculation
        page_boxes: list[OCRBoundingBox] = []

        # Extract bounding boxes from blocks (paragraph-level)
        for block in page.blocks:
            bbox = _extract_bbox_from_layout(block.layout, current_page)
            if bbox:
                # Extract text from text anchor
                text = _extract_text_from_anchor(
                    block.layout.text_anchor, full_text
                )
                bbox.text = text
                page_boxes.append(bbox)

        # Apply reading order for this page
        if apply_reading_order and page_boxes:
            page_boxes = calculate_reading_order(page_boxes)

        bounding_boxes.extend(page_boxes)

    logger.info(
        "bounding_boxes_extracted",
        total_boxes=len(bounding_boxes),
        page_filter=page_number,
        reading_order_applied=apply_reading_order,
    )

    return bounding_boxes


def extract_bounding_boxes_by_token(
    document: "Document",  # type: ignore[name-defined]
    page_number: int | None = None,
    apply_reading_order: bool = True,
) -> list[OCRBoundingBox]:
    """Extract bounding boxes at token (word) level.

    More granular extraction for precise text highlighting.

    Args:
        document: Document AI response document.
        page_number: Optional specific page number (1-indexed).
        apply_reading_order: Whether to calculate and assign reading order (default True).

    Returns:
        List of OCRBoundingBox for each token with reading order.
    """
    bounding_boxes: list[OCRBoundingBox] = []

    if not document or not document.pages:
        return bounding_boxes

    full_text = document.text or ""

    for page in document.pages:
        current_page = page.page_number

        if page_number is not None and current_page != page_number:
            continue

        # Collect page-level boxes for reading order calculation
        page_boxes: list[OCRBoundingBox] = []

        # Extract bounding boxes from tokens (word-level)
        for token in page.tokens:
            bbox = _extract_bbox_from_layout(token.layout, current_page)
            if bbox:
                text = _extract_text_from_anchor(
                    token.layout.text_anchor, full_text
                )
                bbox.text = text
                # Token-level confidence
                if hasattr(token.layout, "confidence"):
                    bbox.confidence = token.layout.confidence
                page_boxes.append(bbox)

        # Apply reading order for this page
        if apply_reading_order and page_boxes:
            page_boxes = calculate_reading_order(page_boxes)

        bounding_boxes.extend(page_boxes)

    logger.info(
        "token_bounding_boxes_extracted",
        total_boxes=len(bounding_boxes),
        page_filter=page_number,
        reading_order_applied=apply_reading_order,
    )

    return bounding_boxes


def _extract_text_from_anchor(
    text_anchor: "Document.TextAnchor",  # type: ignore[name-defined]
    full_text: str,
) -> str:
    """Extract text content from a Document AI text anchor.

    Args:
        text_anchor: Text anchor with segment references.
        full_text: Full document text.

    Returns:
        Extracted text string.
    """
    if not text_anchor or not text_anchor.text_segments:
        return ""

    text_parts: list[str] = []
    for segment in text_anchor.text_segments:
        start_idx = int(segment.start_index) if segment.start_index else 0
        end_idx = int(segment.end_index) if segment.end_index else len(full_text)
        text_parts.append(full_text[start_idx:end_idx])

    return "".join(text_parts).strip()
