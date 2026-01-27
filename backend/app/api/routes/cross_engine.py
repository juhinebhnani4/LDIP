"""Cross-Engine Link Resolution and Consistency API routes.

Gap 5-3: Cross-Engine Correlation Links
Story 5.4: Cross-Engine Consistency Checking

Provides API endpoints for cross-engine data retrieval and consistency checking:
- GET /matters/{matter_id}/cross-engine/entity/{entity_id}/journey
- GET /matters/{matter_id}/cross-engine/entity/{entity_id}/contradictions
- GET /matters/{matter_id}/cross-engine/timeline/{event_id}/context
- GET /matters/{matter_id}/cross-engine/contradiction/{contradiction_id}/context
- GET /matters/{matter_id}/cross-engine/consistency-issues
- GET /matters/{matter_id}/cross-engine/consistency-issues/summary
- PATCH /matters/{matter_id}/cross-engine/consistency-issues/{issue_id}
- POST /matters/{matter_id}/cross-engine/consistency-issues/check
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import MatterMembership, MatterRole, require_matter_role
from app.models.consistency_issue import (
    ConsistencyIssue,
    ConsistencyIssueListResponse,
    ConsistencyIssueSummary,
    ConsistencyIssueSummaryResponse,
    ConsistencyIssueUpdate,
    IssueStatus,
)
from app.models.cross_engine import (
    ContradictionContextResponse,
    CrossEngineErrorResponse,
    CrossLinkedContradictionModel,
    CrossLinkedEntityModel,
    CrossLinkedTimelineEventModel,
    EntityContradictionSummaryResponse,
    EntityJourneyResponse,
    TimelineEventContextResponse,
)
from app.services.consistency_service import (
    ConsistencyService,
    get_consistency_service,
)
from app.services.cross_engine_service import (
    CrossEngineService,
    get_cross_engine_service,
)

router = APIRouter(prefix="/matters/{matter_id}/cross-engine", tags=["cross-engine"])
logger = structlog.get_logger(__name__)


def _get_service() -> CrossEngineService:
    """Get cross-engine service instance."""
    return get_cross_engine_service()


def _get_consistency_service() -> ConsistencyService:
    """Get consistency service instance."""
    return get_consistency_service()


# =============================================================================
# Entity Journey Endpoint
# =============================================================================


@router.get(
    "/entity/{entity_id}/journey",
    response_model=EntityJourneyResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "Entity journey with timeline events"},
        404: {"model": CrossEngineErrorResponse, "description": "Entity not found"},
    },
)
async def get_entity_journey(
    matter_id: str = Path(..., description="Matter UUID"),
    entity_id: str = Path(..., description="Entity UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    service: CrossEngineService = Depends(_get_service),
) -> EntityJourneyResponse:
    """Get the timeline journey for a specific entity.

    Returns all timeline events involving the entity, ordered chronologically.
    Enables "entity journey" visualization in the UI.

    Args:
        matter_id: Matter UUID.
        entity_id: Entity UUID.
        page: Page number for pagination.
        per_page: Items per page.
        membership: Validated matter membership.
        service: Cross-engine service.

    Returns:
        EntityJourneyResponse with timeline events for the entity.
    """
    logger.info(
        "get_entity_journey_requested",
        matter_id=matter_id,
        entity_id=entity_id,
        user_id=membership.user_id,
    )

    try:
        # Note: service methods are synchronous (using sync Supabase client)
        journey = service.get_entity_journey(
            matter_id=matter_id,
            entity_id=entity_id,
            page=page,
            per_page=per_page,
        )

        events = [
            CrossLinkedTimelineEventModel(
                event_id=e.event_id,
                event_date=e.event_date,
                event_type=e.event_type,
                description=e.description,
                document_id=e.document_id,
                document_name=e.document_name,
                source_page=e.source_page,
                confidence=e.confidence,
            )
            for e in journey.events
        ]

        return EntityJourneyResponse(
            entity_id=journey.entity_id,
            entity_name=journey.entity_name,
            entity_type=journey.entity_type,
            events=events,
            total_events=journey.total_events,
            date_range_start=journey.date_range_start,
            date_range_end=journey.date_range_end,
        )

    except Exception as e:
        logger.error(
            "get_entity_journey_failed",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ENTITY_JOURNEY_ERROR",
                    "message": f"Failed to get entity journey: {e}",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Entity Contradictions Endpoint
# =============================================================================


@router.get(
    "/entity/{entity_id}/contradictions",
    response_model=EntityContradictionSummaryResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "Entity contradictions summary"},
        404: {"model": CrossEngineErrorResponse, "description": "Entity not found"},
    },
)
async def get_entity_contradictions(
    matter_id: str = Path(..., description="Matter UUID"),
    entity_id: str = Path(..., description="Entity UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=50, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    service: CrossEngineService = Depends(_get_service),
) -> EntityContradictionSummaryResponse:
    """Get contradictions involving a specific entity.

    Returns all contradictions where the entity appears in either statement.
    Enables "entity contradictions" view in the UI.

    Args:
        matter_id: Matter UUID.
        entity_id: Entity UUID.
        page: Page number for pagination.
        per_page: Items per page.
        membership: Validated matter membership.
        service: Cross-engine service.

    Returns:
        EntityContradictionSummaryResponse with contradictions for the entity.
    """
    logger.info(
        "get_entity_contradictions_requested",
        matter_id=matter_id,
        entity_id=entity_id,
        user_id=membership.user_id,
    )

    try:
        # Note: service methods are synchronous (using sync Supabase client)
        summary = service.get_entity_contradictions(
            matter_id=matter_id,
            entity_id=entity_id,
            page=page,
            per_page=per_page,
        )

        contradictions = [
            CrossLinkedContradictionModel(
                contradiction_id=c.contradiction_id,
                contradiction_type=c.contradiction_type,
                severity=c.severity,
                explanation=c.explanation,
                statement_a_excerpt=c.statement_a_excerpt,
                statement_b_excerpt=c.statement_b_excerpt,
                document_a_id=c.document_a_id,
                document_a_name=c.document_a_name,
                document_b_id=c.document_b_id,
                document_b_name=c.document_b_name,
                confidence=c.confidence,
            )
            for c in summary.contradictions
        ]

        return EntityContradictionSummaryResponse(
            entity_id=summary.entity_id,
            entity_name=summary.entity_name,
            contradictions=contradictions,
            total_contradictions=summary.total_contradictions,
            high_severity_count=summary.high_severity_count,
            medium_severity_count=summary.medium_severity_count,
            low_severity_count=summary.low_severity_count,
        )

    except Exception as e:
        logger.error(
            "get_entity_contradictions_failed",
            matter_id=matter_id,
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ENTITY_CONTRADICTIONS_ERROR",
                    "message": f"Failed to get entity contradictions: {e}",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Timeline Event Context Endpoint
# =============================================================================


@router.get(
    "/timeline/{event_id}/context",
    response_model=TimelineEventContextResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "Timeline event context"},
        404: {"model": CrossEngineErrorResponse, "description": "Event not found"},
    },
)
async def get_timeline_event_context(
    matter_id: str = Path(..., description="Matter UUID"),
    event_id: str = Path(..., description="Timeline event UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    service: CrossEngineService = Depends(_get_service),
) -> TimelineEventContextResponse:
    """Get cross-engine context for a timeline event.

    Returns the event with its linked entities and any contradictions
    involving those entities.

    Args:
        matter_id: Matter UUID.
        event_id: Timeline event UUID.
        membership: Validated matter membership.
        service: Cross-engine service.

    Returns:
        TimelineEventContextResponse with entities and contradictions.
    """
    logger.info(
        "get_timeline_event_context_requested",
        matter_id=matter_id,
        event_id=event_id,
        user_id=membership.user_id,
    )

    try:
        # Note: service methods are synchronous (using sync Supabase client)
        context = service.get_timeline_event_context(
            matter_id=matter_id,
            event_id=event_id,
        )

        if not context:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "EVENT_NOT_FOUND",
                        "message": f"Timeline event {event_id} not found",
                        "details": {"event_id": event_id},
                    }
                },
            )

        entities = [
            CrossLinkedEntityModel(
                entity_id=e.entity_id,
                canonical_name=e.canonical_name,
                entity_type=e.entity_type,
                aliases=e.aliases,
            )
            for e in context.entities
        ]

        contradictions = [
            CrossLinkedContradictionModel(
                contradiction_id=c.contradiction_id,
                contradiction_type=c.contradiction_type,
                severity=c.severity,
                explanation=c.explanation,
                statement_a_excerpt=c.statement_a_excerpt,
                statement_b_excerpt=c.statement_b_excerpt,
                document_a_id=c.document_a_id,
                document_a_name=c.document_a_name,
                document_b_id=c.document_b_id,
                document_b_name=c.document_b_name,
                confidence=c.confidence,
            )
            for c in context.related_contradictions
        ]

        return TimelineEventContextResponse(
            event_id=context.event_id,
            event_date=context.event_date,
            event_type=context.event_type,
            description=context.description,
            document_id=context.document_id,
            document_name=context.document_name,
            entities=entities,
            related_contradictions=contradictions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_timeline_event_context_failed",
            matter_id=matter_id,
            event_id=event_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "EVENT_CONTEXT_ERROR",
                    "message": f"Failed to get event context: {e}",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Contradiction Context Endpoint
# =============================================================================


@router.get(
    "/contradiction/{contradiction_id}/context",
    response_model=ContradictionContextResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "Contradiction context"},
        404: {"model": CrossEngineErrorResponse, "description": "Contradiction not found"},
    },
)
async def get_contradiction_context(
    matter_id: str = Path(..., description="Matter UUID"),
    contradiction_id: str = Path(..., description="Contradiction UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    service: CrossEngineService = Depends(_get_service),
) -> ContradictionContextResponse:
    """Get cross-engine context for a contradiction.

    Returns the contradiction with related timeline events for the same
    entity, providing temporal context for the conflict.

    Args:
        matter_id: Matter UUID.
        contradiction_id: Contradiction UUID.
        membership: Validated matter membership.
        service: Cross-engine service.

    Returns:
        ContradictionContextResponse with related timeline events.
    """
    logger.info(
        "get_contradiction_context_requested",
        matter_id=matter_id,
        contradiction_id=contradiction_id,
        user_id=membership.user_id,
    )

    try:
        # Note: service methods are synchronous (using sync Supabase client)
        context = service.get_contradiction_context(
            matter_id=matter_id,
            contradiction_id=contradiction_id,
        )

        if not context:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "CONTRADICTION_NOT_FOUND",
                        "message": f"Contradiction {contradiction_id} not found",
                        "details": {"contradiction_id": contradiction_id},
                    }
                },
            )

        events = [
            CrossLinkedTimelineEventModel(
                event_id=e.event_id,
                event_date=e.event_date,
                event_type=e.event_type,
                description=e.description,
                document_id=e.document_id,
                document_name=e.document_name,
                source_page=e.source_page,
                confidence=e.confidence,
            )
            for e in context.related_events
        ]

        return ContradictionContextResponse(
            contradiction_id=context.contradiction_id,
            entity_id=context.entity_id,
            entity_name=context.entity_name,
            contradiction_type=context.contradiction_type,
            severity=context.severity,
            explanation=context.explanation,
            related_events=events,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_contradiction_context_failed",
            matter_id=matter_id,
            contradiction_id=contradiction_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CONTRADICTION_CONTEXT_ERROR",
                    "message": f"Failed to get contradiction context: {e}",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 5.4: Consistency Issue Endpoints
# =============================================================================


@router.get(
    "/consistency-issues",
    response_model=ConsistencyIssueListResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "List of consistency issues"},
    },
)
async def get_consistency_issues(
    matter_id: str = Path(..., description="Matter UUID"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    service: ConsistencyService = Depends(_get_consistency_service),
) -> ConsistencyIssueListResponse:
    """Get consistency issues for a matter.

    Story 5.4: Cross-Engine Consistency Checking

    Returns paginated list of consistency issues detected between engines.

    Args:
        matter_id: Matter UUID.
        status_filter: Optional status filter (open, reviewed, resolved, dismissed).
        severity: Optional severity filter (info, warning, error).
        limit: Max results per page.
        offset: Pagination offset.
        membership: Validated matter membership.
        service: Consistency service.

    Returns:
        ConsistencyIssueListResponse with issues and metadata.
    """
    logger.info(
        "get_consistency_issues_requested",
        matter_id=matter_id,
        user_id=membership.user_id,
        status=status_filter,
        severity=severity,
    )

    try:
        issues = await service.get_issues_for_matter(
            matter_id=matter_id,
            status=status_filter,
            severity=severity,
            limit=limit,
            offset=offset,
        )

        return ConsistencyIssueListResponse(
            data=issues,
            meta={
                "limit": limit,
                "offset": offset,
                "count": len(issues),
            },
        )

    except Exception as e:
        logger.error(
            "get_consistency_issues_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CONSISTENCY_ISSUES_ERROR",
                    "message": f"Failed to get consistency issues: {e}",
                    "details": {},
                }
            },
        ) from e


@router.get(
    "/consistency-issues/summary",
    response_model=ConsistencyIssueSummaryResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "Consistency issue summary counts"},
    },
)
async def get_consistency_issues_summary(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    service: ConsistencyService = Depends(_get_consistency_service),
) -> ConsistencyIssueSummaryResponse:
    """Get summary counts of consistency issues for a matter.

    Story 5.4: Cross-Engine Consistency Checking

    Returns counts by status and severity for quick dashboard display.

    Args:
        matter_id: Matter UUID.
        membership: Validated matter membership.
        service: Consistency service.

    Returns:
        ConsistencyIssueSummaryResponse with counts.
    """
    logger.info(
        "get_consistency_issues_summary_requested",
        matter_id=matter_id,
        user_id=membership.user_id,
    )

    try:
        summary = await service.get_issue_summary(matter_id=matter_id)
        return ConsistencyIssueSummaryResponse(data=summary)

    except Exception as e:
        logger.error(
            "get_consistency_issues_summary_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CONSISTENCY_SUMMARY_ERROR",
                    "message": f"Failed to get consistency summary: {e}",
                    "details": {},
                }
            },
        ) from e


@router.patch(
    "/consistency-issues/{issue_id}",
    response_model=dict,
    responses={
        200: {"description": "Issue updated successfully"},
        404: {"description": "Issue not found"},
    },
)
async def update_consistency_issue(
    matter_id: str = Path(..., description="Matter UUID"),
    issue_id: str = Path(..., description="Issue UUID"),
    update: ConsistencyIssueUpdate = ...,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    service: ConsistencyService = Depends(_get_consistency_service),
) -> dict:
    """Update a consistency issue status.

    Story 5.4: Cross-Engine Consistency Checking

    Allows editors to mark issues as reviewed, resolved, or dismissed.

    Args:
        matter_id: Matter UUID.
        issue_id: Issue UUID.
        update: Update payload with status and optional notes.
        membership: Validated matter membership (editor or owner).
        service: Consistency service.

    Returns:
        Success message.
    """
    logger.info(
        "update_consistency_issue_requested",
        matter_id=matter_id,
        issue_id=issue_id,
        user_id=membership.user_id,
        new_status=update.status.value if update.status else None,
    )

    try:
        if update.status:
            success = await service.update_issue_status(
                issue_id=issue_id,
                status=update.status,
                user_id=membership.user_id,
                resolution_notes=update.resolution_notes,
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": {
                            "code": "ISSUE_NOT_FOUND",
                            "message": f"Issue {issue_id} not found or update failed",
                            "details": {"issue_id": issue_id},
                        }
                    },
                )

        return {"message": "Issue updated successfully", "issueId": issue_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_consistency_issue_failed",
            matter_id=matter_id,
            issue_id=issue_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ISSUE_UPDATE_ERROR",
                    "message": f"Failed to update issue: {e}",
                    "details": {},
                }
            },
        ) from e


@router.post(
    "/consistency-issues/check",
    response_model=dict,
    responses={
        200: {"description": "Consistency check completed"},
    },
)
async def run_consistency_check(
    matter_id: str = Path(..., description="Matter UUID"),
    engines: list[str] | None = Query(None, description="Engines to check"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    service: ConsistencyService = Depends(_get_consistency_service),
) -> dict:
    """Run consistency check for a matter.

    Story 5.4: Cross-Engine Consistency Checking

    Triggers a consistency check between analysis engines.
    Only available to editors and owners.

    Args:
        matter_id: Matter UUID.
        engines: Optional list of engines to check.
        membership: Validated matter membership (editor or owner).
        service: Consistency service.

    Returns:
        Check results summary.
    """
    logger.info(
        "run_consistency_check_requested",
        matter_id=matter_id,
        user_id=membership.user_id,
        engines=engines,
    )

    try:
        result = await service.check_matter_consistency(
            matter_id=matter_id,
            engines=engines,
        )

        return {
            "issuesFound": result.issues_found,
            "issuesCreated": result.issues_created,
            "enginesChecked": result.engines_checked,
            "durationMs": result.duration_ms,
        }

    except Exception as e:
        logger.error(
            "run_consistency_check_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CONSISTENCY_CHECK_ERROR",
                    "message": f"Failed to run consistency check: {e}",
                    "details": {},
                }
            },
        ) from e
