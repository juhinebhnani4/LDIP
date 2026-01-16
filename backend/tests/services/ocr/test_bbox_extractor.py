"""Tests for bounding box extraction from Document AI responses."""

from unittest.mock import MagicMock

from app.models.ocr import OCRBoundingBox
from app.services.ocr.bbox_extractor import (
    _extract_text_from_anchor,
    _get_vertex_coordinate,
    calculate_reading_order,
    extract_bounding_boxes,
)


class TestGetVertexCoordinate:
    """Tests for vertex coordinate extraction."""

    def test_extracts_x_coordinate(self) -> None:
        """Should extract x coordinate from vertex."""
        vertex = MagicMock()
        vertex.x = 0.5
        vertices = [vertex]

        result = _get_vertex_coordinate(vertices, 0, "x")

        assert result == 0.5

    def test_extracts_y_coordinate(self) -> None:
        """Should extract y coordinate from vertex."""
        vertex = MagicMock()
        vertex.y = 0.75
        vertices = [vertex]

        result = _get_vertex_coordinate(vertices, 0, "y")

        assert result == 0.75

    def test_returns_default_for_missing_index(self) -> None:
        """Should return default when vertex index is out of range."""
        vertices: list = []

        result = _get_vertex_coordinate(vertices, 0, "x", default=0.0)

        assert result == 0.0

    def test_returns_default_for_missing_attribute(self) -> None:
        """Should return default when vertex attribute is missing."""
        vertex = MagicMock(spec=[])
        vertices = [vertex]

        result = _get_vertex_coordinate(vertices, 0, "x", default=0.0)

        assert result == 0.0

    def test_returns_default_for_none_value(self) -> None:
        """Should return default when vertex value is None."""
        vertex = MagicMock()
        vertex.x = None
        vertices = [vertex]

        result = _get_vertex_coordinate(vertices, 0, "x", default=0.0)

        assert result == 0.0


class TestExtractTextFromAnchor:
    """Tests for text extraction from Document AI text anchors."""

    def test_extracts_single_segment(self) -> None:
        """Should extract text from single segment."""
        segment = MagicMock()
        segment.start_index = 0
        segment.end_index = 5

        text_anchor = MagicMock()
        text_anchor.text_segments = [segment]

        result = _extract_text_from_anchor(text_anchor, "Hello World")

        assert result == "Hello"

    def test_extracts_multiple_segments(self) -> None:
        """Should concatenate text from multiple segments."""
        segment1 = MagicMock()
        segment1.start_index = 0
        segment1.end_index = 5

        segment2 = MagicMock()
        segment2.start_index = 6
        segment2.end_index = 11

        text_anchor = MagicMock()
        text_anchor.text_segments = [segment1, segment2]

        result = _extract_text_from_anchor(text_anchor, "Hello World")

        assert result == "HelloWorld"

    def test_returns_empty_for_none_anchor(self) -> None:
        """Should return empty string for None anchor."""
        result = _extract_text_from_anchor(None, "Hello")  # type: ignore

        assert result == ""

    def test_returns_empty_for_no_segments(self) -> None:
        """Should return empty string when no segments."""
        text_anchor = MagicMock()
        text_anchor.text_segments = []

        result = _extract_text_from_anchor(text_anchor, "Hello")

        assert result == ""

    def test_handles_missing_start_index(self) -> None:
        """Should default to 0 when start_index is missing."""
        segment = MagicMock()
        segment.start_index = None
        segment.end_index = 5

        text_anchor = MagicMock()
        text_anchor.text_segments = [segment]

        result = _extract_text_from_anchor(text_anchor, "Hello")

        assert result == "Hello"


class TestExtractBoundingBoxes:
    """Tests for bounding box extraction from documents."""

    def _create_mock_document(
        self,
        page_count: int = 1,
        block_count_per_page: int = 1,
    ) -> MagicMock:
        """Create a mock Document AI document.

        Args:
            page_count: Number of pages to create.
            block_count_per_page: Number of blocks per page.

        Returns:
            Mock document.
        """
        document = MagicMock()
        document.text = "Test document text content"
        document.pages = []

        for page_num in range(1, page_count + 1):
            page = MagicMock()
            page.page_number = page_num
            page.blocks = []

            for _ in range(block_count_per_page):
                block = MagicMock()
                block.layout = MagicMock()
                block.layout.confidence = 0.95
                block.layout.bounding_poly = MagicMock()

                # Create 4 vertices for rectangle
                vertices = []
                for _i, (x, y) in enumerate([(0.1, 0.2), (0.3, 0.2), (0.3, 0.4), (0.1, 0.4)]):
                    v = MagicMock()
                    v.x = x
                    v.y = y
                    vertices.append(v)

                block.layout.bounding_poly.normalized_vertices = vertices

                # Text anchor
                segment = MagicMock()
                segment.start_index = 0
                segment.end_index = 4

                block.layout.text_anchor = MagicMock()
                block.layout.text_anchor.text_segments = [segment]

                page.blocks.append(block)

            document.pages.append(page)

        return document

    def test_extracts_boxes_from_single_page(self) -> None:
        """Should extract bounding boxes from a single page."""
        document = self._create_mock_document(page_count=1, block_count_per_page=2)

        result = extract_bounding_boxes(document)

        assert len(result) == 2
        assert result[0].page == 1

    def test_extracts_boxes_from_multiple_pages(self) -> None:
        """Should extract bounding boxes from multiple pages."""
        document = self._create_mock_document(page_count=3, block_count_per_page=1)

        result = extract_bounding_boxes(document)

        assert len(result) == 3
        assert result[0].page == 1
        assert result[1].page == 2
        assert result[2].page == 3

    def test_filters_by_page_number(self) -> None:
        """Should filter boxes by specific page number."""
        document = self._create_mock_document(page_count=3, block_count_per_page=2)

        result = extract_bounding_boxes(document, page_number=2)

        assert len(result) == 2
        assert all(box.page == 2 for box in result)

    def test_returns_empty_for_none_document(self) -> None:
        """Should return empty list for None document."""
        result = extract_bounding_boxes(None)  # type: ignore

        assert result == []

    def test_returns_empty_for_document_without_pages(self) -> None:
        """Should return empty list when document has no pages."""
        document = MagicMock()
        document.pages = []

        result = extract_bounding_boxes(document)

        assert result == []

    def test_converts_coordinates_to_percentage(self) -> None:
        """Should convert normalized coordinates (0-1) to percentages (0-100)."""
        document = self._create_mock_document(page_count=1, block_count_per_page=1)

        result = extract_bounding_boxes(document)

        # Coordinates were 0.1, 0.2 normalized -> 10, 20 percentage
        assert result[0].x == 10.0
        assert result[0].y == 20.0
        # Width was 0.3 - 0.1 = 0.2 -> 20%
        assert result[0].width == 20.0
        # Height was 0.4 - 0.2 = 0.2 -> 20%
        assert result[0].height == 20.0

    def test_includes_confidence_score(self) -> None:
        """Should include confidence score from layout."""
        document = self._create_mock_document(page_count=1, block_count_per_page=1)

        result = extract_bounding_boxes(document)

        assert result[0].confidence == 0.95

    def test_applies_reading_order_by_default(self) -> None:
        """Should apply reading order by default."""
        document = self._create_mock_document(page_count=1, block_count_per_page=2)

        result = extract_bounding_boxes(document)

        # All boxes should have reading_order_index assigned
        assert all(box.reading_order_index is not None for box in result)
        assert result[0].reading_order_index == 0
        assert result[1].reading_order_index == 1

    def test_skips_reading_order_when_disabled(self) -> None:
        """Should skip reading order calculation when disabled."""
        document = self._create_mock_document(page_count=1, block_count_per_page=2)

        result = extract_bounding_boxes(document, apply_reading_order=False)

        # All boxes should have None reading_order_index
        assert all(box.reading_order_index is None for box in result)


class TestCalculateReadingOrder:
    """Tests for reading order calculation."""

    def test_empty_list(self) -> None:
        """Should return empty list for empty input."""
        result = calculate_reading_order([])
        assert result == []

    def test_single_box(self) -> None:
        """Should assign index 0 to single box."""
        boxes = [
            OCRBoundingBox(page=1, x=10.0, y=10.0, width=20.0, height=5.0, text="Hello"),
        ]

        result = calculate_reading_order(boxes)

        assert len(result) == 1
        assert result[0].reading_order_index == 0

    def test_horizontal_ordering(self) -> None:
        """Should order boxes left to right on same line."""
        boxes = [
            OCRBoundingBox(page=1, x=50.0, y=10.0, width=20.0, height=5.0, text="World"),
            OCRBoundingBox(page=1, x=10.0, y=10.0, width=20.0, height=5.0, text="Hello"),
        ]

        result = calculate_reading_order(boxes)

        # "Hello" (x=10) should come before "World" (x=50)
        assert result[0].text == "Hello"
        assert result[0].reading_order_index == 0
        assert result[1].text == "World"
        assert result[1].reading_order_index == 1

    def test_vertical_ordering(self) -> None:
        """Should order boxes top to bottom on different lines."""
        boxes = [
            OCRBoundingBox(page=1, x=10.0, y=50.0, width=20.0, height=5.0, text="Second"),
            OCRBoundingBox(page=1, x=10.0, y=10.0, width=20.0, height=5.0, text="First"),
        ]

        result = calculate_reading_order(boxes)

        # "First" (y=10) should come before "Second" (y=50)
        assert result[0].text == "First"
        assert result[0].reading_order_index == 0
        assert result[1].text == "Second"
        assert result[1].reading_order_index == 1

    def test_multiline_ordering(self) -> None:
        """Should order boxes top-to-bottom, then left-to-right."""
        boxes = [
            # Line 2
            OCRBoundingBox(page=1, x=50.0, y=30.0, width=20.0, height=5.0, text="D"),
            OCRBoundingBox(page=1, x=10.0, y=30.0, width=20.0, height=5.0, text="C"),
            # Line 1
            OCRBoundingBox(page=1, x=50.0, y=10.0, width=20.0, height=5.0, text="B"),
            OCRBoundingBox(page=1, x=10.0, y=10.0, width=20.0, height=5.0, text="A"),
        ]

        result = calculate_reading_order(boxes)

        # Expected order: A, B, C, D (top-to-bottom, left-to-right)
        assert [box.text for box in result] == ["A", "B", "C", "D"]
        assert [box.reading_order_index for box in result] == [0, 1, 2, 3]

    def test_y_tolerance_groups_nearby_boxes(self) -> None:
        """Should group boxes within y_tolerance as same line."""
        boxes = [
            OCRBoundingBox(page=1, x=50.0, y=10.5, width=20.0, height=5.0, text="B"),
            OCRBoundingBox(page=1, x=10.0, y=10.0, width=20.0, height=5.0, text="A"),
        ]

        # Default tolerance of 2.0 should group these as same line
        result = calculate_reading_order(boxes, y_tolerance=2.0)

        # "A" should come before "B" (same line, left-to-right)
        assert result[0].text == "A"
        assert result[1].text == "B"

    def test_preserves_original_box_data(self) -> None:
        """Should preserve all original box data."""
        boxes = [
            OCRBoundingBox(
                page=1,
                x=10.0,
                y=10.0,
                width=20.0,
                height=5.0,
                text="Test",
                confidence=0.95,
            ),
        ]

        result = calculate_reading_order(boxes)

        assert result[0].page == 1
        assert result[0].x == 10.0
        assert result[0].y == 10.0
        assert result[0].width == 20.0
        assert result[0].height == 5.0
        assert result[0].text == "Test"
        assert result[0].confidence == 0.95
        assert result[0].reading_order_index == 0
