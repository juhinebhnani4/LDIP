"""Combined language police service with regex + LLM polishing.

Story 8-3: Language Policing (AC #1-6)

This is the full output sanitization pipeline that combines:
1. Quote detection and protection (AC #6)
2. Fast regex replacements (AC #1-4, < 5ms)
3. LLM polish for subtle conclusions (AC #5, ~500-2000ms)

CRITICAL: LLM failures should NOT block output - fall back to regex-only.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import structlog

from app.core.config import get_settings
from app.models.safety import (
    LanguagePolicingResult,
    ReplacementRecord,
)
from app.services.safety.language_policing import (
    LanguagePolicingService,
    get_language_policing_service,
)
from app.services.safety.prompts import (
    SUBTLE_POLICING_SYSTEM_PROMPT,
    format_subtle_policing_prompt,
    validate_policing_response,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Retry configuration (same as Story 8-2)
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 0.5
MAX_RETRY_DELAY = 10.0

# GPT-4o-mini pricing (as of Jan 2025)
DEFAULT_INPUT_COST_PER_1K = 0.00015  # $0.00015 per 1K input tokens
DEFAULT_OUTPUT_COST_PER_1K = 0.0006  # $0.0006 per 1K output tokens

# Input sanitization patterns (prevent prompt injection)
SANITIZE_PATTERNS = [
    ('"""', '"'),  # Triple quotes could break prompt
    ("'''", "'"),  # Triple single quotes
    ("\n\n\n", "\n"),  # Excessive newlines
]


# =============================================================================
# Exceptions
# =============================================================================


class LanguagePoliceError(Exception):
    """Base exception for language police operations.

    Story 8-3: Exception hierarchy for policing.
    """

    def __init__(
        self,
        message: str,
        code: str = "LANGUAGE_POLICE_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class PolishingParseError(LanguagePoliceError):
    """Raised when LLM polishing response cannot be parsed.

    Story 8-3: Task 5.4 - Response parsing errors.
    """

    def __init__(self, message: str):
        super().__init__(message, code="PARSE_ERROR", is_retryable=True)


# =============================================================================
# Story 8-3: LanguagePolice Service (Task 6.1-6.5)
# =============================================================================


class LanguagePolice:
    """Combined language police with regex + LLM polishing.

    Story 8-3: Full output sanitization pipeline.

    Pipeline:
    1. Quote detection and protection
    2. Fast regex replacements (< 5ms)
    3. If enabled, LLM polish for subtle conclusions (~500-2000ms)

    Example:
        >>> police = get_language_police()
        >>> result = await police.police_output(
        ...     "The evidence proves defendant is guilty of violating Section 138."
        ... )
        >>> result.sanitized_text
        "The evidence suggests defendant may face liability regarding Section 138."
    """

    def __init__(
        self,
        policing_service: LanguagePolicingService | None = None,
    ) -> None:
        """Initialize language police.

        Story 8-3: Task 6.2 - Service initialization.

        Args:
            policing_service: Optional regex policing service (for testing).
        """
        self._policing_service = policing_service or get_language_policing_service()
        self._client = None

        # Load settings
        settings = get_settings()
        self._llm_enabled = settings.policing_llm_enabled
        self._model_name = settings.openai_safety_model
        self._api_key = settings.openai_api_key
        self._timeout = settings.policing_llm_timeout

        logger.info(
            "language_police_initialized",
            llm_enabled=self._llm_enabled,
            model=self._model_name if self._llm_enabled else "disabled",
        )

    @property
    def client(self):
        """Get or create OpenAI client (lazy initialization).

        Story 8-3: Task 5.3 - Lazy client initialization.

        Returns:
            AsyncOpenAI client instance.

        Raises:
            LanguagePoliceError: If API key not configured.
        """
        if self._client is None:
            if not self._api_key:
                raise LanguagePoliceError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY environment variable.",
                    code="OPENAI_NOT_CONFIGURED",
                    is_retryable=False,
                )

            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self._api_key)
                logger.info(
                    "language_police_client_initialized",
                    model=self._model_name,
                )
            except Exception as e:
                logger.error("language_police_init_failed", error=str(e))
                raise LanguagePoliceError(
                    f"Failed to initialize OpenAI client: {e}",
                    is_retryable=False,
                ) from e

        return self._client

    async def police_output(self, text: str) -> LanguagePolicingResult:
        """Apply full language policing pipeline.

        Story 8-3: AC #1-6, Task 6.3 - Complete sanitization.

        Pipeline:
        1. Apply fast-path regex policing (always runs)
        2. If LLM enabled, apply subtle polishing
        3. Return combined result with metrics

        Args:
            text: LLM output to sanitize.

        Returns:
            LanguagePolicingResult with fully sanitized text.
        """
        start_time = time.perf_counter()

        # Handle empty input
        if not text or not text.strip():
            return LanguagePolicingResult(
                original_text=text,
                sanitized_text=text,
                replacements_made=[],
                quotes_preserved=[],
                llm_policing_applied=False,
                sanitization_time_ms=0.0,
            )

        # Phase 1: Fast regex policing (always runs)
        regex_result = self._policing_service.sanitize_text(text)

        # If LLM policing is disabled, return regex-only result
        if not self._llm_enabled:
            total_time_ms = (time.perf_counter() - start_time) * 1000
            return LanguagePolicingResult(
                original_text=text,
                sanitized_text=regex_result.sanitized_text,
                replacements_made=regex_result.replacements_made,
                quotes_preserved=regex_result.quotes_preserved,
                llm_policing_applied=False,
                sanitization_time_ms=total_time_ms,
            )

        # Phase 2: LLM polish for subtle conclusions
        try:
            llm_result = await self._apply_llm_polish(regex_result.sanitized_text)

            total_time_ms = (time.perf_counter() - start_time) * 1000

            # Combine regex and LLM changes
            all_replacements = list(regex_result.replacements_made)

            # Add LLM changes as replacement records (H2 fix: handle structured format)
            for change in llm_result.get("changes_made", []):
                if isinstance(change, dict):
                    # New structured format: {original, replacement}
                    all_replacements.append(
                        ReplacementRecord(
                            original_phrase=change.get("original", ""),
                            replacement_phrase=change.get("replacement", ""),
                            position_start=0,  # Position unknown for LLM changes
                            position_end=0,
                            rule_id="llm_subtle_polish",
                        )
                    )
                elif isinstance(change, str):
                    # Legacy string format (backward compatibility)
                    all_replacements.append(
                        ReplacementRecord(
                            original_phrase=change,
                            replacement_phrase="[LLM polished]",
                            position_start=0,
                            position_end=0,
                            rule_id="llm_subtle_polish",
                        )
                    )

            logger.info(
                "language_policing_complete",
                regex_replacements=len(regex_result.replacements_made),
                llm_changes=len(llm_result.get("changes_made", [])),
                total_time_ms=round(total_time_ms, 2),
                llm_cost_usd=round(llm_result.get("cost_usd", 0.0), 6),
            )

            return LanguagePolicingResult(
                original_text=text,
                sanitized_text=llm_result["sanitized_text"],
                replacements_made=all_replacements,
                quotes_preserved=regex_result.quotes_preserved,
                llm_policing_applied=True,
                sanitization_time_ms=total_time_ms,
                llm_cost_usd=llm_result.get("cost_usd", 0.0),
                text_truncated=llm_result.get("text_truncated", False),
                original_length=llm_result.get("original_length", len(text)),
            )

        except Exception as e:
            # LLM failures should NOT block output - use regex-only result
            total_time_ms = (time.perf_counter() - start_time) * 1000

            logger.warning(
                "llm_policing_failed_using_regex_only",
                error=str(e),
                error_type=type(e).__name__,
                total_time_ms=round(total_time_ms, 2),
            )

            return LanguagePolicingResult(
                original_text=text,
                sanitized_text=regex_result.sanitized_text,
                replacements_made=regex_result.replacements_made,
                quotes_preserved=regex_result.quotes_preserved,
                llm_policing_applied=False,
                sanitization_time_ms=total_time_ms,
            )

    async def _apply_llm_polish(self, text: str) -> dict:
        """Apply GPT-4o-mini polishing to text.

        Story 8-3: Task 5.3-5.5 - LLM polishing.
        M1 fix: Track truncation in result.

        Args:
            text: Text after regex sanitization.

        Returns:
            Dict with sanitized_text, changes_made, confidence, cost_usd, text_truncated.
        """
        # Sanitize text to prevent prompt injection (M1: track truncation)
        sanitized_input, was_truncated = self._sanitize_input(text)

        # Call LLM with retry
        result, input_tokens, output_tokens = await self._call_llm_with_retry(
            sanitized_input
        )

        # Calculate cost
        cost_usd = self._calculate_cost(input_tokens, output_tokens)
        result["cost_usd"] = cost_usd
        result["text_truncated"] = was_truncated
        result["original_length"] = len(text)

        return result

    def _sanitize_input(self, text: str) -> tuple[str, bool]:
        """Sanitize input text to prevent prompt injection.

        Story 8-3: Task 5.3 - Input sanitization.
        M1 fix: Return truncation flag for audit.

        Args:
            text: Raw text to sanitize.

        Returns:
            Tuple of (sanitized_text, was_truncated).
        """
        sanitized = text
        was_truncated = False

        for pattern, replacement in SANITIZE_PATTERNS:
            sanitized = sanitized.replace(pattern, replacement)

        # Truncate excessively long text
        max_length = 8000  # Reasonable limit for policing
        if len(sanitized) > max_length:
            logger.warning(
                "text_truncated_for_polishing",
                original_length=len(text),
                truncated_to=max_length,
            )
            sanitized = sanitized[:max_length]
            was_truncated = True

        return sanitized, was_truncated

    async def _call_llm_with_retry(
        self, text: str
    ) -> tuple[dict, int, int]:
        """Call GPT-4o-mini with retry logic.

        Story 8-3: Task 5.3 - LLM call with retry.

        Args:
            text: Text to polish.

        Returns:
            Tuple of (parsed_response, input_tokens, output_tokens).

        Raises:
            LanguagePoliceError: If all retries fail.
        """
        user_prompt = format_subtle_policing_prompt(text)
        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self._model_name,
                        messages=[
                            {"role": "system", "content": SUBTLE_POLICING_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1,  # Low temperature for consistent output
                    ),
                    timeout=self._timeout,
                )

                # Extract token counts
                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0

                # Parse response
                response_text = response.choices[0].message.content
                parsed = self._parse_llm_response(response_text, text)

                logger.debug(
                    "llm_polish_success",
                    attempt=attempt + 1,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    changes_made=len(parsed.get("changes_made", [])),
                )

                return parsed, input_tokens, output_tokens

            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    "llm_polish_timeout",
                    attempt=attempt + 1,
                    timeout=self._timeout,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

            except LanguagePoliceError:
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
                        "llm_polish_retrying",
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
            "llm_polish_failed",
            error=str(last_error),
            attempts=MAX_RETRIES,
        )

        raise LanguagePoliceError(
            f"LLM polish failed after {MAX_RETRIES} attempts: {last_error}",
            is_retryable=False,
        )

    def _parse_llm_response(self, response_text: str, original_text: str) -> dict:
        """Parse and validate LLM JSON response.

        Story 8-3: Task 5.4 - Response parsing.

        Args:
            response_text: Raw JSON response from LLM.
            original_text: Original text (fallback if parsing fails).

        Returns:
            Parsed and validated response dict.

        Raises:
            PolishingParseError: If response cannot be parsed.
        """
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning(
                "llm_polish_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            # Return original text on parse failure
            return {
                "sanitized_text": original_text,
                "changes_made": [],
                "confidence": 0.0,
            }

        # Validate response schema
        errors = validate_policing_response(parsed)
        if errors:
            logger.warning(
                "llm_polish_validation_failed",
                errors=errors,
            )
            # Continue with partial response for graceful degradation

        # Ensure sanitized_text is present
        if "sanitized_text" not in parsed or not parsed["sanitized_text"]:
            parsed["sanitized_text"] = original_text

        # Ensure changes_made is a list
        if "changes_made" not in parsed or not isinstance(parsed["changes_made"], list):
            parsed["changes_made"] = []

        return parsed

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost of LLM call.

        Story 8-3: Task 5.5 - Cost tracking.

        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Cost in USD.
        """
        settings = get_settings()

        # Get pricing from settings if available
        if hasattr(settings, "safety_llm_input_cost_per_1k"):
            input_cost_per_1k = settings.safety_llm_input_cost_per_1k
            if not isinstance(input_cost_per_1k, (int, float)):
                input_cost_per_1k = DEFAULT_INPUT_COST_PER_1K
        else:
            input_cost_per_1k = DEFAULT_INPUT_COST_PER_1K

        if hasattr(settings, "safety_llm_output_cost_per_1k"):
            output_cost_per_1k = settings.safety_llm_output_cost_per_1k
            if not isinstance(output_cost_per_1k, (int, float)):
                output_cost_per_1k = DEFAULT_OUTPUT_COST_PER_1K
        else:
            output_cost_per_1k = DEFAULT_OUTPUT_COST_PER_1K

        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        return input_cost + output_cost


# =============================================================================
# Story 8-3: Singleton Factory (Task 6.5)
# =============================================================================

# Singleton instance (thread-safe)
_language_police: LanguagePolice | None = None
_police_lock = threading.Lock()


def get_language_police() -> LanguagePolice:
    """Get singleton language police instance.

    Story 8-3: Task 6.5 - Factory function with thread-safe initialization.

    Returns:
        LanguagePolice singleton instance.
    """
    global _language_police  # noqa: PLW0603

    if _language_police is None:
        with _police_lock:
            # Double-check locking pattern
            if _language_police is None:
                _language_police = LanguagePolice()

    return _language_police


def reset_language_police() -> None:
    """Reset singleton for testing.

    Story 8-3: Reset function for test isolation.

    Note:
        This creates a fresh instance on next get_language_police() call.
    """
    global _language_police  # noqa: PLW0603

    with _police_lock:
        _language_police = None

    logger.debug("language_police_reset")
