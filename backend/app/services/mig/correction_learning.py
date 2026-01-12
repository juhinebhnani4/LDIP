"""Correction Learning Service for Alias Resolution.

Tracks user corrections to auto-detected aliases and uses them to
improve future alias resolution. Implements:
1. Recording corrections (add, remove, merge)
2. Querying correction history
3. Applying learned patterns to boost/suppress alias confidence

Learning approach:
- If user added alias A->B, boost future A->B similarity
- If user removed alias A->B, suppress future A->B similarity
- Track patterns across matters for global learning (future)
"""

import asyncio
from dataclasses import dataclass
from functools import lru_cache

import structlog

from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AliasCorrection:
    """Represents a single alias correction."""

    id: str
    matter_id: str
    entity_id: str
    correction_type: str  # 'add', 'remove', 'merge'
    alias_name: str | None
    merged_entity_id: str | None
    merged_entity_name: str | None
    original_confidence: float | None
    corrected_by: str
    reason: str | None
    created_at: str


@dataclass
class CorrectionStats:
    """Statistics about corrections for a matter."""

    total_corrections: int
    add_count: int
    remove_count: int
    merge_count: int
    unique_entities: int
    unique_correctors: int


# =============================================================================
# Service Implementation
# =============================================================================


class CorrectionLearningService:
    """Service for tracking and learning from alias corrections.

    Records user corrections and uses them to improve future alias
    detection. Corrections create a feedback loop that makes the
    system smarter over time.
    """

    def __init__(self) -> None:
        """Initialize correction learning service."""
        self.client = get_service_client()

    # =========================================================================
    # Record Corrections
    # =========================================================================

    async def record_correction(
        self,
        matter_id: str,
        entity_id: str,
        correction_type: str,
        corrected_by: str,
        alias_name: str | None = None,
        merged_entity_id: str | None = None,
        merged_entity_name: str | None = None,
        reason: str | None = None,
        original_confidence: float | None = None,
        metadata: dict | None = None,
    ) -> AliasCorrection | None:
        """Record an alias correction (add, remove, or merge).

        Unified method for recording any type of correction. Routes to the
        appropriate internal method based on correction_type.

        Args:
            matter_id: Matter UUID.
            entity_id: Entity UUID.
            correction_type: Type of correction ('add', 'remove', 'merge').
            corrected_by: User ID who made the correction.
            alias_name: The alias name (for add/remove).
            merged_entity_id: Source entity ID (for merge).
            merged_entity_name: Source entity name (for merge).
            reason: Optional reason for the correction.
            original_confidence: Original auto-detection confidence.
            metadata: Additional context for learning.

        Returns:
            Created AliasCorrection or None if failed.
        """
        return await self._record_correction(
            matter_id=matter_id,
            entity_id=entity_id,
            correction_type=correction_type,
            alias_name=alias_name,
            merged_entity_id=merged_entity_id,
            merged_entity_name=merged_entity_name,
            corrected_by=corrected_by,
            reason=reason,
            original_confidence=original_confidence,
            metadata=metadata,
        )

    async def record_add_correction(
        self,
        matter_id: str,
        entity_id: str,
        alias_name: str,
        corrected_by: str,
        reason: str | None = None,
        original_confidence: float | None = None,
        metadata: dict | None = None,
    ) -> AliasCorrection | None:
        """Record an alias addition correction.

        Called when a user manually adds an alias to an entity.

        Args:
            matter_id: Matter UUID.
            entity_id: Entity UUID that received the alias.
            alias_name: The alias name that was added.
            corrected_by: User ID who made the correction.
            reason: Optional reason for adding.
            original_confidence: Original auto-detection confidence (if any).
            metadata: Additional context for learning.

        Returns:
            Created AliasCorrection or None if failed.
        """
        return await self._record_correction(
            matter_id=matter_id,
            entity_id=entity_id,
            correction_type="add",
            alias_name=alias_name,
            corrected_by=corrected_by,
            reason=reason,
            original_confidence=original_confidence,
            metadata=metadata,
        )

    async def record_remove_correction(
        self,
        matter_id: str,
        entity_id: str,
        alias_name: str,
        corrected_by: str,
        reason: str | None = None,
        original_confidence: float | None = None,
        metadata: dict | None = None,
    ) -> AliasCorrection | None:
        """Record an alias removal correction.

        Called when a user manually removes an alias from an entity.

        Args:
            matter_id: Matter UUID.
            entity_id: Entity UUID that lost the alias.
            alias_name: The alias name that was removed.
            corrected_by: User ID who made the correction.
            reason: Optional reason for removal.
            original_confidence: Original auto-detection confidence.
            metadata: Additional context for learning.

        Returns:
            Created AliasCorrection or None if failed.
        """
        return await self._record_correction(
            matter_id=matter_id,
            entity_id=entity_id,
            correction_type="remove",
            alias_name=alias_name,
            corrected_by=corrected_by,
            reason=reason,
            original_confidence=original_confidence,
            metadata=metadata,
        )

    async def record_merge_correction(
        self,
        matter_id: str,
        kept_entity_id: str,
        merged_entity_id: str,
        merged_entity_name: str,
        corrected_by: str,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> AliasCorrection | None:
        """Record an entity merge correction.

        Called when a user manually merges two entities.

        Args:
            matter_id: Matter UUID.
            kept_entity_id: Entity UUID that was kept.
            merged_entity_id: Entity UUID that was merged (deleted).
            merged_entity_name: Name of the merged entity (preserved).
            corrected_by: User ID who made the correction.
            reason: Optional reason for merge.
            metadata: Additional context for learning.

        Returns:
            Created AliasCorrection or None if failed.
        """
        return await self._record_correction(
            matter_id=matter_id,
            entity_id=kept_entity_id,
            correction_type="merge",
            merged_entity_id=merged_entity_id,
            merged_entity_name=merged_entity_name,
            corrected_by=corrected_by,
            reason=reason,
            metadata=metadata,
        )

    async def _record_correction(
        self,
        matter_id: str,
        entity_id: str,
        correction_type: str,
        corrected_by: str,
        alias_name: str | None = None,
        merged_entity_id: str | None = None,
        merged_entity_name: str | None = None,
        reason: str | None = None,
        original_confidence: float | None = None,
        metadata: dict | None = None,
    ) -> AliasCorrection | None:
        """Internal method to record a correction."""
        if self.client is None:
            logger.error("correction_learning_no_client")
            return None

        def _insert():
            return (
                self.client.table("alias_corrections")
                .insert({
                    "matter_id": matter_id,
                    "entity_id": entity_id,
                    "correction_type": correction_type,
                    "alias_name": alias_name,
                    "merged_entity_id": merged_entity_id,
                    "merged_entity_name": merged_entity_name,
                    "original_confidence": original_confidence,
                    "corrected_by": corrected_by,
                    "reason": reason,
                    "metadata": metadata or {},
                })
                .execute()
            )

        try:
            response = await asyncio.to_thread(_insert)

            if response.data:
                row = response.data[0]
                logger.info(
                    "correction_recorded",
                    matter_id=matter_id,
                    entity_id=entity_id,
                    correction_type=correction_type,
                    alias_name=alias_name,
                )
                return self._row_to_correction(row)

        except Exception as e:
            logger.error(
                "correction_record_failed",
                matter_id=matter_id,
                entity_id=entity_id,
                error=str(e),
            )

        return None

    # =========================================================================
    # Query Corrections
    # =========================================================================

    async def get_correction_stats(self, matter_id: str) -> CorrectionStats | None:
        """Get correction statistics for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            CorrectionStats or None if failed.
        """
        if self.client is None:
            return None

        def _query():
            return self.client.rpc(
                "get_correction_stats",
                {"p_matter_id": matter_id},
            ).execute()

        try:
            response = await asyncio.to_thread(_query)

            if response.data and len(response.data) > 0:
                row = response.data[0]
                return CorrectionStats(
                    total_corrections=row["total_corrections"],
                    add_count=row["add_count"],
                    remove_count=row["remove_count"],
                    merge_count=row["merge_count"],
                    unique_entities=row["unique_entities"],
                    unique_correctors=row["unique_correctors"],
                )

        except Exception as e:
            logger.error(
                "correction_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )

        return None

    async def get_recent_corrections(
        self,
        matter_id: str,
        limit: int = 100,
    ) -> list[AliasCorrection]:
        """Get recent corrections for a matter.

        Args:
            matter_id: Matter UUID.
            limit: Maximum number of corrections to return.

        Returns:
            List of recent corrections.
        """
        if self.client is None:
            return []

        def _query():
            return (
                self.client.table("alias_corrections")
                .select("*")
                .eq("matter_id", matter_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_query)

            if response.data:
                return [self._row_to_correction(row) for row in response.data]

        except Exception as e:
            logger.error(
                "recent_corrections_failed",
                matter_id=matter_id,
                error=str(e),
            )

        return []

    async def get_corrections_for_entity(
        self,
        entity_id: str,
        matter_id: str,
    ) -> list[AliasCorrection]:
        """Get all corrections for a specific entity.

        Args:
            entity_id: Entity UUID.
            matter_id: Matter UUID.

        Returns:
            List of corrections for the entity.
        """
        if self.client is None:
            return []

        def _query():
            return (
                self.client.table("alias_corrections")
                .select("*")
                .eq("matter_id", matter_id)
                .eq("entity_id", entity_id)
                .order("created_at", desc=True)
                .execute()
            )

        try:
            response = await asyncio.to_thread(_query)

            if response.data:
                return [self._row_to_correction(row) for row in response.data]

        except Exception as e:
            logger.error(
                "entity_corrections_failed",
                entity_id=entity_id,
                error=str(e),
            )

        return []

    # =========================================================================
    # Learning: Confidence Adjustment
    # =========================================================================

    async def get_learned_adjustments(
        self,
        matter_id: str,
        name1: str,
        name2: str,
    ) -> float:
        """Get learned confidence adjustment for a name pair.

        Based on correction history, returns an adjustment to apply
        to the similarity score:
        - Positive adjustment if user previously added this alias pair
        - Negative adjustment if user previously removed this alias pair
        - Zero if no relevant corrections found

        Args:
            matter_id: Matter UUID.
            name1: First name in the pair.
            name2: Second name in the pair.

        Returns:
            Confidence adjustment (-0.3 to +0.3).
        """
        if self.client is None:
            return 0.0

        # Query corrections involving these names
        def _query():
            return (
                self.client.table("alias_corrections")
                .select("correction_type, alias_name, merged_entity_name")
                .eq("matter_id", matter_id)
                .or_(
                    f"alias_name.ilike.{name1},alias_name.ilike.{name2},"
                    f"merged_entity_name.ilike.{name1},merged_entity_name.ilike.{name2}"
                )
                .execute()
            )

        try:
            response = await asyncio.to_thread(_query)

            if not response.data:
                return 0.0

            # Count adds vs removes for this pair
            add_count = 0
            remove_count = 0

            name1_lower = name1.lower()
            name2_lower = name2.lower()

            for row in response.data:
                alias = (row.get("alias_name") or "").lower()
                merged = (row.get("merged_entity_name") or "").lower()
                corr_type = row.get("correction_type")

                # Check if this correction involves both names
                names_in_correction = {alias, merged}
                if name1_lower in names_in_correction or name2_lower in names_in_correction:
                    if corr_type == "add" or corr_type == "merge":
                        add_count += 1
                    elif corr_type == "remove":
                        remove_count += 1

            # Calculate adjustment
            if add_count > remove_count:
                # User has linked these names - boost confidence
                return min(0.3, 0.1 * (add_count - remove_count))
            elif remove_count > add_count:
                # User has unlinked these names - reduce confidence
                return max(-0.3, -0.1 * (remove_count - add_count))

        except Exception as e:
            logger.error(
                "learned_adjustments_failed",
                matter_id=matter_id,
                error=str(e),
            )

        return 0.0

    # =========================================================================
    # Helpers
    # =========================================================================

    def _row_to_correction(self, row: dict) -> AliasCorrection:
        """Convert database row to AliasCorrection."""
        return AliasCorrection(
            id=row["id"],
            matter_id=row["matter_id"],
            entity_id=row["entity_id"],
            correction_type=row["correction_type"],
            alias_name=row.get("alias_name"),
            merged_entity_id=row.get("merged_entity_id"),
            merged_entity_name=row.get("merged_entity_name"),
            original_confidence=row.get("original_confidence"),
            corrected_by=row["corrected_by"],
            reason=row.get("reason"),
            created_at=row["created_at"],
        )


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_correction_learning_service() -> CorrectionLearningService:
    """Get singleton correction learning service instance.

    Returns:
        CorrectionLearningService instance.
    """
    return CorrectionLearningService()
