"""Library service for Shared Legal Library operations.

Handles CRUD operations for library documents, linking to matters,
and duplicate detection for smart auto-curation.
"""

from datetime import UTC, datetime
from functools import lru_cache

import structlog
from supabase import Client

from app.models.library import (
    LibraryDocument,
    LibraryDocumentCreate,
    LibraryDocumentListItem,
    LibraryDocumentSource,
    LibraryDocumentStatus,
    LibraryDocumentType,
    LibraryDuplicate,
    LibraryPaginationMeta,
    MatterLibraryLink,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class LibraryServiceError(Exception):
    """Base exception for library service operations."""

    def __init__(self, message: str, code: str = "LIBRARY_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class LibraryDocumentNotFoundError(LibraryServiceError):
    """Raised when a library document is not found."""

    def __init__(self, document_id: str):
        super().__init__(
            message=f"Library document not found: {document_id}",
            code="LIBRARY_DOCUMENT_NOT_FOUND",
            status_code=404,
        )


class LibraryLinkExistsError(LibraryServiceError):
    """Raised when trying to link an already-linked document."""

    def __init__(self, matter_id: str, document_id: str):
        super().__init__(
            message=f"Document {document_id} is already linked to matter {matter_id}",
            code="LIBRARY_LINK_EXISTS",
            status_code=409,
        )


# =============================================================================
# Service
# =============================================================================


class LibraryService:
    """Service for library document operations.

    Uses the regular Supabase client which applies RLS policies.
    Library documents are readable by all authenticated users.
    """

    def __init__(self, client: Client | None = None):
        """Initialize library service.

        Args:
            client: Optional Supabase client. Uses default client if not provided.
        """
        self.client = client or get_supabase_client()

    # =========================================================================
    # Library Document CRUD
    # =========================================================================

    def create_document(
        self,
        create_data: LibraryDocumentCreate,
        storage_path: str,
        file_size: int,
        added_by: str,
        source: LibraryDocumentSource = LibraryDocumentSource.USER_UPLOAD,
        source_url: str | None = None,
    ) -> LibraryDocument:
        """Create a new library document record.

        Args:
            create_data: Document metadata.
            storage_path: Supabase Storage path.
            file_size: File size in bytes.
            added_by: User UUID who added the document.
            source: Source of the document.
            source_url: Original URL if fetched from external source.

        Returns:
            Created library document.

        Raises:
            LibraryServiceError: If creation fails.
        """
        if self.client is None:
            raise LibraryServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        logger.info(
            "library_document_create_starting",
            title=create_data.title,
            document_type=create_data.document_type.value,
            file_size=file_size,
        )

        try:
            result = self.client.table("library_documents").insert(
                {
                    "filename": create_data.filename,
                    "storage_path": storage_path,
                    "file_size": file_size,
                    "document_type": create_data.document_type.value,
                    "title": create_data.title,
                    "short_title": create_data.short_title,
                    "year": create_data.year,
                    "jurisdiction": create_data.jurisdiction,
                    "source": source.value,
                    "source_url": source_url,
                    "status": LibraryDocumentStatus.PENDING.value,
                    "added_by": added_by,
                }
            ).execute()

            if not result.data:
                raise LibraryServiceError(
                    message="Failed to create library document record",
                    code="INSERT_FAILED",
                )

            doc_data = result.data[0]

            logger.info(
                "library_document_create_complete",
                document_id=doc_data["id"],
                title=create_data.title,
            )

            return self._parse_document(doc_data)

        except LibraryServiceError:
            raise
        except Exception as e:
            logger.error(
                "library_document_create_failed",
                title=create_data.title,
                error=str(e),
            )
            raise LibraryServiceError(
                message=f"Failed to create library document: {e!s}",
                code="CREATE_FAILED",
            ) from e

    def get_document(self, document_id: str) -> LibraryDocument:
        """Get a library document by ID.

        Args:
            document_id: Document UUID.

        Returns:
            Library document.

        Raises:
            LibraryDocumentNotFoundError: If document doesn't exist.
            LibraryServiceError: If query fails.
        """
        if self.client is None:
            raise LibraryServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            result = (
                self.client.table("library_documents")
                .select("*")
                .eq("id", document_id)
                .execute()
            )

            if not result.data:
                raise LibraryDocumentNotFoundError(document_id)

            return self._parse_document(result.data[0])

        except LibraryDocumentNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "library_document_get_failed",
                document_id=document_id,
                error=str(e),
            )
            raise LibraryServiceError(
                message=f"Failed to get library document: {e!s}",
                code="GET_FAILED",
            ) from e

    def list_documents(
        self,
        page: int = 1,
        per_page: int = 20,
        document_type: LibraryDocumentType | None = None,
        year: int | None = None,
        jurisdiction: str | None = None,
        status: LibraryDocumentStatus | None = None,
        search_query: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        matter_id: str | None = None,
    ) -> tuple[list[LibraryDocumentListItem], LibraryPaginationMeta]:
        """List library documents with pagination and filtering.

        Args:
            page: Page number (1-indexed).
            per_page: Items per page (max 100).
            document_type: Optional filter by document type.
            year: Optional filter by year.
            jurisdiction: Optional filter by jurisdiction.
            status: Optional filter by status.
            search_query: Optional title search query.
            sort_by: Column to sort by.
            sort_order: Sort direction ('asc' or 'desc').
            matter_id: If provided, include is_linked flag for this matter.

        Returns:
            Tuple of (documents list, pagination metadata).

        Raises:
            LibraryServiceError: If query fails.
        """
        if self.client is None:
            raise LibraryServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            # Build query
            query = self.client.table("library_documents").select(
                "id, title, short_title, document_type, year, jurisdiction, "
                "status, source, page_count, created_at",
                count="exact",
            )

            # Apply filters
            if document_type is not None:
                query = query.eq("document_type", document_type.value)
            if year is not None:
                query = query.eq("year", year)
            if jurisdiction is not None:
                query = query.eq("jurisdiction", jurisdiction)
            if status is not None:
                query = query.eq("status", status.value)
            if search_query:
                query = query.ilike("title", f"%{search_query}%")

            # Pagination
            offset = (page - 1) * per_page

            # Validate sort column
            allowed_sort_columns = {"created_at", "title", "year", "document_type"}
            if sort_by not in allowed_sort_columns:
                sort_by = "created_at"

            # Execute
            result = (
                query.order(sort_by, desc=(sort_order.lower() == "desc"))
                .range(offset, offset + per_page - 1)
                .execute()
            )

            total = result.count or 0
            total_pages = (total + per_page - 1) // per_page if total > 0 else 0

            # Get linked document IDs if matter_id provided
            linked_docs: dict[str, datetime] = {}
            if matter_id and result.data:
                doc_ids = [doc["id"] for doc in result.data]
                links_result = (
                    self.client.table("matter_library_links")
                    .select("library_document_id, linked_at")
                    .eq("matter_id", matter_id)
                    .in_("library_document_id", doc_ids)
                    .execute()
                )
                for link in links_result.data or []:
                    linked_docs[link["library_document_id"]] = self._parse_datetime(
                        link["linked_at"]
                    )

            # Parse documents
            documents = [
                LibraryDocumentListItem(
                    id=doc["id"],
                    title=doc["title"],
                    short_title=doc.get("short_title"),
                    document_type=LibraryDocumentType(doc["document_type"]),
                    year=doc.get("year"),
                    jurisdiction=doc.get("jurisdiction"),
                    status=LibraryDocumentStatus(doc["status"]),
                    source=LibraryDocumentSource(doc.get("source", "user_upload")),
                    page_count=doc.get("page_count"),
                    created_at=self._parse_datetime(doc["created_at"]),
                    is_linked=doc["id"] in linked_docs,
                    linked_at=linked_docs.get(doc["id"]),
                )
                for doc in result.data
            ]

            meta = LibraryPaginationMeta(
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            )

            logger.info(
                "library_documents_list_success",
                total=total,
                page=page,
                returned=len(documents),
            )

            return documents, meta

        except Exception as e:
            logger.error(
                "library_documents_list_failed",
                page=page,
                error=str(e),
            )
            raise LibraryServiceError(
                message=f"Failed to list library documents: {e!s}",
                code="LIST_FAILED",
            ) from e

    def update_status(
        self,
        document_id: str,
        status: LibraryDocumentStatus,
        page_count: int | None = None,
        quality_flags: list[str] | None = None,
    ) -> None:
        """Update library document processing status.

        Args:
            document_id: Document UUID.
            status: New status.
            page_count: Number of pages (if known).
            quality_flags: Quality issues detected.

        Raises:
            LibraryServiceError: If update fails.
        """
        if self.client is None:
            raise LibraryServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            update_data: dict = {"status": status.value}

            now = datetime.now(UTC).isoformat()
            if status == LibraryDocumentStatus.PROCESSING:
                update_data["processing_started_at"] = now
            elif status in (
                LibraryDocumentStatus.COMPLETED,
                LibraryDocumentStatus.FAILED,
            ):
                update_data["processing_completed_at"] = now

            if page_count is not None:
                update_data["page_count"] = page_count
            if quality_flags is not None:
                update_data["quality_flags"] = quality_flags

            self.client.table("library_documents").update(update_data).eq(
                "id", document_id
            ).execute()

            logger.info(
                "library_document_status_updated",
                document_id=document_id,
                status=status.value,
            )

        except Exception as e:
            logger.error(
                "library_document_status_update_failed",
                document_id=document_id,
                error=str(e),
            )
            raise LibraryServiceError(
                message=f"Failed to update status: {e!s}",
                code="STATUS_UPDATE_FAILED",
            ) from e

    # =========================================================================
    # Deduplication
    # =========================================================================

    def find_duplicates(
        self,
        title: str,
        year: int | None = None,
        similarity_threshold: float = 0.6,
    ) -> list[LibraryDuplicate]:
        """Find potential duplicate documents by fuzzy title matching.

        Args:
            title: Title to search for.
            year: Optional year to improve matching.
            similarity_threshold: Minimum similarity score (0-1).

        Returns:
            List of potential duplicates.

        Raises:
            LibraryServiceError: If query fails.
        """
        if self.client is None:
            raise LibraryServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            # Use the database function for fuzzy matching
            result = self.client.rpc(
                "find_library_duplicates",
                {
                    "search_title": title,
                    "search_year": year,
                    "similarity_threshold": similarity_threshold,
                },
            ).execute()

            duplicates = [
                LibraryDuplicate(
                    id=dup["id"],
                    title=dup["title"],
                    year=dup.get("year"),
                    document_type=LibraryDocumentType(dup["document_type"]),
                    similarity=dup["similarity"],
                )
                for dup in result.data or []
            ]

            logger.info(
                "library_duplicates_found",
                search_title=title,
                found_count=len(duplicates),
            )

            return duplicates

        except Exception as e:
            logger.error(
                "library_find_duplicates_failed",
                title=title,
                error=str(e),
            )
            raise LibraryServiceError(
                message=f"Failed to find duplicates: {e!s}",
                code="FIND_DUPLICATES_FAILED",
            ) from e

    # =========================================================================
    # Matter Linking
    # =========================================================================

    def link_to_matter(
        self,
        matter_id: str,
        library_document_id: str,
        linked_by: str,
    ) -> MatterLibraryLink:
        """Link a library document to a matter.

        Args:
            matter_id: Matter UUID.
            library_document_id: Library document UUID.
            linked_by: User UUID who is linking.

        Returns:
            Created link record.

        Raises:
            LibraryDocumentNotFoundError: If document doesn't exist.
            LibraryLinkExistsError: If already linked.
            LibraryServiceError: If linking fails.
        """
        if self.client is None:
            raise LibraryServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        # Verify document exists
        self.get_document(library_document_id)

        try:
            # Check for existing link
            existing = (
                self.client.table("matter_library_links")
                .select("id")
                .eq("matter_id", matter_id)
                .eq("library_document_id", library_document_id)
                .execute()
            )

            if existing.data:
                raise LibraryLinkExistsError(matter_id, library_document_id)

            # Create link
            result = (
                self.client.table("matter_library_links")
                .insert(
                    {
                        "matter_id": matter_id,
                        "library_document_id": library_document_id,
                        "linked_by": linked_by,
                    }
                )
                .execute()
            )

            if not result.data:
                raise LibraryServiceError(
                    message="Failed to create link",
                    code="LINK_FAILED",
                )

            link_data = result.data[0]

            logger.info(
                "library_document_linked",
                matter_id=matter_id,
                library_document_id=library_document_id,
                linked_by=linked_by,
            )

            return MatterLibraryLink(
                id=link_data["id"],
                matter_id=link_data["matter_id"],
                library_document_id=link_data["library_document_id"],
                linked_by=link_data["linked_by"],
                linked_at=self._parse_datetime(link_data["linked_at"]),
            )

        except (LibraryDocumentNotFoundError, LibraryLinkExistsError):
            raise
        except LibraryServiceError:
            raise
        except Exception as e:
            logger.error(
                "library_link_failed",
                matter_id=matter_id,
                library_document_id=library_document_id,
                error=str(e),
            )
            raise LibraryServiceError(
                message=f"Failed to link document: {e!s}",
                code="LINK_FAILED",
            ) from e

    def unlink_from_matter(
        self,
        matter_id: str,
        library_document_id: str,
    ) -> bool:
        """Unlink a library document from a matter.

        Args:
            matter_id: Matter UUID.
            library_document_id: Library document UUID.

        Returns:
            True if unlinked successfully.

        Raises:
            LibraryServiceError: If unlinking fails.
        """
        if self.client is None:
            raise LibraryServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            result = (
                self.client.table("matter_library_links")
                .delete()
                .eq("matter_id", matter_id)
                .eq("library_document_id", library_document_id)
                .execute()
            )

            deleted = len(result.data) > 0 if result.data else False

            if deleted:
                logger.info(
                    "library_document_unlinked",
                    matter_id=matter_id,
                    library_document_id=library_document_id,
                )

            return deleted

        except Exception as e:
            logger.error(
                "library_unlink_failed",
                matter_id=matter_id,
                library_document_id=library_document_id,
                error=str(e),
            )
            raise LibraryServiceError(
                message=f"Failed to unlink document: {e!s}",
                code="UNLINK_FAILED",
            ) from e

    def get_linked_documents(
        self,
        matter_id: str,
    ) -> list[LibraryDocumentListItem]:
        """Get all library documents linked to a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            List of linked library documents.

        Raises:
            LibraryServiceError: If query fails.
        """
        if self.client is None:
            raise LibraryServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            # Get links with document details via join
            result = (
                self.client.table("matter_library_links")
                .select(
                    "linked_at, "
                    "library_documents(id, title, short_title, document_type, "
                    "year, jurisdiction, status, source, page_count, created_at)"
                )
                .eq("matter_id", matter_id)
                .execute()
            )

            documents = []
            for link in result.data or []:
                doc = link.get("library_documents")
                if doc:
                    documents.append(
                        LibraryDocumentListItem(
                            id=doc["id"],
                            title=doc["title"],
                            short_title=doc.get("short_title"),
                            document_type=LibraryDocumentType(doc["document_type"]),
                            year=doc.get("year"),
                            jurisdiction=doc.get("jurisdiction"),
                            status=LibraryDocumentStatus(doc["status"]),
                            source=LibraryDocumentSource(
                                doc.get("source", "user_upload")
                            ),
                            page_count=doc.get("page_count"),
                            created_at=self._parse_datetime(doc["created_at"]),
                            is_linked=True,
                            linked_at=self._parse_datetime(link["linked_at"]),
                        )
                    )

            logger.info(
                "library_linked_documents_fetched",
                matter_id=matter_id,
                count=len(documents),
            )

            return documents

        except Exception as e:
            logger.error(
                "library_get_linked_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise LibraryServiceError(
                message=f"Failed to get linked documents: {e!s}",
                code="GET_LINKED_FAILED",
            ) from e

    # =========================================================================
    # Processing Pipeline
    # =========================================================================

    def trigger_processing(
        self,
        library_document_id: str,
        extracted_text: str,
    ) -> str:
        """Trigger the processing pipeline for a library document.

        Enqueues the Celery task chain: chunk -> embed.

        Args:
            library_document_id: Library document UUID.
            extracted_text: OCR/extracted text content.

        Returns:
            Celery task ID for tracking.

        Raises:
            LibraryServiceError: If triggering fails.
        """
        try:
            from app.workers.tasks.library_tasks import process_library_document

            result = process_library_document.delay(
                library_document_id=library_document_id,
                extracted_text=extracted_text,
            )

            logger.info(
                "library_processing_triggered",
                library_document_id=library_document_id,
                task_id=result.id,
                text_length=len(extracted_text),
            )

            return result.id

        except Exception as e:
            logger.error(
                "library_processing_trigger_failed",
                library_document_id=library_document_id,
                error=str(e),
            )
            raise LibraryServiceError(
                message=f"Failed to trigger processing: {e!s}",
                code="PROCESSING_TRIGGER_FAILED",
            ) from e

    # =========================================================================
    # Helpers
    # =========================================================================

    def _parse_datetime(self, value: str | None) -> datetime:
        """Parse datetime string from database."""
        if value is None:
            return datetime.now(UTC)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _parse_document(self, doc_data: dict) -> LibraryDocument:
        """Parse a library document from database row."""
        return LibraryDocument(
            id=doc_data["id"],
            filename=doc_data["filename"],
            storage_path=doc_data["storage_path"],
            file_size=doc_data["file_size"],
            page_count=doc_data.get("page_count"),
            document_type=LibraryDocumentType(doc_data["document_type"]),
            title=doc_data["title"],
            short_title=doc_data.get("short_title"),
            year=doc_data.get("year"),
            jurisdiction=doc_data.get("jurisdiction"),
            source=LibraryDocumentSource(doc_data.get("source", "user_upload")),
            source_url=doc_data.get("source_url"),
            status=LibraryDocumentStatus(doc_data["status"]),
            processing_started_at=(
                self._parse_datetime(doc_data["processing_started_at"])
                if doc_data.get("processing_started_at")
                else None
            ),
            processing_completed_at=(
                self._parse_datetime(doc_data["processing_completed_at"])
                if doc_data.get("processing_completed_at")
                else None
            ),
            quality_flags=doc_data.get("quality_flags") or [],
            added_by=doc_data.get("added_by"),
            created_at=self._parse_datetime(doc_data["created_at"]),
            updated_at=self._parse_datetime(doc_data["updated_at"]),
        )


@lru_cache(maxsize=1)
def get_library_service() -> LibraryService:
    """Get singleton library service instance.

    Returns:
        LibraryService instance.
    """
    return LibraryService()
