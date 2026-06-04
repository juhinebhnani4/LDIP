"""Factory for selecting reranker service by provider.

Provides lazy singleton instances per provider to avoid re-initialization.
"""

import structlog

from app.services.rag.reranker_base import RerankProvider

logger = structlog.get_logger(__name__)

# Lazy singleton instances
_instances: dict[RerankProvider, object] = {}


def get_rerank_service(provider: RerankProvider | str | None = None):
    """Get reranker service for the given provider.

    Args:
        provider: 'cohere' or 'voyage'. Defaults to 'cohere'.

    Returns:
        CohereRerankService or VoyageRerankService instance.
    """
    # Normalize to enum
    if provider is None:
        provider_enum = RerankProvider.COHERE
    elif isinstance(provider, str):
        try:
            provider_enum = RerankProvider(provider)
        except ValueError:
            logger.warning("unknown_rerank_provider", provider=provider)
            provider_enum = RerankProvider.COHERE
    else:
        provider_enum = provider

    # Kill switch: force Cohere when A/B testing is disabled
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.voyage_ab_testing_enabled:
        provider_enum = RerankProvider.COHERE

    if provider_enum not in _instances:
        if provider_enum == RerankProvider.VOYAGE:
            from app.services.rag.voyage_reranker import VoyageRerankService

            _instances[provider_enum] = VoyageRerankService()
            logger.info("voyage_rerank_service_initialized")
        else:
            from app.services.rag.reranker import CohereRerankService

            _instances[provider_enum] = CohereRerankService()
            logger.info("cohere_rerank_service_initialized")

    return _instances[provider_enum]
