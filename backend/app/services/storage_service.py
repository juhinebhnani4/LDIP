"""Supabase Storage service for document file operations.

This service handles file uploads to Supabase Storage with proper
folder structure and matter isolation.

Storage path structure:
- documents/{matter_id}/uploads/{filename}  - Case files and general uploads
- documents/{matter_id}/acts/{filename}     - Act/reference documents
- documents/{matter_id}/exports/{filename}  - Generated exports
"""

import uuid

import structlog
from supabase import Client

from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)

# Valid storage subfolders
VALID_SUBFOLDERS = {"uploads", "acts", "exports"}

# Default signed URL expiration (1 hour)
DEFAULT_SIGNED_URL_EXPIRES = 3600


class StorageError(Exception):
    """Base exception for storage operations."""

    def __init__(self, message: str, code: str = "STORAGE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class StorageService:
    """Service for Supabase Storage operations.

    Uses the service client to bypass RLS since the backend
    has already validated user access via require_matter_role.
    """

    def __init__(self, client: Client | None = None):
        """Initialize storage service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self.client = client or get_service_client()
        self.bucket = "documents"

    def _generate_unique_filename(self, filename: str) -> str:
        """Generate a unique filename by appending UUID suffix.

        Args:
            filename: Original filename.

        Returns:
            Filename with UUID suffix before extension.
        """
        # Split filename and extension
        if "." in filename:
            name_parts = filename.rsplit(".", 1)
            name = name_parts[0]
            ext = name_parts[1]
            return f"{name}_{uuid.uuid4().hex[:8]}.{ext}"
        else:
            return f"{filename}_{uuid.uuid4().hex[:8]}"

    def _validate_subfolder(self, subfolder: str) -> None:
        """Validate subfolder is allowed.

        Args:
            subfolder: Subfolder name to validate.

        Raises:
            StorageError: If subfolder is not valid.
        """
        if subfolder not in VALID_SUBFOLDERS:
            raise StorageError(
                message=f"Invalid subfolder: {subfolder}. Must be one of: {VALID_SUBFOLDERS}",
                code="INVALID_SUBFOLDER"
            )

    def upload_file(
        self,
        matter_id: str,
        subfolder: str,
        file_content: bytes,
        filename: str,
        content_type: str = "application/pdf",
    ) -> tuple[str, str | None]:
        """Upload a file to Supabase Storage.

        Args:
            matter_id: Matter UUID for path organization.
            subfolder: Storage subfolder (uploads, acts, exports).
            file_content: File content as bytes.
            filename: Original filename.
            content_type: MIME type of the file.

        Returns:
            Tuple of (storage_path, signed_url).

        Raises:
            StorageError: If upload fails.
        """
        self._validate_subfolder(subfolder)

        if self.client is None:
            raise StorageError(
                message="Storage client not configured",
                code="STORAGE_NOT_CONFIGURED"
            )

        # Generate unique filename to prevent conflicts
        unique_filename = self._generate_unique_filename(filename)
        storage_path = f"{matter_id}/{subfolder}/{unique_filename}"

        logger.info(
            "storage_upload_starting",
            matter_id=matter_id,
            subfolder=subfolder,
            filename=filename,
            unique_filename=unique_filename,
            file_size=len(file_content),
        )

        try:
            # Upload file to storage
            self.client.storage.from_(self.bucket).upload(
                path=storage_path,
                file=file_content,
                file_options={"content-type": content_type}
            )

            # Generate signed URL for download
            signed_url_response = self.client.storage.from_(self.bucket).create_signed_url(
                path=storage_path,
                expires_in=DEFAULT_SIGNED_URL_EXPIRES
            )

            signed_url = signed_url_response.get("signedURL")

            logger.info(
                "storage_upload_complete",
                matter_id=matter_id,
                storage_path=storage_path,
            )

            return storage_path, signed_url

        except Exception as e:
            logger.error(
                "storage_upload_failed",
                matter_id=matter_id,
                storage_path=storage_path,
                error=str(e),
            )
            raise StorageError(
                message=f"Failed to upload file: {e!s}",
                code="UPLOAD_FAILED"
            ) from e

    def delete_file(self, storage_path: str) -> bool:
        """Delete a file from Supabase Storage.

        Args:
            storage_path: Full storage path to delete.

        Returns:
            True if deletion was successful.

        Raises:
            StorageError: If deletion fails.
        """
        if self.client is None:
            raise StorageError(
                message="Storage client not configured",
                code="STORAGE_NOT_CONFIGURED"
            )

        logger.info("storage_delete_starting", storage_path=storage_path)

        try:
            self.client.storage.from_(self.bucket).remove([storage_path])

            logger.info("storage_delete_complete", storage_path=storage_path)
            return True

        except Exception as e:
            logger.error(
                "storage_delete_failed",
                storage_path=storage_path,
                error=str(e),
            )
            raise StorageError(
                message=f"Failed to delete file: {e!s}",
                code="DELETE_FAILED"
            ) from e

    def get_signed_url(
        self,
        storage_path: str,
        expires_in: int = DEFAULT_SIGNED_URL_EXPIRES,
    ) -> str:
        """Generate a signed URL for file download.

        Args:
            storage_path: Full storage path.
            expires_in: URL expiration time in seconds.

        Returns:
            Signed URL for download.

        Raises:
            StorageError: If URL generation fails.
        """
        if self.client is None:
            raise StorageError(
                message="Storage client not configured",
                code="STORAGE_NOT_CONFIGURED"
            )

        try:
            response = self.client.storage.from_(self.bucket).create_signed_url(
                path=storage_path,
                expires_in=expires_in
            )

            return response.get("signedURL", "")

        except Exception as e:
            logger.error(
                "signed_url_generation_failed",
                storage_path=storage_path,
                error=str(e),
            )
            raise StorageError(
                message=f"Failed to generate signed URL: {e!s}",
                code="SIGNED_URL_FAILED"
            ) from e


# Singleton instance
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get singleton storage service instance.

    Returns:
        StorageService instance.
    """
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
