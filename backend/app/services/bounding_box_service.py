"""Bounding box service for database operations.

Handles saving and retrieving OCR bounding boxes from the bounding_boxes table.
"""

from functools import lru_cache
from typing import Any

import structlog
from supabase import Client

from app.models.ocr import OCRBoundingBox
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


# Database row to response dictionary mapping
def _row_to_bbox_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert database row to BoundingBox response dictionary.

    Maps snake_case database columns to the response format.
    """
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "page_number": row["page_number"],
        "x": row["x"],
        "y": row["y"],
        "width": row["width"],
        "height": row["height"],
        "text": row["text"],
        "confidence": row["confidence"],
        "reading_order_index": row.get("reading_order_index"),
    }


class BoundingBoxServiceError(Exception):
    """Base exception for bounding box service operations."""

    def __init__(self, message: str, code: str = "BBOX_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class BoundingBoxService:
    """Service for bounding box database operations.

    Uses the service client to bypass RLS since the backend
    has already validated access via the document's matter.
    """

    def __init__(self, client: Client | None = None):
        """Initialize bounding box service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self.client = client or get_service_client()

    def save_bounding_boxes(
        self,
        document_id: str,
        matter_id: str,
        bounding_boxes: list[OCRBoundingBox],
        batch_size: int = 100,
    ) -> int:
        """Save bounding boxes to the database.

        Inserts bounding boxes in batches to handle large documents.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID for RLS.
            bounding_boxes: List of OCRBoundingBox to save.
            batch_size: Number of rows per insert batch.

        Returns:
            Number of bounding boxes saved.

        Raises:
            BoundingBoxServiceError: If save fails.
        """
        if self.client is None:
            raise BoundingBoxServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        if not bounding_boxes:
            logger.info(
                "bounding_boxes_save_skipped",
                document_id=document_id,
                reason="empty_list",
            )
            return 0

        logger.info(
            "bounding_boxes_save_starting",
            document_id=document_id,
            matter_id=matter_id,
            total_boxes=len(bounding_boxes),
        )

        try:
            # Convert to database records
            records = [
                {
                    "matter_id": matter_id,
                    "document_id": document_id,
                    "page_number": bbox.page,
                    "x": bbox.x,
                    "y": bbox.y,
                    "width": bbox.width,
                    "height": bbox.height,
                    "text": bbox.text,
                    "confidence": bbox.confidence,
                    "reading_order_index": bbox.reading_order_index,
                }
                for bbox in bounding_boxes
            ]

            # Insert in batches
            total_saved = 0
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                result = self.client.table("bounding_boxes").insert(batch).execute()
                total_saved += len(result.data) if result.data else 0

            logger.info(
                "bounding_boxes_save_complete",
                document_id=document_id,
                total_saved=total_saved,
            )

            return total_saved

        except Exception as e:
            logger.error(
                "bounding_boxes_save_failed",
                document_id=document_id,
                matter_id=matter_id,
                error=str(e),
            )
            raise BoundingBoxServiceError(
                message=f"Failed to save bounding boxes: {e!s}",
                code="SAVE_FAILED"
            ) from e

    def delete_bounding_boxes(self, document_id: str) -> int:
        """Delete all bounding boxes for a document.

        Used when re-processing OCR for a document.

        Args:
            document_id: Document UUID.

        Returns:
            Number of bounding boxes deleted.

        Raises:
            BoundingBoxServiceError: If deletion fails.
        """
        if self.client is None:
            raise BoundingBoxServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        logger.info(
            "bounding_boxes_delete_starting",
            document_id=document_id,
        )

        try:
            result = self.client.table("bounding_boxes").delete().eq(
                "document_id", document_id
            ).execute()

            deleted_count = len(result.data) if result.data else 0

            logger.info(
                "bounding_boxes_delete_complete",
                document_id=document_id,
                deleted_count=deleted_count,
            )

            return deleted_count

        except Exception as e:
            logger.error(
                "bounding_boxes_delete_failed",
                document_id=document_id,
                error=str(e),
            )
            raise BoundingBoxServiceError(
                message=f"Failed to delete bounding boxes: {e!s}",
                code="DELETE_FAILED"
            ) from e

    def get_bounding_boxes_for_page(
        self,
        document_id: str,
        page_number: int,
    ) -> list[dict[str, Any]]:
        """Get bounding boxes for a specific page, ordered by reading order.

        Args:
            document_id: Document UUID.
            page_number: Page number (1-indexed).

        Returns:
            List of bounding box dictionaries ordered by reading_order_index.

        Raises:
            BoundingBoxServiceError: If retrieval fails.
        """
        if self.client is None:
            raise BoundingBoxServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            result = (
                self.client.table("bounding_boxes")
                .select("*")
                .eq("document_id", document_id)
                .eq("page_number", page_number)
                .order("reading_order_index", desc=False, nullsfirst=False)
                .execute()
            )

            boxes = [_row_to_bbox_dict(row) for row in (result.data or [])]

            logger.debug(
                "bounding_boxes_retrieved_for_page",
                document_id=document_id,
                page_number=page_number,
                box_count=len(boxes),
            )

            return boxes

        except Exception as e:
            logger.error(
                "bounding_boxes_get_page_failed",
                document_id=document_id,
                page_number=page_number,
                error=str(e),
            )
            raise BoundingBoxServiceError(
                message=f"Failed to get bounding boxes for page: {e!s}",
                code="GET_PAGE_FAILED"
            ) from e

    def get_bounding_boxes_for_document(
        self,
        document_id: str,
        page: int | None = None,
        per_page: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get bounding boxes for a document, ordered by page then reading order.

        Args:
            document_id: Document UUID.
            page: Page number for pagination (1-indexed). None for all boxes.
            per_page: Number of boxes per page (default 100, max 500).

        Returns:
            Tuple of (list of bounding box dictionaries, total count).

        Raises:
            BoundingBoxServiceError: If retrieval fails.
        """
        if self.client is None:
            raise BoundingBoxServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            # First get total count
            count_result = (
                self.client.table("bounding_boxes")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .execute()
            )
            total = count_result.count or 0

            # Build query with ordering
            query = (
                self.client.table("bounding_boxes")
                .select("*")
                .eq("document_id", document_id)
                .order("page_number", desc=False)
                .order("reading_order_index", desc=False, nullsfirst=False)
            )

            # Apply pagination if requested
            if page is not None:
                offset = (page - 1) * per_page
                query = query.range(offset, offset + per_page - 1)
            else:
                # Limit to per_page if no pagination
                query = query.limit(per_page)

            result = query.execute()

            boxes = [_row_to_bbox_dict(row) for row in (result.data or [])]

            logger.debug(
                "bounding_boxes_retrieved_for_document",
                document_id=document_id,
                box_count=len(boxes),
                total=total,
            )

            return boxes, total

        except Exception as e:
            logger.error(
                "bounding_boxes_get_document_failed",
                document_id=document_id,
                error=str(e),
            )
            raise BoundingBoxServiceError(
                message=f"Failed to get bounding boxes for document: {e!s}",
                code="GET_DOCUMENT_FAILED"
            ) from e

    def get_bounding_boxes_by_ids(
        self,
        bbox_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Get bounding boxes by their IDs, ordered by reading order.

        Useful for retrieving boxes linked to chunks or citations.

        Args:
            bbox_ids: List of bounding box UUIDs.

        Returns:
            List of bounding box dictionaries ordered by reading_order_index.

        Raises:
            BoundingBoxServiceError: If retrieval fails.
        """
        if self.client is None:
            raise BoundingBoxServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        if not bbox_ids:
            return []

        try:
            result = (
                self.client.table("bounding_boxes")
                .select("*")
                .in_("id", bbox_ids)
                .order("page_number", desc=False)
                .order("reading_order_index", desc=False, nullsfirst=False)
                .execute()
            )

            boxes = [_row_to_bbox_dict(row) for row in (result.data or [])]

            logger.debug(
                "bounding_boxes_retrieved_by_ids",
                requested_count=len(bbox_ids),
                retrieved_count=len(boxes),
            )

            return boxes

        except Exception as e:
            logger.error(
                "bounding_boxes_get_by_ids_failed",
                bbox_ids=bbox_ids[:5],  # Log first 5 IDs only
                error=str(e),
            )
            raise BoundingBoxServiceError(
                message=f"Failed to get bounding boxes by IDs: {e!s}",
                code="GET_BY_IDS_FAILED"
            ) from e


@lru_cache(maxsize=1)
def get_bounding_box_service() -> BoundingBoxService:
    """Get singleton bounding box service instance.

    Returns:
        BoundingBoxService instance.
    """
    return BoundingBoxService()
