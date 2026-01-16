"""Rate limiting configuration for API endpoints (Story 13.3).

Uses slowapi for request rate limiting to prevent abuse.
Configured to use in-memory storage by default, with Redis
support available for distributed deployments.

Rate Limit Tiers:
- CRITICAL: LLM/chat/export endpoints (30/min) - expensive API calls
- SEARCH: Vector search endpoints (60/min) - moderate compute
- STANDARD: CRUD operations (100/min) - architecture spec default
- READONLY: Read-only dashboard/stats (120/min) - higher tolerance
- HEALTH: Monitoring endpoints (300/min) - high frequency polling
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.correlation import get_correlation_id

if TYPE_CHECKING:
    from starlette.requests import Request as StarletteRequest

logger = structlog.get_logger(__name__)

# Track if we're in degraded mode (Redis unavailable)
_redis_degraded = False


def _get_rate_limit_key(request: StarletteRequest) -> str:
    """Get rate limit key from request.

    Uses user_id from auth if available, otherwise falls back to IP.
    This ensures authenticated users get per-user limits.

    Priority:
    1. request.state.user_id (set by validate_matter_access or explicitly)
    2. structlog context user_id (set by get_current_user in security.py)
    3. IP address fallback for unauthenticated requests

    Args:
        request: FastAPI request object.

    Returns:
        Rate limit key string.
    """
    # Try to get user_id from request state (set by validate_matter_access)
    if hasattr(request.state, "user_id") and request.state.user_id:
        return f"user:{request.state.user_id}"

    # Try to get user_id from structlog context (set by get_current_user)
    try:
        ctx = structlog.contextvars.get_contextvars()
        if ctx and "user_id" in ctx and ctx["user_id"]:
            return f"user:{ctx['user_id']}"
    except Exception:
        pass

    # Fall back to IP address
    return get_remote_address(request)


# Create limiter instance with graceful Redis fallback
# Uses Redis storage when REDIS_URL is configured and accessible, otherwise in-memory
settings = get_settings()


def _create_limiter(storage_uri: str) -> Limiter:
    """Create a limiter with the specified storage URI."""
    return Limiter(
        key_func=_get_rate_limit_key,
        storage_uri=storage_uri,
        default_limits=["1000/hour"],  # Default rate limit for all endpoints
    )


def _get_limiter_with_fallback() -> tuple[Limiter, str]:
    """Get limiter instance with graceful Redis fallback.

    Attempts to use Redis if configured. If Redis connection fails,
    falls back to in-memory storage and logs a warning.

    Returns:
        Tuple of (Limiter instance, storage_uri used).
    """
    global _redis_degraded

    if not settings.redis_url:
        return _create_limiter("memory://"), "memory://"

    # Try Redis first
    try:
        import redis
        # Test Redis connectivity
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        _redis_degraded = False
        logger.info("rate_limiter_storage", storage="redis", url=settings.redis_url)
        return _create_limiter(settings.redis_url), settings.redis_url
    except Exception as e:
        _redis_degraded = True
        logger.warning(
            "rate_limiter_redis_unavailable",
            error=str(e),
            fallback="memory",
            message="Rate limiter falling back to in-memory storage. Rate limits will not be shared across instances.",
        )
        return _create_limiter("memory://"), "memory://"


limiter, storage_uri = _get_limiter_with_fallback()


# =============================================================================
# Rate Limit Tier Constants (from config with fallbacks)
# =============================================================================

def _get_rate_limit_str(value: int) -> str:
    """Convert rate limit integer to slowapi format string."""
    return f"{value}/minute"


# Critical endpoints: LLM, chat (expensive operations)
CRITICAL_RATE_LIMIT = _get_rate_limit_str(settings.rate_limit_critical)  # 30/minute

# Export endpoints: PDF generation (most resource-intensive)
EXPORT_RATE_LIMIT = _get_rate_limit_str(settings.rate_limit_export)  # 20/minute

# Search endpoints: vector search, RAG (moderate compute)
SEARCH_RATE_LIMIT = _get_rate_limit_str(settings.rate_limit_search)  # 60/minute

# Standard CRUD endpoints: matters, documents, entities (architecture default)
STANDARD_RATE_LIMIT = _get_rate_limit_str(settings.rate_limit_default)  # 100/minute

# Read-only endpoints: dashboard, activity, stats (higher tolerance)
READONLY_RATE_LIMIT = _get_rate_limit_str(settings.rate_limit_readonly)  # 120/minute

# Health/monitoring endpoints (high frequency polling)
HEALTH_RATE_LIMIT = _get_rate_limit_str(settings.rate_limit_health)  # 300/minute

# Legacy aliases for backward compatibility
HUMAN_REVIEW_RATE_LIMIT = CRITICAL_RATE_LIMIT  # 30/minute - OCR validation
READ_RATE_LIMIT = READONLY_RATE_LIMIT  # 120/minute


# =============================================================================
# Custom 429 Response Handler
# =============================================================================

def _parse_retry_after(exception: RateLimitExceeded) -> int:
    """Parse retry-after seconds from rate limit exception.

    Args:
        exception: The RateLimitExceeded exception.

    Returns:
        Seconds until limit resets (minimum 1).
    """
    try:
        # slowapi includes retry_after in the exception detail
        if hasattr(exception, "detail") and isinstance(exception.detail, str):
            # Format: "Rate limit exceeded: X per Y second(s)"
            # Extract the window from the limit string
            detail = exception.detail
            if "minute" in detail.lower():
                return 60
            elif "hour" in detail.lower():
                return 3600
            elif "second" in detail.lower():
                # Extract the number
                parts = detail.split()
                for i, part in enumerate(parts):
                    if part.lower().startswith("second") and i > 0:
                        try:
                            return int(parts[i - 1])
                        except ValueError:
                            pass
                return 1
    except Exception:
        pass
    # Default to 60 seconds for per-minute limits
    return 60


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors.

    Returns a structured error response following project API conventions
    with rate limit headers for client consumption.

    Args:
        request: The FastAPI request object.
        exc: The RateLimitExceeded exception.

    Returns:
        JSONResponse with 429 status and rate limit headers.
    """
    # Parse limit details from exception
    retry_after = _parse_retry_after(exc)
    reset_time = datetime.now(UTC).timestamp() + retry_after
    reset_at_iso = datetime.fromtimestamp(reset_time, tz=UTC).isoformat()

    # Extract limit from exception detail (e.g., "30 per 1 minute")
    limit = 100  # Default
    try:
        if hasattr(exc, "detail") and isinstance(exc.detail, str):
            # Parse "Rate limit exceeded: 30 per 1 minute"
            parts = exc.detail.split()
            for i, part in enumerate(parts):
                if part == "per" and i > 0:
                    limit = int(parts[i - 1])
                    break
    except (ValueError, IndexError):
        pass

    # Get user identifier for logging
    user_id = None
    if hasattr(request.state, "user_id"):
        user_id = request.state.user_id

    # Log the rate limit violation with correlation
    logger.warning(
        "rate_limit_exceeded",
        user_id=user_id,
        endpoint=request.url.path,
        method=request.method,
        limit=limit,
        retry_after=retry_after,
        client_ip=get_remote_address(request),
        correlation_id=get_correlation_id(),
    )

    # Build structured error response per project-context.md
    error_body = {
        "error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
            "details": {
                "limit": limit,
                "remaining": 0,
                "reset_at": reset_at_iso,
                "retry_after": retry_after,
            },
        }
    }

    # Include rate limit headers per HTTP standards
    headers = {
        "Retry-After": str(retry_after),
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": str(int(reset_time)),
    }

    return JSONResponse(
        status_code=429,
        content=error_body,
        headers=headers,
    )


# =============================================================================
# Rate Limit Status Helpers
# =============================================================================

def get_rate_limit_status(request: Request) -> dict:
    """Get current rate limit status for the requesting user.

    Args:
        request: The FastAPI request object.

    Returns:
        Dictionary with rate limit status per tier.
    """
    key = _get_rate_limit_key(request)

    # Return tier configuration (actual usage tracking is in Redis/memory)
    return {
        "key": key,
        "tiers": {
            "critical": {
                "limit": settings.rate_limit_critical,
                "window": "minute",
                "description": "LLM, chat, export endpoints",
            },
            "search": {
                "limit": settings.rate_limit_search,
                "window": "minute",
                "description": "Vector search endpoints",
            },
            "standard": {
                "limit": settings.rate_limit_default,
                "window": "minute",
                "description": "CRUD operations",
            },
            "readonly": {
                "limit": settings.rate_limit_readonly,
                "window": "minute",
                "description": "Dashboard, stats endpoints",
            },
            "health": {
                "limit": settings.rate_limit_health,
                "window": "minute",
                "description": "Monitoring endpoints",
            },
        },
        "storage": "redis" if "redis" in storage_uri else "memory",
        "degraded": _redis_degraded,
    }
