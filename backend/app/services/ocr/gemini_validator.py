"""Gemini-based OCR validation service.

Uses Gemini 3 Flash for validating and correcting low-confidence OCR results
with batch processing for efficiency.
"""

import asyncio
import json
import time
from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.models.ocr_validation import (
    CorrectionType,
    LowConfidenceWord,
    ValidationResult,
)

logger = structlog.get_logger(__name__)


class GeminiValidatorError(Exception):
    """Base exception for Gemini validator operations."""

    def __init__(
        self,
        message: str,
        code: str = "GEMINI_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class GeminiConfigurationError(GeminiValidatorError):
    """Raised when Gemini is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="GEMINI_NOT_CONFIGURED", is_retryable=False)


class GeminiOCRValidator:
    """Service for validating OCR results using Gemini 3 Flash.

    Uses batch processing to efficiently validate multiple words
    per API request (up to 20 words per batch).
    """

    # Validation prompt template
    VALIDATION_PROMPT = """You are an OCR validation assistant for Indian legal documents.
Review these low-confidence OCR results and provide corrections.

Document context: Legal document (petition, appeal, affidavit, or annexure)
Language context: English with possible Hindi/Gujarati

Words to validate:
{words_json}

For each word, respond with a JSON array containing objects with these fields:
- index: The word index from the input
- original: The original OCR text
- corrected: Your corrected text (same as original if no correction needed)
- confidence: Your confidence in the correction (0.0 to 1.0)
- reasoning: Brief explanation if corrected, or "No correction needed"

Common OCR errors to look for:
- O/0 confusion (letter O vs zero)
- l/1/I confusion (lowercase L vs one vs uppercase I)
- S/5 confusion in numbers
- B/8 confusion in numbers
- Date format errors (DD/MM/YYYY)
- Indian currency format (Rs. X,XX,XXX)
- Legal section references (Section 123)

IMPORTANT:
- Only correct if you're confident the OCR made an error
- If unsure, return the original text with lower confidence
- Return ONLY valid JSON array, no other text

Example response:
[
  {{"index": 0, "original": "Rs. 1O,OOO", "corrected": "Rs. 10,000", "confidence": 0.95, "reasoning": "O confused with 0 in currency amount"}},
  {{"index": 1, "original": "Section", "corrected": "Section", "confidence": 0.9, "reasoning": "No correction needed"}}
]
"""

    def __init__(self) -> None:
        """Initialize Gemini validator."""
        self._model = None
        self._genai = None
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self.batch_size = settings.ocr_validation_batch_size

    @property
    def model(self):
        """Get or create Gemini model instance.

        Returns:
            Gemini GenerativeModel instance.

        Raises:
            GeminiConfigurationError: If API key is not configured.
        """
        if self._model is None:
            if not self.api_key:
                raise GeminiConfigurationError(
                    "Gemini API key not configured. Set GEMINI_API_KEY environment variable."
                )

            try:
                import google.generativeai as genai

                self._genai = genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(self.model_name)
                logger.info(
                    "gemini_model_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("gemini_init_failed", error=str(e))
                raise GeminiConfigurationError(
                    f"Failed to initialize Gemini: {e}"
                ) from e

        return self._model

    def validate_batch_sync(
        self,
        words: list[LowConfidenceWord],
        document_type: str | None = None,
    ) -> list[ValidationResult]:
        """Synchronously validate a batch of words using Gemini.

        This is a synchronous wrapper for use in Celery tasks.

        Args:
            words: List of words to validate (max batch_size).
            document_type: Optional document type hint.

        Returns:
            List of ValidationResult for each word.

        Raises:
            GeminiValidatorError: If validation fails.
        """
        if not words:
            return []

        if len(words) > self.batch_size:
            logger.warning(
                "gemini_batch_truncated",
                original_size=len(words),
                max_size=self.batch_size,
            )
            words = words[: self.batch_size]

        start_time = time.time()

        try:
            # Build prompt
            words_data = [
                {
                    "index": i,
                    "text": word.text,
                    "confidence": word.confidence,
                    "context_before": word.context_before,
                    "context_after": word.context_after,
                    "page": word.page,
                }
                for i, word in enumerate(words)
            ]

            prompt = self.VALIDATION_PROMPT.format(
                words_json=json.dumps(words_data, indent=2)
            )

            # Call Gemini synchronously
            response = self.model.generate_content(prompt)

            # Parse response
            results = self._parse_response(response.text, words)

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "gemini_validation_complete",
                word_count=len(words),
                results_count=len(results),
                processing_time_ms=processing_time,
            )

            return results

        except GeminiConfigurationError:
            raise
        except Exception as e:
            logger.error(
                "gemini_validation_failed",
                error=str(e),
                word_count=len(words),
            )
            raise GeminiValidatorError(
                f"Gemini validation failed: {e}",
                is_retryable=True,
            ) from e

    async def validate_batch_async(
        self,
        words: list[LowConfidenceWord],
        document_type: str | None = None,
    ) -> list[ValidationResult]:
        """Asynchronously validate a batch of words using Gemini.

        Args:
            words: List of words to validate (max batch_size).
            document_type: Optional document type hint.

        Returns:
            List of ValidationResult for each word.

        Raises:
            GeminiValidatorError: If validation fails.
        """
        if not words:
            return []

        if len(words) > self.batch_size:
            logger.warning(
                "gemini_batch_truncated",
                original_size=len(words),
                max_size=self.batch_size,
            )
            words = words[: self.batch_size]

        start_time = time.time()

        try:
            # Build prompt
            words_data = [
                {
                    "index": i,
                    "text": word.text,
                    "confidence": word.confidence,
                    "context_before": word.context_before,
                    "context_after": word.context_after,
                    "page": word.page,
                }
                for i, word in enumerate(words)
            ]

            prompt = self.VALIDATION_PROMPT.format(
                words_json=json.dumps(words_data, indent=2)
            )

            # Call Gemini asynchronously
            response = await self.model.generate_content_async(prompt)

            # Parse response
            results = self._parse_response(response.text, words)

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "gemini_validation_async_complete",
                word_count=len(words),
                results_count=len(results),
                processing_time_ms=processing_time,
            )

            return results

        except GeminiConfigurationError:
            raise
        except Exception as e:
            logger.error(
                "gemini_validation_async_failed",
                error=str(e),
                word_count=len(words),
            )
            raise GeminiValidatorError(
                f"Gemini validation failed: {e}",
                is_retryable=True,
            ) from e

    def _parse_response(
        self,
        response_text: str,
        original_words: list[LowConfidenceWord],
    ) -> list[ValidationResult]:
        """Parse Gemini response into ValidationResults.

        Args:
            response_text: Raw response from Gemini.
            original_words: Original words that were validated.

        Returns:
            List of ValidationResult.
        """
        results: list[ValidationResult] = []

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = response_text.strip()
            if json_text.startswith("```"):
                # Remove markdown code block
                lines = json_text.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block or (not line.startswith("```") and in_block is False):
                        json_lines.append(line)
                json_text = "\n".join(json_lines)

            # Parse JSON
            parsed = json.loads(json_text)

            if not isinstance(parsed, list):
                logger.warning(
                    "gemini_response_not_list",
                    response_type=type(parsed).__name__,
                )
                return self._fallback_results(original_words)

            # Map results by index
            result_map: dict[int, dict] = {item["index"]: item for item in parsed}

            for i, word in enumerate(original_words):
                if i in result_map:
                    item = result_map[i]
                    corrected = item.get("corrected", word.text)
                    confidence = item.get("confidence", word.confidence)
                    reasoning = item.get("reasoning")

                    was_corrected = corrected != word.text

                    results.append(
                        ValidationResult(
                            bbox_id=word.bbox_id,
                            original=word.text,
                            corrected=corrected,
                            old_confidence=word.confidence,
                            new_confidence=confidence,
                            correction_type=CorrectionType.GEMINI if was_corrected else None,
                            reasoning=reasoning if was_corrected else None,
                            was_corrected=was_corrected,
                        )
                    )
                else:
                    # Word not in response - return unchanged
                    results.append(
                        ValidationResult(
                            bbox_id=word.bbox_id,
                            original=word.text,
                            corrected=word.text,
                            old_confidence=word.confidence,
                            new_confidence=word.confidence,
                            correction_type=None,
                            reasoning=None,
                            was_corrected=False,
                        )
                    )

            return results

        except json.JSONDecodeError as e:
            logger.warning(
                "gemini_response_parse_failed",
                error=str(e),
                response_preview=response_text[:200],
            )
            return self._fallback_results(original_words)
        except Exception as e:
            logger.warning(
                "gemini_response_processing_failed",
                error=str(e),
            )
            return self._fallback_results(original_words)

    def _fallback_results(
        self,
        words: list[LowConfidenceWord],
    ) -> list[ValidationResult]:
        """Generate fallback results when parsing fails.

        Returns unchanged results for all words.

        Args:
            words: Original words.

        Returns:
            List of unchanged ValidationResult.
        """
        return [
            ValidationResult(
                bbox_id=word.bbox_id,
                original=word.text,
                corrected=word.text,
                old_confidence=word.confidence,
                new_confidence=word.confidence,
                correction_type=None,
                reasoning=None,
                was_corrected=False,
            )
            for word in words
        ]


async def validate_all_words(
    words: list[LowConfidenceWord],
    batch_size: int = 20,
) -> list[ValidationResult]:
    """Validate all words using batched Gemini requests.

    Processes words in parallel batches for efficiency.

    Args:
        words: List of words to validate.
        batch_size: Maximum words per batch.

    Returns:
        List of ValidationResult for all words.
    """
    if not words:
        return []

    validator = GeminiOCRValidator()

    # Split into batches
    batches = [words[i : i + batch_size] for i in range(0, len(words), batch_size)]

    logger.info(
        "gemini_batch_validation_starting",
        total_words=len(words),
        batch_count=len(batches),
    )

    # Process batches in parallel
    tasks = [validator.validate_batch_async(batch) for batch in batches]
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten results
    all_results: list[ValidationResult] = []
    for i, result in enumerate(batch_results):
        if isinstance(result, Exception):
            logger.error(
                "gemini_batch_failed",
                batch_index=i,
                error=str(result),
            )
            # Return fallback for failed batch
            all_results.extend(validator._fallback_results(batches[i]))
        else:
            all_results.extend(result)

    logger.info(
        "gemini_batch_validation_complete",
        total_words=len(words),
        results_count=len(all_results),
    )

    return all_results


@lru_cache(maxsize=1)
def get_gemini_validator() -> GeminiOCRValidator:
    """Get singleton Gemini validator instance.

    Returns:
        GeminiOCRValidator instance.
    """
    return GeminiOCRValidator()
