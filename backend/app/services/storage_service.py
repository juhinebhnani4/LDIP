"""Supabase Storage service for document file operations.

This service handles file uploads to Supabase Storage with proper
folder structure and matter isolation.

Storage path structure:
- documents/{matter_id}/uploads/{filename}  - Case files and general uploads
- documents/{matter_id}/acts/{filename}     - Act/reference documents
- documents/{matter_id}/exports/{filename}  - Generated exports
"""

import threading
import time
import uuid
from functools import lru_cache

import structlog
from supabase import Client

from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)

# Valid storage subfolders
VALID_SUBFOLDERS = {"uploads", "acts", "exports", "chunks"}

# Default signed URL expiration (1 hour)
DEFAULT_SIGNED_URL_EXPIRES = 3600

# Download cache settings
DOWNLOAD_CACHE_TTL_SECONDS = 600  # 10 minutes
DOWNLOAD_CACHE_MAX_BYTES = 500 * 1024 * 1024  # 500 MB


class StorageError(Exception):
    """Base exception for storage operations."""

    def __init__(self, message: str, code: str = "STORAGE_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
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

        # In-memory download cache: {storage_path: (bytes, expiry_timestamp)}
        self._download_cache: dict[str, tuple[bytes, float]] = {}
        self._cache_lock = threading.Lock()
        self._cache_total_bytes = 0

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

    def _evict_expired_cache(self) -> None:
        """Remove expired entries from cache. Must be called with _cache_lock held."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._download_cache.items() if now >= exp]
        for key in expired:
            data, _ = self._download_cache.pop(key)
            self._cache_total_bytes -= len(data)
            logger.debug("storage_download_cache_expired", storage_path=key)

    def _evict_lru_until_fits(self, new_size: int) -> None:
        """Evict oldest entries until new_size fits within max. Must be called with _cache_lock held."""
        while self._cache_total_bytes + new_size > DOWNLOAD_CACHE_MAX_BYTES and self._download_cache:
            # dict preserves insertion order; pop the first (oldest) entry
            oldest_key = next(iter(self._download_cache))
            data, _ = self._download_cache.pop(oldest_key)
            self._cache_total_bytes -= len(data)
            logger.debug("storage_download_cache_evicted_lru", storage_path=oldest_key)

    def _cache_file(self, storage_path: str, data: bytes) -> None:
        """Store downloaded file in cache with TTL."""
        file_size = len(data)
        if file_size > DOWNLOAD_CACHE_MAX_BYTES:
            return  # Don't cache files larger than the entire cache

        with self._cache_lock:
            self._evict_expired_cache()
            self._evict_lru_until_fits(file_size)
            self._download_cache[storage_path] = (data, time.monotonic() + DOWNLOAD_CACHE_TTL_SECONDS)
            self._cache_total_bytes += file_size

    def clear_download_cache(self) -> None:
        """Clear the entire download cache. Useful for testing."""
        with self._cache_lock:
            self._download_cache.clear()
            self._cache_total_bytes = 0
            logger.info("storage_download_cache_cleared")

    def download_file(self, storage_path: str) -> bytes:
        """Download a file from Supabase Storage with in-memory TTL caching.

        Files are cached for 10 minutes (covers full pipeline processing).
        Max cache size is 500 MB with LRU eviction.

        Args:
            storage_path: Full storage path to download.

        Returns:
            File content as bytes.

        Raises:
            StorageError: If download fails.
        """
        if self.client is None:
            raise StorageError(
                message="Storage client not configured",
                code="STORAGE_NOT_CONFIGURED"
            )

        # Check cache first
        with self._cache_lock:
            cached = self._download_cache.get(storage_path)
            if cached is not None:
                data, expiry = cached
                if time.monotonic() < expiry:
                    # Move to end for LRU (re-insert)
                    del self._download_cache[storage_path]
                    self._download_cache[storage_path] = (data, expiry)
                    logger.info(
                        "storage_download_cache_hit",
                        storage_path=storage_path,
                        file_size=len(data),
                        cache_entries=len(self._download_cache),
                    )
                    return data
                else:
                    # Expired — remove it
                    del self._download_cache[storage_path]
                    self._cache_total_bytes -= len(data)

        logger.info("storage_download_starting", storage_path=storage_path)

        try:
            response = self.client.storage.from_(self.bucket).download(storage_path)

            logger.info(
                "storage_download_complete",
                storage_path=storage_path,
                file_size=len(response),
            )

            # Cache the downloaded file
            self._cache_file(storage_path, response)

            return response

        except Exception as e:
            logger.error(
                "storage_download_failed",
                storage_path=storage_path,
                error=str(e),
            )
            raise StorageError(
                message=f"Failed to download file: {e!s}",
                code="DOWNLOAD_FAILED"
            ) from e


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    """Get singleton storage service instance (thread-safe via lru_cache).

    Returns:
        StorageService instance.
    """
    return StorageService()
