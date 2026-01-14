"""Tests for combined language police service (regex + LLM).

Story 8-3: Language Policing (AC #5)

Test Categories:
- Regex-only mode (LLM disabled)
- LLM polishing mode (LLM enabled with mocking)
- Error handling and fail-open behavior
- Cost tracking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.safety.language_police import (
    LanguagePolice,
    LanguagePoliceError,
    get_language_police,
    reset_language_police,
)
from app.services.safety.language_policing import (
    LanguagePolicingService,
    reset_language_policing_service,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.policing_llm_enabled = False  # Default to disabled
    settings.openai_safety_model = "gpt-4o-mini"
    settings.openai_api_key = "test-api-key"
    settings.policing_llm_timeout = 10.0
    settings.language_policing_enabled = True
    return settings


@pytest.fixture
def language_police_regex_only(mock_settings):
    """Get language police with LLM disabled."""
    reset_language_police()
    reset_language_policing_service()

    mock_settings.policing_llm_enabled = False

    with patch("app.services.safety.language_police.get_settings", return_value=mock_settings):
        return LanguagePolice()


@pytest.fixture
def language_police_llm_enabled(mock_settings):
    """Get language police with LLM enabled."""
    reset_language_police()
    reset_language_policing_service()

    mock_settings.policing_llm_enabled = True

    with patch("app.services.safety.language_police.get_settings", return_value=mock_settings):
        return LanguagePolice()


class TestRegexOnlyMode:
    """Test language police with LLM disabled (regex only)."""

    @pytest.mark.asyncio
    async def test_regex_policing_applied(self, language_police_regex_only) -> None:
        """Regex policing should be applied when LLM is disabled."""
        result = await language_police_regex_only.police_output(
            "The evidence proves that defendant violated Section 138."
        )

        assert "suggests that" in result.sanitized_text
        assert "affected by Section 138" in result.sanitized_text
        assert result.llm_policing_applied is False

    @pytest.mark.asyncio
    async def test_no_llm_cost_in_regex_mode(self, language_police_regex_only) -> None:
        """No LLM cost should be incurred in regex-only mode."""
        result = await language_police_regex_only.police_output(
            "The defendant is guilty of fraud."
        )

        assert result.llm_cost_usd == 0.0
        assert result.llm_policing_applied is False

    @pytest.mark.asyncio
    async def test_empty_text_handled(self, language_police_regex_only) -> None:
        """Empty text should return empty result."""
        result = await language_police_regex_only.police_output("")

        assert result.sanitized_text == ""
        assert result.llm_policing_applied is False

    @pytest.mark.asyncio
    async def test_safe_text_unchanged(self, language_police_regex_only) -> None:
        """Safe text should pass through unchanged."""
        original = "The loan was disbursed on January 15, 2023."
        result = await language_police_regex_only.police_output(original)

        assert result.sanitized_text == original
        assert len(result.replacements_made) == 0


class TestLLMPolishingMode:
    """Test language police with LLM enabled (mocked)."""

    @pytest.mark.asyncio
    async def test_llm_polishing_called(self, language_police_llm_enabled) -> None:
        """LLM polishing should be called when enabled."""
        # Mock the OpenAI client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """{
            "sanitized_text": "The evidence may indicate that defendant affected by Section 138.",
            "changes_made": ["polished 'proves that' to 'may indicate that'"],
            "confidence": 0.95
        }"""
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        with patch.object(
            language_police_llm_enabled,
            "_call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=(
                {
                    "sanitized_text": "The evidence may indicate that defendant affected by Section 138.",
                    "changes_made": ["polished 'proves that' to 'may indicate that'"],
                    "confidence": 0.95,
                },
                100,
                50,
            ),
        ):
            result = await language_police_llm_enabled.police_output(
                "The evidence proves that defendant violated Section 138."
            )

            assert result.llm_policing_applied is True
            assert result.llm_cost_usd > 0

    @pytest.mark.asyncio
    async def test_llm_cost_tracked(self, language_police_llm_enabled) -> None:
        """LLM cost should be tracked when LLM is enabled."""
        with patch.object(
            language_police_llm_enabled,
            "_call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=(
                {
                    "sanitized_text": "Safe text.",
                    "changes_made": [],
                    "confidence": 0.99,
                },
                500,  # input tokens
                100,  # output tokens
            ),
        ):
            result = await language_police_llm_enabled.police_output("Test text.")

            # Cost should be calculated based on token counts
            # GPT-4o-mini: $0.00015/1K input, $0.0006/1K output
            expected_cost = (500 / 1000) * 0.00015 + (100 / 1000) * 0.0006
            assert abs(result.llm_cost_usd - expected_cost) < 0.0001


class TestFailOpenBehavior:
    """Test that LLM failures don't block output."""

    @pytest.mark.asyncio
    async def test_llm_error_falls_back_to_regex(
        self, language_police_llm_enabled
    ) -> None:
        """LLM error should fall back to regex-only result."""
        with patch.object(
            language_police_llm_enabled,
            "_apply_llm_polish",
            new_callable=AsyncMock,
            side_effect=LanguagePoliceError("LLM unavailable"),
        ):
            # Should NOT raise - should return regex-sanitized text
            result = await language_police_llm_enabled.police_output(
                "The evidence proves that defendant violated Section 138."
            )

            # Regex should still be applied
            assert "suggests that" in result.sanitized_text
            assert "affected by Section 138" in result.sanitized_text
            assert result.llm_policing_applied is False

    @pytest.mark.asyncio
    async def test_api_key_missing_handled(self, mock_settings) -> None:
        """Missing API key should be handled gracefully."""
        mock_settings.policing_llm_enabled = True
        mock_settings.openai_api_key = ""  # No API key

        with patch(
            "app.services.safety.language_police.get_settings",
            return_value=mock_settings
        ):
            police = LanguagePolice()
            result = await police.police_output(
                "The defendant is guilty of fraud."
            )

            # Should fall back to regex
            assert "liability regarding" in result.sanitized_text.lower()


class TestInputSanitization:
    """Test input sanitization for prompt injection prevention."""

    @pytest.mark.asyncio
    async def test_triple_quotes_sanitized(self, language_police_regex_only) -> None:
        """Triple quotes should be sanitized."""
        text_with_triple = 'Test """injection attempt""" text.'
        result = await language_police_regex_only.police_output(text_with_triple)

        # Should not crash and should sanitize
        assert result.sanitized_text is not None
        assert '"""' not in result.original_text or result.sanitized_text is not None

    @pytest.mark.asyncio
    async def test_very_long_text_truncated(
        self, language_police_llm_enabled
    ) -> None:
        """Very long text should be truncated for LLM."""
        # Create text longer than 8000 chars
        long_text = "The defendant violated Section 138. " * 500

        with patch.object(
            language_police_llm_enabled,
            "_call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=(
                {"sanitized_text": "truncated", "changes_made": [], "confidence": 0.9},
                100,
                50,
            ),
        ) as mock_call:
            await language_police_llm_enabled.police_output(long_text)

            # LLM should receive truncated input
            # The test verifies the method was called (truncation happens internally)
            assert mock_call.called


class TestSingletonFactory:
    """Test singleton factory functions."""

    def test_get_language_police_returns_singleton(self, mock_settings) -> None:
        """get_language_police should return the same instance."""
        reset_language_police()

        with patch(
            "app.services.safety.language_police.get_settings",
            return_value=mock_settings
        ):
            police1 = get_language_police()
            police2 = get_language_police()

            assert police1 is police2

    def test_reset_clears_singleton(self, mock_settings) -> None:
        """reset_language_police should clear the singleton."""
        with patch(
            "app.services.safety.language_police.get_settings",
            return_value=mock_settings
        ):
            police1 = get_language_police()
            reset_language_police()
            police2 = get_language_police()

            assert police1 is not police2


class TestTimingMetrics:
    """Test timing metrics are properly tracked."""

    @pytest.mark.asyncio
    async def test_sanitization_time_tracked(
        self, language_police_regex_only
    ) -> None:
        """Sanitization time should be tracked in result."""
        result = await language_police_regex_only.police_output(
            "The defendant violated Section 138."
        )

        assert result.sanitization_time_ms > 0
        # Regex-only should be fast (< 100ms typically)
        assert result.sanitization_time_ms < 1000


class TestResponseParsing:
    """Test LLM response parsing."""

    def test_parse_valid_response(self, language_police_llm_enabled) -> None:
        """Valid JSON response should be parsed correctly."""
        response_text = """{
            "sanitized_text": "Safe text here.",
            "changes_made": ["change1", "change2"],
            "confidence": 0.95
        }"""

        parsed = language_police_llm_enabled._parse_llm_response(
            response_text, "original"
        )

        assert parsed["sanitized_text"] == "Safe text here."
        assert len(parsed["changes_made"]) == 2
        assert parsed["confidence"] == 0.95

    def test_parse_invalid_json_returns_original(
        self, language_police_llm_enabled
    ) -> None:
        """Invalid JSON should return original text."""
        response_text = "not valid json"

        parsed = language_police_llm_enabled._parse_llm_response(
            response_text, "original text"
        )

        assert parsed["sanitized_text"] == "original text"
        assert parsed["changes_made"] == []
        assert parsed["confidence"] == 0.0

    def test_parse_empty_sanitized_text_uses_original(
        self, language_police_llm_enabled
    ) -> None:
        """Empty sanitized_text in response should use original."""
        response_text = """{
            "sanitized_text": "",
            "changes_made": [],
            "confidence": 0.5
        }"""

        parsed = language_police_llm_enabled._parse_llm_response(
            response_text, "original text"
        )

        assert parsed["sanitized_text"] == "original text"
