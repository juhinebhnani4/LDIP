"""API routes for RAG pipeline inspection/debugging.

Story: RAG Production Gaps - Feature 3: Inspector Mode
Provides detailed timing and scoring information for search debugging.
Only available when inspector_enabled=True in settings.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_matter_service
from app.core.config import get_settings
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.inspector import (
    InspectorSearchRequest,
    InspectorSearchResponse,
)
from app.services.inspector import get_inspector_service
from app.services.matter_service import MatterService

router = APIRouter(prefix="/inspector", tags=["inspector"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def _verify_inspector_enabled() -> None:
    """Verify inspector mode is enabled in settings.

    Raises:
        HTTPException: If inspector mode is disabled.
    """
    settings = get_settings()
    if not settings.inspector_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "INSPECTOR_DISABLED",
                    "message": "Inspector mode is disabled. Set INSPECTOR_ENABLED=true to enable.",
                    "details": {},
                }
            },
        )


def _verify_matter_access(
    matter_id: str,
    user_id: str,
    matter_service: MatterService,
) -> None:
    """Verify user has access to matter.

    Args:
        matter_id: Matter UUID.
        user_id: User UUID.
        matter_service: Matter service instance.

    Raises:
        HTTPException: If access denied.
    """
    role = matter_service.get_user_role(matter_id, user_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "MATTER_NOT_FOUND",
                    "message": "Matter not found or you don't have access",
                    "details": {},
                }
            },
        )


# =============================================================================
# Inspector Endpoints
# =============================================================================


@router.post("/matters/{matter_id}/search", response_model=InspectorSearchResponse)
async def inspector_search(
    matter_id: str = Path(..., description="Matter UUID"),
    body: InspectorSearchRequest = ...,
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> InspectorSearchResponse:
    """Execute search with full debug information.

    Returns detailed timing breakdown, BM25/semantic ranks, RRF scores,
    and reranker scores for each result.

    Only available when INSPECTOR_ENABLED=true in settings.

    Args:
        matter_id: Matter UUID.
        body: Search request with debug options.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Search results with full debug information.
    """
    _verify_inspector_enabled()
    _verify_matter_access(matter_id, current_user.id, matter_service)

    logger.info(
        "inspector_search_request",
        matter_id=matter_id,
        user_id=current_user.id,
        query_length=len(body.query),
        rerank=body.rerank,
    )

    try:
        service = get_inspector_service()

        data, meta, debug = await service.search_with_debug(
            query=body.query,
            matter_id=matter_id,
            limit=body.limit,
            bm25_weight=body.bm25_weight,
            semantic_weight=body.semantic_weight,
            rerank=body.rerank,
            rerank_top_n=body.rerank_top_n,
            expand_aliases=body.expand_aliases,
        )

        logger.info(
            "inspector_search_complete",
            matter_id=matter_id,
            total_ms=debug.timing.total_ms,
            result_count=len(data),
        )

        return InspectorSearchResponse(
            data=data,
            meta=meta,
            debug=debug,
        )

    except Exception as e:
        logger.error(
            "inspector_search_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INSPECTOR_SEARCH_FAILED",
                    "message": str(e),
                    "details": {},
                }
            },
        ) from e


@router.get("/status")
async def inspector_status(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Check if inspector mode is enabled.

    Returns:
        Status indicating if inspector is enabled.
    """
    settings = get_settings()

    return {
        "data": {
            "inspector_enabled": settings.inspector_enabled,
            "auto_evaluation_enabled": settings.auto_evaluation_enabled,
            "table_extraction_enabled": settings.table_extraction_enabled,
        }
    }


@router.get("/matters/{matter_id}/config")
async def get_inspector_config(
    matter_id: str = Path(..., description="Matter UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> dict:
    """Get current search/RAG configuration for debugging.

    Returns the current settings that affect search behavior.

    Args:
        matter_id: Matter UUID.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Current RAG configuration.
    """
    _verify_inspector_enabled()
    _verify_matter_access(matter_id, current_user.id, matter_service)

    settings = get_settings()

    return {
        "data": {
            "embedding": {
                "model": settings.openai_embedding_model,
                "dimensions": 1536,
            },
            "search": {
                "default_hybrid_limit": 50,
                "default_rerank_top_n": 3,
                "rrf_k_constant": 60,
            },
            "reranking": {
                "model": "rerank-v3.5",
                "provider": "cohere",
            },
            "chunking": {
                "parent_size_tokens": 1500,
                "child_size_tokens": 400,
                "overlap_tokens": 50,
            },
        }
    }
