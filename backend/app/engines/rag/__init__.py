"""RAG Engine module.

Story 6-2: Engine Orchestrator - RAG Answer Generation

This module provides LLM-based answer synthesis from retrieved chunks.
"""

from app.engines.rag.prompts import (
    RAG_ANSWER_SYSTEM_PROMPT,
    format_rag_answer_prompt,
)
from app.engines.rag.generator import generate_rag_answer

__all__ = [
    "RAG_ANSWER_SYSTEM_PROMPT",
    "format_rag_answer_prompt",
    "generate_rag_answer",
]
