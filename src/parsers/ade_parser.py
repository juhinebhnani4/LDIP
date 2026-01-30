"""Landing AI ADE (Agentic Document Extraction) parser.

This module provides document parsing with native visual grounding.
Each chunk comes with bounding box coordinates - no fuzzy matching needed.
"""

import os
from pathlib import Path
from typing import Optional, Union

import structlog
from agentic_doc.parse import parse
from agentic_doc.common import ParsedDocument, Chunk as ADEChunk

from src.core.config import settings
from src.core.models import Chunk, ChunkType, BoundingBox
from src.core.utils import generate_chunk_id, count_tokens

logger = structlog.get_logger(__name__)


class ADEParser:
    """Parser using Landing AI's Agentic Document Extraction.

    Features:
    - Native bounding box grounding (no fuzzy matching!)
    - Handles tables, figures, and text
    - Markdown output with anchor tags
    - Multi-page PDF support
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize ADE parser.

        Args:
            api_key: Landing AI API key. If not provided, uses VISION_AGENT_API_KEY env var.
        """
        self.api_key = api_key or settings.vision_agent_api_key
        if self.api_key:
            os.environ["VISION_AGENT_API_KEY"] = self.api_key

    def parse(
        self,
        file_path: Union[str, Path],
        document_id: Optional[str] = None,
        matter_id: Optional[str] = None,
    ) -> list[Chunk]:
        """Parse a document using ADE.

        Args:
            file_path: Path to PDF or image file
            document_id: Optional document identifier
            matter_id: Optional matter/case identifier

        Returns:
            List of Chunk objects with visual grounding
        """
        file_path = Path(file_path)

        logger.info("parsing_document", file=str(file_path))

        # Call ADE API
        results: list[ParsedDocument] = parse(str(file_path))

        if not results:
            logger.warning("no_parse_results", file=str(file_path))
            return []

        # Convert ADE results to our Chunk model
        chunks: list[Chunk] = []

        for result in results:
            for idx, ade_chunk in enumerate(result.chunks):
                chunk = self._convert_chunk(
                    ade_chunk=ade_chunk,
                    index=idx,
                    document_id=document_id,
                    matter_id=matter_id,
                )
                if chunk:
                    chunks.append(chunk)

        logger.info(
            "parsing_complete",
            file=str(file_path),
            total_chunks=len(chunks),
        )

        return chunks

    def _convert_chunk(
        self,
        ade_chunk: ADEChunk,
        index: int,
        document_id: Optional[str] = None,
        matter_id: Optional[str] = None,
    ) -> Optional[Chunk]:
        """Convert ADE chunk to our Chunk model.

        Args:
            ade_chunk: Chunk from ADE
            index: Chunk index
            document_id: Optional document ID
            matter_id: Optional matter ID

        Returns:
            Converted Chunk or None if invalid
        """
        text = ade_chunk.text or ""

        # Skip empty chunks
        if not text.strip():
            return None

        # Get chunk ID
        chunk_id = ade_chunk.chunk_id or generate_chunk_id(text, 0, index)

        # Convert chunk type (it's an enum)
        chunk_type_value = ade_chunk.chunk_type.value if hasattr(ade_chunk.chunk_type, 'value') else str(ade_chunk.chunk_type)
        chunk_type = self._map_chunk_type(chunk_type_value)

        # Extract page and bounding box from grounding
        # grounding is a list of ChunkGrounding objects
        page = 0
        bbox = None

        if ade_chunk.grounding and len(ade_chunk.grounding) > 0:
            first_grounding = ade_chunk.grounding[0]
            page = first_grounding.page

            # Extract bbox from grounding.box (l, t, r, b format)
            if hasattr(first_grounding, 'box') and first_grounding.box:
                box = first_grounding.box
                # Convert l, t, r, b to x0, y0, x1, y1 format
                bbox = BoundingBox(
                    x0=box.l,
                    y0=box.t,
                    x1=box.r,
                    y1=box.b
                )

        return Chunk(
            chunk_id=chunk_id,
            text=text,
            page=page,
            chunk_type=chunk_type,
            bbox=bbox,
            document_id=document_id,
            matter_id=matter_id,
            token_count=count_tokens(text),
        )

    def _map_chunk_type(self, ade_type: str) -> ChunkType:
        """Map ADE chunk type to our ChunkType enum."""
        type_mapping = {
            "text": ChunkType.TEXT,
            "table": ChunkType.TABLE,
            "figure": ChunkType.FIGURE,
            "header": ChunkType.HEADER,
            "footer": ChunkType.FOOTER,
            "marginalia": ChunkType.TEXT,  # Map marginalia to text
        }
        return type_mapping.get(ade_type.lower(), ChunkType.TEXT)

    def get_markdown(self, file_path: Union[str, Path]) -> str:
        """Get full markdown representation of document.

        Args:
            file_path: Path to document

        Returns:
            Markdown string with anchor tags
        """
        results = parse(str(file_path))
        if results:
            return results[0].markdown
        return ""


def parse_document(
    file_path: Union[str, Path],
    document_id: Optional[str] = None,
    matter_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> list[Chunk]:
    """Convenience function to parse a document.

    Args:
        file_path: Path to document
        document_id: Optional document identifier
        matter_id: Optional matter identifier
        api_key: Optional API key (uses env var if not provided)

    Returns:
        List of Chunk objects with visual grounding
    """
    parser = ADEParser(api_key=api_key)
    return parser.parse(file_path, document_id, matter_id)
