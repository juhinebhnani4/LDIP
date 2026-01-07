"""Bounding box service for database operations.

Handles saving OCR bounding boxes to the bounding_boxes table.
"""

from functools import lru_cache

import structlog
from supabase import Client

from app.models.ocr import OCRBoundingBox
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


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


@lru_cache(maxsize=1)
def get_bounding_box_service() -> BoundingBoxService:
    """Get singleton bounding box service instance.

    Returns:
        BoundingBoxService instance.
    """
    return BoundingBoxService()
