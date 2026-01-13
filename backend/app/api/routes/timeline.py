"""Timeline API routes for date extraction and event management.

Provides endpoints for:
- Triggering date extraction for documents/matters
- Listing extracted dates (raw timeline events)
- Getting individual date details
- Event classification (Story 4-2)

Story 4-1: Date Extraction with Gemini
Story 4-2: Event Classification
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
    ClassificationJobData,
    ClassificationJobResponse,
    ClassifiedEventsListResponse,
    DateExtractionJobData,
    DateExtractionJobResponse,
    EventType,
    ManualClassificationRequest,
    ManualClassificationResponse,
    RawDateDetailResponse,
    RawDatesListResponse,
    TimelineErrorResponse,
    UnclassifiedEventsResponse,
)
from app.services.job_tracking import get_job_tracking_service, JobTrackingService
from app.services.timeline_service import (
    TimelineService,
    TimelineServiceError,
    get_timeline_service,
)
from app.workers.tasks.engine_tasks import (
    classify_events_for_matter,
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


# =============================================================================
# Event Classification Endpoints (Story 4-2)
# =============================================================================


@router.post(
    "/classify",
    response_model=ClassificationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Classification job queued"},
        404: {"model": TimelineErrorResponse, "description": "Matter not found"},
    },
)
async def trigger_event_classification(
    matter_id: str = Path(..., description="Matter UUID"),
    document_ids: list[str] | None = Query(
        None,
        description="Optional list of document IDs. If empty, classifies all raw_date events.",
    ),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    job_tracker: JobTrackingService = Depends(_get_job_tracker),
    timeline_service: TimelineService = Depends(_get_timeline_service),
) -> ClassificationJobResponse:
    """Trigger event classification for raw_date events.

    Queues classification jobs for all raw_date events or events
    from specified documents. Returns job_id for progress tracking.

    Classification types:
    - filing: Documents submitted to court
    - notice: Notices issued/served/received
    - hearing: Court proceedings and arguments
    - order: Court orders and judgments
    - transaction: Financial transactions
    - document: Document creation/execution
    - deadline: Time limits and deadlines
    - unclassified: Cannot determine (needs manual review)

    Args:
        matter_id: Matter UUID.
        document_ids: Optional specific document IDs to process.
        membership: Validated matter membership (owner/editor required).
        job_tracker: Job tracking service.
        timeline_service: Timeline service.

    Returns:
        ClassificationJobResponse with job_id and queue status.
    """
    logger.info(
        "event_classification_trigger_requested",
        matter_id=matter_id,
        document_ids=document_ids,
        user_id=membership.user_id,
    )

    # Count events to classify
    events_count = await timeline_service.count_events_for_classification(
        matter_id=matter_id,
        document_ids=document_ids,
    )

    if events_count == 0:
        # No events to classify - return success with 0 count
        job = await job_tracker.create_job(
            matter_id=matter_id,
            job_type=JobType.EVENT_CLASSIFICATION,
            metadata={"document_ids": document_ids, "events_count": 0},
        )

        # Mark immediately complete
        await job_tracker.update_job_status(
            job_id=job.id,
            status=JobStatus.COMPLETED,
            progress_pct=100,
            matter_id=matter_id,
        )

        return ClassificationJobResponse(
            data=ClassificationJobData(
                job_id=job.id,
                status="completed",
                events_to_classify=0,
            )
        )

    # Queue matter-wide classification task
    task = classify_events_for_matter.delay(
        matter_id=matter_id,
        document_ids=document_ids,
        force_reclassify=False,
    )

    # Create job for tracking
    job = await job_tracker.create_job(
        matter_id=matter_id,
        job_type=JobType.EVENT_CLASSIFICATION,
        celery_task_id=task.id,
        metadata={
            "document_ids": document_ids,
            "events_count": events_count,
        },
    )

    logger.info(
        "event_classification_queued",
        matter_id=matter_id,
        job_id=job.id,
        task_id=task.id,
        events_count=events_count,
    )

    return ClassificationJobResponse(
        data=ClassificationJobData(
            job_id=job.id,
            status="queued",
            events_to_classify=events_count,
        )
    )


@router.get(
    "/events",
    response_model=ClassifiedEventsListResponse,
    responses={
        200: {"description": "List of classified events"},
        404: {"model": TimelineErrorResponse, "description": "Matter not found"},
    },
)
async def list_classified_events(
    matter_id: str = Path(..., description="Matter UUID"),
    event_type: str | None = Query(
        None,
        description="Filter by event type (filing, notice, hearing, order, etc.)",
    ),
    confidence_min: float | None = Query(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    timeline_service: TimelineService = Depends(_get_timeline_service),
) -> ClassifiedEventsListResponse:
    """List classified events for a matter.

    Returns events that have been classified (event_type != raw_date).
    Can filter by event type and minimum confidence.

    Args:
        matter_id: Matter UUID.
        event_type: Optional filter by event type.
        confidence_min: Optional minimum confidence filter.
        page: Page number.
        per_page: Items per page.
        membership: Validated matter membership.
        timeline_service: Timeline service.

    Returns:
        ClassifiedEventsListResponse with paginated events.
    """
    try:
        result = await timeline_service.get_classified_events(
            matter_id=matter_id,
            event_type=event_type,
            confidence_min=confidence_min,
            page=page,
            per_page=per_page,
        )

        logger.debug(
            "classified_events_listed",
            matter_id=matter_id,
            event_type=event_type,
            total=result.meta.total,
        )

        return result

    except TimelineServiceError as e:
        logger.error(
            "classified_events_list_failed",
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


@router.get(
    "/unclassified",
    response_model=UnclassifiedEventsResponse,
    responses={
        200: {"description": "List of unclassified events needing review"},
        404: {"model": TimelineErrorResponse, "description": "Matter not found"},
    },
)
async def list_unclassified_events(
    matter_id: str = Path(..., description="Matter UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    timeline_service: TimelineService = Depends(_get_timeline_service),
) -> UnclassifiedEventsResponse:
    """List events that need manual classification.

    Returns events where:
    - event_type is 'raw_date' or 'unclassified'
    - OR confidence < 0.7

    These events require human review and manual classification.

    Args:
        matter_id: Matter UUID.
        page: Page number.
        per_page: Items per page.
        membership: Validated matter membership.
        timeline_service: Timeline service.

    Returns:
        UnclassifiedEventsResponse with paginated events.
    """
    try:
        result = await timeline_service.get_unclassified_events(
            matter_id=matter_id,
            page=page,
            per_page=per_page,
        )

        logger.debug(
            "unclassified_events_listed",
            matter_id=matter_id,
            total=result.meta.total,
        )

        return result

    except TimelineServiceError as e:
        logger.error(
            "unclassified_events_list_failed",
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


@router.patch(
    "/events/{event_id}",
    response_model=ManualClassificationResponse,
    responses={
        200: {"description": "Event classification updated"},
        404: {"model": TimelineErrorResponse, "description": "Event not found"},
    },
)
async def update_event_classification(
    matter_id: str = Path(..., description="Matter UUID"),
    event_id: str = Path(..., description="Event UUID"),
    request: ManualClassificationRequest = ...,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    timeline_service: TimelineService = Depends(_get_timeline_service),
) -> ManualClassificationResponse:
    """Manually update an event's classification.

    Allows users to correct or set the event type for events
    that were unclassified or incorrectly classified.

    Sets is_manual=True and confidence=1.0 (human verified).

    Args:
        matter_id: Matter UUID.
        event_id: Event UUID to update.
        request: New event type.
        membership: Validated matter membership (owner/editor required).
        timeline_service: Timeline service.

    Returns:
        ManualClassificationResponse with updated event.
    """
    logger.info(
        "manual_classification_requested",
        matter_id=matter_id,
        event_id=event_id,
        new_type=request.event_type.value,
        user_id=membership.user_id,
    )

    try:
        updated_event = await timeline_service.update_manual_classification(
            event_id=event_id,
            matter_id=matter_id,
            event_type=request.event_type,
        )

        if not updated_event:
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

        logger.info(
            "manual_classification_updated",
            matter_id=matter_id,
            event_id=event_id,
            event_type=updated_event.event_type.value,
        )

        return ManualClassificationResponse(data=updated_event)

    except HTTPException:
        raise
    except TimelineServiceError as e:
        logger.error(
            "manual_classification_failed",
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
