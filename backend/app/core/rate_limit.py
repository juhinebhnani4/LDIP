"""Rate limiting configuration for API endpoints.

Uses slowapi for request rate limiting to prevent abuse.
Configured to use in-memory storage by default, with Redis
support available for distributed deployments.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def _get_rate_limit_key(request) -> str:
    """Get rate limit key from request.

    Uses user_id from auth if available, otherwise falls back to IP.
    This ensures authenticated users get per-user limits.

    Args:
        request: FastAPI request object.

    Returns:
        Rate limit key string.
    """
    # Try to get user_id from request state (set by auth middleware)
    if hasattr(request.state, "user_id") and request.state.user_id:
        return f"user:{request.state.user_id}"

    # Fall back to IP address
    return get_remote_address(request)


# Create limiter instance
# Uses in-memory storage by default, Redis URL can be configured
settings = get_settings()
storage_uri = settings.redis_url if hasattr(settings, "redis_url") and settings.redis_url else "memory://"

limiter = Limiter(
    key_func=_get_rate_limit_key,
    storage_uri=storage_uri,
    default_limits=["1000/hour"],  # Default rate limit for all endpoints
)


# Rate limit decorators for different endpoint types
# Human review endpoints - more restrictive to prevent bulk manipulation
HUMAN_REVIEW_RATE_LIMIT = "30/minute"  # 30 submissions per minute per user

# Search endpoints - moderate limits
SEARCH_RATE_LIMIT = "60/minute"

# Read-only endpoints - higher limits
READ_RATE_LIMIT = "120/minute"
