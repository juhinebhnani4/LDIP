"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, matters
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
    )

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

    # Future routers (to be implemented in later stories):
    # app.include_router(documents.router, prefix="/api")
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
