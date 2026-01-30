"""Hybrid citation extraction using regex + LLM (Instructor).

Two-stage approach:
1. Fast regex extraction (catches ~80% of citations)
2. LLM validation/extraction for ambiguous cases (handles edge cases)

Supports multiple LLM providers via Instructor:
- Gemini (cheapest, recommended)
- OpenAI (alternative)
"""

from typing import Optional

import structlog
import instructor
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.models import Citation, CitationExtractionResult, Chunk, BoundingBox
from .patterns import extract_citations_regex, CitationMatch
from .abbreviations import resolve_abbreviation

logger = structlog.get_logger(__name__)


def _create_instructor_client(provider: str = "gemini"):
    """Create Instructor client for the specified provider.

    Args:
        provider: "gemini" or "openai"

    Returns:
        Instructor-patched client
    """
    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        return instructor.from_gemini(
            client=genai.GenerativeModel(settings.extraction_model)
        )
    elif provider == "openai":
        from openai import OpenAI
        return instructor.from_openai(OpenAI(api_key=settings.openai_api_key))
    else:
        raise ValueError(f"Unknown provider: {provider}")


# =============================================================================
# Pydantic Models for Instructor
# =============================================================================

class ExtractedCitation(BaseModel):
    """Citation extracted by LLM."""
    act_name: str = Field(..., description="Full act name, e.g., 'Negotiable Instruments Act, 1881'")
    section: str = Field(..., description="Section number, e.g., '138'")
    subsection: Optional[str] = Field(None, description="Subsection if present, e.g., '(1)(a)'")
    raw_text: str = Field(..., description="Original text containing the citation")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score 0-1")


class LLMExtractionResult(BaseModel):
    """Result from LLM citation extraction."""
    citations: list[ExtractedCitation]


# =============================================================================
# Citation Extractor
# =============================================================================

class CitationExtractor:
    """Hybrid citation extractor using regex + LLM.

    Uses regex for fast extraction, then optionally validates
    with Instructor/Pydantic for structured output.

    Supports Gemini (cheapest) and OpenAI providers.
    """

    def __init__(
        self,
        provider: str = "gemini",
        model: Optional[str] = None,
        use_llm: bool = True,
    ):
        """Initialize citation extractor.

        Args:
            provider: LLM provider - "gemini" (cheapest) or "openai"
            model: Model name (uses config default if not provided)
            use_llm: Whether to use LLM validation (False = regex only)
        """
        self.provider = provider or settings.extraction_provider
        self.model = model or settings.extraction_model
        self.use_llm = use_llm
        self.client = None

        # Check if we have the required API key
        if self.use_llm:
            has_key = (
                (self.provider == "gemini" and settings.google_api_key) or
                (self.provider == "openai" and settings.openai_api_key)
            )
            if has_key:
                try:
                    self.client = _create_instructor_client(self.provider)
                except Exception as e:
                    logger.warning("llm_client_init_failed", error=str(e))
                    self.client = None

        logger.info(
            "citation_extractor_initialized",
            provider=self.provider,
            model=self.model,
            use_llm=use_llm and self.client is not None,
        )

    def extract(
        self,
        text: str,
        source_chunk: Optional[Chunk] = None,
    ) -> CitationExtractionResult:
        """Extract citations from text.

        Args:
            text: Text to extract citations from
            source_chunk: Optional source chunk for grounding

        Returns:
            CitationExtractionResult with list of citations
        """
        # Stage 1: Regex extraction
        regex_matches = extract_citations_regex(text)

        logger.debug(
            "regex_extraction_complete",
            matches=len(regex_matches),
        )

        # Convert regex matches to Citation objects
        citations = []
        for match in regex_matches:
            citation = self._match_to_citation(match, source_chunk)
            if citation:
                citations.append(citation)

        # Stage 2: LLM validation/extraction (optional)
        if self.use_llm and self.client and len(text) > 50:
            llm_citations = self._extract_with_llm(text, source_chunk)

            # Merge LLM results (add new citations not found by regex)
            citations = self._merge_citations(citations, llm_citations)

        return CitationExtractionResult(
            citations=citations,
            extraction_method="hybrid" if self.use_llm else "regex",
        )

    def extract_from_chunks(
        self,
        chunks: list[Chunk],
    ) -> CitationExtractionResult:
        """Extract citations from multiple chunks.

        Args:
            chunks: List of document chunks

        Returns:
            Combined CitationExtractionResult
        """
        all_citations = []

        for chunk in chunks:
            result = self.extract(chunk.text, source_chunk=chunk)
            all_citations.extend(result.citations)

        # Deduplicate
        unique_citations = self._deduplicate(all_citations)

        return CitationExtractionResult(
            citations=unique_citations,
            extraction_method="hybrid" if self.use_llm else "regex",
        )

    def _match_to_citation(
        self,
        match: CitationMatch,
        source_chunk: Optional[Chunk] = None,
    ) -> Optional[Citation]:
        """Convert regex match to Citation object."""
        if not match.section or not match.act_name:
            return None

        # Resolve abbreviations
        canonical_act = resolve_abbreviation(match.act_name)

        return Citation(
            act_name=canonical_act,
            section=match.section,
            subsection=match.subsection,
            raw_text=match.raw_text,
            source_chunk_id=source_chunk.chunk_id if source_chunk else None,
            source_page=source_chunk.page if source_chunk else None,
            source_bbox=source_chunk.bbox if source_chunk else None,
            confidence=0.85,  # Regex matches have good confidence
            extraction_method="regex",
        )

    def _extract_with_llm(
        self,
        text: str,
        source_chunk: Optional[Chunk] = None,
    ) -> list[Citation]:
        """Extract citations using LLM (Instructor with Gemini or OpenAI)."""
        try:
            prompt = """You are an expert at extracting Indian legal citations.
Extract ALL legal citations from the text, including:
- Section references (Section 138, S. 302, u/s 420)
- Article references (Article 21, Art. 14)
- Rule references (Rule 3, Order XXI Rule 97)
- Both old acts (IPC, CrPC) and new Bharatiya codes (BNS, BNSS, BSA)

Return the full canonical act name with year when possible.
If act year is not mentioned, use the most common year for that act.

Text to analyze:
""" + text[:3000]

            # Gemini uses different API structure
            if self.provider == "gemini":
                result = self.client.messages.create(
                    response_model=LLMExtractionResult,
                    messages=[{"role": "user", "content": prompt}],
                )
            else:
                # OpenAI style
                result = self.client.chat.completions.create(
                    model=self.model,
                    response_model=LLMExtractionResult,
                    messages=[
                        {"role": "system", "content": "You are an expert at extracting Indian legal citations."},
                        {"role": "user", "content": f"Extract all legal citations from this text:\n\n{text[:3000]}"}
                    ],
                    max_tokens=1000,
                )

            citations = []
            for extracted in result.citations:
                citation = Citation(
                    act_name=resolve_abbreviation(extracted.act_name),
                    section=extracted.section,
                    subsection=extracted.subsection,
                    raw_text=extracted.raw_text,
                    source_chunk_id=source_chunk.chunk_id if source_chunk else None,
                    source_page=source_chunk.page if source_chunk else None,
                    source_bbox=source_chunk.bbox if source_chunk else None,
                    confidence=extracted.confidence,
                    extraction_method="llm",
                )
                citations.append(citation)

            logger.debug(
                "llm_extraction_complete",
                citations=len(citations),
            )

            return citations

        except Exception as e:
            logger.error("llm_extraction_failed", error=str(e))
            return []

    def _merge_citations(
        self,
        regex_citations: list[Citation],
        llm_citations: list[Citation],
    ) -> list[Citation]:
        """Merge citations from regex and LLM, avoiding duplicates."""
        merged = list(regex_citations)
        existing_keys = {
            (c.act_name.lower(), c.section, c.subsection or "")
            for c in regex_citations
        }

        for llm_cit in llm_citations:
            key = (llm_cit.act_name.lower(), llm_cit.section, llm_cit.subsection or "")
            if key not in existing_keys:
                merged.append(llm_cit)
                existing_keys.add(key)

        return merged

    def _deduplicate(self, citations: list[Citation]) -> list[Citation]:
        """Remove duplicate citations."""
        seen = set()
        unique = []

        for cit in citations:
            key = (cit.act_name.lower(), cit.section, cit.subsection or "")
            if key not in seen:
                seen.add(key)
                unique.append(cit)

        return unique


def extract_citations(
    text: str,
    use_llm: bool = True,
    source_chunk: Optional[Chunk] = None,
) -> CitationExtractionResult:
    """Convenience function to extract citations.

    Args:
        text: Text to extract from
        use_llm: Whether to use LLM validation
        source_chunk: Optional source chunk for grounding

    Returns:
        CitationExtractionResult
    """
    extractor = CitationExtractor(use_llm=use_llm)
    return extractor.extract(text, source_chunk)
