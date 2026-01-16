"""Tests for OCR confidence calculator service.

These tests mock the Supabase client to test confidence calculation logic
without making actual database calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.ocr.confidence_calculator import (
    ConfidenceCalculatorError,
    _determine_quality_status,
    calculate_document_confidence,
    update_document_confidence,
)


class TestDetermineQualityStatus:
    """Tests for quality status determination logic."""

    def test_good_quality_above_threshold(self) -> None:
        """Should return 'good' when confidence >= 85%."""
        settings = MagicMock()
        settings.ocr_quality_good_threshold = 0.85
        settings.ocr_quality_fair_threshold = 0.70

        assert _determine_quality_status(0.90, settings) == "good"
        assert _determine_quality_status(0.85, settings) == "good"
        assert _determine_quality_status(1.0, settings) == "good"

    def test_fair_quality_in_range(self) -> None:
        """Should return 'fair' when confidence is 70-85%."""
        settings = MagicMock()
        settings.ocr_quality_good_threshold = 0.85
        settings.ocr_quality_fair_threshold = 0.70

        assert _determine_quality_status(0.70, settings) == "fair"
        assert _determine_quality_status(0.75, settings) == "fair"
        assert _determine_quality_status(0.84, settings) == "fair"

    def test_poor_quality_below_threshold(self) -> None:
        """Should return 'poor' when confidence < 70%."""
        settings = MagicMock()
        settings.ocr_quality_good_threshold = 0.85
        settings.ocr_quality_fair_threshold = 0.70

        assert _determine_quality_status(0.69, settings) == "poor"
        assert _determine_quality_status(0.50, settings) == "poor"
        assert _determine_quality_status(0.0, settings) == "poor"


class TestCalculateDocumentConfidence:
    """Tests for document confidence calculation."""

    @pytest.fixture
    def mock_supabase(self) -> MagicMock:
        """Create a mock Supabase client."""
        with patch("app.services.ocr.confidence_calculator.get_supabase_client") as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        with patch("app.services.ocr.confidence_calculator.get_settings") as mock:
            settings = MagicMock()
            settings.ocr_quality_good_threshold = 0.85
            settings.ocr_quality_fair_threshold = 0.70
            mock.return_value = settings
            yield settings

    def test_empty_bounding_boxes_returns_null_confidence(
        self, mock_supabase: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should return null confidence when no bounding boxes found."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        result = calculate_document_confidence("doc-id")

        assert result.document_id == "doc-id"
        assert result.overall_confidence is None
        assert result.page_confidences == []
        assert result.quality_status is None
        assert result.total_words == 0

    def test_single_page_calculates_average(
        self, mock_supabase: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should calculate average for single page."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"page_number": 1, "confidence_score": 0.90},
            {"page_number": 1, "confidence_score": 0.80},
            {"page_number": 1, "confidence_score": 0.85},
        ]

        result = calculate_document_confidence("doc-id")

        assert result.document_id == "doc-id"
        assert result.overall_confidence == pytest.approx(0.85, rel=1e-2)
        assert len(result.page_confidences) == 1
        assert result.page_confidences[0].page_number == 1
        assert result.page_confidences[0].confidence == pytest.approx(0.85, rel=1e-2)
        assert result.page_confidences[0].word_count == 3
        assert result.quality_status == "good"
        assert result.total_words == 3

    def test_multiple_pages_calculates_per_page_average(
        self, mock_supabase: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should calculate separate averages per page."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            # Page 1: 90% average
            {"page_number": 1, "confidence_score": 0.90},
            {"page_number": 1, "confidence_score": 0.90},
            # Page 2: 70% average
            {"page_number": 2, "confidence_score": 0.70},
            {"page_number": 2, "confidence_score": 0.70},
            # Page 3: 50% average
            {"page_number": 3, "confidence_score": 0.50},
            {"page_number": 3, "confidence_score": 0.50},
        ]

        result = calculate_document_confidence("doc-id")

        assert len(result.page_confidences) == 3

        # Verify sorted by page number
        assert result.page_confidences[0].page_number == 1
        assert result.page_confidences[0].confidence == pytest.approx(0.90, rel=1e-2)

        assert result.page_confidences[1].page_number == 2
        assert result.page_confidences[1].confidence == pytest.approx(0.70, rel=1e-2)

        assert result.page_confidences[2].page_number == 3
        assert result.page_confidences[2].confidence == pytest.approx(0.50, rel=1e-2)

        # Overall = (0.9*2 + 0.7*2 + 0.5*2) / 6 = 0.7
        assert result.overall_confidence == pytest.approx(0.70, rel=1e-2)
        assert result.quality_status == "fair"

    def test_null_confidence_scores_ignored(
        self, mock_supabase: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should ignore bounding boxes with null confidence scores."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"page_number": 1, "confidence_score": 0.90},
            {"page_number": 1, "confidence_score": None},  # Should be ignored
            {"page_number": 1, "confidence_score": 0.80},
        ]

        result = calculate_document_confidence("doc-id")

        assert result.overall_confidence == pytest.approx(0.85, rel=1e-2)
        assert result.total_words == 2  # Only 2 words with confidence

    def test_all_null_confidences_returns_null_overall(
        self, mock_supabase: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should return null confidence when all scores are null."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"page_number": 1, "confidence_score": None},
            {"page_number": 1, "confidence_score": None},
        ]

        result = calculate_document_confidence("doc-id")

        assert result.overall_confidence is None
        assert result.quality_status is None
        assert result.total_words == 2  # Total bounding boxes

    def test_database_error_raises_exception(
        self, mock_supabase: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should raise ConfidenceCalculatorError on database failure."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(ConfidenceCalculatorError) as exc_info:
            calculate_document_confidence("doc-id")

        assert "Database query failed" in str(exc_info.value)

    def test_no_client_raises_exception(self, mock_settings: MagicMock) -> None:
        """Should raise ConfidenceCalculatorError when client not configured."""
        with patch(
            "app.services.ocr.confidence_calculator.get_supabase_client"
        ) as mock:
            mock.return_value = None

            with pytest.raises(ConfidenceCalculatorError) as exc_info:
                calculate_document_confidence("doc-id")

            assert "not configured" in str(exc_info.value)


class TestUpdateDocumentConfidence:
    """Tests for updating document with confidence metrics."""

    @pytest.fixture
    def mock_supabase(self) -> MagicMock:
        """Create a mock Supabase client."""
        with patch("app.services.ocr.confidence_calculator.get_supabase_client") as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        with patch("app.services.ocr.confidence_calculator.get_settings") as mock:
            settings = MagicMock()
            settings.ocr_quality_good_threshold = 0.85
            settings.ocr_quality_fair_threshold = 0.70
            mock.return_value = settings
            yield settings

    def test_updates_document_with_calculated_values(
        self, mock_supabase: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should update document with calculated confidence metrics."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"page_number": 1, "confidence_score": 0.90},
            {"page_number": 2, "confidence_score": 0.80},
        ]

        result = update_document_confidence("doc-id")

        # Verify update was called
        update_call = mock_supabase.table.return_value.update
        assert update_call.called

        # Verify result
        assert result.document_id == "doc-id"
        assert result.overall_confidence == pytest.approx(0.85, rel=1e-2)
        assert result.quality_status == "good"

    def test_update_failure_raises_exception(
        self, mock_supabase: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Should raise exception when update fails."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"page_number": 1, "confidence_score": 0.90},
        ]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
            "Update failed"
        )

        with pytest.raises(ConfidenceCalculatorError) as exc_info:
            update_document_confidence("doc-id")

        assert "Failed to update document" in str(exc_info.value)
