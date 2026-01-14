"""Verification service for managing finding verifications.

Story 8-4: Implement Finding Verifications Table
Epic 8: Safety Layer (Guardrails, Policing, Verification)

This service provides:
- Creation of verification records when findings are generated
- Recording attorney verification decisions
- Retrieval of pending verifications for queue UI
- Statistics for dashboard
- Bulk verification operations

Implements:
- FR10: Attorney Verification Workflow
- NFR23: Court-defensible verification workflow with forensic trail
- ADR-004: Verification Tier Thresholds (>90% optional, 70-90% suggested, <70% required)
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings
from app.models.verification import (
    FindingVerification,
    FindingVerificationCreate,
    FindingVerificationUpdate,
    VerificationDecision,
    VerificationQueueItem,
    VerificationRequirement,
    VerificationStats,
)

if TYPE_CHECKING:
    from supabase import Client

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 8-4: Exceptions
# =============================================================================


class VerificationServiceError(Exception):
    """Base exception for verification service operations.

    Story 8-4: Exception hierarchy for verification service.
    """

    def __init__(
        self,
        message: str,
        code: str = "VERIFICATION_SERVICE_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class VerificationNotFoundError(VerificationServiceError):
    """Raised when verification record is not found.

    Story 8-4: Not found error for specific verification.
    """

    def __init__(self, verification_id: str):
        super().__init__(
            f"Verification record not found: {verification_id}",
            code="VERIFICATION_NOT_FOUND",
            is_retryable=False,
        )


# =============================================================================
# Story 8-4: VerificationService (Task 4.1-4.8)
# =============================================================================


class VerificationService:
    """Service for managing finding verifications.

    Story 8-4: Implements tiered verification per ADR-004.

    Threshold Logic:
    - > 90% confidence: OPTIONAL (informational only)
    - 70-90% confidence: SUGGESTED (warning shown)
    - < 70% confidence: REQUIRED (blocks export)

    Example:
        >>> service = get_verification_service()
        >>> record = await service.create_verification_record(
        ...     create_data=FindingVerificationCreate(
        ...         matter_id="uuid",
        ...         finding_id="uuid",
        ...         finding_type="citation_mismatch",
        ...         finding_summary="Section 138 citation mismatch",
        ...         confidence_before=85.0,
        ...     ),
        ...     supabase=supabase_client,
        ... )
    """

    def __init__(self) -> None:
        """Initialize verification service.

        Story 8-4: Task 4.1 - Service initialization.
        """
        settings = get_settings()
        self._threshold_optional = settings.verification_threshold_optional
        self._threshold_suggested = settings.verification_threshold_suggested

        logger.info(
            "verification_service_initialized",
            threshold_optional=self._threshold_optional,
            threshold_suggested=self._threshold_suggested,
        )

    def get_verification_requirement(
        self, confidence: float
    ) -> VerificationRequirement:
        """Determine verification requirement based on confidence.

        Story 8-4: AC #3-5, Task 4.3 - Tiered verification per ADR-004.

        Args:
            confidence: Finding confidence (0-100 scale).

        Returns:
            OPTIONAL if > 90%, SUGGESTED if > 70% and <= 90%, REQUIRED if <= 70%.
        """
        if confidence > self._threshold_optional:
            return VerificationRequirement.OPTIONAL
        elif confidence > self._threshold_suggested:
            return VerificationRequirement.SUGGESTED
        else:
            return VerificationRequirement.REQUIRED

    async def create_verification_record(
        self,
        create_data: FindingVerificationCreate,
        supabase: Client,
    ) -> FindingVerification:
        """Create verification record when finding is generated.

        Story 8-4: AC #1, Task 4.2 - Automatic record creation.

        Args:
            create_data: Finding data for verification.
            supabase: Supabase client.

        Returns:
            Created FindingVerification record.

        Raises:
            VerificationServiceError: If creation fails.
        """
        start_time = time.perf_counter()

        requirement = self.get_verification_requirement(create_data.confidence_before)

        try:
            result = supabase.table("finding_verifications").insert({
                "matter_id": create_data.matter_id,
                "finding_id": create_data.finding_id,
                "finding_type": create_data.finding_type,
                "finding_summary": create_data.finding_summary[:500],  # Truncate
                "confidence_before": create_data.confidence_before,
                "decision": VerificationDecision.PENDING.value,
            }).execute()

            if not result.data:
                raise VerificationServiceError(
                    "Failed to create verification record: No data returned",
                    code="INSERT_FAILED",
                )

            record = result.data[0]
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "verification_record_created",
                verification_id=record["id"],
                finding_id=create_data.finding_id,
                finding_type=create_data.finding_type,
                confidence=create_data.confidence_before,
                requirement=requirement.value,
                elapsed_ms=round(elapsed_ms, 2),
            )

            return self._to_model(record)

        except Exception as e:
            if isinstance(e, VerificationServiceError):
                raise

            logger.error(
                "verification_record_creation_failed",
                finding_id=create_data.finding_id,
                error=str(e),
            )
            raise VerificationServiceError(
                f"Failed to create verification record: {e}",
                is_retryable=True,
            ) from e

    async def record_verification_decision(
        self,
        verification_id: str,
        update_data: FindingVerificationUpdate,
        verified_by: str,
        supabase: Client,
    ) -> FindingVerification:
        """Record attorney verification decision.

        Story 8-4: AC #2, Task 4.4 - Attorney approval/rejection.

        Args:
            verification_id: UUID of verification record.
            update_data: Decision and notes.
            verified_by: UUID of verifying attorney.
            supabase: Supabase client.

        Returns:
            Updated FindingVerification record.

        Raises:
            VerificationNotFoundError: If verification not found.
            VerificationServiceError: If update fails.
        """
        start_time = time.perf_counter()

        update_fields: dict = {
            "decision": update_data.decision.value,
            "verified_by": verified_by,
            "verified_at": datetime.now(UTC).isoformat(),
        }

        if update_data.confidence_after is not None:
            update_fields["confidence_after"] = update_data.confidence_after
        if update_data.notes is not None:
            update_fields["notes"] = update_data.notes[:2000]  # Truncate

        try:
            result = supabase.table("finding_verifications").update(
                update_fields
            ).eq("id", verification_id).execute()

            if not result.data:
                raise VerificationNotFoundError(verification_id)

            record = result.data[0]
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "verification_decision_recorded",
                verification_id=verification_id,
                decision=update_data.decision.value,
                verified_by=verified_by,
                elapsed_ms=round(elapsed_ms, 2),
            )

            return self._to_model(record)

        except VerificationNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "verification_decision_failed",
                verification_id=verification_id,
                error=str(e),
            )
            raise VerificationServiceError(
                f"Failed to record verification decision: {e}",
                is_retryable=True,
            ) from e

    async def get_verification_by_id(
        self,
        verification_id: str,
        supabase: Client,
    ) -> FindingVerification:
        """Get verification record by ID.

        Story 8-4: Task 4.7 - Lookup by verification ID.

        Args:
            verification_id: UUID of verification record.
            supabase: Supabase client.

        Returns:
            FindingVerification record.

        Raises:
            VerificationNotFoundError: If not found.
        """
        try:
            result = supabase.table("finding_verifications").select(
                "*"
            ).eq("id", verification_id).execute()

            if not result.data:
                raise VerificationNotFoundError(verification_id)

            return self._to_model(result.data[0])

        except VerificationNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "verification_lookup_failed",
                verification_id=verification_id,
                error=str(e),
            )
            raise VerificationServiceError(
                f"Failed to get verification: {e}",
                is_retryable=True,
            ) from e

    async def get_verification_by_finding(
        self,
        finding_id: str,
        supabase: Client,
    ) -> FindingVerification | None:
        """Get verification record by finding ID.

        Story 8-4: Task 4.7 - Lookup by finding_id.

        Args:
            finding_id: UUID of finding.
            supabase: Supabase client.

        Returns:
            FindingVerification record or None if not found.
        """
        try:
            result = supabase.table("finding_verifications").select(
                "*"
            ).eq("finding_id", finding_id).execute()

            if not result.data:
                return None

            return self._to_model(result.data[0])

        except Exception as e:
            logger.error(
                "verification_lookup_by_finding_failed",
                finding_id=finding_id,
                error=str(e),
            )
            raise VerificationServiceError(
                f"Failed to get verification by finding: {e}",
                is_retryable=True,
            ) from e

    async def list_verifications(
        self,
        matter_id: str,
        supabase: Client,
        decision: VerificationDecision | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FindingVerification]:
        """List verification records for a matter.

        Story 8-4: Task 7.2 - List verifications with optional filtering.

        Args:
            matter_id: Matter UUID.
            supabase: Supabase client.
            decision: Optional decision filter.
            limit: Max items to return.
            offset: Number of items to skip.

        Returns:
            List of FindingVerification records.
        """
        try:
            query = supabase.table("finding_verifications").select(
                "*"
            ).eq("matter_id", matter_id)

            if decision is not None:
                query = query.eq("decision", decision.value)

            result = query.order(
                "created_at", desc=True
            ).range(offset, offset + limit - 1).execute()

            return [self._to_model(r) for r in result.data]

        except Exception as e:
            logger.error(
                "list_verifications_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise VerificationServiceError(
                f"Failed to list verifications: {e}",
                is_retryable=True,
            ) from e

    async def get_pending_verifications(
        self,
        matter_id: str,
        supabase: Client,
        limit: int = 50,
    ) -> list[VerificationQueueItem]:
        """Get pending verifications for queue UI.

        Story 8-4: Task 4.5 - For Story 8-5 verification queue display.
        Orders by requirement priority (REQUIRED first) and then by creation date.

        Args:
            matter_id: Matter UUID.
            supabase: Supabase client.
            limit: Max items to return.

        Returns:
            List of VerificationQueueItem for UI display.
        """
        start_time = time.perf_counter()

        try:
            result = supabase.table("finding_verifications").select(
                "*"
            ).eq("matter_id", matter_id).eq(
                "decision", VerificationDecision.PENDING.value
            ).order(
                "confidence_before", desc=False  # Low confidence first (REQUIRED)
            ).order(
                "created_at", desc=False  # Oldest first
            ).limit(limit).execute()

            items = [self._to_queue_item(r) for r in result.data]

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.debug(
                "pending_verifications_retrieved",
                matter_id=matter_id,
                count=len(items),
                elapsed_ms=round(elapsed_ms, 2),
            )

            return items

        except Exception as e:
            logger.error(
                "get_pending_verifications_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise VerificationServiceError(
                f"Failed to get pending verifications: {e}",
                is_retryable=True,
            ) from e

    async def get_verification_stats(
        self,
        matter_id: str,
        supabase: Client,
    ) -> VerificationStats:
        """Get verification statistics for dashboard.

        Story 8-4: Task 4.6 - Aggregate stats for matter.

        Args:
            matter_id: Matter UUID.
            supabase: Supabase client.

        Returns:
            VerificationStats with counts and export status.
        """
        start_time = time.perf_counter()

        try:
            result = supabase.table("finding_verifications").select(
                "*"
            ).eq("matter_id", matter_id).execute()

            records = result.data

            stats = VerificationStats()
            stats.total_verifications = len(records)

            for r in records:
                decision = r["decision"]
                confidence = r["confidence_before"]

                if decision == VerificationDecision.PENDING.value:
                    stats.pending_count += 1
                    requirement = self.get_verification_requirement(confidence)

                    if requirement == VerificationRequirement.REQUIRED:
                        stats.required_pending += 1
                        stats.blocking_count += 1
                    elif requirement == VerificationRequirement.SUGGESTED:
                        stats.suggested_pending += 1
                    else:
                        stats.optional_pending += 1

                elif decision == VerificationDecision.APPROVED.value:
                    stats.approved_count += 1
                elif decision == VerificationDecision.REJECTED.value:
                    stats.rejected_count += 1
                elif decision == VerificationDecision.FLAGGED.value:
                    stats.flagged_count += 1

            stats.export_blocked = stats.blocking_count > 0

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.debug(
                "verification_stats_retrieved",
                matter_id=matter_id,
                total=stats.total_verifications,
                pending=stats.pending_count,
                blocking=stats.blocking_count,
                elapsed_ms=round(elapsed_ms, 2),
            )

            return stats

        except Exception as e:
            logger.error(
                "get_verification_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise VerificationServiceError(
                f"Failed to get verification stats: {e}",
                is_retryable=True,
            ) from e

    async def bulk_update_verifications(
        self,
        verification_ids: list[str],
        decision: VerificationDecision,
        verified_by: str,
        supabase: Client,
        notes: str | None = None,
    ) -> dict:
        """Bulk update verification decisions.

        Story 8-4: Task 4.8 - Bulk approve/reject for Story 8-5 queue UI.

        NOTE: Current implementation uses individual updates per ID due to
        Supabase Python client limitations with bulk WHERE IN updates.
        Performance is acceptable for max 100 items per request.
        Consider PostgreSQL function for high-volume scenarios.

        Args:
            verification_ids: List of verification UUIDs.
            decision: Decision to apply to all.
            verified_by: UUID of verifying attorney.
            supabase: Supabase client.
            notes: Optional notes for all verifications.

        Returns:
            Dict with updated_count and failed_ids.
        """
        start_time = time.perf_counter()

        if len(verification_ids) > 100:
            raise VerificationServiceError(
                "Bulk update limited to 100 records at a time",
                code="BULK_LIMIT_EXCEEDED",
                is_retryable=False,
            )

        update_fields: dict = {
            "decision": decision.value,
            "verified_by": verified_by,
            "verified_at": datetime.now(UTC).isoformat(),
        }

        if notes is not None:
            update_fields["notes"] = notes[:2000]

        updated_count = 0
        failed_ids: list[str] = []

        for verification_id in verification_ids:
            try:
                result = supabase.table("finding_verifications").update(
                    update_fields
                ).eq("id", verification_id).execute()

                if result.data:
                    updated_count += 1
                else:
                    failed_ids.append(verification_id)

            except Exception as e:
                logger.warning(
                    "bulk_update_item_failed",
                    verification_id=verification_id,
                    error=str(e),
                )
                failed_ids.append(verification_id)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "bulk_verification_update_complete",
            total=len(verification_ids),
            updated=updated_count,
            failed=len(failed_ids),
            decision=decision.value,
            verified_by=verified_by,
            elapsed_ms=round(elapsed_ms, 2),
        )

        return {
            "updated_count": updated_count,
            "failed_ids": failed_ids,
            "total_requested": len(verification_ids),
        }

    def _to_model(self, record: dict) -> FindingVerification:
        """Convert database record to Pydantic model.

        Story 8-4: Internal helper for model conversion.

        Args:
            record: Database record dict.

        Returns:
            FindingVerification model.
        """
        return FindingVerification(
            id=record["id"],
            matter_id=record["matter_id"],
            finding_id=record.get("finding_id"),
            finding_type=record["finding_type"],
            finding_summary=record["finding_summary"],
            confidence_before=record["confidence_before"],
            decision=VerificationDecision(record["decision"]),
            verified_by=record.get("verified_by"),
            verified_at=record.get("verified_at"),
            confidence_after=record.get("confidence_after"),
            notes=record.get("notes"),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            verification_requirement=self.get_verification_requirement(
                record["confidence_before"]
            ),
        )

    def _extract_engine_from_finding_type(self, finding_type: str) -> str:
        """Extract engine name from finding type.

        Story 8-4: Code Review Fix - Use explicit mapping for robustness.

        Args:
            finding_type: Finding type string (e.g., "citation_mismatch").

        Returns:
            Engine name string.
        """
        # Explicit mapping for known finding types
        engine_mapping = {
            "citation_mismatch": "citation",
            "citation_verification_failed": "citation",
            "timeline_gap": "timeline",
            "timeline_anomaly": "timeline",
            "contradiction_detected": "contradiction",
            "contradiction_statement": "contradiction",
            "rag_low_confidence": "rag",
            "entity_mismatch": "entity",
            "entity_unresolved": "entity",
        }

        # Return mapped engine or extract from prefix as fallback
        if finding_type in engine_mapping:
            return engine_mapping[finding_type]

        # Fallback: use first word before underscore
        return finding_type.split("_")[0] if "_" in finding_type else finding_type

    def _to_queue_item(self, record: dict) -> VerificationQueueItem:
        """Convert database record to queue item for UI.

        Story 8-4: Internal helper for queue item conversion.

        Args:
            record: Database record dict.

        Returns:
            VerificationQueueItem for queue UI.
        """
        finding_type = record["finding_type"]
        engine = self._extract_engine_from_finding_type(finding_type)

        return VerificationQueueItem(
            id=record["id"],
            finding_id=record.get("finding_id"),
            finding_type=finding_type,
            finding_summary=record["finding_summary"],
            confidence=record["confidence_before"],
            requirement=self.get_verification_requirement(record["confidence_before"]),
            decision=VerificationDecision(record["decision"]),
            created_at=record["created_at"],
            source_document=None,  # Would require join with findings table
            engine=engine,
        )


# =============================================================================
# Story 8-4: Singleton Factory
# =============================================================================

# Singleton instance (thread-safe)
_verification_service: VerificationService | None = None
_service_lock = threading.Lock()


def get_verification_service() -> VerificationService:
    """Get singleton VerificationService instance.

    Story 8-4: Thread-safe singleton factory.

    Returns:
        VerificationService singleton instance.
    """
    global _verification_service  # noqa: PLW0603

    if _verification_service is None:
        with _service_lock:
            # Double-check locking pattern
            if _verification_service is None:
                _verification_service = VerificationService()

    return _verification_service


def reset_verification_service() -> None:
    """Reset singleton for testing.

    Story 8-4: Reset function for test isolation.
    """
    global _verification_service  # noqa: PLW0603

    with _service_lock:
        _verification_service = None

    logger.debug("verification_service_reset")
