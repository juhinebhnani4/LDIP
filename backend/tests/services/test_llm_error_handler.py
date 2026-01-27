"""Tests for LLM Error Handler Service.

Story 5.5: User-Friendly LLM Error Messages

Test Categories:
- Error classification
- User-friendly message mapping
- Retry recommendations
- Error handling wrapper
- Response formatting
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.llm_error_handler import (
    LLMErrorCode,
    LLMErrorResult,
    ERROR_MESSAGES,
    RETRY_RECOMMENDATIONS,
    classify_error,
    format_error_for_response,
    with_error_handling,
    _classify_error_code,
)


# =============================================================================
# Error Classification Tests
# =============================================================================


class TestClassifyErrorCode:
    """Test error code classification from exception messages."""

    def test_classifies_rate_limit(self) -> None:
        """Should classify rate limit errors."""
        error_str = "Error: Rate limit exceeded"
        code = _classify_error_code(error_str.lower(), "APIError")
        assert code == LLMErrorCode.RATE_LIMITED

    def test_classifies_rate_limit_429(self) -> None:
        """Should classify 429 status as rate limited."""
        error_str = "HTTP 429: Too many requests"
        code = _classify_error_code(error_str.lower(), "HTTPError")
        assert code == LLMErrorCode.RATE_LIMITED

    def test_classifies_quota_exceeded(self) -> None:
        """Should classify quota exceeded errors."""
        error_str = "Quota exceeded for the day"
        code = _classify_error_code(error_str.lower(), "APIError")
        assert code == LLMErrorCode.QUOTA_EXCEEDED

    def test_classifies_resource_exhausted(self) -> None:
        """Should classify resource exhausted as rate limited or quota exceeded."""
        error_str = "ResourceExhausted: quota limit reached"
        code = _classify_error_code(error_str.lower(), "GoogleAPIError")
        # Contains both "resourceexhausted" and "quota", should classify as quota exceeded
        assert code in (LLMErrorCode.RATE_LIMITED, LLMErrorCode.QUOTA_EXCEEDED)

    def test_classifies_timeout(self) -> None:
        """Should classify timeout errors."""
        error_str = "Request timed out after 30 seconds"
        code = _classify_error_code(error_str.lower(), "TimeoutError")
        assert code == LLMErrorCode.TIMEOUT

    def test_classifies_deadline_exceeded(self) -> None:
        """Should classify deadline exceeded as timeout."""
        error_str = "Deadline exceeded for API call"
        code = _classify_error_code(error_str.lower(), "DeadlineError")
        assert code == LLMErrorCode.TIMEOUT

    def test_classifies_connection_error(self) -> None:
        """Should classify connection errors."""
        error_str = "Connection refused to api.example.com"
        code = _classify_error_code(error_str.lower(), "ConnectionError")
        assert code == LLMErrorCode.CONNECTION_ERROR

    def test_classifies_network_error(self) -> None:
        """Should classify network errors."""
        error_str = "Network unreachable"
        code = _classify_error_code(error_str.lower(), "NetworkError")
        assert code == LLMErrorCode.CONNECTION_ERROR

    def test_classifies_ssl_error(self) -> None:
        """Should classify SSL errors as connection errors."""
        error_str = "SSL certificate verification failed"
        code = _classify_error_code(error_str.lower(), "SSLError")
        assert code == LLMErrorCode.CONNECTION_ERROR

    def test_classifies_content_filtered(self) -> None:
        """Should classify content filter blocks."""
        error_str = "Content blocked by safety filters"
        code = _classify_error_code(error_str.lower(), "SafetyError")
        assert code == LLMErrorCode.CONTENT_FILTERED

    def test_classifies_harmful_content(self) -> None:
        """Should classify harmful content errors."""
        error_str = "Potentially harmful content detected"
        code = _classify_error_code(error_str.lower(), "ContentError")
        assert code == LLMErrorCode.CONTENT_FILTERED

    def test_classifies_context_too_long(self) -> None:
        """Should classify context length errors."""
        error_str = "Context length exceeds maximum of 128000 tokens"
        code = _classify_error_code(error_str.lower(), "ValidationError")
        assert code == LLMErrorCode.CONTEXT_TOO_LONG

    def test_classifies_token_limit(self) -> None:
        """Should classify token limit errors."""
        error_str = "Token limit exceeded for this model"
        code = _classify_error_code(error_str.lower(), "TokenError")
        assert code == LLMErrorCode.CONTEXT_TOO_LONG

    def test_classifies_service_unavailable(self) -> None:
        """Should classify 503 as service unavailable."""
        error_str = "HTTP 503: Service unavailable"
        code = _classify_error_code(error_str.lower(), "HTTPError")
        assert code == LLMErrorCode.SERVICE_UNAVAILABLE

    def test_classifies_overloaded(self) -> None:
        """Should classify overloaded errors."""
        error_str = "Server overloaded, try again later"
        code = _classify_error_code(error_str.lower(), "ServerError")
        assert code == LLMErrorCode.SERVICE_UNAVAILABLE

    def test_classifies_invalid_response(self) -> None:
        """Should classify invalid response errors."""
        error_str = "Invalid response format from API"
        code = _classify_error_code(error_str.lower(), "ParseError")
        assert code == LLMErrorCode.INVALID_RESPONSE

    def test_classifies_json_error(self) -> None:
        """Should classify JSON parse errors."""
        error_str = "Failed to parse JSON response"
        code = _classify_error_code(error_str.lower(), "JSONDecodeError")
        assert code == LLMErrorCode.INVALID_RESPONSE

    def test_classifies_api_error_500(self) -> None:
        """Should classify 500 as API error."""
        error_str = "HTTP 500: Internal server error"
        code = _classify_error_code(error_str.lower(), "HTTPError")
        assert code == LLMErrorCode.API_ERROR

    def test_classifies_unknown_error(self) -> None:
        """Should classify unknown errors."""
        error_str = "Something completely unexpected happened"
        code = _classify_error_code(error_str.lower(), "Exception")
        assert code == LLMErrorCode.UNKNOWN_ERROR


# =============================================================================
# Error Classification Integration Tests
# =============================================================================


class TestClassifyError:
    """Test full error classification with LLMErrorResult."""

    def test_returns_error_result(self) -> None:
        """Should return LLMErrorResult with all fields."""
        exc = Exception("Rate limit exceeded")
        result = classify_error(exc, provider="gemini")

        assert isinstance(result, LLMErrorResult)
        assert result.code == LLMErrorCode.RATE_LIMITED
        assert result.provider == "gemini"
        assert result.message == ERROR_MESSAGES[LLMErrorCode.RATE_LIMITED]
        assert result.retry_suggested is True
        assert result.retry_after_seconds == 60

    def test_includes_technical_details(self) -> None:
        """Should include technical details."""
        exc = ValueError("Invalid input data")
        result = classify_error(exc, provider="openai")

        assert result.technical_details is not None
        assert "ValueError" in result.technical_details
        assert "Invalid input" in result.technical_details

    def test_truncates_long_error_messages(self) -> None:
        """Should truncate very long error messages."""
        long_message = "x" * 500
        exc = Exception(long_message)
        result = classify_error(exc)

        assert len(result.technical_details) <= 220  # ~200 + type name

    def test_uses_default_provider(self) -> None:
        """Should use 'unknown' as default provider."""
        exc = Exception("Some error")
        result = classify_error(exc)

        assert result.provider == "unknown"


# =============================================================================
# User-Friendly Message Tests
# =============================================================================


class TestErrorMessages:
    """Test user-friendly message content."""

    def test_all_error_codes_have_messages(self) -> None:
        """Every error code should have a user-friendly message."""
        for code in LLMErrorCode:
            assert code in ERROR_MESSAGES, f"Missing message for {code}"
            assert len(ERROR_MESSAGES[code]) > 10, f"Message too short for {code}"

    def test_messages_dont_expose_technical_details(self) -> None:
        """Messages should not contain technical jargon."""
        technical_terms = ["HTTP", "JSON", "API endpoint", "exception", "stack trace"]
        for code, message in ERROR_MESSAGES.items():
            for term in technical_terms:
                assert term.lower() not in message.lower(), (
                    f"Technical term '{term}' found in {code} message"
                )

    def test_messages_are_actionable(self) -> None:
        """Messages should give users actionable guidance."""
        # At least some messages should suggest what to do
        actionable_phrases = ["try again", "please", "contact support", "rephrase"]
        has_actionable = sum(
            1 for msg in ERROR_MESSAGES.values()
            if any(phrase in msg.lower() for phrase in actionable_phrases)
        )
        assert has_actionable >= 8, "Most messages should be actionable"


# =============================================================================
# Retry Recommendation Tests
# =============================================================================


class TestRetryRecommendations:
    """Test retry recommendations."""

    def test_all_error_codes_have_recommendations(self) -> None:
        """Every error code should have a retry recommendation."""
        for code in LLMErrorCode:
            assert code in RETRY_RECOMMENDATIONS, f"Missing retry recommendation for {code}"

    def test_rate_limited_suggests_retry_with_delay(self) -> None:
        """Rate limited should suggest retry with delay."""
        retry, after = RETRY_RECOMMENDATIONS[LLMErrorCode.RATE_LIMITED]
        assert retry is True
        assert after is not None
        assert after >= 30  # Should wait at least 30 seconds

    def test_quota_exceeded_no_retry(self) -> None:
        """Quota exceeded should not suggest retry."""
        retry, after = RETRY_RECOMMENDATIONS[LLMErrorCode.QUOTA_EXCEEDED]
        assert retry is False

    def test_content_filtered_no_retry(self) -> None:
        """Content filtered should not suggest retry."""
        retry, after = RETRY_RECOMMENDATIONS[LLMErrorCode.CONTENT_FILTERED]
        assert retry is False

    def test_context_too_long_no_retry(self) -> None:
        """Context too long should not suggest retry."""
        retry, after = RETRY_RECOMMENDATIONS[LLMErrorCode.CONTEXT_TOO_LONG]
        assert retry is False

    def test_timeout_suggests_retry(self) -> None:
        """Timeout should suggest retry."""
        retry, after = RETRY_RECOMMENDATIONS[LLMErrorCode.TIMEOUT]
        assert retry is True

    def test_connection_error_suggests_retry(self) -> None:
        """Connection error should suggest retry."""
        retry, after = RETRY_RECOMMENDATIONS[LLMErrorCode.CONNECTION_ERROR]
        assert retry is True


# =============================================================================
# Error Handling Wrapper Tests
# =============================================================================


class TestWithErrorHandling:
    """Test async error handling wrapper."""

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self) -> None:
        """Should return result and None error on success."""
        async def successful_op():
            return "success"

        result, error = await with_error_handling(successful_op, provider="gemini")

        assert result == "success"
        assert error is None

    @pytest.mark.asyncio
    async def test_returns_error_on_exception(self) -> None:
        """Should return None result and error on exception."""
        async def failing_op():
            raise Exception("Rate limit exceeded")

        result, error = await with_error_handling(failing_op, provider="gemini")

        assert result is None
        assert error is not None
        assert error.code == LLMErrorCode.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_includes_provider_in_error(self) -> None:
        """Should include provider in error result."""
        async def failing_op():
            raise Exception("Some error")

        result, error = await with_error_handling(failing_op, provider="openai")

        assert error.provider == "openai"


# =============================================================================
# Response Formatting Tests
# =============================================================================


class TestFormatErrorForResponse:
    """Test API response formatting."""

    def test_formats_all_required_fields(self) -> None:
        """Should format all fields for API response."""
        error = LLMErrorResult(
            code=LLMErrorCode.RATE_LIMITED,
            message="Please wait and try again",
            retry_suggested=True,
            retry_after_seconds=60,
            provider="gemini",
        )

        response = format_error_for_response(error)

        assert response["error_code"] == "RATE_LIMITED"
        assert response["error_message"] == "Please wait and try again"
        assert response["retry_suggested"] is True
        assert response["retry_after_seconds"] == 60

    def test_handles_none_retry_after(self) -> None:
        """Should handle None retry_after_seconds."""
        error = LLMErrorResult(
            code=LLMErrorCode.CONTENT_FILTERED,
            message="Content blocked",
            retry_suggested=False,
            retry_after_seconds=None,
        )

        response = format_error_for_response(error)

        assert response["retry_after_seconds"] is None

    def test_does_not_include_technical_details(self) -> None:
        """Should not expose technical details in response."""
        error = LLMErrorResult(
            code=LLMErrorCode.API_ERROR,
            message="Something went wrong",
            technical_details="HTTPError: 500 Internal Server Error at /api/v1/chat",
        )

        response = format_error_for_response(error)

        assert "technical_details" not in response
        assert "HTTPError" not in str(response)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_handles_empty_exception_message(self) -> None:
        """Should handle exceptions with empty messages."""
        exc = Exception("")
        result = classify_error(exc)

        assert result.code == LLMErrorCode.UNKNOWN_ERROR

    def test_handles_none_like_message(self) -> None:
        """Should handle None-like exception messages."""
        exc = Exception(None)
        result = classify_error(exc)

        assert result.code == LLMErrorCode.UNKNOWN_ERROR

    def test_handles_unicode_error_messages(self) -> None:
        """Should handle unicode in error messages."""
        exc = Exception("Error: 请求失败 - rate limit")
        result = classify_error(exc)

        # Should still detect rate limit
        assert result.code == LLMErrorCode.RATE_LIMITED

    def test_error_code_enum_values(self) -> None:
        """Error codes should be uppercase strings."""
        for code in LLMErrorCode:
            assert code.value == code.value.upper()
            assert "_" in code.value or code.value.isalpha()
