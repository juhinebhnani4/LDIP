"""Reasoning Traces API routes for legal defensibility (Story 4.1).

Epic 4: Legal Defensibility (Gap Remediation)

Provides endpoints for:
- Listing reasoning traces for a matter
- Getting a specific trace (with hydration from cold storage)
- Getting traces for a specific finding
- Getting reasoning trace statistics

Implements:
- AC 4.1.4: API for retrieving full chain-of-thought
- AC 4.2.2: Transparent hydration from cold storage (< 5 seconds)
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
)
from app.models.reasoning_trace import (
    EngineType,
    ReasoningTraceListResponse,
    ReasoningTraceResponse,
    ReasoningTraceStatsResponse,
)
from app.services.reasoning_trace_service import (
    ReasoningTraceService,
    get_reasoning_trace_service,
)

router = APIRouter(prefix="/matters/{matter_id}/reasoning-traces", tags=["reasoning-traces"])
logger = structlog.get_logger(__name__)


def _get_service() -> ReasoningTraceService:
    """Get reasoning trace service instance."""
    return get_reasoning_trace_service()


# =============================================================================
# Story 4.1: Statistics Endpoint (Must be before /{trace_id})
# =============================================================================


@router.get(
    "/stats",
    response_model=ReasoningTraceStatsResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "Reasoning trace statistics"},
        403: {"description": "Access denied to matter"},
    },
)
async def get_reasoning_trace_stats(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])),
    service: ReasoningTraceService = Depends(_get_service),
) -> ReasoningTraceStatsResponse:
    """Get reasoning trace statistics for a matter.

    Story 4.1/4.2: Dashboard statistics including hot/cold storage counts.

    Args:
        matter_id: Matter UUID from path.
        membership: Matter membership from auth.
        service: Reasoning trace service.

    Returns:
        ReasoningTraceStatsResponse with aggregate statistics.
    """
    logger.info(
        "reasoning_trace_stats_requested",
        matter_id=matter_id,
        user_id=membership.user_id,
    )

    stats = await service.get_stats(matter_id)
    return ReasoningTraceStatsResponse(data=stats)


# =============================================================================
# Story 4.1: List Traces
# =============================================================================


@router.get(
    "",
    response_model=ReasoningTraceListResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "List of reasoning traces"},
        403: {"description": "Access denied to matter"},
    },
)
async def list_reasoning_traces(
    matter_id: str = Path(..., description="Matter UUID"),
    engine_type: EngineType | None = Query(None, description="Filter by engine type"),
    include_archived: bool = Query(False, description="Include archived traces"),
    limit: int = Query(100, ge=1, le=500, description="Maximum traces to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    membership: MatterMembership = Depends(require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])),
    service: ReasoningTraceService = Depends(_get_service),
) -> ReasoningTraceListResponse:
    """List reasoning traces for a matter.

    Story 4.1: Paginated list view with optional filtering.

    Args:
        matter_id: Matter UUID from path.
        engine_type: Optional filter by engine type.
        include_archived: Whether to include archived traces.
        limit: Maximum number of traces to return.
        offset: Pagination offset.
        membership: Matter membership from auth.
        service: Reasoning trace service.

    Returns:
        ReasoningTraceListResponse with summaries and pagination metadata.
    """
    logger.info(
        "reasoning_traces_listed",
        matter_id=matter_id,
        user_id=membership.user_id,
        engine_type=engine_type.value if engine_type else None,
        include_archived=include_archived,
    )

    traces = await service.get_traces_for_matter(
        matter_id=matter_id,
        engine_type=engine_type,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )

    return ReasoningTraceListResponse(
        data=traces,
        meta={
            "limit": limit,
            "offset": offset,
            "count": len(traces),
            "hasMore": len(traces) == limit,
        },
    )


# =============================================================================
# Story 4.1: Get Single Trace
# =============================================================================


@router.get(
    "/{trace_id}",
    response_model=ReasoningTraceResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "Reasoning trace details"},
        403: {"description": "Access denied to matter"},
        404: {"description": "Trace not found"},
    },
)
async def get_reasoning_trace(
    matter_id: str = Path(..., description="Matter UUID"),
    trace_id: str = Path(..., description="Trace UUID"),
    membership: MatterMembership = Depends(require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])),
    service: ReasoningTraceService = Depends(_get_service),
) -> ReasoningTraceResponse:
    """Get a specific reasoning trace.

    Story 4.1: AC 4.1.4 - Retrieve full chain-of-thought.
    Story 4.2: AC 4.2.2 - Transparent hydration from cold storage.

    Args:
        matter_id: Matter UUID from path.
        trace_id: Trace UUID from path.
        membership: Matter membership from auth.
        service: Reasoning trace service.

    Returns:
        ReasoningTraceResponse with full trace details.

    Raises:
        HTTPException: 404 if trace not found.
    """
    logger.info(
        "reasoning_trace_requested",
        matter_id=matter_id,
        trace_id=trace_id,
        user_id=membership.user_id,
    )

    trace = await service.get_trace(trace_id=trace_id, matter_id=matter_id)

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "TRACE_NOT_FOUND",
                    "message": "Reasoning trace not found",
                }
            },
        )

    return ReasoningTraceResponse(data=trace)


# =============================================================================
# Story 4.1: Get Traces for Finding
# =============================================================================


@router.get(
    "/finding/{finding_id}",
    response_model=ReasoningTraceListResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "Reasoning traces for finding"},
        403: {"description": "Access denied to matter"},
    },
)
async def get_traces_for_finding(
    matter_id: str = Path(..., description="Matter UUID"),
    finding_id: str = Path(..., description="Finding UUID"),
    membership: MatterMembership = Depends(require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])),
    service: ReasoningTraceService = Depends(_get_service),
) -> ReasoningTraceListResponse:
    """Get all reasoning traces for a specific finding.

    Story 4.1: AC 4.1.4 - Reasoning linked to findings.

    Args:
        matter_id: Matter UUID from path.
        finding_id: Finding UUID from path.
        membership: Matter membership from auth.
        service: Reasoning trace service.

    Returns:
        ReasoningTraceListResponse with traces for the finding.
    """
    logger.info(
        "reasoning_traces_for_finding_requested",
        matter_id=matter_id,
        finding_id=finding_id,
        user_id=membership.user_id,
    )

    traces = await service.get_traces_for_finding(
        finding_id=finding_id,
        matter_id=matter_id,
    )

    # Convert full traces to summaries for consistent response format
    from app.models.reasoning_trace import ReasoningTraceSummary

    summaries = [
        ReasoningTraceSummary(
            id=t.id,
            engine_type=t.engine_type,
            model_used=t.model_used,
            reasoning_preview=(
                t.reasoning_text[:200] + "..."
                if len(t.reasoning_text) > 200
                else t.reasoning_text
            ),
            confidence_score=t.confidence_score,
            created_at=t.created_at,
            is_archived=t.archived_at is not None,
        )
        for t in traces
    ]

    return ReasoningTraceListResponse(
        data=summaries,
        meta={
            "findingId": finding_id,
            "count": len(summaries),
        },
    )
