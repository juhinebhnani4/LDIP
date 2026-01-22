"""RAG Answer Generation Service.

Story 6-2: Engine Orchestrator - RAG Answer Synthesis

Uses Gemini Flash for generating grounded answers from retrieved chunks.
This is the "Generation" step in Retrieval-Augmented Generation.

CRITICAL: Uses Gemini Flash for cost-effective generation.
CRITICAL: Answers must be grounded in provided context only.
"""

import asyncio
import time
from functools import lru_cache
from typing import Any

import structlog

from app.core.config import get_settings
from app.engines.rag.prompts import (
    RAG_ANSWER_SYSTEM_PROMPT,
    format_rag_answer_prompt,
    MAX_CONTEXT_CHUNKS,
)

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

MAX_RETRIES = 2
INITIAL_RETRY_DELAY = 0.5
MAX_ANSWER_LENGTH = 2000  # Max characters in generated answer


# =============================================================================
# Exceptions
# =============================================================================


class RAGGeneratorError(Exception):
    """Base exception for RAG generator operations."""

    def __init__(
        self,
        message: str,
        code: str = "RAG_GENERATOR_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class RAGConfigurationError(RAGGeneratorError):
    """Raised when Gemini is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="RAG_NOT_CONFIGURED", is_retryable=False)


# =============================================================================
# Data Classes
# =============================================================================


class RAGAnswerResult:
    """Result of RAG answer generation."""

    def __init__(
        self,
        answer: str,
        sources: list[dict[str, Any]],
        generation_time_ms: int,
        model_used: str,
        chunks_used: int,
    ):
        self.answer = answer
        self.sources = sources
        self.generation_time_ms = generation_time_ms
        self.model_used = model_used
        self.chunks_used = chunks_used

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "answer": self.answer,
            "sources": self.sources,
            "generation_time_ms": self.generation_time_ms,
            "model_used": self.model_used,
            "chunks_used": self.chunks_used,
        }


# =============================================================================
# Service Implementation
# =============================================================================


class RAGAnswerGenerator:
    """Service for generating answers from retrieved document chunks using Gemini.

    Takes retrieved chunks from hybrid search and generates a grounded,
    cited answer to the user's query.

    Example:
        >>> generator = RAGAnswerGenerator()
        >>> result = await generator.generate_answer(
        ...     query="Who are the parties?",
        ...     chunks=[{"content": "...", "document_name": "...", "page_number": 1}],
        ... )
        >>> print(result.answer)
        'The parties include Jyoti H. Mehta as applicant [1]...'
    """

    def __init__(self) -> None:
        """Initialize RAG answer generator."""
        self._model = None
        self._genai = None
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model

    @property
    def model(self):
        """Get or create Gemini model instance.

        Returns:
            Gemini GenerativeModel instance.

        Raises:
            RAGConfigurationError: If API key is not configured.
        """
        if self._model is None:
            if not self.api_key:
                raise RAGConfigurationError(
                    "Gemini API key not configured. Set GEMINI_API_KEY environment variable."
                )

            try:
                import google.generativeai as genai

                self._genai = genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=RAG_ANSWER_SYSTEM_PROMPT,
                )
                logger.info(
                    "rag_generator_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("rag_generator_init_failed", error=str(e))
                raise RAGConfigurationError(
                    f"Failed to initialize Gemini for RAG: {e}"
                ) from e

        return self._model

    async def generate_answer(
        self,
        query: str,
        chunks: list[dict[str, Any]],
    ) -> RAGAnswerResult:
        """Generate a grounded answer from retrieved chunks.

        Args:
            query: User's question.
            chunks: Retrieved document chunks with content and metadata.

        Returns:
            RAGAnswerResult with generated answer and metadata.

        Raises:
            RAGGeneratorError: If generation fails after retries.
        """
        start_time = time.time()

        # Handle empty chunks
        if not chunks:
            logger.debug("rag_generation_no_chunks", query=query[:100])
            return RAGAnswerResult(
                answer="I couldn't find relevant information in the documents to answer this question.",
                sources=[],
                generation_time_ms=0,
                model_used=self.model_name,
                chunks_used=0,
            )

        # Limit chunks to max context
        chunks_to_use = chunks[:MAX_CONTEXT_CHUNKS]

        # Format prompt
        user_prompt = format_rag_answer_prompt(query, chunks_to_use)

        # Generate answer with retries
        last_error = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    user_prompt,
                )

                # Extract answer text
                answer_text = response.text.strip()

                # Truncate if too long
                if len(answer_text) > MAX_ANSWER_LENGTH:
                    answer_text = answer_text[:MAX_ANSWER_LENGTH] + "..."

                generation_time_ms = int((time.time() - start_time) * 1000)

                # Build sources list from chunks used
                sources = [
                    {
                        "document_name": c.get("document_name") or c.get("documentName") or "Unknown",
                        "document_id": c.get("document_id") or c.get("documentId"),
                        "page_number": c.get("page_number") or c.get("pageNumber"),
                        "chunk_id": c.get("chunk_id") or c.get("chunkId") or c.get("id"),
                    }
                    for c in chunks_to_use
                ]

                logger.info(
                    "rag_generation_success",
                    query_length=len(query),
                    chunks_used=len(chunks_to_use),
                    answer_length=len(answer_text),
                    generation_time_ms=generation_time_ms,
                )

                return RAGAnswerResult(
                    answer=answer_text,
                    sources=sources,
                    generation_time_ms=generation_time_ms,
                    model_used=self.model_name,
                    chunks_used=len(chunks_to_use),
                )

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for non-retryable errors
                if "api key" in error_str or "authentication" in error_str:
                    raise RAGConfigurationError(f"Gemini authentication failed: {e}") from e

                if attempt < MAX_RETRIES:
                    logger.warning(
                        "rag_generation_retry",
                        attempt=attempt + 1,
                        error=str(e),
                        retry_delay=retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

        # All retries exhausted
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "rag_generation_failed",
            query=query[:100],
            error=str(last_error),
            generation_time_ms=generation_time_ms,
        )

        raise RAGGeneratorError(
            f"Failed to generate answer after {MAX_RETRIES + 1} attempts: {last_error}"
        )


# =============================================================================
# Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_rag_generator() -> RAGAnswerGenerator:
    """Get singleton RAG generator instance.

    Returns:
        RAGAnswerGenerator instance.
    """
    return RAGAnswerGenerator()


async def generate_rag_answer(
    query: str,
    chunks: list[dict[str, Any]],
) -> RAGAnswerResult:
    """Convenience function to generate RAG answer.

    Args:
        query: User's question.
        chunks: Retrieved document chunks.

    Returns:
        RAGAnswerResult with generated answer.
    """
    generator = get_rag_generator()
    return await generator.generate_answer(query, chunks)
