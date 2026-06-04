"""API routes for Voyage A/B Testing.

Gap 10: Automated Voyage A/B Testing

Provides endpoints for:
- Triggering provider comparison experiments
- Viewing comparison results with statistical analysis
- Checking current A/B testing status and traffic routing
"""

import uuid as _uuid
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import get_matter_service
from app.core.rate_limit import CRITICAL_RATE_LIMIT, READONLY_RATE_LIMIT, limiter
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.services.matter_service import MatterService

router = APIRouter(prefix="/ab-testing", tags=["ab-testing"])
logger = structlog.get_logger(__name__)


def _verify_matter_access(
    matter_id: str,
    user_id: str,
    matter_service: MatterService,
    require_edit: bool = False,
) -> None:
    """Verify user has access to matter. Raises HTTPException if not."""
    role = matter_service.get_user_role(matter_id, user_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "MATTER_NOT_FOUND", "message": "Matter not found or you don't have access"}},
        )
    if require_edit and role not in ("owner", "editor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "INSUFFICIENT_PERMISSIONS", "message": "Owner or Editor role required"}},
        )


# =============================================================================
# Request/Response Models
# =============================================================================


class ABCompareRequest(BaseModel):
    """Request to trigger an A/B comparison experiment."""

    matter_id: str = Field(..., description="Matter UUID to evaluate")

    @field_validator("matter_id")
    @classmethod
    def validate_matter_id_is_uuid(cls, v: str) -> str:
        """BUG-6 fix: reject empty/invalid matter_id before it hits PostgreSQL."""
        try:
            _uuid.UUID(v)
        except (ValueError, AttributeError):
            raise ValueError("matter_id must be a valid UUID") from None
        return v
    tags: list[str] | None = Field(None, description="Golden dataset tag filters")
    control_embedding: Literal["openai", "voyage"] = Field("openai", description="Control embedding provider")
    control_reranker: Literal["cohere", "voyage"] = Field("cohere", description="Control reranker provider")
    treatment_embedding: Literal["openai", "voyage"] = Field("voyage", description="Treatment embedding provider")
    treatment_reranker: Literal["cohere", "voyage"] = Field("voyage", description="Treatment reranker provider")


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/compare")
@limiter.limit(CRITICAL_RATE_LIMIT)
async def trigger_comparison(
    request: Request,
    body: ABCompareRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> dict:
    """Trigger an A/B comparison experiment.

    Runs the same golden dataset through both provider configurations
    (control: OpenAI+Cohere vs treatment: Voyage+Voyage) and compares
    quality using RAGAS metrics + Welch's t-test.

    This is an async operation — returns immediately with a run_id.
    Poll GET /ab-testing/runs/{run_id} for results.

    Cost: ~$0.30-0.60 per comparison (2x batch evaluation).
    """
    _verify_matter_access(body.matter_id, current_user.id, matter_service, require_edit=True)

    logger.info(
        "ab_comparison_requested",
        user_id=current_user.id,
        matter_id=body.matter_id,
    )

    try:
        from app.services.evaluation.ab_testing import ABTestRunner
        from app.workers.tasks.evaluation_tasks import run_ab_comparison

        # BUG-2 fix: Check for active runs BEFORE creating a new one.
        # Previously this check only existed in the Celery task (too late).
        active_statuses = ("pending", "running_control", "running_treatment", "comparing")
        existing_runs = await ABTestRunner.list_runs(
            matter_id=body.matter_id,
            status=None,
            limit=10,
        )
        active_run = next(
            (r for r in existing_runs if r.get("status") in active_statuses),
            None,
        )
        if active_run:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "ACTIVE_RUN_EXISTS",
                        "message": f"An A/B test run is already active (status: {active_run['status']}, id: {active_run['id']}). Wait for it to complete or cancel it.",
                    }
                },
            )

        # Create the run record
        run = await ABTestRunner.create_run(
            matter_id=body.matter_id,
            tags=body.tags,
            created_by=current_user.id,
            control_embedding=body.control_embedding,
            control_reranker=body.control_reranker,
            treatment_embedding=body.treatment_embedding,
            treatment_reranker=body.treatment_reranker,
        )

        run_id = run.get("id")
        if not run_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"code": "RUN_CREATE_FAILED", "message": "Failed to create run"}},
            )

        # Queue the comparison task
        task = run_ab_comparison.delay(
            run_id=run_id,
            matter_id=body.matter_id,
            tags=body.tags,
            user_id=current_user.id,
            control_embedding=body.control_embedding,
            control_reranker=body.control_reranker,
            treatment_embedding=body.treatment_embedding,
            treatment_reranker=body.treatment_reranker,
        )

        return {
            "data": {
                "run_id": run_id,
                "task_id": task.id,
                "status": "pending",
                "message": "A/B comparison started. Both arms will be evaluated sequentially.",
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ab_comparison_trigger_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "AB_COMPARE_FAILED", "message": "Failed to trigger A/B comparison"}},
        ) from e


@router.get("/runs")
@limiter.limit(READONLY_RATE_LIMIT)
async def list_runs(
    request: Request,
    matter_id: str = Query(..., description="Matter ID (required)"),
    run_status: str | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> dict:
    """List A/B test runs for a matter."""
    _verify_matter_access(matter_id, current_user.id, matter_service)

    try:
        from app.services.evaluation.ab_testing import ABTestRunner

        runs = await ABTestRunner.list_runs(
            matter_id=matter_id,
            status=run_status,
            limit=limit,
        )

        return {"data": runs, "meta": {"total": len(runs)}}

    except Exception as e:
        logger.error("ab_list_runs_failed", error=str(e))
        return {"data": [], "meta": {"total": 0}}


@router.get("/runs/{run_id}")
@limiter.limit(READONLY_RATE_LIMIT)
async def get_run(
    request: Request,
    run_id: str = Path(..., description="A/B test run UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> dict:
    """Get a specific A/B test run with full results."""
    try:
        from app.services.evaluation.ab_testing import ABTestRunner

        run = await ABTestRunner.get_run(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "RUN_NOT_FOUND", "message": "A/B test run not found"}},
            )

        # Verify the user has access to the matter this run belongs to
        run_matter_id = run.get("matter_id")
        if not run_matter_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"code": "INVALID_RUN", "message": "Run has no associated matter"}},
            )
        _verify_matter_access(run_matter_id, current_user.id, matter_service)

        return {"data": run}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ab_get_run_failed", run_id=run_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "AB_GET_RUN_FAILED", "message": "Failed to retrieve A/B test run"}},
        ) from e


@router.get("/status")
@limiter.limit(READONLY_RATE_LIMIT)
async def get_ab_status(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Get current A/B testing status.

    Returns:
    - Whether A/B testing is enabled
    - Current traffic routing percentage
    - Latest completed comparison result
    - Any currently running experiment
    """
    try:
        from app.services.evaluation.ab_testing import ABTestRunner

        status_data = await ABTestRunner.get_current_status()
        return {"data": status_data}

    except Exception as e:
        logger.error("ab_status_failed", error=str(e))
        from app.core.config import get_settings
        settings = get_settings()
        return {
            "data": {
                "enabled": settings.voyage_ab_testing_enabled,
                "traffic_percentage": settings.voyage_traffic_percentage,
                "latest_run": None,
                "running": None,
                "total_completed_runs": 0,
                "error": str(e),
            }
        }
