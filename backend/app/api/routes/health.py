"""Health check endpoints (Story 13.2 - Circuit Breaker Status)."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from app.api.deps import AuthenticatedUser, get_current_user, get_db
from app.core.circuit_breaker import (
    CircuitService,
    get_all_circuits_status,
    get_circuit_registry,
    get_circuit_status,
)
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


# =============================================================================
# Circuit Breaker Status Endpoints (Story 13.2)
# =============================================================================


@router.get("/circuits")
async def get_circuits_status() -> dict[str, Any]:
    """Get status of all circuit breakers.

    Returns the current state and statistics for each external service
    circuit breaker (OpenAI, Gemini, Cohere, DocumentAI).

    Returns:
        Circuit breaker status for all services.

    Example response:
        {
            "data": {
                "circuits": [
                    {
                        "circuit_name": "openai_embeddings",
                        "state": "closed",
                        "failure_count": 0,
                        "success_count": 42,
                        "last_failure": null,
                        "cooldown_remaining": 0,
                        "config": {
                            "failure_threshold": 5,
                            "recovery_timeout": 60,
                            "timeout_seconds": 30
                        }
                    },
                    ...
                ],
                "summary": {
                    "total": 5,
                    "open": 0,
                    "closed": 5,
                    "half_open": 0
                }
            }
        }
    """
    circuits = get_all_circuits_status()

    # Calculate summary
    states = [c.get("state", "unknown") for c in circuits]
    summary = {
        "total": len(circuits),
        "open": states.count("open"),
        "closed": states.count("closed"),
        "half_open": states.count("half_open"),
    }

    logger.debug(
        "circuits_status_requested",
        circuit_count=len(circuits),
        open_count=summary["open"],
    )

    return {
        "data": {
            "circuits": circuits,
            "summary": summary,
        }
    }


@router.get("/circuits/{service_name}")
async def get_circuit_status_by_name(service_name: str) -> dict[str, Any]:
    """Get status of a specific circuit breaker.

    Args:
        service_name: Service identifier (openai_embeddings, openai_chat,
                      gemini_flash, cohere_rerank, documentai_ocr).

    Returns:
        Circuit breaker status for the specified service.

    Raises:
        400: If service_name is not a valid circuit service.
    """
    # Validate service name
    try:
        service = CircuitService(service_name)
    except ValueError:
        valid_services = [s.value for s in CircuitService]
        return {
            "error": {
                "code": "INVALID_SERVICE",
                "message": f"Invalid service name: {service_name}",
                "valid_services": valid_services,
            }
        }

    status = get_circuit_status(service)

    logger.debug(
        "circuit_status_requested",
        service=service_name,
        state=status.get("state"),
    )

    return {"data": status}


@router.post("/circuits/{service_name}/reset")
async def reset_circuit(
    service_name: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Reset a circuit breaker to closed state.

    This endpoint manually resets a circuit breaker, allowing requests
    to resume. Requires authentication. Use with caution - only reset
    if you've verified the external service has recovered.

    Args:
        service_name: Service identifier to reset.

    Returns:
        New circuit status after reset.
    """
    # Validate service name
    try:
        service = CircuitService(service_name)
    except ValueError:
        valid_services = [s.value for s in CircuitService]
        return {
            "error": {
                "code": "INVALID_SERVICE",
                "message": f"Invalid service name: {service_name}",
                "valid_services": valid_services,
            }
        }

    registry = get_circuit_registry()
    registry.reset(service)

    status = get_circuit_status(service)

    logger.info(
        "circuit_manually_reset",
        service=service_name,
        user_id=current_user.id,
    )

    return {
        "data": {
            "message": f"Circuit {service_name} reset to closed state",
            "status": status,
        }
    }
