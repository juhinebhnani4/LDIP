"""Subtle violation detector using GPT-4o-mini.

Story 8-2: GPT-4o-mini Subtle Violation Detection

This service detects cleverly-worded legal conclusion requests that
bypass regex patterns. Part of the two-phase safety pipeline:

1. Fast-path regex (Story 8-1) - blocks obvious violations (< 5ms)
2. LLM detection (Story 8-2) - catches subtle violations (~500-2000ms)

CRITICAL: Uses GPT-4o-mini (NOT GPT-4) - 200x cheaper for input tokens.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import structlog

from app.core.config import get_settings
from app.models.safety import SubtleViolationCheck
from app.services.safety.prompts import (
    SUBTLE_DETECTION_SYSTEM_PROMPT,
    format_subtle_detection_prompt,
    validate_detection_response,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 0.5
MAX_RETRY_DELAY = 10.0

# GPT-4o-mini pricing (as of Jan 2025)
# https://openai.com/pricing
# M3 Fix: These can be overridden via settings if pricing changes
DEFAULT_INPUT_COST_PER_1K = 0.00015  # $0.00015 per 1K input tokens
DEFAULT_OUTPUT_COST_PER_1K = 0.0006  # $0.0006 per 1K output tokens

# H2 Fix: Characters to sanitize from queries to prevent prompt injection
# These patterns could be used to break out of the JSON prompt context
SANITIZE_PATTERNS = [
    ('"""', '"'),  # Triple quotes could break prompt
    ("'''", "'"),  # Triple single quotes
    ("\n\n\n", "\n"),  # Excessive newlines
]


# =============================================================================
# Exceptions
# =============================================================================


class SubtleDetectorError(Exception):
    """Base exception for subtle detector operations.

    Story 8-2: Exception hierarchy for LLM-based detection.
    """

    def __init__(
        self,
        message: str,
        code: str = "SUBTLE_DETECTOR_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class OpenAIConfigurationError(SubtleDetectorError):
    """Raised when OpenAI is not properly configured.

    Story 8-2: Task 3.2 - Configuration validation.
    """

    def __init__(self, message: str):
        super().__init__(message, code="OPENAI_NOT_CONFIGURED", is_retryable=False)


class DetectionParseError(SubtleDetectorError):
    """Raised when LLM response cannot be parsed.

    Story 8-2: Task 3.4 - Response parsing errors.
    """

    def __init__(self, message: str):
        super().__init__(message, code="PARSE_ERROR", is_retryable=True)


# =============================================================================
# Story 8-2: SubtleViolationDetector Service (Task 3)
# =============================================================================


class SubtleViolationDetector:
    """GPT-4o-mini based subtle violation detector.

    Story 8-2: Detects cleverly-worded legal conclusion requests
    that bypass regex patterns.

    This is the second phase of the safety pipeline, called only
    when queries pass the fast-path regex check (Story 8-1).

    Example:
        >>> detector = get_subtle_violation_detector()
        >>> check = await detector.detect_violation(
        ...     "Based on the evidence, is it clear that..."
        ... )
        >>> check.is_safe
        False
        >>> check.violation_type
        'implicit_conclusion_request'
    """

    def __init__(self) -> None:
        """Initialize subtle violation detector.

        Story 8-2: Task 3.2 - Lazy OpenAI client initialization.
        """
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_name = settings.openai_safety_model
        self.timeout = settings.safety_llm_timeout
        self._client = None

        logger.info(
            "subtle_violation_detector_configured",
            model=self.model_name,
            timeout=self.timeout,
        )

    @property
    def client(self):
        """Get or create OpenAI client (lazy initialization).

        Story 8-2: Task 3.2 - Lazy client initialization.

        Returns:
            AsyncOpenAI client instance.

        Raises:
            OpenAIConfigurationError: If API key not configured.
        """
        if self._client is None:
            if not self.api_key:
                raise OpenAIConfigurationError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
                )

            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
                logger.info(
                    "subtle_detector_client_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("subtle_detector_init_failed", error=str(e))
                raise OpenAIConfigurationError(
                    f"Failed to initialize OpenAI client: {e}"
                ) from e

        return self._client

    def _sanitize_query(self, query: str) -> str:
        """Sanitize user query to prevent prompt injection.

        Story 8-2: H2 Fix - Input sanitization before LLM call.

        Args:
            query: Raw user query.

        Returns:
            Sanitized query safe for LLM prompt embedding.
        """
        sanitized = query

        # Apply sanitization patterns
        for pattern, replacement in SANITIZE_PATTERNS:
            sanitized = sanitized.replace(pattern, replacement)

        # Truncate excessively long queries (prevent token exhaustion attacks)
        max_query_length = 2000
        if len(sanitized) > max_query_length:
            logger.warning(
                "query_truncated_for_safety",
                original_length=len(query),
                truncated_to=max_query_length,
            )
            sanitized = sanitized[:max_query_length]

        return sanitized

    async def detect_violation(self, query: str) -> SubtleViolationCheck:
        """Detect subtle legal conclusion requests using GPT-4o-mini.

        Story 8-2: AC #1-2 - LLM-based detection.

        This method analyzes a query that has passed the fast-path regex
        check to detect implicit legal conclusion requests.

        Args:
            query: User query that passed regex detection.

        Returns:
            SubtleViolationCheck with detection result.
        """
        start_time = time.perf_counter()

        # H2 Fix: Sanitize query before sending to LLM
        sanitized_query = self._sanitize_query(query)

        logger.debug(
            "subtle_detection_start",
            query_length=len(sanitized_query),
        )

        try:
            # Call GPT-4o-mini with retry (using sanitized query)
            result, input_tokens, output_tokens = await self._call_llm_with_retry(sanitized_query)

            check_time_ms = (time.perf_counter() - start_time) * 1000

            # Calculate cost
            cost_usd = self._calculate_cost(input_tokens, output_tokens)

            # Handle safe queries
            if result.get("is_safe", True):
                logger.debug(
                    "subtle_detection_safe",
                    check_time_ms=round(check_time_ms, 2),
                    cost_usd=round(cost_usd, 6),
                )
                return SubtleViolationCheck(
                    is_safe=True,
                    violation_detected=False,
                    explanation=result.get("explanation", "Query is safe"),
                    confidence=result.get("confidence", 1.0),
                    llm_cost_usd=cost_usd,
                    check_time_ms=check_time_ms,
                )

            # Handle blocked queries
            violation_type = result.get("violation_type")

            logger.info(
                "subtle_violation_detected",
                violation_type=violation_type,
                confidence=result.get("confidence", 0.0),
                check_time_ms=round(check_time_ms, 2),
            )

            return SubtleViolationCheck(
                is_safe=False,
                violation_detected=True,
                violation_type=violation_type,
                explanation=result.get("explanation", ""),
                suggested_rewrite=result.get("suggested_rewrite", ""),
                confidence=result.get("confidence", 0.0),
                llm_cost_usd=cost_usd,
                check_time_ms=check_time_ms,
            )

        except OpenAIConfigurationError:
            # Re-raise configuration errors (non-retryable)
            raise
        except Exception as e:
            # Log error and return fail-open result
            check_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "subtle_detection_error",
                error=str(e),
                error_type=type(e).__name__,
                check_time_ms=round(check_time_ms, 2),
            )
            # Fail open - allow query through if LLM fails
            raise SubtleDetectorError(
                f"Subtle detection failed: {e}",
                is_retryable=False,
            ) from e

    async def _call_llm_with_retry(
        self, query: str
    ) -> tuple[dict, int, int]:
        """Call GPT-4o-mini with retry logic.

        Story 8-2: Task 3.6 - Retry with exponential backoff.

        Args:
            query: User query to analyze.

        Returns:
            Tuple of (parsed_response, input_tokens, output_tokens).

        Raises:
            SubtleDetectorError: If all retries fail.
        """
        user_prompt = format_subtle_detection_prompt(query)
        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": SUBTLE_DETECTION_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1,  # Low temperature for consistent classification
                    ),
                    timeout=self.timeout,
                )

                # Extract token counts
                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0

                # Parse response
                response_text = response.choices[0].message.content
                parsed = self._parse_llm_response(response_text)

                logger.debug(
                    "llm_call_success",
                    attempt=attempt + 1,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

                return parsed, input_tokens, output_tokens

            except TimeoutError as e:
                last_error = e
                logger.warning(
                    "llm_call_timeout",
                    attempt=attempt + 1,
                    timeout=self.timeout,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

            except OpenAIConfigurationError:
                # Don't retry configuration errors
                raise

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for retryable errors
                is_retryable = any(
                    indicator in error_str
                    for indicator in [
                        "429", "rate", "quota", "500", "502", "503", "504",
                        "timeout", "connection", "temporary"
                    ]
                )

                if is_retryable and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "llm_call_retrying",
                        attempt=attempt + 1,
                        max_attempts=MAX_RETRIES,
                        retry_delay=retry_delay,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_retryable:
                    break

        logger.error(
            "llm_call_failed",
            error=str(last_error),
            attempts=MAX_RETRIES,
        )

        raise SubtleDetectorError(
            f"LLM call failed after {MAX_RETRIES} attempts: {last_error}",
            is_retryable=False,
        )

    def _parse_llm_response(self, response_text: str) -> dict:
        """Parse and validate LLM JSON response.

        Story 8-2: Task 3.4 - Response parsing.

        Args:
            response_text: Raw JSON response from LLM.

        Returns:
            Parsed and validated response dict.

        Raises:
            DetectionParseError: If response cannot be parsed.
        """
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning(
                "llm_response_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            raise DetectionParseError(f"Invalid JSON response: {e}") from e

        # Validate response schema
        errors = validate_detection_response(parsed)
        if errors:
            logger.warning(
                "llm_response_validation_failed",
                errors=errors,
                response_preview=response_text[:200] if response_text else "",
            )
            # Continue with partial response for graceful degradation

        # H1 Fix: Validate violation_type against allowed ViolationType Literal values
        # If LLM returns an invalid type, coerce to None (safe behavior)
        valid_violation_types = {
            "implicit_conclusion_request",
            "indirect_outcome_seeking",
            "hypothetical_legal_advice",
            None,
        }
        if parsed.get("violation_type") not in valid_violation_types:
            logger.warning(
                "llm_invalid_violation_type_coerced",
                received=parsed.get("violation_type"),
                coerced_to=None,
            )
            parsed["violation_type"] = None

        return parsed

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost of LLM call.

        Story 8-2: Task 3.5 - Cost tracking.
        M3 Fix: Uses configurable pricing from settings with fallback to defaults.

        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Cost in USD.
        """
        # M3 Fix: Get pricing from settings if configured, else use defaults
        # Use hasattr check to avoid MagicMock issues in tests
        settings = get_settings()

        if hasattr(settings, "safety_llm_input_cost_per_1k"):
            input_cost_per_1k = settings.safety_llm_input_cost_per_1k
            # Check if it's a real number (not a MagicMock)
            if not isinstance(input_cost_per_1k, (int, float)):
                input_cost_per_1k = DEFAULT_INPUT_COST_PER_1K
        else:
            input_cost_per_1k = DEFAULT_INPUT_COST_PER_1K

        if hasattr(settings, "safety_llm_output_cost_per_1k"):
            output_cost_per_1k = settings.safety_llm_output_cost_per_1k
            # Check if it's a real number (not a MagicMock)
            if not isinstance(output_cost_per_1k, (int, float)):
                output_cost_per_1k = DEFAULT_OUTPUT_COST_PER_1K
        else:
            output_cost_per_1k = DEFAULT_OUTPUT_COST_PER_1K

        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        return input_cost + output_cost


# =============================================================================
# Story 8-2: Singleton Factory (Task 3.7)
# M1 Fix: Using thread-safe double-check locking pattern (consistent with GuardrailService)
# =============================================================================

# Singleton instance (thread-safe)
_subtle_detector: SubtleViolationDetector | None = None
_detector_lock = threading.Lock()


def get_subtle_violation_detector() -> SubtleViolationDetector:
    """Get singleton subtle violation detector instance.

    Story 8-2: Task 3.7 - Factory function with thread-safe initialization.
    M1 Fix: Uses double-check locking pattern consistent with GuardrailService.

    Returns:
        SubtleViolationDetector singleton instance.
    """
    global _subtle_detector  # noqa: PLW0603

    if _subtle_detector is None:
        with _detector_lock:
            # Double-check locking pattern
            if _subtle_detector is None:
                _subtle_detector = SubtleViolationDetector()

    return _subtle_detector


def reset_subtle_violation_detector() -> None:
    """Reset singleton for testing.

    Story 8-2: Reset function for test isolation.

    Note:
        This creates a fresh instance on next get_subtle_violation_detector() call.
    """
    global _subtle_detector  # noqa: PLW0603

    with _detector_lock:
        _subtle_detector = None

    logger.debug("subtle_violation_detector_reset")
