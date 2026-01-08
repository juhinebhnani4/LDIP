"""Tests for OCR validation word extractor."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.ocr_validation import LowConfidenceWord
from app.services.ocr.validation_extractor import (
    ValidationExtractor,
    ValidationExtractorError,
)


class TestValidationExtractor:
    """Tests for ValidationExtractor class."""

    def test_initialization_uses_settings(self) -> None:
        """Should use settings for threshold configuration."""
        with patch("app.services.ocr.validation_extractor.get_settings") as mock_settings:
            mock_settings.return_value.ocr_validation_gemini_threshold = 0.85
            mock_settings.return_value.ocr_validation_human_threshold = 0.50

            with patch("app.services.ocr.validation_extractor.get_service_client") as mock_client:
                mock_client.return_value = MagicMock()
                extractor = ValidationExtractor()

            assert extractor.gemini_threshold == 0.85
            assert extractor.human_threshold == 0.50
            assert extractor.context_chars == 50

    def test_raises_error_when_client_not_configured(self) -> None:
        """Should raise error when database client is None."""
        with patch("app.services.ocr.validation_extractor.get_settings") as mock_settings:
            mock_settings.return_value.ocr_validation_gemini_threshold = 0.85
            mock_settings.return_value.ocr_validation_human_threshold = 0.50

            with patch("app.services.ocr.validation_extractor.get_service_client") as mock_client:
                mock_client.return_value = None
                extractor = ValidationExtractor()

        with pytest.raises(ValidationExtractorError) as exc_info:
            extractor.extract_low_confidence_words("doc-123")

        assert exc_info.value.code == "DATABASE_NOT_CONFIGURED"


class TestExtractLowConfidenceWords:
    """Tests for extract_low_confidence_words method."""

    @pytest.fixture
    def mock_extractor(self) -> ValidationExtractor:
        """Create an extractor with mock client."""
        with patch("app.services.ocr.validation_extractor.get_settings") as mock_settings:
            mock_settings.return_value.ocr_validation_gemini_threshold = 0.85
            mock_settings.return_value.ocr_validation_human_threshold = 0.50

            with patch("app.services.ocr.validation_extractor.get_service_client") as mock_client:
                mock_client.return_value = MagicMock()
                extractor = ValidationExtractor()

        return extractor

    def _create_mock_bounding_boxes(
        self,
        confidences: list[float],
        texts: list[str] | None = None,
    ) -> list[dict]:
        """Create mock bounding box data.

        Args:
            confidences: List of confidence values.
            texts: Optional list of texts.

        Returns:
            List of mock bounding box dictionaries.
        """
        if texts is None:
            texts = [f"word{i}" for i in range(len(confidences))]

        return [
            {
                "id": f"bbox-{i}",
                "page_number": 1,
                "x": 10.0 + i * 10,
                "y": 20.0,
                "width": 8.0,
                "height": 5.0,
                "text": texts[i],
                "confidence": conf,
            }
            for i, conf in enumerate(confidences)
        ]

    def test_returns_empty_when_no_boxes(
        self,
        mock_extractor: ValidationExtractor,
    ) -> None:
        """Should return empty lists when no bounding boxes exist."""
        mock_extractor.client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.return_value.data = None

        gemini_words, human_words = mock_extractor.extract_low_confidence_words("doc-123")

        assert gemini_words == []
        assert human_words == []

    def test_ignores_high_confidence_words(
        self,
        mock_extractor: ValidationExtractor,
    ) -> None:
        """Should not return words with confidence >= gemini threshold."""
        boxes = self._create_mock_bounding_boxes([0.90, 0.95, 0.99])

        mock_result = MagicMock()
        mock_result.data = boxes
        mock_extractor.client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.return_value = mock_result

        gemini_words, human_words = mock_extractor.extract_low_confidence_words("doc-123")

        assert len(gemini_words) == 0
        assert len(human_words) == 0

    def test_routes_medium_confidence_to_gemini(
        self,
        mock_extractor: ValidationExtractor,
    ) -> None:
        """Should route words with confidence < 85% but >= 50% to Gemini."""
        boxes = self._create_mock_bounding_boxes([0.60, 0.70, 0.80])

        mock_result = MagicMock()
        mock_result.data = boxes
        mock_extractor.client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.return_value = mock_result

        gemini_words, human_words = mock_extractor.extract_low_confidence_words("doc-123")

        assert len(gemini_words) == 3
        assert len(human_words) == 0

        # Verify confidence values
        assert all(word.confidence >= 0.50 for word in gemini_words)
        assert all(word.confidence < 0.85 for word in gemini_words)

    def test_routes_low_confidence_to_human_review(
        self,
        mock_extractor: ValidationExtractor,
    ) -> None:
        """Should route words with confidence < 50% to human review."""
        boxes = self._create_mock_bounding_boxes([0.30, 0.40, 0.45])

        mock_result = MagicMock()
        mock_result.data = boxes
        mock_extractor.client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.return_value = mock_result

        gemini_words, human_words = mock_extractor.extract_low_confidence_words("doc-123")

        assert len(gemini_words) == 0
        assert len(human_words) == 3

        # Verify confidence values
        assert all(word.confidence < 0.50 for word in human_words)

    def test_separates_gemini_and_human_words(
        self,
        mock_extractor: ValidationExtractor,
    ) -> None:
        """Should correctly separate words by confidence threshold."""
        # Mix of high, medium, and low confidence
        boxes = self._create_mock_bounding_boxes(
            [0.95, 0.70, 0.40, 0.80, 0.30],
            ["high", "medium1", "low1", "medium2", "low2"],
        )

        mock_result = MagicMock()
        mock_result.data = boxes
        mock_extractor.client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.return_value = mock_result

        gemini_words, human_words = mock_extractor.extract_low_confidence_words("doc-123")

        # 2 words for Gemini (0.70, 0.80)
        assert len(gemini_words) == 2
        assert {w.text for w in gemini_words} == {"medium1", "medium2"}

        # 2 words for human review (0.40, 0.30)
        assert len(human_words) == 2
        assert {w.text for w in human_words} == {"low1", "low2"}

    def test_skips_empty_text(
        self,
        mock_extractor: ValidationExtractor,
    ) -> None:
        """Should skip bounding boxes with empty text."""
        boxes = [
            {"id": "bbox-1", "page_number": 1, "x": 10, "y": 20, "width": 8, "height": 5, "text": "", "confidence": 0.60},
            {"id": "bbox-2", "page_number": 1, "x": 20, "y": 20, "width": 8, "height": 5, "text": "   ", "confidence": 0.60},
            {"id": "bbox-3", "page_number": 1, "x": 30, "y": 20, "width": 8, "height": 5, "text": "valid", "confidence": 0.60},
        ]

        mock_result = MagicMock()
        mock_result.data = boxes
        mock_extractor.client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.return_value = mock_result

        gemini_words, human_words = mock_extractor.extract_low_confidence_words("doc-123")

        assert len(gemini_words) == 1
        assert gemini_words[0].text == "valid"

    def test_extracts_word_coordinates(
        self,
        mock_extractor: ValidationExtractor,
    ) -> None:
        """Should include coordinates in LowConfidenceWord."""
        boxes = [
            {"id": "bbox-1", "page_number": 2, "x": 15.5, "y": 25.5, "width": 12.0, "height": 8.0, "text": "word", "confidence": 0.60},
        ]

        mock_result = MagicMock()
        mock_result.data = boxes
        mock_extractor.client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.return_value = mock_result

        gemini_words, _ = mock_extractor.extract_low_confidence_words("doc-123")

        assert len(gemini_words) == 1
        word = gemini_words[0]
        assert word.bbox_id == "bbox-1"
        assert word.page == 2
        assert word.x == 15.5
        assert word.y == 25.5
        assert word.width == 12.0
        assert word.height == 8.0

    def test_extracts_context(
        self,
        mock_extractor: ValidationExtractor,
    ) -> None:
        """Should extract surrounding context for words."""
        boxes = [
            {"id": "bbox-1", "page_number": 1, "x": 10, "y": 20, "width": 8, "height": 5, "text": "before", "confidence": 0.95},
            {"id": "bbox-2", "page_number": 1, "x": 20, "y": 20, "width": 8, "height": 5, "text": "target", "confidence": 0.60},
            {"id": "bbox-3", "page_number": 1, "x": 30, "y": 20, "width": 8, "height": 5, "text": "after", "confidence": 0.95},
        ]

        mock_result = MagicMock()
        mock_result.data = boxes
        mock_extractor.client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.return_value = mock_result

        gemini_words, _ = mock_extractor.extract_low_confidence_words("doc-123")

        assert len(gemini_words) == 1
        word = gemini_words[0]
        assert word.text == "target"
        # Context should include surrounding words
        assert "before" in word.context_before or word.context_before == "before"
        assert "after" in word.context_after or word.context_after == "after"

    def test_handles_database_error(
        self,
        mock_extractor: ValidationExtractor,
    ) -> None:
        """Should wrap database errors in ValidationExtractorError."""
        mock_extractor.client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.side_effect = Exception("Database error")

        with pytest.raises(ValidationExtractorError) as exc_info:
            mock_extractor.extract_low_confidence_words("doc-123")

        assert exc_info.value.code == "EXTRACTION_FAILED"
        assert "Database error" in str(exc_info.value)


class TestGetWordsByPage:
    """Tests for get_words_by_page method."""

    def test_groups_words_by_page(self) -> None:
        """Should group words by page number."""
        words = [
            LowConfidenceWord(
                bbox_id="1", text="word1", confidence=0.6, page=1,
                context_before="", context_after="", x=0, y=0, width=10, height=5
            ),
            LowConfidenceWord(
                bbox_id="2", text="word2", confidence=0.6, page=2,
                context_before="", context_after="", x=0, y=0, width=10, height=5
            ),
            LowConfidenceWord(
                bbox_id="3", text="word3", confidence=0.6, page=1,
                context_before="", context_after="", x=0, y=0, width=10, height=5
            ),
        ]

        with patch("app.services.ocr.validation_extractor.get_settings") as mock_settings:
            mock_settings.return_value.ocr_validation_gemini_threshold = 0.85
            mock_settings.return_value.ocr_validation_human_threshold = 0.50

            with patch("app.services.ocr.validation_extractor.get_service_client"):
                extractor = ValidationExtractor()

        result = extractor.get_words_by_page(words)

        assert len(result) == 2
        assert len(result[1]) == 2
        assert len(result[2]) == 1
        assert {w.text for w in result[1]} == {"word1", "word3"}
        assert result[2][0].text == "word2"

    def test_returns_empty_dict_for_empty_list(self) -> None:
        """Should return empty dict for empty word list."""
        with patch("app.services.ocr.validation_extractor.get_settings") as mock_settings:
            mock_settings.return_value.ocr_validation_gemini_threshold = 0.85
            mock_settings.return_value.ocr_validation_human_threshold = 0.50

            with patch("app.services.ocr.validation_extractor.get_service_client"):
                extractor = ValidationExtractor()

        result = extractor.get_words_by_page([])

        assert result == {}


class TestExtractContext:
    """Tests for context extraction methods."""

    @pytest.fixture
    def extractor(self) -> ValidationExtractor:
        """Create an extractor for testing."""
        with patch("app.services.ocr.validation_extractor.get_settings") as mock_settings:
            mock_settings.return_value.ocr_validation_gemini_threshold = 0.85
            mock_settings.return_value.ocr_validation_human_threshold = 0.50

            with patch("app.services.ocr.validation_extractor.get_service_client"):
                return ValidationExtractor()

    def test_extracts_context_from_page_text(
        self,
        extractor: ValidationExtractor,
    ) -> None:
        """Should extract context using page text position."""
        boxes = [
            {"text": "The"},
            {"text": "quick"},
            {"text": "brown"},
            {"text": "fox"},
        ]
        page_text = "The quick brown fox"

        context_before, context_after = extractor._extract_context(boxes, 2, page_text)

        assert "quick" in context_before
        assert "fox" in context_after

    def test_extracts_context_from_adjacent_when_position_fails(
        self,
        extractor: ValidationExtractor,
    ) -> None:
        """Should fallback to adjacent boxes when position not found."""
        boxes = [
            {"text": "word1"},
            {"text": "word2"},
            {"text": "unique_target"},
            {"text": "word4"},
        ]
        page_text = "different text"  # Target not in page text

        context_before, context_after = extractor._extract_context(boxes, 2, page_text)

        # Should use adjacent boxes
        assert "word1" in context_before or "word2" in context_before
        assert "word4" in context_after
