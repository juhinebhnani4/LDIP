"""RAG Answer Generation Service.

Story 6-2: Engine Orchestrator - RAG Answer Synthesis

Uses Gemini Flash for generating grounded answers from retrieved chunks.
This is the "Generation" step in Retrieval-Augmented Generation.

CRITICAL: Uses Gemini Flash for cost-effective generation.
CRITICAL: Answers must be grounded in provided context only.
"""

import asyncio
import re
import time
from functools import lru_cache
from typing import Any

import structlog
from google.genai import types

from app.core.config import get_settings
from app.core.cost_tracking import (
    CostTracker,
    LLMProvider,
    estimate_tokens,
    persist_cost,
)
from app.core.gemini_client import GeminiClientError, get_gemini_client
from app.core.llm_rate_limiter import LLMProvider as RateLimitProvider
from app.core.llm_rate_limiter import get_rate_limiter
from app.engines.rag.prompts import (
    RAG_ANSWER_SYSTEM_PROMPT,
    SYSTEM_PROMPTS,
    format_rag_answer_prompt,
)
from app.engines.rag.query_profile import QueryProfile

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

MAX_RETRIES = 2
INITIAL_RETRY_DELAY = 0.5
MAX_ANSWER_LENGTH = (
    3500  # Max characters in generated answer (fallback; QueryProfile overrides)
)
GEMINI_GENERATION_TIMEOUT_SECONDS = (
    35.0  # Hard timeout per Gemini call (overridden by config)
)


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


class RAGGenerationTimeoutError(RAGGeneratorError):
    """Raised when Gemini generation exceeds the timeout."""

    def __init__(self, timeout_seconds: float):
        super().__init__(
            f"Gemini generation timed out after {timeout_seconds:.0f}s",
            code="RAG_GENERATION_TIMEOUT",
            is_retryable=False,
        )
        self.timeout_seconds = timeout_seconds


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
        self._client = None
        settings = get_settings()
        self.model_name = settings.gemini_model

    @property
    def client(self):
        """Get Gemini client instance.

        Returns:
            google.genai.Client instance.

        Raises:
            RAGConfigurationError: If API key is not configured.
        """
        if self._client is None:
            try:
                self._client = get_gemini_client()
                logger.info(
                    "rag_generator_initialized",
                    model=self.model_name,
                )
            except GeminiClientError as e:
                raise RAGConfigurationError(str(e)) from e

        return self._client

    async def generate_answer(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        matter_id: str | None = None,
        query_profile: QueryProfile | None = None,
        cause_title: str | None = None,
    ) -> RAGAnswerResult:
        """Generate a grounded answer from retrieved chunks.

        Args:
            query: User's question.
            chunks: Retrieved document chunks with content and metadata.
            matter_id: Optional matter ID for cost tracking.
            query_profile: Optional query profile for adaptive parameters.
            cause_title: Optional cause title (party listing) for context grounding.

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

        # Use QueryProfile parameters if available, otherwise defaults
        profile = query_profile or QueryProfile.default()

        # Limit chunks to max context (profile-aware)
        chunks_to_use = chunks[: profile.max_context_chunks]

        # Format prompt (with profile-aware chunk content limits)
        user_prompt = format_rag_answer_prompt(
            query,
            chunks_to_use,
            max_chunks=profile.max_context_chunks,
            max_chunk_content=profile.max_chunk_content,
            cause_title=cause_title,
        )

        # Initialize cost tracker for Gemini Flash
        cost_tracker = CostTracker(
            provider=LLMProvider.GEMINI_FLASH,
            operation="rag_generation",
            matter_id=matter_id,
        )

        # Get configurable timeout from settings (GEMINI_GENERATION_TIMEOUT env var)
        settings = get_settings()
        generation_timeout = settings.gemini_generation_timeout

        # Generate answer with retries
        last_error = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES + 1):
            try:
                # Select system prompt based on QueryProfile
                system_prompt = SYSTEM_PROMPTS.get(
                    profile.system_prompt_key, RAG_ANSWER_SYSTEM_PROMPT
                )

                gemini_limiter = get_rate_limiter(RateLimitProvider.GEMINI)
                async with gemini_limiter:
                    response = await asyncio.wait_for(
                        self.client.aio.models.generate_content(
                            model=self.model_name,
                            contents=user_prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                            ),
                        ),
                        timeout=generation_timeout,
                    )

                # Extract answer text
                answer_text = response.text.strip()

                # Post-process: Remove "p. ?" patterns that LLM may generate
                # despite instructions not to (FR4: Eliminate "p. ?" output)
                # F6: Narrow patterns to citation contexts only (avoid removing valid content)
                original_text = answer_text

                # Pattern 1: "(Document, p. ?)" -> "(Document)"
                answer_text = re.sub(r",\s*p\.?\s*\?\s*\)", ")", answer_text)

                # Pattern 2: ", p. ?" at end of citation reference (before ] or newline)
                answer_text = re.sub(
                    r",\s*p\.?\s*\?(?=\s*[\]\)]|\s*$|\s*\n)", "", answer_text
                )

                # Pattern 3: "p. ?" after opening paren - "(p. ?)" or "(Doc p. ?)"
                # F6: Only match in parenthetical contexts, not standalone
                answer_text = re.sub(r"(\()\s*p\.?\s*\?", r"\1", answer_text)

                # Pattern 4: "(Document p. ?)" without comma -> "(Document)"
                answer_text = re.sub(r"\s+p\.?\s*\?\s*\)", ")", answer_text)

                # Clean up any double spaces created
                answer_text = re.sub(r"  +", " ", answer_text)

                if original_text != answer_text:
                    logger.info(
                        "rag_postprocess_p_question_cleaned",
                        answer_length=len(answer_text),
                    )

                # Track costs (use actual Gemini token counts with fallback)
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
                    output_tokens = getattr(usage, "candidates_token_count", 0) or 0
                    cached_tokens = getattr(usage, "cached_content_token_count", 0) or 0
                else:
                    input_tokens = estimate_tokens(user_prompt)
                    output_tokens = estimate_tokens(answer_text)
                    cached_tokens = 0
                cost_tracker.add_tokens(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_input_tokens=cached_tokens,
                )
                cost_tracker.log_cost()
                await persist_cost(cost_tracker)

                # Truncate if too long (profile-aware limit)
                effective_max_length = profile.max_answer_length
                if effective_max_length > 0 and len(answer_text) > effective_max_length:
                    answer_text = answer_text[:effective_max_length] + "..."

                generation_time_ms = int((time.time() - start_time) * 1000)

                # Build sources list from chunks used
                sources = [
                    {
                        "document_name": c.get("document_name")
                        or c.get("documentName")
                        or "Unknown",
                        "document_id": c.get("document_id") or c.get("documentId"),
                        "page_number": c.get("page_number") or c.get("pageNumber"),
                        "chunk_id": c.get("chunk_id")
                        or c.get("chunkId")
                        or c.get("id"),
                        "bbox_ids": c.get("bbox_ids"),
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

            except TimeoutError:
                # Gemini call exceeded timeout — don't retry, surface immediately
                generation_time_ms = int((time.time() - start_time) * 1000)
                logger.warning(
                    "rag_generation_timeout",
                    attempt=attempt + 1,
                    timeout_seconds=generation_timeout,
                    generation_time_ms=generation_time_ms,
                )
                raise RAGGenerationTimeoutError(generation_timeout) from None

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for non-retryable errors
                if "api key" in error_str or "authentication" in error_str:
                    raise RAGConfigurationError(
                        f"Gemini authentication failed: {e}"
                    ) from e

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
    matter_id: str | None = None,
    query_profile: QueryProfile | None = None,
    cause_title: str | None = None,
) -> RAGAnswerResult:
    """Convenience function to generate RAG answer.

    Args:
        query: User's question.
        chunks: Retrieved document chunks.
        matter_id: Optional matter ID for cost tracking.
        query_profile: Optional QueryProfile for adaptive parameters.
        cause_title: Optional cause title (party listing) for context grounding.

    Returns:
        RAGAnswerResult with generated answer.
    """
    generator = get_rag_generator()
    return await generator.generate_answer(
        query,
        chunks,
        matter_id=matter_id,
        query_profile=query_profile,
        cause_title=cause_title,
    )
