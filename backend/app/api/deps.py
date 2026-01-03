"""Dependency injection for API routes."""

from collections.abc import AsyncGenerator
from typing import Any

import structlog

from app.core.config import get_settings
from app.core.security import get_current_user, get_optional_user
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


async def get_db() -> AsyncGenerator[Any, None]:
    """Get database client (Supabase).

    This dependency provides the Supabase client for database operations.
    The client handles connection pooling internally.

    Yields:
        Supabase client instance.
    """
    client = get_supabase_client()
    if client is None:
        logger.warning("supabase_not_configured")
    yield client


# Re-export commonly used dependencies for convenience
__all__ = [
    "get_db",
    "get_settings",
    "get_current_user",
    "get_optional_user",
]
