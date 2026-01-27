"""Document service for database operations.

Handles document record creation and management in the documents table.
Works with StorageService for file operations.
"""

from datetime import UTC, datetime
from functools import lru_cache

import structlog
from supabase import Client

from app.models.document import (
    Document,
    DocumentListItem,
    DocumentSource,
    DocumentStatus,
    DocumentType,
    PaginationMeta,
    UploadedDocument,
)
from app.services.supabase.client import get_supabase_client
from app.services.storage_service import get_storage_service, StorageError
from app.engines.citation.abbreviations import normalize_act_name

logger = structlog.get_logger(__name__)

# =============================================================================
# SELECT Field Constants
# =============================================================================
# IMPORTANT: These constants define which fields are selected from the database.
# When adding new fields to DocumentListItem or Document models, you MUST also
# add them here. The field mapping in list_documents() and get_document() must
# stay in sync with these SELECT strings.
#
# Checklist when adding a new field:
# 1. Add column to database migration
# 2. Add field to Pydantic model (DocumentListItem, Document, etc.)
# 3. Add column name to the appropriate SELECT constant below
# 4. Add field mapping in the list comprehension (doc["field_name"])
# 5. Update frontend types if needed
# =============================================================================

# Fields for DocumentListItem (list views) - must match DocumentListItem model
DOCUMENT_LIST_SELECT_FIELDS = (
    "id, matter_id, filename, file_size, page_count, document_type, "
    "is_reference_material, source, status, uploaded_at, uploaded_by, "
    "ocr_confidence, ocr_quality_status"
)


class DocumentServiceError(Exception):
    """Base exception for document service operations."""

    def __init__(self, message: str, code: str = "DOCUMENT_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a document is not found."""

    def __init__(self, document_id: str):
        super().__init__(
            message=f"Document not found: {document_id}",
            code="DOCUMENT_NOT_FOUND",
            status_code=404
        )


class DocumentService:
    """Service for document database operations.

    Uses the regular Supabase client which applies RLS policies.
    Authorization is handled by the API layer via require_matter_role.
    """

    def __init__(self, client: Client | None = None):
        """Initialize document service.

        Args:
            client: Optional Supabase client. Uses default client if not provided.
        """
        self.client = client or get_supabase_client()

    def create_document(
        self,
        matter_id: str,
        filename: str,
        storage_path: str,
        file_size: int,
        document_type: DocumentType,
        uploaded_by: str,
        is_reference_material: bool | None = None,
    ) -> UploadedDocument:
        """Create a new document record in the database.

        Args:
            matter_id: Matter UUID this document belongs to.
            filename: Original filename.
            storage_path: Supabase Storage path.
            file_size: File size in bytes.
            document_type: Document classification type.
            uploaded_by: User UUID who uploaded the document.
            is_reference_material: Whether this is reference material.
                                   Defaults to True for ACT type, False otherwise.

        Returns:
            Created document record.

        Raises:
            DocumentServiceError: If creation fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        # Determine is_reference_material based on document type if not provided
        if is_reference_material is None:
            is_reference_material = document_type == DocumentType.ACT

        logger.info(
            "document_create_starting",
            matter_id=matter_id,
            filename=filename,
            document_type=document_type.value,
            file_size=file_size,
        )

        try:
            # Insert document record
            result = self.client.table("documents").insert({
                "matter_id": matter_id,
                "filename": filename,
                "storage_path": storage_path,
                "file_size": file_size,
                "document_type": document_type.value,
                "is_reference_material": is_reference_material,
                "uploaded_by": uploaded_by,
                "status": DocumentStatus.PENDING.value,
            }).execute()

            if not result.data:
                raise DocumentServiceError(
                    message="Failed to create document record",
                    code="INSERT_FAILED"
                )

            doc_data = result.data[0]

            logger.info(
                "document_create_complete",
                document_id=doc_data["id"],
                matter_id=matter_id,
                filename=filename,
            )

            return UploadedDocument(
                document_id=doc_data["id"],
                filename=doc_data["filename"],
                storage_path=doc_data["storage_path"],
                file_size=doc_data["file_size"],
                document_type=DocumentType(doc_data["document_type"]),
                status=DocumentStatus(doc_data["status"]),
            )

        except DocumentServiceError:
            raise
        except Exception as e:
            logger.error(
                "document_create_failed",
                matter_id=matter_id,
                filename=filename,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to create document: {e!s}",
                code="CREATE_FAILED"
            ) from e

    def get_document(self, document_id: str) -> Document:
        """Get a document by ID.

        Args:
            document_id: Document UUID.

        Returns:
            Document record including OCR fields if available.

        Raises:
            DocumentNotFoundError: If document doesn't exist.
            DocumentServiceError: If query fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            result = self.client.table("documents").select("*").eq(
                "id", document_id
            ).execute()

            if not result.data:
                raise DocumentNotFoundError(document_id)

            return self._parse_document(result.data[0])

        except DocumentNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "document_get_failed",
                document_id=document_id,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to get document: {e!s}",
                code="GET_FAILED"
            ) from e

    def get_documents_by_matter(self, matter_id: str) -> list[Document]:
        """Get all documents for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            List of documents.

        Raises:
            DocumentServiceError: If query fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            result = self.client.table("documents").select("*").eq(
                "matter_id", matter_id
            ).order("created_at", desc=True).execute()

            return [self._to_document(doc) for doc in result.data]

        except Exception as e:
            logger.error(
                "documents_list_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to list documents: {e!s}",
                code="LIST_FAILED"
            ) from e

    def list_documents(
        self,
        matter_id: str,
        page: int = 1,
        per_page: int = 20,
        document_type: DocumentType | None = None,
        status: str | None = None,
        is_reference_material: bool | None = None,
        sort_by: str = "uploaded_at",
        sort_order: str = "desc",
    ) -> tuple[list[DocumentListItem], PaginationMeta]:
        """List documents for a matter with pagination, filtering, and sorting.

        Args:
            matter_id: Matter UUID.
            page: Page number (1-indexed).
            per_page: Items per page (max 100).
            document_type: Optional filter by document type.
            status: Optional filter by processing status.
            is_reference_material: Optional filter by reference material flag.
            sort_by: Column to sort by (uploaded_at, filename, file_size, document_type, status).
            sort_order: Sort direction ('asc' or 'desc').

        Returns:
            Tuple of (documents list, pagination metadata).

        Raises:
            DocumentServiceError: If query fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            # Build query with filters
            # Note: Service role key bypasses RLS, so we must explicitly filter soft-deleted documents
            # IMPORTANT: Use DOCUMENT_LIST_SELECT_FIELDS constant to ensure SELECT stays in sync with model
            query = self.client.table("documents").select(
                DOCUMENT_LIST_SELECT_FIELDS,
                count="exact"
            ).eq("matter_id", matter_id).is_("deleted_at", "null")

            # Exclude documents migrated to library (Acts show in LinkedLibraryPanel instead)
            # Filter: migrated_to_library IS NULL OR migrated_to_library = FALSE
            query = query.or_("migrated_to_library.is.null,migrated_to_library.eq.false")

            # Apply optional filters
            if document_type is not None:
                query = query.eq("document_type", document_type.value)
            if status is not None:
                query = query.eq("status", status)
            if is_reference_material is not None:
                query = query.eq("is_reference_material", is_reference_material)

            # Calculate offset for pagination
            offset = (page - 1) * per_page

            # Validate sort column to prevent injection
            allowed_sort_columns = {"uploaded_at", "filename", "file_size", "document_type", "status"}
            if sort_by not in allowed_sort_columns:
                sort_by = "uploaded_at"

            # Execute with pagination and sorting
            result = query.order(
                sort_by, desc=(sort_order.lower() == "desc")
            ).range(offset, offset + per_page - 1).execute()

            total = result.count or 0
            total_pages = (total + per_page - 1) // per_page if total > 0 else 0

            # IMPORTANT: Field mapping must match DOCUMENT_LIST_SELECT_FIELDS
            # If you add a field, add it to both the SELECT constant AND here
            documents = [
                DocumentListItem(
                    id=doc["id"],
                    matter_id=doc["matter_id"],
                    filename=doc["filename"],
                    file_size=doc["file_size"],
                    page_count=doc.get("page_count"),
                    document_type=DocumentType(doc["document_type"]),
                    is_reference_material=doc["is_reference_material"],
                    source=DocumentSource(doc.get("source", "user_upload")),
                    status=DocumentStatus(doc["status"]),
                    uploaded_at=datetime.fromisoformat(
                        doc["uploaded_at"].replace("Z", "+00:00")
                    ),
                    uploaded_by=doc.get("uploaded_by"),
                    ocr_confidence=doc.get("ocr_confidence"),
                    ocr_quality_status=doc.get("ocr_quality_status"),
                )
                for doc in result.data
            ]

            meta = PaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            )

            logger.info(
                "documents_list_success",
                matter_id=matter_id,
                total=total,
                page=page,
                returned=len(documents),
            )

            return documents, meta

        except Exception as e:
            logger.error(
                "documents_list_paginated_failed",
                matter_id=matter_id,
                page=page,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to list documents: {e!s}",
                code="LIST_FAILED"
            ) from e

    def update_document(
        self,
        document_id: str,
        document_type: DocumentType | None = None,
        is_reference_material: bool | None = None,
        filename: str | None = None,
    ) -> Document:
        """Update document metadata.

        Args:
            document_id: Document UUID.
            document_type: New document type (if provided).
            is_reference_material: Override reference material flag.
                                   If not provided and document_type is 'act',
                                   automatically set to True.
            filename: New filename (if provided).

        Returns:
            Updated document.

        Raises:
            DocumentNotFoundError: If document doesn't exist.
            DocumentServiceError: If update fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        # First verify document exists
        existing = self.get_document(document_id)

        # Build update data
        update_data: dict[str, str | bool] = {}

        if document_type is not None:
            update_data["document_type"] = document_type.value
            # Auto-set is_reference_material for acts unless explicitly overridden
            if is_reference_material is None:
                update_data["is_reference_material"] = document_type == DocumentType.ACT

        if is_reference_material is not None:
            update_data["is_reference_material"] = is_reference_material

        if filename is not None:
            update_data["filename"] = filename

        if not update_data:
            # Nothing to update
            return existing

        try:
            result = self.client.table("documents").update(
                update_data
            ).eq("id", document_id).execute()

            if not result.data:
                raise DocumentServiceError(
                    message="Failed to update document",
                    code="UPDATE_FAILED"
                )

            doc_data = result.data[0]

            logger.info(
                "document_update_success",
                document_id=document_id,
                updated_fields=list(update_data.keys()),
            )

            return self._to_document(doc_data)

        except DocumentNotFoundError:
            raise
        except DocumentServiceError:
            raise
        except Exception as e:
            logger.error(
                "document_update_failed",
                document_id=document_id,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to update document: {e!s}",
                code="UPDATE_FAILED"
            ) from e

    def bulk_update_documents(
        self,
        document_ids: list[str],
        document_type: DocumentType,
    ) -> int:
        """Bulk update document types.

        Args:
            document_ids: List of document UUIDs to update.
            document_type: Document type to assign.

        Returns:
            Number of documents updated.

        Raises:
            DocumentServiceError: If update fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        # Auto-set is_reference_material for acts
        is_reference_material = document_type == DocumentType.ACT

        try:
            result = self.client.table("documents").update({
                "document_type": document_type.value,
                "is_reference_material": is_reference_material,
            }).in_("id", document_ids).execute()

            updated_count = len(result.data) if result.data else 0

            logger.info(
                "documents_bulk_update_success",
                document_ids=document_ids,
                document_type=document_type.value,
                updated_count=updated_count,
            )

            return updated_count

        except Exception as e:
            logger.error(
                "documents_bulk_update_failed",
                document_ids=document_ids,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to bulk update documents: {e!s}",
                code="BULK_UPDATE_FAILED"
            ) from e

    def delete_document(self, document_id: str, cleanup_storage: bool = True) -> bool:
        """Delete a document record and optionally its storage file.

        Args:
            document_id: Document UUID.
            cleanup_storage: If True, also delete the storage file (default: True).

        Returns:
            True if deleted successfully.

        Raises:
            DocumentNotFoundError: If document doesn't exist.
            DocumentServiceError: If deletion fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            # First fetch document to get storage_path
            result = self.client.table("documents").select("id, storage_path").eq(
                "id", document_id
            ).execute()

            if not result.data:
                raise DocumentNotFoundError(document_id)

            storage_path = result.data[0].get("storage_path")

            # Delete the document from database
            self.client.table("documents").delete().eq(
                "id", document_id
            ).execute()

            logger.info("document_deleted", document_id=document_id)

            # Clean up storage file if requested
            if cleanup_storage and storage_path:
                try:
                    storage_service = get_storage_service()
                    storage_service.delete_file(storage_path)
                    logger.info(
                        "document_storage_deleted",
                        document_id=document_id,
                        storage_path=storage_path,
                    )
                except StorageError as e:
                    # Log but don't fail - DB record is already deleted
                    logger.warning(
                        "document_storage_delete_failed",
                        document_id=document_id,
                        storage_path=storage_path,
                        error=str(e),
                    )

            return True

        except DocumentNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "document_delete_failed",
                document_id=document_id,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to delete document: {e!s}",
                code="DELETE_FAILED"
            ) from e

    def soft_delete_document(self, document_id: str) -> dict:
        """Soft delete a document by setting deleted_at timestamp.

        Documents are retained for 30 days before permanent deletion.
        Also invalidates the matter's summary cache.

        Args:
            document_id: Document UUID.

        Returns:
            Dict with deleted_at timestamp and matter_id.

        Raises:
            DocumentNotFoundError: If document doesn't exist.
            DocumentServiceError: If soft delete fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            # First verify document exists and get matter_id for cache invalidation
            result = self.client.table("documents").select("id, matter_id").eq(
                "id", document_id
            ).execute()

            if not result.data:
                raise DocumentNotFoundError(document_id)

            matter_id = result.data[0].get("matter_id")

            # Set deleted_at timestamp
            deleted_at = datetime.now(UTC)
            update_result = self.client.table("documents").update({
                "deleted_at": deleted_at.isoformat(),
            }).eq("id", document_id).execute()

            if not update_result.data:
                raise DocumentServiceError(
                    message="Failed to soft delete document",
                    code="SOFT_DELETE_FAILED"
                )

            # Cascade cleanup: delete related data to prevent orphaned records
            cleanup_result = self.cascade_soft_delete_related_data(document_id)

            # Invalidate summary cache for the matter
            if matter_id:
                self._invalidate_summary_cache(matter_id)

            logger.info(
                "document_soft_deleted",
                document_id=document_id,
                matter_id=matter_id,
                deleted_at=deleted_at.isoformat(),
                cleanup=cleanup_result,
            )

            return {
                "deleted_at": deleted_at.isoformat(),
                "document_id": document_id,
                "matter_id": matter_id,
                "cleanup": cleanup_result,
            }

        except DocumentNotFoundError:
            raise
        except DocumentServiceError:
            raise
        except Exception as e:
            logger.error(
                "document_soft_delete_failed",
                document_id=document_id,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to soft delete document: {e!s}",
                code="SOFT_DELETE_FAILED"
            ) from e

    def _invalidate_summary_cache(self, matter_id: str) -> None:
        """Invalidate the summary cache for a matter.

        Args:
            matter_id: Matter UUID.
        """
        try:
            import asyncio
            from app.services.summary_service import get_summary_service

            # Run async cache invalidation in sync context
            loop = asyncio.new_event_loop()
            try:
                summary_service = get_summary_service()
                loop.run_until_complete(summary_service.invalidate_cache(matter_id))
                logger.info(
                    "summary_cache_invalidated_on_delete",
                    matter_id=matter_id,
                )
            finally:
                loop.close()
        except Exception as e:
            # Don't fail the delete operation if cache invalidation fails
            logger.warning(
                "summary_cache_invalidation_failed",
                matter_id=matter_id,
                error=str(e),
            )

    def cascade_soft_delete_related_data(self, document_id: str) -> dict:
        """Soft-delete or clean up data related to a soft-deleted document.

        This method handles orphaned data that would otherwise still appear
        in queries. It marks related records for cleanup.

        Args:
            document_id: Document UUID that was soft-deleted.

        Returns:
            Dict with counts of affected records per table.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        affected = {
            "chunks_deleted": 0,
            "citations_deleted": 0,
            "events_nullified": 0,
        }

        try:
            # Delete chunks (they have ON DELETE CASCADE, but for soft-delete
            # we need to manually remove them to prevent orphaned embeddings)
            chunks_result = self.client.table("chunks").delete().eq(
                "document_id", document_id
            ).execute()
            affected["chunks_deleted"] = len(chunks_result.data) if chunks_result.data else 0

            # Delete citations from this document
            citations_result = self.client.table("citations").delete().eq(
                "source_document_id", document_id
            ).execute()
            affected["citations_deleted"] = len(citations_result.data) if citations_result.data else 0

            # Nullify document_id on events (matches ON DELETE SET NULL behavior)
            events_result = self.client.table("events").update({
                "document_id": None
            }).eq("document_id", document_id).execute()
            affected["events_nullified"] = len(events_result.data) if events_result.data else 0

            logger.info(
                "cascade_soft_delete_completed",
                document_id=document_id,
                **affected,
            )

            return affected

        except Exception as e:
            logger.error(
                "cascade_soft_delete_failed",
                document_id=document_id,
                error=str(e),
            )
            # Don't raise - this is a cleanup operation
            return affected

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse datetime string from database.

        Args:
            value: ISO format datetime string or None.

        Returns:
            Parsed datetime or None.
        """
        if value is None:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _parse_document(self, doc_data: dict) -> Document:
        """Parse a document record from database row.

        Args:
            doc_data: Dictionary from database query.

        Returns:
            Document model instance.
        """
        # Handle source field with default for backward compatibility
        source_str = doc_data.get("source", "user_upload")
        try:
            source = DocumentSource(source_str)
        except ValueError:
            source = DocumentSource.USER_UPLOAD

        return Document(
            id=doc_data["id"],
            matter_id=doc_data["matter_id"],
            filename=doc_data["filename"],
            storage_path=doc_data["storage_path"],
            file_size=doc_data["file_size"],
            page_count=doc_data.get("page_count"),
            document_type=DocumentType(doc_data["document_type"]),
            is_reference_material=doc_data["is_reference_material"],
            source=source,
            uploaded_by=doc_data.get("uploaded_by"),
            uploaded_at=datetime.fromisoformat(
                doc_data["uploaded_at"].replace("Z", "+00:00")
            ),
            india_code_url=doc_data.get("india_code_url"),
            status=DocumentStatus(doc_data["status"]),
            processing_started_at=self._parse_datetime(
                doc_data.get("processing_started_at")
            ),
            processing_completed_at=self._parse_datetime(
                doc_data.get("processing_completed_at")
            ),
            extracted_text=doc_data.get("extracted_text"),
            ocr_confidence=doc_data.get("ocr_confidence"),
            ocr_quality_score=doc_data.get("ocr_quality_score"),
            ocr_confidence_per_page=doc_data.get("ocr_confidence_per_page"),
            ocr_quality_status=doc_data.get("ocr_quality_status"),
            ocr_error=doc_data.get("ocr_error"),
            created_at=datetime.fromisoformat(
                doc_data["created_at"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                doc_data["updated_at"].replace("Z", "+00:00")
            ),
        )

    def update_ocr_status(
        self,
        document_id: str,
        status: DocumentStatus,
        extracted_text: str | None = None,
        page_count: int | None = None,
        ocr_confidence: float | None = None,
        ocr_quality_score: float | None = None,
        ocr_error: str | None = None,
    ) -> None:
        """Update document OCR processing status and results.

        Used by Celery tasks to update document after OCR processing.

        Args:
            document_id: Document UUID.
            status: New document status.
            extracted_text: Full extracted text content.
            page_count: Number of pages in document.
            ocr_confidence: Average OCR confidence score (0-1).
            ocr_quality_score: Document AI image quality score (0-1).
            ocr_error: Error message if processing failed.

        Raises:
            DocumentServiceError: If update fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        update_data: dict[str, str | int | float | None] = {
            "status": status.value,
        }

        # Set processing timestamps based on status
        now = datetime.now(UTC).isoformat()
        if status == DocumentStatus.PROCESSING:
            update_data["processing_started_at"] = now
        elif status in (DocumentStatus.OCR_COMPLETE, DocumentStatus.OCR_FAILED):
            update_data["processing_completed_at"] = now

        # Add OCR results if provided
        if extracted_text is not None:
            update_data["extracted_text"] = extracted_text
        if page_count is not None:
            update_data["page_count"] = page_count
        if ocr_confidence is not None:
            update_data["ocr_confidence"] = ocr_confidence
        if ocr_quality_score is not None:
            update_data["ocr_quality_score"] = ocr_quality_score
        if ocr_error is not None:
            update_data["ocr_error"] = ocr_error

        try:
            result = self.client.table("documents").update(
                update_data
            ).eq("id", document_id).execute()

            if not result.data:
                logger.warning(
                    "document_ocr_status_update_no_rows",
                    document_id=document_id,
                    status=status.value,
                )
                return

            logger.info(
                "document_ocr_status_updated",
                document_id=document_id,
                status=status.value,
                page_count=page_count,
                ocr_confidence=ocr_confidence,
            )

        except Exception as e:
            logger.error(
                "document_ocr_status_update_failed",
                document_id=document_id,
                status=status.value,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to update OCR status: {e!s}",
                code="OCR_STATUS_UPDATE_FAILED"
            ) from e

    def update_injection_scan(
        self,
        document_id: str,
        injection_risk: str,
        scan_result: dict | None = None,
    ) -> None:
        """Update document with injection scan results.

        Story 1.2: Add LLM Detection for Suspicious Documents

        Args:
            document_id: Document UUID.
            injection_risk: Risk level ('none', 'low', 'medium', 'high').
            scan_result: Detailed scan results (patterns found, confidence, etc.).

        Raises:
            DocumentServiceError: If update fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        update_data: dict = {
            "injection_risk": injection_risk,
        }

        if scan_result is not None:
            update_data["injection_scan_result"] = scan_result

        try:
            result = self.client.table("documents").update(
                update_data
            ).eq("id", document_id).execute()

            if not result.data:
                logger.warning(
                    "document_injection_scan_update_no_rows",
                    document_id=document_id,
                    injection_risk=injection_risk,
                )
                return

            logger.info(
                "document_injection_scan_updated",
                document_id=document_id,
                injection_risk=injection_risk,
                requires_review=injection_risk == "high",
            )

        except Exception as e:
            logger.error(
                "document_injection_scan_update_failed",
                document_id=document_id,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to update injection scan: {e!s}",
                code="INJECTION_SCAN_UPDATE_FAILED"
            ) from e

    def increment_ocr_retry_count(self, document_id: str) -> int:
        """Increment OCR retry count for a document.

        Args:
            document_id: Document UUID.

        Returns:
            New retry count.

        Raises:
            DocumentServiceError: If update fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            # Get current retry count
            result = self.client.table("documents").select(
                "ocr_retry_count"
            ).eq("id", document_id).execute()

            current_count = 0
            if result.data:
                current_count = result.data[0].get("ocr_retry_count") or 0

            new_count = current_count + 1

            # Update retry count
            self.client.table("documents").update({
                "ocr_retry_count": new_count,
            }).eq("id", document_id).execute()

            logger.info(
                "document_ocr_retry_incremented",
                document_id=document_id,
                retry_count=new_count,
            )

            return new_count

        except Exception as e:
            logger.error(
                "document_ocr_retry_increment_failed",
                document_id=document_id,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to increment retry count: {e!s}",
                code="RETRY_INCREMENT_FAILED"
            ) from e

    def get_document_for_processing(self, document_id: str) -> tuple[str, str]:
        """Get document storage path and matter_id for OCR processing.

        Args:
            document_id: Document UUID.

        Returns:
            Tuple of (storage_path, matter_id).

        Raises:
            DocumentNotFoundError: If document doesn't exist.
            DocumentServiceError: If query fails.
        """
        if self.client is None:
            raise DocumentServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            result = self.client.table("documents").select(
                "storage_path, matter_id"
            ).eq("id", document_id).execute()

            if not result.data:
                raise DocumentNotFoundError(document_id)

            doc_data = result.data[0]
            return doc_data["storage_path"], doc_data["matter_id"]

        except DocumentNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "document_get_for_processing_failed",
                document_id=document_id,
                error=str(e),
            )
            raise DocumentServiceError(
                message=f"Failed to get document for processing: {e!s}",
                code="GET_FOR_PROCESSING_FAILED"
            ) from e

    def get_pending_documents_for_matter(self, matter_id: str) -> list[dict]:
        """Get pending documents with page counts for ETA calculation.

        Story 5.7: Processing ETA Display

        Args:
            matter_id: Matter UUID.

        Returns:
            List of dicts with {"id": str, "page_count": int, "status": str}
            for documents that are queued or processing.
        """
        if self.client is None:
            logger.warning("get_pending_documents_no_client")
            return []

        try:
            # Get documents that are still processing
            pending_statuses = [
                DocumentStatus.UPLOADED.value,
                DocumentStatus.QUEUED.value,
                DocumentStatus.PROCESSING.value,
                DocumentStatus.OCR_PENDING.value,
                DocumentStatus.OCR_PROCESSING.value,
            ]

            result = self.client.table("documents").select(
                "id, page_count, status"
            ).eq("matter_id", matter_id).in_("status", pending_statuses).execute()

            if not result.data:
                return []

            return [
                {
                    "id": doc["id"],
                    "page_count": doc.get("page_count") or 1,  # Default to 1 if unknown
                    "status": doc["status"],
                }
                for doc in result.data
            ]

        except Exception as e:
            logger.warning(
                "get_pending_documents_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return []

    def sync_act_resolutions_for_matter(self, matter_id: str) -> int:
        """Sync act_resolutions table with existing Act documents.

        This method finds Act documents in the matter that are not reflected
        in the act_resolutions table and updates them to AVAILABLE status.

        This fixes the issue where Acts uploaded via India Code or manually
        still show as "missing" in the Citations tab.

        Args:
            matter_id: Matter UUID.

        Returns:
            Number of act resolutions updated.
        """
        if self.client is None:
            logger.warning("sync_act_resolutions_no_client")
            return 0

        try:
            # Get all Act documents in the matter
            act_docs_result = self.client.table("documents").select(
                "id, filename, source"
            ).eq("matter_id", matter_id).eq("document_type", "act").execute()

            act_docs = act_docs_result.data or []
            if not act_docs:
                return 0

            updated_count = 0

            for doc in act_docs:
                doc_id = doc["id"]
                filename = doc["filename"]
                source = doc.get("source", "uploaded")

                # Extract act name from filename (remove .pdf extension)
                act_name = filename
                if act_name.lower().endswith(".pdf"):
                    act_name = act_name[:-4]

                normalized_name = normalize_act_name(act_name)

                # Determine resolution status based on source
                if source in ("india_code", "auto_fetched"):
                    resolution_status = "auto_fetched"
                else:
                    resolution_status = "available"

                # Check if act_resolution exists and update if needed
                existing = self.client.table("act_resolutions").select(
                    "id, resolution_status, act_document_id"
                ).eq("matter_id", matter_id).eq(
                    "act_name_normalized", normalized_name
                ).execute()

                if existing.data:
                    resolution = existing.data[0]
                    # Only update if currently missing and no document linked
                    if resolution.get("resolution_status") == "missing":
                        self.client.table("act_resolutions").update({
                            "resolution_status": resolution_status,
                            "act_document_id": doc_id,
                            "user_action": "uploaded" if source == "uploaded" else "auto_fetched",
                            "updated_at": datetime.now(UTC).isoformat(),
                        }).eq("id", resolution["id"]).execute()

                        updated_count += 1
                        logger.info(
                            "act_resolution_synced",
                            matter_id=matter_id,
                            act_name=act_name,
                            document_id=doc_id,
                            resolution_status=resolution_status,
                        )
                else:
                    # No resolution exists - create one
                    self.client.table("act_resolutions").insert({
                        "matter_id": matter_id,
                        "act_name_normalized": normalized_name,
                        "act_name_display": act_name,
                        "resolution_status": resolution_status,
                        "act_document_id": doc_id,
                        "user_action": "uploaded" if source == "uploaded" else "auto_fetched",
                        "citation_count": 0,
                    }).execute()

                    updated_count += 1
                    logger.info(
                        "act_resolution_created",
                        matter_id=matter_id,
                        act_name=act_name,
                        document_id=doc_id,
                    )

            if updated_count > 0:
                logger.info(
                    "act_resolutions_sync_complete",
                    matter_id=matter_id,
                    updated_count=updated_count,
                )

            return updated_count

        except Exception as e:
            logger.error(
                "sync_act_resolutions_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return 0


@lru_cache(maxsize=1)
def get_document_service() -> DocumentService:
    """Get singleton document service instance (thread-safe via lru_cache).

    Returns:
        DocumentService instance.
    """
    return DocumentService()
