"""Gemini-based Citation Extraction Service.

Uses Gemini 3 Flash for extracting Act citations from legal documents.
Combines LLM extraction with regex patterns for reliability.

CRITICAL: Uses Gemini for citation extraction per LLM routing rules -
this is an ingestion task, NOT user-facing reasoning.

Story 3-1: Act Citation Extraction (AC: #1, #2, #4)
"""

import asyncio
import json
import re
import time
from datetime import UTC, datetime
from functools import lru_cache
from typing import Final

import structlog

from app.core.config import get_settings
from app.engines.citation.abbreviations import (
    get_canonical_name,
    normalize_act_name,
)
from app.engines.citation.prompts import (
    CITATION_EXTRACTION_PROMPT,
    CITATION_EXTRACTION_SYSTEM_PROMPT,
)
from app.models.citation import (
    CitationExtractionResult,
    ExtractedCitation,
)

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

MAX_RETRIES: Final[int] = 3
INITIAL_RETRY_DELAY: Final[float] = 1.0
MAX_RETRY_DELAY: Final[float] = 30.0
MAX_TEXT_LENGTH: Final[int] = 30000  # Max characters per extraction request

# Regex patterns for common citation formats
CITATION_PATTERNS: Final[list[re.Pattern]] = [
    # Section X of Act Name, Year - e.g., "Section 138 of the Negotiable Instruments Act, 1881"
    re.compile(
        r"[Ss]ection\s+(\d+(?:\s*\(\s*\d+\s*\))?(?:\s*\(\s*[a-z]\s*\))?)"
        r"(?:\s+(?:of\s+)?(?:the\s+)?)?([A-Z][A-Za-z\s,&]+(?:Act|Code|Rules))"
        r"(?:,?\s*(\d{4}))?",
        re.IGNORECASE,
    ),
    # S. X / Sec. X of Act - e.g., "S. 138 NI Act"
    re.compile(
        r"[Ss](?:ec)?\.?\s*(\d+(?:\s*\(\s*\d+\s*\))?)"
        r"\s+(?:of\s+)?([A-Z][A-Za-z\s\.]+(?:Act|Code))",
        re.IGNORECASE,
    ),
    # u/s X patterns - e.g., "u/s 138 of NI Act"
    re.compile(
        r"u/s\s*\.?\s*(\d+(?:\s*\(\s*\d+\s*\))?)"
        r"\s+(?:of\s+)?([A-Z][A-Za-z\s\.]+)",
        re.IGNORECASE,
    ),
    # Section ranges - e.g., "Sections 138-141 of NI Act"
    re.compile(
        r"[Ss]ections?\s+(\d+)\s*[-–to]+\s*(\d+)"
        r"\s+(?:of\s+)?([A-Z][A-Za-z\s\.]+(?:Act|Code)?)",
        re.IGNORECASE,
    ),
    # Read with patterns - e.g., "Section 138 read with Section 139"
    re.compile(
        r"[Ss]ection\s+(\d+)\s+read\s+with\s+[Ss]ection\s+(\d+)",
        re.IGNORECASE,
    ),
]


# =============================================================================
# Exceptions
# =============================================================================


class CitationExtractorError(Exception):
    """Base exception for citation extractor operations."""

    def __init__(
        self,
        message: str,
        code: str = "CITATION_EXTRACTOR_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class CitationConfigurationError(CitationExtractorError):
    """Raised when Gemini is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="CITATION_NOT_CONFIGURED", is_retryable=False)


# =============================================================================
# Service Implementation
# =============================================================================


class CitationExtractor:
    """Service for extracting Act citations from legal documents using Gemini 3 Flash.

    Extracts:
    - Act/Statute names (full and abbreviated)
    - Section numbers, subsections, and clauses
    - Quoted text from Acts
    - Provisos, explanations, and amendments

    Combines LLM extraction with regex patterns for higher recall.

    Example:
        >>> extractor = CitationExtractor()
        >>> result = await extractor.extract_from_text(
        ...     text="Section 138 of the NI Act was invoked.",
        ...     document_id="doc-123",
        ...     matter_id="matter-456",
        ...     page_number=5,
        ... )
        >>> len(result.citations)
        1
        >>> result.citations[0].act_name
        'NI Act'
    """

    def __init__(self) -> None:
        """Initialize citation extractor."""
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
            CitationConfigurationError: If API key is not configured.
        """
        if self._model is None:
            if not self.api_key:
                raise CitationConfigurationError(
                    "Gemini API key not configured. Set GEMINI_API_KEY environment variable."
                )

            try:
                import google.generativeai as genai

                self._genai = genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=CITATION_EXTRACTION_SYSTEM_PROMPT,
                )
                logger.info(
                    "citation_extractor_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("citation_extractor_init_failed", error=str(e))
                raise CitationConfigurationError(
                    f"Failed to initialize Gemini for citation extraction: {e}"
                ) from e

        return self._model

    async def extract_from_text(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        page_number: int | None = None,
        chunk_id: str | None = None,
    ) -> CitationExtractionResult:
        """Extract citations from text using Gemini and regex.

        Args:
            text: Document text to extract citations from.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.
            page_number: Optional page number.
            chunk_id: Optional source chunk UUID.

        Returns:
            CitationExtractionResult containing extracted citations.

        Raises:
            CitationExtractorError: If extraction fails after retries.
        """
        # Handle empty text
        if not text or not text.strip():
            logger.debug(
                "citation_extraction_empty_text",
                document_id=document_id,
                matter_id=matter_id,
            )
            return CitationExtractionResult(
                citations=[],
                unique_acts=[],
                source_document_id=document_id,
                source_chunk_id=chunk_id,
                page_number=page_number,
                extraction_timestamp=datetime.now(UTC),
            )

        # Truncate if too long
        if len(text) > MAX_TEXT_LENGTH:
            logger.warning(
                "citation_extraction_text_truncated",
                original_length=len(text),
                max_length=MAX_TEXT_LENGTH,
                document_id=document_id,
            )
            text = text[:MAX_TEXT_LENGTH]

        start_time = time.time()

        # Step 1: Extract with regex first (fast, reliable)
        regex_citations = self._extract_with_regex(text)

        # Step 2: Extract with Gemini (comprehensive)
        gemini_citations = await self._extract_with_gemini(text, document_id)

        # Step 3: Merge and deduplicate
        all_citations = self._merge_citations(regex_citations, gemini_citations)

        # Step 4: Normalize act names and compute unique acts
        unique_acts = self._get_unique_acts(all_citations)

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "citation_extraction_complete",
            document_id=document_id,
            matter_id=matter_id,
            citation_count=len(all_citations),
            unique_act_count=len(unique_acts),
            regex_count=len(regex_citations),
            gemini_count=len(gemini_citations),
            processing_time_ms=processing_time,
        )

        return CitationExtractionResult(
            citations=all_citations,
            unique_acts=unique_acts,
            source_document_id=document_id,
            source_chunk_id=chunk_id,
            page_number=page_number,
            extraction_timestamp=datetime.now(UTC),
        )

    def extract_from_text_sync(
        self,
        text: str,
        document_id: str,
        matter_id: str,
        page_number: int | None = None,
        chunk_id: str | None = None,
    ) -> CitationExtractionResult:
        """Synchronous wrapper for citation extraction.

        For use in Celery tasks or other synchronous contexts.

        Args:
            text: Document text to extract citations from.
            document_id: Source document UUID.
            matter_id: Matter UUID for context.
            page_number: Optional page number.
            chunk_id: Optional source chunk UUID.

        Returns:
            CitationExtractionResult containing extracted citations.
        """
        # Handle empty text
        if not text or not text.strip():
            return CitationExtractionResult(
                citations=[],
                unique_acts=[],
                source_document_id=document_id,
                source_chunk_id=chunk_id,
                page_number=page_number,
                extraction_timestamp=datetime.now(UTC),
            )

        # Truncate if too long
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH]

        start_time = time.time()

        # Step 1: Extract with regex first
        regex_citations = self._extract_with_regex(text)

        # Step 2: Extract with Gemini (sync)
        gemini_citations = self._extract_with_gemini_sync(text, document_id)

        # Step 3: Merge and deduplicate
        all_citations = self._merge_citations(regex_citations, gemini_citations)

        # Step 4: Get unique acts
        unique_acts = self._get_unique_acts(all_citations)

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "citation_extraction_sync_complete",
            document_id=document_id,
            matter_id=matter_id,
            citation_count=len(all_citations),
            unique_act_count=len(unique_acts),
            processing_time_ms=processing_time,
        )

        return CitationExtractionResult(
            citations=all_citations,
            unique_acts=unique_acts,
            source_document_id=document_id,
            source_chunk_id=chunk_id,
            page_number=page_number,
            extraction_timestamp=datetime.now(UTC),
        )

    def _extract_with_regex(self, text: str) -> list[ExtractedCitation]:
        """Extract citations using regex patterns.

        Args:
            text: Text to extract from.

        Returns:
            List of extracted citations.
        """
        citations: list[ExtractedCitation] = []

        for pattern in CITATION_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    groups = match.groups()

                    # Handle different pattern formats
                    if len(groups) >= 2:
                        section = groups[0].strip() if groups[0] else ""
                        act_name = groups[1].strip() if groups[1] else ""

                        # Skip if no act name
                        if not act_name:
                            continue

                        # Parse subsection from section (e.g., "138(1)")
                        subsection = None
                        clause = None
                        section_match = re.match(
                            r"(\d+)\s*(?:\((\d+)\))?\s*(?:\(([a-z])\))?",
                            section,
                            re.IGNORECASE,
                        )
                        if section_match:
                            section = section_match.group(1)
                            if section_match.group(2):
                                subsection = f"({section_match.group(2)})"
                            if section_match.group(3):
                                clause = f"({section_match.group(3)})"

                        citation = ExtractedCitation(
                            act_name=act_name,
                            section=section,
                            subsection=subsection,
                            clause=clause,
                            raw_text=match.group(0).strip(),
                            quoted_text=None,
                            confidence=75.0,  # Regex matches are high confidence
                        )
                        citations.append(citation)

                except Exception as e:
                    logger.debug(
                        "citation_regex_parse_error",
                        error=str(e),
                        match=match.group(0)[:100] if match else "",
                    )
                    continue

        return citations

    async def _extract_with_gemini(
        self,
        text: str,
        document_id: str,
    ) -> list[ExtractedCitation]:
        """Extract citations using Gemini.

        Args:
            text: Text to extract from.
            document_id: Document ID for logging.

        Returns:
            List of extracted citations.
        """
        prompt = CITATION_EXTRACTION_PROMPT.format(text=text)

        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.model.generate_content_async(prompt)
                return self._parse_gemini_response(response.text)

            except CitationConfigurationError:
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
                        "citation_extraction_rate_limited",
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
            "citation_extraction_gemini_failed",
            error=str(last_error),
            document_id=document_id,
            attempts=MAX_RETRIES,
        )

        return []  # Return empty on failure, regex results still available

    def _extract_with_gemini_sync(
        self,
        text: str,
        document_id: str,
    ) -> list[ExtractedCitation]:
        """Synchronous Gemini extraction.

        Args:
            text: Text to extract from.
            document_id: Document ID for logging.

        Returns:
            List of extracted citations.
        """
        prompt = CITATION_EXTRACTION_PROMPT.format(text=text)

        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                response = self.model.generate_content(prompt)
                return self._parse_gemini_response(response.text)

            except CitationConfigurationError:
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
                        "citation_extraction_sync_rate_limited",
                        attempt=attempt + 1,
                        retry_delay=retry_delay,
                    )
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_rate_limit:
                    break

        logger.error(
            "citation_extraction_gemini_sync_failed",
            error=str(last_error),
            document_id=document_id,
        )

        return []

    def _parse_gemini_response(self, response_text: str) -> list[ExtractedCitation]:
        """Parse Gemini response into citation list.

        Args:
            response_text: Raw response from Gemini.

        Returns:
            List of parsed citations.
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
                    "citation_response_not_dict",
                    response_type=type(parsed).__name__,
                )
                return []

            citations: list[ExtractedCitation] = []
            raw_citations = parsed.get("citations", [])

            for raw in raw_citations:
                try:
                    citation = ExtractedCitation(
                        act_name=raw.get("act_name", ""),
                        section=raw.get("section", ""),
                        subsection=raw.get("subsection"),
                        clause=raw.get("clause"),
                        raw_text=raw.get("raw_text", ""),
                        quoted_text=raw.get("quoted_text"),
                        confidence=float(raw.get("confidence", 80.0)),
                    )

                    if citation.act_name and citation.section:
                        citations.append(citation)

                except Exception as e:
                    logger.debug(
                        "citation_parse_error",
                        error=str(e),
                        raw=str(raw)[:100],
                    )
                    continue

            return citations

        except json.JSONDecodeError as e:
            logger.warning(
                "citation_response_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            return []

        except Exception as e:
            logger.warning(
                "citation_response_parse_error",
                error=str(e),
            )
            return []

    def _merge_citations(
        self,
        regex_citations: list[ExtractedCitation],
        gemini_citations: list[ExtractedCitation],
    ) -> list[ExtractedCitation]:
        """Merge and deduplicate citations from regex and Gemini.

        Prefers Gemini results for richer metadata, uses regex for validation.

        Args:
            regex_citations: Citations from regex extraction.
            gemini_citations: Citations from Gemini extraction.

        Returns:
            Merged and deduplicated list.
        """
        # Create a set of normalized keys for deduplication
        seen: set[str] = set()
        merged: list[ExtractedCitation] = []

        def make_key(c: ExtractedCitation) -> str:
            """Create a unique key for deduplication."""
            act_normalized = normalize_act_name(c.act_name)
            return f"{act_normalized}:{c.section}:{c.subsection or ''}:{c.clause or ''}"

        # Add Gemini citations first (higher quality)
        for citation in gemini_citations:
            key = make_key(citation)
            if key not in seen:
                seen.add(key)
                merged.append(citation)

        # Add regex citations that weren't found by Gemini
        for citation in regex_citations:
            key = make_key(citation)
            if key not in seen:
                seen.add(key)
                merged.append(citation)

        return merged

    def _get_unique_acts(self, citations: list[ExtractedCitation]) -> list[str]:
        """Get list of unique Act names from citations.

        Args:
            citations: List of extracted citations.

        Returns:
            List of unique normalized Act names.
        """
        unique_acts: set[str] = set()

        for citation in citations:
            # Try to get canonical name
            canonical = get_canonical_name(citation.act_name)
            if canonical:
                name, year = canonical
                if year:
                    unique_acts.add(f"{name}, {year}")
                else:
                    unique_acts.add(name)
            else:
                # Use the raw name
                unique_acts.add(citation.act_name)

        return sorted(unique_acts)


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_citation_extractor() -> CitationExtractor:
    """Get singleton citation extractor instance.

    Returns:
        CitationExtractor instance.
    """
    return CitationExtractor()
