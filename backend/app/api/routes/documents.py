"""Document API routes for file upload and management.

Implements document upload with Supabase Storage integration,
ZIP extraction, and proper matter isolation via require_matter_role.
"""

import io
import os
import zipfile

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import (
    MatterMembership,
    MatterRole,
    require_matter_role_from_form,
)
from app.models.document import (
    BulkUploadResponse,
    DocumentResponse,
    DocumentType,
    UploadedDocument,
)
from app.services.document_service import (
    DocumentService,
    DocumentServiceError,
    get_document_service,
)
from app.services.storage_service import (
    StorageError,
    StorageService,
    get_storage_service,
)

router = APIRouter(prefix="/documents", tags=["documents"])
logger = structlog.get_logger(__name__)

# File size limits
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/zip": "zip",
    "application/x-zip-compressed": "zip",
}


def _handle_service_error(error: DocumentServiceError | StorageError) -> HTTPException:
    """Convert service errors to HTTP exceptions."""
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
    uploaded_paths: list[str] = []  # Track for rollback

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
        # Rollback: delete any uploaded files on failure
        logger.error(
            "zip_extraction_failed",
            matter_id=matter_id,
            error=str(e),
            uploaded_paths=uploaded_paths,
        )

        for path in uploaded_paths:
            try:
                storage_service.delete_file(path)
            except Exception as delete_error:
                logger.warning(
                    "rollback_delete_failed",
                    storage_path=path,
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

            logger.info(
                "document_upload_complete",
                document_id=doc.document_id,
                matter_id=matter_id,
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
