"""Gemini-based Date Extraction Service.

Story 13-2: Circuit breaker protection for Gemini calls

Uses Gemini 3 Flash for extracting dates with surrounding context
from legal document text for timeline construction.

CRITICAL: Uses Gemini for date extraction per LLM routing rules -
this is an ingestion task, NOT user-facing reasoning.

Fallback: Returns empty result when circuit is open - date extraction
is non-critical for document ingestion to continue.
"""

import json
import re
import time
from datetime import date
from functools import lru_cache

import structlog

from app.engines.base import ReasoningCaptureMixin
from app.models.reasoning_trace import EngineType
from app.core.bbox_filter import get_filtered_bbox_ids
from app.core.circuit_breaker import (
    CircuitOpenError,
    CircuitService,
    with_circuit_breaker,
)
from app.core.config import get_settings
from app.core.llm_rate_limiter import (
    LLMProvider as RateLimitProvider,
    get_distributed_rate_limiter,
    get_rate_limiter,
)
from app.core.gemini_client import GeminiClientError, get_gemini_client
from app.core.cost_tracking import (
    CostTracker,
    LLMProvider,
    estimate_tokens,
    persist_cost,
    persist_cost_sync,
)
from app.engines.timeline.prompts import (
    DATE_EXTRACTION_BATCH_PROMPT,
    DATE_EXTRACTION_SYSTEM_PROMPT,
    DATE_EXTRACTION_USER_PROMPT,
)
from app.models.timeline import (
    DateExtractionResult,
    ExtractedDate,
)

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

MAX_TEXT_LENGTH = 5000  # Max characters per extraction request (reduced from 30000 to avoid Gemini output truncation)
CHUNK_OVERLAP = 500  # Characters to overlap between chunks for boundary dates

# Date validation bounds - reject dates outside reasonable legal document range
MIN_VALID_YEAR = 1800  # No legal documents before 1800
MAX_VALID_YEAR = 2100  # No future dates beyond 2100


# =============================================================================
# Exceptions
# =============================================================================


class DateExtractorError(Exception):
    """Base exception for date extractor operations."""

    def __init__(
        self,
        message: str,
        code: str = "DATE_EXTRACTOR_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class DateConfigurationError(DateExtractorError):
    """Raised when Gemini is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="DATE_NOT_CONFIGURED", is_retryable=False)


# =============================================================================
# Service Implementation
# =============================================================================


class DateExtractor(ReasoningCaptureMixin):
    """Service for extracting dates from legal documents using Gemini 3 Flash.

    Extracts dates in various formats with surrounding context for timeline
    construction. Handles Indian date formats (DD/MM/YYYY priority) and
    ambiguity detection.

    Example:
        >>> extractor = DateExtractor()
        >>> result = await extractor.extract_dates_from_text(
        ...     text="The hearing is scheduled for 15/01/2024.",
        ...     document_id="doc-123",
        ...     matter_id="matter-456",
        ... )
        >>> len(result.dates)
        1
        >>> result.dates[0].extracted_date
        date(2024, 1, 15)
    """

    def __init__(self) -> None:
        """Initialize date extractor."""
        self._client = None
        settings = get_settings()
        self.model_name = settings.gemini_model

    @property
    def client(self):
        """Get or create Gemini client instance.

        Returns:
            google.genai.Client instance.

        Raises:
            DateConfigurationError: If API key is not configured.
        """
        if self._client is None:
            try:
                self._client = get_gemini_client()
                logger.info(
                    "date_extractor_initialized",
                    model=self.model_name,
                )
            except GeminiClientError as e:
                logger.error("date_extractor_init_failed", error=str(e))
                raise DateConfigurationError(
                    f"Failed to initialize Gemini for date extraction: {e}"
                ) from e

        return self._client

    async def extract_dates_from_text(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        page_number: int | None = None,
    ) -> DateExtractionResult:
        """Extract dates and context from text.

        Args:
            text: Document text to extract dates from.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.
            page_number: Optional page number.

        Returns:
            DateExtractionResult containing extracted dates with context.

        Raises:
            DateExtractorError: If extraction fails after retries.
        """
        start_time = time.time()

        # Handle empty text
        if not text or not text.strip():
            logger.debug(
                "date_extraction_empty_text",
                document_id=document_id,
                matter_id=matter_id,
            )
            return DateExtractionResult(
                dates=[],
                document_id=document_id,
                matter_id=matter_id,
                total_dates_found=0,
                processing_time_ms=0,
            )

        # Process in chunks if text is too long
        if len(text) > MAX_TEXT_LENGTH:
            result = await self._extract_from_chunks(
                text=text,
                document_id=document_id,
                matter_id=matter_id,
                page_number=page_number,
            )
            processing_time = int((time.time() - start_time) * 1000)
            result.processing_time_ms = processing_time
            return result

        # Single extraction for shorter text
        result = await self._extract_single(
            text=text,
            document_id=document_id,
            matter_id=matter_id,
            page_number=page_number,
        )

        processing_time = int((time.time() - start_time) * 1000)
        result.processing_time_ms = processing_time

        logger.info(
            "date_extraction_complete",
            document_id=document_id,
            matter_id=matter_id,
            date_count=len(result.dates),
            processing_time_ms=processing_time,
        )

        return result

    async def _extract_single(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        page_number: int | None = None,
        bbox_ids: list[str] | None = None,
    ) -> DateExtractionResult:
        """Extract dates from a single text chunk with circuit breaker.

        Args:
            text: Text chunk to process.
            document_id: Source document UUID.
            matter_id: Matter UUID.
            page_number: Optional page number.
            bbox_ids: Optional bounding box UUIDs from source chunk.

        Returns:
            DateExtractionResult with extracted dates.
            Returns empty result if circuit is open (graceful degradation).
        """
        prompt = DATE_EXTRACTION_USER_PROMPT.format(text=text)

        # Initialize cost tracker for Gemini Flash
        cost_tracker = CostTracker(
            provider=LLMProvider.GEMINI_FLASH,
            operation="date_extraction",
            matter_id=matter_id,
            document_id=document_id,
        )

        try:
            # Call Gemini with circuit breaker protection
            response_text = await self._call_gemini_extract(prompt)

            # Track costs (Gemini doesn't expose token counts, so estimate)
            input_tokens = estimate_tokens(prompt)
            output_tokens = estimate_tokens(response_text) if response_text else 0
            cost_tracker.add_tokens(input_tokens=input_tokens, output_tokens=output_tokens)
            cost_tracker.log_cost()
            await persist_cost(cost_tracker)

            # Parse response
            result = self._parse_response(
                response_text,
                document_id=document_id,
                matter_id=matter_id,
                page_number=page_number,
                bbox_ids=bbox_ids,
            )

            # Store reasoning trace for legal defensibility
            await self.store_reasoning(
                matter_id=matter_id,
                engine_type=EngineType.TIMELINE,
                model_used=self.model_name,
                reasoning_text=response_text or "",
                input_summary=f"Date extraction from document {document_id}, text length {len(text)}",
                tokens_used=(input_tokens + output_tokens),
                cost_usd=cost_tracker.total_cost_usd,
            )

            logger.debug(
                "date_extraction_chunk_complete",
                document_id=document_id,
                date_count=len(result.dates),
            )

            return result

        except CircuitOpenError as e:
            # Graceful degradation: return empty result
            logger.warning(
                "date_extraction_circuit_open_fallback",
                document_id=document_id,
                circuit_name=e.circuit_name,
                cooldown_remaining=e.cooldown_remaining,
            )
            return self._empty_result(document_id, matter_id)

        except DateConfigurationError:
            raise

        except Exception as e:
            logger.error(
                "date_extraction_failed",
                error=str(e),
                error_type=type(e).__name__,
                document_id=document_id,
                matter_id=matter_id,
            )
            # Graceful degradation: return empty result
            return self._empty_result(document_id, matter_id)

    @with_circuit_breaker(CircuitService.GEMINI_FLASH)
    async def _call_gemini_extract(self, prompt: str) -> str:
        """Call Gemini API with circuit breaker protection.

        Args:
            prompt: Extraction prompt.

        Returns:
            Response text from Gemini.
        """
        from google.genai import types

        gemini_limiter = get_rate_limiter(RateLimitProvider.GEMINI)
        async with gemini_limiter:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=DATE_EXTRACTION_SYSTEM_PROMPT,
                    max_output_tokens=8192,
                    temperature=0.1,
                ),
            )
        return response.text

    async def _extract_from_chunks(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        page_number: int | None = None,
    ) -> DateExtractionResult:
        """Extract dates from text by processing in chunks.

        Handles large documents by splitting into overlapping chunks
        and deduplicating results.

        Args:
            text: Full text to process.
            document_id: Source document UUID.
            matter_id: Matter UUID.
            page_number: Optional page number.

        Returns:
            Combined DateExtractionResult from all chunks.
        """
        chunks = self._split_into_chunks(text)
        logger.info(
            "date_extraction_chunking",
            document_id=document_id,
            total_length=len(text),
            chunk_count=len(chunks),
        )

        all_dates: list[ExtractedDate] = []

        for i, chunk in enumerate(chunks):
            logger.debug(
                "date_extraction_processing_chunk",
                document_id=document_id,
                chunk_index=i + 1,
                chunk_count=len(chunks),
            )

            chunk_result = await self._extract_single(
                text=chunk,
                document_id=document_id,
                matter_id=matter_id,
                page_number=page_number,
            )

            all_dates.extend(chunk_result.dates)

        # Deduplicate dates (same date_text and similar context)
        unique_dates = self._deduplicate_dates(all_dates)

        return DateExtractionResult(
            dates=unique_dates,
            document_id=document_id,
            matter_id=matter_id,
            total_dates_found=len(unique_dates),
            processing_time_ms=0,  # Will be set by caller
        )

    def _split_into_chunks(self, text: str) -> list[str]:
        """Split text into overlapping chunks for processing.

        Uses sentence-boundary-aware splitting to avoid cutting dates
        from their context. Prioritizes sentence endings (.?!) and
        falls back to other boundaries (newlines, semicolons).

        Args:
            text: Full text to split.

        Returns:
            List of text chunks with overlap.
        """
        chunks = []
        chunk_size = MAX_TEXT_LENGTH - CHUNK_OVERLAP

        # Pre-compute sentence boundaries for smarter splitting
        # Match sentence endings: period/question/exclamation followed by space or newline
        sentence_boundaries = [
            m.end() for m in re.finditer(r'[.!?]\s+', text)
        ]
        # Also consider paragraph breaks as boundaries
        paragraph_boundaries = [
            m.end() for m in re.finditer(r'\n\s*\n', text)
        ]
        # Combine and sort all boundaries
        all_boundaries = sorted(set(sentence_boundaries + paragraph_boundaries))

        start = 0
        while start < len(text):
            end = min(start + MAX_TEXT_LENGTH, len(text))

            # Try to break at sentence boundary
            if end < len(text):
                # Find the best boundary within the acceptable range
                # Look for boundaries in the last 1000 chars (increased from 500)
                search_start = max(end - 1000, start + chunk_size // 2)

                # Find the latest boundary before our end point
                best_boundary = None
                for boundary in all_boundaries:
                    if search_start <= boundary <= end:
                        best_boundary = boundary

                if best_boundary:
                    end = best_boundary
                else:
                    # Fallback: try simple sentence ending patterns
                    for pattern in ['. ', '.\n', '? ', '!\n', '; ', ';\n']:
                        last_match = text.rfind(pattern, search_start, end)
                        if last_match > search_start:
                            end = last_match + len(pattern)
                            break

            chunks.append(text[start:end])

            # Next chunk starts with overlap to catch boundary dates
            # Increase overlap at sentence boundaries to preserve context
            overlap = CHUNK_OVERLAP
            if end < len(text):
                # Find the start of the sentence containing the boundary
                # Look back for sentence start to preserve context
                overlap_start = max(end - overlap, start)
                for pattern in ['. ', '.\n', '? ', '!\n']:
                    sentence_start = text.rfind(pattern, overlap_start, end)
                    if sentence_start > overlap_start:
                        overlap = end - sentence_start - 2
                        break

            start = end - min(overlap, CHUNK_OVERLAP) if end < len(text) else end

        return chunks

    def _deduplicate_dates(self, dates: list[ExtractedDate]) -> list[ExtractedDate]:
        """Remove duplicate date extractions.

        Uses date_text and extracted_date for deduplication.

        Args:
            dates: List of extracted dates (may contain duplicates).

        Returns:
            Deduplicated list of dates.
        """
        seen = set()
        unique = []

        for d in dates:
            # Create a key from the date text and extracted date
            key = (d.date_text.strip().lower(), str(d.extracted_date))

            if key not in seen:
                seen.add(key)
                unique.append(d)

        return unique

    def extract_dates_sync(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        page_number: int | None = None,
        bbox_ids: list[str] | None = None,
    ) -> DateExtractionResult:
        """Synchronous wrapper for date extraction.

        For use in Celery tasks or other synchronous contexts.

        Args:
            text: Document text to extract dates from.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.
            page_number: Optional page number.
            bbox_ids: Optional bounding box UUIDs from source chunk.

        Returns:
            DateExtractionResult containing extracted dates.
        """
        start_time = time.time()

        # Handle empty text
        if not text or not text.strip():
            return DateExtractionResult(
                dates=[],
                document_id=document_id,
                matter_id=matter_id,
                total_dates_found=0,
                processing_time_ms=0,
            )

        # Process in chunks if needed
        if len(text) > MAX_TEXT_LENGTH:
            chunks = self._split_into_chunks(text)
            all_dates: list[ExtractedDate] = []

            for chunk in chunks:
                chunk_result = self._extract_single_sync(
                    text=chunk,
                    document_id=document_id,
                    matter_id=matter_id,
                    page_number=page_number,
                    bbox_ids=bbox_ids,
                )
                all_dates.extend(chunk_result.dates)

            unique_dates = self._deduplicate_dates(all_dates)
            processing_time = int((time.time() - start_time) * 1000)

            return DateExtractionResult(
                dates=unique_dates,
                document_id=document_id,
                matter_id=matter_id,
                total_dates_found=len(unique_dates),
                processing_time_ms=processing_time,
            )

        result = self._extract_single_sync(
            text=text,
            document_id=document_id,
            matter_id=matter_id,
            page_number=page_number,
            bbox_ids=bbox_ids,
        )

        result.processing_time_ms = int((time.time() - start_time) * 1000)
        return result

    def _extract_single_sync(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        page_number: int | None = None,
        bbox_ids: list[str] | None = None,
    ) -> DateExtractionResult:
        """Synchronous single chunk extraction.

        Note: Circuit breaker decorator is async-only, but we check
        circuit state manually for sync calls.
        """
        from app.core.circuit_breaker import get_circuit_registry

        prompt = DATE_EXTRACTION_USER_PROMPT.format(text=text)

        # Initialize cost tracker for Gemini Flash
        cost_tracker = CostTracker(
            provider=LLMProvider.GEMINI_FLASH,
            operation="date_extraction_sync",
            matter_id=matter_id,
            document_id=document_id,
        )

        # Check circuit state (manual check for sync methods)
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.GEMINI_FLASH)

        if breaker.is_open:
            logger.warning(
                "date_extraction_sync_circuit_open",
                document_id=document_id,
                cooldown_remaining=breaker.cooldown_remaining,
            )
            return self._empty_result(document_id, matter_id)

        try:
            from google.genai import types

            gemini_limiter = get_distributed_rate_limiter(RateLimitProvider.GEMINI)
            with gemini_limiter:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=DATE_EXTRACTION_SYSTEM_PROMPT,
                        max_output_tokens=8192,
                        temperature=0.1,
                    ),
                )

            # Track costs (Gemini doesn't expose token counts, so estimate)
            response_text = response.text if response.text else ""
            input_tokens = estimate_tokens(prompt)
            output_tokens = estimate_tokens(response_text)
            cost_tracker.add_tokens(input_tokens=input_tokens, output_tokens=output_tokens)
            cost_tracker.log_cost()
            persist_cost_sync(cost_tracker)

            result = self._parse_response(
                response_text,
                document_id=document_id,
                matter_id=matter_id,
                page_number=page_number,
                bbox_ids=bbox_ids,
            )

            # Store reasoning trace for legal defensibility
            self.store_reasoning_sync(
                matter_id=matter_id,
                engine_type=EngineType.TIMELINE,
                model_used=self.model_name,
                reasoning_text=response_text,
                input_summary=f"Date extraction (sync) from document {document_id}, text length {len(text)}",
                tokens_used=(input_tokens + output_tokens),
                cost_usd=cost_tracker.total_cost_usd,
            )

            # Record success
            breaker.record_success()

            return result

        except DateConfigurationError:
            raise

        except Exception as e:
            # Record failure for circuit breaker
            breaker.record_failure()

            logger.error(
                "date_extraction_sync_failed",
                error=str(e),
                error_type=type(e).__name__,
                document_id=document_id,
            )
            return self._empty_result(document_id, matter_id)

    def _parse_response(
        self,
        response_text: str,
        document_id: str,
        matter_id: str,
        page_number: int | None,
        bbox_ids: list[str] | None = None,
    ) -> DateExtractionResult:
        """Parse Gemini response into DateExtractionResult.

        Args:
            response_text: Raw response from Gemini.
            document_id: Source document UUID.
            matter_id: Matter UUID.
            page_number: Optional page number.
            bbox_ids: Optional bounding box UUIDs from source chunk.

        Returns:
            Parsed DateExtractionResult.
        """
        try:
            # Clean up response text
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

            # Parse JSON
            parsed = json.loads(json_text)

            if not isinstance(parsed, dict):
                logger.warning(
                    "date_response_not_dict",
                    response_type=type(parsed).__name__,
                )
                return self._empty_result(document_id, matter_id)

            # Parse dates
            dates: list[ExtractedDate] = []
            raw_dates = parsed.get("dates", [])

            for raw_date in raw_dates:
                try:
                    extracted = self._parse_single_date(
                        raw_date, page_number, bbox_ids, document_id, matter_id
                    )
                    if extracted:
                        dates.append(extracted)
                except Exception as e:
                    logger.debug(
                        "date_parse_error",
                        error=str(e),
                        raw_date=str(raw_date)[:100],
                    )
                    continue

            return DateExtractionResult(
                dates=dates,
                document_id=document_id,
                matter_id=matter_id,
                total_dates_found=len(dates),
                processing_time_ms=0,
            )

        except json.JSONDecodeError as e:
            # Attempt JSON repair for truncated Gemini responses
            repaired = self._try_repair_json(json_text)
            if repaired is not None:
                logger.info(
                    "date_response_json_repaired",
                    original_error=str(e),
                )
                dates_list: list[ExtractedDate] = []
                for raw_date in repaired.get("dates", []):
                    try:
                        extracted = self._parse_single_date(
                            raw_date, page_number, bbox_ids, document_id, matter_id
                        )
                        if extracted:
                            dates_list.append(extracted)
                    except Exception:
                        continue
                return DateExtractionResult(
                    dates=dates_list,
                    document_id=document_id,
                    matter_id=matter_id,
                    total_dates_found=len(dates_list),
                    processing_time_ms=0,
                )

            logger.warning(
                "date_response_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            return self._empty_result(document_id, matter_id)

        except Exception as e:
            logger.warning(
                "date_response_parse_error",
                error=str(e),
            )
            return self._empty_result(document_id, matter_id)

    @staticmethod
    def _try_repair_json(text: str) -> dict | None:
        """Attempt to repair truncated JSON from LLM responses.

        Handles common truncation patterns: missing closing brackets/braces,
        trailing commas, and incomplete string values.
        """
        import re

        if not text or not text.strip():
            return None

        repaired = text.strip()
        # Remove trailing incomplete key-value pairs (e.g., truncated mid-string)
        repaired = re.sub(r',\s*"[^"]*"?\s*:\s*"?[^"]*$', '', repaired)
        # Remove trailing comma
        repaired = re.sub(r',\s*$', '', repaired)

        # Close any open brackets/braces
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')

        # Close open strings — if odd number of unescaped quotes, add one
        # (simplified: just try parsing and if it fails, skip)

        repaired += ']' * max(0, open_brackets)
        repaired += '}' * max(0, open_braces)

        try:
            result = json.loads(repaired)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
        return None

    def _parse_single_date(
        self,
        raw_date: dict,
        page_number: int | None,
        bbox_ids: list[str] | None = None,
        document_id: str | None = None,
        matter_id: str | None = None,
    ) -> ExtractedDate | None:
        """Parse a single date entry from LLM response.

        Story 6.1: Added matter_id for citation page accuracy logging.

        Args:
            raw_date: Raw date dictionary from Gemini response.
            page_number: Optional page number.
            bbox_ids: Optional bounding box UUIDs from source chunk.
            document_id: Optional document ID for per-date bbox filtering.
            matter_id: Optional matter ID for reliability logging.

        Returns:
            ExtractedDate or None if parsing fails.
        """
        date_text = raw_date.get("date_text", "").strip()
        if not date_text:
            return None

        # Reject bracket numbers misidentified as dates (e.g., [993], [994])
        # These are paragraph references in legal documents, not years
        if re.match(r'^\[?\d{3,4}\]?$', date_text):
            logger.debug(
                "date_rejected_bracket_number",
                date_text=date_text,
                reason="Looks like paragraph reference [NNN], not a date",
            )
            return None

        extracted_date_str = raw_date.get("extracted_date", "")
        if not extracted_date_str:
            return None

        # Sanitize date_text: fix OCR artifacts like extra digits in years (e.g., "8/10/20214" → "8/10/2021")
        # Match year-like sequences of 5+ digits and truncate to 4
        date_text = re.sub(r'(\d{4})\d+', r'\1', date_text)

        # Parse date string
        try:
            date_parts = extracted_date_str.split("-")
            year = int(date_parts[0])
            month = int(date_parts[1])
            day = int(date_parts[2])

            # Validate year is within reasonable bounds for legal documents
            if year < MIN_VALID_YEAR or year > MAX_VALID_YEAR:
                logger.debug(
                    "date_rejected_invalid_year",
                    date_str=extracted_date_str,
                    year=year,
                    reason=f"Year {year} outside valid range {MIN_VALID_YEAR}-{MAX_VALID_YEAR}",
                )
                return None

            extracted_date = date(year, month, day)
        except (ValueError, IndexError):
            logger.debug(
                "date_parse_invalid_date",
                date_str=extracted_date_str,
            )
            return None

        # Parse precision
        precision_str = raw_date.get("date_precision", "day")
        if precision_str not in ("day", "month", "year", "approximate"):
            precision_str = "day"

        # Per-date bbox filtering: filter chunk bbox_ids to only those
        # containing this specific date's text (fixes chunk-level aggregation)
        filtered_bbox_ids = bbox_ids or []
        filtered_page = page_number
        if bbox_ids and document_id:
            # F9: Build search text from date_text + context for better matching
            # Increased from 200 to 500 chars to capture more context for legal clauses
            context_before = raw_date.get("context_before", "")[:500]
            context_after = raw_date.get("context_after", "")[:500]
            search_text = f"{context_before} {date_text} {context_after}".strip()

            # Story 6.1: Enable reliability logging for citation page accuracy
            filtered_ids, detected_page = get_filtered_bbox_ids(
                item_text=search_text,
                chunk_bbox_ids=bbox_ids,
                document_id=document_id,
                matter_id=matter_id,
                log_reliability=bool(matter_id),  # Only log if matter_id provided
            )
            if filtered_ids:
                filtered_bbox_ids = filtered_ids
                if detected_page is not None:
                    filtered_page = detected_page

        # Parse event type and description
        event_type = raw_date.get("event_type", "unclassified")
        valid_event_types = ["filing", "hearing", "order", "notice", "transaction", "document", "deadline", "incident", "unclassified"]
        if event_type not in valid_event_types:
            event_type = "unclassified"

        event_description = raw_date.get("event_description", "")
        if not event_description:
            # Fallback: use truncated context as description
            context = raw_date.get("context_before", "") + " " + raw_date.get("context_after", "")
            event_description = context.strip()[:100] if context.strip() else ""

        # Parse event_source (primary vs referenced) from LLM response
        event_source = raw_date.get("event_source", "primary")
        is_ambiguous = raw_date.get("is_ambiguous", False)
        ambiguity_reason = raw_date.get("ambiguity_reason")

        # If event is referenced, enforce ambiguity flags
        if event_source == "referenced":
            is_ambiguous = True
            if not ambiguity_reason:
                ambiguity_reason = "Referenced in document, not a primary event"
            # Cap confidence for referenced events
            confidence = float(raw_date.get("confidence", 0.7))
            confidence = min(confidence, 0.75)
        else:
            confidence = float(raw_date.get("confidence", 0.8))

        return ExtractedDate(
            extracted_date=extracted_date,
            date_text=date_text,
            date_precision=precision_str,  # type: ignore
            event_type=event_type,
            event_description=event_description[:200],  # Limit to 200 chars
            context_before=raw_date.get("context_before", "")[:1000],  # Limit size
            context_after=raw_date.get("context_after", "")[:1000],
            page_number=filtered_page,
            bbox_ids=filtered_bbox_ids,
            is_ambiguous=is_ambiguous,
            ambiguity_reason=ambiguity_reason,
            confidence=confidence,
        )

    def extract_dates_batch_sync(
        self,
        chunks: list[dict],
        document_id: str,
        matter_id: str | None = None,
    ) -> dict[str, DateExtractionResult]:
        """Extract dates from multiple chunks in a single Gemini call.

        B3 optimization: Batches N chunks (default 3) per Gemini call using
        [CHUNK:id] markers, reducing LLM calls by ~66%.

        Falls back to per-chunk extraction on parse failure.

        Args:
            chunks: List of chunk dicts with 'id', 'content', 'page_number', 'bbox_ids'.
            document_id: Document ID for cost tracking.
            matter_id: Matter ID for cost tracking.

        Returns:
            Dict mapping chunk_id -> DateExtractionResult.
        """
        from app.core.circuit_breaker import get_circuit_registry

        # Build combined text with chunk markers
        marked_sections = []
        for chunk in chunks:
            chunk_id = chunk["id"]
            content = chunk.get("content", "")
            if not content or not content.strip():
                continue
            # Cap each chunk at MAX_TEXT_LENGTH (same as single-chunk mode)
            truncated = content[:MAX_TEXT_LENGTH] if len(content) > MAX_TEXT_LENGTH else content
            page_num = chunk.get("page_number", "unknown")
            marked_sections.append(
                f"[CHUNK:{chunk_id}] (page {page_num})\n{truncated}"
            )

        # If no valid content, return empty results for all chunks
        if not marked_sections:
            return {
                chunk["id"]: self._empty_result(document_id, matter_id or "")
                for chunk in chunks
            }

        batch_text = "\n\n".join(marked_sections)
        prompt = DATE_EXTRACTION_BATCH_PROMPT.format(batch_sections=batch_text)

        cost_tracker = CostTracker(
            provider=LLMProvider.GEMINI_FLASH,
            operation="date_extraction_batch",
            matter_id=matter_id or "",
            document_id=document_id,
        )

        # Check circuit state
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.GEMINI_FLASH)

        if breaker.is_open:
            logger.warning(
                "date_extraction_batch_circuit_open",
                document_id=document_id,
                chunk_count=len(chunks),
                cooldown_remaining=breaker.cooldown_remaining,
            )
            return {
                chunk["id"]: self._empty_result(document_id, matter_id or "")
                for chunk in chunks
            }

        try:
            from google.genai import types

            distributed_limiter = get_distributed_rate_limiter(RateLimitProvider.GEMINI)
            with distributed_limiter:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=DATE_EXTRACTION_SYSTEM_PROMPT,
                        max_output_tokens=8192,
                        temperature=0.1,
                    ),
                )

            response_text = response.text if response.text else ""
            input_tokens = estimate_tokens(prompt)
            output_tokens = estimate_tokens(response_text)
            cost_tracker.add_tokens(input_tokens=input_tokens, output_tokens=output_tokens)
            cost_tracker.log_cost()
            persist_cost_sync(cost_tracker)

            breaker.record_success()

            # Parse batch response into per-chunk date lists
            chunk_dates = self._parse_batch_response(
                response_text, [c["id"] for c in chunks]
            )

            # Build DateExtractionResult per chunk, attaching page/bbox metadata
            chunk_lookup = {c["id"]: c for c in chunks}
            results: dict[str, DateExtractionResult] = {}

            for chunk_id, raw_dates in chunk_dates.items():
                chunk_meta = chunk_lookup.get(chunk_id, {})
                page_number = chunk_meta.get("page_number")
                bbox_ids = chunk_meta.get("bbox_ids") or []

                dates: list[ExtractedDate] = []
                for raw_date in raw_dates:
                    try:
                        extracted = self._parse_single_date(
                            raw_date, page_number, bbox_ids, document_id, matter_id
                        )
                        if extracted:
                            dates.append(extracted)
                    except Exception as e:
                        logger.debug(
                            "date_batch_parse_single_error",
                            error=str(e),
                            chunk_id=chunk_id,
                        )
                        continue

                results[chunk_id] = DateExtractionResult(
                    dates=dates,
                    document_id=document_id,
                    matter_id=matter_id or "",
                    total_dates_found=len(dates),
                    processing_time_ms=0,
                )

            # Ensure every input chunk has a result (even if not in response)
            for chunk in chunks:
                if chunk["id"] not in results:
                    results[chunk["id"]] = self._empty_result(
                        document_id, matter_id or ""
                    )

            logger.info(
                "date_extraction_batch_complete",
                document_id=document_id,
                chunk_count=len(chunks),
                total_dates=sum(len(r.dates) for r in results.values()),
            )

            return results

        except DateConfigurationError:
            raise

        except Exception as e:
            breaker.record_failure()
            logger.warning(
                "date_extraction_batch_failed_fallback",
                document_id=document_id,
                chunk_count=len(chunks),
                error=str(e),
                error_type=type(e).__name__,
            )

            # Fallback: extract chunks individually
            results = {}
            for chunk in chunks:
                chunk_result = self._extract_single_sync(
                    text=chunk.get("content", ""),
                    document_id=document_id,
                    matter_id=matter_id or "",
                    page_number=chunk.get("page_number"),
                    bbox_ids=chunk.get("bbox_ids") or [],
                )
                results[chunk["id"]] = chunk_result

            return results

    def _parse_batch_response(
        self,
        response_text: str,
        chunk_ids: list[str],
    ) -> dict[str, list[dict]]:
        """Parse Gemini batch response with per-chunk grouping.

        Expected format: {"chunks": {"chunk_id": {"dates": [...]}}}
        Falls back to flat format for backwards compatibility.

        Args:
            response_text: Raw Gemini response.
            chunk_ids: Expected chunk IDs.

        Returns:
            Dict mapping chunk_id -> list of raw date dicts.
        """
        result: dict[str, list[dict]] = {cid: [] for cid in chunk_ids}

        try:
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

            parsed = json.loads(json_text)

            # Batch format: {"chunks": {"id": {"dates": [...]}}}
            if "chunks" in parsed and isinstance(parsed["chunks"], dict):
                for chunk_id, chunk_data in parsed["chunks"].items():
                    if chunk_id in result:
                        result[chunk_id] = chunk_data.get("dates", [])
                return result

            # Fallback: flat format {"dates": [...]} — assign all to first chunk
            if "dates" in parsed and chunk_ids:
                result[chunk_ids[0]] = parsed["dates"]
                return result

        except json.JSONDecodeError as e:
            # Attempt JSON repair for truncated responses
            repaired = self._try_repair_json(json_text)
            if repaired is not None:
                logger.info(
                    "date_batch_response_json_repaired",
                    original_error=str(e),
                )
                if "chunks" in repaired and isinstance(repaired["chunks"], dict):
                    for chunk_id, chunk_data in repaired["chunks"].items():
                        if chunk_id in result:
                            result[chunk_id] = chunk_data.get("dates", [])
                    return result
                if "dates" in repaired and chunk_ids:
                    result[chunk_ids[0]] = repaired["dates"]
                    return result

            logger.warning(
                "date_batch_parse_failed",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )

        except (KeyError, TypeError) as e:
            logger.warning(
                "date_batch_parse_failed",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )

        return result

    def _empty_result(
        self,
        document_id: str,
        matter_id: str,
    ) -> DateExtractionResult:
        """Create empty extraction result."""
        return DateExtractionResult(
            dates=[],
            document_id=document_id,
            matter_id=matter_id,
            total_dates_found=0,
            processing_time_ms=0,
        )


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_date_extractor() -> DateExtractor:
    """Get singleton date extractor instance.

    Returns:
        DateExtractor instance.
    """
    return DateExtractor()
