"""Unit tests for CitationVerifier service.

Tests verification of citations against Act documents.

Story 3-3: Citation Verification (AC: #1, #2, #3)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.citation.verifier import (
    CitationVerifier,
    VerificationConfigurationError,
    get_citation_verifier,
)
from app.models.chunk import ChunkType, ChunkWithContent
from app.models.citation import (
    Citation,
    VerificationResult,
    VerificationStatus,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_citation():
    """Create a mock citation for testing."""
    return Citation(
        id="citation-123",
        matter_id="matter-456",
        document_id="doc-789",
        act_name="Negotiable Instruments Act, 1881",
        section_number="138",
        subsection=None,
        clause=None,
        source_page=5,
        source_bbox_ids=[],
        act_name_original="NI Act",
        raw_citation_text="Section 138 of the Negotiable Instruments Act",
        quoted_text="Where any cheque drawn by a person on an account",
        verification_status=VerificationStatus.PENDING,
        target_act_document_id=None,
        target_page=None,
        target_bbox_ids=[],
        confidence=85.0,
        extraction_metadata={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_chunks():
    """Create mock Act document chunks."""
    return [
        ChunkWithContent(
            id="chunk-1",
            document_id="act-doc-123",
            chunk_type=ChunkType.PARENT,
            chunk_index=0,
            token_count=500,
            parent_chunk_id=None,
            page_number=10,
            content="""Section 138. Dishonour of cheque for insufficiency, etc., of funds in the account.—
Where any cheque drawn by a person on an account maintained by him with a banker
for payment of any amount of money to another person from out of that account for
the discharge, in whole or in part, of any debt or other liability, is returned by
the bank unpaid, either because of the amount of money standing to the credit of
that account is insufficient to honour the cheque or that it exceeds the amount
arranged to be paid from that account by an agreement made with that bank, such
person shall be deemed to have committed an offence and shall, without prejudice
to any other provision of this Act, be punished with imprisonment for a term which
may extend to two years, or with fine which may extend to twice the amount of the
cheque, or with both.""",
        ),
        ChunkWithContent(
            id="chunk-2",
            document_id="act-doc-123",
            chunk_type=ChunkType.PARENT,
            chunk_index=1,
            token_count=400,
            parent_chunk_id=None,
            page_number=11,
            content="""Section 139. Presumption in favour of holder.—
It shall be presumed, unless the contrary is proved, that the holder of a cheque
received the cheque of the nature referred to in section 138 for the discharge, in
whole or in part, of any debt or other liability.""",
        ),
    ]


@pytest.fixture
def mock_act_indexer():
    """Create a mock ActIndexer."""
    indexer = MagicMock()
    indexer.index_act_document = AsyncMock()
    indexer.get_section_chunks = AsyncMock()
    indexer.get_available_sections = MagicMock(return_value=["138", "139", "140"])
    indexer.chunk_service = MagicMock()
    return indexer


# =============================================================================
# CitationVerifier Tests
# =============================================================================


class TestCitationVerifier:
    """Tests for CitationVerifier class."""

    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with patch("app.engines.citation.verifier.get_settings") as mock_settings:
            mock_settings.return_value.gemini_api_key = None
            mock_settings.return_value.gemini_model = "gemini-2.0-flash"

            verifier = CitationVerifier()

            with pytest.raises(VerificationConfigurationError) as exc_info:
                _ = verifier.model

            assert "API key not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_citation_section_found_exact_match(
        self, mock_citation, mock_chunks, mock_act_indexer
    ):
        """Test verification with exact text match."""
        mock_act_indexer.get_section_chunks.return_value = [mock_chunks[0]]

        verifier = CitationVerifier(act_indexer=mock_act_indexer)

        # Mock the Gemini model
        with patch.object(verifier, "_call_gemini_with_retry") as mock_gemini:
            # Mock comparison response
            mock_gemini.return_value = '{"match_type": "exact", "similarity_score": 98, "differences": [], "explanation": "Text matches exactly."}'

            # Set up the model mock
            verifier._model = MagicMock()
            verifier._model.generate_content_async = AsyncMock()

            result = await verifier.verify_citation(
                citation=mock_citation,
                act_document_id="act-doc-123",
                act_name="Negotiable Instruments Act, 1881",
            )

            assert result.status == VerificationStatus.VERIFIED
            assert result.section_found is True
            assert result.section_text is not None
            assert result.target_page == 10
            assert result.similarity_score >= 90.0

    @pytest.mark.asyncio
    async def test_verify_citation_section_not_found(
        self, mock_citation, mock_act_indexer
    ):
        """Test verification when section is not found."""
        mock_act_indexer.get_section_chunks.return_value = []
        mock_act_indexer.chunk_service.get_chunks_for_document = MagicMock(
            return_value=([], 0, 0)
        )

        verifier = CitationVerifier(act_indexer=mock_act_indexer)

        # Mock Gemini for explanation generation
        with patch.object(verifier, "_call_gemini_with_retry") as mock_gemini:
            mock_gemini.return_value = '{"found": false, "section_number": null, "section_text": null, "chunk_id": null, "confidence": 0, "closest_match": "138(1)", "explanation": "Section not found"}'

            result = await verifier.verify_citation(
                citation=mock_citation,
                act_document_id="act-doc-123",
                act_name="Negotiable Instruments Act, 1881",
            )

            assert result.status == VerificationStatus.SECTION_NOT_FOUND
            assert result.section_found is False
            assert result.similarity_score == 0.0
            assert "not found" in result.explanation.lower()

    @pytest.mark.asyncio
    async def test_verify_citation_mismatch(
        self, mock_citation, mock_chunks, mock_act_indexer
    ):
        """Test verification with text mismatch."""
        mock_citation.quoted_text = "imprisonment of not less than one year"
        mock_act_indexer.get_section_chunks.return_value = [mock_chunks[0]]

        verifier = CitationVerifier(act_indexer=mock_act_indexer)

        with patch.object(verifier, "_call_gemini_with_retry") as mock_gemini:
            # Mock mismatch response
            mock_gemini.return_value = '{"match_type": "mismatch", "similarity_score": 45, "differences": ["Citation claims imprisonment of not less than one year but Act states may extend to two years"], "explanation": "Significant mismatch in punishment term."}'

            result = await verifier.verify_citation(
                citation=mock_citation,
                act_document_id="act-doc-123",
                act_name="Negotiable Instruments Act, 1881",
            )

            assert result.status == VerificationStatus.MISMATCH
            assert result.section_found is True
            assert result.similarity_score < 70.0
            assert result.diff_details is not None
            assert result.diff_details.match_type == "mismatch"

    @pytest.mark.asyncio
    async def test_verify_citation_paraphrase(
        self, mock_citation, mock_chunks, mock_act_indexer
    ):
        """Test verification with paraphrased text (still verified)."""
        mock_citation.quoted_text = "shall be punished with imprisonment for two years"
        mock_act_indexer.get_section_chunks.return_value = [mock_chunks[0]]

        verifier = CitationVerifier(act_indexer=mock_act_indexer)

        with patch.object(verifier, "_call_gemini_with_retry") as mock_gemini:
            mock_gemini.return_value = '{"match_type": "paraphrase", "similarity_score": 88, "differences": ["Minor wording differences"], "explanation": "Text is paraphrased but meaning preserved."}'

            result = await verifier.verify_citation(
                citation=mock_citation,
                act_document_id="act-doc-123",
                act_name="Negotiable Instruments Act, 1881",
            )

            # Paraphrase should still be VERIFIED
            assert result.status == VerificationStatus.VERIFIED
            assert result.section_found is True
            assert result.similarity_score > 70.0

    @pytest.mark.asyncio
    async def test_verify_citation_no_quoted_text(
        self, mock_citation, mock_chunks, mock_act_indexer
    ):
        """Test verification without quoted text (section-only verification)."""
        mock_citation.quoted_text = None
        mock_act_indexer.get_section_chunks.return_value = [mock_chunks[0]]

        verifier = CitationVerifier(act_indexer=mock_act_indexer)

        with patch.object(verifier, "_call_gemini_with_retry") as mock_gemini:
            mock_gemini.return_value = '{"explanation": "Section 138 verified."}'

            result = await verifier.verify_citation(
                citation=mock_citation,
                act_document_id="act-doc-123",
                act_name="Negotiable Instruments Act, 1881",
            )

            # Should be verified if section is found
            assert result.status == VerificationStatus.VERIFIED
            assert result.section_found is True
            assert result.similarity_score == 100.0  # Default for section-only

    def test_normalize_text(self):
        """Test text normalization for comparison."""
        verifier = CitationVerifier()

        # Test basic normalization
        assert verifier._normalize_text("Hello  World") == "hello world"
        assert verifier._normalize_text("  Spaces  ") == "spaces"
        assert verifier._normalize_text("Quote's") == "quotes"
        assert verifier._normalize_text('"Text"') == "text"

    def test_parse_json_response(self):
        """Test JSON response parsing."""
        verifier = CitationVerifier()

        # Valid JSON
        result = verifier._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

        # JSON with markdown code blocks
        result = verifier._parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

        # Invalid JSON
        result = verifier._parse_json_response("not json")
        assert result is None

    def test_sync_wrapper(self, mock_citation, mock_act_indexer):
        """Test synchronous wrapper method."""
        mock_act_indexer.get_section_chunks.return_value = []
        mock_act_indexer.chunk_service.get_chunks_for_document = MagicMock(
            return_value=([], 0, 0)
        )

        verifier = CitationVerifier(act_indexer=mock_act_indexer)

        result = verifier.verify_citation_sync(
            citation=mock_citation,
            act_document_id="act-doc-123",
            act_name="Test Act",
        )

        # Should return a valid result even if section not found
        assert isinstance(result, VerificationResult)


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestVerifierFactory:
    """Tests for verifier factory function."""

    def test_get_citation_verifier_singleton(self):
        """Test that factory returns singleton instance."""
        # Clear the cache
        get_citation_verifier.cache_clear()

        verifier1 = get_citation_verifier()
        verifier2 = get_citation_verifier()

        assert verifier1 is verifier2
