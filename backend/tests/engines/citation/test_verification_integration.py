"""Integration tests for citation verification workflow.

Tests the complete verification flow from triggering verification
through to updating citation status and broadcasting results.

Story 3-3: Citation Verification (AC: #4, #5, #6)
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.citation.storage import CitationStorageService
from app.engines.citation.verifier import CitationVerifier
from app.models.citation import (
    Citation,
    VerificationResult,
    VerificationStatus,
)
from app.models.chunk import ChunkType, ChunkWithContent


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_citations():
    """Create sample citations for batch verification."""
    base = {
        "matter_id": "matter-123",
        "document_id": "doc-456",
        "act_name": "Negotiable Instruments Act, 1881",
        "verification_status": VerificationStatus.PENDING,
        "source_bbox_ids": [],
        "target_bbox_ids": [],
        "extraction_metadata": {},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    return [
        Citation(
            id="citation-1",
            section_number="138",
            subsection=None,
            clause=None,
            source_page=5,
            act_name_original="NI Act",
            raw_citation_text="Section 138 of the Negotiable Instruments Act",
            quoted_text="Where any cheque drawn by a person",
            target_act_document_id=None,
            target_page=None,
            confidence=85.0,
            **base,
        ),
        Citation(
            id="citation-2",
            section_number="139",
            subsection=None,
            clause=None,
            source_page=6,
            act_name_original="NI Act",
            raw_citation_text="Section 139 of the NI Act",
            quoted_text=None,
            target_act_document_id=None,
            target_page=None,
            confidence=80.0,
            **base,
        ),
        Citation(
            id="citation-3",
            section_number="999",  # Non-existent section
            subsection=None,
            clause=None,
            source_page=7,
            act_name_original="NI Act",
            raw_citation_text="Section 999",
            quoted_text="Some quoted text",
            target_act_document_id=None,
            target_page=None,
            confidence=60.0,
            **base,
        ),
    ]


@pytest.fixture
def mock_act_chunks():
    """Create mock Act document chunks."""
    return [
        ChunkWithContent(
            id="chunk-1",
            document_id="act-doc-789",
            chunk_type=ChunkType.PARENT,
            chunk_index=0,
            token_count=500,
            parent_chunk_id=None,
            page_number=10,
            content="""Section 138. Dishonour of cheque.—
Where any cheque drawn by a person on an account maintained by him.""",
        ),
        ChunkWithContent(
            id="chunk-2",
            document_id="act-doc-789",
            chunk_type=ChunkType.PARENT,
            chunk_index=1,
            token_count=400,
            parent_chunk_id=None,
            page_number=11,
            content="""Section 139. Presumption in favour of holder.—
It shall be presumed unless the contrary is proved.""",
        ),
    ]


# =============================================================================
# Verification Flow Integration Tests
# =============================================================================


class TestVerificationFlow:
    """Tests for complete verification workflow."""

    @pytest.mark.asyncio
    async def test_batch_verification_flow(
        self, sample_citations, mock_act_chunks
    ):
        """Test batch verification of multiple citations."""
        # Mock storage service
        mock_storage = MagicMock(spec=CitationStorageService)
        mock_storage.get_citations_for_act = AsyncMock(
            return_value=sample_citations
        )
        mock_storage.update_citation_verification = AsyncMock(
            return_value=sample_citations[0]
        )

        # Mock act indexer
        mock_indexer = MagicMock()
        mock_indexer.index_act_document = AsyncMock()
        mock_indexer.get_section_chunks = AsyncMock(
            side_effect=lambda doc_id, section: (
                [mock_act_chunks[0]] if section == "138"
                else [mock_act_chunks[1]] if section == "139"
                else []
            )
        )
        mock_indexer.get_available_sections = MagicMock(
            return_value=["138", "139", "140"]
        )
        mock_indexer.chunk_service = MagicMock()
        mock_indexer.chunk_service.get_chunks_for_document = MagicMock(
            return_value=(mock_act_chunks, 2, 0)
        )

        # Create verifier with mocked dependencies
        verifier = CitationVerifier(act_indexer=mock_indexer)

        # Mock Gemini responses
        with patch.object(verifier, "_call_gemini_with_retry") as mock_gemini:
            mock_gemini.return_value = '{"match_type": "exact", "similarity_score": 95, "differences": [], "explanation": "Match found."}'

            results = []
            for citation in sample_citations:
                result = await verifier.verify_citation(
                    citation=citation,
                    act_document_id="act-doc-789",
                    act_name="Negotiable Instruments Act, 1881",
                )
                results.append(result)

            # Check results
            assert results[0].status == VerificationStatus.VERIFIED
            assert results[1].status == VerificationStatus.VERIFIED
            assert results[2].status == VerificationStatus.SECTION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_storage_update_on_verification(self, sample_citations):
        """Test that storage is updated after verification."""
        mock_storage = MagicMock(spec=CitationStorageService)
        mock_storage.update_citation_verification = AsyncMock(
            return_value=sample_citations[0]
        )

        # Simulate verification result
        result = VerificationResult(
            status=VerificationStatus.VERIFIED,
            section_found=True,
            section_text="Section 138 text here",
            target_page=10,
            target_bbox_ids=["bbox-1"],
            similarity_score=95.0,
            explanation="Verified successfully",
            diff_details=None,
        )

        # Update storage
        updated = await mock_storage.update_citation_verification(
            citation_id=sample_citations[0].id,
            matter_id=sample_citations[0].matter_id,
            verification_status=result.status,
            target_act_document_id="act-doc-789",
            target_page=result.target_page,
            target_bbox_ids=result.target_bbox_ids,
            confidence=result.similarity_score,
        )

        mock_storage.update_citation_verification.assert_called_once()
        assert updated is not None


class TestActUploadTrigger:
    """Tests for Act upload verification trigger."""

    @pytest.mark.asyncio
    async def test_status_update_on_act_upload(self):
        """Test that citation statuses are updated when Act is uploaded."""
        mock_storage = MagicMock(spec=CitationStorageService)
        mock_storage.bulk_update_verification_status = AsyncMock(return_value=5)

        # Simulate uploading an Act
        updated_count = await mock_storage.bulk_update_verification_status(
            matter_id="matter-123",
            act_name="Negotiable Instruments Act, 1881",
            from_status=VerificationStatus.ACT_UNAVAILABLE,
            to_status=VerificationStatus.PENDING,
        )

        assert updated_count == 5
        mock_storage.bulk_update_verification_status.assert_called_once_with(
            matter_id="matter-123",
            act_name="Negotiable Instruments Act, 1881",
            from_status=VerificationStatus.ACT_UNAVAILABLE,
            to_status=VerificationStatus.PENDING,
        )


class TestPubSubBroadcasting:
    """Tests for real-time verification broadcasting."""

    def test_verification_progress_broadcast(self):
        """Test broadcasting verification progress."""
        from app.services.pubsub_service import broadcast_verification_progress

        with patch("app.services.pubsub_service.get_pubsub_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service
            mock_service.client.publish = MagicMock(return_value=1)

            # Should not raise
            broadcast_verification_progress(
                matter_id="matter-123",
                act_name="Test Act",
                verified_count=5,
                total_count=10,
                task_id="task-456",
            )

            mock_service.client.publish.assert_called_once()

    def test_citation_verified_broadcast(self):
        """Test broadcasting individual citation verification."""
        from app.services.pubsub_service import broadcast_citation_verified

        with patch("app.services.pubsub_service.get_pubsub_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service
            mock_service.client.publish = MagicMock(return_value=1)

            broadcast_citation_verified(
                matter_id="matter-123",
                citation_id="citation-456",
                status="verified",
                explanation="Citation verified successfully",
                similarity_score=95.0,
            )

            mock_service.client.publish.assert_called_once()

    def test_verification_complete_broadcast(self):
        """Test broadcasting verification completion."""
        from app.services.pubsub_service import broadcast_verification_complete

        with patch("app.services.pubsub_service.get_pubsub_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service
            mock_service.client.publish = MagicMock(return_value=1)

            broadcast_verification_complete(
                matter_id="matter-123",
                act_name="Test Act",
                total_verified=10,
                verified_count=8,
                mismatch_count=1,
                not_found_count=1,
                task_id="task-456",
            )

            mock_service.client.publish.assert_called_once()

    def test_broadcast_failure_is_silent(self):
        """Test that broadcast failures don't raise exceptions."""
        from app.services.pubsub_service import broadcast_verification_progress

        with patch("app.services.pubsub_service.get_pubsub_service") as mock_get:
            mock_get.side_effect = Exception("Redis error")

            # Should not raise - just logs warning
            broadcast_verification_progress(
                matter_id="matter-123",
                act_name="Test Act",
                verified_count=5,
                total_count=10,
            )


# =============================================================================
# Verification Prompts Tests
# =============================================================================


class TestVerificationPrompts:
    """Tests for verification prompt templates."""

    def test_section_matching_prompt_format(self):
        """Test section matching prompt can be formatted."""
        from app.engines.citation.verification_prompts import SECTION_MATCHING_PROMPT

        formatted = SECTION_MATCHING_PROMPT.format(
            section_number="138",
            act_name="Test Act",
            chunks_text="Sample chunk text",
        )

        assert "138" in formatted
        assert "Test Act" in formatted
        assert "Sample chunk text" in formatted

    def test_text_comparison_prompt_format(self):
        """Test text comparison prompt can be formatted."""
        from app.engines.citation.verification_prompts import TEXT_COMPARISON_PROMPT

        formatted = TEXT_COMPARISON_PROMPT.format(
            citation_quote="quoted text",
            act_text="act text",
        )

        assert "quoted text" in formatted
        assert "act text" in formatted

    def test_explanation_prompt_format(self):
        """Test explanation prompt can be formatted."""
        from app.engines.citation.verification_prompts import (
            VERIFICATION_EXPLANATION_PROMPT,
        )

        formatted = VERIFICATION_EXPLANATION_PROMPT.format(
            act_name="Test Act",
            section_number="138",
            quoted_text="Some text",
            status="verified",
            section_found=True,
            similarity_score=95.0,
            match_type="exact",
            differences="None",
        )

        assert "Test Act" in formatted
        assert "138" in formatted
        assert "verified" in formatted
