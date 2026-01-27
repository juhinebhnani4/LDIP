"""LLM error handler for user-friendly error messages.

Story 5.5: User-Friendly LLM Error Messages

Provides standardized error handling for LLM API calls with:
- Error code to user-friendly message mapping
- Automatic retry suggestions based on error type
- Rate limit detection and backoff recommendations
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class LLMErrorCode(str, Enum):
    """Standardized error codes for LLM failures.

    Pre-mortem fix: Use enums, not raw strings, for error codes.
    """

    # Rate limiting
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # API errors
    API_ERROR = "API_ERROR"
    TIMEOUT = "TIMEOUT"
    CONNECTION_ERROR = "CONNECTION_ERROR"

    # Content errors
    INVALID_RESPONSE = "INVALID_RESPONSE"
    CONTENT_FILTERED = "CONTENT_FILTERED"
    CONTEXT_TOO_LONG = "CONTEXT_TOO_LONG"

    # Generic errors
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


@dataclass
class LLMErrorResult:
    """Result of an LLM operation that resulted in an error.

    Story 5.5: User-Friendly LLM Error Messages

    Attributes:
        code: Standardized error code.
        message: User-friendly error message.
        technical_details: Technical details for logging.
        retry_suggested: Whether retrying might help.
        retry_after_seconds: Suggested wait time before retry.
        provider: The LLM provider that failed (gemini, openai).
    """

    code: LLMErrorCode
    message: str
    technical_details: str | None = None
    retry_suggested: bool = False
    retry_after_seconds: int | None = None
    provider: str | None = None


# =============================================================================
# Error Message Mappings
# =============================================================================

# User-friendly messages for each error code
ERROR_MESSAGES = {
    LLMErrorCode.RATE_LIMITED: (
        "Our AI service is temporarily busy. Please wait a moment and try again."
    ),
    LLMErrorCode.QUOTA_EXCEEDED: (
        "We've reached our AI usage limit for the day. "
        "Please try again tomorrow or contact support."
    ),
    LLMErrorCode.API_ERROR: (
        "Something went wrong with our AI service. Please try again."
    ),
    LLMErrorCode.TIMEOUT: (
        "The AI took too long to respond. Please try with a shorter question or try again."
    ),
    LLMErrorCode.CONNECTION_ERROR: (
        "Unable to connect to our AI service. Please check your connection and try again."
    ),
    LLMErrorCode.INVALID_RESPONSE: (
        "We received an unexpected response from our AI. Please try rephrasing your question."
    ),
    LLMErrorCode.CONTENT_FILTERED: (
        "Your question couldn't be processed due to content restrictions. "
        "Please try rephrasing."
    ),
    LLMErrorCode.CONTEXT_TOO_LONG: (
        "Your question requires too much context. Please try a more specific question."
    ),
    LLMErrorCode.SERVICE_UNAVAILABLE: (
        "Our AI service is temporarily unavailable. Please try again in a few minutes."
    ),
    LLMErrorCode.UNKNOWN_ERROR: (
        "An unexpected error occurred. Please try again."
    ),
}

# Retry recommendations for each error type
RETRY_RECOMMENDATIONS = {
    LLMErrorCode.RATE_LIMITED: (True, 60),  # Retry after 60 seconds
    LLMErrorCode.QUOTA_EXCEEDED: (False, None),  # Don't retry
    LLMErrorCode.API_ERROR: (True, 5),  # Retry after 5 seconds
    LLMErrorCode.TIMEOUT: (True, None),  # Retry immediately
    LLMErrorCode.CONNECTION_ERROR: (True, 5),  # Retry after 5 seconds
    LLMErrorCode.INVALID_RESPONSE: (True, None),  # Retry immediately
    LLMErrorCode.CONTENT_FILTERED: (False, None),  # Don't retry (user needs to rephrase)
    LLMErrorCode.CONTEXT_TOO_LONG: (False, None),  # Don't retry (user needs to rephrase)
    LLMErrorCode.SERVICE_UNAVAILABLE: (True, 30),  # Retry after 30 seconds
    LLMErrorCode.UNKNOWN_ERROR: (True, 5),  # Retry after 5 seconds
}


def classify_error(exception: Exception, provider: str = "unknown") -> LLMErrorResult:
    """Classify an exception into a user-friendly error result.

    Story 5.5: Error classification for user-friendly messages.

    Args:
        exception: The exception that occurred.
        provider: The LLM provider (gemini, openai).

    Returns:
        LLMErrorResult with user-friendly message.
    """
    error_str = str(exception).lower()
    error_type = type(exception).__name__

    # Classify based on exception type and message content
    code = _classify_error_code(error_str, error_type)

    retry_suggested, retry_after = RETRY_RECOMMENDATIONS.get(
        code, (True, 5)
    )

    result = LLMErrorResult(
        code=code,
        message=ERROR_MESSAGES.get(code, ERROR_MESSAGES[LLMErrorCode.UNKNOWN_ERROR]),
        technical_details=f"{error_type}: {str(exception)[:200]}",
        retry_suggested=retry_suggested,
        retry_after_seconds=retry_after,
        provider=provider,
    )

    logger.warning(
        "llm_error_classified",
        code=code.value,
        provider=provider,
        error_type=error_type,
        retry_suggested=retry_suggested,
    )

    return result


def _classify_error_code(error_str: str, error_type: str) -> LLMErrorCode:
    """Classify error string into error code.

    Args:
        error_str: Lowercase error message.
        error_type: Exception type name.

    Returns:
        Classified LLMErrorCode.
    """
    # Rate limiting patterns
    if any(pattern in error_str for pattern in [
        "rate limit", "ratelimit", "rate_limit",
        "429", "too many requests", "quota exceeded",
        "resource exhausted", "resourceexhausted",
    ]):
        if "quota" in error_str:
            return LLMErrorCode.QUOTA_EXCEEDED
        return LLMErrorCode.RATE_LIMITED

    # Timeout patterns
    if any(pattern in error_str for pattern in [
        "timeout", "timed out", "deadline exceeded",
        "deadline_exceeded", "read timed out",
    ]):
        return LLMErrorCode.TIMEOUT

    # Connection patterns
    if any(pattern in error_str for pattern in [
        "connection", "connect", "network",
        "unreachable", "dns", "ssl",
    ]):
        return LLMErrorCode.CONNECTION_ERROR

    # Content filtering
    if any(pattern in error_str for pattern in [
        "content filter", "blocked", "safety",
        "recitation", "harmful", "prohibited",
    ]):
        return LLMErrorCode.CONTENT_FILTERED

    # Context length
    if any(pattern in error_str for pattern in [
        "context length", "token limit", "too long",
        "max tokens", "maximum context",
    ]):
        return LLMErrorCode.CONTEXT_TOO_LONG

    # Service unavailable
    if any(pattern in error_str for pattern in [
        "service unavailable", "503", "overloaded",
        "maintenance", "temporarily unavailable",
    ]):
        return LLMErrorCode.SERVICE_UNAVAILABLE

    # Invalid response
    if any(pattern in error_str for pattern in [
        "invalid response", "parse error", "json",
        "unexpected response", "malformed",
    ]):
        return LLMErrorCode.INVALID_RESPONSE

    # API errors (catch-all for HTTP errors)
    if any(pattern in error_str for pattern in [
        "400", "401", "403", "404", "500", "502", "504",
        "api error", "api_error", "http error",
    ]):
        return LLMErrorCode.API_ERROR

    # Default
    return LLMErrorCode.UNKNOWN_ERROR


async def with_error_handling(
    operation: Callable[[], T],
    provider: str = "unknown",
    context: str = "LLM operation",
) -> tuple[T | None, LLMErrorResult | None]:
    """Execute an LLM operation with standardized error handling.

    Story 5.5: Wrapper for consistent error handling.

    Args:
        operation: Async callable that performs the LLM operation.
        provider: LLM provider name for error classification.
        context: Description of the operation for logging.

    Returns:
        Tuple of (result, error). One will be None.

    Example:
        result, error = await with_error_handling(
            lambda: gemini.generate_content(prompt),
            provider="gemini",
            context="chat response",
        )
        if error:
            return error.message  # User-friendly message
    """
    try:
        result = await operation()
        return result, None
    except Exception as e:
        error = classify_error(e, provider)
        logger.error(
            "llm_operation_failed",
            context=context,
            code=error.code.value,
            provider=provider,
            error=error.technical_details,
        )
        return None, error


def format_error_for_response(error: LLMErrorResult) -> dict:
    """Format error result for API response.

    Story 5.5: Format for frontend consumption.

    Args:
        error: The LLMErrorResult to format.

    Returns:
        Dict suitable for API response.
    """
    return {
        "error_code": error.code.value,
        "error_message": error.message,
        "retry_suggested": error.retry_suggested,
        "retry_after_seconds": error.retry_after_seconds,
    }
