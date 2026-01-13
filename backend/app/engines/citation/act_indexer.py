"""Act Text Indexing Service for building section indices.

Provides functionality for indexing Act documents to enable efficient
section lookup during citation verification.

Story 3-3: Citation Verification (AC: #1)
"""

import asyncio
import re
from datetime import datetime
from functools import lru_cache
from typing import Final

import structlog

from app.services.chunk_service import ChunkService, get_chunk_service
from app.models.chunk import ChunkType, ChunkWithContent

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Regex patterns for section identification in Indian Acts
SECTION_HEADER_PATTERNS: Final[list[re.Pattern]] = [
    # "Section 138" or "Section 138." at line start
    re.compile(r"^Section\s+(\d+(?:\([a-zA-Z0-9]+\))?)\s*[.:\-—]?", re.IGNORECASE | re.MULTILINE),
    # "138. " at paragraph start (numbered section)
    re.compile(r"^(\d+)\.\s+[A-Z]", re.MULTILINE),
    # "[Section 138]" in brackets
    re.compile(r"^\[Section\s+(\d+(?:\([a-zA-Z0-9]+\))?)\]", re.IGNORECASE | re.MULTILINE),
    # "Sec. 138" abbreviated
    re.compile(r"^Sec\.\s*(\d+(?:\([a-zA-Z0-9]+\))?)", re.IGNORECASE | re.MULTILINE),
    # "§ 138" symbol notation
    re.compile(r"^§\s*(\d+(?:\([a-zA-Z0-9]+\))?)", re.MULTILINE),
]

# Pattern to find section references within text
SECTION_REFERENCE_PATTERN: Final[re.Pattern] = re.compile(
    r"(?:Section|Sec\.?|§)\s*(\d+(?:\s*\([a-zA-Z0-9]+\))*)",
    re.IGNORECASE,
)


# =============================================================================
# Data Classes
# =============================================================================


class SectionBoundary:
    """Represents the boundaries of a section in Act text."""

    def __init__(
        self,
        section_number: str,
        start_position: int,
        chunk_id: str,
        page_number: int | None = None,
        bbox_ids: list[str] | None = None,
    ):
        self.section_number = section_number
        self.start_position = start_position
        self.chunk_id = chunk_id
        self.page_number = page_number
        self.bbox_ids = bbox_ids or []

    def __repr__(self) -> str:
        return f"SectionBoundary(section={self.section_number}, chunk={self.chunk_id[:8]})"


class ActIndex:
    """Index of sections in an Act document."""

    def __init__(
        self,
        document_id: str,
        act_name: str,
        sections: dict[str, list[str]],  # section_number -> chunk_ids
        boundaries: list[SectionBoundary],
        indexed_at: datetime,
    ):
        self.document_id = document_id
        self.act_name = act_name
        self.sections = sections
        self.boundaries = boundaries
        self.indexed_at = indexed_at

    @property
    def section_numbers(self) -> list[str]:
        """Get all indexed section numbers."""
        return sorted(self.sections.keys(), key=lambda x: int(re.match(r"\d+", x).group()) if re.match(r"\d+", x) else 0)


# =============================================================================
# Exceptions
# =============================================================================


class ActIndexerError(Exception):
    """Base exception for act indexer operations."""

    def __init__(
        self,
        message: str,
        code: str = "ACT_INDEXER_ERROR",
    ):
        self.message = message
        self.code = code
        super().__init__(message)


class ActNotIndexedError(ActIndexerError):
    """Act document not yet indexed."""

    def __init__(self, document_id: str):
        super().__init__(
            f"Act document {document_id} not indexed",
            code="ACT_NOT_INDEXED",
        )


# =============================================================================
# Service Implementation
# =============================================================================


class ActIndexer:
    """Service for indexing Act documents to enable section lookup.

    Creates a section index mapping section numbers to chunk IDs,
    enabling efficient verification of citations against Act text.

    Example:
        >>> indexer = ActIndexer()
        >>> index = await indexer.index_act_document("doc-123", "matter-456")
        >>> chunks = await indexer.get_section_chunks("doc-123", "138")
    """

    def __init__(self, chunk_service: ChunkService | None = None) -> None:
        """Initialize act indexer.

        Args:
            chunk_service: Optional ChunkService instance for testing.
        """
        self._chunk_service = chunk_service
        self._index_cache: dict[str, ActIndex] = {}

    @property
    def chunk_service(self) -> ChunkService:
        """Get chunk service instance."""
        if self._chunk_service is None:
            self._chunk_service = get_chunk_service()
        return self._chunk_service

    async def index_act_document(
        self,
        document_id: str,
        matter_id: str,
        act_name: str = "Unknown Act",
    ) -> ActIndex:
        """Index an Act document for section lookup.

        Loads all chunks from the Act document and builds a section index
        mapping section numbers to chunk IDs.

        Args:
            document_id: Act document UUID.
            matter_id: Matter UUID for context.
            act_name: Display name of the Act.

        Returns:
            ActIndex with section mappings.

        Raises:
            ActIndexerError: If indexing fails.
        """
        # Check cache first
        if document_id in self._index_cache:
            logger.debug(
                "act_index_cache_hit",
                document_id=document_id,
            )
            return self._index_cache[document_id]

        try:
            # Load all chunks (use parent chunks for better context)
            chunks, parent_count, _ = await asyncio.to_thread(
                self.chunk_service.get_chunks_for_document,
                document_id,
                ChunkType.PARENT,
            )

            if not chunks:
                # Fall back to all chunks if no parents
                chunks, _, _ = await asyncio.to_thread(
                    self.chunk_service.get_chunks_for_document,
                    document_id,
                )

            if not chunks:
                raise ActIndexerError(
                    f"No chunks found for document {document_id}",
                    code="NO_CHUNKS_FOUND",
                )

            # Extract section boundaries
            boundaries = self.extract_section_boundaries(chunks)

            # Build section index
            sections: dict[str, list[str]] = {}
            for boundary in boundaries:
                section = boundary.section_number
                if section not in sections:
                    sections[section] = []
                if boundary.chunk_id not in sections[section]:
                    sections[section].append(boundary.chunk_id)

            # Create index
            index = ActIndex(
                document_id=document_id,
                act_name=act_name,
                sections=sections,
                boundaries=boundaries,
                indexed_at=datetime.utcnow(),
            )

            # Cache the index
            self._index_cache[document_id] = index

            logger.info(
                "act_document_indexed",
                document_id=document_id,
                act_name=act_name,
                section_count=len(sections),
                chunk_count=len(chunks),
            )

            return index

        except ActIndexerError:
            raise
        except Exception as e:
            logger.error(
                "act_indexing_failed",
                document_id=document_id,
                error=str(e),
            )
            raise ActIndexerError(
                f"Failed to index Act document: {e}",
                code="INDEXING_FAILED",
            ) from e

    async def get_section_chunks(
        self,
        act_document_id: str,
        section: str,
    ) -> list[ChunkWithContent]:
        """Retrieve chunks containing the specified section.

        Args:
            act_document_id: Act document UUID.
            section: Section number to find (e.g., "138", "138(1)").

        Returns:
            List of chunks containing the section, ordered by page.

        Raises:
            ActNotIndexedError: If Act not indexed.
            ActIndexerError: If retrieval fails.
        """
        # Ensure document is indexed
        if act_document_id not in self._index_cache:
            raise ActNotIndexedError(act_document_id)

        index = self._index_cache[act_document_id]

        # Normalize section number
        normalized_section = self._normalize_section(section)

        # Find matching section(s)
        chunk_ids: list[str] = []

        # Exact match first
        if normalized_section in index.sections:
            chunk_ids.extend(index.sections[normalized_section])
        else:
            # Try partial matches (e.g., "138" matches "138(1)", "138(2)")
            for sec, cids in index.sections.items():
                if sec.startswith(normalized_section) or normalized_section.startswith(sec.split("(")[0]):
                    chunk_ids.extend(cids)

        if not chunk_ids:
            return []

        # Load chunks with content
        try:
            chunks = []
            for chunk_id in chunk_ids:
                try:
                    chunk = await asyncio.to_thread(
                        self.chunk_service.get_chunk,
                        chunk_id,
                    )
                    # Convert to ChunkWithContent format
                    chunks.append(ChunkWithContent(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        chunk_type=chunk.chunk_type,
                        chunk_index=chunk.chunk_index,
                        token_count=chunk.token_count,
                        parent_chunk_id=chunk.parent_chunk_id,
                        page_number=chunk.page_number,
                        content=chunk.content,
                    ))
                except Exception as e:
                    logger.warning(
                        "chunk_load_failed",
                        chunk_id=chunk_id,
                        error=str(e),
                    )
                    continue

            # Sort by page number
            chunks.sort(key=lambda c: c.page_number or 0)

            return chunks

        except Exception as e:
            logger.error(
                "get_section_chunks_failed",
                act_document_id=act_document_id,
                section=section,
                error=str(e),
            )
            raise ActIndexerError(
                f"Failed to retrieve section chunks: {e}",
                code="CHUNK_RETRIEVAL_FAILED",
            ) from e

    def extract_section_boundaries(
        self,
        chunks: list[ChunkWithContent],
    ) -> list[SectionBoundary]:
        """Extract section boundaries from Act chunks.

        Identifies where sections start in the document text.

        Args:
            chunks: List of document chunks.

        Returns:
            List of section boundaries found.
        """
        boundaries: list[SectionBoundary] = []
        seen_sections: set[str] = set()

        for chunk in chunks:
            content = chunk.content

            # Try each pattern
            for pattern in SECTION_HEADER_PATTERNS:
                for match in pattern.finditer(content):
                    section_num = match.group(1).strip()
                    normalized = self._normalize_section(section_num)

                    # Skip duplicates from same chunk
                    key = f"{chunk.id}:{normalized}"
                    if key in seen_sections:
                        continue
                    seen_sections.add(key)

                    boundary = SectionBoundary(
                        section_number=normalized,
                        start_position=match.start(),
                        chunk_id=chunk.id,
                        page_number=chunk.page_number,
                        bbox_ids=chunk.bbox_ids if hasattr(chunk, 'bbox_ids') else [],
                    )
                    boundaries.append(boundary)

            # Also check for section references if no headers found
            if not any(b.chunk_id == chunk.id for b in boundaries):
                for match in SECTION_REFERENCE_PATTERN.finditer(content):
                    section_num = match.group(1).strip()
                    normalized = self._normalize_section(section_num)

                    key = f"{chunk.id}:{normalized}"
                    if key in seen_sections:
                        continue
                    seen_sections.add(key)

                    boundary = SectionBoundary(
                        section_number=normalized,
                        start_position=match.start(),
                        chunk_id=chunk.id,
                        page_number=chunk.page_number,
                        bbox_ids=[],
                    )
                    boundaries.append(boundary)

        # Sort by section number
        boundaries.sort(
            key=lambda b: int(re.match(r"\d+", b.section_number).group())
            if re.match(r"\d+", b.section_number)
            else 0
        )

        logger.debug(
            "section_boundaries_extracted",
            boundary_count=len(boundaries),
            unique_sections=len(set(b.section_number for b in boundaries)),
        )

        return boundaries

    def _normalize_section(self, section: str) -> str:
        """Normalize section number for matching.

        Args:
            section: Raw section string (e.g., "138", "138(1)", "138 (1)").

        Returns:
            Normalized section string (e.g., "138", "138(1)").
        """
        # Remove extra whitespace
        normalized = re.sub(r"\s+", "", section)
        # Ensure consistent format for subsections
        normalized = re.sub(r"\((\d+)\)", r"(\1)", normalized)
        return normalized

    def get_available_sections(self, document_id: str) -> list[str]:
        """Get list of sections available in an indexed Act.

        Args:
            document_id: Act document UUID.

        Returns:
            List of section numbers.

        Raises:
            ActNotIndexedError: If Act not indexed.
        """
        if document_id not in self._index_cache:
            raise ActNotIndexedError(document_id)

        return self._index_cache[document_id].section_numbers

    def clear_cache(self, document_id: str | None = None) -> None:
        """Clear index cache.

        Args:
            document_id: Optional specific document to clear. Clears all if None.
        """
        if document_id:
            self._index_cache.pop(document_id, None)
        else:
            self._index_cache.clear()


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_act_indexer() -> ActIndexer:
    """Get singleton act indexer instance.

    Returns:
        ActIndexer instance.
    """
    return ActIndexer()
