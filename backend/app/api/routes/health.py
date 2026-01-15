"""Health check endpoints."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from app.api.deps import AuthenticatedUser, get_current_user, get_db
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])
logger = structlog.get_logger(__name__)


@router.get("")
async def health_check() -> dict[str, Any]:
    """Basic health check endpoint.

    Returns:
        Health status with version info.
    """
    return {
        "data": {
            "status": "healthy",
            "service": "ldip-backend",
        }
    }


@router.get("/ready")
async def readiness_check(
    settings: Settings = Depends(get_settings),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    """Readiness check with dependency status.

    Checks if the service is ready to accept traffic by verifying
    that all required dependencies are available.

    Returns:
        Detailed readiness status.
    """
    checks: dict[str, bool] = {
        "supabase_configured": settings.is_configured,
        "supabase_connected": db is not None,
    }

    all_healthy = all(checks.values())

    logger.debug("readiness_check", checks=checks, healthy=all_healthy)

    return {
        "data": {
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
        }
    }


@router.get("/live")
async def liveness_check() -> dict[str, Any]:
    """Liveness check endpoint.

    Simple check to verify the service is running.
    Used by orchestration systems to detect crashed processes.

    Returns:
        Simple alive status.
    """
    return {
        "data": {
            "status": "alive",
        }
    }


@router.get("/me")
async def get_authenticated_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Protected endpoint to verify authentication.

    Returns the authenticated user's information from the JWT token.
    Used for testing JWT validation and auth flow.

    Returns:
        Authenticated user information.
    """
    return {
        "data": {
            "user_id": current_user.id,
            "email": current_user.email,
            "role": current_user.role,
        }
    }
