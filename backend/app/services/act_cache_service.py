"""Global Act Cache Service for caching validated Act PDFs.

This service manages the global cache of Act PDFs fetched from India Code.
Acts are cached globally (not per-matter) to avoid re-downloading the same
Act multiple times.

Storage structure:
- documents/global/acts/{normalized_name}.pdf - Cached Act PDFs

Part of Act Validation and Auto-Fetching feature.
"""

import structlog
from supabase import Client

from app.core.config import get_settings
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)

# Get settings for URL expiry (default to 24 hours if not configured)
_settings = get_settings()
CACHED_ACT_URL_EXPIRES = getattr(_settings, 'act_cache_url_expiry_seconds', 86400)


class ActCacheError(Exception):
    """Base exception for act cache operations."""

    def __init__(self, message: str, code: str = "ACT_CACHE_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ActCacheService:
    """Service for managing global Act PDF cache.

    This service provides:
    1. Caching fetched Act PDFs globally
    2. Checking if an Act is already cached
    3. Retrieving cached Act PDFs
    4. Linking cached Acts to matter-specific act_resolutions

    Acts are stored in a global location (not per-matter) to avoid
    re-downloading the same Act for different matters.
    """

    def __init__(self, client: Client | None = None):
        """Initialize act cache service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self.client = client or get_service_client()
        self.bucket = "documents"
        self._settings = get_settings()

    def _get_storage_path(self, normalized_name: str) -> str:
        """Get storage path for a cached Act.

        Args:
            normalized_name: Normalized act name (e.g., "negotiable_instruments_act_1881")

        Returns:
            Storage path (e.g., "global/acts/negotiable_instruments_act_1881.pdf")
        """
        prefix = self._settings.act_cache_storage_prefix
        return f"{prefix}/{normalized_name}.pdf"

    def is_cached(self, normalized_name: str) -> bool:
        """Check if an Act PDF is already cached.

        Args:
            normalized_name: Normalized act name.

        Returns:
            True if cached, False otherwise.
        """
        if self.client is None:
            return False

        storage_path = self._get_storage_path(normalized_name)

        try:
            # Try to get file info - if it exists, it's cached
            # We use list with prefix to check existence
            prefix = self._settings.act_cache_storage_prefix
            result = self.client.storage.from_(self.bucket).list(
                path=f"{prefix}/",
                options={"search": f"{normalized_name}.pdf"}
            )

            # Check if our file is in the results
            if result:
                for file in result:
                    if file.get("name") == f"{normalized_name}.pdf":
                        return True

            return False

        except Exception as e:
            logger.debug(
                "act_cache_check_error",
                normalized_name=normalized_name,
                error=str(e),
            )
            return False

    def cache_act(
        self,
        normalized_name: str,
        pdf_content: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Cache an Act PDF globally.

        Args:
            normalized_name: Normalized act name.
            pdf_content: PDF content as bytes.
            content_type: MIME type of the file.

        Returns:
            Storage path of cached file.

        Raises:
            ActCacheError: If caching fails.
        """
        if self.client is None:
            raise ActCacheError(
                message="Storage client not configured",
                code="STORAGE_NOT_CONFIGURED"
            )

        storage_path = self._get_storage_path(normalized_name)

        logger.info(
            "act_cache_starting",
            normalized_name=normalized_name,
            file_size=len(pdf_content),
        )

        try:
            # Upload to global cache location
            self.client.storage.from_(self.bucket).upload(
                path=storage_path,
                file=pdf_content,
                file_options={
                    "content-type": content_type,
                    "upsert": "true",  # Overwrite if exists
                }
            )

            logger.info(
                "act_cache_complete",
                normalized_name=normalized_name,
                storage_path=storage_path,
            )

            return storage_path

        except Exception as e:
            logger.error(
                "act_cache_failed",
                normalized_name=normalized_name,
                error=str(e),
            )
            raise ActCacheError(
                message=f"Failed to cache Act PDF: {e!s}",
                code="CACHE_FAILED"
            ) from e

    def get_cached_act(self, normalized_name: str) -> bytes | None:
        """Get a cached Act PDF.

        Args:
            normalized_name: Normalized act name.

        Returns:
            PDF content as bytes if cached, None otherwise.
        """
        if self.client is None:
            return None

        storage_path = self._get_storage_path(normalized_name)

        try:
            response = self.client.storage.from_(self.bucket).download(storage_path)

            logger.info(
                "act_cache_hit",
                normalized_name=normalized_name,
                file_size=len(response),
            )

            return response

        except Exception as e:
            logger.debug(
                "act_cache_miss",
                normalized_name=normalized_name,
                error=str(e),
            )
            return None

    def get_signed_url(
        self,
        normalized_name: str,
        expires_in: int | None = None,
    ) -> str | None:
        """Get a signed URL for a cached Act PDF.

        Args:
            normalized_name: Normalized act name.
            expires_in: URL expiration time in seconds.

        Returns:
            Signed URL for download, None if not cached.
        """
        if self.client is None:
            return None

        storage_path = self._get_storage_path(normalized_name)

        # Use config default if not specified
        if expires_in is None:
            expires_in = self._settings.act_cache_url_expiry_seconds

        try:
            response = self.client.storage.from_(self.bucket).create_signed_url(
                path=storage_path,
                expires_in=expires_in
            )

            return response.get("signedURL")

        except Exception as e:
            logger.debug(
                "act_cache_signed_url_failed",
                normalized_name=normalized_name,
                error=str(e),
            )
            return None

    def delete_cached_act(self, normalized_name: str) -> bool:
        """Delete a cached Act PDF.

        Args:
            normalized_name: Normalized act name.

        Returns:
            True if deletion was successful.
        """
        if self.client is None:
            return False

        storage_path = self._get_storage_path(normalized_name)

        try:
            self.client.storage.from_(self.bucket).remove([storage_path])

            logger.info(
                "act_cache_deleted",
                normalized_name=normalized_name,
            )

            return True

        except Exception as e:
            logger.error(
                "act_cache_delete_failed",
                normalized_name=normalized_name,
                error=str(e),
            )
            return False

    def list_cached_acts(self) -> list[str]:
        """List all cached Act normalized names.

        Returns:
            List of normalized act names that are cached.
        """
        if self.client is None:
            return []

        prefix = self._settings.act_cache_storage_prefix
        try:
            result = self.client.storage.from_(self.bucket).list(
                path=f"{prefix}/",
            )

            cached = []
            if result:
                for file in result:
                    name = file.get("name", "")
                    if name.endswith(".pdf"):
                        # Remove .pdf extension to get normalized name
                        cached.append(name[:-4])

            return cached

        except Exception as e:
            logger.error(
                "act_cache_list_failed",
                error=str(e),
            )
            return []

    def get_cache_stats(self) -> dict:
        """Get statistics about the act cache.

        Returns:
            Dict with cache statistics.
        """
        if self.client is None:
            return {"total_cached": 0, "total_size_bytes": 0}

        prefix = self._settings.act_cache_storage_prefix
        try:
            result = self.client.storage.from_(self.bucket).list(
                path=f"{prefix}/",
            )

            total_cached = 0
            total_size = 0

            if result:
                for file in result:
                    if file.get("name", "").endswith(".pdf"):
                        total_cached += 1
                        total_size += file.get("metadata", {}).get("size", 0)

            return {
                "total_cached": total_cached,
                "total_size_bytes": total_size,
            }

        except Exception as e:
            logger.error(
                "act_cache_stats_failed",
                error=str(e),
            )
            return {"total_cached": 0, "total_size_bytes": 0}


# Singleton instance
_act_cache_service: ActCacheService | None = None


def get_act_cache_service() -> ActCacheService:
    """Get singleton act cache service instance.

    Returns:
        ActCacheService instance.
    """
    global _act_cache_service
    if _act_cache_service is None:
        _act_cache_service = ActCacheService()
    return _act_cache_service
