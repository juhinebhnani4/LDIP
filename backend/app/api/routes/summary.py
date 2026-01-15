"""Summary API routes for Matter Executive Summary.

Story 14.1: Summary API Endpoint (Task 3)

Provides GET /api/matters/{matter_id}/summary endpoint for retrieving
AI-generated executive summaries.

CRITICAL: Uses matter access validation for Layer 4 security.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    MatterAccessContext,
    MatterRole,
    validate_matter_access,
)
from app.models.summary import MatterSummaryResponse
from app.services.summary_service import (
    SummaryService,
    SummaryServiceError,
    get_summary_service,
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
async def get_matter_summary(
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
        raise _handle_service_error(e)
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
