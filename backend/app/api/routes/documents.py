"""Document API routes for file upload and management.

Implements document upload with Supabase Storage integration,
ZIP extraction, and proper matter isolation via require_matter_role.
"""

import io
import os
import zipfile

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from app.api.deps import (
    MatterMembership,
    MatterRole,
    get_matter_service,
    require_matter_role,
    require_matter_role_from_form,
)
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.services.matter_service import MatterService
from app.models.document import (
    BulkDocumentUpdate,
    BulkUpdateResponse,
    BulkUploadResponse,
    Document,
    DocumentDetailResponse,
    DocumentListResponseWithPagination,
    DocumentResponse,
    DocumentType,
    DocumentUpdate,
    UploadedDocument,
)
from app.models.ocr_confidence import OCRQualityResponse
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
    DocumentServiceError,
    get_document_service,
)
from app.services.storage_service import (
    StorageError,
    StorageService,
    get_storage_service,
)
from app.services.ocr.confidence_calculator import (
    ConfidenceCalculatorError,
    calculate_document_confidence,
)
from app.services.ocr.human_review_service import (
    HumanReviewService,
    HumanReviewServiceError,
    get_human_review_service,
)
from app.workers.tasks.document_tasks import (
    calculate_confidence,
    chunk_document,
    embed_chunks,
    extract_entities,
    process_document,
    validate_ocr,
)

router = APIRouter(prefix="/documents", tags=["documents"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Request/Response Models for Manual Review
# =============================================================================


class ManualReviewRequest(BaseModel):
    """Request body for requesting manual review of specific pages."""

    pages: list[int] = Field(
        ...,
        min_length=1,
        description="List of page numbers to flag for manual review"
    )


class ManualReviewResponse(BaseModel):
    """Response for manual review request."""

    data: dict[str, str | int | bool]

# File size limits
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
SMALL_DOCUMENT_THRESHOLD_PAGES = 100  # Documents under this use 'high' priority queue


def _verify_matter_access(
    matter_id: str,
    user_id: str,
    matter_service: MatterService,
    allowed_roles: list[MatterRole],
) -> MatterRole:
    """Verify user has required role on a matter (Layer 4 defense-in-depth).

    Args:
        matter_id: Matter UUID to check access for.
        user_id: User UUID requesting access.
        matter_service: MatterService instance.
        allowed_roles: List of roles that permit this action.

    Returns:
        The user's role on the matter.

    Raises:
        HTTPException: 404 if no access, 403 if insufficient role.
    """
    role = matter_service.get_user_role(matter_id, user_id)

    if role is None:
        logger.warning(
            "document_access_denied",
            user_id=user_id,
            matter_id=matter_id,
            reason="no_membership",
        )
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

    if role not in allowed_roles:
        logger.warning(
            "document_access_denied",
            user_id=user_id,
            matter_id=matter_id,
            user_role=role.value,
            required_roles=[r.value for r in allowed_roles],
        )
        roles_str = ", ".join(r.value for r in allowed_roles)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": f"This action requires one of these roles: {roles_str}",
                    "details": {},
                }
            },
        )

    return role

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/zip": "zip",
    "application/x-zip-compressed": "zip",
}


def _handle_service_error(error: DocumentServiceError | StorageError) -> HTTPException:
    """Convert service layer errors to HTTP exceptions.

    Maps service-specific error codes to appropriate HTTP status codes
    and formats the response according to the API error response standard.

    Args:
        error: Service error from DocumentService or StorageService.

    Returns:
        HTTPException with properly formatted error detail.
    """
    status_code = getattr(error, "status_code", 500)
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {},
            }
        },
    )


def _validate_file(file: UploadFile) -> str:
    """Validate uploaded file type and size.

    Args:
        file: Uploaded file to validate.

    Returns:
        File type string ('pdf' or 'zip').

    Raises:
        HTTPException: If file is invalid.
    """
    # Check content type
    content_type = file.content_type or ""
    file_type = ALLOWED_MIME_TYPES.get(content_type)

    if file_type is None:
        # Also check by extension as fallback
        filename = file.filename or ""
        if filename.lower().endswith(".pdf"):
            file_type = "pdf"
        elif filename.lower().endswith(".zip"):
            file_type = "zip"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_FILE_TYPE",
                        "message": "Only PDF and ZIP files are supported",
                        "details": {"content_type": content_type},
                    }
                },
            )

    return file_type


def _get_subfolder(document_type: DocumentType) -> str:
    """Get storage subfolder based on document type.

    Args:
        document_type: Document classification type.

    Returns:
        Storage subfolder name.
    """
    if document_type == DocumentType.ACT:
        return "acts"
    return "uploads"


def _queue_ocr_task(document_id: str, file_size: int) -> None:
    """Queue full document processing pipeline for a document.

    Uses Celery chain to run the complete document ingestion pipeline.
    Smaller documents (<10MB, ~100 pages) get 'high' priority.

    The task chain:
    1. process_document: OCR with Google Document AI
    2. validate_ocr: Gemini validation + pattern correction
    3. calculate_confidence: Calculate and store OCR quality metrics
    4. chunk_document: Create parent-child chunks for RAG
    5. embed_chunks: Generate OpenAI embeddings for semantic search

    After completion, documents are fully searchable via hybrid search.

    Args:
        document_id: Document UUID to process.
        file_size: File size in bytes.
    """
    from celery import chain

    # Heuristic: ~100KB per page average for scanned PDFs
    # 10MB ~ 100 pages
    is_small_document = file_size < 10 * 1024 * 1024

    queue_name = "high" if is_small_document else "default"

    # Create task chain: OCR -> Validation -> Confidence -> Chunking -> Embedding -> Entity Extraction
    # Each task receives the result from the previous task as first argument
    # Full pipeline makes documents searchable via hybrid search (BM25 + semantic)
    # and populates the Matter Identity Graph (MIG) with extracted entities
    task_chain = chain(
        process_document.s(document_id),
        validate_ocr.s(),
        calculate_confidence.s(),
        chunk_document.s(),
        embed_chunks.s(),
        extract_entities.s(),
    )

    # Apply the chain to the appropriate queue
    task_chain.apply_async(queue=queue_name)

    logger.info(
        "document_processing_chain_queued",
        document_id=document_id,
        queue=queue_name,
        file_size=file_size,
        stages="ocr->validation->confidence->chunking->embedding->entity_extraction",
    )


async def _extract_and_upload_zip(
    zip_content: bytes,
    matter_id: str,
    user_id: str,
    storage_service: StorageService,
    document_service: DocumentService,
) -> list[UploadedDocument]:
    """Extract ZIP and upload each PDF individually.

    Args:
        zip_content: ZIP file content as bytes.
        matter_id: Matter UUID.
        user_id: User UUID who uploaded.
        storage_service: Storage service instance.
        document_service: Document service instance.

    Returns:
        List of uploaded documents.

    Raises:
        HTTPException: If extraction fails or ZIP contains no PDFs.
    """
    documents: list[UploadedDocument] = []
    uploaded_paths: list[str] = []  # Track storage paths for rollback
    created_doc_ids: list[str] = []  # Track document IDs for rollback

    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            # Filter for PDF files only
            pdf_files = [
                f for f in zf.namelist()
                if f.lower().endswith(".pdf") and not f.startswith("__MACOSX")
            ]

            if not pdf_files:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "code": "NO_PDFS_IN_ZIP",
                            "message": "ZIP contains no PDF files",
                            "details": {},
                        }
                    },
                )

            logger.info(
                "zip_extraction_starting",
                matter_id=matter_id,
                pdf_count=len(pdf_files),
            )

            for pdf_path in pdf_files:
                # Read PDF content
                pdf_content = zf.read(pdf_path)

                # Get just the filename (handle nested paths)
                filename = os.path.basename(pdf_path)

                # Skip if filename is empty (directory entries)
                if not filename:
                    continue

                # Upload to storage
                storage_path, _ = storage_service.upload_file(
                    matter_id=matter_id,
                    subfolder="uploads",
                    file_content=pdf_content,
                    filename=filename,
                    content_type="application/pdf",
                )
                uploaded_paths.append(storage_path)

                # Create document record
                doc = document_service.create_document(
                    matter_id=matter_id,
                    filename=filename,
                    storage_path=storage_path,
                    file_size=len(pdf_content),
                    document_type=DocumentType.CASE_FILE,
                    uploaded_by=user_id,
                )
                documents.append(doc)
                created_doc_ids.append(doc.document_id)

                # Queue OCR processing for this document
                _queue_ocr_task(doc.document_id, len(pdf_content))

            logger.info(
                "zip_extraction_complete",
                matter_id=matter_id,
                documents_created=len(documents),
            )

            return documents

    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_ZIP",
                    "message": "The uploaded file is not a valid ZIP archive",
                    "details": {},
                }
            },
        )
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        # Rollback: delete uploaded files AND document records on failure
        logger.error(
            "zip_extraction_failed",
            matter_id=matter_id,
            error=str(e),
            uploaded_paths=uploaded_paths,
            created_doc_ids=created_doc_ids,
        )

        # Delete storage files
        for path in uploaded_paths:
            try:
                storage_service.delete_file(path)
            except Exception as delete_error:
                logger.warning(
                    "rollback_storage_delete_failed",
                    storage_path=path,
                    error=str(delete_error),
                )

        # Delete document records
        for doc_id in created_doc_ids:
            try:
                document_service.delete_document(doc_id)
            except Exception as delete_error:
                logger.warning(
                    "rollback_document_delete_failed",
                    document_id=doc_id,
                    error=str(delete_error),
                )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ZIP_EXTRACTION_FAILED",
                    "message": f"Failed to extract ZIP file: {e!s}",
                    "details": {},
                }
            },
        )


@router.post(
    "/upload",
    response_model=DocumentResponse | BulkUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(..., description="PDF or ZIP file to upload"),
    document_type: DocumentType = Form(
        default=DocumentType.CASE_FILE,
        description="Document classification type"
    ),
    membership: MatterMembership = Depends(
        require_matter_role_from_form([MatterRole.OWNER, MatterRole.EDITOR])
    ),
    storage_service: StorageService = Depends(get_storage_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentResponse | BulkUploadResponse:
    """Upload a document to a matter.

    Supports PDF files (stored directly) and ZIP files (extracted, PDFs stored individually).

    Requires editor or owner role on the matter.

    Args:
        file: PDF or ZIP file to upload.
        document_type: Document classification type.
        membership: User's matter membership (validated by dependency, includes matter_id).
        storage_service: Storage service for file operations.
        document_service: Document service for database operations.

    Returns:
        DocumentResponse for single PDF, BulkUploadResponse for ZIP.

    Raises:
        HTTPException: If upload fails or file is invalid.
    """
    # Get matter_id from validated membership
    matter_id = membership.matter_id

    # Validate file type
    file_type = _validate_file(file)

    # Read file content
    file_content = await file.read()

    # Validate file size
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit",
                    "details": {"file_size": len(file_content)},
                }
            },
        )

    logger.info(
        "document_upload_starting",
        matter_id=matter_id,
        user_id=membership.user_id,
        filename=file.filename,
        file_type=file_type,
        file_size=len(file_content),
        document_type=document_type.value,
    )

    try:
        if file_type == "zip":
            # Extract ZIP and upload each PDF
            documents = await _extract_and_upload_zip(
                zip_content=file_content,
                matter_id=matter_id,
                user_id=membership.user_id,
                storage_service=storage_service,
                document_service=document_service,
            )

            return BulkUploadResponse(
                data=documents,
                meta={
                    "total_files": len(documents),
                    "source_filename": file.filename,
                },
            )

        else:
            # Single PDF upload
            subfolder = _get_subfolder(document_type)

            # Upload to storage
            storage_path, _ = storage_service.upload_file(
                matter_id=matter_id,
                subfolder=subfolder,
                file_content=file_content,
                filename=file.filename or "document.pdf",
                content_type="application/pdf",
            )

            # Create document record
            doc = document_service.create_document(
                matter_id=matter_id,
                filename=file.filename or "document.pdf",
                storage_path=storage_path,
                file_size=len(file_content),
                document_type=document_type,
                uploaded_by=membership.user_id,
            )

            # Queue OCR processing task
            # Use 'high' priority for small files (under 10MB heuristic for <100 pages)
            _queue_ocr_task(doc.document_id, len(file_content))

            logger.info(
                "document_upload_complete",
                document_id=doc.document_id,
                matter_id=matter_id,
                ocr_queued=True,
            )

            return DocumentResponse(data=doc)

    except HTTPException:
        raise
    except (StorageError, DocumentServiceError) as e:
        raise _handle_service_error(e)
    except Exception as e:
        logger.error(
            "document_upload_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "UPLOAD_FAILED",
                    "message": f"Failed to upload document: {e!s}",
                    "details": {},
                }
            },
        )


# =============================================================================
# Matter-scoped document endpoints
# =============================================================================


# Create a separate router for matter-scoped endpoints
matters_router = APIRouter(prefix="/matters", tags=["documents"])


@matters_router.get(
    "/{matter_id}/documents",
    response_model=DocumentListResponseWithPagination,
)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    document_type: DocumentType | None = Query(
        None, description="Filter by document type"
    ),
    doc_status: str | None = Query(
        None,
        alias="status",
        description="Filter by processing status",
    ),
    is_reference_material: bool | None = Query(
        None, description="Filter by reference material flag"
    ),
    sort_by: str = Query(
        "uploaded_at",
        description="Column to sort by (uploaded_at, filename, file_size, document_type, status)",
    ),
    sort_order: str = Query(
        "desc",
        description="Sort direction (asc or desc)",
    ),
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentListResponseWithPagination:
    """List documents in a matter with filtering, sorting, and pagination.

    Returns paginated list with metadata (filename, type, status, uploaded_at).
    Supports filtering by document_type, status, and is_reference_material.
    Supports sorting by uploaded_at, filename, file_size, document_type, or status.

    Requires viewer, editor, or owner role on the matter.
    """
    try:
        documents, meta = document_service.list_documents(
            matter_id=membership.matter_id,
            page=page,
            per_page=per_page,
            document_type=document_type,
            status=doc_status,
            is_reference_material=is_reference_material,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return DocumentListResponseWithPagination(data=documents, meta=meta)

    except DocumentServiceError as e:
        raise _handle_service_error(e)
    except Exception as e:
        logger.error(
            "document_list_failed",
            matter_id=membership.matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "LIST_FAILED",
                    "message": f"Failed to list documents: {e!s}",
                    "details": {},
                }
            },
        )


# =============================================================================
# Bulk Operations (must be defined BEFORE /{document_id} to avoid conflict)
# =============================================================================


@router.patch(
    "/bulk",
    response_model=BulkUpdateResponse,
)
async def bulk_update_documents(
    update: BulkDocumentUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
) -> BulkUpdateResponse:
    """Bulk update document types.

    Accepts a list of document IDs and a document type to assign to all.
    When document_type is 'act', is_reference_material is automatically set to true.

    User must have editor or owner role on each document's matter.
    Validates access for ALL documents before performing any updates.
    """
    try:
        # Verify user has EDITOR/OWNER access to all documents' matters
        # by checking each document's matter_id
        matter_ids_checked: set[str] = set()
        for doc_id in update.document_ids:
            try:
                doc = document_service.get_document(doc_id)
                # Only check each matter once
                if doc.matter_id not in matter_ids_checked:
                    _verify_matter_access(
                        matter_id=doc.matter_id,
                        user_id=current_user.id,
                        matter_service=matter_service,
                        allowed_roles=[MatterRole.OWNER, MatterRole.EDITOR],
                    )
                    matter_ids_checked.add(doc.matter_id)
            except DocumentNotFoundError:
                # Document doesn't exist - will be skipped by bulk update
                continue

        updated_count = document_service.bulk_update_documents(
            document_ids=update.document_ids,
            document_type=update.document_type,
        )

        return BulkUpdateResponse(
            data={
                "updated_count": updated_count,
                "requested_count": len(update.document_ids),
                "document_type": update.document_type.value,
            }
        )

    except HTTPException:
        raise
    except DocumentServiceError as e:
        raise _handle_service_error(e)
    except Exception as e:
        logger.error(
            "document_bulk_update_failed",
            document_ids=update.document_ids,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "BULK_UPDATE_FAILED",
                    "message": f"Failed to bulk update documents: {e!s}",
                    "details": {},
                }
            },
        )


# =============================================================================
# Document-scoped endpoints
# =============================================================================


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
async def get_document(
    document_id: str = Path(..., description="Document UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    storage_service: StorageService = Depends(get_storage_service),
) -> DocumentDetailResponse:
    """Get document details with signed URL.

    Returns full document metadata including a signed URL for file access.
    User must have access to the document's matter.
    """
    try:
        # Get document (RLS will filter if user doesn't have access)
        doc = document_service.get_document(document_id)

        # Generate signed URL for storage access (valid for 1 hour)
        signed_url = storage_service.get_signed_url(doc.storage_path, expires_in=3600)

        # Create response with signed URL in storage_path field
        doc_with_url = Document(
            id=doc.id,
            matter_id=doc.matter_id,
            filename=doc.filename,
            storage_path=signed_url,
            file_size=doc.file_size,
            page_count=doc.page_count,
            document_type=doc.document_type,
            is_reference_material=doc.is_reference_material,
            uploaded_by=doc.uploaded_by,
            uploaded_at=doc.uploaded_at,
            status=doc.status,
            processing_started_at=doc.processing_started_at,
            processing_completed_at=doc.processing_completed_at,
            extracted_text=doc.extracted_text,
            ocr_confidence=doc.ocr_confidence,
            ocr_quality_score=doc.ocr_quality_score,
            ocr_confidence_per_page=doc.ocr_confidence_per_page,
            ocr_quality_status=doc.ocr_quality_status,
            ocr_error=doc.ocr_error,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

        return DocumentDetailResponse(data=doc_with_url)

    except DocumentNotFoundError:
        # Return 404 to prevent enumeration
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
    except DocumentServiceError as e:
        raise _handle_service_error(e)
    except StorageError as e:
        raise _handle_service_error(e)
    except Exception as e:
        logger.error(
            "document_get_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "GET_FAILED",
                    "message": f"Failed to get document: {e!s}",
                    "details": {},
                }
            },
        )


@router.patch(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
async def update_document(
    document_id: str = Path(..., description="Document UUID"),
    update: DocumentUpdate = ...,
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
) -> DocumentDetailResponse:
    """Update document metadata.

    Allows updating document_type and is_reference_material.
    When document_type is changed to 'act', is_reference_material is automatically
    set to true unless explicitly overridden.

    User must have editor or owner role on the document's matter.
    """
    try:
        # Get document first to get matter_id for access verification
        doc = document_service.get_document(document_id)

        # Verify user has EDITOR/OWNER role on the document's matter (Layer 4)
        _verify_matter_access(
            matter_id=doc.matter_id,
            user_id=current_user.id,
            matter_service=matter_service,
            allowed_roles=[MatterRole.OWNER, MatterRole.EDITOR],
        )

        # Perform the update
        updated_doc = document_service.update_document(
            document_id=document_id,
            document_type=update.document_type,
            is_reference_material=update.is_reference_material,
        )

        return DocumentDetailResponse(data=updated_doc)

    except HTTPException:
        raise
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
    except DocumentServiceError as e:
        raise _handle_service_error(e)
    except Exception as e:
        logger.error(
            "document_update_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "UPDATE_FAILED",
                    "message": f"Failed to update document: {e!s}",
                    "details": {},
                }
            },
        )


@router.get(
    "/{document_id}/ocr-quality",
    response_model=OCRQualityResponse,
)
async def get_ocr_quality(
    document_id: str = Path(..., description="Document UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> OCRQualityResponse:
    """Get detailed OCR quality breakdown for a document.

    Returns overall confidence, per-page confidence breakdown,
    and quality status determination.

    User must have access to the document's matter.
    """
    try:
        # Verify access to document (RLS will filter)
        document_service.get_document(document_id)

        # Calculate confidence metrics
        result = calculate_document_confidence(document_id)

        return OCRQualityResponse(data=result)

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
    except ConfidenceCalculatorError as e:
        logger.error(
            "ocr_quality_calculation_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "OCR_QUALITY_CALCULATION_FAILED",
                    "message": f"Failed to calculate OCR quality: {e!s}",
                    "details": {},
                }
            },
        )
    except Exception as e:
        logger.error(
            "ocr_quality_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "OCR_QUALITY_FAILED",
                    "message": f"Failed to get OCR quality: {e!s}",
                    "details": {},
                }
            },
        )


@router.post(
    "/{document_id}/request-manual-review",
    response_model=ManualReviewResponse,
)
async def request_manual_review(
    document_id: str = Path(..., description="Document UUID"),
    request: ManualReviewRequest = ...,
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
    human_review_service: HumanReviewService = Depends(get_human_review_service),
) -> ManualReviewResponse:
    """Request manual review for specific pages of a document.

    Adds the specified pages to the human review queue for manual verification.
    User must have editor or owner role on the document's matter.
    """
    try:
        # Get document to get matter_id for access verification
        doc = document_service.get_document(document_id)

        # Verify user has EDITOR/OWNER role on the document's matter
        _verify_matter_access(
            matter_id=doc.matter_id,
            user_id=current_user.id,
            matter_service=matter_service,
            allowed_roles=[MatterRole.OWNER, MatterRole.EDITOR],
        )

        # Add pages to review queue
        added_count = human_review_service.add_pages_to_queue(
            document_id=document_id,
            matter_id=doc.matter_id,
            pages=request.pages,
        )

        logger.info(
            "manual_review_requested",
            document_id=document_id,
            pages=request.pages,
            added_count=added_count,
            user_id=current_user.id,
        )

        return ManualReviewResponse(
            data={
                "document_id": document_id,
                "pages_added": added_count,
                "success": True,
            }
        )

    except HTTPException:
        raise
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
    except HumanReviewServiceError as e:
        logger.error(
            "manual_review_request_failed",
            document_id=document_id,
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
    except Exception as e:
        logger.error(
            "manual_review_request_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "MANUAL_REVIEW_REQUEST_FAILED",
                    "message": f"Failed to request manual review: {e!s}",
                    "details": {},
                }
            },
        )
