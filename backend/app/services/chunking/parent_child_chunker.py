"""Parent-child chunker for hierarchical document chunking.

Implements a two-level chunking strategy for RAG:
- Parent chunks (1500-2000 tokens) provide broader context for LLM
- Child chunks (400-700 tokens) enable precise retrieval via semantic search

This pattern allows retrieving small, precise chunks while having
access to their parent for expanded context when needed.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import structlog

from app.core.config import get_settings
from app.services.chunking.text_splitter import RecursiveTextSplitter
from app.services.chunking.token_counter import count_tokens

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
        page_number: Primary page number (determined during bbox linking).
        bbox_ids: List of bounding box UUIDs (populated during bbox linking).
    """

    id: UUID
    content: str
    chunk_type: str  # 'parent' or 'child'
    chunk_index: int
    parent_id: UUID | None
    token_count: int
    page_number: int | None = None
    bbox_ids: list[UUID] = field(default_factory=list)


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

    def chunk_document(self, document_id: str, text: str) -> ChunkingResult:
        """Chunk a document into parent-child hierarchy.

        Args:
            document_id: UUID of the source document.
            text: Extracted text from OCR to chunk.

        Returns:
            ChunkingResult with parent and child chunks.
        """
        logger.info(
            "chunking_document_start",
            document_id=document_id,
            text_length=len(text),
        )

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
        )

        return ChunkingResult(
            document_id=document_id,
            parent_chunks=parent_chunks,
            child_chunks=child_chunks,
            total_tokens=total_tokens,
        )
