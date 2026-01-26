"""Bounding box API routes for text positioning and highlighting.

Implements endpoints for retrieving bounding boxes for documents,
pages, and chunks. All endpoints enforce matter isolation via RLS
and Layer 4 validation.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from supabase import Client

from app.api.deps import (
    get_matter_service,
)
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.services.bounding_box_service import (
    BoundingBoxService,
    BoundingBoxServiceError,
    get_bounding_box_service,
)
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
    get_document_service,
)
from app.services.matter_service import MatterService
from app.services.supabase.client import get_service_client

router = APIRouter(prefix="/documents", tags=["bounding-boxes"])
chunks_router = APIRouter(prefix="/chunks", tags=["bounding-boxes"])
logger = structlog.get_logger(__name__)


def get_supabase_client() -> Client | None:
    """Dependency for Supabase service client."""
    return get_service_client()


# =============================================================================
# Response Models
# =============================================================================


class BoundingBoxData(BaseModel):
    """Bounding box data model for API responses."""

    id: str = Field(..., description="Bounding box UUID")
    document_id: str = Field(..., description="Document UUID")
    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    x: float = Field(..., ge=0, le=100, description="X coordinate (percentage)")
    y: float = Field(..., ge=0, le=100, description="Y coordinate (percentage)")
    width: float = Field(..., ge=0, le=100, description="Width (percentage)")
    height: float = Field(..., ge=0, le=100, description="Height (percentage)")
    text: str = Field(..., description="OCR-extracted text content")
    confidence: float | None = Field(None, description="OCR confidence score (0-1)")
    reading_order_index: int | None = Field(
        None, description="Reading order within page (0-indexed)"
    )


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class BoundingBoxListResponse(BaseModel):
    """Response model for bounding box list endpoints."""

    data: list[BoundingBoxData]
    meta: PaginationMeta | None = None


class BoundingBoxPageResponse(BaseModel):
    """Response model for page-specific bounding box endpoint."""

    data: list[BoundingBoxData]


class BoundingBoxIdsRequest(BaseModel):
    """Request model for fetching bboxes by IDs."""

    bbox_ids: list[str] = Field(..., min_length=1, max_length=100, description="List of bbox UUIDs")
    matter_id: str = Field(..., description="Matter UUID for access control")


# =============================================================================
# Helper Functions
# =============================================================================


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


def _handle_bbox_service_error(error: BoundingBoxServiceError) -> HTTPException:
    """Convert bounding box service errors to HTTP exceptions."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {},
            }
        },
    )


# =============================================================================
# Document Bounding Box Endpoints
# =============================================================================


@router.get(
    "/{document_id}/bounding-boxes",
    response_model=BoundingBoxListResponse,
    response_model_by_alias=True,
)
async def get_document_bounding_boxes(
    document_id: str = Path(..., description="Document UUID"),
    page: int | None = Query(None, ge=1, description="Page number for pagination"),
    per_page: int = Query(100, ge=1, le=500, description="Items per page"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
    bbox_service: BoundingBoxService = Depends(get_bounding_box_service),
) -> BoundingBoxListResponse:
    """Get all bounding boxes for a document, ordered by reading order.

    Returns paginated list of bounding boxes sorted by page number
    and then by reading order index within each page.

    User must have access to the document's matter.
    """
    # Verify access to document
    _verify_document_access(document_id, current_user.id, document_service, matter_service)

    try:
        boxes, total = bbox_service.get_bounding_boxes_for_document(
            document_id=document_id,
            page=page,
            per_page=per_page,
        )

        # Calculate total pages
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return BoundingBoxListResponse(
            data=[BoundingBoxData(**box) for box in boxes],
            meta=PaginationMeta(
                total=total,
                page=page or 1,
                per_page=per_page,
                total_pages=total_pages,
            ),
        )

    except BoundingBoxServiceError as e:
        raise _handle_bbox_service_error(e) from e
    except Exception as e:
        logger.error(
            "get_document_bounding_boxes_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "BOUNDING_BOXES_RETRIEVAL_FAILED",
                    "message": f"Failed to retrieve bounding boxes: {e!s}",
                    "details": {},
                }
            },
        ) from e


@router.get(
    "/{document_id}/pages/{page_number}/bounding-boxes",
    response_model=BoundingBoxPageResponse,
    response_model_by_alias=True,
)
async def get_page_bounding_boxes(
    document_id: str = Path(..., description="Document UUID"),
    page_number: int = Path(..., ge=1, description="Page number (1-indexed)"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
    bbox_service: BoundingBoxService = Depends(get_bounding_box_service),
) -> BoundingBoxPageResponse:
    """Get bounding boxes for a specific page, ordered by reading order.

    Returns all bounding boxes for the specified page sorted by
    reading order index for proper text flow.

    User must have access to the document's matter.
    """
    # Verify access to document
    _verify_document_access(document_id, current_user.id, document_service, matter_service)

    try:
        boxes = bbox_service.get_bounding_boxes_for_page(
            document_id=document_id,
            page_number=page_number,
        )

        return BoundingBoxPageResponse(
            data=[BoundingBoxData(**box) for box in boxes],
        )

    except BoundingBoxServiceError as e:
        raise _handle_bbox_service_error(e) from e
    except Exception as e:
        logger.error(
            "get_page_bounding_boxes_failed",
            document_id=document_id,
            page_number=page_number,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "BOUNDING_BOXES_RETRIEVAL_FAILED",
                    "message": f"Failed to retrieve bounding boxes: {e!s}",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Chunk Bounding Box Endpoints
# =============================================================================


@chunks_router.get(
    "/{chunk_id}/bounding-boxes",
    response_model=BoundingBoxPageResponse,
)
async def get_chunk_bounding_boxes(
    chunk_id: str = Path(..., description="Chunk UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
    bbox_service: BoundingBoxService = Depends(get_bounding_box_service),
    db_client: Client | None = Depends(get_supabase_client),
) -> BoundingBoxPageResponse:
    """Get bounding boxes linked to a chunk via its bbox_ids array.

    Returns bounding boxes associated with the chunk for text
    highlighting in the UI. Boxes are ordered by reading order.

    User must have access to the chunk's matter.
    """
    # Note: We need to get the chunk first to access its bbox_ids and matter_id
    # This requires a ChunkService which will be created in Story 2b-5
    # For now, we'll use the service client to get the chunk directly

    if db_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "DATABASE_NOT_CONFIGURED",
                    "message": "Database client not configured",
                    "details": {},
                }
            },
        )

    try:
        # Get chunk to access matter_id and bbox_ids
        chunk_result = (
            db_client.table("chunks")
            .select("matter_id, bbox_ids")
            .eq("id", chunk_id)
            .execute()
        )

        if not chunk_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "CHUNK_NOT_FOUND",
                        "message": "Chunk not found or you don't have access",
                        "details": {},
                    }
                },
            )

        chunk = chunk_result.data[0]
        matter_id = chunk["matter_id"]
        bbox_ids = chunk.get("bbox_ids") or []

        # Verify user has access to the matter
        role = matter_service.get_user_role(matter_id, current_user.id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "CHUNK_NOT_FOUND",
                        "message": "Chunk not found or you don't have access",
                        "details": {},
                    }
                },
            )

        # Get bounding boxes by IDs
        if not bbox_ids:
            return BoundingBoxPageResponse(data=[])

        boxes = bbox_service.get_bounding_boxes_by_ids(bbox_ids)

        return BoundingBoxPageResponse(
            data=[BoundingBoxData(**box) for box in boxes],
        )

    except HTTPException:
        raise
    except BoundingBoxServiceError as e:
        raise _handle_bbox_service_error(e) from e
    except Exception as e:
        logger.error(
            "get_chunk_bounding_boxes_failed",
            chunk_id=chunk_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "BOUNDING_BOXES_RETRIEVAL_FAILED",
                    "message": f"Failed to retrieve bounding boxes: {e!s}",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Bounding Box By IDs Router
# =============================================================================

bbox_ids_router = APIRouter(prefix="/bounding-boxes", tags=["bounding-boxes"])


@bbox_ids_router.post(
    "/by-ids",
    response_model=BoundingBoxPageResponse,
)
async def get_bboxes_by_ids(
    request: BoundingBoxIdsRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
    bbox_service: BoundingBoxService = Depends(get_bounding_box_service),
) -> BoundingBoxPageResponse:
    """Get bounding boxes by their IDs directly.

    This endpoint allows fetching bboxes when you already have the IDs
    (e.g., from Q&A source references with bbox_ids).

    User must have access to the specified matter.
    """
    # Verify user has access to the matter
    role = matter_service.get_user_role(request.matter_id, current_user.id)
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

    try:
        # Get bounding boxes by IDs
        if not request.bbox_ids:
            return BoundingBoxPageResponse(data=[])

        boxes = bbox_service.get_bounding_boxes_by_ids(request.bbox_ids)

        return BoundingBoxPageResponse(
            data=[BoundingBoxData(**box) for box in boxes],
        )

    except BoundingBoxServiceError as e:
        raise _handle_bbox_service_error(e) from e
    except Exception as e:
        logger.error(
            "get_bboxes_by_ids_failed",
            bbox_ids_count=len(request.bbox_ids),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "BOUNDING_BOXES_RETRIEVAL_FAILED",
                    "message": f"Failed to retrieve bounding boxes: {e!s}",
                    "details": {},
                }
            },
        ) from e
