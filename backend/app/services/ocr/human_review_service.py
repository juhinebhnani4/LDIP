"""Human review queue service for OCR validation.

Manages the queue of words requiring human review due to very low
OCR confidence (<50%).
"""

from datetime import UTC, datetime
from functools import lru_cache

import structlog
from supabase import Client

from app.models.ocr_validation import (
    CorrectionType,
    HumanReviewItem,
    HumanReviewStatus,
    LowConfidenceWord,
    ValidationResult,
)
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


class HumanReviewServiceError(Exception):
    """Base exception for human review service operations."""

    def __init__(self, message: str, code: str = "HUMAN_REVIEW_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class HumanReviewService:
    """Service for managing the human review queue.

    Handles adding items to the review queue, retrieving pending reviews,
    and submitting corrections.
    """

    def __init__(self, client: Client | None = None):
        """Initialize human review service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self.client = client or get_service_client()

    def add_to_queue(
        self,
        document_id: str,
        matter_id: str,
        words: list[LowConfidenceWord],
    ) -> int:
        """Add low-confidence words to the human review queue.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID.
            words: List of words requiring human review.

        Returns:
            Number of items added to the queue.

        Raises:
            HumanReviewServiceError: If adding fails.
        """
        if self.client is None:
            raise HumanReviewServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        if not words:
            return 0

        logger.info(
            "human_review_adding_items",
            document_id=document_id,
            matter_id=matter_id,
            word_count=len(words),
        )

        try:
            records = [
                {
                    "document_id": document_id,
                    "matter_id": matter_id,
                    "bbox_id": word.bbox_id,
                    "original_text": word.text,
                    "context_before": word.context_before,
                    "context_after": word.context_after,
                    "page_number": word.page,
                    "status": HumanReviewStatus.PENDING.value,
                }
                for word in words
            ]

            result = self.client.table("ocr_human_review").insert(records).execute()

            added_count = len(result.data) if result.data else 0

            logger.info(
                "human_review_items_added",
                document_id=document_id,
                added_count=added_count,
            )

            return added_count

        except Exception as e:
            logger.error(
                "human_review_add_failed",
                document_id=document_id,
                error=str(e),
            )
            raise HumanReviewServiceError(
                message=f"Failed to add items to review queue: {e!s}",
                code="ADD_FAILED"
            ) from e

    def get_pending_reviews(
        self,
        matter_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[HumanReviewItem], int]:
        """Get pending review items for a matter.

        Args:
            matter_id: Matter UUID.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (items, total_count).

        Raises:
            HumanReviewServiceError: If retrieval fails.
        """
        if self.client is None:
            raise HumanReviewServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            # Get total count
            count_result = self.client.table("ocr_human_review").select(
                "id", count="exact"
            ).eq(
                "matter_id", matter_id
            ).eq(
                "status", HumanReviewStatus.PENDING.value
            ).execute()

            total_count = count_result.count or 0

            # Get paginated items
            offset = (page - 1) * per_page
            result = self.client.table("ocr_human_review").select(
                "*"
            ).eq(
                "matter_id", matter_id
            ).eq(
                "status", HumanReviewStatus.PENDING.value
            ).order(
                "created_at"
            ).range(
                offset, offset + per_page - 1
            ).execute()

            items = [
                HumanReviewItem(
                    id=row["id"],
                    document_id=row["document_id"],
                    matter_id=row["matter_id"],
                    bbox_id=row.get("bbox_id"),
                    original_text=row["original_text"],
                    context_before=row.get("context_before"),
                    context_after=row.get("context_after"),
                    page_number=row["page_number"],
                    status=HumanReviewStatus(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                )
                for row in result.data
            ] if result.data else []

            return items, total_count

        except Exception as e:
            logger.error(
                "human_review_get_pending_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise HumanReviewServiceError(
                message=f"Failed to get pending reviews: {e!s}",
                code="GET_PENDING_FAILED"
            ) from e

    def get_reviews_by_document(
        self,
        document_id: str,
    ) -> list[HumanReviewItem]:
        """Get all review items for a document.

        Args:
            document_id: Document UUID.

        Returns:
            List of review items.

        Raises:
            HumanReviewServiceError: If retrieval fails.
        """
        if self.client is None:
            raise HumanReviewServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            result = self.client.table("ocr_human_review").select(
                "*"
            ).eq(
                "document_id", document_id
            ).order(
                "page_number"
            ).execute()

            items = [
                HumanReviewItem(
                    id=row["id"],
                    document_id=row["document_id"],
                    matter_id=row["matter_id"],
                    bbox_id=row.get("bbox_id"),
                    original_text=row["original_text"],
                    context_before=row.get("context_before"),
                    context_after=row.get("context_after"),
                    page_number=row["page_number"],
                    status=HumanReviewStatus(row["status"]),
                    corrected_text=row.get("corrected_text"),
                    reviewed_by=row.get("reviewed_by"),
                    reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if row.get("reviewed_at") else None,
                    created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                )
                for row in result.data
            ] if result.data else []

            return items

        except Exception as e:
            logger.error(
                "human_review_get_by_document_failed",
                document_id=document_id,
                error=str(e),
            )
            raise HumanReviewServiceError(
                message=f"Failed to get reviews for document: {e!s}",
                code="GET_BY_DOCUMENT_FAILED"
            ) from e

    def submit_correction(
        self,
        review_id: str,
        corrected_text: str,
        user_id: str,
        authorized_matter_id: str | None = None,
    ) -> ValidationResult:
        """Submit a human correction for a review item.

        Args:
            review_id: Review item UUID.
            corrected_text: Human-corrected text.
            user_id: UUID of the reviewing user.
            authorized_matter_id: Matter ID the user is authorized for (CRITICAL for IDOR prevention).

        Returns:
            ValidationResult with the correction.

        Raises:
            HumanReviewServiceError: If submission fails or user not authorized.
        """
        if self.client is None:
            raise HumanReviewServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            # Get the review item first
            item_result = self.client.table("ocr_human_review").select(
                "*"
            ).eq(
                "id", review_id
            ).single().execute()

            if not item_result.data:
                raise HumanReviewServiceError(
                    message=f"Review item {review_id} not found",
                    code="ITEM_NOT_FOUND"
                )

            item = item_result.data

            # CRITICAL: Validate matter_id matches authorized matter (IDOR prevention)
            if authorized_matter_id and item["matter_id"] != authorized_matter_id:
                logger.warning(
                    "human_review_idor_attempt",
                    review_id=review_id,
                    item_matter_id=item["matter_id"],
                    authorized_matter_id=authorized_matter_id,
                    user_id=user_id,
                )
                raise HumanReviewServiceError(
                    message=f"Review item {review_id} not found",
                    code="ITEM_NOT_FOUND"  # Don't reveal the item exists in another matter
                )

            original_text = item["original_text"]

            # Update the review item
            now = datetime.now(UTC).isoformat()
            self.client.table("ocr_human_review").update({
                "corrected_text": corrected_text,
                "status": HumanReviewStatus.COMPLETED.value,
                "reviewed_by": user_id,
                "reviewed_at": now,
            }).eq(
                "id", review_id
            ).execute()

            # Update the bounding box if bbox_id exists
            bbox_id = item.get("bbox_id")
            if bbox_id and corrected_text != original_text:
                self.client.table("bounding_boxes").update({
                    "text": corrected_text,
                    "confidence": 1.0,  # Human-verified = 100% confidence
                }).eq(
                    "id", bbox_id
                ).execute()

            was_corrected = corrected_text != original_text

            # Log the correction to validation log (per AC #4)
            if was_corrected:
                self.client.table("ocr_validation_log").insert({
                    "document_id": item["document_id"],
                    "bbox_id": bbox_id,
                    "original_text": original_text,
                    "corrected_text": corrected_text,
                    "old_confidence": 0.0,  # Was below human threshold
                    "new_confidence": 1.0,  # Human-verified
                    "validation_type": "human",
                    "reasoning": f"Human correction by user {user_id}",
                }).execute()

            logger.info(
                "human_review_correction_submitted",
                review_id=review_id,
                user_id=user_id,
                was_corrected=was_corrected,
            )

            return ValidationResult(
                bbox_id=bbox_id or "",
                original=original_text,
                corrected=corrected_text,
                old_confidence=0.0,  # Was below human threshold
                new_confidence=1.0,  # Human-verified
                correction_type=CorrectionType.HUMAN if was_corrected else None,
                reasoning="Human-verified correction" if was_corrected else "Human-verified as correct",
                was_corrected=was_corrected,
            )

        except HumanReviewServiceError:
            raise
        except Exception as e:
            logger.error(
                "human_review_submit_failed",
                review_id=review_id,
                error=str(e),
            )
            raise HumanReviewServiceError(
                message=f"Failed to submit correction: {e!s}",
                code="SUBMIT_FAILED"
            ) from e

    def skip_review(
        self,
        review_id: str,
        user_id: str,
        authorized_matter_id: str | None = None,
    ) -> None:
        """Skip a review item (accept original text).

        Args:
            review_id: Review item UUID.
            user_id: UUID of the reviewing user.
            authorized_matter_id: Matter ID the user is authorized for (CRITICAL for IDOR prevention).

        Raises:
            HumanReviewServiceError: If skipping fails or user not authorized.
        """
        if self.client is None:
            raise HumanReviewServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            # CRITICAL: Validate matter_id matches authorized matter (IDOR prevention)
            if authorized_matter_id:
                item_result = self.client.table("ocr_human_review").select(
                    "id, matter_id"
                ).eq(
                    "id", review_id
                ).single().execute()

                if not item_result.data:
                    raise HumanReviewServiceError(
                        message=f"Review item {review_id} not found",
                        code="ITEM_NOT_FOUND"
                    )

                if item_result.data["matter_id"] != authorized_matter_id:
                    logger.warning(
                        "human_review_skip_idor_attempt",
                        review_id=review_id,
                        item_matter_id=item_result.data["matter_id"],
                        authorized_matter_id=authorized_matter_id,
                        user_id=user_id,
                    )
                    raise HumanReviewServiceError(
                        message=f"Review item {review_id} not found",
                        code="ITEM_NOT_FOUND"  # Don't reveal the item exists in another matter
                    )

            now = datetime.now(UTC).isoformat()
            self.client.table("ocr_human_review").update({
                "status": HumanReviewStatus.SKIPPED.value,
                "reviewed_by": user_id,
                "reviewed_at": now,
            }).eq(
                "id", review_id
            ).execute()

            logger.info(
                "human_review_skipped",
                review_id=review_id,
                user_id=user_id,
            )

        except Exception as e:
            logger.error(
                "human_review_skip_failed",
                review_id=review_id,
                error=str(e),
            )
            raise HumanReviewServiceError(
                message=f"Failed to skip review: {e!s}",
                code="SKIP_FAILED"
            ) from e

    def add_pages_to_queue(
        self,
        document_id: str,
        matter_id: str,
        pages: list[int],
    ) -> int:
        """Add specific pages to the human review queue.

        Used when user explicitly requests manual review for poor OCR pages.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID.
            pages: List of page numbers to flag for review.

        Returns:
            Number of items added to the queue.

        Raises:
            HumanReviewServiceError: If adding fails.
        """
        if self.client is None:
            raise HumanReviewServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        if not pages:
            return 0

        logger.info(
            "human_review_adding_pages",
            document_id=document_id,
            matter_id=matter_id,
            page_count=len(pages),
            pages=pages,
        )

        try:
            records = [
                {
                    "document_id": document_id,
                    "matter_id": matter_id,
                    "bbox_id": None,  # Page-level review, not bbox-specific
                    "original_text": f"[Page {page} manual review requested]",
                    "context_before": None,
                    "context_after": None,
                    "page_number": page,
                    "status": HumanReviewStatus.PENDING.value,
                }
                for page in pages
            ]

            result = self.client.table("ocr_human_review").insert(records).execute()

            added_count = len(result.data) if result.data else 0

            # Update document validation status to indicate manual review requested
            self.client.table("documents").update({
                "validation_status": "requires_human_review",
            }).eq("id", document_id).execute()

            logger.info(
                "human_review_pages_added",
                document_id=document_id,
                added_count=added_count,
            )

            return added_count

        except Exception as e:
            logger.error(
                "human_review_add_pages_failed",
                document_id=document_id,
                error=str(e),
            )
            raise HumanReviewServiceError(
                message=f"Failed to add pages to review queue: {e!s}",
                code="ADD_PAGES_FAILED"
            ) from e

    def get_review_stats(
        self,
        matter_id: str,
    ) -> dict[str, int]:
        """Get review statistics for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            Dictionary with counts for each status.

        Raises:
            HumanReviewServiceError: If retrieval fails.
        """
        if self.client is None:
            raise HumanReviewServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED"
            )

        try:
            result = self.client.table("ocr_human_review").select(
                "status"
            ).eq(
                "matter_id", matter_id
            ).execute()

            stats = {
                "pending": 0,
                "completed": 0,
                "skipped": 0,
                "total": 0,
            }

            if result.data:
                for row in result.data:
                    status = row["status"]
                    if status in stats:
                        stats[status] += 1
                    stats["total"] += 1

            return stats

        except Exception as e:
            logger.error(
                "human_review_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise HumanReviewServiceError(
                message=f"Failed to get review stats: {e!s}",
                code="STATS_FAILED"
            ) from e


@lru_cache(maxsize=1)
def get_human_review_service() -> HumanReviewService:
    """Get singleton human review service instance.

    Returns:
        HumanReviewService instance.
    """
    return HumanReviewService()
