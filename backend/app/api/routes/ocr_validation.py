"""OCR validation API routes.

Endpoints for document validation status, validation history,
and human review queue management.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
)
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.ocr_validation import (
    DocumentValidationSummary,
    HumanReviewItem,
    HumanReviewStatus,
    ValidationLogEntry,
    ValidationStatus,
)
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
    get_document_service,
)
from app.services.ocr.human_review_service import (
    HumanReviewService,
    HumanReviewServiceError,
    get_human_review_service,
)
from app.services.supabase.client import get_service_client

router = APIRouter(prefix="/documents", tags=["ocr-validation"])
matters_router = APIRouter(prefix="/matters", tags=["ocr-validation"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Response Models
# =============================================================================


class ValidationStatusResponse(BaseModel):
    """Response for validation status endpoint."""

    data: DocumentValidationSummary


class ValidationLogResponse(BaseModel):
    """Response for validation log endpoint."""

    data: list[ValidationLogEntry]
    meta: dict[str, int | str]


class HumanReviewListResponse(BaseModel):
    """Response for human review list endpoint."""

    data: list[HumanReviewItem]
    meta: dict[str, int | str]


class HumanReviewCorrectionRequest(BaseModel):
    """Request body for submitting a human correction."""

    corrected_text: str = Field(..., min_length=1, description="Corrected text")


class HumanReviewCorrectionResponse(BaseModel):
    """Response for human review correction submission."""

    data: dict[str, str | bool]


class HumanReviewSkipRequest(BaseModel):
    """Request body for skipping a human review."""

    pass  # No fields required


class HumanReviewStatsResponse(BaseModel):
    """Response for human review statistics."""

    data: dict[str, int]


# =============================================================================
# Document Validation Endpoints
# =============================================================================


@router.get(
    "/{document_id}/validation-status",
    response_model=ValidationStatusResponse,
)
async def get_validation_status(
    document_id: str = Path(..., description="Document UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> ValidationStatusResponse:
    """Get validation status and summary for a document.

    Returns validation status, correction counts by type,
    and human review queue status.
    """
    client = get_service_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database service unavailable",
                    "details": {},
                }
            },
        )

    try:
        # Get document to verify access (RLS will filter)
        doc = document_service.get_document(document_id)

        # Get validation status from document
        doc_result = client.table("documents").select(
            "validation_status"
        ).eq("id", document_id).single().execute()

        validation_status_str = doc_result.data.get("validation_status", "pending") if doc_result.data else "pending"
        validation_status = ValidationStatus(validation_status_str)

        # Count corrections from validation log
        log_result = client.table("ocr_validation_log").select(
            "validation_type"
        ).eq("document_id", document_id).execute()

        pattern_count = 0
        gemini_count = 0
        human_count = 0

        if log_result.data:
            for entry in log_result.data:
                match entry.get("validation_type"):
                    case "pattern":
                        pattern_count += 1
                    case "gemini":
                        gemini_count += 1
                    case "human":
                        human_count += 1

        # Count human review items
        human_result = client.table("ocr_human_review").select(
            "status"
        ).eq("document_id", document_id).execute()

        human_pending = 0
        human_completed = 0

        if human_result.data:
            for entry in human_result.data:
                if entry.get("status") == "pending":
                    human_pending += 1
                elif entry.get("status") == "completed":
                    human_completed += 1

        summary = DocumentValidationSummary(
            document_id=document_id,
            validation_status=validation_status,
            total_words_validated=pattern_count + gemini_count + human_count,
            pattern_corrections=pattern_count,
            gemini_corrections=gemini_count,
            human_review_pending=human_pending,
            human_review_completed=human_completed,
        )

        return ValidationStatusResponse(data=summary)

    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "Document not found or you don't have access",
                    "details": {},
                }
            },
        )
    except Exception as e:
        logger.error(
            "validation_status_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "STATUS_FAILED",
                    "message": f"Failed to get validation status: {e!s}",
                    "details": {},
                }
            },
        )


@router.get(
    "/{document_id}/validation-log",
    response_model=ValidationLogResponse,
)
async def get_validation_log(
    document_id: str = Path(..., description="Document UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> ValidationLogResponse:
    """Get validation history for a document.

    Returns chronological list of all corrections made to the document,
    including the original text, corrected text, and correction type.
    """
    client = get_service_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database service unavailable",
                    "details": {},
                }
            },
        )

    try:
        # Verify access to document
        document_service.get_document(document_id)

        # Get total count
        count_result = client.table("ocr_validation_log").select(
            "id", count="exact"
        ).eq("document_id", document_id).execute()

        total = count_result.count or 0

        # Get paginated log entries
        offset = (page - 1) * per_page
        result = client.table("ocr_validation_log").select(
            "*"
        ).eq(
            "document_id", document_id
        ).order(
            "created_at", desc=True
        ).range(
            offset, offset + per_page - 1
        ).execute()

        entries = []
        if result.data:
            for row in result.data:
                entries.append(
                    ValidationLogEntry(
                        id=row["id"],
                        document_id=row["document_id"],
                        bbox_id=row.get("bbox_id"),
                        original_text=row["original_text"],
                        corrected_text=row["corrected_text"],
                        old_confidence=row.get("old_confidence"),
                        new_confidence=row.get("new_confidence"),
                        validation_type=row["validation_type"],
                        reasoning=row.get("reasoning"),
                        created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                    )
                )

        return ValidationLogResponse(
            data=entries,
            meta={
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
            },
        )

    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "Document not found or you don't have access",
                    "details": {},
                }
            },
        )
    except Exception as e:
        logger.error(
            "validation_log_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "LOG_FAILED",
                    "message": f"Failed to get validation log: {e!s}",
                    "details": {},
                }
            },
        )


# =============================================================================
# Human Review Endpoints
# =============================================================================


@matters_router.get(
    "/{matter_id}/human-review",
    response_model=HumanReviewListResponse,
)
async def get_pending_human_reviews(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    review_status: HumanReviewStatus = Query(
        HumanReviewStatus.PENDING,
        alias="status",
        description="Filter by review status",
    ),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    human_review_service: HumanReviewService = Depends(get_human_review_service),
) -> HumanReviewListResponse:
    """Get human review queue for a matter.

    Returns items awaiting human review due to very low OCR confidence.
    Editors and owners can view and process the review queue.
    """
    try:
        items, total = human_review_service.get_pending_reviews(
            matter_id=membership.matter_id,
            page=page,
            per_page=per_page,
        )

        return HumanReviewListResponse(
            data=items,
            meta={
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
                "status": review_status.value,
            },
        )

    except HumanReviewServiceError as e:
        logger.error(
            "human_review_list_failed",
            matter_id=membership.matter_id,
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


@matters_router.post(
    "/{matter_id}/human-review/{review_id}",
    response_model=HumanReviewCorrectionResponse,
)
async def submit_human_correction(
    review_id: str = Path(..., description="Review item UUID"),
    correction: HumanReviewCorrectionRequest = ...,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    human_review_service: HumanReviewService = Depends(get_human_review_service),
) -> HumanReviewCorrectionResponse:
    """Submit a human correction for a review item.

    Updates the OCR text with the corrected value and logs the correction.
    Only editors and owners can submit corrections.
    """
    try:
        result = human_review_service.submit_correction(
            review_id=review_id,
            corrected_text=correction.corrected_text,
            user_id=membership.user_id,
        )

        return HumanReviewCorrectionResponse(
            data={
                "review_id": review_id,
                "original": result.original,
                "corrected": result.corrected,
                "was_changed": result.was_corrected,
                "status": "completed",
            }
        )

    except HumanReviewServiceError as e:
        if e.code == "ITEM_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "details": {},
                    }
                },
            )
        logger.error(
            "human_review_correction_failed",
            review_id=review_id,
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


@matters_router.post(
    "/{matter_id}/human-review/{review_id}/skip",
    response_model=HumanReviewCorrectionResponse,
)
async def skip_human_review(
    review_id: str = Path(..., description="Review item UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    human_review_service: HumanReviewService = Depends(get_human_review_service),
) -> HumanReviewCorrectionResponse:
    """Skip a review item (accept original text as correct).

    Marks the review item as skipped without making changes.
    Only editors and owners can skip reviews.
    """
    try:
        human_review_service.skip_review(
            review_id=review_id,
            user_id=membership.user_id,
        )

        return HumanReviewCorrectionResponse(
            data={
                "review_id": review_id,
                "was_changed": False,
                "status": "skipped",
            }
        )

    except HumanReviewServiceError as e:
        if e.code == "ITEM_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "details": {},
                    }
                },
            )
        logger.error(
            "human_review_skip_failed",
            review_id=review_id,
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


@matters_router.get(
    "/{matter_id}/human-review/stats",
    response_model=HumanReviewStatsResponse,
)
async def get_human_review_stats(
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    human_review_service: HumanReviewService = Depends(get_human_review_service),
) -> HumanReviewStatsResponse:
    """Get human review statistics for a matter.

    Returns counts of pending, completed, and skipped reviews.
    """
    try:
        stats = human_review_service.get_review_stats(
            matter_id=membership.matter_id,
        )

        return HumanReviewStatsResponse(data=stats)

    except HumanReviewServiceError as e:
        logger.error(
            "human_review_stats_failed",
            matter_id=membership.matter_id,
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
