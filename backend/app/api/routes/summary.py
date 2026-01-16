"""Summary API routes for Matter Executive Summary.

Story 14.1: Summary API Endpoint (Task 3)
Story 14.4: Summary Verification API (Task 5)
Story 14.6: Summary Edit API (Task 1, 2)

Provides endpoints for:
- GET /api/matters/{matter_id}/summary - Retrieve AI-generated executive summaries
- POST /api/matters/{matter_id}/summary/verify - Record verification decisions
- POST /api/matters/{matter_id}/summary/notes - Add notes to sections
- GET /api/matters/{matter_id}/summary/verifications - List verification records
- PUT /api/matters/{matter_id}/summary/sections/{section_type} - Save edited content
- POST /api/matters/{matter_id}/summary/regenerate - Regenerate section with fresh AI

CRITICAL: Uses matter access validation for Layer 4 security.
"""

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.api.deps import (
    MatterAccessContext,
    MatterRole,
    validate_matter_access,
)
from app.core.rate_limit import READONLY_RATE_LIMIT, STANDARD_RATE_LIMIT, limiter
from app.models.summary import (
    MatterSummaryResponse,
    SummaryEditCreate,
    SummaryEditResponse,
    SummaryNoteCreate,
    SummaryNoteResponse,
    SummaryRegenerateRequest,
    SummarySectionTypeEnum,
    SummaryVerificationCreate,
    SummaryVerificationResponse,
    SummaryVerificationsListResponse,
)
from app.services.summary_edit_service import (
    SummaryEditService,
    SummaryEditServiceError,
    get_summary_edit_service,
)
from app.services.summary_service import (
    SummaryService,
    SummaryServiceError,
    get_summary_service,
)
from app.services.summary_verification_service import (
    SummaryVerificationService,
    SummaryVerificationServiceError,
    get_summary_verification_service,
)

router = APIRouter(prefix="/matters", tags=["summary"])
logger = structlog.get_logger(__name__)


def _handle_service_error(error: SummaryServiceError) -> HTTPException:
    """Convert service errors to HTTP exceptions."""
    return HTTPException(
        status_code=error.status_code,
        detail={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {},
            }
        },
    )


@router.get(
    "/{matter_id}/summary",
    response_model=MatterSummaryResponse,
    summary="Get Matter Summary",
    description="""
    Get AI-generated executive summary for a matter.

    Returns summary including:
    - Attention items (contradictions, citation issues, timeline gaps)
    - Parties (petitioner, respondent) from MIG
    - Subject matter description (GPT-4 generated)
    - Current status (last order, proceedings)
    - Key issues (GPT-4 extracted)
    - Matter statistics (pages, entities, events, citations)

    Summary is cached in Redis with 1-hour TTL.
    Use `force_refresh=true` to bypass cache and regenerate.

    Requires viewer role or higher on the matter.
    """,
    responses={
        200: {
            "description": "Summary retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "matterId": "uuid",
                            "attentionItems": [
                                {
                                    "type": "contradiction",
                                    "count": 3,
                                    "label": "contradictions detected",
                                    "targetTab": "verification",
                                }
                            ],
                            "parties": [
                                {
                                    "entityId": "uuid",
                                    "entityName": "John Doe",
                                    "role": "petitioner",
                                    "sourceDocument": "Petition.pdf",
                                    "sourcePage": 1,
                                    "isVerified": False,
                                }
                            ],
                            "subjectMatter": {
                                "description": "Case description...",
                                "sources": [
                                    {"documentName": "Doc.pdf", "pageRange": "1-3"}
                                ],
                                "isVerified": False,
                            },
                            "currentStatus": {
                                "lastOrderDate": "2026-01-15T00:00:00Z",
                                "description": "Matter status...",
                                "sourceDocument": "Order.pdf",
                                "sourcePage": 1,
                                "isVerified": False,
                            },
                            "keyIssues": [
                                {
                                    "id": "issue-1",
                                    "number": 1,
                                    "title": "Whether...",
                                    "verificationStatus": "pending",
                                }
                            ],
                            "stats": {
                                "totalPages": 156,
                                "entitiesFound": 24,
                                "eventsExtracted": 18,
                                "citationsFound": 42,
                                "verificationPercent": 67.5,
                            },
                            "generatedAt": "2026-01-15T10:30:00Z",
                        }
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_AUTHENTICATED",
                            "message": "Authentication required",
                            "details": {},
                        }
                    }
                }
            },
        },
        404: {
            "description": "Matter not found or no access",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "MATTER_NOT_FOUND",
                            "message": "Matter not found or you don't have access",
                            "details": {},
                        }
                    }
                }
            },
        },
        500: {
            "description": "Summary generation failed",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "GENERATION_FAILED",
                            "message": "Failed to generate summary",
                            "details": {},
                        }
                    }
                }
            },
        },
    },
)
@limiter.limit(READONLY_RATE_LIMIT)
async def get_matter_summary(
    request: Request,  # Required for rate limiter
    access: MatterAccessContext = Depends(
        validate_matter_access(require_role=MatterRole.VIEWER)
    ),
    force_refresh: bool = Query(
        False,
        alias="forceRefresh",
        description="Bypass cache and regenerate summary",
    ),
    summary_service: SummaryService = Depends(get_summary_service),
) -> MatterSummaryResponse:
    """Get AI-generated executive summary for a matter.

    Story 14.1: AC #1 - GET /api/matters/{matter_id}/summary endpoint.

    Args:
        access: Validated matter access context (enforces Layer 4 security).
        force_refresh: If True, bypass cache and regenerate.
        summary_service: Summary service instance.

    Returns:
        MatterSummaryResponse with summary data.

    Raises:
        HTTPException: On authentication, authorization, or generation errors.
    """
    try:
        logger.info(
            "summary_request",
            matter_id=access.matter_id,
            user_id=access.user_id,
            force_refresh=force_refresh,
        )

        summary = await summary_service.get_summary(
            matter_id=access.matter_id,
            force_refresh=force_refresh,
        )

        return MatterSummaryResponse(data=summary)

    except SummaryServiceError as e:
        logger.error(
            "summary_request_failed",
            matter_id=access.matter_id,
            error=e.message,
            code=e.code,
        )
        raise _handle_service_error(e) from e
    except Exception as e:
        logger.error(
            "summary_request_unexpected_error",
            matter_id=access.matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 14.4: Summary Verification Endpoints (Task 5)
# =============================================================================


def _handle_verification_service_error(
    error: SummaryVerificationServiceError,
) -> HTTPException:
    """Convert verification service errors to HTTP exceptions."""
    return HTTPException(
        status_code=error.status_code,
        detail={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {},
            }
        },
    )


@router.post(
    "/{matter_id}/summary/verify",
    response_model=SummaryVerificationResponse,
    summary="Verify Summary Section",
    description="""
    Record a verification decision for a summary section.

    Supports sections:
    - parties: Individual party entities (use entityId as sectionId)
    - subject_matter: Subject matter section (use "main" as sectionId)
    - current_status: Current status section (use "main" as sectionId)
    - key_issue: Individual key issues (use issue id as sectionId)

    Decisions:
    - verified: Section content is accurate
    - flagged: Section needs attention or is incorrect

    Requires editor role or higher on the matter.
    """,
    responses={
        200: {
            "description": "Verification recorded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": "uuid",
                            "matterId": "uuid",
                            "sectionType": "subject_matter",
                            "sectionId": "main",
                            "decision": "verified",
                            "notes": "Reviewed and approved",
                            "verifiedBy": "user-uuid",
                            "verifiedAt": "2026-01-16T10:00:00Z",
                        }
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
        },
        403: {
            "description": "Insufficient permissions (requires editor role)",
        },
        404: {
            "description": "Matter not found or no access",
        },
    },
)
@limiter.limit(STANDARD_RATE_LIMIT)
async def verify_summary_section(
    http_request: Request,  # Required for rate limiter
    access: MatterAccessContext = Depends(
        validate_matter_access(require_role=MatterRole.EDITOR)
    ),
    request: SummaryVerificationCreate = Body(...),
    verification_service: SummaryVerificationService = Depends(
        get_summary_verification_service
    ),
    summary_service: SummaryService = Depends(get_summary_service),
) -> SummaryVerificationResponse:
    """Record verification decision for a summary section.

    Story 14.4: AC #1 - POST /api/matters/{matter_id}/summary/verify endpoint.

    Args:
        access: Validated matter access context (enforces Layer 4 security).
        request: Verification request with section details and decision.
        verification_service: Verification service instance.
        summary_service: Summary service instance (for cache invalidation).

    Returns:
        SummaryVerificationResponse with created/updated verification.

    Raises:
        HTTPException: On authentication, authorization, or operation errors.
    """
    try:
        logger.info(
            "verify_section_request",
            matter_id=access.matter_id,
            user_id=access.user_id,
            section_type=request.section_type.value,
            section_id=request.section_id,
            decision=request.decision.value,
        )

        verification = await verification_service.record_verification(
            matter_id=access.matter_id,
            section_type=request.section_type,
            section_id=request.section_id,
            decision=request.decision,
            notes=request.notes,
            user_id=access.user_id,
        )

        # Invalidate summary cache so next GET returns updated isVerified
        await summary_service.invalidate_cache(access.matter_id)

        return SummaryVerificationResponse(data=verification)

    except SummaryVerificationServiceError as e:
        logger.error(
            "verify_section_failed",
            matter_id=access.matter_id,
            error=e.message,
            code=e.code,
        )
        raise _handle_verification_service_error(e) from e
    except Exception as e:
        logger.error(
            "verify_section_unexpected_error",
            matter_id=access.matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        ) from e


@router.post(
    "/{matter_id}/summary/notes",
    response_model=SummaryNoteResponse,
    summary="Add Note to Summary Section",
    description="""
    Add a note to a summary section.

    Multiple notes can be added per section.
    Notes are visible to all users with access to the matter.

    Requires editor role or higher on the matter.
    """,
    responses={
        200: {
            "description": "Note added successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": "uuid",
                            "matterId": "uuid",
                            "sectionType": "parties",
                            "sectionId": "entity-uuid",
                            "text": "Need to verify identity",
                            "createdBy": "user-uuid",
                            "createdAt": "2026-01-16T10:00:00Z",
                        }
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
        },
        403: {
            "description": "Insufficient permissions (requires editor role)",
        },
        404: {
            "description": "Matter not found or no access",
        },
    },
)
@limiter.limit(STANDARD_RATE_LIMIT)
async def add_summary_note(
    http_request: Request,  # Required for rate limiter
    access: MatterAccessContext = Depends(
        validate_matter_access(require_role=MatterRole.EDITOR)
    ),
    request: SummaryNoteCreate = Body(...),
    verification_service: SummaryVerificationService = Depends(
        get_summary_verification_service
    ),
) -> SummaryNoteResponse:
    """Add a note to a summary section.

    Story 14.4: AC #2 - POST /api/matters/{matter_id}/summary/notes endpoint.

    Args:
        access: Validated matter access context (enforces Layer 4 security).
        request: Note request with section details and text.
        verification_service: Verification service instance.

    Returns:
        SummaryNoteResponse with created note.

    Raises:
        HTTPException: On authentication, authorization, or operation errors.
    """
    try:
        logger.info(
            "add_note_request",
            matter_id=access.matter_id,
            user_id=access.user_id,
            section_type=request.section_type.value,
            section_id=request.section_id,
        )

        note = await verification_service.add_note(
            matter_id=access.matter_id,
            section_type=request.section_type,
            section_id=request.section_id,
            text=request.text,
            user_id=access.user_id,
        )

        return SummaryNoteResponse(data=note)

    except SummaryVerificationServiceError as e:
        logger.error(
            "add_note_failed",
            matter_id=access.matter_id,
            error=e.message,
            code=e.code,
        )
        raise _handle_verification_service_error(e) from e
    except Exception as e:
        logger.error(
            "add_note_unexpected_error",
            matter_id=access.matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        ) from e


@router.get(
    "/{matter_id}/summary/verifications",
    response_model=SummaryVerificationsListResponse,
    summary="List Summary Verifications",
    description="""
    Get all verification decisions for a matter.

    Optionally filter by section type.

    Requires viewer role or higher on the matter.
    """,
    responses={
        200: {
            "description": "Verifications retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "uuid",
                                "matterId": "uuid",
                                "sectionType": "subject_matter",
                                "sectionId": "main",
                                "decision": "verified",
                                "notes": None,
                                "verifiedBy": "user-uuid",
                                "verifiedAt": "2026-01-16T10:00:00Z",
                            }
                        ],
                        "meta": {"total": 1},
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Matter not found or no access",
        },
    },
)
@limiter.limit(READONLY_RATE_LIMIT)
async def get_summary_verifications(
    request: Request,  # Required for rate limiter
    access: MatterAccessContext = Depends(
        validate_matter_access(require_role=MatterRole.VIEWER)
    ),
    section_type: SummarySectionTypeEnum | None = Query(
        None,
        alias="sectionType",
        description="Filter by section type",
    ),
    verification_service: SummaryVerificationService = Depends(
        get_summary_verification_service
    ),
) -> SummaryVerificationsListResponse:
    """Get all verification decisions for a matter.

    Story 14.4: AC #3 - GET /api/matters/{matter_id}/summary/verifications endpoint.

    Args:
        access: Validated matter access context (enforces Layer 4 security).
        section_type: Optional filter by section type.
        verification_service: Verification service instance.

    Returns:
        SummaryVerificationsListResponse with list of verifications.

    Raises:
        HTTPException: On authentication or authorization errors.
    """
    try:
        logger.info(
            "get_verifications_request",
            matter_id=access.matter_id,
            user_id=access.user_id,
            section_type=section_type.value if section_type else None,
        )

        verifications = await verification_service.get_verifications(
            matter_id=access.matter_id,
            section_type=section_type,
        )

        return SummaryVerificationsListResponse(
            data=verifications,
            meta={"total": len(verifications)},
        )

    except SummaryVerificationServiceError as e:
        logger.error(
            "get_verifications_failed",
            matter_id=access.matter_id,
            error=e.message,
            code=e.code,
        )
        raise _handle_verification_service_error(e) from e
    except Exception as e:
        logger.error(
            "get_verifications_unexpected_error",
            matter_id=access.matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Story 14.6: Summary Edit Endpoints (Task 1.5, Task 2.3)
# =============================================================================


def _handle_edit_service_error(error: SummaryEditServiceError) -> HTTPException:
    """Convert edit service errors to HTTP exceptions."""
    return HTTPException(
        status_code=error.status_code,
        detail={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {},
            }
        },
    )


@router.put(
    "/{matter_id}/summary/sections/{section_type}",
    response_model=SummaryEditResponse,
    summary="Save Summary Section Edit",
    description="""
    Save edited content for a summary section.

    This endpoint allows users to modify AI-generated summary content
    while preserving the original for comparison and audit.

    Supported section types:
    - subject_matter: Main case description (use sectionId="main")
    - current_status: Current proceedings (use sectionId="main")
    - parties: Individual party info (use sectionId=entityId)
    - key_issue: Individual issues (use sectionId=issueId)

    Uses upsert pattern - creates new edit or updates existing.

    Requires editor role or higher on the matter.
    """,
    responses={
        200: {
            "description": "Edit saved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": "uuid",
                            "matterId": "uuid",
                            "sectionType": "subject_matter",
                            "sectionId": "main",
                            "originalContent": "Original AI text...",
                            "editedContent": "User edited text...",
                            "editedBy": "user-uuid",
                            "editedAt": "2026-01-16T10:00:00Z",
                        }
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (requires editor role)"},
        404: {"description": "Matter not found or no access"},
        422: {"description": "Invalid section type"},
    },
)
@limiter.limit(STANDARD_RATE_LIMIT)
async def save_section_edit(
    http_request: Request,  # Required for rate limiter
    section_type: str,
    access: MatterAccessContext = Depends(
        validate_matter_access(require_role=MatterRole.EDITOR)
    ),
    request: SummaryEditCreate = Body(...),
    edit_service: SummaryEditService = Depends(get_summary_edit_service),
    summary_service: SummaryService = Depends(get_summary_service),
) -> SummaryEditResponse:
    """Save edited content for a summary section.

    Story 14.6: AC #7 - PUT /api/matters/{matter_id}/summary/sections/{section_type}

    Args:
        section_type: Section type from URL path.
        access: Validated matter access context (enforces Layer 4 security).
        request: Edit request with content and section details.
        edit_service: Edit service instance.
        summary_service: Summary service instance (for cache invalidation).

    Returns:
        SummaryEditResponse with saved edit data.

    Raises:
        HTTPException: On authentication, authorization, or operation errors.
    """
    try:
        # Validate section type
        try:
            section_type_enum = SummarySectionTypeEnum(section_type)
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "INVALID_SECTION_TYPE",
                        "message": f"Invalid section type: {section_type}. "
                        f"Valid types: {[t.value for t in SummarySectionTypeEnum]}",
                        "details": {},
                    }
                },
            ) from e

        logger.info(
            "save_section_edit_request",
            matter_id=access.matter_id,
            user_id=access.user_id,
            section_type=section_type,
            section_id=request.section_id,
        )

        edit = await edit_service.save_edit(
            matter_id=access.matter_id,
            section_type=section_type_enum,
            section_id=request.section_id,
            content=request.content,
            original_content=request.original_content,
            user_id=access.user_id,
        )

        # Invalidate summary cache so next GET returns edited content
        await summary_service.invalidate_cache(access.matter_id)

        return SummaryEditResponse(data=edit)

    except SummaryEditServiceError as e:
        logger.error(
            "save_section_edit_failed",
            matter_id=access.matter_id,
            error=e.message,
            code=e.code,
        )
        raise _handle_edit_service_error(e) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "save_section_edit_unexpected_error",
            matter_id=access.matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        ) from e


@router.post(
    "/{matter_id}/summary/regenerate",
    response_model=MatterSummaryResponse,
    summary="Regenerate Summary Section",
    description="""
    Regenerate a specific summary section using GPT-4.

    This endpoint:
    1. Deletes any existing user edit for the section (revert to AI)
    2. Invalidates cached summary
    3. Regenerates the section with fresh AI analysis
    4. Returns the updated summary

    Use this when the user wants to discard their edits and get fresh AI content.

    Requires editor role or higher on the matter.
    """,
    responses={
        200: {
            "description": "Section regenerated successfully",
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (requires editor role)"},
        404: {"description": "Matter not found or no access"},
    },
)
@limiter.limit(STANDARD_RATE_LIMIT)
async def regenerate_section(
    http_request: Request,  # Required for rate limiter
    access: MatterAccessContext = Depends(
        validate_matter_access(require_role=MatterRole.EDITOR)
    ),
    request: SummaryRegenerateRequest = Body(...),
    edit_service: SummaryEditService = Depends(get_summary_edit_service),
    summary_service: SummaryService = Depends(get_summary_service),
) -> MatterSummaryResponse:
    """Regenerate a specific summary section using GPT-4.

    Story 14.6: AC #8 - POST /api/matters/{matter_id}/summary/regenerate

    Args:
        access: Validated matter access context (enforces Layer 4 security).
        request: Regenerate request with section type.
        edit_service: Edit service instance.
        summary_service: Summary service instance.

    Returns:
        MatterSummaryResponse with regenerated summary.

    Raises:
        HTTPException: On authentication, authorization, or generation errors.
    """
    try:
        logger.info(
            "regenerate_section_request",
            matter_id=access.matter_id,
            user_id=access.user_id,
            section_type=request.section_type.value,
        )

        # Delete existing edit for this section (revert to AI-generated)
        # For subject_matter and current_status, use "main" as section_id
        section_id = "main"
        await edit_service.delete_edit(
            matter_id=access.matter_id,
            section_type=request.section_type,
            section_id=section_id,
        )

        # Invalidate cache and force regeneration
        await summary_service.invalidate_cache(access.matter_id)

        # Get fresh summary (will regenerate)
        summary = await summary_service.get_summary(
            matter_id=access.matter_id,
            force_refresh=True,
        )

        return MatterSummaryResponse(data=summary)

    except SummaryEditServiceError as e:
        logger.error(
            "regenerate_section_failed",
            matter_id=access.matter_id,
            error=e.message,
            code=e.code,
        )
        raise _handle_edit_service_error(e) from e
    except SummaryServiceError as e:
        logger.error(
            "regenerate_section_generation_failed",
            matter_id=access.matter_id,
            error=e.message,
            code=e.code,
        )
        raise _handle_service_error(e) from e
    except Exception as e:
        logger.error(
            "regenerate_section_unexpected_error",
            matter_id=access.matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        ) from e
