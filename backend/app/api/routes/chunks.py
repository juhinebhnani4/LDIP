"""Chunk API routes for RAG retrieval and context.

Implements endpoints for retrieving chunks from documents,
including parent-child relationships and context expansion.
All endpoints enforce matter isolation via Layer 4 validation.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_matter_service
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.chunk import (
    Chunk,
    ChunkContextResponse,
    ChunkListResponse,
    ChunkResponse,
    ChunkStatsMeta,
    ChunkType,
    ChunkWithContent,
)
from app.services.chunk_service import (
    ChunkNotFoundError,
    ChunkService,
    ChunkServiceError,
    get_chunk_service,
)
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
    get_document_service,
)
from app.services.matter_service import MatterService

router = APIRouter(prefix="/documents", tags=["chunks"])
chunks_router = APIRouter(prefix="/chunks", tags=["chunks"])
logger = structlog.get_logger(__name__)


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


def _verify_chunk_access(
    chunk_id: str,
    user_id: str,
    chunk_service: ChunkService,
    matter_service: MatterService,
) -> Chunk:
    """Verify user has access to chunk's matter.

    Args:
        chunk_id: Chunk UUID.
        user_id: User UUID.
        chunk_service: Chunk service instance.
        matter_service: Matter service instance.

    Returns:
        Chunk record.

    Raises:
        HTTPException: If chunk not found or access denied.
    """
    try:
        chunk = chunk_service.get_chunk(chunk_id)
    except ChunkNotFoundError:
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

    # Verify user has access to the matter
    role = matter_service.get_user_role(chunk.matter_id, user_id)
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

    return chunk


def _handle_chunk_service_error(error: ChunkServiceError) -> HTTPException:
    """Convert chunk service errors to HTTP exceptions."""
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


# =============================================================================
# Document Chunk Endpoints
# =============================================================================


@router.get(
    "/{document_id}/chunks",
    response_model=ChunkListResponse,
)
async def get_document_chunks(
    document_id: str = Path(..., description="Document UUID"),
    chunk_type: ChunkType | None = Query(None, description="Filter by chunk type"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
    chunk_service: ChunkService = Depends(get_chunk_service),
) -> ChunkListResponse:
    """Get all chunks for a document.

    Returns chunks for the document, optionally filtered by type.
    Parent chunks are returned before child chunks, ordered by index.

    User must have access to the document's matter.
    """
    # Verify access to document
    _verify_document_access(document_id, current_user.id, document_service, matter_service)

    try:
        chunks, parent_count, child_count = chunk_service.get_chunks_for_document(
            document_id=document_id,
            chunk_type=chunk_type,
        )

        return ChunkListResponse(
            data=chunks,
            meta=ChunkStatsMeta(
                total=len(chunks),
                parent_count=parent_count,
                child_count=child_count,
            ),
        )

    except ChunkServiceError as e:
        raise _handle_chunk_service_error(e)
    except Exception as e:
        logger.error(
            "get_document_chunks_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CHUNKS_RETRIEVAL_FAILED",
                    "message": f"Failed to retrieve chunks: {e!s}",
                    "details": {},
                }
            },
        )


# =============================================================================
# Individual Chunk Endpoints
# =============================================================================


@chunks_router.get(
    "/{chunk_id}",
    response_model=ChunkResponse,
)
async def get_chunk(
    chunk_id: str = Path(..., description="Chunk UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
    chunk_service: ChunkService = Depends(get_chunk_service),
) -> ChunkResponse:
    """Get a single chunk by ID.

    Returns the full chunk record including content.

    User must have access to the chunk's matter.
    """
    chunk = _verify_chunk_access(chunk_id, current_user.id, chunk_service, matter_service)

    return ChunkResponse(data=chunk)


@chunks_router.get(
    "/{chunk_id}/context",
    response_model=ChunkContextResponse,
)
async def get_chunk_context(
    chunk_id: str = Path(..., description="Chunk UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
    chunk_service: ChunkService = Depends(get_chunk_service),
) -> ChunkContextResponse:
    """Get a chunk with surrounding context.

    For child chunks, returns the parent chunk and sibling children.
    For parent chunks, returns all child chunks.

    Useful for expanding context when displaying search results.

    User must have access to the chunk's matter.
    """
    # Verify access
    _verify_chunk_access(chunk_id, current_user.id, chunk_service, matter_service)

    try:
        context = chunk_service.get_chunk_with_context(chunk_id)

        return ChunkContextResponse(data=context)

    except ChunkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CHUNK_NOT_FOUND",
                    "message": "Chunk not found",
                    "details": {},
                }
            },
        )
    except ChunkServiceError as e:
        raise _handle_chunk_service_error(e)
    except Exception as e:
        logger.error(
            "get_chunk_context_failed",
            chunk_id=chunk_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CONTEXT_RETRIEVAL_FAILED",
                    "message": f"Failed to retrieve chunk context: {e!s}",
                    "details": {},
                }
            },
        )


@chunks_router.get(
    "/{chunk_id}/parent",
    response_model=ChunkResponse,
)
async def get_chunk_parent(
    chunk_id: str = Path(..., description="Chunk UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
    chunk_service: ChunkService = Depends(get_chunk_service),
) -> ChunkResponse:
    """Get the parent chunk of a child chunk.

    Returns 404 if the chunk has no parent (is itself a parent).

    User must have access to the chunk's matter.
    """
    # Verify access to the child chunk first
    _verify_chunk_access(chunk_id, current_user.id, chunk_service, matter_service)

    try:
        parent = chunk_service.get_parent_chunk(chunk_id)

        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "NO_PARENT_CHUNK",
                        "message": "This chunk has no parent (it is a parent chunk)",
                        "details": {},
                    }
                },
            )

        return ChunkResponse(data=parent)

    except HTTPException:
        raise
    except ChunkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CHUNK_NOT_FOUND",
                    "message": "Chunk not found",
                    "details": {},
                }
            },
        )
    except ChunkServiceError as e:
        raise _handle_chunk_service_error(e)
    except Exception as e:
        logger.error(
            "get_chunk_parent_failed",
            chunk_id=chunk_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "PARENT_RETRIEVAL_FAILED",
                    "message": f"Failed to retrieve parent chunk: {e!s}",
                    "details": {},
                }
            },
        )


@chunks_router.get(
    "/{chunk_id}/children",
    response_model=ChunkListResponse,
)
async def get_chunk_children(
    chunk_id: str = Path(..., description="Parent chunk UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    matter_service: MatterService = Depends(get_matter_service),
    chunk_service: ChunkService = Depends(get_chunk_service),
) -> ChunkListResponse:
    """Get all child chunks of a parent chunk.

    Returns empty list if the chunk has no children (is itself a child).

    User must have access to the chunk's matter.
    """
    # Verify access to the parent chunk
    _verify_chunk_access(chunk_id, current_user.id, chunk_service, matter_service)

    try:
        children = chunk_service.get_child_chunks(chunk_id)

        # Convert to ChunkWithContent format
        chunks_with_content = [
            ChunkWithContent(
                id=c.id,
                document_id=c.document_id,
                content=c.content,
                chunk_type=c.chunk_type,
                chunk_index=c.chunk_index,
                token_count=c.token_count,
                parent_chunk_id=c.parent_chunk_id,
                page_number=c.page_number,
            )
            for c in children
        ]

        return ChunkListResponse(
            data=chunks_with_content,
            meta=ChunkStatsMeta(
                total=len(children),
                parent_count=0,
                child_count=len(children),
            ),
        )

    except ChunkNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CHUNK_NOT_FOUND",
                    "message": "Chunk not found",
                    "details": {},
                }
            },
        )
    except ChunkServiceError as e:
        raise _handle_chunk_service_error(e)
    except Exception as e:
        logger.error(
            "get_chunk_children_failed",
            chunk_id=chunk_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CHILDREN_RETRIEVAL_FAILED",
                    "message": f"Failed to retrieve child chunks: {e!s}",
                    "details": {},
                }
            },
        )
