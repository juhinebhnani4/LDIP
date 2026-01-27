"""OpenAI Embedding Service for RAG pipeline.

This module provides embedding generation for semantic search using
OpenAI's text-embedding-3-small model. Features include:
- Single text and batch embedding generation
- Redis caching with 24-hour TTL
- Circuit breaker protection with retry logic (Story 13.2)
- Rate limiting compliance

CRITICAL: Used in hybrid search for semantic similarity matching.
Fallback: Returns None on circuit open, callers should use BM25 only.
"""

import hashlib
import json
from collections.abc import Sequence

import structlog
from openai import AsyncOpenAI, RateLimitError

from app.core.circuit_breaker import (
    CircuitOpenError,
    CircuitService,
    with_circuit_breaker,
)
from app.core.config import get_settings
from app.services.memory.redis_keys import EMBEDDING_CACHE_TTL, embedding_cache_key

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_MODEL_VERSION = "text-embedding-3-small"  # Story 1.3: Version for storage
EMBEDDING_DIMENSIONS = 1536
MAX_BATCH_SIZE = 100
MAX_TOKENS_PER_REQUEST = 8191  # OpenAI limit for text-embedding-3-small


def get_current_embedding_model_version() -> str:
    """Get the current embedding model version string.

    Story 1.3: Store Embedding Model Version with Vectors

    Returns:
        Current embedding model version (e.g., 'text-embedding-3-small').
    """
    return EMBEDDING_MODEL_VERSION


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

    async def embed_text(self, text: str) -> list[float] | None:
        """Generate embedding for single text with circuit breaker protection.

        Args:
            text: Text content to embed. Must not be empty.

        Returns:
            List of 1536 float values representing the embedding,
            or None if circuit is open (fallback to BM25 only).

        Raises:
            EmbeddingServiceError: If embedding generation fails.
            ValueError: If text is empty.

        Example:
            >>> embedding = await service.embed_text("legal agreement")
            >>> if embedding:
            ...     len(embedding)
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
            # Generate embedding with circuit breaker
            embedding = await self._call_openai_embedding(text)

            # Cache result
            await self._cache_embedding(cache_key_str, embedding)

            logger.info(
                "embedding_generated",
                text_len=len(text),
            )

            return embedding

        except CircuitOpenError as e:
            # Fallback: return None when circuit is open
            # Callers (hybrid search) should use BM25 only
            logger.warning(
                "embedding_circuit_open_fallback",
                text_len=len(text),
                circuit_name=e.circuit_name,
                cooldown_remaining=e.cooldown_remaining,
            )
            return None

        except RateLimitError as e:
            # Fallback: return None when rate limited (quota exceeded)
            # Callers (hybrid search) should use BM25 only
            logger.warning(
                "embedding_rate_limit_fallback",
                text_len=len(text),
                error=str(e)[:200],
            )
            return None

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

    @with_circuit_breaker(CircuitService.OPENAI_EMBEDDINGS)
    async def _call_openai_embedding(self, text: str) -> list[float]:
        """Call OpenAI API with circuit breaker protection.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.
        """
        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        return response.data[0].embedding

    async def embed_batch(
        self,
        texts: Sequence[str],
        skip_empty: bool = True,
    ) -> list[list[float] | None]:
        """Generate embeddings for batch of texts with circuit breaker protection.

        Processes up to MAX_BATCH_SIZE texts in a single API call.
        Empty texts are either skipped or raise an error based on skip_empty.

        Args:
            texts: Sequence of text strings to embed.
            skip_empty: If True, empty strings return None. If False,
                raises ValueError for empty strings.

        Returns:
            List of embeddings (or None for empty texts if skip_empty=True).
            Returns all None if circuit is open (fallback to BM25 only).
            Results are in the same order as input texts.

        Raises:
            EmbeddingServiceError: If embedding generation fails.
            ValueError: If batch size exceeds limit or empty text with skip_empty=False.

        Example:
            >>> embeddings = await service.embed_batch(["text1", "text2"])
            >>> len(embeddings)
            2
            >>> if embeddings[0]:
            ...     len(embeddings[0])
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
            # Generate embeddings in batch with circuit breaker
            embeddings = await self._call_openai_batch_embedding(valid_texts)

            # Map back to original indices
            results: list[list[float] | None] = [None] * len(texts)

            for i, embedding in enumerate(embeddings):
                original_idx = valid_indices[i]
                results[original_idx] = embedding

            logger.info(
                "batch_embeddings_generated",
                batch_size=len(texts),
                valid_count=len(valid_texts),
            )

            return results

        except CircuitOpenError as e:
            # Fallback: return all None when circuit is open
            logger.warning(
                "batch_embedding_circuit_open_fallback",
                batch_size=len(texts),
                circuit_name=e.circuit_name,
                cooldown_remaining=e.cooldown_remaining,
            )
            return [None] * len(texts)

        except RateLimitError as e:
            # Fallback: return all None when rate limited (quota exceeded)
            logger.warning(
                "batch_embedding_rate_limit_fallback",
                batch_size=len(texts),
                error=str(e)[:200],
            )
            return [None] * len(texts)

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

    @with_circuit_breaker(CircuitService.OPENAI_EMBEDDINGS)
    async def _call_openai_batch_embedding(
        self, texts: list[str]
    ) -> list[list[float]]:
        """Call OpenAI batch API with circuit breaker protection.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors.
        """
        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        return [data.embedding for data in response.data]


_embedding_service_instance: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service instance.

    Attempts to initialize with Redis caching for cost savings.
    Falls back to non-cached mode if Redis is unavailable.

    Returns:
        EmbeddingService instance (with or without caching).
    """
    global _embedding_service_instance

    if _embedding_service_instance is not None:
        return _embedding_service_instance

    # Try to get Redis client for caching
    redis_client = None
    try:
        import redis.asyncio as aioredis

        from app.core.config import get_settings

        settings = get_settings()
        if settings.redis_url:
            redis_client = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            logger.info("embedding_service_redis_caching_enabled")
    except Exception as e:
        logger.warning(
            "embedding_service_redis_unavailable",
            error=str(e),
            message="Embedding caching disabled - each request will hit OpenAI API",
        )

    _embedding_service_instance = EmbeddingService(redis_client=redis_client)
    return _embedding_service_instance
