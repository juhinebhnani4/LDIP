"""Verifications API routes for attorney finding verification workflow.

Story 8-4: Implement Finding Verifications Table
Epic 8: Safety Layer (Guardrails, Policing, Verification)

Provides endpoints for:
- Listing verification records for a matter
- Getting pending verification queue
- Getting verification statistics
- Recording verification decisions (approve/reject/flag)
- Bulk verification operations
- Export eligibility check

Implements:
- FR10: Attorney Verification Workflow
- NFR23: Court-defensible verification workflow with forensic trail
- ADR-004: Verification Tier Thresholds (>90% optional, 70-90% suggested, <70% required)
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status, Body

from app.api.deps import (
    MatterMembership,
    MatterRole,
    get_db,
    require_matter_role,
)
from app.models.verification import (
    ApproveVerificationRequest,
    BulkVerificationRequest,
    BulkVerificationResponse,
    ExportEligibilityResult,
    FindingVerification,
    FindingVerificationUpdate,
    FlagVerificationRequest,
    RejectVerificationRequest,
    VerificationDecision,
    VerificationListResponse,
    VerificationQueueItem,
    VerificationQueueResponse,
    VerificationResponse,
    VerificationStats,
    VerificationStatsResponse,
)
from app.services.verification import (
    VerificationService,
    VerificationServiceError,
    get_verification_service,
    ExportEligibilityService,
    get_export_eligibility_service,
)

router = APIRouter(prefix="/matters/{matter_id}/verifications", tags=["verifications"])
logger = structlog.get_logger(__name__)


def _get_verification_service() -> VerificationService:
    """Get verification service instance.

    Story 8-4: Service factory for dependency injection.
    """
    return get_verification_service()


def _get_export_service() -> ExportEligibilityService:
    """Get export eligibility service instance.

    Story 8-4: Service factory for dependency injection.
    """
    return get_export_eligibility_service()


# =============================================================================
# Story 8-4: Statistics Endpoint (Must be before /{verification_id})
# =============================================================================


@router.get(
    "/stats",
    response_model=VerificationStatsResponse,
    responses={
        200: {"description": "Verification statistics for matter"},
        404: {"description": "Matter not found"},
    },
)
async def get_verification_stats(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    db=Depends(get_db),
    service: VerificationService = Depends(_get_verification_service),
) -> VerificationStatsResponse:
    """Get verification statistics for dashboard.

    Story 8-4: Task 7.4 - Statistics endpoint for verification dashboard.

    Returns aggregate counts by decision status and verification tier,
    plus export eligibility status.

    Args:
        matter_id: Matter UUID.
        membership: Validated matter membership.
        db: Supabase client.
        service: Verification service.

    Returns:
        VerificationStatsResponse with statistics.
    """
    try:
        stats = await service.get_verification_stats(matter_id, db)
        return VerificationStatsResponse(data=stats)
    except VerificationServiceError as e:
        logger.error(
            "get_verification_stats_failed",
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
        ) from e


# =============================================================================
# Story 8-4: Pending Queue Endpoint (Must be before /{verification_id})
# =============================================================================


@router.get(
    "/pending",
    response_model=VerificationQueueResponse,
    responses={
        200: {"description": "Pending verification queue"},
        404: {"description": "Matter not found"},
    },
)
async def get_pending_verifications(
    matter_id: str = Path(..., description="Matter UUID"),
    limit: int = Query(50, ge=1, le=100, description="Max items to return"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    db=Depends(get_db),
    service: VerificationService = Depends(_get_verification_service),
) -> VerificationQueueResponse:
    """Get pending verification queue for UI.

    Story 8-4: Task 7.3 - For Story 8-5 verification queue UI.

    Returns pending verifications sorted by:
    1. Requirement tier (REQUIRED first, then SUGGESTED, then OPTIONAL)
    2. Creation date (oldest first)

    Args:
        matter_id: Matter UUID.
        limit: Max items to return (default 50, max 100).
        membership: Validated matter membership.
        db: Supabase client.
        service: Verification service.

    Returns:
        VerificationQueueResponse with pending items.
    """
    try:
        items = await service.get_pending_verifications(matter_id, db, limit)
        return VerificationQueueResponse(
            data=items,
            meta={"limit": limit, "count": len(items)},
        )
    except VerificationServiceError as e:
        logger.error(
            "get_pending_verifications_failed",
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
        ) from e


# =============================================================================
# Story 8-4: Export Eligibility Endpoint (Must be before /{verification_id})
# =============================================================================


@router.get(
    "/export-eligibility",
    response_model=ExportEligibilityResult,
    responses={
        200: {"description": "Export eligibility check result"},
        404: {"description": "Matter not found"},
    },
)
async def check_export_eligibility(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    db=Depends(get_db),
    export_service: ExportEligibilityService = Depends(_get_export_service),
) -> ExportEligibilityResult:
    """Check if matter is eligible for export.

    Story 8-4: AC #5, Task 8.4 - Export eligibility check for Story 12-3.

    Returns eligibility status and list of blocking findings.
    Export is blocked if there are unverified findings with
    confidence < 70% (REQUIRED verification tier).

    Args:
        matter_id: Matter UUID.
        membership: Validated matter membership.
        db: Supabase client.
        export_service: Export eligibility service.

    Returns:
        ExportEligibilityResult with eligibility and blocking findings.
    """
    return await export_service.check_export_eligibility(matter_id, db)


# =============================================================================
# Story 8-4: List Verifications Endpoint
# =============================================================================


@router.get(
    "",
    response_model=VerificationListResponse,
    responses={
        200: {"description": "List of verification records"},
        404: {"description": "Matter not found"},
    },
)
async def list_verifications(
    matter_id: str = Path(..., description="Matter UUID"),
    decision: VerificationDecision | None = Query(
        None, description="Filter by decision (pending, approved, rejected, flagged)"
    ),
    limit: int = Query(100, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    db=Depends(get_db),
    service: VerificationService = Depends(_get_verification_service),
) -> VerificationListResponse:
    """List verification records for a matter.

    Story 8-4: Task 7.2 - List verifications with optional filtering.

    Args:
        matter_id: Matter UUID.
        decision: Optional filter by decision status.
        limit: Max items to return.
        offset: Items to skip for pagination.
        membership: Validated matter membership.
        db: Supabase client.
        service: Verification service.

    Returns:
        VerificationListResponse with verification records.
    """
    try:
        verifications = await service.list_verifications(
            matter_id, db, decision, limit, offset
        )
        return VerificationListResponse(data=verifications)
    except VerificationServiceError as e:
        logger.error(
            "list_verifications_failed",
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
        ) from e


# =============================================================================
# Story 8-4: Bulk Verification Endpoint
# =============================================================================


@router.post(
    "/bulk",
    response_model=BulkVerificationResponse,
    responses={
        200: {"description": "Bulk verification results"},
        400: {"description": "Invalid request"},
        404: {"description": "Matter not found"},
    },
)
async def bulk_update_verifications(
    matter_id: str = Path(..., description="Matter UUID"),
    request: BulkVerificationRequest = Body(...),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    db=Depends(get_db),
    service: VerificationService = Depends(_get_verification_service),
) -> BulkVerificationResponse:
    """Bulk update verification decisions.

    Story 8-4: Task 7.8, Task 4.8 - Bulk approve/reject for Story 8-5 queue UI.

    Limited to 100 verifications per request.

    Args:
        matter_id: Matter UUID.
        request: Bulk verification request with IDs and decision.
        membership: Validated matter membership (editor/owner required).
        db: Supabase client.
        service: Verification service.

    Returns:
        BulkVerificationResponse with update results.
    """
    logger.info(
        "bulk_verification_requested",
        matter_id=matter_id,
        user_id=membership.user_id,
        count=len(request.verification_ids),
        decision=request.decision.value,
    )

    try:
        result = await service.bulk_update_verifications(
            verification_ids=request.verification_ids,
            decision=request.decision,
            verified_by=membership.user_id,
            supabase=db,
            notes=request.notes,
        )

        return BulkVerificationResponse(
            data=result,
            updated_count=result["updated_count"],
            failed_ids=result["failed_ids"],
        )
    except VerificationServiceError as e:
        logger.error(
            "bulk_verification_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 8-4: Get Verification by ID
# =============================================================================


@router.get(
    "/{verification_id}",
    response_model=VerificationResponse,
    responses={
        200: {"description": "Verification record"},
        404: {"description": "Verification not found"},
    },
)
async def get_verification(
    matter_id: str = Path(..., description="Matter UUID"),
    verification_id: str = Path(..., description="Verification UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    db=Depends(get_db),
    service: VerificationService = Depends(_get_verification_service),
) -> VerificationResponse:
    """Get a single verification record.

    Story 8-4: Get verification details by ID.

    Args:
        matter_id: Matter UUID.
        verification_id: Verification UUID.
        membership: Validated matter membership.
        db: Supabase client.
        service: Verification service.

    Returns:
        VerificationResponse with verification record.
    """
    try:
        verification = await service.get_verification_by_id(verification_id, db)
        return VerificationResponse(data=verification)
    except VerificationServiceError as e:
        if e.code == "VERIFICATION_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "VERIFICATION_NOT_FOUND",
                        "message": f"Verification {verification_id} not found",
                        "details": {"verification_id": verification_id},
                    }
                },
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 8-4: Approve Verification
# =============================================================================


@router.post(
    "/{verification_id}/approve",
    response_model=VerificationResponse,
    responses={
        200: {"description": "Verification approved"},
        404: {"description": "Verification not found"},
    },
)
async def approve_verification(
    matter_id: str = Path(..., description="Matter UUID"),
    verification_id: str = Path(..., description="Verification UUID"),
    request: ApproveVerificationRequest = Body(default=ApproveVerificationRequest()),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    db=Depends(get_db),
    service: VerificationService = Depends(_get_verification_service),
) -> VerificationResponse:
    """Approve a finding verification.

    Story 8-4: AC #2, Task 7.5 - Attorney approval of finding.

    Args:
        matter_id: Matter UUID.
        verification_id: Verification UUID.
        request: Optional approval request with notes and confidence adjustment.
        membership: Validated matter membership (editor/owner required).
        db: Supabase client.
        service: Verification service.

    Returns:
        VerificationResponse with updated record.
    """
    logger.info(
        "verification_approve_requested",
        matter_id=matter_id,
        verification_id=verification_id,
        user_id=membership.user_id,
    )

    try:
        verification = await service.record_verification_decision(
            verification_id=verification_id,
            update_data=FindingVerificationUpdate(
                decision=VerificationDecision.APPROVED,
                notes=request.notes,
                confidence_after=request.confidence_after,
            ),
            verified_by=membership.user_id,
            supabase=db,
        )
        return VerificationResponse(data=verification)
    except VerificationServiceError as e:
        if e.code == "VERIFICATION_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "VERIFICATION_NOT_FOUND",
                        "message": f"Verification {verification_id} not found",
                        "details": {"verification_id": verification_id},
                    }
                },
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 8-4: Reject Verification
# =============================================================================


@router.post(
    "/{verification_id}/reject",
    response_model=VerificationResponse,
    responses={
        200: {"description": "Verification rejected"},
        400: {"description": "Notes required for rejection"},
        404: {"description": "Verification not found"},
    },
)
async def reject_verification(
    matter_id: str = Path(..., description="Matter UUID"),
    verification_id: str = Path(..., description="Verification UUID"),
    request: RejectVerificationRequest = Body(...),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    db=Depends(get_db),
    service: VerificationService = Depends(_get_verification_service),
) -> VerificationResponse:
    """Reject a finding verification.

    Story 8-4: AC #2, Task 7.6 - Attorney rejection of finding.

    Notes are required for rejections to provide audit trail.

    Args:
        matter_id: Matter UUID.
        verification_id: Verification UUID.
        request: Rejection request with required notes.
        membership: Validated matter membership (editor/owner required).
        db: Supabase client.
        service: Verification service.

    Returns:
        VerificationResponse with updated record.
    """
    logger.info(
        "verification_reject_requested",
        matter_id=matter_id,
        verification_id=verification_id,
        user_id=membership.user_id,
    )

    try:
        verification = await service.record_verification_decision(
            verification_id=verification_id,
            update_data=FindingVerificationUpdate(
                decision=VerificationDecision.REJECTED,
                notes=request.notes,
            ),
            verified_by=membership.user_id,
            supabase=db,
        )
        return VerificationResponse(data=verification)
    except VerificationServiceError as e:
        if e.code == "VERIFICATION_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "VERIFICATION_NOT_FOUND",
                        "message": f"Verification {verification_id} not found",
                        "details": {"verification_id": verification_id},
                    }
                },
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 8-4: Flag Verification
# =============================================================================


@router.post(
    "/{verification_id}/flag",
    response_model=VerificationResponse,
    responses={
        200: {"description": "Verification flagged"},
        404: {"description": "Verification not found"},
    },
)
async def flag_verification(
    matter_id: str = Path(..., description="Matter UUID"),
    verification_id: str = Path(..., description="Verification UUID"),
    request: FlagVerificationRequest = Body(...),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    db=Depends(get_db),
    service: VerificationService = Depends(_get_verification_service),
) -> VerificationResponse:
    """Flag a finding verification for further review.

    Story 8-4: AC #2, Task 7.7 - Attorney flags finding for review.

    Used when attorney needs additional review or consultation
    before making approve/reject decision.

    Args:
        matter_id: Matter UUID.
        verification_id: Verification UUID.
        request: Flag request with required notes.
        membership: Validated matter membership (editor/owner required).
        db: Supabase client.
        service: Verification service.

    Returns:
        VerificationResponse with updated record.
    """
    logger.info(
        "verification_flag_requested",
        matter_id=matter_id,
        verification_id=verification_id,
        user_id=membership.user_id,
    )

    try:
        verification = await service.record_verification_decision(
            verification_id=verification_id,
            update_data=FindingVerificationUpdate(
                decision=VerificationDecision.FLAGGED,
                notes=request.notes,
            ),
            verified_by=membership.user_id,
            supabase=db,
        )
        return VerificationResponse(data=verification)
    except VerificationServiceError as e:
        if e.code == "VERIFICATION_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "VERIFICATION_NOT_FOUND",
                        "message": f"Verification {verification_id} not found",
                        "details": {"verification_id": verification_id},
                    }
                },
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {},
                }
            },
        ) from e
