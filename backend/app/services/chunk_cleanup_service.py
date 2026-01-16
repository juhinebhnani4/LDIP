"""Chunk Cleanup Service for removing stale OCR chunk records.

Story 15.4: Chunk Cleanup Mechanism

Provides automatic cleanup of chunk records after document processing
completes successfully. Cleans up both database records and storage.
"""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import structlog

from app.models.ocr_chunk import ChunkStatus
from app.services.ocr_chunk_service import (
    OCRChunkService,
    get_ocr_chunk_service,
)
from app.services.storage_service import (
    StorageService,
    get_storage_service,
)

logger = structlog.get_logger(__name__)

# Default retention period for chunk records (24 hours after completion)
DEFAULT_RETENTION_HOURS = 24


class ChunkCleanupError(Exception):
    """Base exception for chunk cleanup operations."""

    def __init__(self, message: str, code: str = "CHUNK_CLEANUP_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ChunkCleanupService:
    """Service for cleaning up stale chunk records and storage.

    Handles:
    - Deleting chunk database records after document processing completes
    - Removing cached OCR results from storage
    - Scheduled cleanup via Celery beat

    Example:
        >>> service = ChunkCleanupService()
        >>> await service.cleanup_document_chunks("doc-123")
        >>> stats = await service.cleanup_stale_chunks()
        >>> print(f"Cleaned {stats['documents_cleaned']} documents")
    """

    def __init__(
        self,
        chunk_service: OCRChunkService | None = None,
        storage_service: StorageService | None = None,
        retention_hours: int = DEFAULT_RETENTION_HOURS,
    ) -> None:
        """Initialize chunk cleanup service.

        Args:
            chunk_service: Optional OCR chunk service (for testing).
            storage_service: Optional storage service (for testing).
            retention_hours: Hours to retain chunks after processing.
        """
        self._chunk_service = chunk_service
        self._storage_service = storage_service
        self.retention_hours = retention_hours

    @property
    def chunk_service(self) -> OCRChunkService:
        """Get OCR chunk service instance."""
        if self._chunk_service is None:
            self._chunk_service = get_ocr_chunk_service()
        return self._chunk_service

    @property
    def storage_service(self) -> StorageService:
        """Get storage service instance."""
        if self._storage_service is None:
            self._storage_service = get_storage_service()
        return self._storage_service

    async def cleanup_document_chunks(
        self,
        document_id: str,
        delete_storage: bool = True,
    ) -> dict:
        """Clean up all chunks for a document.

        Called after document processing completes successfully.
        Removes chunk records and optionally deletes cached results.

        Args:
            document_id: Document UUID.
            delete_storage: Whether to delete storage files.

        Returns:
            Dict with cleanup statistics.
        """
        result = {
            "document_id": document_id,
            "chunks_deleted": 0,
            "storage_files_deleted": 0,
            "storage_errors": [],
        }

        # Get chunks to find storage paths before deleting
        chunks = await self.chunk_service.get_chunks_by_document(document_id)

        if not chunks:
            logger.debug(
                "cleanup_no_chunks_found",
                document_id=document_id,
            )
            return result

        # Delete storage files if requested
        if delete_storage:
            for chunk in chunks:
                if chunk.result_storage_path:
                    try:
                        self.storage_service.delete_file(
                            chunk.result_storage_path
                        )
                        result["storage_files_deleted"] += 1
                    except Exception as e:
                        logger.warning(
                            "cleanup_storage_delete_failed",
                            chunk_id=chunk.id,
                            storage_path=chunk.result_storage_path,
                            error=str(e),
                        )
                        result["storage_errors"].append({
                            "chunk_id": chunk.id,
                            "path": chunk.result_storage_path,
                            "error": str(e),
                        })

        # Delete chunk records
        result["chunks_deleted"] = await self.chunk_service.delete_chunks_for_document(
            document_id
        )

        logger.info(
            "document_chunks_cleaned_up",
            document_id=document_id,
            chunks_deleted=result["chunks_deleted"],
            storage_files_deleted=result["storage_files_deleted"],
            storage_errors=len(result["storage_errors"]),
        )

        return result

    async def cleanup_stale_chunks(
        self,
        retention_hours: int | None = None,
        dry_run: bool = False,
    ) -> dict:
        """Clean up stale chunk records based on retention period.

        Called by Celery beat task to cleanup old chunk records.

        Args:
            retention_hours: Override default retention period.
            dry_run: If True, only report what would be cleaned.

        Returns:
            Dict with cleanup statistics.
        """
        hours = retention_hours or self.retention_hours
        cutoff_date = datetime.now(UTC) - timedelta(hours=hours)

        result = {
            "cutoff_date": cutoff_date.isoformat(),
            "retention_hours": hours,
            "dry_run": dry_run,
            "documents_checked": 0,
            "documents_cleaned": 0,
            "total_chunks_deleted": 0,
            "total_storage_files_deleted": 0,
            "errors": [],
        }

        # Find documents with stale chunks
        stale_docs = await self.chunk_service.get_stale_chunk_documents(
            cutoff_date=cutoff_date
        )

        result["documents_checked"] = len(stale_docs)

        if dry_run:
            logger.info(
                "cleanup_dry_run",
                documents_found=len(stale_docs),
                cutoff_date=cutoff_date.isoformat(),
            )
            return result

        # Cleanup each document
        for doc_info in stale_docs:
            try:
                cleanup_result = await self.cleanup_document_chunks(
                    document_id=doc_info["document_id"],
                    delete_storage=True,
                )

                result["documents_cleaned"] += 1
                result["total_chunks_deleted"] += cleanup_result["chunks_deleted"]
                result["total_storage_files_deleted"] += cleanup_result[
                    "storage_files_deleted"
                ]

            except Exception as e:
                logger.error(
                    "cleanup_document_failed",
                    document_id=doc_info["document_id"],
                    error=str(e),
                )
                result["errors"].append({
                    "document_id": doc_info["document_id"],
                    "error": str(e),
                })

        logger.info(
            "stale_chunks_cleanup_complete",
            documents_cleaned=result["documents_cleaned"],
            total_chunks_deleted=result["total_chunks_deleted"],
            total_storage_files_deleted=result["total_storage_files_deleted"],
            errors=len(result["errors"]),
        )

        return result


@lru_cache(maxsize=1)
def get_chunk_cleanup_service() -> ChunkCleanupService:
    """Get singleton chunk cleanup service instance.

    Returns:
        ChunkCleanupService instance.
    """
    return ChunkCleanupService()
