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
    DocumentStatus,
    DocumentType,
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


# Singleton instance
_document_service: DocumentService | None = None


def get_document_service() -> DocumentService:
    """Get singleton document service instance.

    Returns:
        DocumentService instance.
    """
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
