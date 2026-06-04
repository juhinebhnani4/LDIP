"""Document API routes for file upload and management.

Implements document upload with Supabase Storage integration,
ZIP extraction, and proper matter isolation via require_matter_role.

Security notes:
- Uses SpooledTemporaryFile for memory-efficient streaming (avoids DoS via memory exhaustion)
- ZIP extraction includes bomb protection (compression ratio and total size limits)
- Storage access uses Service Role client (RLS bypassed - access validated at API layer)
"""

import asyncio
import io
import os
import tempfile
import zipfile
from typing import Any

import structlog
from celery import chain
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
from app.core.config import get_settings
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.document import (
    BulkDocumentUpdate,
    BulkUpdateResponse,
    BulkUploadResponse,
    DocumentDetailResponse,
    DocumentFeatures,
    DocumentListResponseWithPagination,
    DocumentResponse,
    DocumentType,
    DocumentUpdate,
    DocumentWithFeatures,
    UploadedDocument,
)
from app.models.library import (
    LibraryDocumentCreate,
    LibraryDocumentSource,
    LibraryDocumentType,
)
from app.models.ocr_confidence import OCRQualityResponse
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
    DocumentServiceError,
    get_document_service,
)
from app.services.library_service import (
    LibraryService,
    LibraryServiceError,
    get_library_service,
)
from app.services.matter_service import MatterService
from app.services.ocr.confidence_calculator import (
    ConfidenceCalculatorError,
    calculate_document_confidence,
)
from app.services.ocr.human_review_service import (
    HumanReviewService,
    HumanReviewServiceError,
    get_human_review_service,
)
from app.services.storage_service import (
    StorageError,
    StorageService,
    get_storage_service,
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


# =============================================================================
# Feature Availability Helper (Story 7.2)
# =============================================================================


async def _get_document_features(document_id: str) -> DocumentFeatures:
    """Query database to determine feature availability for a document.

    Story 7.2: Progressive UI updates - indicates which features are available
    based on pipeline completion status.

    Args:
        document_id: Document UUID to check features for.

    Returns:
        DocumentFeatures with availability flags for each feature.
    """
    from app.services.supabase.client import get_service_client

    features = DocumentFeatures()

    try:
        client = get_service_client()

        # Run all feature checks in a single thread to avoid blocking
        # the async event loop (sync Supabase client uses httpx.Client).
        def _check_features() -> DocumentFeatures:
            f = DocumentFeatures()

            chunks_resp = (
                client.table("chunks")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .limit(1)
                .execute()
            )
            f.search = (chunks_resp.count or 0) > 0

            if f.search:
                embeddings_resp = (
                    client.table("chunks")
                    .select("id", count="exact")
                    .eq("document_id", document_id)
                    .not_.is_("embedding", "null")
                    .limit(1)
                    .execute()
                )
                f.semantic_search = (embeddings_resp.count or 0) > 0

            entities_resp = (
                client.table("identity_nodes")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .limit(1)
                .execute()
            )
            f.entities = (entities_resp.count or 0) > 0

            timeline_resp = (
                client.table("timeline_events")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .limit(1)
                .execute()
            )
            f.timeline = (timeline_resp.count or 0) > 0

            citations_resp = (
                client.table("citations")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .limit(1)
                .execute()
            )
            f.citations = (citations_resp.count or 0) > 0

            bbox_resp = (
                client.table("chunk_bounding_boxes")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .limit(1)
                .execute()
            )
            f.bbox_highlighting = (bbox_resp.count or 0) > 0

            return f

        features = await asyncio.to_thread(_check_features)

        logger.debug(
            "document_features_checked",
            document_id=document_id,
            search=features.search,
            semantic_search=features.semantic_search,
            entities=features.entities,
            timeline=features.timeline,
            citations=features.citations,
            bbox_highlighting=features.bbox_highlighting,
        )

    except Exception as e:
        logger.warning(
            "document_features_check_failed",
            document_id=document_id,
            error=str(e),
        )
        # Return default features (all False) on error

    return features


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

# File size limits (Story 2.5: Configurable limit with soft-launch mode)
_settings = get_settings()
MAX_FILE_SIZE_MB = _settings.file_size_max_mb  # Default: 50MB
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
LEGACY_MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB absolute max (DoS protection)
SMALL_DOCUMENT_THRESHOLD_PAGES = 100  # <100 pages -> 'high' priority queue

# Streaming upload configuration
# Files under this threshold are kept in memory; larger files spill to disk
SPOOL_MAX_SIZE = 10 * 1024 * 1024  # 10MB - files larger than this use disk

# ZIP bomb protection limits
ZIP_MAX_COMPRESSION_RATIO = 100  # Max allowed compression ratio (uncompressed/compressed)
ZIP_MAX_TOTAL_EXTRACTED_SIZE = 2 * 1024 * 1024 * 1024  # 2GB max total extracted size
ZIP_MAX_FILES = 500  # Maximum number of files in a ZIP


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


def _extract_year_from_filename(filename: str) -> int | None:
    """Extract year from filename like 'Indian Contract Act, 1872.pdf'."""
    import re
    match = re.search(r'\b(1[89]\d{2}|20\d{2})\b', filename)
    return int(match.group(1)) if match else None


def _detect_act_from_filename(filename: str) -> bool:
    """Detect if a filename looks like a statute/Act.

    Matches patterns like "TORTS Act 1992.pdf", "Indian Contract Act, 1872.pdf",
    "Code of Criminal Procedure 1973.pdf", etc.

    Returns True if the filename matches a statute pattern.
    """
    import re
    # Remove extension
    name = re.sub(r'\.[^.]+$', '', filename)
    # Match common statute keywords as whole words
    return bool(re.search(
        r'\b(act|code|statute|ordinance|regulation|rules|bill)\b',
        name,
        re.IGNORECASE,
    ))


async def _upload_act_to_library(
    file_content: bytes,
    filename: str,
    file_size: int,
    matter_id: str,
    user_id: str,
    storage_service: StorageService,
    library_service: LibraryService,
) -> dict:
    """Upload an Act to the shared library and link to matter.

    Acts go to the global library (library_documents table) instead of
    matter-specific documents. They are then linked to the matter via
    matter_library_links.

    Args:
        file_content: PDF file bytes.
        filename: Original filename.
        file_size: File size in bytes.
        matter_id: Matter to link the Act to.
        user_id: User uploading the Act.
        storage_service: Storage service for file operations.
        library_service: Library service for database operations.

    Returns:
        Dictionary with library_document_id and link_id.

    Raises:
        HTTPException: If upload or linking fails.
    """
    # Generate title from filename (remove .pdf extension)
    title = filename.rsplit(".", 1)[0] if "." in filename else filename
    year = _extract_year_from_filename(filename)

    # Upload to global acts storage (not matter-specific)
    # Use normalized filename for storage path
    import re
    normalized_name = re.sub(r'[^\w\s-]', '', title.lower())
    normalized_name = re.sub(r'\s+', '_', normalized_name)
    storage_path = f"global/acts/{normalized_name}.pdf"

    # GAP-12: Standardized dedup using find_library_duplicates RPC
    try:
        duplicates = library_service.find_duplicates(title, year=year, similarity_threshold=0.6)
        if duplicates:
            existing_id = duplicates[0].id
            logger.info(
                "act_already_in_library",
                existing_id=existing_id,
                title=title,
                similarity=duplicates[0].similarity,
            )
            link = library_service.link_to_matter(
                matter_id=matter_id,
                library_document_id=existing_id,
                linked_by=user_id,
            )
            return {
                "library_document_id": existing_id,
                "link_id": link.id,
                "is_new": False,
                "title": duplicates[0].title,
            }
    except Exception as e:
        logger.warning("act_dedup_rpc_failed", title=title, error=str(e))

    # Upload file to global storage
    # Use "global" as pseudo-matter_id to get path: global/acts/{filename}
    actual_storage_path, _ = storage_service.upload_file(
        matter_id="global",  # Global storage, not matter-specific
        subfolder="acts",
        file_content=file_content,
        filename=f"{normalized_name}.pdf",
        content_type="application/pdf",
    )

    # Create library document record
    create_data = LibraryDocumentCreate(
        filename=filename,
        title=title,
        document_type=LibraryDocumentType.ACT,
        year=year,
        jurisdiction="central",  # Default to central for uploaded Acts
    )

    library_doc = library_service.create_document(
        create_data=create_data,
        storage_path=actual_storage_path,
        file_size=file_size,
        added_by=user_id,
        source=LibraryDocumentSource.USER_UPLOAD,
    )

    # Link to the matter
    link = library_service.link_to_matter(
        matter_id=matter_id,
        library_document_id=library_doc.id,
        linked_by=user_id,
    )

    logger.info(
        "act_uploaded_to_library",
        library_document_id=library_doc.id,
        matter_id=matter_id,
        title=title,
        link_id=link.id,
    )

    # GAP-1 fix: Dispatch OCR immediately for user-uploaded Acts.
    # Previously, OCR only started 30-45 min later when the maintenance sweep
    # caught the pending doc. Now we dispatch synchronously from the upload path.
    # Wrapped in try/except so upload succeeds even if Redis is down —
    # the maintenance sweep will catch the pending doc within 60 min.
    ocr_queued = False
    try:
        from app.workers.tasks.library_tasks import ocr_and_process_library_document
        ocr_and_process_library_document.apply_async(
            kwargs={
                "library_document_id": library_doc.id,
                "storage_path": actual_storage_path,
            },
            countdown=2,  # Small delay to let DB transaction commit
        )
        ocr_queued = True
        logger.info(
            "act_ocr_dispatched",
            library_document_id=library_doc.id,
            storage_path=actual_storage_path,
        )
    except Exception as e:
        logger.warning(
            "act_ocr_dispatch_failed",
            library_document_id=library_doc.id,
            error=str(e),
            note="Maintenance sweep will pick up this pending doc within 60 min",
        )

    return {
        "library_document_id": library_doc.id,
        "link_id": link.id,
        "is_new": True,
        "title": library_doc.title,
        "ocr_queued": ocr_queued,
    }


def _is_soft_launch_active() -> bool:
    """Check if soft-launch period is active for file size validation.

    Story 2.5: During soft-launch, oversized files are allowed but logged.
    After soft-launch ends, enforcement mode takes over.

    Returns:
        True if soft-launch is active (warn mode), False otherwise (enforce mode).
    """
    from datetime import UTC, datetime

    settings = get_settings()

    # If explicitly set to "warn" mode, soft-launch is active
    if settings.file_size_enforcement == "warn":
        return True

    # If soft-launch end date is set and we're before it, soft-launch is active
    if settings.file_size_soft_launch_until:
        try:
            date_str = settings.file_size_soft_launch_until.replace("Z", "+00:00")
            end_date = datetime.fromisoformat(date_str)
            if datetime.now(UTC) < end_date:
                return True
        except ValueError:
            # Invalid date format - ignore and use enforce mode
            logger.warning(
                "invalid_soft_launch_date",
                value=settings.file_size_soft_launch_until,
            )

    return False


async def _read_file_with_streaming(file: UploadFile) -> tuple[bytes, int]:
    """Read uploaded file using streaming to avoid memory exhaustion.

    Uses SpooledTemporaryFile to handle large files efficiently:
    - Small files (< SPOOL_MAX_SIZE) stay in memory
    - Large files automatically spill to disk

    Story 2.5: Enforces configurable file size limit (default 50MB) with
    soft-launch mode support that logs warnings instead of rejecting.

    Args:
        file: FastAPI UploadFile object.

    Returns:
        Tuple of (file_content_bytes, file_size).

    Raises:
        HTTPException: If file exceeds MAX_FILE_SIZE (unless soft-launch mode).
    """
    soft_launch = _is_soft_launch_active()
    size_exceeded_logged = False

    # Use SpooledTemporaryFile for memory-efficient streaming
    # Small files stay in RAM, large files spill to disk automatically
    with tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_SIZE) as spooled:
        total_size = 0
        chunk_size = 64 * 1024  # 64KB chunks

        # Stream file in chunks to avoid loading 500MB into RAM at once
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break

            total_size += len(chunk)

            # Story 2.5: Check configurable size limit during streaming (fail fast)
            if total_size > MAX_FILE_SIZE and not size_exceeded_logged:
                if soft_launch:
                    # Soft-launch mode: warn but allow (Story 2.5)
                    logger.warning(
                        "file_size_exceeded_soft_launch",
                        filename=file.filename,
                        file_size=total_size,
                        limit_mb=MAX_FILE_SIZE_MB,
                    )
                    size_exceeded_logged = True
                else:
                    # Enforce mode: reject with 413 Payload Too Large
                    logger.warning(
                        "file_size_exceeded_rejected",
                        filename=file.filename,
                        file_size=total_size,
                        limit_mb=MAX_FILE_SIZE_MB,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={
                            "error": {
                                "code": "FILE_TOO_LARGE",
                                "message": f"Maximum file size is {MAX_FILE_SIZE_MB}MB",
                                "details": {
                                    "file_size": total_size,
                                    "limit_bytes": MAX_FILE_SIZE,
                                    "limit_mb": MAX_FILE_SIZE_MB,
                                },
                            }
                        },
                    )

            # Safety limit: absolute maximum regardless of config (DoS protection)
            if total_size > LEGACY_MAX_FILE_SIZE:
                max_mb = LEGACY_MAX_FILE_SIZE // (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={
                        "error": {
                            "code": "FILE_TOO_LARGE",
                            "message": f"File exceeds absolute maximum of {max_mb}MB",
                            "details": {"file_size": total_size},
                        }
                    },
                )

            spooled.write(chunk)

        # Seek back to start and read all content
        spooled.seek(0)
        content = spooled.read()

    return content, total_size


def _queue_ocr_task(document_id: str, file_size: int, matter_id: str | None = None) -> None:
    """Queue full document processing pipeline for a document.

    Uses Celery chain to run the complete document ingestion pipeline.

    Stage 2.4: If the matter already has >= max_concurrent_docs_per_matter
    documents in PROCESSING, the document stays QUEUED and will be picked up
    by the dispatch_stuck_queued_jobs maintenance task when a slot opens.

    The task chain:
    1. process_document: OCR with Google Document AI
    2. validate_ocr: Gemini validation + pattern correction
    3. calculate_confidence: Calculate and store OCR quality metrics
    4. chunk_document: Create parent-child chunks for RAG
    5. embed_chunks: Generate OpenAI embeddings for semantic search
    6. extract_entities: Extract entities for Matter Identity Graph
    7. resolve_aliases: Resolve entity aliases and create links
       -> Dispatches extract_citations and extract_dates_from_document in parallel

    After completion, documents are fully searchable via hybrid search.

    Args:
        document_id: Document UUID to process.
        file_size: File size in bytes.
        matter_id: Matter UUID (for concurrency limit check).
    """
    from celery import chain

    # Stage 2.4: Per-matter concurrency limit
    if matter_id:
        try:
            from app.services.supabase.client import get_service_client
            settings = get_settings()
            client = get_service_client()
            if client:
                processing_count = (
                    client.table("processing_jobs")
                    .select("id", count="exact")
                    .eq("matter_id", matter_id)
                    .eq("status", "PROCESSING")
                    .execute()
                ).count or 0

                if processing_count >= settings.max_concurrent_docs_per_matter:
                    # Create a QUEUED processing_job so dispatch_stuck_queued_jobs
                    # maintenance task (runs every 10 min) picks it up when a slot opens
                    try:
                        client.table("processing_jobs").insert({
                            "matter_id": matter_id,
                            "document_id": document_id,
                            "job_type": "DOCUMENT_PROCESSING",
                            "status": "QUEUED",
                            "current_stage": "queued_concurrency_limit",
                        }).execute()
                    except Exception as insert_err:
                        logger.warning(
                            "queued_job_insert_failed",
                            document_id=document_id,
                            error=str(insert_err),
                        )
                    logger.info(
                        "document_queued_concurrency_limit",
                        document_id=document_id,
                        matter_id=matter_id,
                        processing_count=processing_count,
                        limit=settings.max_concurrent_docs_per_matter,
                    )
                    return
        except Exception as e:
            # Fail open: if check fails, dispatch anyway
            logger.warning(
                "concurrency_limit_check_failed",
                document_id=document_id,
                error=str(e),
            )

    # Stage 2.1: All document processing starts in "default" queue.
    # Individual tasks route to llm/heavy queues via task_routes in celery.py.
    queue_name = "default"

    # BUG-4 fix: Use create_post_ocr_chain() factory (single source of truth)
    # instead of hardcoded chain that was missing extract_tables.
    # process_document handles OCR; the factory handles everything after.
    from app.workers.tasks.pipeline_chains import create_post_ocr_chain

    # Need matter_id and job_id for the factory chain.
    # job_id may not exist yet — the factory chain handles this gracefully.
    post_ocr_chain = create_post_ocr_chain(
        document_id=document_id,
        matter_id=matter_id or "",
        job_id="",  # Job created during process_document
    )
    task_chain = chain(
        process_document.s(document_id),
        post_ocr_chain,
    )

    # Apply the chain to the appropriate queue
    task_chain.apply_async(queue=queue_name)

    logger.info(
        "document_processing_chain_queued",
        document_id=document_id,
        queue=queue_name,
        file_size=file_size,
        stages="ocr->validation->confidence->chunking->extract_tables->embedding->entity_extraction->(citations+dates+aliases)",
    )


def _check_zip_bomb(zf: zipfile.ZipFile, compressed_size: int) -> None:
    """Check for ZIP bomb attacks before extraction.

    Args:
        zf: Open ZipFile object.
        compressed_size: Size of the compressed ZIP file.

    Raises:
        HTTPException: If ZIP appears to be a bomb (suspicious compression ratio or size).
    """
    # Calculate total uncompressed size
    total_uncompressed = sum(info.file_size for info in zf.infolist())

    # Check compression ratio (ZIP bombs have extreme ratios like 1000:1 or more)
    if compressed_size > 0:
        compression_ratio = total_uncompressed / compressed_size
        if compression_ratio > ZIP_MAX_COMPRESSION_RATIO:
            logger.warning(
                "zip_bomb_detected_ratio",
                compression_ratio=compression_ratio,
                compressed_size=compressed_size,
                uncompressed_size=total_uncompressed,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "ZIP_BOMB_DETECTED",
                        "message": f"ZIP file has suspicious compression ratio ({compression_ratio:.0f}:1). Maximum allowed is {ZIP_MAX_COMPRESSION_RATIO}:1",
                        "details": {"compression_ratio": compression_ratio},
                    }
                },
            )

    # Check total extracted size
    if total_uncompressed > ZIP_MAX_TOTAL_EXTRACTED_SIZE:
        logger.warning(
            "zip_bomb_detected_size",
            total_uncompressed=total_uncompressed,
            limit=ZIP_MAX_TOTAL_EXTRACTED_SIZE,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "ZIP_TOO_LARGE",
                    "message": f"ZIP extracts to {total_uncompressed // (1024 * 1024)}MB. Maximum allowed is {ZIP_MAX_TOTAL_EXTRACTED_SIZE // (1024 * 1024 * 1024)}GB",
                    "details": {"uncompressed_size": total_uncompressed},
                }
            },
        )

    # Check file count
    file_count = len(zf.namelist())
    if file_count > ZIP_MAX_FILES:
        logger.warning(
            "zip_too_many_files",
            file_count=file_count,
            limit=ZIP_MAX_FILES,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "ZIP_TOO_MANY_FILES",
                    "message": f"ZIP contains {file_count} files. Maximum allowed is {ZIP_MAX_FILES}",
                    "details": {"file_count": file_count},
                }
            },
        )


async def _extract_and_upload_zip(
    zip_content: bytes,
    matter_id: str,
    user_id: str,
    storage_service: StorageService,
    document_service: DocumentService,
    library_service: "LibraryService | None" = None,
    document_type: DocumentType = DocumentType.CASE_FILE,
) -> list[UploadedDocument]:
    """Extract ZIP and upload each PDF individually.

    Includes ZIP bomb protection to prevent DoS attacks via malicious archives.
    Per-file act detection routes statute PDFs to the shared library (GAP-9 Gap 2).

    Args:
        zip_content: ZIP file content as bytes.
        matter_id: Matter UUID.
        user_id: User UUID who uploaded.
        storage_service: Storage service instance.
        document_service: Document service instance.
        library_service: Library service for act routing (optional).
        document_type: Outer document type from user selection (default CASE_FILE).

    Returns:
        List of uploaded documents.

    Raises:
        HTTPException: If extraction fails, ZIP contains no PDFs, or ZIP bomb detected.
    """
    documents: list[UploadedDocument] = []
    uploaded_paths: list[str] = []  # Track storage paths for rollback
    created_doc_ids: list[str] = []  # Track document IDs for rollback

    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            # ZIP bomb protection - check before extracting anything
            _check_zip_bomb(zf, len(zip_content))

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

                # Security: Validate filename against path traversal attacks
                # Reject filenames containing path separators or parent references
                if ".." in filename or "/" in filename or "\\" in filename:
                    logger.warning(
                        "zip_malicious_filename_rejected",
                        matter_id=matter_id,
                        original_path=pdf_path,
                        filename=filename,
                    )
                    continue

                # Per-file act detection (GAP-9 Gap 2):
                # If user explicitly selected 'act', all files go to library.
                # If user selected 'case_file', auto-detect per filename.
                file_is_act = (
                    document_type == DocumentType.ACT
                    or (document_type == DocumentType.CASE_FILE and _detect_act_from_filename(filename))
                )

                if file_is_act and library_service:
                    # Route to shared library — continue on failure
                    try:
                        result = await _upload_act_to_library(
                            file_content=pdf_content,
                            filename=filename,
                            file_size=len(pdf_content),
                            matter_id=matter_id,
                            user_id=user_id,
                            storage_service=storage_service,
                            library_service=library_service,
                        )
                        lib_doc = library_service.get_document(result["library_document_id"])
                        doc = UploadedDocument(
                            document_id=lib_doc.id,
                            filename=lib_doc.filename,
                            storage_path=lib_doc.storage_path,
                            file_size=lib_doc.file_size,
                            document_type=DocumentType.ACT,
                            matter_id=matter_id,
                            ocr_queued=result.get("ocr_queued", False),
                        )
                        documents.append(doc)
                        logger.info(
                            "zip_file_routed_to_library",
                            filename=filename,
                            library_document_id=result["library_document_id"],
                            is_new=result["is_new"],
                            matter_id=matter_id,
                        )
                        continue  # Skip normal upload path
                    except Exception as act_err:
                        logger.warning(
                            "zip_act_upload_failed_continuing_as_case_file",
                            filename=filename,
                            matter_id=matter_id,
                            error=str(act_err),
                        )
                        # Fall through to normal upload as case_file

                # Normal document upload path
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
                _queue_ocr_task(doc.document_id, len(pdf_content), matter_id=matter_id)

            logger.info(
                "zip_extraction_complete",
                matter_id=matter_id,
                documents_created=len(documents),
            )

            return documents

    except zipfile.BadZipFile as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_ZIP",
                    "message": "The uploaded file is not a valid ZIP archive",
                    "details": {},
                }
            },
        ) from err
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

        # Track rollback failures for reporting (H2 fix - don't silently swallow errors)
        rollback_failures: list[dict] = []

        # Delete storage files
        for path in uploaded_paths:
            try:
                storage_service.delete_file(path)
            except Exception as delete_error:
                rollback_failures.append({
                    "type": "storage",
                    "path": path,
                    "error": str(delete_error),
                })
                logger.error(
                    "rollback_storage_delete_failed",
                    storage_path=path,
                    error=str(delete_error),
                )

        # Delete document records
        for doc_id in created_doc_ids:
            try:
                document_service.delete_document(doc_id)
            except Exception as delete_error:
                rollback_failures.append({
                    "type": "document",
                    "document_id": doc_id,
                    "error": str(delete_error),
                })
                logger.error(
                    "rollback_document_delete_failed",
                    document_id=doc_id,
                    error=str(delete_error),
                )

        # Log summary of rollback outcome
        if rollback_failures:
            logger.critical(
                "zip_rollback_incomplete",
                matter_id=matter_id,
                rollback_failures=rollback_failures,
                orphaned_storage_paths=[f["path"] for f in rollback_failures if f["type"] == "storage"],
                orphaned_document_ids=[f["document_id"] for f in rollback_failures if f["type"] == "document"],
            )

        # Include rollback failures in error response for visibility
        error_details: dict = {}
        if rollback_failures:
            error_details["rollback_failures"] = len(rollback_failures)
            error_details["warning"] = "Some resources could not be cleaned up. Contact support if issues persist."

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ZIP_EXTRACTION_FAILED",
                    "message": f"Failed to extract ZIP file: {e!s}",
                    "details": error_details,
                }
            },
        ) from e


@router.post(
    "/upload",
    response_model=DocumentResponse | BulkUploadResponse,
    response_model_by_alias=True,
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
    Uses streaming upload to avoid memory exhaustion with large files (C1 fix).

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

    # Read file content using streaming to avoid memory exhaustion (C1 fix)
    # Small files stay in memory, large files spill to disk via SpooledTemporaryFile
    # Size validation happens during streaming (fail fast if too large)
    file_content, file_size = await _read_file_with_streaming(file)

    logger.info(
        "document_upload_starting",
        matter_id=matter_id,
        user_id=membership.user_id,
        filename=file.filename,
        file_type=file_type,
        file_size=file_size,
        document_type=document_type.value,
    )

    # Auto-detect Act from filename when frontend sends default 'case_file'
    # Safety net: "TORTS Act 1992.pdf" should route to library even if UI didn't classify it
    if document_type == DocumentType.CASE_FILE and _detect_act_from_filename(file.filename or ""):
        logger.info(
            "document_type_auto_detected",
            filename=file.filename,
            original_type=document_type.value,
            detected_type="act",
            matter_id=matter_id,
        )
        document_type = DocumentType.ACT

    try:
        if file_type == "zip":
            # Extract ZIP and upload each PDF (GAP-9 Gap 2: per-file act detection)
            documents = await _extract_and_upload_zip(
                zip_content=file_content,
                matter_id=matter_id,
                user_id=membership.user_id,
                storage_service=storage_service,
                document_service=document_service,
                library_service=get_library_service(),
                document_type=document_type,
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
            # Route Acts to the shared library instead of matter-specific documents
            if document_type == DocumentType.ACT:
                library_service = get_library_service()
                try:
                    result = await _upload_act_to_library(
                        file_content=file_content,
                        filename=file.filename or "document.pdf",
                        file_size=file_size,
                        matter_id=matter_id,
                        user_id=membership.user_id,
                        storage_service=storage_service,
                        library_service=library_service,
                    )

                    logger.info(
                        "act_upload_to_library_complete",
                        library_document_id=result["library_document_id"],
                        matter_id=matter_id,
                        is_new=result["is_new"],
                    )

                    # Return a document-like response for frontend compatibility
                    # Create a minimal Document-like object from library document
                    lib_doc = library_service.get_document(result["library_document_id"])

                    # Return as UploadedDocument to maintain API compatibility
                    uploaded_doc = UploadedDocument(
                        document_id=lib_doc.id,
                        filename=lib_doc.filename,
                        storage_path=lib_doc.storage_path,
                        file_size=lib_doc.file_size,
                        document_type=DocumentType.ACT,
                        matter_id=matter_id,
                        ocr_queued=result.get("ocr_queued", False),
                    )
                    return DocumentResponse(data=uploaded_doc)

                except LibraryServiceError as e:
                    logger.error(
                        "act_library_upload_failed",
                        matter_id=matter_id,
                        error=str(e),
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={
                            "error": {
                                "code": "LIBRARY_UPLOAD_FAILED",
                                "message": f"Failed to upload Act to library: {e.message}",
                                "details": {},
                            }
                        },
                    ) from e

            # Regular document upload (non-Act)
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
                file_size=file_size,
                document_type=document_type,
                uploaded_by=membership.user_id,
            )

            # Queue OCR processing task
            _queue_ocr_task(doc.document_id, file_size, matter_id=matter_id)

            logger.info(
                "document_upload_complete",
                document_id=doc.document_id,
                matter_id=matter_id,
                ocr_queued=True,
            )

            # UX-004: Create activity for document upload
            try:
                from app.models.activity import ActivityTypeEnum
                from app.services.activity_service import get_activity_service
                activity_service = get_activity_service()
                await activity_service.create_activity(
                    user_id=membership.user_id,
                    type=ActivityTypeEnum.DOCUMENT_UPLOADED,
                    description=f"Uploaded document: {file.filename or 'document.pdf'}",
                    matter_id=matter_id,
                    metadata={"document_id": doc.document_id, "file_size": file_size},
                )
            except Exception as activity_err:
                logger.warning("activity_creation_failed_on_upload", error=str(activity_err))

            return DocumentResponse(data=doc)

    except HTTPException:
        raise
    except (StorageError, DocumentServiceError) as e:
        raise _handle_service_error(e) from e
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
        ) from e


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
    filename: str | None = Query(
        None, description="Filter by exact filename match"
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
        # Wrap sync service call in thread to avoid blocking event loop
        documents, meta = await asyncio.to_thread(
            document_service.list_documents,
            matter_id=membership.matter_id,
            page=page,
            per_page=per_page,
            document_type=document_type,
            status=doc_status,
            is_reference_material=is_reference_material,
            sort_by=sort_by,
            sort_order=sort_order,
            filename=filename,
        )

        return DocumentListResponseWithPagination(data=documents, meta=meta)

    except DocumentServiceError as e:
        raise _handle_service_error(e) from e
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
        ) from e


# =============================================================================
# Bulk Operations (must be defined BEFORE /{document_id} to avoid conflict)
# =============================================================================


@router.patch(
    "/bulk",
    response_model=BulkUpdateResponse,
    response_model_by_alias=True,
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
        # Collect doc objects from validation loop for post-write promotion/demotion (GAP-9 Gap 4)
        docs_by_id: dict[str, object] = {}

        # Verify user has EDITOR/OWNER access to all documents' matters
        # by checking each document's matter_id
        matter_ids_checked: set[str] = set()
        for doc_id in update.document_ids:
            try:
                doc = document_service.get_document(doc_id)
                docs_by_id[doc_id] = doc
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

        # Promote to library for documents transitioning to Act (GAP-9 Gap 4)
        # Same pattern as single-doc PATCH — per-doc try/except, log-but-don't-fail
        if update.document_type == DocumentType.ACT:
            library_service = get_library_service()
            from app.workers.tasks.library_tasks import promote_chunks_to_library

            for doc_id, doc in docs_by_id.items():
                if doc.document_type == "act":
                    continue  # Already an act — skip
                try:
                    library_doc_id = library_service.promote_document_to_library(
                        document_id=str(doc_id),
                        matter_id=str(doc.matter_id),
                        user_id=current_user.id,
                    )
                    promote_chunks_to_library.apply_async(
                        kwargs={
                            "library_document_id": library_doc_id,
                            "source_document_id": str(doc_id),
                            "storage_path": doc.storage_path,
                        },
                        queue="default",
                    )
                    logger.info(
                        "bulk_document_promoted_to_library",
                        document_id=str(doc_id),
                        library_document_id=library_doc_id,
                    )
                except Exception as promo_err:
                    logger.error(
                        "bulk_promote_to_library_failed",
                        document_id=str(doc_id),
                        error=str(promo_err),
                    )

        # Demote from library for documents transitioning FROM Act (GAP-9 Gap 5 parity)
        elif update.document_type != DocumentType.ACT:
            for doc_id, doc in docs_by_id.items():
                if doc.document_type != "act":
                    continue  # Wasn't an act — skip
                try:
                    raw_row = document_service.client.table("documents").select(
                        "migrated_to_library, library_document_id"
                    ).eq("id", str(doc_id)).execute()

                    if raw_row.data:
                        row = raw_row.data[0]
                        lib_doc_id = row.get("library_document_id")
                        was_migrated = row.get("migrated_to_library", False)

                        if was_migrated or lib_doc_id:
                            # Clear promotion fields FIRST (hostile-review D2 fix)
                            document_service.client.table("documents").update({
                                "migrated_to_library": False,
                                "library_document_id": None,
                            }).eq("id", str(doc_id)).execute()

                        if was_migrated and lib_doc_id:
                            library_svc = get_library_service()
                            library_svc.unlink_from_matter(
                                matter_id=str(doc.matter_id),
                                library_document_id=lib_doc_id,
                            )

                    logger.info(
                        "bulk_document_demoted_from_library",
                        document_id=str(doc_id),
                    )
                except Exception as demote_err:
                    logger.error(
                        "bulk_demote_from_library_failed",
                        document_id=str(doc_id),
                        error=str(demote_err),
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
        raise _handle_service_error(e) from e
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
        ) from e


# =============================================================================
# Document-scoped endpoints
# =============================================================================


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    response_model_by_alias=True,
)
async def get_document(
    document_id: str = Path(..., description="Document UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    storage_service: StorageService = Depends(get_storage_service),
) -> DocumentDetailResponse:
    """Get document details with signed URL and feature availability.

    Returns full document metadata including a signed URL for file access
    and feature flags indicating which pipeline stages have completed.
    User must have access to the document's matter.
    """
    try:
        # Get document and signed URL in thread to avoid blocking event loop
        doc = await asyncio.to_thread(document_service.get_document, document_id)
        signed_url = await asyncio.to_thread(storage_service.get_signed_url, doc.storage_path, 3600)

        # Query feature availability (Story 7.2)
        features = await _get_document_features(document_id)

        # Create response with signed URL and features
        doc_with_features = DocumentWithFeatures(
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
            features=features,
        )

        return DocumentDetailResponse(data=doc_with_features)

    except DocumentNotFoundError as e:
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
        ) from e
    except DocumentServiceError as e:
        raise _handle_service_error(e) from e
    except StorageError as e:
        raise _handle_service_error(e) from e
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
        ) from e


# =============================================================================
# Document Delete Response Model
# =============================================================================


class DocumentDeleteResponse(BaseModel):
    """Response for document soft-delete operation."""

    data: dict[str, str | bool]


# =============================================================================
# Document Delete Endpoint (Story 10D.4)
# =============================================================================


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    response_model_by_alias=True,
)
async def delete_document(
    document_id: str = Path(..., description="Document UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
) -> DocumentDeleteResponse:
    """Soft-delete a document (30-day retention).

    Sets deleted_at timestamp on the document. The document will be
    permanently deleted after 30 days.

    Requires OWNER or EDITOR role on the matter.
    """
    try:
        # Get document first to get matter_id for access verification
        doc = document_service.get_document(document_id)

        # Verify user has OWNER or EDITOR role on the document's matter
        _verify_matter_access(
            matter_id=doc.matter_id,
            user_id=current_user.id,
            matter_service=matter_service,
            allowed_roles=[MatterRole.OWNER, MatterRole.EDITOR],
        )

        # Perform soft delete
        result = document_service.soft_delete_document(document_id)

        return DocumentDeleteResponse(
            data={
                "success": True,
                "message": "Document will be permanently deleted after 30 days",
                "deleted_at": result["deleted_at"],
            }
        )

    except HTTPException:
        raise
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
    except DocumentServiceError as e:
        raise _handle_service_error(e) from e
    except Exception as e:
        logger.error(
            "document_delete_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "DELETE_FAILED",
                    "message": f"Failed to delete document: {e!s}",
                    "details": {},
                }
            },
        ) from e


@router.patch(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    response_model_by_alias=True,
)
async def update_document(
    document_id: str = Path(..., description="Document UUID"),
    update: DocumentUpdate = ...,
    current_user: AuthenticatedUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    matter_service: MatterService = Depends(get_matter_service),
) -> DocumentDetailResponse:
    """Update document metadata.

    Allows updating document_type, is_reference_material, and filename.
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
            filename=update.filename,
        )

        # Detect transition to Act → promote to shared library
        if (
            update.document_type == DocumentType.ACT
            and doc.document_type != "act"
        ):
            try:
                library_service = get_library_service()
                library_doc_id = library_service.promote_document_to_library(
                    document_id=str(document_id),
                    matter_id=str(doc.matter_id),
                    user_id=current_user.id,
                )

                from app.workers.tasks.library_tasks import promote_chunks_to_library
                promote_chunks_to_library.apply_async(
                    kwargs={
                        "library_document_id": library_doc_id,
                        "source_document_id": str(document_id),
                        "storage_path": doc.storage_path,
                    },
                    queue="default",
                )

                logger.info(
                    "document_promoted_to_library_on_type_change",
                    document_id=str(document_id),
                    library_document_id=library_doc_id,
                    matter_id=str(doc.matter_id),
                )
            except Exception as promo_err:
                # Log but don't fail the PATCH — the type change itself succeeded
                logger.error(
                    "promote_to_library_on_type_change_failed",
                    document_id=str(document_id),
                    error=str(promo_err),
                )

        # Detect transition FROM Act → demote from shared library (GAP-9 Gap 5)
        # Without this, changing type back to case_file leaves migrated_to_library=true,
        # making the document invisible in the documents list (document_service.py:311 filter)
        elif (
            update.document_type is not None
            and update.document_type != DocumentType.ACT
            and doc.document_type == "act"
        ):
            try:
                # Query raw row for library fields not in Document model
                raw_row = document_service.client.table("documents").select(
                    "migrated_to_library, library_document_id"
                ).eq("id", str(document_id)).execute()

                if raw_row.data:
                    row = raw_row.data[0]
                    lib_doc_id = row.get("library_document_id")
                    was_migrated = row.get("migrated_to_library", False)

                    if was_migrated or lib_doc_id:
                        # Clear promotion fields FIRST so document reappears in list
                        # even if the subsequent unlink fails (hostile-review D2 fix)
                        document_service.client.table("documents").update({
                            "migrated_to_library": False,
                            "library_document_id": None,
                        }).eq("id", str(document_id)).execute()

                    if was_migrated and lib_doc_id:
                        # Unlink from matter's library panel (safe if this fails —
                        # document is already visible again in the documents list)
                        library_service = get_library_service()
                        library_service.unlink_from_matter(
                            matter_id=str(doc.matter_id),
                            library_document_id=lib_doc_id,
                        )

                    logger.info(
                        "document_demoted_from_library",
                        document_id=str(document_id),
                        library_document_id=lib_doc_id,
                        matter_id=str(doc.matter_id),
                    )
            except Exception as demote_err:
                # Log but don't fail the PATCH — the type change itself succeeded
                logger.error(
                    "demote_from_library_failed",
                    document_id=str(document_id),
                    error=str(demote_err),
                )

        # Query feature availability (Story 7.2)
        features = await _get_document_features(document_id)

        # Create response with features
        doc_with_features = DocumentWithFeatures(
            id=updated_doc.id,
            matter_id=updated_doc.matter_id,
            filename=updated_doc.filename,
            storage_path=updated_doc.storage_path,
            file_size=updated_doc.file_size,
            page_count=updated_doc.page_count,
            document_type=updated_doc.document_type,
            is_reference_material=updated_doc.is_reference_material,
            uploaded_by=updated_doc.uploaded_by,
            uploaded_at=updated_doc.uploaded_at,
            status=updated_doc.status,
            processing_started_at=updated_doc.processing_started_at,
            processing_completed_at=updated_doc.processing_completed_at,
            extracted_text=updated_doc.extracted_text,
            ocr_confidence=updated_doc.ocr_confidence,
            ocr_quality_score=updated_doc.ocr_quality_score,
            ocr_confidence_per_page=updated_doc.ocr_confidence_per_page,
            ocr_quality_status=updated_doc.ocr_quality_status,
            ocr_error=updated_doc.ocr_error,
            created_at=updated_doc.created_at,
            updated_at=updated_doc.updated_at,
            features=features,
        )

        return DocumentDetailResponse(data=doc_with_features)

    except HTTPException:
        raise
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
    except DocumentServiceError as e:
        raise _handle_service_error(e) from e
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
        ) from e


@router.get(
    "/{document_id}/ocr-quality",
    response_model=OCRQualityResponse,
    response_model_by_alias=True,
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
        ) from e
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
        ) from e


@router.post(
    "/{document_id}/request-manual-review",
    response_model=ManualReviewResponse,
    response_model_by_alias=True,
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
        ) from e
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
        ) from e


# =============================================================================
# Document Retry/Reprocess Endpoints
# =============================================================================


class RetryResponse(BaseModel):
    """Response model for retry operations."""

    success: bool = Field(..., description="Whether retry was initiated")
    document_id: str = Field(..., description="Document ID")
    task_id: str | None = Field(None, description="Celery task ID")
    message: str = Field(..., description="Status message")
    retry_type: str = Field(..., description="Type of retry: full_ocr or rag_only")


@matters_router.post(
    "/{matter_id}/documents/{document_id}/retry",
    response_model=dict[str, RetryResponse],
)
async def retry_document_processing(
    document_id: str = Path(..., description="Document UUID to retry"),
    retry_type: str = Query(
        "auto",
        description="Retry type: 'full' (full OCR), 'rag' (RAG only), 'auto' (detect)",
    ),
    membership: MatterMembership = Depends(require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])),
    doc_service: DocumentService = Depends(get_document_service),
) -> dict[str, RetryResponse]:
    """Retry processing for a stuck or failed document.

    This endpoint allows users to retry document processing without re-uploading.
    It can retry the full OCR pipeline or just the RAG pipeline based on document state.

    Args:
        document_id: The document UUID to retry.
        retry_type: Type of retry:
            - 'full': Full OCR pipeline (process_document -> validate_ocr -> etc)
            - 'rag': RAG only (chunk_document -> embed_chunks -> etc)
            - 'auto': Automatically detect based on document status

    Returns:
        RetryResponse with task details.

    Raises:
        404: Document not found.
        400: Document cannot be retried (e.g., already processing).
    """
    matter_id = membership.matter_id

    try:
        # Get document (in thread to avoid blocking event loop)
        doc = await asyncio.to_thread(doc_service.get_document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "DOCUMENT_NOT_FOUND",
                        "message": "Document not found",
                        "details": {},
                    }
                },
            )

        # Verify document belongs to this matter
        if str(doc.matter_id) != matter_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "DOCUMENT_NOT_FOUND",
                        "message": "Document not found in this matter",
                        "details": {},
                    }
                },
            )

        # Determine retry type
        actual_retry_type = retry_type
        if retry_type == "auto":
            # Statuses where OCR already succeeded → RAG-only retry
            rag_only_statuses = ["ocr_complete", "chunking_failed", "embedding_failed", "searchable"]
            if doc.status.value in rag_only_statuses or doc.status.value in ["ocr_failed", "failed"] and doc.extracted_text:
                actual_retry_type = "rag"
            else:
                actual_retry_type = "full"

        # Reset or create processing_job so _mark_job_completed can fire
        from app.services.supabase.client import get_service_client as get_supa_client
        job_id: str | None = None
        try:
            supa = get_supa_client()
            if supa:
                def _reset_or_create_job() -> str | None:
                    """Reset failed job or create new one (sync Supabase calls)."""
                    existing = (
                        supa.table("processing_jobs")
                        .select("id")
                        .eq("document_id", document_id)
                        .in_("status", ["FAILED", "CANCELLED"])
                        .order("created_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                    if existing.data:
                        jid = existing.data[0]["id"]
                        supa.table("processing_jobs").update({
                            "status": "PROCESSING",
                            "current_stage": "retry_started",
                            "error_message": None,
                        }).eq("id", jid).execute()
                        return jid
                    else:
                        new_job = supa.table("processing_jobs").insert({
                            "matter_id": matter_id,
                            "document_id": document_id,
                            "job_type": "DOCUMENT_PROCESSING",
                            "status": "PROCESSING",
                            "current_stage": "retry_started",
                        }).execute()
                        if new_job.data:
                            return new_job.data[0]["id"]
                    return None

                job_id = await asyncio.to_thread(_reset_or_create_job)
                if job_id:
                    logger.info("retry_job_tracking_setup", job_id=job_id, document_id=document_id)
        except Exception as job_err:
            logger.warning("retry_job_tracking_setup_failed", error=str(job_err), document_id=document_id)

        # Build and dispatch task chain
        from app.workers.tasks.pipeline_chains import create_post_ocr_chain

        if actual_retry_type == "full":
            # Full OCR pipeline — use factory chain for post-OCR consistency (BUG-4 fix)
            post_ocr = create_post_ocr_chain(
                document_id=document_id,
                matter_id=matter_id,
                job_id=job_id,
            )
            task_chain = chain(
                process_document.s(document_id),
                post_ocr,
            )
            message = "Full OCR + RAG pipeline queued (entities fan out to citations, dates, aliases)"
        else:
            # RAG only — use unified chain (single source of truth)
            task_chain = create_post_ocr_chain(
                document_id=document_id,
                matter_id=matter_id,
                job_id=job_id,
            )
            message = "RAG pipeline queued (validate → chunk → embed → entities → citations+dates+aliases)"

        # Apply the chain
        result = task_chain.apply_async()

        logger.info(
            "document_retry_initiated",
            document_id=document_id,
            matter_id=matter_id,
            retry_type=actual_retry_type,
            task_id=result.id,
            user_id=membership.user_id,
        )

        return {
            "data": RetryResponse(
                success=True,
                document_id=document_id,
                task_id=result.id,
                message=message,
                retry_type=actual_retry_type,
            )
        }

    except HTTPException:
        raise
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": str(e),
                    "details": {},
                }
            },
        ) from e
    except Exception as e:
        logger.error(
            "document_retry_failed",
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RETRY_FAILED",
                    "message": f"Failed to retry document: {e!s}",
                    "details": {},
                }
            },
        ) from e


@matters_router.post(
    "/{matter_id}/documents/retry-all-stuck",
    response_model=dict[str, Any],
)
async def retry_all_stuck_documents(
    membership: MatterMembership = Depends(require_matter_role([MatterRole.OWNER, MatterRole.EDITOR])),
    doc_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """Retry all stuck documents in a matter.

    Finds documents that are stuck (OCR complete but RAG not done, or failed)
    and queues them for reprocessing.

    Returns:
        Summary of retry operations.
    """
    from app.services.supabase.client import get_supabase_client

    matter_id = membership.matter_id

    try:
        client = get_supabase_client()

        # Run all sync Supabase queries in a thread to avoid blocking event loop
        def _find_and_retry_stuck() -> dict:
            stuck_statuses = ["ocr_complete", "failed", "ocr_failed", "chunking_failed", "embedding_failed"]
            docs_response = (
                client.table("documents")
                .select("id, filename, status, extracted_text")
                .eq("matter_id", matter_id)
                .in_("status", stuck_statuses)
                .execute()
            )

            documents = docs_response.data or []
            results = {
                "total_checked": len(documents),
                "retried": 0,
                "skipped": 0,
                "errors": [],
            }

            for doc in documents:
                doc_id = doc["id"]
                doc_status = doc.get("status", "")
                has_text = bool(doc.get("extracted_text"))

                needs_full_ocr = doc_status in ["failed", "ocr_failed"] and not has_text

                if needs_full_ocr:
                    try:
                        task_chain = chain(
                            process_document.s(doc_id),
                            validate_ocr.s(),
                            calculate_confidence.s(),
                            chunk_document.s(),
                            embed_chunks.s(),
                            extract_entities.s(),
                        )
                        task_chain.apply_async()
                        results["retried"] += 1
                        logger.info("stuck_document_full_retry_queued", document_id=doc_id, matter_id=matter_id)
                    except Exception as e:
                        results["errors"].append({"document_id": doc_id, "error": str(e)})
                    continue

                if not has_text:
                    results["skipped"] += 1
                    continue

                chunks_response = (
                    client.table("chunks")
                    .select("id", count="exact")
                    .eq("document_id", doc_id)
                    .limit(1)
                    .execute()
                )
                has_chunks = (chunks_response.count or 0) > 0

                if has_chunks and doc_status == "ocr_complete":
                    results["skipped"] += 1
                    continue

                try:
                    task_chain = chain(
                        chunk_document.s({"document_id": doc_id}),
                        embed_chunks.s(),
                        extract_entities.s(),
                    )
                    task_chain.apply_async()
                    results["retried"] += 1
                    logger.info("stuck_document_rag_retry_queued", document_id=doc_id, matter_id=matter_id)
                except Exception as e:
                    results["errors"].append({"document_id": doc_id, "error": str(e)})

            return results

        results = await asyncio.to_thread(_find_and_retry_stuck)

        logger.info(
            "retry_all_stuck_completed",
            matter_id=matter_id,
            total=results["total_checked"],
            retried=results["retried"],
            skipped=results["skipped"],
            errors=len(results["errors"]),
        )

        return {"data": results}

    except Exception as e:
        logger.error(
            "retry_all_stuck_failed",
            matter_id=matter_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RETRY_ALL_FAILED",
                    "message": f"Failed to retry stuck documents: {e!s}",
                    "details": {},
                }
            },
        ) from e
