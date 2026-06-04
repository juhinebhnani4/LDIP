"""Factory for selecting embedding service by provider.

Provides lazy singleton instances per provider to avoid re-initialization.
Mirrors the reranker_factory.py pattern.
"""

from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""
    OPENAI = "openai"
    VOYAGE = "voyage"


# Lazy singleton instances
_instances: dict[EmbeddingProvider, object] = {}


def get_embedding_service(provider: EmbeddingProvider | str | None = None):
    """Get embedding service for the given provider.

    Args:
        provider: 'openai' or 'voyage'. Defaults to 'openai'.

    Returns:
        EmbeddingService or VoyageEmbeddingService instance.
    """
    # Normalize to enum
    if provider is None:
        provider_enum = EmbeddingProvider.OPENAI
    elif isinstance(provider, str):
        try:
            provider_enum = EmbeddingProvider(provider)
        except ValueError:
            logger.warning("unknown_embedding_provider", provider=provider)
            provider_enum = EmbeddingProvider.OPENAI
    else:
        provider_enum = provider

    # Kill switch: force OpenAI when A/B testing is disabled
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.voyage_ab_testing_enabled:
        provider_enum = EmbeddingProvider.OPENAI

    if provider_enum not in _instances:
        if provider_enum == EmbeddingProvider.VOYAGE:
            from app.services.rag.voyage_embedder import get_voyage_embedding_service
            _instances[provider_enum] = get_voyage_embedding_service()
            logger.info("voyage_embedding_service_initialized")
        else:
            from app.services.rag.embedder import (
                get_embedding_service as get_openai_service,
            )
            _instances[provider_enum] = get_openai_service()
            logger.info("openai_embedding_service_initialized")

    return _instances[provider_enum]
