"""OpenAI Embedding Service for RAG pipeline.

This module provides embedding generation for semantic search using
OpenAI's text-embedding-3-small model. Features include:
- Single text and batch embedding generation
- Redis caching with 24-hour TTL
- Retry logic with exponential backoff
- Rate limiting compliance

CRITICAL: Used in hybrid search for semantic similarity matching.
"""

import hashlib
import json
from functools import lru_cache
from typing import Sequence

import structlog
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.config import get_settings
from app.services.memory.redis_keys import embedding_cache_key, EMBEDDING_CACHE_TTL

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
MAX_BATCH_SIZE = 100
MAX_TOKENS_PER_REQUEST = 8191  # OpenAI limit for text-embedding-3-small


class EmbeddingServiceError(Exception):
    """Base exception for embedding service operations."""

    def __init__(
        self,
        message: str,
        code: str = "EMBEDDING_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class EmbeddingService:
    """Service for generating OpenAI embeddings with caching.

    Uses text-embedding-3-small (1536 dimensions) with Redis caching
    to avoid re-generating embeddings for the same text content.

    Example:
        >>> service = EmbeddingService()
        >>> embedding = await service.embed_text("contract termination clause")
        >>> len(embedding)
        1536
    """

    def __init__(self, redis_client=None):
        """Initialize embedding service.

        Args:
            redis_client: Optional Redis client for caching. If not provided,
                caching is disabled.
        """
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._redis = redis_client

    def _hash_text(self, text: str) -> str:
        """Generate SHA256 hash of text for cache key.

        Args:
            text: Text content to hash.

        Returns:
            Lowercase hex string of SHA256 hash.
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def _get_cached(self, cache_key: str) -> list[float] | None:
        """Get cached embedding from Redis.

        Args:
            cache_key: Redis cache key.

        Returns:
            Cached embedding or None if not found.
        """
        if self._redis is None:
            return None

        try:
            cached = await self._redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(
                "embedding_cache_get_failed",
                cache_key=cache_key,
                error=str(e),
            )

        return None

    async def _cache_embedding(self, cache_key: str, embedding: list[float]) -> None:
        """Cache embedding in Redis.

        Args:
            cache_key: Redis cache key.
            embedding: Embedding vector to cache.
        """
        if self._redis is None:
            return

        try:
            await self._redis.setex(
                cache_key,
                EMBEDDING_CACHE_TTL,
                json.dumps(embedding),
            )
        except Exception as e:
            logger.warning(
                "embedding_cache_set_failed",
                cache_key=cache_key,
                error=str(e),
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for single text.

        Args:
            text: Text content to embed. Must not be empty.

        Returns:
            List of 1536 float values representing the embedding.

        Raises:
            EmbeddingServiceError: If embedding generation fails.
            ValueError: If text is empty.

        Example:
            >>> embedding = await service.embed_text("legal agreement")
            >>> len(embedding)
            1536
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        text = text.strip()

        # Check cache first
        text_hash = self._hash_text(text)
        cache_key_str = embedding_cache_key(text_hash)
        cached = await self._get_cached(cache_key_str)

        if cached:
            logger.debug(
                "embedding_cache_hit",
                text_len=len(text),
            )
            return cached

        try:
            # Generate embedding
            response = await self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
                dimensions=EMBEDDING_DIMENSIONS,
            )

            embedding = response.data[0].embedding

            # Cache result
            await self._cache_embedding(cache_key_str, embedding)

            logger.info(
                "embedding_generated",
                text_len=len(text),
                tokens=response.usage.total_tokens,
            )

            return embedding

        except Exception as e:
            logger.error(
                "embedding_generation_failed",
                text_len=len(text),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmbeddingServiceError(
                message=f"Failed to generate embedding: {e!s}",
                code="EMBEDDING_GENERATION_FAILED",
                is_retryable=True,
            ) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    async def embed_batch(
        self,
        texts: Sequence[str],
        skip_empty: bool = True,
    ) -> list[list[float] | None]:
        """Generate embeddings for batch of texts.

        Processes up to MAX_BATCH_SIZE texts in a single API call.
        Empty texts are either skipped or raise an error based on skip_empty.

        Args:
            texts: Sequence of text strings to embed.
            skip_empty: If True, empty strings return None. If False,
                raises ValueError for empty strings.

        Returns:
            List of embeddings (or None for empty texts if skip_empty=True).
            Results are in the same order as input texts.

        Raises:
            EmbeddingServiceError: If embedding generation fails.
            ValueError: If batch size exceeds limit or empty text with skip_empty=False.

        Example:
            >>> embeddings = await service.embed_batch(["text1", "text2"])
            >>> len(embeddings)
            2
            >>> len(embeddings[0])
            1536
        """
        if len(texts) > MAX_BATCH_SIZE:
            raise ValueError(f"Batch size {len(texts)} exceeds max {MAX_BATCH_SIZE}")

        # Filter and track empty texts
        valid_indices: list[int] = []
        valid_texts: list[str] = []

        for i, text in enumerate(texts):
            if text and text.strip():
                valid_indices.append(i)
                valid_texts.append(text.strip())
            elif not skip_empty:
                raise ValueError(f"Empty text at index {i}")

        if not valid_texts:
            return [None] * len(texts)

        try:
            # Generate embeddings in batch
            response = await self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=valid_texts,
                dimensions=EMBEDDING_DIMENSIONS,
            )

            # Map back to original indices
            results: list[list[float] | None] = [None] * len(texts)

            for i, embedding_data in enumerate(response.data):
                original_idx = valid_indices[i]
                results[original_idx] = embedding_data.embedding

            logger.info(
                "batch_embeddings_generated",
                batch_size=len(texts),
                valid_count=len(valid_texts),
                tokens=response.usage.total_tokens,
            )

            return results

        except Exception as e:
            logger.error(
                "batch_embedding_generation_failed",
                batch_size=len(texts),
                valid_count=len(valid_texts),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmbeddingServiceError(
                message=f"Failed to generate batch embeddings: {e!s}",
                code="BATCH_EMBEDDING_FAILED",
                is_retryable=True,
            ) from e


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service instance.

    Note: This returns an instance without Redis caching.
    For production with caching, create instance with Redis client.

    Returns:
        EmbeddingService instance.
    """
    return EmbeddingService()
