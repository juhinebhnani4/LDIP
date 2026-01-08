"""Chunking services for parent-child document chunking.

This module provides hierarchical document chunking for RAG pipelines:
- Parent chunks (1500-2000 tokens) for context
- Child chunks (400-700 tokens) for precise retrieval
"""

from app.services.chunking.token_counter import count_tokens, get_encoder
from app.services.chunking.text_splitter import RecursiveTextSplitter
from app.services.chunking.parent_child_chunker import (
    ParentChildChunker,
    ChunkData,
    ChunkingResult,
)
from app.services.chunking.bbox_linker import link_chunks_to_bboxes

__all__ = [
    "count_tokens",
    "get_encoder",
    "RecursiveTextSplitter",
    "ParentChildChunker",
    "ChunkData",
    "ChunkingResult",
    "link_chunks_to_bboxes",
]
