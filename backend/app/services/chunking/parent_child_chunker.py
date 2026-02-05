"""Parent-child chunker for hierarchical document chunking.

Implements a two-level chunking strategy for RAG:
- Parent chunks (1500-2000 tokens) provide broader context for LLM
- Child chunks (400-700 tokens) enable precise retrieval via semantic search

This pattern allows retrieving small, precise chunks while having
access to their parent for expanded context when needed.

Supports optional layout-aware chunking when a DocumentLayout is provided,
which respects document structure (paragraphs, headings, tables) instead of
splitting arbitrarily by character patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.core.config import get_settings
from app.services.chunking.text_splitter import RecursiveTextSplitter
from app.services.chunking.token_counter import count_tokens

if TYPE_CHECKING:
    from app.services.table_extraction.models import DocumentLayout, LayoutBlock

logger = structlog.get_logger(__name__)


@dataclass
class ChunkData:
    """Internal representation of a chunk before database insertion.

    Attributes:
        id: Unique identifier for the chunk.
        content: Text content of the chunk.
        chunk_type: Either 'parent' or 'child'.
        chunk_index: Order within document (parents indexed separately from children).
        parent_id: UUID of parent chunk (None for parent chunks).
        token_count: Number of tokens in the chunk.
        page_number: Primary page number (set during layout-aware chunking or bbox linking).
        bbox_ids: List of bounding box UUIDs (populated during bbox linking).
        block_types: List of block types this chunk contains (when using layout-aware chunking).
        layout_derived: Whether page/bbox info was derived from layout (vs fuzzy matching).
        source_block_ids: UUIDs of LayoutBlocks that contributed to this chunk.
    """

    id: UUID
    content: str
    chunk_type: str  # 'parent' or 'child'
    chunk_index: int
    parent_id: UUID | None
    token_count: int
    page_number: int | None = None
    bbox_ids: list[UUID] = field(default_factory=list)
    block_types: list[str] = field(default_factory=list)
    layout_derived: bool = False
    source_block_ids: list[UUID] = field(default_factory=list)  # Track source layout blocks


@dataclass
class ChunkingResult:
    """Result of chunking a document.

    Attributes:
        document_id: UUID of the source document.
        parent_chunks: List of parent chunks for context.
        child_chunks: List of child chunks for retrieval.
        total_tokens: Sum of all chunk tokens.
    """

    document_id: str
    parent_chunks: list[ChunkData]
    child_chunks: list[ChunkData]
    total_tokens: int


class ParentChildChunker:
    """Two-level hierarchical chunker for RAG retrieval.

    Creates parent chunks (1500-2000 tokens) for broader context,
    and child chunks (400-700 tokens) for precise semantic search.

    Each child chunk maintains a reference to its parent, enabling
    context expansion when search results are displayed.
    """

    def __init__(
        self,
        parent_size: int | None = None,
        parent_overlap: int | None = None,
        child_size: int | None = None,
        child_overlap: int | None = None,
        min_size: int | None = None,
    ):
        """Initialize the chunker with size parameters.

        Args:
            parent_size: Target token size for parent chunks.
            parent_overlap: Token overlap between parent chunks.
            child_size: Target token size for child chunks.
            child_overlap: Token overlap between child chunks.
            min_size: Minimum viable chunk size (smaller chunks are discarded).
        """
        settings = get_settings()

        self.parent_size = parent_size or settings.chunk_parent_size
        self.parent_overlap = parent_overlap or settings.chunk_parent_overlap
        self.child_size = child_size or settings.chunk_child_size
        self.child_overlap = child_overlap or settings.chunk_child_overlap
        self.min_size = min_size or settings.chunk_min_size

        self.parent_splitter = RecursiveTextSplitter(
            chunk_size=self.parent_size,
            chunk_overlap=self.parent_overlap,
            length_function=count_tokens,
        )

        self.child_splitter = RecursiveTextSplitter(
            chunk_size=self.child_size,
            chunk_overlap=self.child_overlap,
            length_function=count_tokens,
        )

    def chunk_document(
        self,
        document_id: str,
        text: str,
        layout: DocumentLayout | None = None,
    ) -> ChunkingResult:
        """Chunk a document into parent-child hierarchy.

        When layout is provided, uses layout-aware chunking that respects
        document structure (paragraphs, headings, tables). Otherwise falls
        back to text-based splitting.

        Args:
            document_id: UUID of the source document.
            text: Extracted text from OCR to chunk.
            layout: Optional DocumentLayout from Docling for structure-aware chunking.

        Returns:
            ChunkingResult with parent and child chunks.
        """
        logger.info(
            "chunking_document_start",
            document_id=document_id,
            text_length=len(text),
            layout_provided=layout is not None,
            layout_blocks=len(layout.blocks) if layout and layout.has_blocks else 0,
        )

        # Use layout-aware chunking if layout is available and has blocks
        # Layout blocks may have their own text_content, so empty text is OK
        if layout and layout.has_blocks and layout.success:
            return self._chunk_with_layout(document_id, text, layout)

        # For text-based chunking, we need actual text
        if not text or not text.strip():
            logger.warning(
                "chunking_document_empty_text",
                document_id=document_id,
            )
            return ChunkingResult(
                document_id=document_id,
                parent_chunks=[],
                child_chunks=[],
                total_tokens=0,
            )

        # Fall back to text-based chunking
        return self._chunk_text_based(document_id, text)

    def _chunk_text_based(self, document_id: str, text: str) -> ChunkingResult:
        """Original text-based chunking without layout awareness.

        Args:
            document_id: UUID of the source document.
            text: Extracted text from OCR to chunk.

        Returns:
            ChunkingResult with parent and child chunks.
        """
        # Step 1: Create parent chunks
        parent_texts = self.parent_splitter.split_text(text)
        parent_chunks: list[ChunkData] = []

        for idx, parent_text in enumerate(parent_texts):
            token_count = count_tokens(parent_text)

            # Skip chunks below minimum size
            if token_count < self.min_size:
                logger.debug(
                    "skipping_small_parent",
                    index=idx,
                    tokens=token_count,
                    min_size=self.min_size,
                )
                continue

            parent_chunks.append(
                ChunkData(
                    id=uuid4(),
                    content=parent_text,
                    chunk_type="parent",
                    chunk_index=idx,
                    parent_id=None,
                    token_count=token_count,
                )
            )

        # Step 2: Create child chunks from each parent
        child_chunks: list[ChunkData] = []
        child_index = 0

        for parent in parent_chunks:
            child_texts = self.child_splitter.split_text(parent.content)

            for child_text in child_texts:
                token_count = count_tokens(child_text)

                # Skip chunks below minimum size
                if token_count < self.min_size:
                    logger.debug(
                        "skipping_small_child",
                        parent_index=parent.chunk_index,
                        tokens=token_count,
                        min_size=self.min_size,
                    )
                    continue

                child_chunks.append(
                    ChunkData(
                        id=uuid4(),
                        content=child_text,
                        chunk_type="child",
                        chunk_index=child_index,
                        parent_id=parent.id,
                        token_count=token_count,
                    )
                )
                child_index += 1

        # Calculate total tokens
        parent_tokens = sum(c.token_count for c in parent_chunks)
        child_tokens = sum(c.token_count for c in child_chunks)
        total_tokens = parent_tokens + child_tokens

        logger.info(
            "chunking_document_complete",
            document_id=document_id,
            parent_count=len(parent_chunks),
            child_count=len(child_chunks),
            parent_tokens=parent_tokens,
            child_tokens=child_tokens,
            total_tokens=total_tokens,
            layout_aware=False,
        )

        return ChunkingResult(
            document_id=document_id,
            parent_chunks=parent_chunks,
            child_chunks=child_chunks,
            total_tokens=total_tokens,
        )

    def _chunk_with_layout(
        self,
        document_id: str,
        text: str,
        layout: DocumentLayout,
    ) -> ChunkingResult:
        """Layout-aware chunking that respects document structure.

        Groups blocks together until token limit is reached, preferring
        to break between blocks rather than within them.

        Args:
            document_id: UUID of the source document.
            text: Extracted text from OCR.
            layout: DocumentLayout with block structure from Docling.

        Returns:
            ChunkingResult with layout-aware parent and child chunks.
        """
        logger.info(
            "layout_aware_chunking_start",
            document_id=document_id,
            block_count=len(layout.blocks),
            page_count=layout.page_count,
        )

        # Sort blocks by reading order
        sorted_blocks = sorted(layout.blocks, key=lambda b: b.reading_order)

        # Check if any blocks have text content from Docling
        blocks_with_text = sum(1 for b in sorted_blocks if b.text_content)

        if blocks_with_text == 0 and text and text.strip():
            # Docling detected layout but has no text (OCR was disabled).
            # Fall back to text-based chunking with layout page metadata.
            logger.info(
                "layout_aware_chunking_fallback_to_text",
                document_id=document_id,
                reason="blocks_have_no_text_content",
                block_count=len(sorted_blocks),
            )
            # Use text-based chunking but enrich with page numbers from layout
            result = self._chunk_text_based(document_id, text)
            # Try to assign page numbers from layout blocks based on reading position
            if result.parent_chunks and sorted_blocks:
                self._assign_page_numbers_from_layout(
                    result.parent_chunks, sorted_blocks, layout.page_count
                )
            return result

        # Group blocks into parent-sized chunks
        parent_chunks: list[ChunkData] = []
        current_blocks: list[LayoutBlock] = []
        current_text_parts: list[str] = []
        current_tokens = 0

        for block in sorted_blocks:
            # Get text for this block
            block_text = self._get_block_text(block, text)
            if not block_text or not block_text.strip():
                continue

            block_tokens = count_tokens(block_text)

            # Check if adding this block would exceed parent size
            if current_tokens + block_tokens > self.parent_size and current_blocks:
                # Save current parent chunk
                parent_chunk = self._create_parent_chunk_from_blocks(
                    current_blocks,
                    current_text_parts,
                    len(parent_chunks),
                )
                if parent_chunk:
                    parent_chunks.append(parent_chunk)

                # Start new chunk with this block
                current_blocks = [block]
                current_text_parts = [block_text]
                current_tokens = block_tokens
            else:
                # Add block to current chunk
                current_blocks.append(block)
                current_text_parts.append(block_text)
                current_tokens += block_tokens

        # Don't forget the last chunk
        if current_blocks:
            parent_chunk = self._create_parent_chunk_from_blocks(
                current_blocks,
                current_text_parts,
                len(parent_chunks),
            )
            if parent_chunk:
                parent_chunks.append(parent_chunk)

        # Create child chunks from each parent
        child_chunks: list[ChunkData] = []
        child_index = 0

        for parent in parent_chunks:
            # Split parent into children using text splitter
            child_texts = self.child_splitter.split_text(parent.content)

            for child_text in child_texts:
                token_count = count_tokens(child_text)

                if token_count < self.min_size:
                    continue

                child_chunks.append(
                    ChunkData(
                        id=uuid4(),
                        content=child_text,
                        chunk_type="child",
                        chunk_index=child_index,
                        parent_id=parent.id,
                        token_count=token_count,
                        # Inherit page and source blocks from parent
                        page_number=parent.page_number,
                        block_types=parent.block_types.copy(),
                        layout_derived=True,
                        source_block_ids=parent.source_block_ids.copy(),
                    )
                )
                child_index += 1

        # Calculate total tokens
        parent_tokens = sum(c.token_count for c in parent_chunks)
        child_tokens = sum(c.token_count for c in child_chunks)
        total_tokens = parent_tokens + child_tokens

        # Fallback: If layout-aware chunking produced no chunks but we have text,
        # use text-based chunking instead. This handles cases where Docling extracts
        # layout but blocks have no usable text_content (e.g., OCR disabled).
        if len(parent_chunks) == 0 and text and text.strip():
            logger.info(
                "layout_aware_chunking_fallback_to_text",
                document_id=document_id,
                reason="layout_produced_zero_chunks",
                block_count=len(layout.blocks),
                blocks_with_text=blocks_with_text,
            )
            result = self._chunk_text_based(document_id, text)
            # Try to assign page numbers from layout blocks based on reading position
            if result.parent_chunks and sorted_blocks:
                self._assign_page_numbers_from_layout(
                    result.parent_chunks, sorted_blocks, layout.page_count
                )
            return result

        logger.info(
            "chunking_document_complete",
            document_id=document_id,
            parent_count=len(parent_chunks),
            child_count=len(child_chunks),
            parent_tokens=parent_tokens,
            child_tokens=child_tokens,
            total_tokens=total_tokens,
            layout_aware=True,
        )

        return ChunkingResult(
            document_id=document_id,
            parent_chunks=parent_chunks,
            child_chunks=child_chunks,
            total_tokens=total_tokens,
        )

    def _get_block_text(self, block: LayoutBlock, full_text: str, page_texts: dict[int, str] | None = None) -> str:
        """Extract text for a block from the full document text.

        Issue #1 fix: Enhanced with fallback to page-based text extraction.

        Args:
            block: Layout block with optional text_content or text range.
            full_text: Full document text from OCR.
            page_texts: Optional dict mapping page numbers to their text content.

        Returns:
            Text content for this block.
        """
        # Prefer block's own text content if available (from Docling)
        if block.text_content:
            return block.text_content

        # Fall back to extracting from full text using character offsets
        if block.text_start is not None and block.text_end is not None:
            return full_text[block.text_start : block.text_end]

        # If we have page-based text and this is not a figure/stamp, try page text
        # Note: For figures and stamps, we don't have text and that's expected
        if page_texts and block.block_type not in ("figure", "stamp", "picture"):
            page_text = page_texts.get(block.page_number, "")
            if page_text:
                # Return the page text - it will be deduplicated in chunk creation
                return page_text

        # If no text info available, return empty (block will be skipped)
        return ""

    def _create_parent_chunk_from_blocks(
        self,
        blocks: list[LayoutBlock],
        text_parts: list[str],
        chunk_index: int,
    ) -> ChunkData | None:
        """Create a parent chunk from a list of layout blocks.

        Args:
            blocks: List of LayoutBlock objects in this chunk.
            text_parts: Text content for each block.
            chunk_index: Index of this parent chunk.

        Returns:
            ChunkData for the parent chunk, or None if empty.
        """
        # Join text parts with double newlines (paragraph separator)
        content = "\n\n".join(text_parts)

        if not content.strip():
            return None

        token_count = count_tokens(content)

        if token_count < self.min_size:
            return None

        # Determine primary page (most common among blocks)
        page_counts: dict[int, int] = {}
        for block in blocks:
            page_counts[block.page_number] = page_counts.get(block.page_number, 0) + 1

        primary_page = max(page_counts, key=page_counts.get) if page_counts else None

        # Collect unique block types
        block_types = list(set(block.block_type for block in blocks))

        return ChunkData(
            id=uuid4(),
            content=content,
            chunk_type="parent",
            chunk_index=chunk_index,
            parent_id=None,
            token_count=token_count,
            page_number=primary_page,
            block_types=block_types,
            layout_derived=True,
            source_block_ids=[block.id for block in blocks],  # Track source blocks
        )

    def _assign_page_numbers_from_layout(
        self,
        chunks: list[ChunkData],
        layout_blocks: list[LayoutBlock],
        page_count: int,
    ) -> None:
        """Assign page numbers to text-based chunks using layout block distribution.

        When Docling provides layout blocks without text (OCR disabled), we can
        still use the block distribution across pages to estimate page numbers
        for text-based chunks.

        Args:
            chunks: List of chunks to assign page numbers to.
            layout_blocks: Layout blocks from Docling (sorted by reading order).
            page_count: Total number of pages in the document.
        """
        if not chunks or not layout_blocks or page_count < 1:
            return

        # Count blocks per page to understand document structure
        page_block_counts: dict[int, int] = {}
        for block in layout_blocks:
            page = block.page_number
            page_block_counts[page] = page_block_counts.get(page, 0) + 1

        # Calculate cumulative block positions for proportional mapping
        total_blocks = len(layout_blocks)

        # Build page boundaries as cumulative block percentages
        # E.g., if page 1 has 5 blocks and page 2 has 10 blocks out of 15 total,
        # page 1 covers 0-33% and page 2 covers 33-100%
        page_boundaries: list[tuple[int, float, float]] = []
        cumulative = 0
        for page in sorted(page_block_counts.keys()):
            start_pct = cumulative / total_blocks
            cumulative += page_block_counts[page]
            end_pct = cumulative / total_blocks
            page_boundaries.append((page, start_pct, end_pct))

        # Assign page to each chunk based on its position in the document
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            # Skip if already has a page number
            if chunk.page_number is not None:
                continue

            # Calculate chunk's position as a percentage through the document
            chunk_position = (i + 0.5) / total_chunks  # Use center of chunk

            # Find which page this position maps to
            for page, start_pct, end_pct in page_boundaries:
                if start_pct <= chunk_position < end_pct:
                    chunk.page_number = page
                    break
            else:
                # If beyond last boundary, use last page
                if page_boundaries:
                    chunk.page_number = page_boundaries[-1][0]

        logger.debug(
            "page_numbers_assigned_from_layout",
            chunk_count=len(chunks),
            pages_used=list(set(c.page_number for c in chunks if c.page_number)),
        )
