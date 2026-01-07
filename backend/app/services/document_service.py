"""Document service for database operations.

Handles document record creation and management in the documents table.
Works with StorageService for file operations.
"""

from datetime import datetime, timezone

import structlog
from supabase import Client

from app.models.document import (
    Document,
    DocumentCreate,
    DocumentListItem,
    DocumentStatus,
    DocumentType,
    PaginationMeta,
    UploadedDocument,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


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
            Document record.

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

            doc_data = result.data[0]

            return Document(
                id=doc_data["id"],
                matter_id=doc_data["matter_id"],
                filename=doc_data["filename"],
                storage_path=doc_data["storage_path"],
                file_size=doc_data["file_size"],
                page_count=doc_data.get("page_count"),
                document_type=DocumentType(doc_data["document_type"]),
                is_reference_material=doc_data["is_reference_material"],
                uploaded_by=doc_data["uploaded_by"],
                uploaded_at=datetime.fromisoformat(doc_data["uploaded_at"].replace("Z", "+00:00")),
                status=DocumentStatus(doc_data["status"]),
                processing_started_at=self._parse_datetime(doc_data.get("processing_started_at")),
                processing_completed_at=self._parse_datetime(doc_data.get("processing_completed_at")),
                created_at=datetime.fromisoformat(doc_data["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(doc_data["updated_at"].replace("Z", "+00:00")),
            )

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

            return [
                Document(
                    id=doc["id"],
                    matter_id=doc["matter_id"],
                    filename=doc["filename"],
                    storage_path=doc["storage_path"],
                    file_size=doc["file_size"],
                    page_count=doc.get("page_count"),
                    document_type=DocumentType(doc["document_type"]),
                    is_reference_material=doc["is_reference_material"],
                    uploaded_by=doc["uploaded_by"],
                    uploaded_at=datetime.fromisoformat(doc["uploaded_at"].replace("Z", "+00:00")),
                    status=DocumentStatus(doc["status"]),
                    processing_started_at=self._parse_datetime(doc.get("processing_started_at")),
                    processing_completed_at=self._parse_datetime(doc.get("processing_completed_at")),
                    created_at=datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(doc["updated_at"].replace("Z", "+00:00")),
                )
                for doc in result.data
            ]

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
            query = self.client.table("documents").select(
                "id, matter_id, filename, file_size, document_type, "
                "is_reference_material, status, uploaded_at, uploaded_by",
                count="exact"
            ).eq("matter_id", matter_id)

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

            documents = [
                DocumentListItem(
                    id=doc["id"],
                    matter_id=doc["matter_id"],
                    filename=doc["filename"],
                    file_size=doc["file_size"],
                    document_type=DocumentType(doc["document_type"]),
                    is_reference_material=doc["is_reference_material"],
                    status=DocumentStatus(doc["status"]),
                    uploaded_at=datetime.fromisoformat(
                        doc["uploaded_at"].replace("Z", "+00:00")
                    ),
                    uploaded_by=doc["uploaded_by"],
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
    ) -> Document:
        """Update document metadata.

        Args:
            document_id: Document UUID.
            document_type: New document type (if provided).
            is_reference_material: Override reference material flag.
                                   If not provided and document_type is 'act',
                                   automatically set to True.

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

            return Document(
                id=doc_data["id"],
                matter_id=doc_data["matter_id"],
                filename=doc_data["filename"],
                storage_path=doc_data["storage_path"],
                file_size=doc_data["file_size"],
                page_count=doc_data.get("page_count"),
                document_type=DocumentType(doc_data["document_type"]),
                is_reference_material=doc_data["is_reference_material"],
                uploaded_by=doc_data["uploaded_by"],
                uploaded_at=datetime.fromisoformat(
                    doc_data["uploaded_at"].replace("Z", "+00:00")
                ),
                status=DocumentStatus(doc_data["status"]),
                processing_started_at=self._parse_datetime(
                    doc_data.get("processing_started_at")
                ),
                processing_completed_at=self._parse_datetime(
                    doc_data.get("processing_completed_at")
                ),
                created_at=datetime.fromisoformat(
                    doc_data["created_at"].replace("Z", "+00:00")
                ),
                updated_at=datetime.fromisoformat(
                    doc_data["updated_at"].replace("Z", "+00:00")
                ),
            )

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

    def delete_document(self, document_id: str) -> bool:
        """Delete a document record.

        Note: This only deletes the database record. The storage file
        should be deleted separately via StorageService.

        Args:
            document_id: Document UUID.

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
            # First verify document exists
            result = self.client.table("documents").select("id").eq(
                "id", document_id
            ).execute()

            if not result.data:
                raise DocumentNotFoundError(document_id)

            # Delete the document
            self.client.table("documents").delete().eq(
                "id", document_id
            ).execute()

            logger.info("document_deleted", document_id=document_id)
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


from functools import lru_cache


@lru_cache(maxsize=1)
def get_document_service() -> DocumentService:
    """Get singleton document service instance (thread-safe via lru_cache).

    Returns:
        DocumentService instance.
    """
    return DocumentService()
