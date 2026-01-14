"""Gemini-based Event Classification Service.

Uses Gemini 3 Flash for classifying extracted dates into event types
(filing, notice, hearing, order, transaction, document, deadline).

CRITICAL: Uses Gemini for event classification per LLM routing rules -
this is an ingestion task, NOT user-facing reasoning.

Story 4-2: Event Classification
"""

import asyncio
import json
import time
from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.models.timeline import (
    EventClassificationResult,
    EventType,
    SecondaryTypeScore,
)
from app.engines.timeline.classification_prompts import (
    EVENT_CLASSIFICATION_SYSTEM_PROMPT,
    EVENT_CLASSIFICATION_USER_PROMPT,
    EVENT_CLASSIFICATION_BATCH_PROMPT,
)

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0
MAX_BATCH_SIZE = 20  # Max events per batch to stay within token limits
CONFIDENCE_THRESHOLD = 0.7  # Below this, classify as unclassified


# =============================================================================
# Exceptions
# =============================================================================


class EventClassifierError(Exception):
    """Base exception for event classifier operations."""

    def __init__(
        self,
        message: str,
        code: str = "EVENT_CLASSIFIER_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class ClassifierConfigurationError(EventClassifierError):
    """Raised when Gemini is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="CLASSIFIER_NOT_CONFIGURED", is_retryable=False)


# =============================================================================
# Service Implementation
# =============================================================================


class EventClassifier:
    """Service for classifying events using Gemini 3 Flash.

    Classifies raw_date events into specific event types (filing, notice,
    hearing, order, transaction, document, deadline) based on context.

    Example:
        >>> classifier = EventClassifier()
        >>> result = await classifier.classify_event(
        ...     event_id="event-123",
        ...     context_text="The petitioner filed this writ petition on 15/01/2024",
        ...     date_text="15/01/2024",
        ... )
        >>> result.event_type
        EventType.FILING
    """

    def __init__(self) -> None:
        """Initialize event classifier."""
        self._model = None
        self._genai = None
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model

    @property
    def model(self):
        """Get or create Gemini model instance.

        Returns:
            Gemini GenerativeModel instance.

        Raises:
            ClassifierConfigurationError: If API key is not configured.
        """
        if self._model is None:
            if not self.api_key:
                raise ClassifierConfigurationError(
                    "Gemini API key not configured. Set GEMINI_API_KEY environment variable."
                )

            try:
                import google.generativeai as genai

                self._genai = genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=EVENT_CLASSIFICATION_SYSTEM_PROMPT,
                )
                logger.info(
                    "event_classifier_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("event_classifier_init_failed", error=str(e))
                raise ClassifierConfigurationError(
                    f"Failed to initialize Gemini for event classification: {e}"
                ) from e

        return self._model

    async def classify_event(
        self,
        event_id: str,
        context_text: str,
        date_text: str,
    ) -> EventClassificationResult:
        """Classify a single event into an event type.

        Args:
            event_id: Event UUID to classify.
            context_text: Context text surrounding the date.
            date_text: Original date text from document.

        Returns:
            EventClassificationResult with classification details.

        Raises:
            EventClassifierError: If classification fails after retries.
        """
        start_time = time.time()

        # Handle empty context
        if not context_text or not context_text.strip():
            logger.debug(
                "event_classification_empty_context",
                event_id=event_id,
            )
            return EventClassificationResult(
                event_id=event_id,
                event_type=EventType.UNCLASSIFIED,
                classification_confidence=0.0,
                secondary_types=[],
                keywords_matched=[],
                classification_reasoning="No context available for classification",
            )

        prompt = EVENT_CLASSIFICATION_USER_PROMPT.format(
            date_text=date_text,
            context=context_text,
        )

        # Retry with exponential backoff
        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                # Call Gemini asynchronously
                response = await self.model.generate_content_async(prompt)

                # Parse response
                result = self._parse_single_response(
                    response.text,
                    event_id=event_id,
                )

                processing_time = int((time.time() - start_time) * 1000)
                logger.debug(
                    "event_classification_complete",
                    event_id=event_id,
                    event_type=result.event_type.value,
                    confidence=result.classification_confidence,
                    processing_time_ms=processing_time,
                    attempts=attempt + 1,
                )

                return result

            except ClassifierConfigurationError:
                raise
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit errors
                is_rate_limit = (
                    "429" in error_str
                    or "rate" in error_str
                    or "quota" in error_str
                    or "resource exhausted" in error_str
                )

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "event_classification_rate_limited",
                        event_id=event_id,
                        attempt=attempt + 1,
                        max_attempts=MAX_RETRIES,
                        retry_delay=retry_delay,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_rate_limit:
                    break

        logger.error(
            "event_classification_failed",
            error=str(last_error),
            event_id=event_id,
            attempts=MAX_RETRIES,
        )

        # Return unclassified on failure (graceful degradation)
        return EventClassificationResult(
            event_id=event_id,
            event_type=EventType.UNCLASSIFIED,
            classification_confidence=0.0,
            secondary_types=[],
            keywords_matched=[],
            classification_reasoning=f"Classification failed: {last_error}",
        )

    async def classify_events_batch(
        self,
        events: list[dict],
    ) -> list[EventClassificationResult]:
        """Classify multiple events in a single LLM call.

        More efficient than individual classification for bulk processing.
        Processes up to MAX_BATCH_SIZE events per call.

        Args:
            events: List of event dicts with keys:
                - event_id: Event UUID
                - date_text: Original date text
                - context: Context text surrounding the date

        Returns:
            List of EventClassificationResult in same order as input.

        Raises:
            EventClassifierError: If classification fails.
        """
        if not events:
            return []

        # Process in batches if too many events
        if len(events) > MAX_BATCH_SIZE:
            results = []
            for i in range(0, len(events), MAX_BATCH_SIZE):
                batch = events[i : i + MAX_BATCH_SIZE]
                batch_results = await self._classify_batch(batch)
                results.extend(batch_results)
            return results

        return await self._classify_batch(events)

    async def _classify_batch(
        self,
        events: list[dict],
    ) -> list[EventClassificationResult]:
        """Classify a batch of events (max MAX_BATCH_SIZE).

        Args:
            events: List of event dicts.

        Returns:
            List of EventClassificationResult.
        """
        start_time = time.time()

        # Prepare events for prompt
        events_for_prompt = [
            {
                "event_id": e.get("event_id", ""),
                "date_text": e.get("date_text", ""),
                "context": e.get("context", "")[:2000],  # Limit context per event
            }
            for e in events
        ]

        events_json = json.dumps(events_for_prompt, indent=2)
        prompt = EVENT_CLASSIFICATION_BATCH_PROMPT.format(events_json=events_json)

        # Retry with exponential backoff
        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                # Call Gemini
                response = await self.model.generate_content_async(prompt)

                # Parse response
                results = self._parse_batch_response(response.text, events)

                processing_time = int((time.time() - start_time) * 1000)
                logger.info(
                    "event_classification_batch_complete",
                    event_count=len(events),
                    classified_count=len(results),
                    processing_time_ms=processing_time,
                    attempts=attempt + 1,
                )

                return results

            except ClassifierConfigurationError:
                raise
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                is_rate_limit = (
                    "429" in error_str
                    or "rate" in error_str
                    or "quota" in error_str
                    or "resource exhausted" in error_str
                )

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "event_classification_batch_rate_limited",
                        event_count=len(events),
                        attempt=attempt + 1,
                        retry_delay=retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_rate_limit:
                    break

        logger.error(
            "event_classification_batch_failed",
            error=str(last_error),
            event_count=len(events),
        )

        # Return unclassified for all events on failure
        return [
            EventClassificationResult(
                event_id=e.get("event_id", ""),
                event_type=EventType.UNCLASSIFIED,
                classification_confidence=0.0,
                secondary_types=[],
                keywords_matched=[],
                classification_reasoning=f"Batch classification failed: {last_error}",
            )
            for e in events
        ]

    def classify_event_sync(
        self,
        event_id: str,
        context_text: str,
        date_text: str,
    ) -> EventClassificationResult:
        """Synchronous wrapper for event classification.

        For use in Celery tasks or other synchronous contexts.

        Args:
            event_id: Event UUID to classify.
            context_text: Context text surrounding the date.
            date_text: Original date text.

        Returns:
            EventClassificationResult with classification details.
        """
        # Handle empty context
        if not context_text or not context_text.strip():
            return EventClassificationResult(
                event_id=event_id,
                event_type=EventType.UNCLASSIFIED,
                classification_confidence=0.0,
                secondary_types=[],
                keywords_matched=[],
                classification_reasoning="No context available for classification",
            )

        prompt = EVENT_CLASSIFICATION_USER_PROMPT.format(
            date_text=date_text,
            context=context_text,
        )

        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = self.model.generate_content(prompt)
                return self._parse_single_response(response.text, event_id)

            except ClassifierConfigurationError:
                raise
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                is_rate_limit = (
                    "429" in error_str
                    or "rate" in error_str
                    or "quota" in error_str
                    or "resource exhausted" in error_str
                )

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "event_classification_sync_rate_limited",
                        event_id=event_id,
                        attempt=attempt + 1,
                        retry_delay=retry_delay,
                    )
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_rate_limit:
                    break

        logger.error(
            "event_classification_sync_failed",
            error=str(last_error),
            event_id=event_id,
        )

        return EventClassificationResult(
            event_id=event_id,
            event_type=EventType.UNCLASSIFIED,
            classification_confidence=0.0,
            secondary_types=[],
            keywords_matched=[],
            classification_reasoning=f"Classification failed: {last_error}",
        )

    def classify_events_batch_sync(
        self,
        events: list[dict],
    ) -> list[EventClassificationResult]:
        """Synchronous batch classification for Celery tasks.

        Args:
            events: List of event dicts with event_id, date_text, context.

        Returns:
            List of EventClassificationResult.
        """
        if not events:
            return []

        # Process in batches if too many events
        if len(events) > MAX_BATCH_SIZE:
            results = []
            for i in range(0, len(events), MAX_BATCH_SIZE):
                batch = events[i : i + MAX_BATCH_SIZE]
                batch_results = self._classify_batch_sync(batch)
                results.extend(batch_results)
            return results

        return self._classify_batch_sync(events)

    def _classify_batch_sync(
        self,
        events: list[dict],
    ) -> list[EventClassificationResult]:
        """Synchronous batch classification."""
        events_for_prompt = [
            {
                "event_id": e.get("event_id", ""),
                "date_text": e.get("date_text", ""),
                "context": e.get("context", "")[:2000],
            }
            for e in events
        ]

        events_json = json.dumps(events_for_prompt, indent=2)
        prompt = EVENT_CLASSIFICATION_BATCH_PROMPT.format(events_json=events_json)

        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = self.model.generate_content(prompt)
                return self._parse_batch_response(response.text, events)

            except ClassifierConfigurationError:
                raise
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                is_rate_limit = (
                    "429" in error_str
                    or "rate" in error_str
                    or "quota" in error_str
                    or "resource exhausted" in error_str
                )

                if is_rate_limit and attempt < MAX_RETRIES - 1:
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_rate_limit:
                    break

        logger.error(
            "event_classification_batch_sync_failed",
            error=str(last_error),
            event_count=len(events),
        )

        return [
            EventClassificationResult(
                event_id=e.get("event_id", ""),
                event_type=EventType.UNCLASSIFIED,
                classification_confidence=0.0,
                secondary_types=[],
                keywords_matched=[],
                classification_reasoning=f"Batch classification failed: {last_error}",
            )
            for e in events
        ]

    # =========================================================================
    # Response Parsing
    # =========================================================================

    def _parse_single_response(
        self,
        response_text: str,
        event_id: str,
    ) -> EventClassificationResult:
        """Parse Gemini response for single event classification.

        Args:
            response_text: Raw response from Gemini.
            event_id: Event UUID being classified.

        Returns:
            EventClassificationResult.
        """
        try:
            json_text = self._clean_json_response(response_text)
            parsed = json.loads(json_text)

            if not isinstance(parsed, dict):
                return self._unclassified_result(
                    event_id, "Response was not a valid object"
                )

            return self._dict_to_result(parsed, event_id)

        except json.JSONDecodeError as e:
            logger.warning(
                "event_classification_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            return self._unclassified_result(event_id, f"JSON parse error: {e}")

        except Exception as e:
            logger.warning(
                "event_classification_parse_error",
                error=str(e),
            )
            return self._unclassified_result(event_id, f"Parse error: {e}")

    def _parse_batch_response(
        self,
        response_text: str,
        events: list[dict],
    ) -> list[EventClassificationResult]:
        """Parse Gemini response for batch classification.

        Args:
            response_text: Raw response from Gemini.
            events: Original event list for fallback.

        Returns:
            List of EventClassificationResult.
        """
        try:
            json_text = self._clean_json_response(response_text)
            parsed = json.loads(json_text)

            if not isinstance(parsed, list):
                logger.warning(
                    "event_classification_batch_not_array",
                    response_type=type(parsed).__name__,
                )
                return [
                    self._unclassified_result(e.get("event_id", ""), "Invalid response")
                    for e in events
                ]

            # Build results, using event IDs from parsed or original events
            results = []
            for i, event_data in enumerate(parsed):
                if i < len(events):
                    event_id = event_data.get("event_id") or events[i].get(
                        "event_id", ""
                    )
                else:
                    event_id = event_data.get("event_id", "")

                result = self._dict_to_result(event_data, event_id)
                results.append(result)

            # If we got fewer results than events, add unclassified for remainder
            # and log a warning about the count mismatch
            if len(results) < len(events):
                missing_count = len(events) - len(results)
                logger.warning(
                    "event_classification_batch_result_count_mismatch",
                    expected=len(events),
                    received=len(results),
                    missing=missing_count,
                    msg="LLM returned fewer results than events sent - padding with unclassified",
                )

            for i in range(len(results), len(events)):
                results.append(
                    self._unclassified_result(
                        events[i].get("event_id", ""),
                        "No classification returned for this event",
                    )
                )

            return results

        except json.JSONDecodeError as e:
            logger.warning(
                "event_classification_batch_json_error",
                error=str(e),
            )
            return [
                self._unclassified_result(
                    e_data.get("event_id", ""), f"JSON parse error: {e}"
                )
                for e_data in events
            ]

        except Exception as e:
            logger.warning(
                "event_classification_batch_parse_error",
                error=str(e),
            )
            return [
                self._unclassified_result(e_data.get("event_id", ""), f"Parse error: {e}")
                for e_data in events
            ]

    def _dict_to_result(
        self,
        data: dict,
        event_id: str,
    ) -> EventClassificationResult:
        """Convert parsed dict to EventClassificationResult.

        Args:
            data: Parsed classification data.
            event_id: Event UUID.

        Returns:
            EventClassificationResult.
        """
        # Parse event type
        raw_type = data.get("event_type", "unclassified").lower()
        try:
            event_type = EventType(raw_type)
        except ValueError:
            event_type = EventType.UNCLASSIFIED

        # Parse confidence - handle None explicitly
        # Default to 1.0 to trust the LLM's event_type when confidence not provided
        raw_confidence = data.get("classification_confidence")
        confidence = float(raw_confidence) if raw_confidence is not None else 1.0

        # If confidence below threshold, force unclassified
        if confidence < CONFIDENCE_THRESHOLD and event_type != EventType.UNCLASSIFIED:
            event_type = EventType.UNCLASSIFIED

        # Parse secondary types - handle None values
        secondary_types = []
        raw_secondary = data.get("secondary_types")
        if raw_secondary and isinstance(raw_secondary, list):
            for st in raw_secondary:
                if isinstance(st, dict):
                    try:
                        st_type = EventType(st.get("type", "").lower())
                        st_raw_conf = st.get("confidence")
                        st_conf = float(st_raw_conf) if st_raw_conf is not None else 0.5
                        secondary_types.append(SecondaryTypeScore(type=st_type, confidence=st_conf))
                    except (ValueError, TypeError):
                        continue

        # Parse keywords
        keywords = data.get("keywords_matched", [])
        if not isinstance(keywords, list):
            keywords = []
        keywords = [str(k) for k in keywords if k]

        return EventClassificationResult(
            event_id=event_id,
            event_type=event_type,
            classification_confidence=confidence,
            secondary_types=secondary_types,
            keywords_matched=keywords,
            classification_reasoning=data.get("classification_reasoning"),
        )

    def _unclassified_result(
        self,
        event_id: str,
        reason: str,
    ) -> EventClassificationResult:
        """Create an unclassified result with reason.

        Args:
            event_id: Event UUID.
            reason: Reason for being unclassified.

        Returns:
            EventClassificationResult with unclassified type.
        """
        return EventClassificationResult(
            event_id=event_id,
            event_type=EventType.UNCLASSIFIED,
            classification_confidence=0.0,
            secondary_types=[],
            keywords_matched=[],
            classification_reasoning=reason,
        )

    def _clean_json_response(self, response_text: str) -> str:
        """Clean up response text for JSON parsing.

        Args:
            response_text: Raw response text.

        Returns:
            Cleaned JSON string.
        """
        json_text = response_text.strip()

        # Remove markdown code blocks if present
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            json_text = "\n".join(json_lines)

        return json_text


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_event_classifier() -> EventClassifier:
    """Get singleton event classifier instance.

    Returns:
        EventClassifier instance.
    """
    return EventClassifier()
