"""Tests for Gemini-based OCR validation service.

These tests mock the Gemini API to test the validation logic without
making actual API calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ocr_validation import CorrectionType, LowConfidenceWord, ValidationResult
from app.services.ocr.gemini_validator import (
    GeminiConfigurationError,
    GeminiOCRValidator,
    GeminiValidatorError,
    get_gemini_validator,
    validate_all_words,
)


class TestGeminiOCRValidator:
    """Tests for GeminiOCRValidator class."""

    def test_initialization_uses_settings(self) -> None:
        """Should use settings for configuration."""
        with patch("app.services.ocr.gemini_validator.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = "test-api-key"
            mock_settings.return_value.gemini_model = "gemini-1.5-flash"
            mock_settings.return_value.ocr_validation_batch_size = 20

            validator = GeminiOCRValidator()

            assert validator.api_key == "test-api-key"
            assert validator.model_name == "gemini-1.5-flash"
            assert validator.batch_size == 20

    def test_model_property_raises_when_not_configured(self) -> None:
        """Should raise GeminiConfigurationError when API key not set."""
        with patch("app.services.ocr.gemini_validator.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = ""
            mock_settings.return_value.gemini_model = "gemini-1.5-flash"
            mock_settings.return_value.ocr_validation_batch_size = 20

            validator = GeminiOCRValidator()

            with pytest.raises(GeminiConfigurationError) as exc_info:
                _ = validator.model

            assert exc_info.value.code == "GEMINI_NOT_CONFIGURED"
            assert exc_info.value.is_retryable is False


class TestValidateBatchSync:
    """Tests for synchronous batch validation."""

    @pytest.fixture
    def mock_validator(self) -> GeminiOCRValidator:
        """Create a validator with mocked settings."""
        with patch("app.services.ocr.gemini_validator.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = "test-api-key"
            mock_settings.return_value.gemini_model = "gemini-1.5-flash"
            mock_settings.return_value.ocr_validation_batch_size = 20

            return GeminiOCRValidator()

    def _create_mock_words(self, count: int) -> list[LowConfidenceWord]:
        """Create mock low-confidence words.

        Args:
            count: Number of words to create.

        Returns:
            List of LowConfidenceWord instances.
        """
        return [
            LowConfidenceWord(
                bbox_id=f"bbox-{i}",
                text=f"word{i}",
                confidence=0.60 + i * 0.01,
                page=1,
                context_before="before",
                context_after="after",
                x=10.0 + i * 10,
                y=20.0,
                width=8.0,
                height=5.0,
            )
            for i in range(count)
        ]

    def _create_mock_response(
        self,
        words: list[LowConfidenceWord],
        corrections: dict[int, str] | None = None,
    ) -> str:
        """Create a mock Gemini response.

        Args:
            words: Original words.
            corrections: Optional dict of index -> corrected text.

        Returns:
            JSON response string.
        """
        corrections = corrections or {}
        result = []
        for i, word in enumerate(words):
            corrected = corrections.get(i, word.text)
            result.append({
                "index": i,
                "original": word.text,
                "corrected": corrected,
                "confidence": 0.9 if corrected != word.text else word.confidence,
                "reasoning": "Corrected" if corrected != word.text else "No correction needed",
            })
        return json.dumps(result)

    def test_returns_empty_for_empty_input(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should return empty list for empty input."""
        results = mock_validator.validate_batch_sync([])

        assert results == []

    def test_truncates_batch_over_limit(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should truncate batch if over batch_size limit."""
        words = self._create_mock_words(30)  # Over the 20 limit

        mock_response = MagicMock()
        mock_response.text = self._create_mock_response(words[:20])

        with patch.object(
            mock_validator,
            "_model",
            MagicMock(generate_content=MagicMock(return_value=mock_response)),
        ):
            results = mock_validator.validate_batch_sync(words)

        # Should only process first 20
        assert len(results) == 20

    def test_parses_gemini_response(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should correctly parse Gemini response."""
        words = self._create_mock_words(3)

        mock_response = MagicMock()
        mock_response.text = self._create_mock_response(
            words,
            corrections={1: "corrected_word1"},
        )

        with patch.object(
            mock_validator,
            "_model",
            MagicMock(generate_content=MagicMock(return_value=mock_response)),
        ):
            results = mock_validator.validate_batch_sync(words)

        assert len(results) == 3

        # First word unchanged
        assert results[0].corrected == "word0"
        assert results[0].was_corrected is False

        # Second word corrected
        assert results[1].corrected == "corrected_word1"
        assert results[1].was_corrected is True
        assert results[1].correction_type == CorrectionType.GEMINI

        # Third word unchanged
        assert results[2].corrected == "word2"
        assert results[2].was_corrected is False

    def test_handles_markdown_code_block_response(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should extract JSON from markdown code blocks."""
        words = self._create_mock_words(1)

        json_content = self._create_mock_response(words)
        mock_response = MagicMock()
        mock_response.text = f"```json\n{json_content}\n```"

        with patch.object(
            mock_validator,
            "_model",
            MagicMock(generate_content=MagicMock(return_value=mock_response)),
        ):
            results = mock_validator.validate_batch_sync(words)

        assert len(results) == 1

    def test_returns_fallback_for_invalid_json(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should return fallback results when JSON parsing fails."""
        words = self._create_mock_words(2)

        mock_response = MagicMock()
        mock_response.text = "This is not valid JSON"

        with patch.object(
            mock_validator,
            "_model",
            MagicMock(generate_content=MagicMock(return_value=mock_response)),
        ):
            results = mock_validator.validate_batch_sync(words)

        # Should return fallback (unchanged) results
        assert len(results) == 2
        assert results[0].corrected == words[0].text
        assert results[0].was_corrected is False

    def test_handles_api_error(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should raise GeminiValidatorError on API failure."""
        words = self._create_mock_words(2)

        with patch.object(
            mock_validator,
            "_model",
            MagicMock(generate_content=MagicMock(side_effect=Exception("API Error"))),
        ):
            with pytest.raises(GeminiValidatorError) as exc_info:
                mock_validator.validate_batch_sync(words)

            assert exc_info.value.is_retryable is True

    def test_preserves_bbox_id_in_results(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should preserve bbox_id from input to output."""
        words = self._create_mock_words(2)

        mock_response = MagicMock()
        mock_response.text = self._create_mock_response(words)

        with patch.object(
            mock_validator,
            "_model",
            MagicMock(generate_content=MagicMock(return_value=mock_response)),
        ):
            results = mock_validator.validate_batch_sync(words)

        assert results[0].bbox_id == "bbox-0"
        assert results[1].bbox_id == "bbox-1"


class TestValidateBatchAsync:
    """Tests for asynchronous batch validation."""

    @pytest.fixture
    def mock_validator(self) -> GeminiOCRValidator:
        """Create a validator with mocked settings."""
        with patch("app.services.ocr.gemini_validator.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = "test-api-key"
            mock_settings.return_value.gemini_model = "gemini-1.5-flash"
            mock_settings.return_value.ocr_validation_batch_size = 20

            return GeminiOCRValidator()

    def _create_mock_words(self, count: int) -> list[LowConfidenceWord]:
        """Create mock low-confidence words."""
        return [
            LowConfidenceWord(
                bbox_id=f"bbox-{i}",
                text=f"word{i}",
                confidence=0.60,
                page=1,
                context_before="before",
                context_after="after",
                x=10.0,
                y=20.0,
                width=8.0,
                height=5.0,
            )
            for i in range(count)
        ]

    def _create_mock_response(self, words: list[LowConfidenceWord]) -> str:
        """Create a mock Gemini response."""
        result = []
        for i, word in enumerate(words):
            result.append({
                "index": i,
                "original": word.text,
                "corrected": word.text,
                "confidence": word.confidence,
                "reasoning": "No correction needed",
            })
        return json.dumps(result)

    @pytest.mark.anyio
    async def test_async_returns_empty_for_empty_input(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should return empty list for empty input."""
        results = await mock_validator.validate_batch_async([])

        assert results == []

    @pytest.mark.anyio
    async def test_async_parses_response(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should correctly parse async Gemini response."""
        words = self._create_mock_words(2)

        mock_response = MagicMock()
        mock_response.text = self._create_mock_response(words)

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.object(mock_validator, "_model", mock_model):
            results = await mock_validator.validate_batch_async(words)

        assert len(results) == 2

    @pytest.mark.anyio
    async def test_async_handles_api_error(
        self,
        mock_validator: GeminiOCRValidator,
    ) -> None:
        """Should raise GeminiValidatorError on async API failure."""
        words = self._create_mock_words(2)

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(
            side_effect=Exception("Async API Error")
        )

        with patch.object(mock_validator, "_model", mock_model):
            with pytest.raises(GeminiValidatorError):
                await mock_validator.validate_batch_async(words)


class TestParseResponse:
    """Tests for response parsing."""

    @pytest.fixture
    def validator(self) -> GeminiOCRValidator:
        """Create a validator for testing."""
        with patch("app.services.ocr.gemini_validator.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = "test-key"
            mock_settings.return_value.gemini_model = "gemini-1.5-flash"
            mock_settings.return_value.ocr_validation_batch_size = 20

            return GeminiOCRValidator()

    def _create_words(self, count: int) -> list[LowConfidenceWord]:
        """Create mock words."""
        return [
            LowConfidenceWord(
                bbox_id=f"bbox-{i}",
                text=f"word{i}",
                confidence=0.60,
                page=1,
                context_before="",
                context_after="",
                x=0,
                y=0,
                width=10,
                height=5,
            )
            for i in range(count)
        ]

    def test_handles_missing_indices_in_response(
        self,
        validator: GeminiOCRValidator,
    ) -> None:
        """Should return unchanged for words not in response."""
        words = self._create_words(3)

        # Response only has index 0, missing 1 and 2
        response_data = [
            {
                "index": 0,
                "original": "word0",
                "corrected": "corrected0",
                "confidence": 0.9,
                "reasoning": "Fixed",
            }
        ]

        results = validator._parse_response(json.dumps(response_data), words)

        assert len(results) == 3
        assert results[0].corrected == "corrected0"
        assert results[0].was_corrected is True
        # Missing indices should be unchanged
        assert results[1].corrected == "word1"
        assert results[1].was_corrected is False
        assert results[2].corrected == "word2"
        assert results[2].was_corrected is False

    def test_handles_non_list_response(
        self,
        validator: GeminiOCRValidator,
    ) -> None:
        """Should return fallback for non-list response."""
        words = self._create_words(2)

        # Invalid response format
        response_data = {"error": "Invalid format"}

        results = validator._parse_response(json.dumps(response_data), words)

        # Should return fallback results
        assert len(results) == 2
        assert all(not r.was_corrected for r in results)

    def test_extracts_correction_type(
        self,
        validator: GeminiOCRValidator,
    ) -> None:
        """Should set correction_type to GEMINI when corrected."""
        words = self._create_words(1)

        response_data = [
            {
                "index": 0,
                "original": "word0",
                "corrected": "fixed0",
                "confidence": 0.95,
                "reasoning": "OCR error fixed",
            }
        ]

        results = validator._parse_response(json.dumps(response_data), words)

        assert results[0].correction_type == CorrectionType.GEMINI

    def test_no_correction_type_when_unchanged(
        self,
        validator: GeminiOCRValidator,
    ) -> None:
        """Should not set correction_type when text unchanged."""
        words = self._create_words(1)

        response_data = [
            {
                "index": 0,
                "original": "word0",
                "corrected": "word0",  # Same as original
                "confidence": 0.80,
                "reasoning": "No correction needed",
            }
        ]

        results = validator._parse_response(json.dumps(response_data), words)

        assert results[0].correction_type is None
        assert results[0].was_corrected is False


class TestFallbackResults:
    """Tests for fallback result generation."""

    @pytest.fixture
    def validator(self) -> GeminiOCRValidator:
        """Create a validator for testing."""
        with patch("app.services.ocr.gemini_validator.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = "test-key"
            mock_settings.return_value.gemini_model = "gemini-1.5-flash"
            mock_settings.return_value.ocr_validation_batch_size = 20

            return GeminiOCRValidator()

    def test_returns_unchanged_results(
        self,
        validator: GeminiOCRValidator,
    ) -> None:
        """Should return unchanged results for all words."""
        words = [
            LowConfidenceWord(
                bbox_id="bbox-1",
                text="test",
                confidence=0.65,
                page=1,
                context_before="",
                context_after="",
                x=0,
                y=0,
                width=10,
                height=5,
            )
        ]

        results = validator._fallback_results(words)

        assert len(results) == 1
        assert results[0].bbox_id == "bbox-1"
        assert results[0].original == "test"
        assert results[0].corrected == "test"
        assert results[0].old_confidence == 0.65
        assert results[0].new_confidence == 0.65
        assert results[0].was_corrected is False
        assert results[0].correction_type is None


class TestValidateAllWords:
    """Tests for validate_all_words batch processing function."""

    @pytest.mark.anyio
    async def test_returns_empty_for_empty_input(self) -> None:
        """Should return empty list for empty input."""
        results = await validate_all_words([])

        assert results == []

    @pytest.mark.anyio
    async def test_processes_words_in_batches(self) -> None:
        """Should split words into batches and process."""
        words = [
            LowConfidenceWord(
                bbox_id=f"bbox-{i}",
                text=f"word{i}",
                confidence=0.60,
                page=1,
                context_before="",
                context_after="",
                x=0,
                y=0,
                width=10,
                height=5,
            )
            for i in range(25)  # More than one batch
        ]

        # Create mock response for each batch
        def create_response(batch_words: list[LowConfidenceWord]) -> str:
            result = []
            for i, word in enumerate(batch_words):
                result.append({
                    "index": i,
                    "original": word.text,
                    "corrected": word.text,
                    "confidence": word.confidence,
                    "reasoning": "No correction",
                })
            return json.dumps(result)

        with patch("app.services.ocr.gemini_validator.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = "test-key"
            mock_settings.return_value.gemini_model = "gemini-1.5-flash"
            mock_settings.return_value.ocr_validation_batch_size = 20

            with patch("app.services.ocr.gemini_validator.GeminiOCRValidator") as MockValidator:
                mock_instance = MagicMock()

                # Mock validate_batch_async to return appropriate results
                async def mock_validate(batch: list[LowConfidenceWord]) -> list[ValidationResult]:
                    return [
                        ValidationResult(
                            bbox_id=w.bbox_id,
                            original=w.text,
                            corrected=w.text,
                            old_confidence=w.confidence,
                            new_confidence=w.confidence,
                            correction_type=None,
                            reasoning=None,
                            was_corrected=False,
                        )
                        for w in batch
                    ]

                mock_instance.validate_batch_async = mock_validate
                MockValidator.return_value = mock_instance

                results = await validate_all_words(words, batch_size=20)

        assert len(results) == 25

    @pytest.mark.anyio
    async def test_handles_batch_failures_gracefully(self) -> None:
        """Should return fallback for failed batches."""
        words = [
            LowConfidenceWord(
                bbox_id=f"bbox-{i}",
                text=f"word{i}",
                confidence=0.60,
                page=1,
                context_before="",
                context_after="",
                x=0,
                y=0,
                width=10,
                height=5,
            )
            for i in range(5)
        ]

        with patch("app.services.ocr.gemini_validator.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = "test-key"
            mock_settings.return_value.gemini_model = "gemini-1.5-flash"
            mock_settings.return_value.ocr_validation_batch_size = 20

            with patch("app.services.ocr.gemini_validator.GeminiOCRValidator") as MockValidator:
                mock_instance = MagicMock()
                mock_instance.validate_batch_async = AsyncMock(
                    side_effect=Exception("Batch failed")
                )
                mock_instance._fallback_results = lambda words: [
                    ValidationResult(
                        bbox_id=w.bbox_id,
                        original=w.text,
                        corrected=w.text,
                        old_confidence=w.confidence,
                        new_confidence=w.confidence,
                        correction_type=None,
                        reasoning=None,
                        was_corrected=False,
                    )
                    for w in words
                ]
                MockValidator.return_value = mock_instance

                results = await validate_all_words(words, batch_size=20)

        # Should still return results (fallback)
        assert len(results) == 5


class TestGetGeminiValidator:
    """Tests for get_gemini_validator factory function."""

    def test_returns_cached_instance(self) -> None:
        """Should return cached validator instance."""
        with patch("app.services.ocr.gemini_validator.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = "test-key"
            mock_settings.return_value.gemini_model = "gemini-1.5-flash"
            mock_settings.return_value.ocr_validation_batch_size = 20

            # Clear cache first
            get_gemini_validator.cache_clear()

            validator1 = get_gemini_validator()
            validator2 = get_gemini_validator()

            # Should be same instance due to lru_cache
            assert validator1 is validator2


class TestGeminiValidatorError:
    """Tests for error classes."""

    def test_gemini_validator_error_attributes(self) -> None:
        """Should have correct attributes."""
        error = GeminiValidatorError(
            message="Test error",
            code="TEST_CODE",
            is_retryable=True,
        )

        assert error.message == "Test error"
        assert error.code == "TEST_CODE"
        assert error.is_retryable is True
        assert str(error) == "Test error"

    def test_gemini_configuration_error_not_retryable(self) -> None:
        """Configuration errors should not be retryable."""
        error = GeminiConfigurationError("Not configured")

        assert error.is_retryable is False
        assert error.code == "GEMINI_NOT_CONFIGURED"

    def test_default_gemini_error_is_retryable(self) -> None:
        """Default validator errors should be retryable."""
        error = GeminiValidatorError("Temporary failure")

        assert error.is_retryable is True
        assert error.code == "GEMINI_ERROR"
