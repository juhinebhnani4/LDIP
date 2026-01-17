"""Health check endpoints (Story 13.2, 13.3 - Circuit Breaker + Rate Limit Status)."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request

from app.api.deps import AuthenticatedUser, get_current_user, get_db
from app.core.circuit_breaker import (
    CircuitService,
    get_all_circuits_status,
    get_circuit_registry,
    get_circuit_status,
)
from app.core.config import Settings, get_settings
from app.core.rate_limit import HEALTH_RATE_LIMIT, get_rate_limit_status, limiter

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


# =============================================================================
# Rate Limit Status Endpoint (Story 13.3)
# =============================================================================


@router.get("/rate-limits")
@limiter.limit(HEALTH_RATE_LIMIT)
async def get_rate_limits_status(
    request: Request,  # Required for rate limiter
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current rate limit configuration and status.

    Returns the rate limit tiers and their configured limits.
    Requires authentication to identify the rate limit key.

    Story 13.3: AC #4 - Rate limit status endpoint.

    Returns:
        Rate limit configuration per tier.

    Example response:
        {
            "data": {
                "key": "user:123e4567-e89b-12d3-a456-426614174000",
                "tiers": {
                    "critical": {"limit": 30, "window": "minute", "description": "LLM, chat, export endpoints"},
                    "search": {"limit": 60, "window": "minute", "description": "Vector search endpoints"},
                    "standard": {"limit": 100, "window": "minute", "description": "CRUD operations"},
                    "readonly": {"limit": 120, "window": "minute", "description": "Dashboard, stats endpoints"},
                    "health": {"limit": 300, "window": "minute", "description": "Monitoring endpoints"}
                },
                "storage": "memory"
            }
        }
    """
    # Set user_id in request state for rate limit key function
    request.state.user_id = current_user.id

    status = get_rate_limit_status(request)

    logger.debug(
        "rate_limits_status_requested",
        user_id=current_user.id,
        key=status["key"],
    )

    return {"data": status}


# =============================================================================
# Pipeline Health Status Endpoint (Story 19 - Pipeline Improvements)
# =============================================================================


@router.get("/pipeline")
async def get_pipeline_health(
    settings: Settings = Depends(get_settings),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    """Get pipeline health status including LLM configurations and stuck jobs.

    Returns configuration status for LLM services (Gemini, OpenAI) and
    counts of stuck processing jobs/chunks.

    Returns:
        Pipeline health status with configuration and stuck job counts.

    Example response:
        {
            "data": {
                "config": {
                    "gemini_configured": true,
                    "gemini_model": "gemini-2.0-flash",
                    "openai_configured": true,
                    "cohere_configured": true,
                    "documentai_configured": true
                },
                "processing": {
                    "stale_chunks_count": 0,
                    "pending_merges_count": 0,
                    "stuck_jobs_count": 2,
                    "processing_jobs_count": 5
                },
                "status": "healthy"
            }
        }
    """
    from datetime import datetime, timedelta, timezone

    # Configuration status
    config_status = {
        "gemini_configured": settings.is_gemini_configured,
        "gemini_model": settings.gemini_model if settings.is_gemini_configured else None,
        "openai_configured": settings.is_openai_configured,
        "cohere_configured": bool(settings.cohere_api_key),
        "documentai_configured": bool(
            settings.google_cloud_project_id and settings.google_document_ai_processor_id
        ),
    }

    # Processing status - get counts from database
    processing_status = {
        "stale_chunks_count": 0,
        "pending_merges_count": 0,
        "stuck_jobs_count": 0,
        "processing_jobs_count": 0,
    }

    if db:
        try:
            from app.services.supabase.client import get_service_client
            client = get_service_client()

            # Count processing jobs
            jobs_resp = (
                client.table("processing_jobs")
                .select("id", count="exact")
                .eq("status", "PROCESSING")
                .execute()
            )
            processing_status["processing_jobs_count"] = jobs_resp.count or 0

            # Count stuck jobs (processing > 30 min)
            stuck_threshold = datetime.now(timezone.utc) - timedelta(minutes=30)
            stuck_resp = (
                client.table("processing_jobs")
                .select("id", count="exact")
                .eq("status", "PROCESSING")
                .lt("updated_at", stuck_threshold.isoformat())
                .execute()
            )
            processing_status["stuck_jobs_count"] = stuck_resp.count or 0

            # Count stale OCR chunks (processing > configurable threshold)
            chunk_threshold = datetime.now(timezone.utc) - timedelta(
                seconds=settings.chunk_stale_threshold_seconds
            )
            stale_chunks_resp = (
                client.table("ocr_chunks")
                .select("id", count="exact")
                .eq("status", "processing")
                .lt("updated_at", chunk_threshold.isoformat())
                .execute()
            )
            processing_status["stale_chunks_count"] = stale_chunks_resp.count or 0

            # Count pending merges (all chunks completed but document not finalized)
            # This is a simplified check - could be more sophisticated
            pending_merges_resp = (
                client.rpc(
                    "count_pending_merges",
                    {},
                ).execute()
            )
            if pending_merges_resp.data:
                processing_status["pending_merges_count"] = pending_merges_resp.data or 0

        except Exception as e:
            logger.warning("pipeline_health_db_error", error=str(e))

    # Determine overall status
    overall_status = "healthy"
    if not config_status["gemini_configured"] or not config_status["openai_configured"]:
        overall_status = "degraded"
    if processing_status["stuck_jobs_count"] > 0 or processing_status["stale_chunks_count"] > 0:
        overall_status = "warning"

    logger.debug(
        "pipeline_health_checked",
        config=config_status,
        processing=processing_status,
        status=overall_status,
    )

    return {
        "data": {
            "config": config_status,
            "processing": processing_status,
            "status": overall_status,
        }
    }
