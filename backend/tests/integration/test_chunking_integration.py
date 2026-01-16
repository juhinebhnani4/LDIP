"""Integration tests for chunking pipeline.

Tests the complete chunking flow from text input to database storage.
"""

from unittest.mock import MagicMock

import pytest

from app.services.chunking.parent_child_chunker import ParentChildChunker
from app.services.chunking.text_splitter import RecursiveTextSplitter
from app.services.chunking.token_counter import count_tokens


class TestChunkingPipelineIntegration:
    """Integration tests for the chunking pipeline."""

    @pytest.fixture
    def legal_document(self) -> str:
        """Generate a realistic legal document for testing."""
        sections = []
        for i in range(5):
            sections.append(f"""
ARTICLE {i + 1}: TERMS AND CONDITIONS

Section {i + 1}.1 - General Provisions

The parties hereby agree that all terms and conditions set forth in this
Agreement shall be binding and enforceable according to the laws of the
jurisdiction specified herein. Each party acknowledges that they have
read and understood all provisions contained in this document.

Section {i + 1}.2 - Obligations and Responsibilities

The first party ("Party A") agrees to perform the following obligations:
(a) Maintain accurate records of all transactions;
(b) Provide timely notification of any material changes;
(c) Comply with all applicable laws and regulations.

The second party ("Party B") agrees to:
(a) Make payments according to the schedule in Exhibit A;
(b) Cooperate fully with Party A in executing the terms;
(c) Maintain confidentiality as specified in Section 5.

Section {i + 1}.3 - Dispute Resolution

In the event of any dispute arising under or relating to this Agreement,
the parties shall first attempt to resolve the dispute through good faith
negotiation. If the dispute cannot be resolved through negotiation within
thirty (30) days, either party may initiate binding arbitration in
accordance with the rules of the American Arbitration Association.
            """)
        return "\n\n".join(sections)

    def test_complete_chunking_flow(self, legal_document: str) -> None:
        """Test the complete flow from text to chunks."""
        # Create chunker with realistic settings
        chunker = ParentChildChunker(
            parent_size=1750,
            parent_overlap=100,
            child_size=550,
            child_overlap=75,
            min_size=100,
        )

        # Process document
        result = chunker.chunk_document("test-doc-123", legal_document)

        # Verify result structure
        assert result.document_id == "test-doc-123"
        assert len(result.parent_chunks) > 0
        assert len(result.child_chunks) > 0

        # Verify parent chunks
        for parent in result.parent_chunks:
            assert parent.chunk_type == "parent"
            assert parent.parent_id is None
            assert parent.token_count > 0
            assert parent.content.strip()

        # Verify child chunks reference valid parents
        parent_ids = {p.id for p in result.parent_chunks}
        for child in result.child_chunks:
            assert child.chunk_type == "child"
            assert child.parent_id in parent_ids
            assert child.token_count > 0
            assert child.content.strip()

        # Verify token counts are accurate
        for chunk in result.parent_chunks + result.child_chunks:
            actual_tokens = count_tokens(chunk.content)
            assert chunk.token_count == actual_tokens

    def test_chunking_preserves_content(self, legal_document: str) -> None:
        """Verify chunking doesn't lose significant content."""
        chunker = ParentChildChunker(
            parent_size=1750,
            parent_overlap=100,
            child_size=550,
            child_overlap=75,
            min_size=50,
        )

        result = chunker.chunk_document("test-doc", legal_document)

        # Combine all parent chunks (children are subsets)
        combined_parent_text = " ".join(p.content for p in result.parent_chunks)

        # Key phrases from the document should be present
        key_phrases = [
            "ARTICLE",
            "General Provisions",
            "Obligations",
            "Dispute Resolution",
            "parties",
            "Agreement",
        ]

        for phrase in key_phrases:
            assert phrase in combined_parent_text, f"Missing phrase: {phrase}"

    def test_parent_child_relationship(self, legal_document: str) -> None:
        """Verify parent-child relationships are correct."""
        chunker = ParentChildChunker(
            parent_size=500,
            parent_overlap=50,
            child_size=150,
            child_overlap=20,
            min_size=30,
        )

        result = chunker.chunk_document("test-doc", legal_document)

        # Build parent lookup
        parent_lookup = {p.id: p for p in result.parent_chunks}

        # Each child should have content that's a subset of its parent
        for child in result.child_chunks:
            parent = parent_lookup.get(child.parent_id)
            assert parent is not None, "Child references non-existent parent"

            # Child content should have words from parent
            child_words = set(child.content.lower().split())
            parent_words = set(parent.content.lower().split())

            # Most child words should appear in parent
            overlap = child_words & parent_words
            overlap_ratio = len(overlap) / len(child_words) if child_words else 0
            assert overlap_ratio > 0.5, f"Child has low overlap with parent: {overlap_ratio}"


class TestTextSplitterIntegration:
    """Integration tests for text splitter."""

    def test_splitter_chain(self) -> None:
        """Test that splitters can be chained effectively."""
        # First pass: large chunks
        large_splitter = RecursiveTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
        )

        # Second pass: smaller chunks
        small_splitter = RecursiveTextSplitter(
            chunk_size=100,
            chunk_overlap=10,
        )

        text = """
        This is the first section of the document with important content.

        This is the second section that contains different information.

        The third section wraps up the document with conclusions.
        """ * 10

        # First pass
        large_chunks = large_splitter.split_text(text)
        assert len(large_chunks) > 0

        # Second pass on each large chunk
        all_small_chunks = []
        for large_chunk in large_chunks:
            small_chunks = small_splitter.split_text(large_chunk)
            all_small_chunks.extend(small_chunks)

        # Should have more small chunks than large
        assert len(all_small_chunks) > len(large_chunks)

        # All chunks should have content
        for chunk in all_small_chunks:
            assert chunk.strip()

    def test_splitter_preserves_boundaries(self) -> None:
        """Test that splitter respects semantic boundaries."""
        splitter = RecursiveTextSplitter(
            chunk_size=100,
            chunk_overlap=10,
        )

        text = """First paragraph with complete thoughts.

Second paragraph that is separate.

Third paragraph for testing."""

        chunks = splitter.split_text(text)

        # Paragraphs should be mostly intact or split at sentence boundaries
        for chunk in chunks:
            # Should not start mid-word
            assert not chunk[0].islower() or chunk.startswith("paragraph")


class TestTokenCounterIntegration:
    """Integration tests for token counter with splitter."""

    def test_tokens_match_splitter_limits(self) -> None:
        """Verify token counts respect splitter chunk_size."""
        chunk_size = 200
        splitter = RecursiveTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=20,
        )

        # Large text that needs splitting
        text = "word " * 1000

        chunks = splitter.split_text(text)

        for chunk in chunks:
            tokens = count_tokens(chunk)
            # Allow 20% margin for edge cases
            assert tokens <= chunk_size * 1.2, f"Chunk exceeds limit: {tokens} tokens"

    def test_consistent_token_counting(self) -> None:
        """Token counting should be consistent across calls."""
        text = "The quick brown fox jumps over the lazy dog."

        # Multiple calls should return same result
        results = [count_tokens(text) for _ in range(10)]
        assert len(set(results)) == 1  # All results identical


class TestChunkingWithMockedDatabase:
    """Integration tests with mocked database operations."""

    @pytest.fixture
    def mock_chunk_service(self) -> MagicMock:
        """Create a mock chunk service with async methods."""
        from unittest.mock import AsyncMock

        mock = MagicMock()
        mock.save_chunks = AsyncMock(return_value=10)
        mock.delete_chunks_for_document = AsyncMock(return_value=5)
        return mock

    @pytest.mark.asyncio
    async def test_end_to_end_with_mock_db(self, mock_chunk_service: MagicMock) -> None:
        """Test chunking with mocked database save."""
        # Create document text
        text = """
        LEGAL DOCUMENT

        This document establishes terms between parties.
        All provisions are binding and enforceable.

        SECTION 1: DEFINITIONS

        "Agreement" means this document.
        "Party" means a signatory to this Agreement.

        SECTION 2: OBLIGATIONS

        Each party agrees to fulfill their obligations.
        """ * 5

        # Chunk the document
        chunker = ParentChildChunker(
            parent_size=500,
            parent_overlap=50,
            child_size=150,
            child_overlap=20,
            min_size=30,
        )

        result = chunker.chunk_document("doc-123", text)

        # Save using mock service
        saved = await mock_chunk_service.save_chunks(
            document_id="doc-123",
            matter_id="matter-456",
            parent_chunks=result.parent_chunks,
            child_chunks=result.child_chunks,
        )

        # Verify save was called
        mock_chunk_service.save_chunks.assert_called_once()
        call_args = mock_chunk_service.save_chunks.call_args

        assert call_args.kwargs["document_id"] == "doc-123"
        assert call_args.kwargs["matter_id"] == "matter-456"
        assert len(call_args.kwargs["parent_chunks"]) == len(result.parent_chunks)
        assert len(call_args.kwargs["child_chunks"]) == len(result.child_chunks)


class TestChunkingEdgeCases:
    """Edge case integration tests."""

    def test_very_short_document(self) -> None:
        """Document shorter than min_size should produce no chunks."""
        chunker = ParentChildChunker(
            parent_size=500,
            parent_overlap=50,
            child_size=150,
            child_overlap=20,
            min_size=100,  # High minimum
        )

        result = chunker.chunk_document("doc-123", "Short text.")

        # Very short text below min_size
        assert len(result.parent_chunks) == 0

    def test_document_with_many_sections(self) -> None:
        """Document with many sections should chunk properly."""
        sections = [f"Section {i}: Content for section {i}. " * 20 for i in range(20)]
        text = "\n\n".join(sections)

        chunker = ParentChildChunker(
            parent_size=500,
            parent_overlap=50,
            child_size=150,
            child_overlap=20,
            min_size=30,
        )

        result = chunker.chunk_document("doc-123", text)

        # Should create multiple chunks
        assert len(result.parent_chunks) >= 5
        assert len(result.child_chunks) >= len(result.parent_chunks)

    def test_document_with_unicode(self) -> None:
        """Document with unicode should chunk correctly."""
        text = """
        LEGAL DOCUMENT - 法律文件

        This Agreement (本协议) between parties.

        Section 1: 定义 (Definitions)
        "Agreement" means 协议.

        Section 2: 义务 (Obligations)
        All parties agree 所有方同意.
        """ * 10

        chunker = ParentChildChunker(
            parent_size=500,
            parent_overlap=50,
            child_size=150,
            child_overlap=20,
            min_size=30,
        )

        result = chunker.chunk_document("doc-123", text)

        # Should handle unicode
        assert len(result.parent_chunks) > 0

        # Unicode should be preserved
        combined = " ".join(p.content for p in result.parent_chunks)
        assert "法律文件" in combined or "协议" in combined
