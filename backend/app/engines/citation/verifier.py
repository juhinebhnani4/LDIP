"""Citation Verification Service.

Verifies citations extracted from legal documents against the actual text
of Acts and statutes. Uses Gemini 3 Flash for semantic comparison.

CRITICAL: Uses Gemini per LLM routing rules - verification is
extraction-adjacent, downstream from initial extraction.

Story 3-3: Citation Verification (AC: #1, #2, #3)
"""

import asyncio
import json
import re
import time
from functools import lru_cache
from typing import Final

import structlog

from app.core.config import get_settings
from app.engines.citation.act_indexer import ActIndexer, ActNotIndexedError, get_act_indexer
from app.engines.citation.verification_prompts import (
    SECTION_MATCHING_PROMPT,
    TEXT_COMPARISON_PROMPT,
    VERIFICATION_EXPLANATION_PROMPT,
    VERIFICATION_SYSTEM_PROMPT,
)
from app.models.chunk import ChunkWithContent
from app.models.citation import (
    Citation,
    DiffDetail,
    QuoteComparison,
    SectionMatch,
    VerificationResult,
    VerificationStatus,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

MAX_RETRIES: Final[int] = 3
INITIAL_RETRY_DELAY: Final[float] = 1.0
MAX_RETRY_DELAY: Final[float] = 30.0
RATE_LIMIT_DELAY: Final[float] = 0.5  # Delay between API calls

# Similarity thresholds
EXACT_MATCH_THRESHOLD: Final[float] = 95.0
PARAPHRASE_THRESHOLD: Final[float] = 70.0
MISMATCH_THRESHOLD: Final[float] = 50.0


# =============================================================================
# Exceptions
# =============================================================================


class CitationVerificationError(Exception):
    """Base exception for verification errors."""

    def __init__(
        self,
        message: str,
        code: str = "VERIFICATION_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class VerificationConfigurationError(CitationVerificationError):
    """Raised when Gemini is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="VERIFICATION_NOT_CONFIGURED", is_retryable=False)


class SectionNotFoundError(CitationVerificationError):
    """Section not found in Act document."""

    def __init__(self, section: str, act_name: str):
        super().__init__(
            f"Section {section} not found in {act_name}",
            code="SECTION_NOT_FOUND",
            is_retryable=False,
        )


class QuoteComparisonError(CitationVerificationError):
    """Error comparing quoted text."""

    def __init__(self, message: str):
        super().__init__(message, code="QUOTE_COMPARISON_ERROR", is_retryable=True)


# =============================================================================
# Service Implementation
# =============================================================================


class CitationVerifier:
    """Service for verifying citations against Act text using Gemini.

    Verifies:
    - Section exists in cited Act
    - Quoted text matches Act text (semantic comparison)
    - Returns detailed verification results with explanations

    Example:
        >>> verifier = CitationVerifier()
        >>> result = await verifier.verify_citation(citation, act_document_id)
        >>> if result.status == VerificationStatus.VERIFIED:
        ...     print(f"Citation verified: {result.explanation}")
    """

    def __init__(self, act_indexer: ActIndexer | None = None) -> None:
        """Initialize citation verifier.

        Args:
            act_indexer: Optional ActIndexer instance for testing.
        """
        self._model = None
        self._genai = None
        self._act_indexer = act_indexer
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model

    @property
    def model(self):
        """Get or create Gemini model instance.

        Returns:
            Gemini GenerativeModel instance.

        Raises:
            VerificationConfigurationError: If API key is not configured.
        """
        if self._model is None:
            if not self.api_key:
                raise VerificationConfigurationError(
                    "Gemini API key not configured. Set GEMINI_API_KEY environment variable."
                )

            try:
                import google.generativeai as genai

                self._genai = genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=VERIFICATION_SYSTEM_PROMPT,
                )
                logger.info(
                    "citation_verifier_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("citation_verifier_init_failed", error=str(e))
                raise VerificationConfigurationError(
                    f"Failed to initialize Gemini for verification: {e}"
                ) from e

        return self._model

    @property
    def act_indexer(self) -> ActIndexer:
        """Get act indexer instance."""
        if self._act_indexer is None:
            self._act_indexer = get_act_indexer()
        return self._act_indexer

    async def verify_citation(
        self,
        citation: Citation,
        act_document_id: str,
        act_name: str = "Unknown Act",
    ) -> VerificationResult:
        """Verify a citation against an Act document.

        Args:
            citation: Citation to verify.
            act_document_id: UUID of the uploaded Act document.
            act_name: Display name of the Act.

        Returns:
            VerificationResult with status and explanation.
        """
        start_time = time.time()

        try:
            # Step 1: Index the Act document (cached after first call)
            index = await self.act_indexer.index_act_document(
                document_id=act_document_id,
                matter_id=citation.matter_id,
                act_name=act_name,
            )

            # Step 2: Find the section in the Act
            section_match = await self.find_section_in_act(
                act_name=act_name,
                section=citation.section_number,
                act_document_id=act_document_id,
            )

            if section_match is None:
                # Section not found
                processing_time = int((time.time() - start_time) * 1000)
                available_sections = self.act_indexer.get_available_sections(act_document_id)

                explanation = await self._generate_not_found_explanation(
                    act_name=act_name,
                    section=citation.section_number,
                    available_sections=available_sections[:10],  # First 10 for context
                )

                logger.info(
                    "citation_verification_section_not_found",
                    citation_id=citation.id,
                    section=citation.section_number,
                    act_name=act_name,
                    processing_time_ms=processing_time,
                )

                return VerificationResult(
                    status=VerificationStatus.SECTION_NOT_FOUND,
                    section_found=False,
                    section_text=None,
                    target_page=None,
                    target_bbox_ids=[],
                    similarity_score=0.0,
                    explanation=explanation,
                    diff_details=None,
                )

            # Step 3: Compare quoted text if present
            diff_details = None
            similarity_score = 100.0  # Default for section-only verification
            status = VerificationStatus.VERIFIED

            if citation.quoted_text and citation.quoted_text.strip():
                comparison = await self.compare_quoted_text(
                    citation_quote=citation.quoted_text,
                    act_text=section_match.section_text,
                )

                similarity_score = comparison.similarity_score

                if comparison.match_type == "mismatch":
                    status = VerificationStatus.MISMATCH
                    diff_details = DiffDetail(
                        citation_text=citation.quoted_text,
                        act_text=section_match.section_text[:500],  # Truncate for storage
                        match_type=comparison.match_type,
                        differences=[comparison.explanation],
                    )
                elif comparison.match_type == "paraphrase":
                    # Paraphrase is still considered verified
                    status = VerificationStatus.VERIFIED

            # Step 4: Generate explanation
            explanation = await self._generate_verification_explanation(
                act_name=act_name,
                section=citation.section_number,
                quoted_text=citation.quoted_text,
                status=status,
                section_found=True,
                similarity_score=similarity_score,
                match_type=diff_details.match_type if diff_details else "exact",
                differences=[diff_details.differences[0]] if diff_details and diff_details.differences else [],
            )

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "citation_verification_complete",
                citation_id=citation.id,
                status=status.value,
                similarity_score=similarity_score,
                processing_time_ms=processing_time,
            )

            return VerificationResult(
                status=status,
                section_found=True,
                section_text=section_match.section_text[:1000],  # Truncate for storage
                target_page=section_match.page_number,
                target_bbox_ids=section_match.bbox_ids,
                similarity_score=similarity_score,
                explanation=explanation,
                diff_details=diff_details,
            )

        except ActNotIndexedError as e:
            logger.error(
                "citation_verification_act_not_indexed",
                citation_id=citation.id,
                act_document_id=act_document_id,
                error=str(e),
            )
            return VerificationResult(
                status=VerificationStatus.ACT_UNAVAILABLE,
                section_found=False,
                section_text=None,
                target_page=None,
                target_bbox_ids=[],
                similarity_score=0.0,
                explanation=f"Act document could not be indexed: {e.message}",
                diff_details=None,
            )

        except Exception as e:
            logger.error(
                "citation_verification_failed",
                citation_id=citation.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return VerificationResult(
                status=VerificationStatus.ACT_UNAVAILABLE,
                section_found=False,
                section_text=None,
                target_page=None,
                target_bbox_ids=[],
                similarity_score=0.0,
                explanation=f"Verification failed: {str(e)}",
                diff_details=None,
            )

    async def find_section_in_act(
        self,
        act_name: str,
        section: str,
        act_document_id: str,
    ) -> SectionMatch | None:
        """Find a section in the Act document.

        Uses regex patterns first, then falls back to LLM-based search.

        Args:
            act_name: Name of the Act.
            section: Section number to find.
            act_document_id: Act document UUID.

        Returns:
            SectionMatch if found, None otherwise.
        """
        try:
            # Get chunks for the section
            chunks = await self.act_indexer.get_section_chunks(
                act_document_id=act_document_id,
                section=section,
            )

            if not chunks:
                # Try LLM-based search as fallback
                all_chunks, _, _ = await asyncio.to_thread(
                    self.act_indexer.chunk_service.get_chunks_for_document,
                    act_document_id,
                )
                if all_chunks:
                    return await self._find_section_with_llm(
                        act_name=act_name,
                        section=section,
                        chunks=all_chunks[:20],  # Limit to first 20 chunks
                    )
                return None

            # Combine chunk content for section text
            section_text = "\n".join(c.content for c in chunks)

            # Get page and bbox from first chunk
            first_chunk = chunks[0]

            return SectionMatch(
                section_number=section,
                section_text=section_text,
                chunk_id=first_chunk.id,
                page_number=first_chunk.page_number or 1,
                bbox_ids=[],  # Will be populated if available
                confidence=90.0,
            )

        except ActNotIndexedError:
            raise
        except Exception as e:
            logger.warning(
                "find_section_in_act_failed",
                section=section,
                act_document_id=act_document_id,
                error=str(e),
            )
            return None

    async def _find_section_with_llm(
        self,
        act_name: str,
        section: str,
        chunks: list[ChunkWithContent],
    ) -> SectionMatch | None:
        """Use LLM to find section when regex fails.

        Args:
            act_name: Name of the Act.
            section: Section number to find.
            chunks: Act document chunks.

        Returns:
            SectionMatch if found, None otherwise.
        """
        # Prepare chunks text
        chunks_text = "\n\n---\n\n".join(
            f"CHUNK {i+1} (ID: {c.id}, Page: {c.page_number or 'N/A'}):\n{c.content[:2000]}"
            for i, c in enumerate(chunks)
        )

        prompt = SECTION_MATCHING_PROMPT.format(
            section_number=section,
            act_name=act_name,
            chunks_text=chunks_text,
        )

        try:
            response = await self._call_gemini_with_retry(prompt)
            result = self._parse_json_response(response)

            if result and result.get("found"):
                chunk_id = result.get("chunk_id")
                if chunk_id:
                    # Find the matching chunk
                    matching_chunk = next(
                        (c for c in chunks if c.id == chunk_id), None
                    )
                    if matching_chunk:
                        return SectionMatch(
                            section_number=result.get("section_number", section),
                            section_text=result.get("section_text", matching_chunk.content[:1000]),
                            chunk_id=chunk_id,
                            page_number=matching_chunk.page_number or 1,
                            bbox_ids=[],
                            confidence=result.get("confidence", 75.0),
                        )

            return None

        except Exception as e:
            logger.warning(
                "llm_section_search_failed",
                section=section,
                error=str(e),
            )
            return None

    async def compare_quoted_text(
        self,
        citation_quote: str,
        act_text: str,
    ) -> QuoteComparison:
        """Compare quoted text from citation against Act text.

        Uses LLM for semantic comparison.

        Args:
            citation_quote: Text quoted in the citation.
            act_text: Actual text from the Act.

        Returns:
            QuoteComparison with match type and similarity score.
        """
        # Quick exact match check first
        normalized_quote = self._normalize_text(citation_quote)
        normalized_act = self._normalize_text(act_text)

        if normalized_quote in normalized_act:
            return QuoteComparison(
                similarity_score=100.0,
                match_type="exact",
                explanation="The quoted text matches the Act text exactly.",
            )

        # Use LLM for semantic comparison
        prompt = TEXT_COMPARISON_PROMPT.format(
            citation_quote=citation_quote[:1000],
            act_text=act_text[:2000],
        )

        try:
            response = await self._call_gemini_with_retry(prompt)
            result = self._parse_json_response(response)

            if result:
                return QuoteComparison(
                    similarity_score=float(result.get("similarity_score", 50.0)),
                    match_type=result.get("match_type", "mismatch"),
                    explanation=result.get("explanation", "Unable to compare texts."),
                )

            # Fallback if parsing fails
            return QuoteComparison(
                similarity_score=50.0,
                match_type="mismatch",
                explanation="Unable to compare texts - parsing error.",
            )

        except Exception as e:
            logger.warning(
                "quote_comparison_failed",
                error=str(e),
            )
            return QuoteComparison(
                similarity_score=50.0,
                match_type="mismatch",
                explanation=f"Comparison error: {str(e)}",
            )

    async def _generate_verification_explanation(
        self,
        act_name: str,
        section: str,
        quoted_text: str | None,
        status: VerificationStatus,
        section_found: bool,
        similarity_score: float,
        match_type: str,
        differences: list[str],
    ) -> str:
        """Generate human-readable verification explanation.

        Args:
            act_name: Name of the Act.
            section: Section number.
            quoted_text: Quoted text (if any).
            status: Verification status.
            section_found: Whether section was found.
            similarity_score: Similarity score.
            match_type: Match type.
            differences: List of differences.

        Returns:
            Human-readable explanation.
        """
        prompt = VERIFICATION_EXPLANATION_PROMPT.format(
            act_name=act_name,
            section_number=section,
            quoted_text=quoted_text[:500] if quoted_text else "None",
            status=status.value,
            section_found=section_found,
            similarity_score=similarity_score,
            match_type=match_type,
            differences=", ".join(differences) if differences else "None",
        )

        try:
            response = await self._call_gemini_with_retry(prompt)
            result = self._parse_json_response(response)

            if result and result.get("explanation"):
                return result["explanation"]

        except Exception as e:
            logger.warning(
                "explanation_generation_failed",
                error=str(e),
            )

        # Fallback explanations
        if status == VerificationStatus.VERIFIED:
            return f"Section {section} of {act_name} verified. Citation matches Act text."
        elif status == VerificationStatus.MISMATCH:
            return f"Section {section} found in {act_name} but quoted text differs. Similarity: {similarity_score:.0f}%"
        else:
            return f"Section {section} verification result: {status.value}"

    async def _generate_not_found_explanation(
        self,
        act_name: str,
        section: str,
        available_sections: list[str],
    ) -> str:
        """Generate explanation for section not found.

        Args:
            act_name: Name of the Act.
            section: Section that wasn't found.
            available_sections: List of available sections.

        Returns:
            Human-readable explanation.
        """
        sections_str = ", ".join(available_sections) if available_sections else "unknown"
        return (
            f"Section {section} not found in {act_name}. "
            f"Available sections include: {sections_str}. "
            "The citation may contain a typographical error or reference a non-existent section."
        )

    async def _call_gemini_with_retry(self, prompt: str) -> str:
        """Call Gemini API with retry logic.

        Args:
            prompt: Prompt to send.

        Returns:
            Response text.

        Raises:
            CitationVerificationError: If all retries fail.
        """
        last_error: Exception | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                # Rate limiting
                await asyncio.sleep(RATE_LIMIT_DELAY)

                response = await self.model.generate_content_async(prompt)
                return response.text

            except VerificationConfigurationError:
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
                        "gemini_rate_limited",
                        attempt=attempt + 1,
                        retry_delay=retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                elif not is_rate_limit:
                    break

        raise CitationVerificationError(
            f"Gemini API call failed after {MAX_RETRIES} attempts: {last_error}",
            code="GEMINI_API_ERROR",
        )

    def _parse_json_response(self, response_text: str) -> dict | None:
        """Parse JSON from Gemini response.

        Args:
            response_text: Raw response text.

        Returns:
            Parsed dict or None if parsing fails.
        """
        try:
            # Clean up response
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

            return json.loads(json_text)

        except json.JSONDecodeError as e:
            logger.warning(
                "json_parse_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            return None

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison.

        Args:
            text: Text to normalize.

        Returns:
            Normalized text.
        """
        # Lowercase
        normalized = text.lower()
        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized)
        # Remove punctuation variations
        normalized = re.sub(r"[''""\"']", "", normalized)
        return normalized.strip()

    def verify_citation_sync(
        self,
        citation: Citation,
        act_document_id: str,
        act_name: str = "Unknown Act",
    ) -> VerificationResult:
        """Synchronous wrapper for citation verification.

        For use in Celery tasks or other synchronous contexts.

        Args:
            citation: Citation to verify.
            act_document_id: UUID of the uploaded Act document.
            act_name: Display name of the Act.

        Returns:
            VerificationResult with status and explanation.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.verify_citation(citation, act_document_id, act_name)
            )
        finally:
            loop.close()


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_citation_verifier() -> CitationVerifier:
    """Get singleton citation verifier instance.

    Returns:
        CitationVerifier instance.
    """
    return CitationVerifier()
