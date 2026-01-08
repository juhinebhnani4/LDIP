"""Chunk-to-BoundingBox linking service.

Handles linking chunks to bounding boxes via the bbox_ids array column
in the chunks table. This enables text highlighting for search results
and citations.
"""

from functools import lru_cache
from typing import Any

import structlog
from supabase import Client

from app.services.supabase.client import get_service_client
from app.services.bounding_box_service import (
    BoundingBoxService,
    get_bounding_box_service,
)

logger = structlog.get_logger(__name__)


class ChunkBBoxLinkerError(Exception):
    """Base exception for chunk-bbox linking operations."""

    def __init__(self, message: str, code: str = "CHUNK_BBOX_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ChunkBBoxLinker:
    """Service for linking chunks to bounding boxes.

    Uses the existing bbox_ids array column in the chunks table
    to store references to bounding boxes for text highlighting.
    """

    def __init__(
        self,
        client: Client | None = None,
        bbox_service: BoundingBoxService | None = None,
    ):
        """Initialize chunk-bbox linker.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
            bbox_service: Optional BoundingBoxService. Uses singleton if not provided.
        """
        self.client = client or get_service_client()
        self.bbox_service = bbox_service or get_bounding_box_service()

    def link_chunk_to_bboxes(
        self,
        chunk_id: str,
        bbox_ids: list[str],
    ) -> bool:
        """Link a chunk to bounding boxes.

        Updates the chunk's bbox_ids array with the provided bounding box IDs.

        Args:
            chunk_id: Chunk UUID.
            bbox_ids: List of bounding box UUIDs to link.

        Returns:
            True if link was successful.

        Raises:
            ChunkBBoxLinkerError: If linking fails.
        """
        if self.client is None:
            raise ChunkBBoxLinkerError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        if not bbox_ids:
            logger.warning(
                "chunk_bbox_link_skipped",
                chunk_id=chunk_id,
                reason="empty_bbox_ids",
            )
            return True

        try:
            result = (
                self.client.table("chunks")
                .update({"bbox_ids": bbox_ids})
                .eq("id", chunk_id)
                .execute()
            )

            success = bool(result.data)

            logger.info(
                "chunk_bbox_linked",
                chunk_id=chunk_id,
                bbox_count=len(bbox_ids),
                success=success,
            )

            return success

        except Exception as e:
            logger.error(
                "chunk_bbox_link_failed",
                chunk_id=chunk_id,
                bbox_count=len(bbox_ids),
                error=str(e),
            )
            raise ChunkBBoxLinkerError(
                message=f"Failed to link chunk to bounding boxes: {e!s}",
                code="LINK_FAILED"
            ) from e

    def add_bboxes_to_chunk(
        self,
        chunk_id: str,
        bbox_ids: list[str],
    ) -> bool:
        """Add bounding boxes to a chunk's existing bbox_ids.

        Appends new bbox_ids to any existing ones (deduplicating).

        Args:
            chunk_id: Chunk UUID.
            bbox_ids: List of bounding box UUIDs to add.

        Returns:
            True if addition was successful.

        Raises:
            ChunkBBoxLinkerError: If operation fails.
        """
        if self.client is None:
            raise ChunkBBoxLinkerError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        if not bbox_ids:
            return True

        try:
            # Get existing bbox_ids
            result = (
                self.client.table("chunks")
                .select("bbox_ids")
                .eq("id", chunk_id)
                .execute()
            )

            if not result.data:
                raise ChunkBBoxLinkerError(
                    message="Chunk not found",
                    code="CHUNK_NOT_FOUND"
                )

            existing_ids = result.data[0].get("bbox_ids") or []

            # Merge and deduplicate
            merged_ids = list(set(existing_ids + bbox_ids))

            # Update with merged list
            return self.link_chunk_to_bboxes(chunk_id, merged_ids)

        except ChunkBBoxLinkerError:
            raise
        except Exception as e:
            logger.error(
                "chunk_bbox_add_failed",
                chunk_id=chunk_id,
                error=str(e),
            )
            raise ChunkBBoxLinkerError(
                message=f"Failed to add bounding boxes to chunk: {e!s}",
                code="ADD_FAILED"
            ) from e

    def get_bboxes_for_chunk(
        self,
        chunk_id: str,
    ) -> list[dict[str, Any]]:
        """Get bounding boxes for a chunk.

        Retrieves the bounding boxes linked to a chunk via its bbox_ids array.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            List of bounding box dictionaries ordered by reading order.

        Raises:
            ChunkBBoxLinkerError: If retrieval fails.
        """
        if self.client is None:
            raise ChunkBBoxLinkerError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            # Get chunk's bbox_ids
            result = (
                self.client.table("chunks")
                .select("bbox_ids")
                .eq("id", chunk_id)
                .execute()
            )

            if not result.data:
                raise ChunkBBoxLinkerError(
                    message="Chunk not found",
                    code="CHUNK_NOT_FOUND"
                )

            bbox_ids = result.data[0].get("bbox_ids") or []

            if not bbox_ids:
                return []

            # Get bounding boxes by IDs using the bbox service
            return self.bbox_service.get_bounding_boxes_by_ids(bbox_ids)

        except ChunkBBoxLinkerError:
            raise
        except Exception as e:
            logger.error(
                "chunk_bbox_get_failed",
                chunk_id=chunk_id,
                error=str(e),
            )
            raise ChunkBBoxLinkerError(
                message=f"Failed to get bounding boxes for chunk: {e!s}",
                code="GET_FAILED"
            ) from e

    def clear_chunk_bboxes(
        self,
        chunk_id: str,
    ) -> bool:
        """Clear all bounding box links from a chunk.

        Sets the chunk's bbox_ids to an empty array.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            True if clear was successful.

        Raises:
            ChunkBBoxLinkerError: If operation fails.
        """
        if self.client is None:
            raise ChunkBBoxLinkerError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            result = (
                self.client.table("chunks")
                .update({"bbox_ids": []})
                .eq("id", chunk_id)
                .execute()
            )

            success = bool(result.data)

            logger.info(
                "chunk_bboxes_cleared",
                chunk_id=chunk_id,
                success=success,
            )

            return success

        except Exception as e:
            logger.error(
                "chunk_bbox_clear_failed",
                chunk_id=chunk_id,
                error=str(e),
            )
            raise ChunkBBoxLinkerError(
                message=f"Failed to clear chunk bounding boxes: {e!s}",
                code="CLEAR_FAILED"
            ) from e


@lru_cache(maxsize=1)
def get_chunk_bbox_linker() -> ChunkBBoxLinker:
    """Get singleton chunk-bbox linker instance.

    Returns:
        ChunkBBoxLinker instance.
    """
    return ChunkBBoxLinker()
