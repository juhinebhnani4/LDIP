"""Citation API routes for Act citation operations.

Provides endpoints for:
- Listing citations in a matter
- Getting citation details
- Getting Act Discovery Report
- Updating Act resolution status
- Citation verification (Story 3-3)

Story 3-1: Act Citation Extraction (AC: #4)
Story 3-3: Citation Verification (AC: #6)
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
    ActResolutionStatus,
    BatchVerificationResponse,
    Citation,
    CitationListItem,
    CitationResponse,
    CitationsListResponse,
    CitationSummaryItem,
    CitationSummaryResponse,
    PaginationMeta,
    VerificationResult,
    VerificationStatus,
)
from app.services.bounding_box_service import get_bounding_box_service

# Split-view specific imports
from app.services.storage_service import get_storage_service
from app.services.supabase.client import get_service_client
from app.workers.tasks.verification_tasks import (
    trigger_verification_on_act_upload,
    verify_citations_for_act,
    verify_single_citation,
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


@router.get("", response_model=CitationsListResponse, response_model_by_alias=True)
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
            # Get by document with proper database pagination
            citations, total = await storage_service.get_citations_by_document(
                document_id=document_id,
                matter_id=matter_id,
                page=page,
                per_page=per_page,
            )
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


@router.get("/stats", response_model=CitationStatsResponse, response_model_by_alias=True)
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


@router.get("/{citation_id}", response_model=CitationResponse, response_model_by_alias=True)
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


@router.get("/summary/by-act", response_model=CitationSummaryResponse, response_model_by_alias=True)
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


@router.get("/acts/discovery", response_model=ActDiscoveryResponse, response_model_by_alias=True)
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


@router.post("/acts/mark-uploaded", response_model=ActResolutionResponse, response_model_by_alias=True)
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


@router.post("/acts/mark-skipped", response_model=ActResolutionResponse, response_model_by_alias=True)
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


# =============================================================================
# Citation Verification (Story 3-3)
# =============================================================================


class VerifyActRequest(BaseModel):
    """Request to verify citations for an Act."""

    act_name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Act name to verify citations for",
        examples=["Negotiable Instruments Act, 1881"],
    )
    act_document_id: str = Field(
        ...,
        description="UUID of the uploaded Act document to verify against",
    )


class VerifyCitationRequest(BaseModel):
    """Request to verify a single citation."""

    act_document_id: str = Field(
        ...,
        description="UUID of the Act document to verify against",
    )
    act_name: str = Field(
        ...,
        description="Act name for context",
    )


@router.post("/verify", response_model=BatchVerificationResponse, response_model_by_alias=True)
async def verify_citations_batch(
    request: VerifyActRequest,
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    storage_service=Depends(_get_storage_service),
) -> BatchVerificationResponse:
    """Start batch verification of citations for an Act.

    Triggers an async Celery task to verify all citations referencing
    the specified Act against the uploaded Act document.

    Args:
        request: Verification request with Act name and document ID.
        matter_id: Matter UUID.
        membership: Validated matter membership (editor/owner required).
        storage_service: Citation storage service.

    Returns:
        BatchVerificationResponse with task ID and status.
    """
    logger.info(
        "verify_citations_batch_request",
        matter_id=matter_id,
        act_name=request.act_name,
        act_document_id=request.act_document_id,
        user_id=membership.user_id,
    )

    try:
        # Get citation count for this Act
        citations, total = await storage_service.get_citations_by_matter(
            matter_id=matter_id,
            act_name=request.act_name,
            page=1,
            per_page=1,
        )

        # Start verification task
        task = verify_citations_for_act.delay(
            matter_id=matter_id,
            act_name=request.act_name,
            act_document_id=request.act_document_id,
        )

        logger.info(
            "verify_citations_batch_started",
            matter_id=matter_id,
            act_name=request.act_name,
            task_id=task.id,
            total_citations=total,
        )

        return BatchVerificationResponse(
            task_id=task.id,
            status="started",
            total_citations=total,
            act_name=request.act_name,
        )

    except Exception as e:
        logger.error(
            "verify_citations_batch_error",
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
                    "message": "Failed to start verification",
                    "details": {},
                }
            },
        ) from e


@router.post("/{citation_id}/verify", response_model=BatchVerificationResponse, response_model_by_alias=True)
async def verify_single_citation_endpoint(
    request: VerifyCitationRequest,
    matter_id: str = Path(..., description="Matter UUID"),
    citation_id: str = Path(..., description="Citation UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    storage_service=Depends(_get_storage_service),
) -> BatchVerificationResponse:
    """Verify a single citation against an Act document.

    Triggers an async task to verify the specific citation.
    Useful for re-verification or on-demand verification.

    Args:
        request: Verification request with Act document ID.
        matter_id: Matter UUID.
        citation_id: Citation UUID to verify.
        membership: Validated matter membership (editor/owner required).
        storage_service: Citation storage service.

    Returns:
        BatchVerificationResponse with task ID.

    Raises:
        HTTPException 404: If citation not found.
    """
    logger.info(
        "verify_single_citation_request",
        matter_id=matter_id,
        citation_id=citation_id,
        act_document_id=request.act_document_id,
        user_id=membership.user_id,
    )

    try:
        # Verify citation exists
        citation = await storage_service.get_citation(citation_id, matter_id)

        if citation is None:
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

        # Start verification task
        task = verify_single_citation.delay(
            matter_id=matter_id,
            citation_id=citation_id,
            act_document_id=request.act_document_id,
            act_name=request.act_name,
        )

        logger.info(
            "verify_single_citation_started",
            matter_id=matter_id,
            citation_id=citation_id,
            task_id=task.id,
        )

        return BatchVerificationResponse(
            task_id=task.id,
            status="started",
            total_citations=1,
            act_name=request.act_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "verify_single_citation_error",
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
                    "message": "Failed to start verification",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Verification Details Endpoint
# =============================================================================


class VerificationDetailsResponse(BaseModel):
    """Response containing verification details for a citation."""

    data: dict = Field(
        ...,
        description="Verification details",
    )


@router.get("/{citation_id}/verification", response_model_by_alias=True)
async def get_verification_details(
    matter_id: str = Path(..., description="Matter UUID"),
    citation_id: str = Path(..., description="Citation UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    storage_service=Depends(_get_storage_service),
) -> VerificationDetailsResponse:
    """Get verification details for a citation.

    Returns the current verification status and any stored verification
    metadata for the specified citation.

    Args:
        matter_id: Matter UUID.
        citation_id: Citation UUID.
        membership: Validated matter membership.
        storage_service: Citation storage service.

    Returns:
        VerificationDetailsResponse with verification details.

    Raises:
        HTTPException 404: If citation not found.
    """
    logger.info(
        "get_verification_details_request",
        matter_id=matter_id,
        citation_id=citation_id,
        user_id=membership.user_id,
    )

    try:
        citation = await storage_service.get_citation(citation_id, matter_id)

        if citation is None:
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

        # Build verification details from citation
        verification_data = {
            "status": citation.verification_status.value,
            "sectionFound": citation.target_page is not None,
            "sectionText": None,  # Not stored in citation model
            "targetPage": citation.target_page,
            "targetBboxIds": citation.target_bbox_ids,
            "similarityScore": citation.confidence,
            "explanation": citation.extraction_metadata.get("verification_explanation"),
            "diffDetails": citation.extraction_metadata.get("diff_details"),
        }

        return VerificationDetailsResponse(data=verification_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_verification_details_error",
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
                    "message": "Failed to get verification details",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Act Upload with Auto-Verification Trigger
# =============================================================================


@router.post("/acts/mark-uploaded-verify", response_model=ActResolutionResponse, response_model_by_alias=True)
async def mark_act_uploaded_and_verify(
    request: MarkActUploadedRequest,
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    discovery_service=Depends(_get_discovery_service),
) -> ActResolutionResponse:
    """Mark an Act as uploaded and automatically trigger verification.

    Combines marking the Act as uploaded with triggering verification
    of all citations referencing this Act.

    Args:
        request: Act upload details.
        matter_id: Matter UUID.
        membership: Validated matter membership (editor/owner required).
        discovery_service: Act discovery service.

    Returns:
        Updated resolution status.
    """
    logger.info(
        "mark_act_uploaded_verify_request",
        matter_id=matter_id,
        act_name=request.act_name,
        act_document_id=request.act_document_id,
        user_id=membership.user_id,
    )

    try:
        # First mark as uploaded
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

        # Trigger verification automatically
        trigger_verification_on_act_upload.delay(
            matter_id=matter_id,
            act_name=request.act_name,
            act_document_id=request.act_document_id,
        )

        logger.info(
            "mark_act_uploaded_verify_success",
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
            "mark_act_uploaded_verify_error",
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


# =============================================================================
# Split-View Endpoint (Story 3-4)
# =============================================================================


class SplitViewBoundingBox(BaseModel):
    """Bounding box data for split view display."""

    model_config = ConfigDict(populate_by_name=True)

    bbox_id: str = Field(..., alias="bboxId", description="Bounding box UUID")
    x: float = Field(..., description="Normalized x coordinate (0-1)")
    y: float = Field(..., description="Normalized y coordinate (0-1)")
    width: float = Field(..., description="Normalized width (0-1)")
    height: float = Field(..., description="Normalized height (0-1)")
    text: str = Field(default="", description="Text content of bbox")


class DocumentViewDataModel(BaseModel):
    """Document view data for one side of split view."""

    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(..., alias="documentId", description="Document UUID")
    document_url: str = Field(..., alias="documentUrl", description="Signed URL for PDF")
    page_number: int = Field(..., alias="pageNumber", description="Page to display (1-indexed)")
    bounding_boxes: list[SplitViewBoundingBox] = Field(
        ..., alias="boundingBoxes", description="Bounding boxes to highlight"
    )


class SplitViewDataModel(BaseModel):
    """Complete split view data for citation display."""

    model_config = ConfigDict(populate_by_name=True)

    citation: Citation
    source_document: DocumentViewDataModel = Field(..., alias="sourceDocument")
    target_document: DocumentViewDataModel | None = Field(None, alias="targetDocument")
    verification: VerificationResult | None = None


class SplitViewResponseModel(BaseModel):
    """Response for split view endpoint."""

    data: SplitViewDataModel


@router.get("/{citation_id}/split-view", response_model=SplitViewResponseModel, response_model_by_alias=True)
async def get_citation_split_view(
    matter_id: str = Path(..., description="Matter UUID"),
    citation_id: str = Path(..., description="Citation UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    storage_service=Depends(_get_storage_service),
    discovery_service=Depends(_get_discovery_service),
) -> SplitViewResponseModel:
    """Get split-view data for a citation.

    Returns all data needed to render the split-view panel including:
    - Source document URL, page, and bounding boxes (case file)
    - Target Act document URL, page, and bounding boxes (if available)
    - Verification result with explanation

    Args:
        matter_id: Matter UUID.
        citation_id: Citation UUID.
        membership: Validated matter membership.
        storage_service: Citation storage service.
        discovery_service: Act discovery service.

    Returns:
        SplitViewResponseModel with source and target document data.

    Raises:
        HTTPException 404: If citation not found.
    """
    logger.info(
        "get_citation_split_view_request",
        matter_id=matter_id,
        citation_id=citation_id,
        user_id=membership.user_id,
    )

    try:
        # Get citation
        citation = await storage_service.get_citation(citation_id, matter_id)

        if citation is None:
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

        import asyncio
        # Get storage service for signed URLs
        file_storage = get_storage_service()
        bbox_service = get_bounding_box_service()

        # Build source document data (case file where citation was found)
        source_document_id = citation.document_id
        source_page = citation.source_page or 1

        # Get source document storage path
        client = get_service_client()
        doc_result = await asyncio.to_thread(
            lambda: client.table("documents").select("storage_path, filename").eq("id", source_document_id).single().execute()
        )

        if not doc_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "SOURCE_DOCUMENT_NOT_FOUND",
                        "message": "Source document not found",
                        "details": {},
                    }
                },
            )

        source_storage_path = doc_result.data["storage_path"]
        source_url = file_storage.get_signed_url(source_storage_path, expires_in=3600)

        # Get source bounding boxes (sync service, use to_thread)
        source_bboxes: list[SplitViewBoundingBox] = []
        if citation.source_bbox_ids:
            bboxes = await asyncio.to_thread(
                bbox_service.get_bounding_boxes_by_ids, citation.source_bbox_ids
            )
            source_bboxes = [
                SplitViewBoundingBox(
                    bbox_id=str(bbox["id"]),
                    x=bbox["x"],
                    y=bbox["y"],
                    width=bbox["width"],
                    height=bbox["height"],
                    text=bbox.get("text", ""),
                )
                for bbox in bboxes
            ]

        source_doc_data = DocumentViewDataModel(
            document_id=source_document_id,
            document_url=source_url,
            page_number=source_page,
            bounding_boxes=source_bboxes,
        )

        # Build target document data (Act document) if available
        target_doc_data: DocumentViewDataModel | None = None
        verification_result: VerificationResult | None = None

        if citation.verification_status not in (VerificationStatus.PENDING, VerificationStatus.ACT_UNAVAILABLE):
            # Get Act document info from act resolution
            act_resolution = await discovery_service.get_act_resolution_by_name(
                matter_id=matter_id,
                act_name=citation.act_name,
            )

            if act_resolution and act_resolution.act_document_id:
                # Get target document storage path
                target_doc_result = await asyncio.to_thread(
                    lambda: client.table("documents").select("storage_path, filename").eq("id", act_resolution.act_document_id).single().execute()
                )

                if target_doc_result.data:
                    target_storage_path = target_doc_result.data["storage_path"]
                    target_url = file_storage.get_signed_url(target_storage_path, expires_in=3600)

                    target_page = citation.target_page or 1

                    # Get target bounding boxes
                    target_bboxes: list[SplitViewBoundingBox] = []
                    if citation.target_bbox_ids:
                        target_bbox_data = await asyncio.to_thread(
                            bbox_service.get_bounding_boxes_by_ids, citation.target_bbox_ids
                        )
                        target_bboxes = [
                            SplitViewBoundingBox(
                                bbox_id=str(bbox["id"]),
                                x=bbox["x"],
                                y=bbox["y"],
                                width=bbox["width"],
                                height=bbox["height"],
                                text=bbox.get("text", ""),
                            )
                            for bbox in target_bbox_data
                        ]

                    target_doc_data = DocumentViewDataModel(
                        document_id=act_resolution.act_document_id,
                        document_url=target_url,
                        page_number=target_page,
                        bounding_boxes=target_bboxes,
                    )

        # Build verification result
        if citation.verification_status != VerificationStatus.PENDING:
            # Extract diff_details and convert to DiffDetail model if present
            diff_details_raw = citation.extraction_metadata.get("diff_details")
            diff_details = None
            if diff_details_raw and isinstance(diff_details_raw, dict):
                from app.models.citation import DiffDetail
                diff_details = DiffDetail(
                    citation_text=diff_details_raw.get("citation_text", ""),
                    act_text=diff_details_raw.get("act_text", ""),
                    match_type=diff_details_raw.get("match_type", "mismatch"),
                    differences=diff_details_raw.get("differences", []),
                )

            verification_result = VerificationResult(
                status=citation.verification_status,
                section_found=citation.target_page is not None,
                section_text=citation.extraction_metadata.get("section_text"),
                target_page=citation.target_page,
                target_bbox_ids=citation.target_bbox_ids or [],
                similarity_score=citation.confidence,
                explanation=citation.extraction_metadata.get("verification_explanation", ""),
                diff_details=diff_details,
            )

        split_view_data = SplitViewDataModel(
            citation=citation,
            source_document=source_doc_data,
            target_document=target_doc_data,
            verification=verification_result,
        )

        logger.info(
            "get_citation_split_view_success",
            matter_id=matter_id,
            citation_id=citation_id,
            has_target=target_doc_data is not None,
        )

        return SplitViewResponseModel(data=split_view_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_citation_split_view_error",
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
                    "message": "Failed to get split view data",
                    "details": {},
                }
            },
        ) from e
