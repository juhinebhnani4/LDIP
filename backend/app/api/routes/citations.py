"""Citation API routes for Act citation operations.

Provides endpoints for:
- Listing citations in a matter
- Getting citation details
- Getting Act Discovery Report
- Updating Act resolution status

Story 3-1: Act Citation Extraction (AC: #4)
"""

import math

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
)
from app.engines.citation import (
    get_act_discovery_service,
    get_citation_storage_service,
)
from app.models.citation import (
    ActDiscoveryResponse,
    ActDiscoverySummary,
    ActResolution,
    ActResolutionStatus,
    Citation,
    CitationListItem,
    CitationResponse,
    CitationsListResponse,
    CitationSummaryItem,
    CitationSummaryResponse,
    PaginationMeta,
    UserAction,
    VerificationStatus,
)


# =============================================================================
# Request/Response Models
# =============================================================================


class MarkActUploadedRequest(BaseModel):
    """Request to mark an Act as uploaded."""

    act_name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Act name (will be normalized)",
        examples=["Negotiable Instruments Act, 1881"],
    )
    act_document_id: str = Field(
        ...,
        description="UUID of the uploaded Act document",
    )


class MarkActSkippedRequest(BaseModel):
    """Request to mark an Act as skipped."""

    act_name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Act name (will be normalized)",
        examples=["Negotiable Instruments Act, 1881"],
    )


class ActResolutionResponse(BaseModel):
    """Response for Act resolution update."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(..., description="Whether update was successful")
    act_name: str = Field(..., alias="actName", description="Act display name")
    resolution_status: ActResolutionStatus = Field(
        ..., alias="resolutionStatus", description="New resolution status"
    )


class CitationStatsResponse(BaseModel):
    """Response for citation statistics."""

    model_config = ConfigDict(populate_by_name=True)

    total_citations: int = Field(..., alias="totalCitations", description="Total citation count")
    unique_acts: int = Field(..., alias="uniqueActs", description="Number of unique Acts")
    verified_count: int = Field(..., alias="verifiedCount", description="Verified citations")
    pending_count: int = Field(..., alias="pendingCount", description="Pending verification")
    missing_acts_count: int = Field(..., alias="missingActsCount", description="Missing Acts")


router = APIRouter(prefix="/matters/{matter_id}/citations", tags=["citations"])
logger = structlog.get_logger(__name__)


def _get_storage_service():
    """Get citation storage service instance."""
    return get_citation_storage_service()


def _get_discovery_service():
    """Get act discovery service instance."""
    return get_act_discovery_service()


# =============================================================================
# List Citations
# =============================================================================


@router.get("", response_model=CitationsListResponse)
async def list_citations(
    matter_id: str = Path(..., description="Matter UUID"),
    act_name: str | None = Query(None, description="Filter by Act name"),
    verification_status: VerificationStatus | None = Query(
        None, description="Filter by verification status"
    ),
    document_id: str | None = Query(None, description="Filter by source document"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    storage_service=Depends(_get_storage_service),
) -> CitationsListResponse:
    """List all citations in a matter.

    Returns paginated list of citations with filtering options.
    Results are sorted by creation date (most recent first).

    Args:
        matter_id: Matter UUID.
        act_name: Optional filter by Act name.
        verification_status: Optional filter by verification status.
        document_id: Optional filter by source document.
        page: Page number (1-indexed).
        per_page: Items per page.
        membership: Validated matter membership.
        storage_service: Citation storage service.

    Returns:
        Paginated list of citations.
    """
    logger.info(
        "list_citations_request",
        matter_id=matter_id,
        act_name=act_name,
        verification_status=verification_status.value if verification_status else None,
        document_id=document_id,
        page=page,
        per_page=per_page,
        user_id=membership.user_id,
    )

    try:
        if document_id:
            # Get by document
            citations = await storage_service.get_citations_by_document(
                document_id=document_id,
                matter_id=matter_id,
            )
            # Apply pagination manually
            total = len(citations)
            offset = (page - 1) * per_page
            citations = citations[offset : offset + per_page]
        else:
            # Get by matter with filters
            citations, total = await storage_service.get_citations_by_matter(
                matter_id=matter_id,
                act_name=act_name,
                verification_status=verification_status,
                page=page,
                per_page=per_page,
            )

        # Convert to list items
        items = [
            CitationListItem(
                id=c.id,
                act_name=c.act_name,
                section_number=c.section_number,
                subsection=c.subsection,
                raw_citation_text=c.raw_citation_text,
                source_page=c.source_page,
                verification_status=c.verification_status,
                confidence=c.confidence,
                document_id=c.document_id,
                document_name=c.document_name,
            )
            for c in citations
        ]

        total_pages = math.ceil(total / per_page) if total > 0 else 0

        logger.info(
            "list_citations_success",
            matter_id=matter_id,
            citation_count=len(items),
            total=total,
        )

        return CitationsListResponse(
            data=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            ),
        )

    except Exception as e:
        logger.error(
            "list_citations_error",
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to list citations",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Citation Statistics (MUST be before /{citation_id} to avoid path collision)
# =============================================================================


@router.get("/stats", response_model=CitationStatsResponse)
async def get_citation_stats(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    discovery_service=Depends(_get_discovery_service),
    storage_service=Depends(_get_storage_service),
) -> CitationStatsResponse:
    """Get citation statistics for a matter.

    Returns summary statistics including total citations,
    unique Acts, and verification status breakdown.

    Args:
        matter_id: Matter UUID.
        membership: Validated matter membership.
        discovery_service: Act discovery service.
        storage_service: Citation storage service.

    Returns:
        Citation statistics.
    """
    logger.info(
        "get_citation_stats_request",
        matter_id=matter_id,
        user_id=membership.user_id,
    )

    try:
        # Get discovery stats
        discovery_stats = await discovery_service.get_discovery_stats(matter_id)

        # Get citation counts for verification breakdown
        counts = await storage_service.get_citation_counts_by_act(matter_id)

        total_citations = sum(c["citation_count"] for c in counts)
        verified_count = sum(c.get("verified_count", 0) for c in counts)
        pending_count = sum(c.get("pending_count", 0) for c in counts)

        logger.info(
            "get_citation_stats_success",
            matter_id=matter_id,
            total_citations=total_citations,
            unique_acts=discovery_stats["total_acts"],
        )

        return CitationStatsResponse(
            total_citations=total_citations,
            unique_acts=discovery_stats["total_acts"],
            verified_count=verified_count,
            pending_count=pending_count,
            missing_acts_count=discovery_stats["missing_count"],
        )

    except Exception as e:
        logger.error(
            "get_citation_stats_error",
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get citation statistics",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Get Single Citation
# =============================================================================


@router.get("/{citation_id}", response_model=CitationResponse)
async def get_citation(
    matter_id: str = Path(..., description="Matter UUID"),
    citation_id: str = Path(..., description="Citation UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    storage_service=Depends(_get_storage_service),
) -> CitationResponse:
    """Get a single citation by ID.

    Returns full citation details including source location,
    verification status, and any matched Act document location.

    Args:
        matter_id: Matter UUID.
        citation_id: Citation UUID.
        membership: Validated matter membership.
        storage_service: Citation storage service.

    Returns:
        Citation details.

    Raises:
        HTTPException 404: If citation not found.
    """
    logger.info(
        "get_citation_request",
        matter_id=matter_id,
        citation_id=citation_id,
        user_id=membership.user_id,
    )

    try:
        citation = await storage_service.get_citation(citation_id, matter_id)

        if citation is None:
            logger.warning(
                "get_citation_not_found",
                matter_id=matter_id,
                citation_id=citation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "CITATION_NOT_FOUND",
                        "message": f"Citation {citation_id} not found",
                        "details": {},
                    }
                },
            )

        logger.info(
            "get_citation_success",
            matter_id=matter_id,
            citation_id=citation_id,
        )

        return CitationResponse(data=citation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_citation_error",
            matter_id=matter_id,
            citation_id=citation_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get citation",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Citation Summary
# =============================================================================


@router.get("/summary/by-act", response_model=CitationSummaryResponse)
async def get_citation_summary(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    storage_service=Depends(_get_storage_service),
) -> CitationSummaryResponse:
    """Get citation counts grouped by Act.

    Returns summary of citations per Act including verified and pending counts.
    Useful for showing which Acts are most frequently cited.

    Args:
        matter_id: Matter UUID.
        membership: Validated matter membership.
        storage_service: Citation storage service.

    Returns:
        Citation summary grouped by Act.
    """
    logger.info(
        "get_citation_summary_request",
        matter_id=matter_id,
        user_id=membership.user_id,
    )

    try:
        counts = await storage_service.get_citation_counts_by_act(matter_id)

        items = [
            CitationSummaryItem(
                act_name=c["act_name"],
                citation_count=c["citation_count"],
                verified_count=c.get("verified_count", 0),
                pending_count=c.get("pending_count", 0),
            )
            for c in counts
        ]

        logger.info(
            "get_citation_summary_success",
            matter_id=matter_id,
            act_count=len(items),
        )

        return CitationSummaryResponse(data=items)

    except Exception as e:
        logger.error(
            "get_citation_summary_error",
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get citation summary",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Act Discovery Report
# =============================================================================


@router.get("/acts/discovery", response_model=ActDiscoveryResponse)
async def get_act_discovery_report(
    matter_id: str = Path(..., description="Matter UUID"),
    include_available: bool = Query(
        True, description="Include Acts that are already available"
    ),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    discovery_service=Depends(_get_discovery_service),
) -> ActDiscoveryResponse:
    """Get Act Discovery Report.

    Returns list of all Acts referenced in the matter with their resolution status.
    Shows which Acts are uploaded, missing, or skipped.

    This is the primary endpoint for the "Missing Acts" UI.

    Args:
        matter_id: Matter UUID.
        include_available: Whether to include Acts that are already available.
        membership: Validated matter membership.
        discovery_service: Act discovery service.

    Returns:
        Act Discovery Report.
    """
    logger.info(
        "get_act_discovery_report_request",
        matter_id=matter_id,
        include_available=include_available,
        user_id=membership.user_id,
    )

    try:
        report = await discovery_service.get_discovery_report(
            matter_id=matter_id,
            include_available=include_available,
        )

        logger.info(
            "get_act_discovery_report_success",
            matter_id=matter_id,
            act_count=len(report),
        )

        return ActDiscoveryResponse(data=report)

    except Exception as e:
        logger.error(
            "get_act_discovery_report_error",
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get Act discovery report",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Act Resolution Management
# =============================================================================


@router.post("/acts/mark-uploaded", response_model=ActResolutionResponse)
async def mark_act_uploaded(
    request: MarkActUploadedRequest,
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    discovery_service=Depends(_get_discovery_service),
) -> ActResolutionResponse:
    """Mark an Act as uploaded.

    Updates the act resolution to indicate the Act document is now available.
    This should be called after uploading an Act document.

    Args:
        request: Act upload details.
        matter_id: Matter UUID.
        membership: Validated matter membership (editor/owner required).
        discovery_service: Act discovery service.

    Returns:
        Updated resolution status.
    """
    logger.info(
        "mark_act_uploaded_request",
        matter_id=matter_id,
        act_name=request.act_name,
        act_document_id=request.act_document_id,
        user_id=membership.user_id,
    )

    try:
        success = await discovery_service.mark_act_uploaded(
            matter_id=matter_id,
            act_name=request.act_name,
            act_document_id=request.act_document_id,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ACT_NOT_FOUND",
                        "message": f"Act '{request.act_name}' not found in resolutions",
                        "details": {},
                    }
                },
            )

        logger.info(
            "mark_act_uploaded_success",
            matter_id=matter_id,
            act_name=request.act_name,
        )

        return ActResolutionResponse(
            success=True,
            act_name=request.act_name,
            resolution_status=ActResolutionStatus.AVAILABLE,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "mark_act_uploaded_error",
            matter_id=matter_id,
            act_name=request.act_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to mark Act as uploaded",
                    "details": {},
                }
            },
        ) from e


@router.post("/acts/mark-skipped", response_model=ActResolutionResponse)
async def mark_act_skipped(
    request: MarkActSkippedRequest,
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    discovery_service=Depends(_get_discovery_service),
) -> ActResolutionResponse:
    """Mark an Act as skipped.

    User chooses not to upload this Act (maybe they don't have it).
    The Act will no longer appear in the "missing" list.

    Args:
        request: Act to skip.
        matter_id: Matter UUID.
        membership: Validated matter membership (editor/owner required).
        discovery_service: Act discovery service.

    Returns:
        Updated resolution status.
    """
    logger.info(
        "mark_act_skipped_request",
        matter_id=matter_id,
        act_name=request.act_name,
        user_id=membership.user_id,
    )

    try:
        success = await discovery_service.mark_act_skipped(
            matter_id=matter_id,
            act_name=request.act_name,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "ACT_NOT_FOUND",
                        "message": f"Act '{request.act_name}' not found in resolutions",
                        "details": {},
                    }
                },
            )

        logger.info(
            "mark_act_skipped_success",
            matter_id=matter_id,
            act_name=request.act_name,
        )

        return ActResolutionResponse(
            success=True,
            act_name=request.act_name,
            resolution_status=ActResolutionStatus.SKIPPED,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "mark_act_skipped_error",
            matter_id=matter_id,
            act_name=request.act_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to mark Act as skipped",
                    "details": {},
                }
            },
        ) from e


