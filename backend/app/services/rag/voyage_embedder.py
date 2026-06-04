"""Voyage AI Embedding Service for RAG pipeline.

Mirrors OpenAI EmbeddingService structure but uses Voyage AI's voyage-law-2
model (1024 dimensions) optimized for legal text.

Features:
- Single text and batch embedding generation
- Redis caching with 24-hour TTL (separate cache keys from OpenAI)
- Circuit breaker protection with retry logic
- Rate limiting compliance

CRITICAL: Used in hybrid search for semantic similarity matching.
Fallback: Returns None on circuit open, callers should use BM25 only.
"""

import asyncio
import hashlib
import json
from collections.abc import Sequence

import structlog

from app.core.circuit_breaker import (
    CircuitOpenError,
    CircuitService,
    with_circuit_breaker,
)
from app.core.config import get_settings
from app.core.cost_tracking import CostTracker, LLMProvider, persist_cost
from app.services.memory.redis_keys import EMBEDDING_CACHE_TTL

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

VOYAGE_EMBEDDING_MODEL = "voyage-law-2"
VOYAGE_EMBEDDING_MODEL_VERSION = "voyage-law-2"
VOYAGE_EMBEDDING_DIMENSIONS = 1024
VOYAGE_MAX_BATCH_SIZE = 128  # Voyage allows up to 128 texts per batch
VOYAGE_EMBED_TIMEOUT_SECONDS = 30


def voyage_embedding_cache_key(text_hash: str) -> str:
    """Generate Redis key for cached Voyage embeddings.

    Uses 'voyage:' prefix to avoid collisions with OpenAI cache keys.
    """
    return f"voyage:emb:{text_hash}"


class VoyageEmbeddingService:
    """Service for generating Voyage AI embeddings with caching.

    Uses voyage-law-2 (1024 dimensions) optimized for legal text.
    Redis caching with separate key prefix from OpenAI embeddings.
    """

    def __init__(self, redis_client=None):
        settings = get_settings()
        self._api_key = settings.voyage_api_key
        self._redis = redis_client
        self._client = None

    @property
    def client(self):
        """Get Voyage client (lazy initialization)."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("Voyage API key not configured")
            import voyageai

            self._client = voyageai.Client(api_key=self._api_key)
        return self._client

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def _get_cached(self, cache_key: str) -> list[float] | None:
        if self._redis is None:
            return None
        try:
            cached = await self._redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(
                "voyage_embedding_cache_get_failed", cache_key=cache_key, error=str(e)
            )
        return None

    async def _cache_embedding(self, cache_key: str, embedding: list[float]) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.setex(
                cache_key, EMBEDDING_CACHE_TTL, json.dumps(embedding)
            )
        except Exception as e:
            logger.warning(
                "voyage_embedding_cache_set_failed", cache_key=cache_key, error=str(e)
            )

    async def embed_text(
        self, text: str, matter_id: str | None = None
    ) -> list[float] | None:
        """Generate embedding for single text with circuit breaker protection.

        Args:
            text: Text content to embed. Must not be empty.
            matter_id: Optional matter UUID for cost attribution.

        Returns:
            List of 1024 float values, or None if circuit is open.
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        text = text.strip()

        # Check cache first (Voyage-specific key)
        text_hash = self._hash_text(text)
        cache_key = voyage_embedding_cache_key(text_hash)
        cached = await self._get_cached(cache_key)
        if cached:
            logger.debug("voyage_embedding_cache_hit", text_len=len(text))
            return cached

        try:
            embedding = await self._call_voyage_embedding(text, matter_id=matter_id)
            await self._cache_embedding(cache_key, embedding)
            logger.info("voyage_embedding_generated", text_len=len(text))
            return embedding

        except CircuitOpenError as e:
            logger.warning(
                "voyage_embedding_circuit_open_fallback",
                text_len=len(text),
                circuit_name=e.circuit_name,
                cooldown_remaining=e.cooldown_remaining,
            )
            return None

        except Exception as e:
            logger.error(
                "voyage_embedding_generation_failed",
                text_len=len(text),
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def _do_embed(
        self, texts: list[str], input_type: str = "query"
    ) -> list[list[float]]:
        """Execute synchronous Voyage embedding API call."""
        result = self.client.embed(
            texts=texts,
            model=VOYAGE_EMBEDDING_MODEL,
            input_type=input_type,
        )
        return result.embeddings

    @with_circuit_breaker(
        CircuitService.VOYAGE_EMBEDDINGS, timeout_override=VOYAGE_EMBED_TIMEOUT_SECONDS
    )
    async def _call_voyage_embedding(
        self,
        text: str,
        matter_id: str | None = None,
    ) -> list[float]:
        """Call Voyage API with circuit breaker protection for single text."""
        tracker = CostTracker(
            provider=LLMProvider.VOYAGE_EMBEDDING_LAW2,
            operation="embedding_single",
            matter_id=matter_id,
        )
        embeddings = await asyncio.to_thread(
            self._do_embed,
            [text],
            "query",
        )
        # Voyage charges per token, estimate ~1 token per 4 chars
        estimated_tokens = max(1, len(text) // 4)
        tracker.add_tokens(input_tokens=estimated_tokens)
        tracker.log_cost()
        await persist_cost(tracker)
        return embeddings[0]

    async def embed_batch(
        self,
        texts: Sequence[str],
        skip_empty: bool = True,
        matter_id: str | None = None,
        input_type: str = "document",
    ) -> list[list[float] | None]:
        """Generate embeddings for batch of texts with circuit breaker protection.

        Args:
            texts: Sequence of text strings to embed.
            skip_empty: If True, empty strings return None.
            matter_id: Optional matter UUID for cost attribution.
            input_type: 'query' for search or 'document' for indexing.

        Returns:
            List of embeddings (or None for empty texts).
        """
        if len(texts) > VOYAGE_MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(texts)} exceeds max {VOYAGE_MAX_BATCH_SIZE}"
            )

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
            embeddings = await self._call_voyage_batch_embedding(
                valid_texts,
                input_type=input_type,
                matter_id=matter_id,
            )

            results: list[list[float] | None] = [None] * len(texts)
            for i, embedding in enumerate(embeddings):
                results[valid_indices[i]] = embedding

            logger.info(
                "voyage_batch_embeddings_generated",
                batch_size=len(texts),
                valid_count=len(valid_texts),
            )
            return results

        except CircuitOpenError as e:
            logger.warning(
                "voyage_batch_embedding_circuit_open_fallback",
                batch_size=len(texts),
                circuit_name=e.circuit_name,
                cooldown_remaining=e.cooldown_remaining,
            )
            return [None] * len(texts)

        except Exception as e:
            logger.error(
                "voyage_batch_embedding_generation_failed",
                batch_size=len(texts),
                valid_count=len(valid_texts),
                error=str(e),
                error_type=type(e).__name__,
            )
            return [None] * len(texts)

    @with_circuit_breaker(
        CircuitService.VOYAGE_EMBEDDINGS, timeout_override=VOYAGE_EMBED_TIMEOUT_SECONDS
    )
    async def _call_voyage_batch_embedding(
        self,
        texts: list[str],
        input_type: str = "document",
        matter_id: str | None = None,
    ) -> list[list[float]]:
        """Call Voyage batch API with circuit breaker protection."""
        tracker = CostTracker(
            provider=LLMProvider.VOYAGE_EMBEDDING_LAW2,
            operation="embedding_batch",
            matter_id=matter_id,
        )
        embeddings = await asyncio.to_thread(
            self._do_embed,
            texts,
            input_type,
        )
        # Estimate tokens
        estimated_tokens = sum(max(1, len(t) // 4) for t in texts)
        tracker.add_tokens(input_tokens=estimated_tokens)
        tracker.log_cost()
        await persist_cost(tracker)
        return embeddings


# =============================================================================
# Singleton
# =============================================================================

_voyage_embedding_service_instance: VoyageEmbeddingService | None = None


def get_voyage_embedding_service() -> VoyageEmbeddingService:
    """Get singleton Voyage embedding service instance."""
    global _voyage_embedding_service_instance

    if _voyage_embedding_service_instance is not None:
        return _voyage_embedding_service_instance

    redis_client = None
    try:
        import redis.asyncio as aioredis

        from app.core.config import get_settings

        settings = get_settings()
        if settings.redis_url:
            redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
            logger.info("voyage_embedding_service_redis_caching_enabled")
    except Exception as e:
        logger.warning(
            "voyage_embedding_service_redis_unavailable",
            error=str(e),
        )

    _voyage_embedding_service_instance = VoyageEmbeddingService(
        redis_client=redis_client
    )
    return _voyage_embedding_service_instance
