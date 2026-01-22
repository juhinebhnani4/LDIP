"""API routes for table extraction and retrieval.

Story: RAG Production Gaps - Feature 1: Table Extraction
Provides endpoints for retrieving tables extracted from documents.
All endpoints enforce matter isolation via Layer 4 validation.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_matter_service
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.table import (
    TableListResponse,
    TableResponse,
    TableStats,
)
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
    get_document_service,
)
from app.services.matter_service import MatterService
from app.services.supabase.client import get_supabase_client as get_supabase

router = APIRouter(prefix="/matters/{matter_id}/tables", tags=["tables"])
document_tables_router = APIRouter(prefix="/documents/{document_id}/tables", tags=["tables"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


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


def _verify_document_access(
    document_id: str,
    user_id: str,
    document_service: DocumentService,
    matter_service: MatterService,
) -> str:
    """Verify user has access to document's matter.

    Args:
        document_id: Document UUID.
        user_id: User UUID.
        document_service: Document service instance.
        matter_service: Matter service instance.

    Returns:
        Matter ID of the document.

    Raises:
        HTTPException: If document not found or access denied.
    """
    try:
        doc = document_service.get_document(document_id)
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "Document not found or you don't have access",
                    "details": {},
                }
            },
        ) from e

    # Verify user has access to the matter
    role = matter_service.get_user_role(doc.matter_id, user_id)
    if role is None:
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

    return doc.matter_id


# =============================================================================
# Matter-Scoped Endpoints
# =============================================================================


@router.get("", response_model=TableListResponse)
async def get_matter_tables(
    matter_id: str = Path(..., description="Matter UUID"),
    document_id: str | None = Query(None, description="Filter by document"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> TableListResponse:
    """Get all tables for a matter.

    Optionally filter by document or confidence threshold.
    Results are paginated and ordered by creation date (newest first).

    Args:
        matter_id: Matter UUID.
        document_id: Optional document UUID to filter.
        page: Page number (1-indexed).
        per_page: Items per page (max 100).
        min_confidence: Minimum confidence threshold.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Paginated list of tables with metadata.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service)

    logger.info(
        "get_matter_tables_request",
        matter_id=matter_id,
        document_id=document_id,
        page=page,
        per_page=per_page,
        user_id=current_user.id,
    )

    supabase = get_supabase()

    # Build query
    query = (
        supabase.table("document_tables")
        .select("*", count="exact")
        .eq("matter_id", matter_id)
        .gte("confidence", min_confidence)
    )

    if document_id:
        query = query.eq("document_id", document_id)

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order("created_at", desc=True).range(offset, offset + per_page - 1)

    result = query.execute()

    total = result.count or 0
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    logger.info(
        "get_matter_tables_complete",
        matter_id=matter_id,
        total=total,
        page=page,
    )

    return TableListResponse(
        data=result.data,
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    )


@router.get("/stats", response_model=TableStats)
async def get_matter_table_stats(
    matter_id: str = Path(..., description="Matter UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> TableStats:
    """Get table extraction statistics for a matter.

    Args:
        matter_id: Matter UUID.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Table statistics including counts and averages.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service)

    supabase = get_supabase()

    # Get all tables for stats calculation
    result = (
        supabase.table("document_tables")
        .select("confidence, row_count, col_count, document_id")
        .eq("matter_id", matter_id)
        .execute()
    )

    tables = result.data
    total = len(tables)

    if total == 0:
        return TableStats(
            total_tables=0,
            documents_with_tables=0,
            avg_confidence=0.0,
            avg_rows=0.0,
            avg_cols=0.0,
            low_confidence_count=0,
        )

    # Calculate stats
    confidences = [t["confidence"] for t in tables]
    rows = [t["row_count"] for t in tables]
    cols = [t["col_count"] for t in tables]
    document_ids = {t["document_id"] for t in tables}
    low_conf_count = sum(1 for c in confidences if c < 0.7)

    return TableStats(
        total_tables=total,
        documents_with_tables=len(document_ids),
        avg_confidence=sum(confidences) / total,
        avg_rows=sum(rows) / total,
        avg_cols=sum(cols) / total,
        low_confidence_count=low_conf_count,
    )


@router.get("/{table_id}", response_model=TableResponse)
async def get_table(
    matter_id: str = Path(..., description="Matter UUID"),
    table_id: str = Path(..., description="Table UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
) -> TableResponse:
    """Get a specific table by ID.

    Args:
        matter_id: Matter UUID.
        table_id: Table UUID.
        current_user: Authenticated user.
        matter_service: Matter service instance.

    Returns:
        Table data.
    """
    _verify_matter_access(matter_id, current_user.id, matter_service)

    supabase = get_supabase()

    result = (
        supabase.table("document_tables")
        .select("*")
        .eq("id", table_id)
        .eq("matter_id", matter_id)
        .maybe_single()
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "TABLE_NOT_FOUND",
                    "message": "Table not found",
                    "details": {},
                }
            },
        )

    return TableResponse(data=result.data)


# =============================================================================
# Document-Scoped Endpoints
# =============================================================================


@document_tables_router.get("", response_model=TableListResponse)
async def get_document_tables(
    document_id: str = Path(..., description="Document UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
) -> TableListResponse:
    """Get all tables from a specific document.

    Args:
        document_id: Document UUID.
        current_user: Authenticated user.
        document_service: Document service instance.
        matter_service: Matter service instance.

    Returns:
        List of tables from the document.
    """
    matter_id = _verify_document_access(
        document_id, current_user.id, document_service, matter_service
    )

    logger.info(
        "get_document_tables_request",
        document_id=document_id,
        user_id=current_user.id,
    )

    supabase = get_supabase()

    result = (
        supabase.table("document_tables")
        .select("*", count="exact")
        .eq("document_id", document_id)
        .order("table_index")
        .execute()
    )

    total = result.count or 0

    return TableListResponse(
        data=result.data,
        meta={
            "total": total,
            "page": 1,
            "per_page": total,
            "total_pages": 1,
        },
    )
