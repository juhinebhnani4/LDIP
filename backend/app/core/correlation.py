"""Correlation ID middleware for request tracing (Story 13.1).

This middleware assigns a unique correlation_id to each request, enabling
distributed tracing across logs. The correlation_id is:

1. Extracted from X-Correlation-ID header (if present)
2. Generated as a new UUID if not present
3. Bound to all logs in the request via structlog.contextvars
4. Returned in response headers for client-side correlation

Usage:
    In main.py, add the middleware to the FastAPI app:

    from app.core.correlation import CorrelationMiddleware
    app.add_middleware(CorrelationMiddleware)
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Header name for correlation ID
CORRELATION_HEADER = "X-Correlation-ID"

logger = structlog.get_logger(__name__)


def _is_redis_error(exc: Exception) -> bool:
    """Check if an exception is a Redis error (e.g., Upstash limit exceeded).

    Checks by class name to avoid importing redis at module level.
    """
    exc_module = getattr(type(exc), "__module__", "") or ""
    return "redis" in exc_module.lower()


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns correlation IDs to requests for distributed tracing.

    The correlation_id is bound to structlog's contextvars, making it available
    to all logs within the request lifecycle without explicit passing.

    Attributes:
        dispatch: The middleware dispatch function.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request, adding correlation_id tracking.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware/route handler.

        Returns:
            The response with X-Correlation-ID header added.
        """
        # Extract correlation_id from header or generate a new one
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())

        # Bind correlation_id to structlog contextvars
        # This makes it available to ALL logs within this request
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        try:
            # Process the request
            response = await call_next(request)

            # Include correlation_id in response headers for client-side correlation
            response.headers[CORRELATION_HEADER] = correlation_id

            return response
        except Exception as exc:
            # Catch ALL exceptions before BaseHTTPMiddleware wraps them in
            # ExceptionGroup. Returning a JSONResponse here lets CORS middleware
            # add its headers — a re-raised exception would bypass CORS entirely.

            if _is_redis_error(exc):
                logger.warning(
                    "redis_error_caught_in_middleware",
                    correlation_id=correlation_id,
                    error=str(exc),
                    path=str(request.url.path),
                )
                # Switch rate limiter to in-memory so subsequent requests don't crash
                from app.core.rate_limit import switch_to_memory_limiter

                switch_to_memory_limiter()
                # Update app.state.limiter so slowapi uses the new memory limiter
                from app.core.rate_limit import limiter as updated_limiter

                request.app.state.limiter = updated_limiter

                resp = JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "code": "SERVICE_DEGRADED",
                            "message": "Service temporarily degraded. Please retry.",
                            "details": {"correlationId": correlation_id},
                        }
                    },
                )
                resp.headers[CORRELATION_HEADER] = correlation_id
                return resp

            # Generic catch-all: return 500 JSONResponse instead of re-raising.
            # This prevents ExceptionGroup wrapping which strips CORS headers.
            logger.error(
                "unhandled_error_in_middleware",
                correlation_id=correlation_id,
                error=str(exc),
                error_type=type(exc).__name__,
                path=str(request.url.path),
            )
            resp = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An internal error occurred. Please try again.",
                        "details": {"correlationId": correlation_id},
                    }
                },
            )
            resp.headers[CORRELATION_HEADER] = correlation_id
            return resp
        finally:
            # Clear context after request to prevent leakage to other requests
            structlog.contextvars.unbind_contextvars("correlation_id", "cost_user_id")


def get_correlation_id() -> str | None:
    """Get the current correlation_id from context.

    This can be used by code that needs to access the correlation_id
    programmatically (e.g., for passing to external services).

    Returns:
        The current correlation_id, or None if not in a request context.
    """
    try:
        # Access the current context variables
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("correlation_id")
    except Exception:
        return None


def bind_cost_user_id(user_id: str) -> None:
    """Bind user_id to structlog context for cost attribution (P5).

    Called in chat endpoints so all CostTracker calls within the request
    automatically pick up the user_id without explicit passing.

    Args:
        user_id: Authenticated user's UUID string.
    """
    structlog.contextvars.bind_contextvars(cost_user_id=user_id)


def get_cost_user_id() -> str | None:
    """Get the current cost_user_id from context.

    Returns:
        The user_id bound for cost attribution, or None if not set.
    """
    try:
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("cost_user_id")
    except Exception:
        return None
