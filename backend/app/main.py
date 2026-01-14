"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.routes import anomalies, bounding_boxes, chunks, citations, contradiction, documents, entities, health, jobs, matters, ocr_validation, search, timeline, verifications
from app.core.config import get_settings
from app.core.logging import configure_logging

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

    settings = get_settings()
    if not settings.is_configured:
        logger.warning(
            "application_not_fully_configured",
            message="Supabase credentials not set. Some features will be unavailable.",
        )

    yield

    # Shutdown
    logger.info("application_shutting_down")


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

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
    app.include_router(timeline.router, prefix="/api")
    app.include_router(anomalies.router, prefix="/api")
    app.include_router(contradiction.router, prefix="/api")
    app.include_router(verifications.router, prefix="/api")

    # Future routers (to be implemented in later stories):
    # app.include_router(engines.router, prefix="/api")
    # app.include_router(chat.router, prefix="/api")

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
