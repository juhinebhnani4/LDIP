"""Citation service for database operations.

Handles citation creation, retrieval, and bounding box linking
for the Citation Verification Engine.
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


class CitationServiceError(Exception):
    """Base exception for citation service operations."""

    def __init__(self, message: str, code: str = "CITATION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class CitationService:
    """Service for citation database operations.

    Uses the service client to bypass RLS since the backend
    has already validated access via the document's matter.
    """

    def __init__(
        self,
        client: Client | None = None,
        bbox_service: BoundingBoxService | None = None,
    ):
        """Initialize citation service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
            bbox_service: Optional BoundingBoxService. Uses singleton if not provided.
        """
        self.client = client or get_service_client()
        self.bbox_service = bbox_service or get_bounding_box_service()

    def link_citation_to_source_bboxes(
        self,
        citation_id: str,
        bbox_ids: list[str],
    ) -> bool:
        """Link source bounding boxes to a citation.

        Updates the citation's source_bbox_ids array with bounding boxes
        from the case file where the citation was found.

        Args:
            citation_id: Citation UUID.
            bbox_ids: List of bounding box UUIDs from the source document.

        Returns:
            True if link was successful.

        Raises:
            CitationServiceError: If linking fails.
        """
        if self.client is None:
            raise CitationServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        if not bbox_ids:
            logger.warning(
                "citation_source_bbox_link_skipped",
                citation_id=citation_id,
                reason="empty_bbox_ids",
            )
            return True

        try:
            result = (
                self.client.table("citations")
                .update({"source_bbox_ids": bbox_ids})
                .eq("id", citation_id)
                .execute()
            )

            success = bool(result.data)

            logger.info(
                "citation_source_bbox_linked",
                citation_id=citation_id,
                bbox_count=len(bbox_ids),
                success=success,
            )

            return success

        except Exception as e:
            logger.error(
                "citation_source_bbox_link_failed",
                citation_id=citation_id,
                error=str(e),
            )
            raise CitationServiceError(
                message=f"Failed to link source bounding boxes: {e!s}",
                code="SOURCE_LINK_FAILED"
            ) from e

    def link_citation_to_target_bboxes(
        self,
        citation_id: str,
        bbox_ids: list[str],
    ) -> bool:
        """Link target bounding boxes to a citation.

        Updates the citation's target_bbox_ids array with bounding boxes
        from the Act document (the matched/verified section).

        Args:
            citation_id: Citation UUID.
            bbox_ids: List of bounding box UUIDs from the target Act document.

        Returns:
            True if link was successful.

        Raises:
            CitationServiceError: If linking fails.
        """
        if self.client is None:
            raise CitationServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        if not bbox_ids:
            logger.warning(
                "citation_target_bbox_link_skipped",
                citation_id=citation_id,
                reason="empty_bbox_ids",
            )
            return True

        try:
            result = (
                self.client.table("citations")
                .update({"target_bbox_ids": bbox_ids})
                .eq("id", citation_id)
                .execute()
            )

            success = bool(result.data)

            logger.info(
                "citation_target_bbox_linked",
                citation_id=citation_id,
                bbox_count=len(bbox_ids),
                success=success,
            )

            return success

        except Exception as e:
            logger.error(
                "citation_target_bbox_link_failed",
                citation_id=citation_id,
                error=str(e),
            )
            raise CitationServiceError(
                message=f"Failed to link target bounding boxes: {e!s}",
                code="TARGET_LINK_FAILED"
            ) from e

    def get_source_bboxes_for_citation(
        self,
        citation_id: str,
    ) -> list[dict[str, Any]]:
        """Get source bounding boxes for a citation.

        Retrieves the bounding boxes from the case file where
        the citation was found.

        Args:
            citation_id: Citation UUID.

        Returns:
            List of bounding box dictionaries ordered by reading order.

        Raises:
            CitationServiceError: If retrieval fails.
        """
        if self.client is None:
            raise CitationServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            result = (
                self.client.table("citations")
                .select("source_bbox_ids")
                .eq("id", citation_id)
                .execute()
            )

            if not result.data:
                raise CitationServiceError(
                    message="Citation not found",
                    code="CITATION_NOT_FOUND"
                )

            bbox_ids = result.data[0].get("source_bbox_ids") or []

            if not bbox_ids:
                return []

            return self.bbox_service.get_bounding_boxes_by_ids(bbox_ids)

        except CitationServiceError:
            raise
        except Exception as e:
            logger.error(
                "citation_source_bbox_get_failed",
                citation_id=citation_id,
                error=str(e),
            )
            raise CitationServiceError(
                message=f"Failed to get source bounding boxes: {e!s}",
                code="SOURCE_GET_FAILED"
            ) from e

    def get_target_bboxes_for_citation(
        self,
        citation_id: str,
    ) -> list[dict[str, Any]]:
        """Get target bounding boxes for a citation.

        Retrieves the bounding boxes from the Act document that
        match/verify the citation.

        Args:
            citation_id: Citation UUID.

        Returns:
            List of bounding box dictionaries ordered by reading order.

        Raises:
            CitationServiceError: If retrieval fails.
        """
        if self.client is None:
            raise CitationServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            result = (
                self.client.table("citations")
                .select("target_bbox_ids")
                .eq("id", citation_id)
                .execute()
            )

            if not result.data:
                raise CitationServiceError(
                    message="Citation not found",
                    code="CITATION_NOT_FOUND"
                )

            bbox_ids = result.data[0].get("target_bbox_ids") or []

            if not bbox_ids:
                return []

            return self.bbox_service.get_bounding_boxes_by_ids(bbox_ids)

        except CitationServiceError:
            raise
        except Exception as e:
            logger.error(
                "citation_target_bbox_get_failed",
                citation_id=citation_id,
                error=str(e),
            )
            raise CitationServiceError(
                message=f"Failed to get target bounding boxes: {e!s}",
                code="TARGET_GET_FAILED"
            ) from e

    def get_bboxes_for_citation(
        self,
        citation_id: str,
    ) -> dict[str, list[dict[str, Any]]]:
        """Get both source and target bounding boxes for a citation.

        Convenience method for split-view citation highlighting.

        Args:
            citation_id: Citation UUID.

        Returns:
            Dictionary with 'source' and 'target' lists of bounding boxes.

        Raises:
            CitationServiceError: If retrieval fails.
        """
        return {
            "source": self.get_source_bboxes_for_citation(citation_id),
            "target": self.get_target_bboxes_for_citation(citation_id),
        }


@lru_cache(maxsize=1)
def get_citation_service() -> CitationService:
    """Get singleton citation service instance.

    Returns:
        CitationService instance.
    """
    return CitationService()
