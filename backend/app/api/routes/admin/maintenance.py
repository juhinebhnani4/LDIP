"""Admin Maintenance API routes.

Provides admin-only endpoints for:
- POST /api/admin/maintenance/cleanup-deleted-matters - Trigger immediate hard delete of soft-deleted matters

All endpoints require admin access (configured via ADMIN_EMAILS env var).
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import require_admin_access
from app.core.rate_limit import ADMIN_RATE_LIMIT, limiter
from app.models.auth import AuthenticatedUser

router = APIRouter(prefix="/admin/maintenance", tags=["admin-maintenance"])
logger = structlog.get_logger(__name__)


class CleanupResponse(BaseModel):
    """Response model for cleanup operations."""

    success: bool = Field(..., description="Whether the task was triggered successfully")
    task_id: str | None = Field(None, description="Celery task ID for tracking")
    message: str = Field(..., description="Human-readable status message")


class CleanupRequest(BaseModel):
    """Request model for cleanup operations."""

    retention_days: int = Field(
        default=0,
        ge=0,
        le=365,
        description="Number of days to retain soft-deleted items. 0 = delete all soft-deleted items immediately.",
    )


@router.post(
    "/cleanup-deleted-matters",
    response_model=CleanupResponse,
    summary="Cleanup Soft-Deleted Matters",
    description="""
Trigger immediate hard deletion of soft-deleted matters.

This permanently removes matters (and all related data via CASCADE delete):
- documents, chunks, bounding_boxes
- entities, entity_mentions, citations
- events, processing_jobs, act_resolutions
- Storage files in Supabase Storage

**Warning**: This action is irreversible.

Args:
    retention_days: Number of days to retain. Default 0 deletes ALL soft-deleted matters immediately.
""",
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def cleanup_deleted_matters(
    request: Request,
    body: CleanupRequest = CleanupRequest(),
    admin_user: AuthenticatedUser = Depends(require_admin_access),
) -> CleanupResponse:
    """Trigger hard deletion of soft-deleted matters."""
    try:
        from app.workers.tasks.maintenance_tasks import hard_delete_expired_matters

        logger.info(
            "admin_cleanup_deleted_matters_triggered",
            admin_user=admin_user.email,
            retention_days=body.retention_days,
        )

        # Dispatch the task
        result = hard_delete_expired_matters.delay(retention_days=body.retention_days)

        return CleanupResponse(
            success=True,
            task_id=result.id,
            message=f"Cleanup task triggered. Matters soft-deleted more than {body.retention_days} days ago will be permanently removed.",
        )

    except Exception as e:
        logger.error(
            "admin_cleanup_deleted_matters_failed",
            admin_user=admin_user.email,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "CLEANUP_FAILED", "message": str(e)}},
        ) from e


@router.post(
    "/cleanup-deleted-documents",
    response_model=CleanupResponse,
    summary="Cleanup Soft-Deleted Documents",
    description="""
Trigger immediate hard deletion of soft-deleted documents.

This permanently removes documents and their storage files.

**Warning**: This action is irreversible.

Args:
    retention_days: Number of days to retain. Default 0 deletes ALL soft-deleted documents immediately.
""",
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def cleanup_deleted_documents(
    request: Request,
    body: CleanupRequest = CleanupRequest(),
    admin_user: AuthenticatedUser = Depends(require_admin_access),
) -> CleanupResponse:
    """Trigger hard deletion of soft-deleted documents."""
    try:
        from app.workers.tasks.maintenance_tasks import hard_delete_expired_documents

        logger.info(
            "admin_cleanup_deleted_documents_triggered",
            admin_user=admin_user.email,
            retention_days=body.retention_days,
        )

        # Dispatch the task
        result = hard_delete_expired_documents.delay(retention_days=body.retention_days)

        return CleanupResponse(
            success=True,
            task_id=result.id,
            message=f"Cleanup task triggered. Documents soft-deleted more than {body.retention_days} days ago will be permanently removed.",
        )

    except Exception as e:
        logger.error(
            "admin_cleanup_deleted_documents_failed",
            admin_user=admin_user.email,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "CLEANUP_FAILED", "message": str(e)}},
        ) from e
