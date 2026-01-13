"""Timeline API routes for date extraction and event management.

Provides endpoints for:
- Triggering date extraction for documents/matters
- Listing extracted dates (raw timeline events)
- Getting individual date details

Story 4-1: Date Extraction with Gemini
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
)
from app.models.job import JobStatus, JobType
from app.models.timeline import (
    DateExtractionJobData,
    DateExtractionJobResponse,
    RawDateDetailResponse,
    RawDatesListResponse,
    TimelineErrorResponse,
)
from app.services.job_tracking import get_job_tracking_service, JobTrackingService
from app.services.timeline_service import (
    TimelineService,
    TimelineServiceError,
    get_timeline_service,
)
from app.workers.tasks.engine_tasks import (
    extract_dates_from_document,
    extract_dates_from_matter,
)

router = APIRouter(prefix="/matters/{matter_id}/timeline", tags=["timeline"])
logger = structlog.get_logger(__name__)


def _get_timeline_service() -> TimelineService:
    """Get timeline service instance."""
    return get_timeline_service()


def _get_job_tracker() -> JobTrackingService:
    """Get job tracking service instance."""
    return get_job_tracking_service()


# =============================================================================
# Date Extraction Trigger
# =============================================================================


@router.post(
    "/extract",
    response_model=DateExtractionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Date extraction job queued"},
        404: {"model": TimelineErrorResponse, "description": "Matter not found"},
    },
)
async def trigger_date_extraction(
    matter_id: str = Path(..., description="Matter UUID"),
    document_ids: list[str] | None = Query(
        None,
        description="Optional list of document IDs. If empty, processes all case files.",
    ),
    force: bool = Query(
        False,
        description="Force reprocessing of already processed documents",
    ),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
) -> DateExtractionJobResponse:
    """Trigger date extraction for documents in a matter.

    Queues date extraction jobs for all case file documents or
    specified documents. Returns job_id for progress tracking.

    Only processes case_file documents (not Acts) as dates are
    extracted from depositions, complaints, etc.

    Args:
        matter_id: Matter UUID.
        document_ids: Optional specific document IDs to process.
        force: If True, reprocess already processed documents.
        membership: Validated matter membership (owner/editor required).
        job_tracker: Job tracking service.

    Returns:
        DateExtractionJobResponse with job_id and queue status.
    """
    logger.info(
        "date_extraction_trigger_requested",
        matter_id=matter_id,
        document_ids=document_ids,
        force=force,
        user_id=membership.user_id,
    )

    # Determine if we process specific docs or all
    if document_ids:
        # Queue individual document extractions
        # Create a job for tracking
        job = await job_tracker.create_job(
            matter_id=matter_id,
            job_type=JobType.DATE_EXTRACTION,
            metadata={"document_ids": document_ids, "force": force},
        )

        # Queue tasks for each document
        for doc_id in document_ids:
            extract_dates_from_document.delay(
                document_id=doc_id,
                matter_id=matter_id,
                job_id=None,  # Not tracking individual documents
                force_reprocess=force,
            )

        logger.info(
            "date_extraction_documents_queued",
            matter_id=matter_id,
            job_id=job.id,
            document_count=len(document_ids),
        )

        return DateExtractionJobResponse(
            data=DateExtractionJobData(
                job_id=job.id,
                status="queued",
                documents_to_process=len(document_ids),
            )
        )
    else:
        # Queue matter-wide extraction
        task = extract_dates_from_matter.delay(
            matter_id=matter_id,
            document_ids=None,
            force_reprocess=force,
        )

        # The task will create its own job, but we can return the task ID
        # for correlation. The actual job_id will be in the task result.
        logger.info(
            "date_extraction_matter_queued",
            matter_id=matter_id,
            task_id=task.id,
        )

        # Create a placeholder job for immediate response
        job = await job_tracker.create_job(
            matter_id=matter_id,
            job_type=JobType.DATE_EXTRACTION,
            celery_task_id=task.id,
            metadata={"scope": "matter", "force": force},
        )

        # Note: documents_to_process is set to None for matter-wide extraction
        # because the count depends on document_type filtering (case_file only)
        # and force_reprocess logic. The task will update the job metadata
        # with the actual count once it starts processing.
        return DateExtractionJobResponse(
            data=DateExtractionJobData(
                job_id=job.id,
                status="queued",
                documents_to_process=None,  # Determined when task starts
            )
        )


# =============================================================================
# Raw Dates List
# =============================================================================


@router.get(
    "/raw-dates",
    response_model=RawDatesListResponse,
    responses={
        200: {"description": "List of extracted dates"},
        404: {"model": TimelineErrorResponse, "description": "Matter not found"},
    },
)
async def list_raw_dates(
    matter_id: str = Path(..., description="Matter UUID"),
    document_id: str | None = Query(
        None,
        description="Filter by source document",
    ),
    page: int | None = Query(
        None,
        description="Filter by page number",
        alias="page_filter",
    ),
    page_num: int = Query(1, ge=1, description="Page number for pagination"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    timeline_service: TimelineService = Depends(_get_timeline_service),
) -> RawDatesListResponse:
    """List all extracted dates (raw timeline events) for a matter.

    Returns paginated list of dates extracted from documents,
    sorted by event_date ascending.

    These are pre-classification events with event_type="raw_date".
    Story 4-2 will classify them into specific event types.

    Args:
        matter_id: Matter UUID.
        document_id: Optional filter by document.
        page: Optional filter by page number in document.
        page_num: Page number for pagination.
        per_page: Items per page.
        membership: Validated matter membership.
        timeline_service: Timeline service.

    Returns:
        RawDatesListResponse with paginated dates.
    """
    try:
        result = await timeline_service.get_raw_dates_for_matter(
            matter_id=matter_id,
            document_id=document_id,
            page_filter=page,
            page=page_num,
            per_page=per_page,
        )

        logger.debug(
            "raw_dates_listed",
            matter_id=matter_id,
            document_id=document_id,
            total=result.meta.total,
            page=page_num,
        )

        return result

    except TimelineServiceError as e:
        logger.error(
            "raw_dates_list_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        )


# =============================================================================
# Raw Date Detail
# =============================================================================


@router.get(
    "/raw-dates/{event_id}",
    response_model=RawDateDetailResponse,
    responses={
        200: {"description": "Raw date details"},
        404: {"model": TimelineErrorResponse, "description": "Event not found"},
    },
)
async def get_raw_date(
    matter_id: str = Path(..., description="Matter UUID"),
    event_id: str = Path(..., description="Event UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    timeline_service: TimelineService = Depends(_get_timeline_service),
) -> RawDateDetailResponse:
    """Get details of a single extracted date.

    Returns full event record including context text and
    bounding box references for highlighting.

    Args:
        matter_id: Matter UUID.
        event_id: Event UUID.
        membership: Validated matter membership.
        timeline_service: Timeline service.

    Returns:
        RawDateDetailResponse with full event details.
    """
    try:
        event = await timeline_service.get_event_by_id(
            event_id=event_id,
            matter_id=matter_id,
        )

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "EVENT_NOT_FOUND",
                        "message": f"Event {event_id} not found in matter",
                        "details": {"event_id": event_id},
                    }
                },
            )

        logger.debug(
            "raw_date_retrieved",
            matter_id=matter_id,
            event_id=event_id,
        )

        return RawDateDetailResponse(data=event)

    except HTTPException:
        raise
    except TimelineServiceError as e:
        logger.error(
            "raw_date_get_failed",
            matter_id=matter_id,
            event_id=event_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        )


# =============================================================================
# Timeline List (all events, not just raw)
# =============================================================================


@router.get(
    "",
    response_model=RawDatesListResponse,
    responses={
        200: {"description": "Timeline events"},
        404: {"model": TimelineErrorResponse, "description": "Matter not found"},
    },
)
async def list_timeline_events(
    matter_id: str = Path(..., description="Matter UUID"),
    event_type: str | None = Query(
        None,
        description="Filter by event type (raw_date, filing, hearing, etc.)",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    timeline_service: TimelineService = Depends(_get_timeline_service),
) -> RawDatesListResponse:
    """List all timeline events for a matter.

    Returns paginated list of events sorted by event_date.
    Can filter by event_type (raw_date, filing, hearing, etc.)

    Args:
        matter_id: Matter UUID.
        event_type: Optional filter by event type.
        page: Page number.
        per_page: Items per page.
        membership: Validated matter membership.
        timeline_service: Timeline service.

    Returns:
        RawDatesListResponse with paginated events.
    """
    try:
        result = await timeline_service.get_timeline_for_matter(
            matter_id=matter_id,
            event_type=event_type,
            page=page,
            per_page=per_page,
        )

        logger.debug(
            "timeline_events_listed",
            matter_id=matter_id,
            event_type=event_type,
            total=result.meta.total,
        )

        return result

    except TimelineServiceError as e:
        logger.error(
            "timeline_list_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        )
