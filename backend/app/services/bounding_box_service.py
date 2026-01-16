"""Bounding box service for database operations.

Handles saving and retrieving OCR bounding boxes from the bounding_boxes table.

Story 17.5: Batch Bounding Box Inserts
- Configurable batch size (default 500 for chunked documents)
- Parallel batch inserts using thread pool
- Performance logging for insert operations
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Any

import structlog
from supabase import Client

from app.models.ocr import OCRBoundingBox
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)

# Story 17.5: Batch insert configuration
DEFAULT_BATCH_SIZE = 500  # Increased from 100 for better throughput
PARALLEL_BATCH_THRESHOLD = 1000  # Use parallel inserts above this count
MAX_PARALLEL_BATCHES = 4  # Max concurrent batch inserts


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
        batch_size: int = DEFAULT_BATCH_SIZE,
        use_parallel: bool | None = None,
    ) -> int:
        """Save bounding boxes to the database.

        Story 17.5: Enhanced with batch inserts and optional parallelism.
        - Inserts in configurable batches (default 500)
        - Uses parallel inserts for large datasets (>1000 boxes)
        - Detailed performance logging

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID for RLS.
            bounding_boxes: List of OCRBoundingBox to save.
            batch_size: Number of rows per insert batch (default 500).
            use_parallel: Force parallel inserts. Auto-detects if None.

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

        start_time = time.time()
        total_boxes = len(bounding_boxes)

        # Auto-detect parallel mode based on count
        if use_parallel is None:
            use_parallel = total_boxes >= PARALLEL_BATCH_THRESHOLD

        logger.info(
            "bounding_boxes_save_starting",
            document_id=document_id,
            matter_id=matter_id,
            total_boxes=total_boxes,
            batch_size=batch_size,
            use_parallel=use_parallel,
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

            # Create batches
            batches = [
                records[i : i + batch_size]
                for i in range(0, len(records), batch_size)
            ]

            if use_parallel and len(batches) > 1:
                total_saved = self._insert_batches_parallel(batches)
            else:
                total_saved = self._insert_batches_sequential(batches)

            elapsed_ms = int((time.time() - start_time) * 1000)
            boxes_per_second = round(total_saved / (elapsed_ms / 1000), 1) if elapsed_ms > 0 else 0

            logger.info(
                "bounding_boxes_save_complete",
                document_id=document_id,
                total_saved=total_saved,
                batch_count=len(batches),
                elapsed_ms=elapsed_ms,
                boxes_per_second=boxes_per_second,
                use_parallel=use_parallel,
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

    def _insert_batches_sequential(self, batches: list[list[dict]]) -> int:
        """Insert batches sequentially.

        Args:
            batches: List of record batches to insert.

        Returns:
            Total number of records inserted.
        """
        total_saved = 0
        for i, batch in enumerate(batches):
            result = self.client.table("bounding_boxes").insert(batch).execute()
            saved = len(result.data) if result.data else 0
            total_saved += saved
            logger.debug(
                "bbox_batch_inserted",
                batch_index=i,
                batch_size=len(batch),
                saved=saved,
            )
        return total_saved

    def _insert_batches_parallel(self, batches: list[list[dict]]) -> int:
        """Insert batches in parallel using thread pool.

        Story 17.5: Parallel batch inserts for large documents.

        Args:
            batches: List of record batches to insert.

        Returns:
            Total number of records inserted.
        """
        total_saved = 0

        def insert_batch(batch_data: tuple[int, list[dict]]) -> tuple[int, int]:
            """Insert a single batch and return (index, count)."""
            idx, batch = batch_data
            result = self.client.table("bounding_boxes").insert(batch).execute()
            return idx, len(result.data) if result.data else 0

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_BATCHES) as executor:
            futures = {
                executor.submit(insert_batch, (i, batch)): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(futures):
                try:
                    idx, saved = future.result()
                    total_saved += saved
                    logger.debug(
                        "bbox_batch_inserted_parallel",
                        batch_index=idx,
                        saved=saved,
                    )
                except Exception as e:
                    batch_idx = futures[future]
                    logger.error(
                        "bbox_batch_insert_failed",
                        batch_index=batch_idx,
                        error=str(e),
                    )
                    raise

        return total_saved

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


    # =========================================================================
    # Bbox Reference Validation (Story 17.8)
    # =========================================================================

    def validate_bbox_references(
        self,
        bbox_ids: list[str],
        document_id: str | None = None,
    ) -> tuple[list[str], list[str]]:
        """Validate that bounding box references exist in the database.

        Story 17.8: Ensures entity mentions and citations only reference
        valid bounding boxes that exist in the database.

        Args:
            bbox_ids: List of bounding box UUIDs to validate.
            document_id: Optional document ID to scope validation.

        Returns:
            Tuple of (valid_ids, invalid_ids).
            valid_ids contains bbox IDs that exist in DB.
            invalid_ids contains bbox IDs that don't exist.

        Raises:
            BoundingBoxServiceError: If validation query fails.
        """
        if self.client is None:
            raise BoundingBoxServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        if not bbox_ids:
            return [], []

        try:
            # Query for existence of all bbox IDs
            query = (
                self.client.table("bounding_boxes")
                .select("id")
                .in_("id", bbox_ids)
            )

            if document_id:
                query = query.eq("document_id", document_id)

            result = query.execute()

            existing_ids = {row["id"] for row in (result.data or [])}
            valid_ids = [bid for bid in bbox_ids if bid in existing_ids]
            invalid_ids = [bid for bid in bbox_ids if bid not in existing_ids]

            if invalid_ids:
                logger.warning(
                    "bbox_reference_validation_failures",
                    document_id=document_id,
                    valid_count=len(valid_ids),
                    invalid_count=len(invalid_ids),
                    invalid_ids=invalid_ids[:10],  # Log first 10 only
                )
            else:
                logger.debug(
                    "bbox_reference_validation_passed",
                    document_id=document_id,
                    validated_count=len(valid_ids),
                )

            return valid_ids, invalid_ids

        except Exception as e:
            logger.error(
                "bbox_reference_validation_failed",
                document_id=document_id,
                bbox_count=len(bbox_ids),
                error=str(e),
            )
            raise BoundingBoxServiceError(
                message=f"Failed to validate bbox references: {e!s}",
                code="VALIDATION_FAILED"
            ) from e

    def cleanup_invalid_bbox_references(
        self,
        document_id: str,
    ) -> dict[str, int]:
        """Clean up invalid bbox references in citations and entities.

        Story 17.8: After re-OCR processing, some bbox IDs may no longer
        be valid. This method identifies and removes invalid references
        from citations and entity mentions.

        Args:
            document_id: Document UUID to clean up references for.

        Returns:
            Dict with cleanup statistics:
            - citations_updated: Number of citations with references cleaned
            - entities_updated: Number of entities with references cleaned
            - invalid_refs_removed: Total invalid references removed

        Raises:
            BoundingBoxServiceError: If cleanup fails.
        """
        if self.client is None:
            raise BoundingBoxServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            stats = {
                "citations_updated": 0,
                "entities_updated": 0,
                "invalid_refs_removed": 0,
            }

            # Get all valid bbox IDs for this document
            valid_bboxes_result = (
                self.client.table("bounding_boxes")
                .select("id")
                .eq("document_id", document_id)
                .execute()
            )
            valid_bbox_ids = {row["id"] for row in (valid_bboxes_result.data or [])}

            # Clean up citations with invalid source_bbox_ids
            citations_result = (
                self.client.table("citations")
                .select("id, source_bbox_ids, target_bbox_ids")
                .eq("document_id", document_id)
                .execute()
            )

            for citation in (citations_result.data or []):
                citation_id = citation["id"]
                updated = False
                update_data = {}

                # Validate source_bbox_ids
                source_ids = citation.get("source_bbox_ids") or []
                if source_ids:
                    valid_source = [bid for bid in source_ids if bid in valid_bbox_ids]
                    if len(valid_source) != len(source_ids):
                        update_data["source_bbox_ids"] = valid_source
                        stats["invalid_refs_removed"] += len(source_ids) - len(valid_source)
                        updated = True

                # Validate target_bbox_ids
                target_ids = citation.get("target_bbox_ids") or []
                if target_ids:
                    valid_target = [bid for bid in target_ids if bid in valid_bbox_ids]
                    if len(valid_target) != len(target_ids):
                        update_data["target_bbox_ids"] = valid_target
                        stats["invalid_refs_removed"] += len(target_ids) - len(valid_target)
                        updated = True

                if updated:
                    self.client.table("citations").update(update_data).eq("id", citation_id).execute()
                    stats["citations_updated"] += 1

            # Clean up entity_mentions with invalid bbox_ids
            entities_result = (
                self.client.table("entity_mentions")
                .select("id, bbox_ids")
                .eq("document_id", document_id)
                .execute()
            )

            for entity in (entities_result.data or []):
                entity_id = entity["id"]
                bbox_ids = entity.get("bbox_ids") or []

                if bbox_ids:
                    valid_entity_bboxes = [bid for bid in bbox_ids if bid in valid_bbox_ids]
                    if len(valid_entity_bboxes) != len(bbox_ids):
                        self.client.table("entity_mentions").update(
                            {"bbox_ids": valid_entity_bboxes}
                        ).eq("id", entity_id).execute()
                        stats["entities_updated"] += 1
                        stats["invalid_refs_removed"] += len(bbox_ids) - len(valid_entity_bboxes)

            logger.info(
                "bbox_reference_cleanup_complete",
                document_id=document_id,
                **stats,
            )

            return stats

        except Exception as e:
            logger.error(
                "bbox_reference_cleanup_failed",
                document_id=document_id,
                error=str(e),
            )
            raise BoundingBoxServiceError(
                message=f"Failed to cleanup bbox references: {e!s}",
                code="CLEANUP_FAILED"
            ) from e


@lru_cache(maxsize=1)
def get_bounding_box_service() -> BoundingBoxService:
    """Get singleton bounding box service instance.

    Returns:
        BoundingBoxService instance.
    """
    return BoundingBoxService()
