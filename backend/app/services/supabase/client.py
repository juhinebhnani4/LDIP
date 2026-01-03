"""Supabase client configuration and initialization."""

from functools import lru_cache

import structlog
from supabase import Client, create_client

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Global client instance (lazy initialized)
_supabase_client: Client | None = None


def _create_supabase_client() -> Client | None:
    """Create and configure Supabase client.

    Returns:
        Configured Supabase client or None if not configured.
    """
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_key:
        logger.warning(
            "supabase_not_configured",
            has_url=bool(settings.supabase_url),
            has_key=bool(settings.supabase_key),
        )
        return None

    try:
        client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_key,
        )
        logger.info("supabase_client_created")
        return client
    except Exception as e:
        logger.error("supabase_client_creation_failed", error=str(e))
        return None


@lru_cache(maxsize=1)
def get_supabase_client() -> Client | None:
    """Get cached Supabase client instance.

    Uses lru_cache to ensure a single client instance is reused
    across the application lifecycle.

    Returns:
        Supabase client or None if not configured.
    """
    return _create_supabase_client()


def get_service_client() -> Client | None:
    """Get Supabase client with service role key for admin operations.

    This client bypasses RLS and should only be used for administrative
    operations like migrations, background jobs, etc.

    SECURITY: Never expose this client to user-facing endpoints.

    Returns:
        Supabase admin client or None if not configured.
    """
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_service_key:
        logger.warning(
            "supabase_service_client_not_configured",
            has_url=bool(settings.supabase_url),
            has_service_key=bool(settings.supabase_service_key),
        )
        return None

    try:
        client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_key,
        )
        logger.info("supabase_service_client_created")
        return client
    except Exception as e:
        logger.error("supabase_service_client_creation_failed", error=str(e))
        return None
