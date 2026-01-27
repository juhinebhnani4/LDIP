"""Cache Control middleware to reduce Supabase egress.

Adds Cache-Control headers to API responses to enable browser caching
for appropriate endpoints.

Story: Reduce cached egress costs
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Endpoints that can be cached (GET only)
# Format: (path_pattern, max_age_seconds, stale_while_revalidate_seconds)
CACHEABLE_ENDPOINTS = [
    # Health endpoints - cache for 30 seconds
    ("/api/health", 30, 60),
    ("/api/health/circuits", 30, 60),

    # Static-ish data endpoints - cache for 60 seconds
    ("/api/matters/{matter_id}/entities", 60, 120),
    ("/api/matters/{matter_id}/timeline/stats", 60, 120),
    ("/api/matters/{matter_id}/citations/acts/discovery", 60, 120),

    # Job stats - cache for 5 seconds (frequently polled)
    ("/api/jobs/matters/{matter_id}/stats", 5, 10),

    # Summary data - cache for 2 minutes (rarely changes)
    ("/api/matters/{matter_id}/summary", 120, 300),

    # Timeline events - cache for 30 seconds
    ("/api/matters/{matter_id}/timeline", 30, 60),

    # Document list - cache for 10 seconds
    ("/api/matters/{matter_id}/documents", 10, 30),
]

# Endpoints that should NEVER be cached (sensitive or dynamic)
NO_CACHE_ENDPOINTS = [
    "/api/chat",
    "/api/session",
    "/api/users/me",
    "/api/auth",
    "/ws",
]


def match_path_pattern(path: str, pattern: str) -> bool:
    """Check if path matches pattern with {param} placeholders."""
    path_parts = path.strip("/").split("/")
    pattern_parts = pattern.strip("/").split("/")

    if len(path_parts) != len(pattern_parts):
        return False

    for path_part, pattern_part in zip(path_parts, pattern_parts, strict=False):
        if pattern_part.startswith("{") and pattern_part.endswith("}"):
            # Parameter placeholder - matches anything
            continue
        if path_part != pattern_part:
            return False

    return True


def get_cache_settings(path: str) -> tuple[int, int] | None:
    """Get cache settings for a path.

    Returns:
        Tuple of (max_age, stale_while_revalidate) or None if not cacheable.
    """
    # Check no-cache list first
    for no_cache_path in NO_CACHE_ENDPOINTS:
        if path.startswith(no_cache_path):
            return None

    # Check cacheable endpoints
    for pattern, max_age, stale in CACHEABLE_ENDPOINTS:
        if match_path_pattern(path, pattern):
            return (max_age, stale)

    return None


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Middleware to add Cache-Control headers to GET responses.

    This helps reduce egress by allowing browsers to cache responses
    for appropriate endpoints.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only cache GET requests
        if request.method != "GET":
            return response

        # Skip if response already has Cache-Control
        if "cache-control" in response.headers:
            return response

        # Get cache settings for this path
        cache_settings = get_cache_settings(request.url.path)

        if cache_settings:
            max_age, stale = cache_settings
            # Private: user-specific, must revalidate after max-age
            # stale-while-revalidate: serve stale while fetching fresh
            response.headers["Cache-Control"] = (
                f"private, max-age={max_age}, stale-while-revalidate={stale}"
            )
        else:
            # Default: no caching for unspecified endpoints
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response
