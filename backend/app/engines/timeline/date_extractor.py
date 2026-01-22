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

from app.core.circuit_breaker import (
    CircuitOpenError,
    CircuitService,
    with_circuit_breaker,
)
from app.core.config import get_settings
from app.core.cost_tracking import (
    CostTracker,
    LLMProvider,
    estimate_tokens,
)
from app.engines.timeline.prompts import (
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


class DateExtractor:
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
            DateConfigurationError: If API key is not configured.
        """
        if self._model is None:
            if not self.api_key:
                raise DateConfigurationError(
                    "Gemini API key not configured. Set GEMINI_API_KEY environment variable."
                )

            try:
                import google.generativeai as genai

                self._genai = genai
                genai.configure(api_key=self.api_key)
                # Configure generation with higher max_output_tokens to avoid truncation
                generation_config = genai.GenerationConfig(
                    max_output_tokens=8192,  # Increased from default to avoid truncation
                    temperature=0.1,  # Low temperature for consistent extraction
                )
                self._model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=DATE_EXTRACTION_SYSTEM_PROMPT,
                    generation_config=generation_config,
                )
                logger.info(
                    "date_extractor_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("date_extractor_init_failed", error=str(e))
                raise DateConfigurationError(
                    f"Failed to initialize Gemini for date extraction: {e}"
                ) from e

        return self._model

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
    ) -> DateExtractionResult:
        """Extract dates from a single text chunk with circuit breaker.

        Args:
            text: Text chunk to process.
            document_id: Source document UUID.
            matter_id: Matter UUID.
            page_number: Optional page number.

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

            # Parse response
            result = self._parse_response(
                response_text,
                document_id=document_id,
                matter_id=matter_id,
                page_number=page_number,
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
        response = await self.model.generate_content_async(prompt)
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
    ) -> DateExtractionResult:
        """Synchronous wrapper for date extraction.

        For use in Celery tasks or other synchronous contexts.

        Args:
            text: Document text to extract dates from.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.
            page_number: Optional page number.

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
        )

        result.processing_time_ms = int((time.time() - start_time) * 1000)
        return result

    def _extract_single_sync(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        page_number: int | None = None,
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
            response = self.model.generate_content(prompt)

            # Track costs (Gemini doesn't expose token counts, so estimate)
            response_text = response.text if response.text else ""
            input_tokens = estimate_tokens(prompt)
            output_tokens = estimate_tokens(response_text)
            cost_tracker.add_tokens(input_tokens=input_tokens, output_tokens=output_tokens)
            cost_tracker.log_cost()

            result = self._parse_response(
                response_text,
                document_id=document_id,
                matter_id=matter_id,
                page_number=page_number,
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
    ) -> DateExtractionResult:
        """Parse Gemini response into DateExtractionResult.

        Args:
            response_text: Raw response from Gemini.
            document_id: Source document UUID.
            matter_id: Matter UUID.
            page_number: Optional page number.

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
                    extracted = self._parse_single_date(raw_date, page_number)
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

    def _parse_single_date(
        self,
        raw_date: dict,
        page_number: int | None,
    ) -> ExtractedDate | None:
        """Parse a single date entry from LLM response.

        Args:
            raw_date: Raw date dictionary from Gemini response.
            page_number: Optional page number.

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

        return ExtractedDate(
            extracted_date=extracted_date,
            date_text=date_text,
            date_precision=precision_str,  # type: ignore
            context_before=raw_date.get("context_before", "")[:1000],  # Limit size
            context_after=raw_date.get("context_after", "")[:1000],
            page_number=page_number,
            bbox_ids=[],  # Will be populated if bbox data available
            is_ambiguous=raw_date.get("is_ambiguous", False),
            ambiguity_reason=raw_date.get("ambiguity_reason"),
            confidence=float(raw_date.get("confidence", 0.8)),
        )

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
