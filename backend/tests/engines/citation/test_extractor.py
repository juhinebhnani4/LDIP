"""Tests for Citation Extractor service.

Story 3-1: Act Citation Extraction (AC: #1, #2)
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.citation.extractor import (
    CITATION_PATTERNS,
    CitationConfigurationError,
    CitationExtractor,
    CitationExtractorError,
    get_citation_extractor,
)
from app.models.citation import ExtractedCitation


class TestCitationExtractorRegex:
    """Tests for regex-based citation extraction."""

    def test_section_of_act_pattern(self) -> None:
        """Should extract 'Section X of Act' pattern."""
        extractor = CitationExtractor()
        text = "Section 138 of the Negotiable Instruments Act, 1881 was invoked."

        citations = extractor._extract_with_regex(text)

        assert len(citations) >= 1
        citation = citations[0]
        assert citation.section == "138"
        assert "Negotiable Instruments Act" in citation.act_name

    def test_abbreviated_section_pattern(self) -> None:
        """Should extract 'S. X' abbreviation pattern."""
        extractor = CitationExtractor()
        # Note: Regex requires act name to end with "Act" or "Code"
        text = "S. 420 of Indian Penal Code applies here."

        citations = extractor._extract_with_regex(text)

        assert len(citations) >= 1
        citation = citations[0]
        assert citation.section == "420"

    def test_us_pattern(self) -> None:
        """Should extract 'u/s X' pattern."""
        extractor = CitationExtractor()
        text = "The charge u/s 302 of IPC was filed."

        citations = extractor._extract_with_regex(text)

        assert len(citations) >= 1
        citation = citations[0]
        assert citation.section == "302"

    def test_section_with_subsection(self) -> None:
        """Should extract section with subsection."""
        extractor = CitationExtractor()
        text = "Section 138(1) of the NI Act is applicable."

        citations = extractor._extract_with_regex(text)

        assert len(citations) >= 1
        citation = citations[0]
        assert citation.section == "138"
        assert citation.subsection == "(1)"

    def test_section_with_clause(self) -> None:
        """Should extract section with clause."""
        extractor = CitationExtractor()
        text = "Section 138(1)(a) of the NI Act was cited."

        citations = extractor._extract_with_regex(text)

        assert len(citations) >= 1
        citation = citations[0]
        assert citation.section == "138"
        assert citation.subsection == "(1)"
        assert citation.clause == "(a)"

    def test_multiple_citations(self) -> None:
        """Should extract multiple citations from text."""
        extractor = CitationExtractor()
        # Note: Regex requires act name to end with "Act" or "Code"
        text = """
        Section 138 of NI Act and Section 420 of Indian Penal Code
        were both considered in this case.
        """

        citations = extractor._extract_with_regex(text)

        assert len(citations) >= 2
        sections = {c.section for c in citations}
        assert "138" in sections
        assert "420" in sections

    def test_regex_confidence(self) -> None:
        """Regex citations should have appropriate confidence."""
        extractor = CitationExtractor()
        # Note: Regex requires act name to end with "Act" or "Code"
        text = "Section 302 of Indian Penal Code was charged."

        citations = extractor._extract_with_regex(text)

        assert len(citations) >= 1
        assert citations[0].confidence == 75.0

    def test_no_citations_in_text(self) -> None:
        """Should return empty list for text without citations."""
        extractor = CitationExtractor()
        text = "This is a general paragraph without any legal citations."

        citations = extractor._extract_with_regex(text)

        assert len(citations) == 0


class TestCitationExtractorGeminiParsing:
    """Tests for Gemini response parsing."""

    def test_parse_valid_json_response(self) -> None:
        """Should parse valid JSON response."""
        extractor = CitationExtractor()
        response = json.dumps({
            "citations": [
                {
                    "act_name": "Negotiable Instruments Act",
                    "section": "138",
                    "subsection": "(1)",
                    "raw_text": "Section 138(1) of NI Act",
                    "confidence": 90,
                }
            ]
        })

        citations = extractor._parse_gemini_response(response)

        assert len(citations) == 1
        assert citations[0].act_name == "Negotiable Instruments Act"
        assert citations[0].section == "138"
        assert citations[0].confidence == 90.0

    def test_parse_json_with_markdown_blocks(self) -> None:
        """Should parse JSON wrapped in markdown code blocks."""
        extractor = CitationExtractor()
        response = """```json
{
    "citations": [
        {
            "act_name": "IPC",
            "section": "302",
            "raw_text": "Section 302 of IPC",
            "confidence": 85
        }
    ]
}
```"""

        citations = extractor._parse_gemini_response(response)

        assert len(citations) == 1
        assert citations[0].section == "302"

    def test_parse_empty_citations(self) -> None:
        """Should handle empty citations array."""
        extractor = CitationExtractor()
        response = json.dumps({"citations": []})

        citations = extractor._parse_gemini_response(response)

        assert len(citations) == 0

    def test_parse_invalid_json(self) -> None:
        """Should return empty list for invalid JSON."""
        extractor = CitationExtractor()
        response = "This is not valid JSON"

        citations = extractor._parse_gemini_response(response)

        assert len(citations) == 0

    def test_parse_missing_required_fields(self) -> None:
        """Should skip citations missing act_name or section."""
        extractor = CitationExtractor()
        response = json.dumps({
            "citations": [
                {"act_name": "IPC"},  # Missing section
                {"section": "302"},  # Missing act_name
                {"act_name": "NI Act", "section": "138", "raw_text": "test"},  # Valid
            ]
        })

        citations = extractor._parse_gemini_response(response)

        assert len(citations) == 1
        assert citations[0].act_name == "NI Act"


class TestCitationMerging:
    """Tests for citation deduplication and merging."""

    def test_merge_deduplicates(self) -> None:
        """Should deduplicate identical citations."""
        extractor = CitationExtractor()

        regex_citations = [
            ExtractedCitation(
                act_name="NI Act",
                section="138",
                raw_text="Section 138 NI Act",
                confidence=75.0,
            )
        ]

        gemini_citations = [
            ExtractedCitation(
                act_name="Negotiable Instruments Act",
                section="138",
                raw_text="Section 138 of NI Act",
                confidence=90.0,
            )
        ]

        merged = extractor._merge_citations(regex_citations, gemini_citations)

        # Should deduplicate based on normalized act name
        assert len(merged) == 1
        # Gemini citation preferred (added first)
        assert merged[0].confidence == 90.0

    def test_merge_keeps_unique(self) -> None:
        """Should keep unique citations from both sources."""
        extractor = CitationExtractor()

        regex_citations = [
            ExtractedCitation(
                act_name="IPC",
                section="302",
                raw_text="Section 302 IPC",
                confidence=75.0,
            )
        ]

        gemini_citations = [
            ExtractedCitation(
                act_name="NI Act",
                section="138",
                raw_text="Section 138 NI Act",
                confidence=90.0,
            )
        ]

        merged = extractor._merge_citations(regex_citations, gemini_citations)

        assert len(merged) == 2

    def test_merge_prefers_gemini(self) -> None:
        """Should prefer Gemini citations over regex for same citation."""
        extractor = CitationExtractor()

        regex_citations = [
            ExtractedCitation(
                act_name="NI Act",
                section="138",
                raw_text="S. 138 NI Act",
                confidence=75.0,
                quoted_text=None,
            )
        ]

        gemini_citations = [
            ExtractedCitation(
                act_name="Negotiable Instruments Act",
                section="138",
                raw_text="Section 138 of the Negotiable Instruments Act",
                confidence=92.0,
                quoted_text="The drawer shall be punished...",
            )
        ]

        merged = extractor._merge_citations(regex_citations, gemini_citations)

        assert len(merged) == 1
        assert merged[0].quoted_text == "The drawer shall be punished..."


class TestGetUniqueActs:
    """Tests for unique acts extraction."""

    def test_get_unique_acts_canonical(self) -> None:
        """Should use canonical names when available."""
        extractor = CitationExtractor()

        citations = [
            ExtractedCitation(act_name="NI Act", section="138", raw_text="", confidence=80),
            ExtractedCitation(act_name="NI Act", section="139", raw_text="", confidence=80),
        ]

        unique_acts = extractor._get_unique_acts(citations)

        assert len(unique_acts) == 1
        assert "Negotiable Instruments Act, 1881" in unique_acts[0]

    def test_get_unique_acts_multiple(self) -> None:
        """Should return multiple unique acts."""
        extractor = CitationExtractor()

        citations = [
            ExtractedCitation(act_name="NI Act", section="138", raw_text="", confidence=80),
            ExtractedCitation(act_name="IPC", section="420", raw_text="", confidence=80),
            ExtractedCitation(act_name="CrPC", section="200", raw_text="", confidence=80),
        ]

        unique_acts = extractor._get_unique_acts(citations)

        assert len(unique_acts) == 3

    def test_get_unique_acts_preserves_unknown(self) -> None:
        """Should preserve unknown act names as-is."""
        extractor = CitationExtractor()

        citations = [
            ExtractedCitation(
                act_name="Custom Local Act 2020",
                section="5",
                raw_text="",
                confidence=80,
            ),
        ]

        unique_acts = extractor._get_unique_acts(citations)

        assert len(unique_acts) == 1
        assert "Custom Local Act 2020" in unique_acts[0]


class TestCitationExtractorAsync:
    """Tests for async extraction methods."""

    @pytest.mark.asyncio
    async def test_extract_from_empty_text(self) -> None:
        """Should handle empty text gracefully."""
        extractor = CitationExtractor()

        result = await extractor.extract_from_text(
            text="",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert len(result.citations) == 0
        assert len(result.unique_acts) == 0
        assert result.source_document_id == "doc-123"

    @pytest.mark.asyncio
    async def test_extract_from_whitespace_text(self) -> None:
        """Should handle whitespace-only text."""
        extractor = CitationExtractor()

        result = await extractor.extract_from_text(
            text="   \n\t   ",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert len(result.citations) == 0

    @pytest.mark.asyncio
    async def test_extract_includes_metadata(self) -> None:
        """Should include metadata in extraction result."""
        with patch.object(
            CitationExtractor,
            "_extract_with_gemini",
            new_callable=AsyncMock,
            return_value=[],
        ):
            extractor = CitationExtractor()

            result = await extractor.extract_from_text(
                text="Section 138 of NI Act",
                document_id="doc-123",
                matter_id="matter-456",
                page_number=5,
                chunk_id="chunk-789",
            )

            assert result.source_document_id == "doc-123"
            assert result.source_chunk_id == "chunk-789"
            assert result.page_number == 5
            assert result.extraction_timestamp is not None


class TestCitationExtractorSync:
    """Tests for sync extraction methods."""

    def test_sync_extract_from_empty_text(self) -> None:
        """Should handle empty text in sync mode."""
        extractor = CitationExtractor()

        result = extractor.extract_from_text_sync(
            text="",
            document_id="doc-123",
            matter_id="matter-456",
        )

        assert len(result.citations) == 0

    def test_sync_extract_with_regex_only(self) -> None:
        """Should extract with regex when Gemini fails."""
        with patch.object(
            CitationExtractor,
            "_extract_with_gemini_sync",
            return_value=[],
        ):
            extractor = CitationExtractor()

            # Note: Regex requires act name to end with "Act" or "Code"
            result = extractor.extract_from_text_sync(
                text="Section 302 of Indian Penal Code was charged.",
                document_id="doc-123",
                matter_id="matter-456",
            )

            # Should still have regex results
            assert len(result.citations) >= 1


class TestCitationConfigurationError:
    """Tests for configuration error handling."""

    def test_raises_on_missing_api_key(self) -> None:
        """Should raise error when API key not configured."""
        with patch("app.engines.citation.extractor.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = None
            mock_settings.return_value.gemini_model = "gemini-2.0-flash"

            extractor = CitationExtractor()

            with pytest.raises(CitationConfigurationError) as exc_info:
                _ = extractor.model

            assert "API key not configured" in str(exc_info.value)
            assert not exc_info.value.is_retryable


class TestCitationPatterns:
    """Tests for regex pattern coverage."""

    def test_patterns_list_not_empty(self) -> None:
        """Should have defined citation patterns."""
        assert len(CITATION_PATTERNS) > 0

    def test_patterns_are_compiled(self) -> None:
        """All patterns should be compiled regex objects."""
        import re

        for pattern in CITATION_PATTERNS:
            assert isinstance(pattern, re.Pattern)

    def test_case_insensitive_patterns(self) -> None:
        """Patterns should be case insensitive."""
        extractor = CitationExtractor()

        test_cases = [
            "SECTION 138 of NI Act",
            "section 138 of ni act",
            "Section 138 of NI Act",
        ]

        for text in test_cases:
            citations = extractor._extract_with_regex(text)
            assert len(citations) >= 1, f"Failed for: {text}"


class TestGetCitationExtractor:
    """Tests for factory function."""

    def test_returns_singleton(self) -> None:
        """Should return same instance on multiple calls."""
        # Clear cache first
        get_citation_extractor.cache_clear()

        extractor1 = get_citation_extractor()
        extractor2 = get_citation_extractor()

        assert extractor1 is extractor2

    def test_returns_extractor_instance(self) -> None:
        """Should return CitationExtractor instance."""
        get_citation_extractor.cache_clear()

        extractor = get_citation_extractor()

        assert isinstance(extractor, CitationExtractor)
