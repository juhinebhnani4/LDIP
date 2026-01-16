"""Tests for OCR processor service."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.ocr import OCRResult
from app.services.ocr.processor import (
    OCRConfigurationError,
    OCRProcessingError,
    OCRProcessor,
    OCRServiceError,
)


class TestOCRProcessor:
    """Tests for OCRProcessor class."""

    def test_initialization_uses_settings(self) -> None:
        """Should use settings for configuration when not provided."""
        with patch("app.services.ocr.processor.get_settings") as mock_settings:
            mock_settings.return_value.google_cloud_project_id = "test-project"
            mock_settings.return_value.google_cloud_location = "us"
            mock_settings.return_value.google_document_ai_processor_id = "test-processor"

            processor = OCRProcessor()

            assert processor.project_id == "test-project"
            assert processor.location == "us"
            assert processor.processor_id == "test-processor"

    def test_initialization_uses_explicit_values(self) -> None:
        """Should use explicit values when provided."""
        processor = OCRProcessor(
            project_id="my-project",
            location="eu",
            processor_id="my-processor",
        )

        assert processor.project_id == "my-project"
        assert processor.location == "eu"
        assert processor.processor_id == "my-processor"

    def test_processor_name_format(self) -> None:
        """Should format processor name correctly."""
        processor = OCRProcessor(
            project_id="my-project",
            location="us",
            processor_id="abc123",
        )

        assert processor.processor_name == (
            "projects/my-project/locations/us/processors/abc123"
        )

    def test_processor_name_raises_when_not_configured(self) -> None:
        """Should raise error when processor not configured."""
        with patch("app.services.ocr.processor.get_settings") as mock_settings:
            # Mock settings to return empty values
            mock_settings.return_value.google_cloud_project_id = ""
            mock_settings.return_value.google_cloud_location = "us"
            mock_settings.return_value.google_document_ai_processor_id = ""

            processor = OCRProcessor(
                project_id="",
                location="us",
                processor_id="",
            )

            with pytest.raises(OCRConfigurationError) as exc_info:
                _ = processor.processor_name

            assert "not configured" in str(exc_info.value)
            assert exc_info.value.code == "OCR_NOT_CONFIGURED"


class TestOCRProcessorProcessDocument:
    """Tests for process_document method."""

    @pytest.fixture
    def mock_processor(self) -> OCRProcessor:
        """Create a processor with mock client."""
        processor = OCRProcessor(
            project_id="test-project",
            location="us",
            processor_id="test-processor",
        )
        return processor

    def _create_mock_document_response(
        self,
        text: str = "Test document content",
        page_count: int = 1,
        confidence: float = 0.95,
    ) -> MagicMock:
        """Create mock Document AI response."""
        document = MagicMock()
        document.text = text
        document.pages = []

        for i in range(page_count):
            page = MagicMock()
            page.page_number = i + 1
            page.tokens = []
            page.blocks = []

            # Layout with text anchor
            page.layout = MagicMock()
            page.layout.text_anchor = MagicMock()
            page.layout.text_anchor.text_segments = []

            # Image quality scores
            page.image_quality_scores = MagicMock()
            page.image_quality_scores.quality_score = 0.9

            document.pages.append(page)

        return document

    @patch("app.services.ocr.processor.documentai")
    def test_successful_processing(
        self,
        mock_documentai: MagicMock,
        mock_processor: OCRProcessor,
    ) -> None:
        """Should process document and return OCRResult."""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.document = self._create_mock_document_response()
        mock_client.process_document.return_value = mock_response

        mock_processor._client = mock_client

        # Execute
        result = mock_processor.process_document(
            pdf_content=b"fake pdf content",
            document_id="doc-123",
        )

        # Verify
        assert isinstance(result, OCRResult)
        assert result.document_id == "doc-123"
        assert result.page_count == 1
        assert result.full_text == "Test document content"

    @patch("app.services.ocr.processor.documentai")
    def test_processing_includes_page_count(
        self,
        mock_documentai: MagicMock,
        mock_processor: OCRProcessor,
    ) -> None:
        """Should include correct page count in result."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.document = self._create_mock_document_response(page_count=5)
        mock_client.process_document.return_value = mock_response

        mock_processor._client = mock_client

        result = mock_processor.process_document(
            pdf_content=b"fake pdf content",
            document_id="doc-123",
        )

        assert result.page_count == 5
        assert len(result.pages) == 5

    @patch("app.services.ocr.processor.documentai")
    def test_processing_tracks_time(
        self,
        mock_documentai: MagicMock,
        mock_processor: OCRProcessor,
    ) -> None:
        """Should track processing time in milliseconds."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.document = self._create_mock_document_response()
        mock_client.process_document.return_value = mock_response

        mock_processor._client = mock_client

        result = mock_processor.process_document(
            pdf_content=b"fake pdf content",
        )

        assert result.processing_time_ms is not None
        assert result.processing_time_ms >= 0

    @patch("app.services.ocr.processor.documentai")
    def test_process_document_configures_indian_language_hints(
        self,
        mock_documentai: MagicMock,
        mock_processor: OCRProcessor,
    ) -> None:
        """Should configure language hints for Hindi, Gujarati, English.

        Verifies that ProcessRequest is constructed with OcrConfig containing
        language hints for Indian languages (en, hi, gu) per AC#3.
        """
        # Setup documentai mock to capture the ProcessRequest
        mock_process_request = MagicMock()
        mock_documentai.ProcessRequest = mock_process_request

        mock_ocr_config = MagicMock()
        mock_documentai.OcrConfig = mock_ocr_config

        mock_process_options = MagicMock()
        mock_documentai.ProcessOptions = mock_process_options

        mock_ocr_hints = MagicMock()
        mock_documentai.OcrConfig.Hints = mock_ocr_hints

        mock_raw_document = MagicMock()
        mock_documentai.RawDocument = mock_raw_document

        # Setup client mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.document = self._create_mock_document_response(
            text="English text मराठी ગુજરાતી"
        )
        mock_client.process_document.return_value = mock_response

        mock_processor._client = mock_client

        mock_processor.process_document(
            pdf_content=b"fake multilingual pdf content",
            document_id="doc-multilingual",
        )

        # Verify OcrConfig.Hints was called with language hints
        mock_ocr_hints.assert_called_once()
        hints_call_kwargs = mock_ocr_hints.call_args.kwargs
        assert "language_hints" in hints_call_kwargs
        language_hints = hints_call_kwargs["language_hints"]
        assert "en" in language_hints
        assert "hi" in language_hints
        assert "gu" in language_hints

    @patch("app.services.ocr.processor.documentai")
    def test_process_document_handles_multilingual_content(
        self,
        mock_documentai: MagicMock,
        mock_processor: OCRProcessor,
    ) -> None:
        """Should correctly extract text from multilingual documents."""
        # Multilingual content: English, Hindi, Gujarati
        multilingual_text = "Legal Document\nधारा 302 भारतीय दंड संहिता\nકલમ 302 ભારતીય દંડ સંહિતા"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.document = self._create_mock_document_response(
            text=multilingual_text
        )
        mock_client.process_document.return_value = mock_response

        mock_processor._client = mock_client

        result = mock_processor.process_document(
            pdf_content=b"fake multilingual pdf",
            document_id="doc-multilingual",
        )

        # Verify multilingual text is preserved
        assert result.full_text == multilingual_text
        assert "Legal Document" in result.full_text  # English
        assert "धारा" in result.full_text  # Hindi
        assert "કલમ" in result.full_text  # Gujarati

    def test_raises_configuration_error_when_not_configured(
        self,
    ) -> None:
        """Should raise OCRConfigurationError when not configured."""
        processor = OCRProcessor(
            project_id="",
            location="us",
            processor_id="",
        )

        with pytest.raises(OCRConfigurationError):
            processor.process_document(
                pdf_content=b"fake pdf content",
            )


class TestOCRServiceError:
    """Tests for OCR error classes."""

    def test_ocr_service_error_attributes(self) -> None:
        """Should have correct attributes."""
        error = OCRServiceError(
            message="Test error",
            code="TEST_CODE",
            is_retryable=True,
        )

        assert error.message == "Test error"
        assert error.code == "TEST_CODE"
        assert error.is_retryable is True
        assert str(error) == "Test error"

    def test_ocr_configuration_error_not_retryable(self) -> None:
        """Configuration errors should not be retryable."""
        error = OCRConfigurationError("Not configured")

        assert error.is_retryable is False
        assert error.code == "OCR_NOT_CONFIGURED"

    def test_ocr_processing_error_defaults_to_retryable(self) -> None:
        """Processing errors should default to retryable."""
        error = OCRProcessingError("Processing failed")

        assert error.is_retryable is True
        assert error.code == "OCR_PROCESSING_FAILED"

    def test_ocr_processing_error_can_be_not_retryable(self) -> None:
        """Processing errors can be marked as not retryable."""
        error = OCRProcessingError("Bad input", is_retryable=False)

        assert error.is_retryable is False
