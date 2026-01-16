"""Unit tests for parent-child chunker."""

from uuid import UUID

import pytest

from app.services.chunking.parent_child_chunker import (
    ChunkData,
    ChunkingResult,
    ParentChildChunker,
)
from app.services.chunking.token_counter import count_tokens


class TestParentChildChunker:
    """Tests for ParentChildChunker class."""

    @pytest.fixture
    def chunker(self) -> ParentChildChunker:
        """Create a chunker with test settings."""
        return ParentChildChunker(
            parent_size=500,
            parent_overlap=50,
            child_size=150,
            child_overlap=20,
            min_size=20,
        )

    def test_empty_text(self, chunker: ParentChildChunker) -> None:
        """Should return empty result for empty text."""
        result = chunker.chunk_document("doc-123", "")
        assert result.document_id == "doc-123"
        assert len(result.parent_chunks) == 0
        assert len(result.child_chunks) == 0
        assert result.total_tokens == 0

    def test_whitespace_text(self, chunker: ParentChildChunker) -> None:
        """Should return empty result for whitespace only."""
        result = chunker.chunk_document("doc-123", "   \n\n  ")
        assert len(result.parent_chunks) == 0
        assert len(result.child_chunks) == 0

    def test_short_text_single_parent(self, chunker: ParentChildChunker) -> None:
        """Short text should create one parent and children."""
        text = "This is a short document with some content. " * 5
        result = chunker.chunk_document("doc-123", text)

        assert len(result.parent_chunks) >= 1
        # Children are created from parent content
        assert result.total_tokens > 0

    def test_parent_chunks_have_correct_type(self, chunker: ParentChildChunker) -> None:
        """Parent chunks should have type 'parent'."""
        text = "Content for testing. " * 100
        result = chunker.chunk_document("doc-123", text)

        for parent in result.parent_chunks:
            assert parent.chunk_type == "parent"
            assert parent.parent_id is None
            assert isinstance(parent.id, UUID)

    def test_child_chunks_reference_parent(self, chunker: ParentChildChunker) -> None:
        """Child chunks should reference their parent."""
        text = "Content for testing. " * 100
        result = chunker.chunk_document("doc-123", text)

        parent_ids = {p.id for p in result.parent_chunks}

        for child in result.child_chunks:
            assert child.chunk_type == "child"
            assert child.parent_id is not None
            assert child.parent_id in parent_ids

    def test_chunk_indices_sequential(self, chunker: ParentChildChunker) -> None:
        """Chunk indices should be sequential."""
        text = "Content for testing purposes. " * 150
        result = chunker.chunk_document("doc-123", text)

        # Parent indices should be sequential
        parent_indices = [p.chunk_index for p in result.parent_chunks]
        for i, idx in enumerate(parent_indices):
            assert idx == i

        # Child indices should be sequential
        child_indices = [c.chunk_index for c in result.child_chunks]
        for i, idx in enumerate(child_indices):
            assert idx == i

    def test_token_counts_accurate(self, chunker: ParentChildChunker) -> None:
        """Token counts in chunks should be accurate."""
        text = "Content for testing purposes. " * 100
        result = chunker.chunk_document("doc-123", text)

        for chunk in result.parent_chunks + result.child_chunks:
            actual_tokens = count_tokens(chunk.content)
            assert chunk.token_count == actual_tokens

    def test_total_tokens_sum(self, chunker: ParentChildChunker) -> None:
        """Total tokens should equal sum of all chunk tokens."""
        text = "Content for testing purposes. " * 100
        result = chunker.chunk_document("doc-123", text)

        expected_total = sum(c.token_count for c in result.parent_chunks)
        expected_total += sum(c.token_count for c in result.child_chunks)

        assert result.total_tokens == expected_total

    def test_chunks_not_empty(self, chunker: ParentChildChunker) -> None:
        """All chunks should have non-empty content."""
        text = "Content for testing purposes. " * 100
        result = chunker.chunk_document("doc-123", text)

        for chunk in result.parent_chunks + result.child_chunks:
            assert chunk.content.strip()
            assert chunk.token_count > 0

    def test_min_size_filter(self) -> None:
        """Chunks below min_size should be filtered out."""
        chunker = ParentChildChunker(
            parent_size=100,
            parent_overlap=10,
            child_size=50,
            child_overlap=5,
            min_size=30,  # High minimum
        )
        text = "A. B. C. D. E."  # Very short segments
        result = chunker.chunk_document("doc-123", text)

        # Small chunks should be filtered
        for chunk in result.parent_chunks + result.child_chunks:
            assert chunk.token_count >= 30 or len(result.parent_chunks) == 0


class TestParentChildChunkerLegalText:
    """Tests with legal document-style text."""

    @pytest.fixture
    def legal_chunker(self) -> ParentChildChunker:
        """Create a chunker with production-like settings."""
        return ParentChildChunker(
            parent_size=1750,
            parent_overlap=100,
            child_size=550,
            child_overlap=75,
            min_size=100,
        )

    @pytest.fixture
    def legal_document(self) -> str:
        """Create a sample legal document with enough content for multiple parent chunks."""
        sections = []
        for i in range(30):  # More sections to generate ~5000+ tokens
            sections.append(f"""
            ARTICLE {i + 1} - SECTION TITLE {i + 1}

            {i + 1}.1 This section establishes certain terms and conditions
            regarding the subject matter described herein. All parties agree
            to comply with these provisions in their entirety without exception.
            The terms outlined in this section shall be binding upon all parties
            and their respective successors, assigns, and legal representatives.

            {i + 1}.2 The obligations set forth in this section shall remain
            in effect for the duration of this Agreement unless otherwise
            modified by written consent of all parties. Any modification must
            be documented in writing and signed by authorized representatives
            of all parties to this Agreement.

            {i + 1}.3 In the event of any dispute arising under this section,
            the parties agree to first attempt resolution through good faith
            negotiation before pursuing any other remedies. Such negotiation
            shall continue for a period of no less than thirty (30) days before
            either party may initiate formal legal proceedings.

            {i + 1}.4 Neither party shall be liable for any failure to perform
            its obligations under this section if such failure results from
            circumstances beyond the reasonable control of such party, including
            but not limited to acts of God, natural disasters, war, terrorism,
            riots, embargoes, acts of civil or military authorities, fire, floods,
            accidents, strikes, or shortages of transportation, facilities, fuel,
            energy, labor, or materials.
            """)
        return "\n\n".join(sections)

    def test_legal_document_chunking(
        self,
        legal_chunker: ParentChildChunker,
        legal_document: str,
    ) -> None:
        """Should properly chunk a legal document."""
        result = legal_chunker.chunk_document("legal-doc-1", legal_document)

        # Should create multiple parent chunks
        assert len(result.parent_chunks) >= 2

        # Should create multiple child chunks
        assert len(result.child_chunks) >= len(result.parent_chunks)

        # Parent chunks should be larger than child chunks on average
        avg_parent_tokens = sum(p.token_count for p in result.parent_chunks) / len(
            result.parent_chunks
        )
        avg_child_tokens = sum(c.token_count for c in result.child_chunks) / len(
            result.child_chunks
        )
        assert avg_parent_tokens > avg_child_tokens

    def test_preserves_section_structure(
        self,
        legal_chunker: ParentChildChunker,
        legal_document: str,
    ) -> None:
        """Should preserve document section structure where possible."""
        result = legal_chunker.chunk_document("legal-doc-1", legal_document)

        # At least some chunks should contain "ARTICLE"
        articles_found = sum(
            1 for c in result.parent_chunks if "ARTICLE" in c.content
        )
        assert articles_found > 0


class TestChunkData:
    """Tests for ChunkData dataclass."""

    def test_chunk_data_creation(self) -> None:
        """Should create ChunkData with all fields."""
        from uuid import uuid4

        chunk_id = uuid4()
        parent_id = uuid4()

        chunk = ChunkData(
            id=chunk_id,
            content="Test content",
            chunk_type="child",
            chunk_index=5,
            parent_id=parent_id,
            token_count=10,
            page_number=1,
            bbox_ids=[uuid4(), uuid4()],
        )

        assert chunk.id == chunk_id
        assert chunk.content == "Test content"
        assert chunk.chunk_type == "child"
        assert chunk.chunk_index == 5
        assert chunk.parent_id == parent_id
        assert chunk.token_count == 10
        assert chunk.page_number == 1
        assert len(chunk.bbox_ids) == 2

    def test_chunk_data_defaults(self) -> None:
        """Should have correct defaults."""
        from uuid import uuid4

        chunk = ChunkData(
            id=uuid4(),
            content="Test",
            chunk_type="parent",
            chunk_index=0,
            parent_id=None,
            token_count=1,
        )

        assert chunk.page_number is None
        assert chunk.bbox_ids == []


class TestChunkingResult:
    """Tests for ChunkingResult dataclass."""

    def test_result_creation(self) -> None:
        """Should create ChunkingResult with all fields."""
        from uuid import uuid4

        parent = ChunkData(
            id=uuid4(),
            content="Parent",
            chunk_type="parent",
            chunk_index=0,
            parent_id=None,
            token_count=10,
        )

        child = ChunkData(
            id=uuid4(),
            content="Child",
            chunk_type="child",
            chunk_index=0,
            parent_id=parent.id,
            token_count=5,
        )

        result = ChunkingResult(
            document_id="doc-123",
            parent_chunks=[parent],
            child_chunks=[child],
            total_tokens=15,
        )

        assert result.document_id == "doc-123"
        assert len(result.parent_chunks) == 1
        assert len(result.child_chunks) == 1
        assert result.total_tokens == 15
