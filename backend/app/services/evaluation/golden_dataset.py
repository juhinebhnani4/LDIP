"""Golden dataset management for evaluation.

Story: RAG Production Gaps - Feature 2: Evaluation Framework
Manages QA pairs used as ground truth for evaluation.
"""

from __future__ import annotations

import structlog

from app.services.evaluation.models import GoldenDatasetItem
from app.services.supabase.client import get_supabase_client as get_supabase

logger = structlog.get_logger(__name__)


class GoldenDatasetError(Exception):
    """Base exception for golden dataset operations."""

    def __init__(
        self,
        message: str,
        code: str = "GOLDEN_DATASET_ERROR",
    ):
        self.message = message
        self.code = code
        super().__init__(message)


class GoldenDatasetService:
    """Manage golden QA pairs for RAG evaluation.

    The golden dataset contains verified QA pairs that serve as
    ground truth for measuring RAG quality. Each item includes:
    - A question that users might ask
    - The expected correct answer
    - Optionally, the chunk IDs that should be retrieved
    - Tags for filtering by topic/intent

    Example:
        >>> service = GoldenDatasetService()
        >>> item = GoldenDatasetItem(
        ...     matter_id="matter-123",
        ...     question="What is the penalty for Section 138?",
        ...     expected_answer="Imprisonment up to 2 years...",
        ...     tags=["citation", "penalty"],
        ... )
        >>> created = await service.add_item(item)
    """

    def __init__(self) -> None:
        """Initialize golden dataset service."""
        self._supabase = None

    @property
    def supabase(self):
        """Lazy-load Supabase client."""
        if self._supabase is None:
            self._supabase = get_supabase()
        return self._supabase

    async def add_item(self, item: GoldenDatasetItem) -> GoldenDatasetItem:
        """Add a QA pair to the golden dataset.

        Args:
            item: GoldenDatasetItem to add.

        Returns:
            GoldenDatasetItem with ID populated.

        Raises:
            GoldenDatasetError: If insertion fails.
        """
        try:
            result = self.supabase.table("golden_dataset").insert({
                "matter_id": item.matter_id,
                "question": item.question,
                "expected_answer": item.expected_answer,
                "relevant_chunk_ids": item.relevant_chunk_ids,
                "tags": item.tags,
                "created_by": item.created_by,
            }).execute()

            if not result.data:
                raise GoldenDatasetError("Insert returned no data")

            created_data = result.data[0]

            logger.info(
                "golden_item_added",
                matter_id=item.matter_id,
                item_id=created_data["id"],
                question_preview=item.question[:50],
                tags=item.tags,
            )

            return GoldenDatasetItem(
                id=created_data["id"],
                matter_id=created_data["matter_id"],
                question=created_data["question"],
                expected_answer=created_data["expected_answer"],
                relevant_chunk_ids=created_data.get("relevant_chunk_ids", []),
                tags=created_data.get("tags", []),
                created_by=created_data.get("created_by"),
                created_at=created_data.get("created_at"),
                updated_at=created_data.get("updated_at"),
            )

        except GoldenDatasetError:
            raise

        except Exception as e:
            logger.error(
                "golden_item_add_failed",
                matter_id=item.matter_id,
                error=str(e),
            )
            raise GoldenDatasetError(f"Failed to add golden item: {e}") from e

    async def get_items(
        self,
        matter_id: str,
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[GoldenDatasetItem]:
        """Get golden dataset items for a matter.

        Args:
            matter_id: Matter UUID for isolation.
            tags: Optional tags to filter by (items must have ALL tags).
            limit: Maximum items to return.
            offset: Offset for pagination.

        Returns:
            List of GoldenDatasetItem objects.
        """
        try:
            query = (
                self.supabase.table("golden_dataset")
                .select("*")
                .eq("matter_id", matter_id)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
            )

            if tags:
                # Filter by tags (contains all specified tags)
                query = query.contains("tags", tags)

            result = query.execute()

            logger.debug(
                "golden_items_retrieved",
                matter_id=matter_id,
                count=len(result.data),
                tags=tags,
            )

            return [
                GoldenDatasetItem(
                    id=item["id"],
                    matter_id=item["matter_id"],
                    question=item["question"],
                    expected_answer=item["expected_answer"],
                    relevant_chunk_ids=item.get("relevant_chunk_ids", []),
                    tags=item.get("tags", []),
                    created_by=item.get("created_by"),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                )
                for item in result.data
            ]

        except Exception as e:
            logger.error(
                "golden_items_get_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise GoldenDatasetError(f"Failed to get golden items: {e}") from e

    async def get_item(self, item_id: str, matter_id: str) -> GoldenDatasetItem | None:
        """Get a single golden dataset item.

        Args:
            item_id: Item UUID.
            matter_id: Matter UUID for isolation check.

        Returns:
            GoldenDatasetItem or None if not found.
        """
        try:
            result = (
                self.supabase.table("golden_dataset")
                .select("*")
                .eq("id", item_id)
                .eq("matter_id", matter_id)
                .maybe_single()
                .execute()
            )

            if not result.data:
                return None

            item = result.data
            return GoldenDatasetItem(
                id=item["id"],
                matter_id=item["matter_id"],
                question=item["question"],
                expected_answer=item["expected_answer"],
                relevant_chunk_ids=item.get("relevant_chunk_ids", []),
                tags=item.get("tags", []),
                created_by=item.get("created_by"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
            )

        except Exception as e:
            logger.error(
                "golden_item_get_failed",
                item_id=item_id,
                matter_id=matter_id,
                error=str(e),
            )
            raise GoldenDatasetError(f"Failed to get golden item: {e}") from e

    async def update_item(
        self,
        item_id: str,
        matter_id: str,
        updates: dict,
    ) -> GoldenDatasetItem | None:
        """Update a golden dataset item.

        Args:
            item_id: Item UUID.
            matter_id: Matter UUID for isolation check.
            updates: Dictionary of fields to update.

        Returns:
            Updated GoldenDatasetItem or None if not found.
        """
        try:
            # Only allow specific fields to be updated
            allowed_fields = {"question", "expected_answer", "relevant_chunk_ids", "tags"}
            filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

            if not filtered_updates:
                return await self.get_item(item_id, matter_id)

            result = (
                self.supabase.table("golden_dataset")
                .update(filtered_updates)
                .eq("id", item_id)
                .eq("matter_id", matter_id)
                .execute()
            )

            if not result.data:
                return None

            logger.info(
                "golden_item_updated",
                item_id=item_id,
                matter_id=matter_id,
                updated_fields=list(filtered_updates.keys()),
            )

            return await self.get_item(item_id, matter_id)

        except Exception as e:
            logger.error(
                "golden_item_update_failed",
                item_id=item_id,
                matter_id=matter_id,
                error=str(e),
            )
            raise GoldenDatasetError(f"Failed to update golden item: {e}") from e

    async def delete_item(self, item_id: str, matter_id: str) -> bool:
        """Delete a golden dataset item.

        Args:
            item_id: Item UUID.
            matter_id: Matter UUID for isolation check.

        Returns:
            True if deleted, False if not found.
        """
        try:
            result = (
                self.supabase.table("golden_dataset")
                .delete()
                .eq("id", item_id)
                .eq("matter_id", matter_id)
                .execute()
            )

            deleted = len(result.data) > 0

            if deleted:
                logger.info(
                    "golden_item_deleted",
                    item_id=item_id,
                    matter_id=matter_id,
                )

            return deleted

        except Exception as e:
            logger.error(
                "golden_item_delete_failed",
                item_id=item_id,
                matter_id=matter_id,
                error=str(e),
            )
            raise GoldenDatasetError(f"Failed to delete golden item: {e}") from e

    async def count_items(self, matter_id: str) -> int:
        """Count golden dataset items for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            Count of items.
        """
        try:
            result = (
                self.supabase.table("golden_dataset")
                .select("*", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )

            return result.count or 0

        except Exception as e:
            logger.error(
                "golden_items_count_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return 0
