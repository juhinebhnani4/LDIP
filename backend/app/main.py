"""FastAPI application entry point.

Updated: 2026-01-26 15:30 - Force reload for timeline event_type fix v2
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import (
    activity,
    anomalies,
    bounding_boxes,
    chat,
    chunks,
    citations,
    contradiction,
    dashboard,
    documents,
    entities,
    evaluation,
    exports,
    global_search,
    health,
    inspector,
    jobs,
    library,
    matters,
    notifications,
    ocr_validation,
    search,
    session,
    summary,
    tables,
    timeline,
    users,
    verifications,
    ws,
)
from app.api.routes.admin import pipeline as admin_pipeline
from app.core.config import get_settings
from app.core.correlation import CorrelationMiddleware
from app.core.logging import configure_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

# Configure structured logging on module load
configure_logging()

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("application_starting", app_name=app.title)

    # Clear LRU caches on startup to ensure fresh instances
    from app.engines.orchestrator.adapters import get_cached_adapter
    from app.engines.orchestrator.aggregator import get_result_aggregator
    from app.engines.orchestrator.streaming import reset_streaming_orchestrator

    get_cached_adapter.cache_clear()
    get_result_aggregator.cache_clear()
    reset_streaming_orchestrator()
    logger.info("singleton_caches_cleared")

    settings = get_settings()
    if not settings.is_configured:
        logger.warning(
            "application_not_fully_configured",
            message="Supabase credentials not set. Some features will be unavailable.",
        )

    # Validate Gemini configuration (required for entity extraction)
    if not settings.is_gemini_configured:
        logger.warning(
            "gemini_not_configured",
            message="GEMINI_API_KEY not set. Entity extraction will be unavailable.",
            hint="Set GEMINI_API_KEY in .env file",
        )
    else:
        logger.info(
            "gemini_configured",
            model=settings.gemini_model,
        )

    # Validate OpenAI configuration (required for embeddings and LLM)
    if not settings.is_openai_configured:
        logger.warning(
            "openai_not_configured",
            message="OPENAI_API_KEY not set. Embeddings and chat will be unavailable.",
            hint="Set OPENAI_API_KEY in .env file",
        )

    # Start Redis-to-WebSocket bridge for real-time streaming
    from app.api.ws.redis_bridge import get_redis_bridge

    redis_bridge = get_redis_bridge()
    try:
        await redis_bridge.start()
        logger.info("redis_websocket_bridge_started")
    except Exception as e:
        # Log but don't fail startup - WebSocket is non-critical
        logger.warning(
            "redis_websocket_bridge_start_failed",
            error=str(e),
            hint="WebSocket streaming will be unavailable",
        )

    yield

    # Shutdown
    logger.info("application_shutting_down")

    # Stop Redis bridge
    try:
        await redis_bridge.stop()
        logger.info("redis_websocket_bridge_stopped")
    except Exception as e:
        logger.warning("redis_websocket_bridge_stop_failed", error=str(e))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Legal Document Intelligence Platform - Backend API",
        version=settings.api_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
        swagger_ui_init_oauth={
            "usePkceWithAuthorizationCodeGrant": True,
        },
    )

    # Custom OpenAPI schema with Bearer token auth
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=settings.app_name,
            version=settings.api_version,
            description="Legal Document Intelligence Platform - Backend API",
            routes=app.routes,
        )
        # Override security schemes - rename HTTPBearer to BearerAuth
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter your Supabase JWT token",
            }
        }
        # Apply security globally to all endpoints
        openapi_schema["security"] = [{"BearerAuth": []}]
        # Fix per-endpoint security to use BearerAuth instead of HTTPBearer
        for path in openapi_schema.get("paths", {}).values():
            for operation in path.values():
                if isinstance(operation, dict) and "security" in operation:
                    operation["security"] = [{"BearerAuth": []}]
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # Add correlation ID middleware for distributed tracing (Story 13.1)
    # Middleware execution order is LIFO (last added runs first)
    # So we add CorrelationMiddleware first, then CORS last to ensure
    # CORS headers are added to ALL responses including auth errors
    app.add_middleware(CorrelationMiddleware)

    # Configure CORS - MUST be added LAST to run FIRST
    # This ensures CORS headers are added even to 401/403/500 error responses
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],  # Allow frontend to access correlation ID
    )

    # Configure rate limiting with custom 429 handler (Story 13.3)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Global exception handlers for consistent error responses (P3.2)
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle HTTP exceptions with structured error response."""
        correlation_id = getattr(request.state, "correlation_id", None)

        # If detail is already structured (from AppException), use it
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            content = exc.detail
            if correlation_id:
                content["error"]["details"] = content["error"].get("details", {})
                content["error"]["details"]["correlationId"] = correlation_id
        else:
            # Wrap unstructured detail in standard format
            content = {
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail) if exc.detail else "An error occurred",
                    "details": {"correlationId": correlation_id} if correlation_id else {},
                }
            }

        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors with field-level details."""
        correlation_id = getattr(request.state, "correlation_id", None)

        # Extract field-level errors
        field_errors = []
        for error in exc.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            field_errors.append({
                "field": field_path,
                "message": error["msg"],
                "type": error["type"],
            })

        content = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {
                    "fields": field_errors,
                },
            }
        }
        if correlation_id:
            content["error"]["details"]["correlationId"] = correlation_id

        logger.warning(
            "validation_error",
            correlation_id=correlation_id,
            path=str(request.url.path),
            errors=field_errors,
        )

        return JSONResponse(status_code=422, content=content)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler for unhandled exceptions."""
        correlation_id = getattr(request.state, "correlation_id", None)

        # Log full traceback for debugging
        logger.exception(
            "unhandled_exception",
            correlation_id=correlation_id,
            path=str(request.url.path),
            method=request.method,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

        # Return generic error to client (don't expose internals)
        content = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            }
        }
        if correlation_id:
            content["error"]["details"]["correlationId"] = correlation_id

        return JSONResponse(status_code=500, content=content)

    # Include routers
    app.include_router(health.router, prefix="/api")
    app.include_router(matters.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(documents.matters_router, prefix="/api")
    app.include_router(ocr_validation.router, prefix="/api")
    app.include_router(ocr_validation.matters_router, prefix="/api")
    app.include_router(bounding_boxes.router, prefix="/api")
    app.include_router(bounding_boxes.chunks_router, prefix="/api")
    app.include_router(chunks.router, prefix="/api")
    app.include_router(chunks.chunks_router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(entities.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(citations.router, prefix="/api")
    app.include_router(library.router, prefix="/api")
    app.include_router(library.matters_router, prefix="/api")
    app.include_router(timeline.router, prefix="/api")
    app.include_router(anomalies.router, prefix="/api")
    app.include_router(contradiction.router, prefix="/api")
    app.include_router(verifications.router, prefix="/api")
    app.include_router(exports.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(session.router, prefix="/api")
    app.include_router(summary.router, prefix="/api")
    app.include_router(activity.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(notifications.router, prefix="/api")
    app.include_router(global_search.router, prefix="/api")
    app.include_router(tables.router, prefix="/api")
    app.include_router(tables.document_tables_router, prefix="/api")
    app.include_router(evaluation.router, prefix="/api")
    app.include_router(inspector.router, prefix="/api")
    app.include_router(users.router)

    # Admin routes (require admin access)
    app.include_router(admin_pipeline.router, prefix="/api")

    # WebSocket routes for real-time streaming
    app.include_router(ws.router, prefix="/api")

    return app


# Create the application instance
app = create_app()


# Root endpoint
@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        Welcome message with API documentation link.
    """
    payload: dict[str, str] = {
        "message": "LDIP Backend API",
        "health": "/api/health",
    }

    if get_settings().debug:
        payload["docs"] = "/docs"

    return payload
