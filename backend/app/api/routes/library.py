"""Library API routes for Shared Legal Library operations.

Provides endpoints for:
- Listing library documents with filters
- Getting linked library documents for a matter
- Linking/unlinking library documents to/from matters
- Checking for duplicates before upload
- Uploading new library documents

Phase 2: Shared Legal Library feature.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status, UploadFile, File
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role,
    get_current_user,
)
from app.models.library import (
    LibraryDocument,
    LibraryDocumentCreate,
    LibraryDocumentListItem,
    LibraryDocumentListResponse,
    LibraryDocumentSource,
    LibraryDocumentStatus,
    LibraryDocumentType,
    LibraryDuplicate,
    LibraryLinkRequest,
    LibraryPaginationMeta,
    LinkedLibraryDocumentsResponse,
    MatterLibraryLink,
)
from app.services.library_service import (
    get_library_service,
    LibraryDocumentNotFoundError,
    LibraryLinkExistsError,
    LibraryServiceError,
)

# =============================================================================
# Router Configuration
# =============================================================================

# Global library routes (not matter-scoped)
router = APIRouter(prefix="/library", tags=["library"])

# Matter-scoped library routes
matters_router = APIRouter(prefix="/matters/{matter_id}/library", tags=["library"])

logger = structlog.get_logger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class DuplicateCheckRequest(BaseModel):
    """Request to check for duplicate library documents."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Document title to check",
        examples=["Indian Contract Act, 1872"],
    )
    year: int | None = Field(
        None,
        ge=1800,
        le=2100,
        description="Year of enactment/publication",
    )


class DuplicateCheckResponse(BaseModel):
    """Response for duplicate check."""

    model_config = ConfigDict(populate_by_name=True)

    has_duplicates: bool = Field(..., alias="hasDuplicates", description="Whether duplicates exist")
    duplicates: list[LibraryDuplicate] = Field(
        default_factory=list,
        description="List of potential duplicates",
    )


class LinkSuccessResponse(BaseModel):
    """Response for successful link operation."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(default=True, description="Operation success")
    link: MatterLibraryLink = Field(..., description="Created link details")


class UnlinkSuccessResponse(BaseModel):
    """Response for successful unlink operation."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(default=True, description="Operation success")
    message: str = Field(default="Document unlinked from matter", description="Success message")


class UploadSuccessResponse(BaseModel):
    """Response for successful library upload."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(default=True, description="Operation success")
    document: LibraryDocument = Field(..., description="Created library document")


# =============================================================================
# Global Library Endpoints
# =============================================================================


@router.get("/documents", response_model=LibraryDocumentListResponse, response_model_by_alias=True)
async def list_library_documents(
    document_type: LibraryDocumentType | None = Query(None, description="Filter by document type"),
    year: int | None = Query(None, ge=1800, le=2100, description="Filter by year"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction"),
    doc_status: LibraryDocumentStatus | None = Query(None, alias="status", description="Filter by processing status"),
    search: str | None = Query(None, min_length=2, max_length=200, description="Search in title"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, alias="perPage", description="Items per page"),
    current_user=Depends(get_current_user),
    library_service=Depends(get_library_service),
):
    """List library documents with optional filters.

    All authenticated users can access the shared library.
    """
    try:
        # Service returns tuple of (documents, pagination_meta)
        documents, pagination = library_service.list_documents(
            page=page,
            per_page=per_page,
            document_type=document_type,
            year=year,
            jurisdiction=jurisdiction,
            status=doc_status,
            search_query=search,
        )

        return LibraryDocumentListResponse(
            documents=documents,
            pagination=pagination,
        )
    except LibraryServiceError as e:
        logger.error("list_library_documents_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIBRARY_ERROR", "message": str(e)}},
        )


@router.get("/documents/{document_id}", response_model=LibraryDocument, response_model_by_alias=True)
async def get_library_document(
    document_id: str = Path(..., description="Library document UUID"),
    current_user=Depends(get_current_user),
    library_service=Depends(get_library_service),
):
    """Get a specific library document by ID.

    All authenticated users can view library documents.
    """
    try:
        document = library_service.get_document(document_id)
        return document
    except LibraryDocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Library document not found"}},
        )
    except LibraryServiceError as e:
        logger.error("get_library_document_failed", document_id=document_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIBRARY_ERROR", "message": str(e)}},
        )


@router.post("/documents/check-duplicates", response_model=DuplicateCheckResponse, response_model_by_alias=True)
async def check_duplicates(
    request: DuplicateCheckRequest,
    current_user=Depends(get_current_user),
    library_service=Depends(get_library_service),
):
    """Check for duplicate library documents before upload.

    Uses fuzzy matching on title and year to find potential duplicates.
    Call this before uploading to avoid duplicate entries.
    """
    try:
        duplicates = library_service.find_duplicates(
            title=request.title,
            year=request.year,
        )

        return DuplicateCheckResponse(
            has_duplicates=len(duplicates) > 0,
            duplicates=duplicates,
        )
    except LibraryServiceError as e:
        logger.error("check_duplicates_failed", title=request.title, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIBRARY_ERROR", "message": str(e)}},
        )


# =============================================================================
# Matter-Scoped Library Endpoints
# =============================================================================


@matters_router.get("/documents", response_model=LinkedLibraryDocumentsResponse, response_model_by_alias=True)
async def get_linked_library_documents(
    matter_id: str = Path(..., description="Matter UUID"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    library_service=Depends(get_library_service),
):
    """Get library documents linked to a matter.

    Returns all library documents that have been linked to this matter.
    These documents will be included in matter searches.
    """
    try:
        documents = library_service.get_linked_documents(matter_id)

        return LinkedLibraryDocumentsResponse(
            documents=documents,
            total=len(documents),
        )
    except LibraryServiceError as e:
        logger.error("get_linked_documents_failed", matter_id=matter_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIBRARY_ERROR", "message": str(e)}},
        )


@matters_router.post("/documents", response_model=LinkSuccessResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
async def link_library_document(
    matter_id: str = Path(..., description="Matter UUID"),
    request: LibraryLinkRequest = ...,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    library_service=Depends(get_library_service),
):
    """Link a library document to a matter.

    Links a shared library document to this matter, making it searchable
    within the matter context. Only Owners and Editors can link documents.
    """
    try:
        link = library_service.link_to_matter(
            matter_id=matter_id,
            library_document_id=request.library_document_id,
            linked_by=membership.user_id,
        )

        logger.info(
            "library_document_linked",
            matter_id=matter_id,
            library_document_id=request.library_document_id,
            user_id=membership.user_id,
        )

        return LinkSuccessResponse(success=True, link=link)
    except LibraryDocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Library document not found"}},
        )
    except LibraryLinkExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_LINKED", "message": "Document is already linked to this matter"}},
        )
    except LibraryServiceError as e:
        logger.error(
            "link_library_document_failed",
            matter_id=matter_id,
            library_document_id=request.library_document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIBRARY_ERROR", "message": str(e)}},
        )


@matters_router.delete("/documents/{document_id}", response_model=UnlinkSuccessResponse, response_model_by_alias=True)
async def unlink_library_document(
    matter_id: str = Path(..., description="Matter UUID"),
    document_id: str = Path(..., description="Library document UUID to unlink"),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    library_service=Depends(get_library_service),
):
    """Unlink a library document from a matter.

    Removes the link between a library document and this matter.
    The document remains in the library but won't appear in matter searches.
    Only Owners and Editors can unlink documents.
    """
    try:
        success = library_service.unlink_from_matter(
            matter_id=matter_id,
            library_document_id=document_id,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Link not found"}},
            )

        logger.info(
            "library_document_unlinked",
            matter_id=matter_id,
            library_document_id=document_id,
            user_id=membership.user_id,
        )

        return UnlinkSuccessResponse(success=True, message="Document unlinked from matter")
    except LibraryServiceError as e:
        logger.error(
            "unlink_library_document_failed",
            matter_id=matter_id,
            library_document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIBRARY_ERROR", "message": str(e)}},
        )
