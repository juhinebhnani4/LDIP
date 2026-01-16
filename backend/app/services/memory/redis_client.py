"""Async Redis client for session memory.

Story 7-1: Session Memory Redis Storage

Uses Upstash Redis (HTTP-based, serverless) for session persistence.
Falls back to standard redis-py for local development.

CRITICAL: This is an async client. All operations must be awaited.

Environment Variables:
- UPSTASH_REDIS_REST_URL: Upstash REST API URL (production)
- UPSTASH_REDIS_REST_TOKEN: Upstash auth token (production)
- REDIS_URL: Standard Redis URL for local dev (default: redis://localhost:6379/0)
"""

import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Singleton client instance
_redis_client: Any = None


async def get_redis_client() -> Any:
    """Get or create async Redis client.

    Returns Upstash Redis client for production or redis-py for local.

    Returns:
        Async Redis client instance.

    Raises:
        RuntimeError: If no Redis client can be initialized.
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    # Check for Upstash environment variables first
    upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
    upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

    if upstash_url and upstash_token:
        # Use Upstash Redis (HTTP-based, async)
        try:
            from upstash_redis.asyncio import Redis

            _redis_client = Redis(url=upstash_url, token=upstash_token)
            logger.info(
                "redis_client_initialized",
                type="upstash",
                url=upstash_url[:30] + "..." if len(upstash_url) > 30 else upstash_url,
            )
            return _redis_client
        except ImportError:
            # CRITICAL: If Upstash is configured but library missing, FAIL FAST
            # Do NOT silently fall back to localhost - this causes production data loss
            logger.error(
                "upstash_redis_configured_but_not_installed",
                upstash_url=upstash_url[:30] + "...",
                message="UPSTASH_REDIS_REST_URL is set but upstash-redis package not installed",
            )
            raise RuntimeError(
                "Upstash Redis is configured (UPSTASH_REDIS_REST_URL set) but "
                "upstash-redis package is not installed. Install it with: "
                "pip install upstash-redis"
            )

    # Fallback to standard redis-py for local development
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        import redis.asyncio as redis

        _redis_client = redis.from_url(redis_url, decode_responses=True)
        logger.info(
            "redis_client_initialized",
            type="redis-py",
            url=redis_url[:30] + "..." if len(redis_url) > 30 else redis_url,
        )
        return _redis_client
    except ImportError:
        logger.error(
            "no_redis_client_available",
            message="Install redis or upstash-redis package",
        )
        raise RuntimeError(
            "No Redis client available. Install redis or upstash-redis."
        )


def reset_redis_client() -> None:
    """Reset Redis client singleton.

    Use this for testing to ensure clean state between tests.
    """
    global _redis_client
    _redis_client = None
    logger.debug("redis_client_reset")
