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
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Header name for correlation ID
CORRELATION_HEADER = "X-Correlation-ID"


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
        finally:
            # Clear context after request to prevent leakage to other requests
            structlog.contextvars.unbind_contextvars("correlation_id")


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
