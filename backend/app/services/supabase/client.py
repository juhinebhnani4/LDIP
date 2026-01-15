"""Supabase client configuration and initialization.

SECURITY MODEL (4-Layer Matter Isolation):
- Layer 1: Database RLS (bypassed by service role - intentional)
- Layer 2: Vector namespace isolation (enforced in SQL functions)
- Layer 3: Storage bucket policies (enforced by Supabase)
- Layer 4: Application authorization (FastAPI deps + service validation)

The backend uses service role key which bypasses RLS (Layer 1).
This is intentional because:
1. Celery workers run as background jobs without user JWT context
2. The application layer (Layer 4) handles authorization via:
   - FastAPI dependencies (require_matter_role)
   - Service-level matter_id validation (CRITICAL)
   - API middleware checks

CRITICAL: All services using these clients MUST validate matter_id
ownership before performing operations. See HumanReviewService for
the pattern of validating item.matter_id matches authorized matter.
"""

from functools import lru_cache

import structlog
from supabase import Client, create_client

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Global client instance (lazy initialized)
_supabase_client: Client | None = None


def _create_supabase_client() -> Client | None:
    """Create and configure Supabase client.

    SECURITY: Uses service role key which bypasses RLS (Layer 1).
    All calling code MUST validate matter access at Layer 4.
    This client is for backend services that handle their own authorization.

    Returns:
        Configured Supabase client or None if not configured.
    """
    settings = get_settings()

    # Service role key bypasses RLS - application layer handles authorization
    # CRITICAL: Callers MUST validate matter_id ownership before operations
    key = settings.supabase_service_key or settings.supabase_key

    if not settings.supabase_url or not key:
        logger.warning(
            "supabase_not_configured",
            has_url=bool(settings.supabase_url),
            has_key=bool(key),
        )
        return None

    try:
        client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=key,
        )
        logger.info("supabase_client_created", using_service_key=bool(settings.supabase_service_key))
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
