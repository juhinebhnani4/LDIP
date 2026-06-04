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
        articles_found = sum(1 for c in result.parent_chunks if "ARTICLE" in c.content)
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


class TestLayoutAwareChunking:
    """Tests for layout-aware chunking with DocumentLayout.

    Issue #2 fix: Added comprehensive tests for layout-aware chunking.
    """

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

    @pytest.fixture
    def sample_layout(self):
        """Create a sample DocumentLayout for testing."""
        from app.services.table_extraction.models import (
            BoundingBox,
            DocumentLayout,
            LayoutBlock,
        )

        blocks = [
            LayoutBlock(
                block_type="heading",
                page_number=1,
                bbox=BoundingBox(page=1, x=0.1, y=0.1, width=0.8, height=0.05),
                reading_order=0,
                confidence=0.95,
                text_content="ARTICLE 1 - DEFINITIONS",
            ),
            LayoutBlock(
                block_type="paragraph",
                page_number=1,
                bbox=BoundingBox(page=1, x=0.1, y=0.2, width=0.8, height=0.3),
                reading_order=1,
                confidence=0.92,
                text_content="This agreement defines the terms and conditions for the parties involved. "
                "All parties must comply with these provisions in their entirety without exception. "
                "The following definitions shall apply throughout this document.",
            ),
            LayoutBlock(
                block_type="paragraph",
                page_number=1,
                bbox=BoundingBox(page=1, x=0.1, y=0.55, width=0.8, height=0.2),
                reading_order=2,
                confidence=0.90,
                text_content="Party A refers to the first signatory of this agreement. "
                "Party B refers to the second signatory of this agreement. "
                "Effective Date means the date on which this agreement is signed by all parties.",
            ),
            LayoutBlock(
                block_type="heading",
                page_number=2,
                bbox=BoundingBox(page=2, x=0.1, y=0.1, width=0.8, height=0.05),
                reading_order=3,
                confidence=0.95,
                text_content="ARTICLE 2 - OBLIGATIONS",
            ),
            LayoutBlock(
                block_type="paragraph",
                page_number=2,
                bbox=BoundingBox(page=2, x=0.1, y=0.2, width=0.8, height=0.4),
                reading_order=4,
                confidence=0.91,
                text_content="Each party shall perform its obligations as specified in this agreement. "
                "Neither party shall be liable for failure to perform due to circumstances beyond control. "
                "All obligations shall remain in effect for the duration of this agreement.",
            ),
        ]

        return DocumentLayout(
            document_id="test-doc-123",
            blocks=blocks,
            page_count=2,
            processing_time_ms=500,
        )

    def test_layout_aware_chunking_creates_chunks(
        self, chunker: ParentChildChunker, sample_layout
    ) -> None:
        """Layout-aware chunking should create chunks from layout blocks."""
        text = "Full document text (not used when blocks have text_content)"
        result = chunker.chunk_document("test-doc-123", text, layout=sample_layout)

        assert len(result.parent_chunks) >= 1
        assert len(result.child_chunks) >= 1
        assert result.total_tokens > 0

    def test_layout_chunks_have_layout_derived_true(
        self, chunker: ParentChildChunker, sample_layout
    ) -> None:
        """Chunks from layout should have layout_derived=True."""
        text = "Full document text"
        result = chunker.chunk_document("test-doc-123", text, layout=sample_layout)

        for parent in result.parent_chunks:
            assert parent.layout_derived is True

        for child in result.child_chunks:
            assert child.layout_derived is True

    def test_layout_chunks_have_page_numbers(
        self, chunker: ParentChildChunker, sample_layout
    ) -> None:
        """Chunks from layout should have page numbers set."""
        text = "Full document text"
        result = chunker.chunk_document("test-doc-123", text, layout=sample_layout)

        for parent in result.parent_chunks:
            assert parent.page_number is not None
            assert parent.page_number >= 1

        for child in result.child_chunks:
            assert child.page_number is not None
            assert child.page_number >= 1

    def test_layout_chunks_have_block_types(
        self, chunker: ParentChildChunker, sample_layout
    ) -> None:
        """Chunks from layout should have block_types populated."""
        text = "Full document text"
        result = chunker.chunk_document("test-doc-123", text, layout=sample_layout)

        for parent in result.parent_chunks:
            assert len(parent.block_types) > 0
            # Block types should be valid
            for bt in parent.block_types:
                assert bt in (
                    "paragraph",
                    "heading",
                    "table",
                    "figure",
                    "list",
                    "code",
                    "caption",
                    "footer",
                    "header",
                    "stamp",
                )

    def test_fallback_to_text_based_when_no_layout(
        self, chunker: ParentChildChunker
    ) -> None:
        """Should fall back to text-based chunking when no layout provided."""
        text = "This is test content. " * 50
        result = chunker.chunk_document("test-doc-123", text, layout=None)

        assert len(result.parent_chunks) >= 1
        # Without layout, layout_derived should be False
        for parent in result.parent_chunks:
            assert parent.layout_derived is False

    def test_fallback_when_layout_has_no_blocks(
        self, chunker: ParentChildChunker
    ) -> None:
        """Should fall back to text-based when layout has no blocks."""
        from app.services.table_extraction.models import DocumentLayout

        empty_layout = DocumentLayout(
            document_id="test-doc-123",
            blocks=[],
            page_count=0,
        )

        text = "This is test content. " * 50
        result = chunker.chunk_document("test-doc-123", text, layout=empty_layout)

        assert len(result.parent_chunks) >= 1
        # Without blocks, should fall back to text-based
        for parent in result.parent_chunks:
            assert parent.layout_derived is False

    def test_fallback_when_layout_has_error(self, chunker: ParentChildChunker) -> None:
        """Should fall back to text-based when layout has an error."""
        from app.services.table_extraction.models import DocumentLayout

        error_layout = DocumentLayout(
            document_id="test-doc-123",
            blocks=[],
            page_count=0,
            error="Docling failed to process document",
        )

        text = "This is test content. " * 50
        result = chunker.chunk_document("test-doc-123", text, layout=error_layout)

        assert len(result.parent_chunks) >= 1

    def test_child_inherits_page_from_parent(
        self, chunker: ParentChildChunker, sample_layout
    ) -> None:
        """Child chunks should inherit page number from their parent."""
        text = "Full document text"
        result = chunker.chunk_document("test-doc-123", text, layout=sample_layout)

        # Map parent IDs to page numbers
        parent_pages = {p.id: p.page_number for p in result.parent_chunks}

        for child in result.child_chunks:
            assert child.parent_id in parent_pages
            assert child.page_number == parent_pages[child.parent_id]


class TestGetBlockText:
    """Tests for _get_block_text helper method."""

    @pytest.fixture
    def chunker(self) -> ParentChildChunker:
        """Create a chunker for testing."""
        return ParentChildChunker()

    def test_prefers_block_text_content(self, chunker: ParentChildChunker) -> None:
        """Should use block.text_content when available."""
        from app.services.table_extraction.models import BoundingBox, LayoutBlock

        block = LayoutBlock(
            block_type="paragraph",
            page_number=1,
            bbox=BoundingBox(page=1, x=0.1, y=0.1, width=0.8, height=0.2),
            reading_order=0,
            text_content="Block's own text content",
        )

        result = chunker._get_block_text(block, "Full document text that differs")
        assert result == "Block's own text content"

    def test_uses_text_offsets_when_no_content(
        self, chunker: ParentChildChunker
    ) -> None:
        """Should use text_start/text_end when text_content is None."""
        from app.services.table_extraction.models import BoundingBox, LayoutBlock

        block = LayoutBlock(
            block_type="paragraph",
            page_number=1,
            bbox=BoundingBox(page=1, x=0.1, y=0.1, width=0.8, height=0.2),
            reading_order=0,
            text_start=5,
            text_end=15,
        )

        result = chunker._get_block_text(block, "XXXXX0123456789XXXXX")
        assert result == "0123456789"

    def test_returns_empty_for_figures(self, chunker: ParentChildChunker) -> None:
        """Should return empty string for figure blocks without text."""
        from app.services.table_extraction.models import BoundingBox, LayoutBlock

        block = LayoutBlock(
            block_type="figure",
            page_number=1,
            bbox=BoundingBox(page=1, x=0.1, y=0.1, width=0.8, height=0.2),
            reading_order=0,
        )

        result = chunker._get_block_text(block, "Full document text")
        assert result == ""

    def test_returns_empty_when_no_text_info(self, chunker: ParentChildChunker) -> None:
        """Should return empty when no text_content and no offsets."""
        from app.services.table_extraction.models import BoundingBox, LayoutBlock

        block = LayoutBlock(
            block_type="paragraph",
            page_number=1,
            bbox=BoundingBox(page=1, x=0.1, y=0.1, width=0.8, height=0.2),
            reading_order=0,
        )

        result = chunker._get_block_text(block, "Full document text")
        assert result == ""


class TestCreateParentChunkFromBlocks:
    """Tests for _create_parent_chunk_from_blocks helper method."""

    @pytest.fixture
    def chunker(self) -> ParentChildChunker:
        """Create a chunker for testing."""
        return ParentChildChunker(min_size=10)

    def test_creates_chunk_with_correct_page(self, chunker: ParentChildChunker) -> None:
        """Should set primary page from most common page among blocks."""
        from app.services.table_extraction.models import BoundingBox, LayoutBlock

        blocks = [
            LayoutBlock(
                block_type="paragraph",
                page_number=1,
                bbox=BoundingBox(page=1, x=0.1, y=0.1, width=0.8, height=0.2),
                reading_order=0,
            ),
            LayoutBlock(
                block_type="paragraph",
                page_number=2,
                bbox=BoundingBox(page=2, x=0.1, y=0.1, width=0.8, height=0.2),
                reading_order=1,
            ),
            LayoutBlock(
                block_type="paragraph",
                page_number=2,
                bbox=BoundingBox(page=2, x=0.1, y=0.3, width=0.8, height=0.2),
                reading_order=2,
            ),
        ]
        text_parts = [
            "First paragraph text.",
            "Second paragraph text.",
            "Third paragraph text.",
        ]

        result = chunker._create_parent_chunk_from_blocks(blocks, text_parts, 0)

        assert result is not None
        assert result.page_number == 2  # Most common page

    def test_collects_unique_block_types(self, chunker: ParentChildChunker) -> None:
        """Should collect unique block types from all blocks."""
        from app.services.table_extraction.models import BoundingBox, LayoutBlock

        blocks = [
            LayoutBlock(
                block_type="heading",
                page_number=1,
                bbox=BoundingBox(page=1, x=0.1, y=0.1, width=0.8, height=0.1),
                reading_order=0,
            ),
            LayoutBlock(
                block_type="paragraph",
                page_number=1,
                bbox=BoundingBox(page=1, x=0.1, y=0.2, width=0.8, height=0.2),
                reading_order=1,
            ),
            LayoutBlock(
                block_type="paragraph",
                page_number=1,
                bbox=BoundingBox(page=1, x=0.1, y=0.5, width=0.8, height=0.2),
                reading_order=2,
            ),
        ]
        text_parts = [
            "Section Title",
            "First paragraph content.",
            "Second paragraph content.",
        ]

        result = chunker._create_parent_chunk_from_blocks(blocks, text_parts, 0)

        assert result is not None
        assert set(result.block_types) == {"heading", "paragraph"}

    def test_returns_none_for_empty_content(self, chunker: ParentChildChunker) -> None:
        """Should return None when text parts are all empty."""
        from app.services.table_extraction.models import BoundingBox, LayoutBlock

        blocks = [
            LayoutBlock(
                block_type="figure",
                page_number=1,
                bbox=BoundingBox(page=1, x=0.1, y=0.1, width=0.8, height=0.2),
                reading_order=0,
            ),
        ]
        text_parts = ["", "   ", ""]

        result = chunker._create_parent_chunk_from_blocks(blocks, text_parts, 0)

        assert result is None
