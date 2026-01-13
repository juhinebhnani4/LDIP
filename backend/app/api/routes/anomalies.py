"""Anomalies API routes for timeline anomaly detection.

Provides endpoints for:
- Listing detected anomalies for a matter
- Getting anomaly details
- Triggering anomaly detection
- Dismissing/verifying anomalies
- Getting anomaly summary for attention banners

Story 4-4: Timeline Anomaly Detection
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
)
from app.models.anomaly import (
    AnomaliesListResponse,
    AnomalyDetailResponse,
    AnomalyDetectionJobData,
    AnomalyDetectionJobResponse,
    AnomalySummaryResponse,
    AnomalyUpdateResponse,
    AnomalyErrorResponse,
)
from app.models.job import JobStatus, JobType
from app.services.anomaly_service import get_anomaly_service, AnomalyService
from app.services.job_tracking import get_job_tracking_service, JobTrackingService
from app.services.timeline_service import get_timeline_service, TimelineService
from app.workers.tasks.engine_tasks import detect_timeline_anomalies

router = APIRouter(prefix="/matters/{matter_id}/anomalies", tags=["anomalies"])
logger = structlog.get_logger(__name__)


def _get_anomaly_service() -> AnomalyService:
    """Get anomaly service instance."""
    return get_anomaly_service()


def _get_job_tracker() -> JobTrackingService:
    """Get job tracking service instance."""
    return get_job_tracking_service()


def _get_timeline_service() -> TimelineService:
    """Get timeline service instance."""
    return get_timeline_service()


# =============================================================================
# Anomaly Summary (MUST be before /{anomaly_id} to avoid route conflict)
# =============================================================================


@router.get(
    "/summary",
    response_model=AnomalySummaryResponse,
    responses={
        200: {"description": "Anomaly summary counts"},
        404: {"model": AnomalyErrorResponse, "description": "Matter not found"},
    },
)
async def get_anomaly_summary(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    anomaly_service: AnomalyService = Depends(_get_anomaly_service),
) -> AnomalySummaryResponse:
    """Get anomaly summary counts for attention banner.

    Returns counts by severity, type, and review status.

    Args:
        matter_id: Matter UUID.
        membership: Validated matter membership.
        anomaly_service: Anomaly service.

    Returns:
        AnomalySummaryResponse with summary counts.
    """
    return await anomaly_service.get_anomaly_summary(matter_id)


# =============================================================================
# List Anomalies
# =============================================================================


@router.get(
    "",
    response_model=AnomaliesListResponse,
    responses={
        200: {"description": "List of anomalies"},
        404: {"model": AnomalyErrorResponse, "description": "Matter not found"},
    },
)
async def list_anomalies(
    matter_id: str = Path(..., description="Matter UUID"),
    severity: str | None = Query(
        None,
        description="Filter by severity (low, medium, high, critical)",
    ),
    anomaly_type: str | None = Query(
        None,
        description="Filter by type (gap, sequence_violation, duplicate, outlier)",
    ),
    dismissed: bool | None = Query(
        None,
        description="Filter by dismissed status",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    anomaly_service: AnomalyService = Depends(_get_anomaly_service),
) -> AnomaliesListResponse:
    """List all anomalies for a matter.

    Returns paginated list of detected anomalies sorted by severity
    and creation date (most severe/recent first).

    Args:
        matter_id: Matter UUID.
        severity: Optional filter by severity level.
        anomaly_type: Optional filter by anomaly type.
        dismissed: Optional filter by dismissed status.
        page: Page number.
        per_page: Items per page.
        membership: Validated matter membership.
        anomaly_service: Anomaly service.

    Returns:
        AnomaliesListResponse with paginated anomalies.
    """
    logger.debug(
        "anomalies_list_requested",
        matter_id=matter_id,
        severity=severity,
        anomaly_type=anomaly_type,
        page=page,
    )

    result = await anomaly_service.get_anomalies_for_matter(
        matter_id=matter_id,
        page=page,
        per_page=per_page,
        severity=severity,
        anomaly_type=anomaly_type,
        dismissed=dismissed,
    )

    return result


# =============================================================================
# Get Anomaly Details
# =============================================================================


@router.get(
    "/{anomaly_id}",
    response_model=AnomalyDetailResponse,
    responses={
        200: {"description": "Anomaly details"},
        404: {"model": AnomalyErrorResponse, "description": "Anomaly not found"},
    },
)
async def get_anomaly(
    matter_id: str = Path(..., description="Matter UUID"),
    anomaly_id: str = Path(..., description="Anomaly UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    anomaly_service: AnomalyService = Depends(_get_anomaly_service),
) -> AnomalyDetailResponse:
    """Get details of a single anomaly.

    Args:
        matter_id: Matter UUID.
        anomaly_id: Anomaly UUID.
        membership: Validated matter membership.
        anomaly_service: Anomaly service.

    Returns:
        AnomalyDetailResponse with full anomaly details.
    """
    anomaly = await anomaly_service.get_anomaly_by_id(
        anomaly_id=anomaly_id,
        matter_id=matter_id,
    )

    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ANOMALY_NOT_FOUND",
                    "message": f"Anomaly {anomaly_id} not found in matter",
                    "details": {"anomaly_id": anomaly_id},
                }
            },
        )

    return AnomalyDetailResponse(data=anomaly)


# =============================================================================
# Trigger Detection
# =============================================================================


@router.post(
    "/detect",
    response_model=AnomalyDetectionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Anomaly detection job queued"},
        404: {"model": AnomalyErrorResponse, "description": "Matter not found"},
    },
)
async def trigger_anomaly_detection(
    matter_id: str = Path(..., description="Matter UUID"),
    force_redetect: bool = Query(
        False,
        description="Force redetection (deletes existing anomalies first)",
    ),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
    timeline_service: TimelineService = Depends(_get_timeline_service),
) -> AnomalyDetectionJobResponse:
    """Trigger anomaly detection for a matter's timeline.

    Queues a background task to analyze all timeline events
    for sequence violations, gaps, duplicates, and outliers.

    Args:
        matter_id: Matter UUID.
        force_redetect: If True, delete existing anomalies first.
        membership: Validated matter membership (owner/editor required).
        job_tracker: Job tracking service.
        timeline_service: Timeline service for event counting.

    Returns:
        AnomalyDetectionJobResponse with job_id.
    """
    logger.info(
        "anomaly_detection_trigger_requested",
        matter_id=matter_id,
        force_redetect=force_redetect,
        user_id=membership.user_id,
    )

    # Count events to analyze
    events_result = await timeline_service.get_timeline_for_matter(
        matter_id=matter_id,
        page=1,
        per_page=1,  # Just need count
    )
    events_count = events_result.meta.total

    # Create job for tracking
    job = await job_tracker.create_job(
        matter_id=matter_id,
        job_type=JobType.ANOMALY_DETECTION,
        metadata={
            "force_redetect": force_redetect,
            "events_to_analyze": events_count,
        },
    )

    # Queue anomaly detection task
    task = detect_timeline_anomalies.delay(
        matter_id=matter_id,
        force_redetect=force_redetect,
        job_id=job.id,
    )

    logger.info(
        "anomaly_detection_queued",
        matter_id=matter_id,
        job_id=job.id,
        task_id=task.id,
        events_count=events_count,
    )

    return AnomalyDetectionJobResponse(
        data=AnomalyDetectionJobData(
            job_id=job.id,
            status="queued",
            events_to_analyze=events_count,
        )
    )


# =============================================================================
# Dismiss Anomaly
# =============================================================================


@router.patch(
    "/{anomaly_id}/dismiss",
    response_model=AnomalyUpdateResponse,
    responses={
        200: {"description": "Anomaly dismissed"},
        404: {"model": AnomalyErrorResponse, "description": "Anomaly not found"},
    },
)
async def dismiss_anomaly(
    matter_id: str = Path(..., description="Matter UUID"),
    anomaly_id: str = Path(..., description="Anomaly UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    anomaly_service: AnomalyService = Depends(_get_anomaly_service),
) -> AnomalyUpdateResponse:
    """Dismiss an anomaly as not a real issue.

    Attorney decision that the flagged anomaly is not actually
    a problem (e.g., intentional gap, valid date).

    Args:
        matter_id: Matter UUID.
        anomaly_id: Anomaly UUID.
        membership: Validated matter membership (owner/editor required).
        anomaly_service: Anomaly service.

    Returns:
        AnomalyUpdateResponse with updated anomaly.
    """
    logger.info(
        "anomaly_dismiss_requested",
        matter_id=matter_id,
        anomaly_id=anomaly_id,
        user_id=membership.user_id,
    )

    updated = await anomaly_service.dismiss_anomaly(
        anomaly_id=anomaly_id,
        matter_id=matter_id,
        user_id=membership.user_id,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ANOMALY_NOT_FOUND",
                    "message": f"Anomaly {anomaly_id} not found in matter",
                    "details": {"anomaly_id": anomaly_id},
                }
            },
        )

    return AnomalyUpdateResponse(data=updated)


# =============================================================================
# Verify Anomaly
# =============================================================================


@router.patch(
    "/{anomaly_id}/verify",
    response_model=AnomalyUpdateResponse,
    responses={
        200: {"description": "Anomaly verified"},
        404: {"model": AnomalyErrorResponse, "description": "Anomaly not found"},
    },
)
async def verify_anomaly(
    matter_id: str = Path(..., description="Matter UUID"),
    anomaly_id: str = Path(..., description="Anomaly UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    anomaly_service: AnomalyService = Depends(_get_anomaly_service),
) -> AnomalyUpdateResponse:
    """Verify an anomaly as a real issue.

    Attorney confirmation that the flagged anomaly is indeed
    a problem that needs attention or follow-up.

    Args:
        matter_id: Matter UUID.
        anomaly_id: Anomaly UUID.
        membership: Validated matter membership (owner/editor required).
        anomaly_service: Anomaly service.

    Returns:
        AnomalyUpdateResponse with updated anomaly.
    """
    logger.info(
        "anomaly_verify_requested",
        matter_id=matter_id,
        anomaly_id=anomaly_id,
        user_id=membership.user_id,
    )

    updated = await anomaly_service.verify_anomaly(
        anomaly_id=anomaly_id,
        matter_id=matter_id,
        user_id=membership.user_id,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ANOMALY_NOT_FOUND",
                    "message": f"Anomaly {anomaly_id} not found in matter",
                    "details": {"anomaly_id": anomaly_id},
                }
            },
        )

    return AnomalyUpdateResponse(data=updated)
