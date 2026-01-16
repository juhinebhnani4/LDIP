"""Anomaly service for database operations.

Handles saving and retrieving detected timeline anomalies
for attorney review.

Story 4-4: Timeline Anomaly Detection
"""

from datetime import UTC, datetime
from functools import lru_cache
from math import ceil

import structlog

from app.models.anomaly import (
    AnomaliesListResponse,
    Anomaly,
    AnomalyCreate,
    AnomalyListItem,
    AnomalySeverity,
    AnomalySummaryData,
    AnomalySummaryResponse,
    AnomalyType,
    PaginationMeta,
)
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class AnomalyServiceError(Exception):
    """Base exception for anomaly service operations."""

    def __init__(self, message: str, code: str = "ANOMALY_SERVICE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class AnomalyNotFoundError(AnomalyServiceError):
    """Raised when anomaly is not found."""

    def __init__(self, message: str):
        super().__init__(message, code="ANOMALY_NOT_FOUND")


# =============================================================================
# Service Implementation
# =============================================================================


class AnomalyService:
    """Service for anomaly database operations.

    Handles CRUD operations for the anomalies table.
    Uses the service client to bypass RLS since the backend
    has already validated access via the matter.
    """

    def __init__(self) -> None:
        """Initialize anomaly service."""
        self._client = None

    @property
    def client(self):
        """Get Supabase service client.

        Raises:
            AnomalyServiceError: If Supabase is not configured.
        """
        if self._client is None:
            self._client = get_service_client()
            if self._client is None:
                raise AnomalyServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                )
        return self._client

    async def save_anomalies(
        self,
        anomalies: list[AnomalyCreate],
    ) -> list[str]:
        """Save detected anomalies to database.

        Args:
            anomalies: List of AnomalyCreate objects.

        Returns:
            List of created anomaly UUIDs.

        Raises:
            AnomalyServiceError: If save fails.
        """
        if not anomalies:
            return []

        # Convert to database records
        records = []
        for anomaly in anomalies:
            record = {
                "matter_id": anomaly.matter_id,
                "anomaly_type": anomaly.anomaly_type.value,
                "severity": anomaly.severity.value,
                "title": anomaly.title,
                "explanation": anomaly.explanation,
                "event_ids": anomaly.event_ids,
                "confidence": anomaly.confidence,
            }

            if anomaly.expected_order:
                record["expected_order"] = anomaly.expected_order
            if anomaly.actual_order:
                record["actual_order"] = anomaly.actual_order
            if anomaly.gap_days is not None:
                record["gap_days"] = anomaly.gap_days

            records.append(record)

        try:
            response = self.client.table("anomalies").insert(records).execute()

            created_ids = [item["id"] for item in response.data]

            logger.info(
                "anomalies_saved",
                count=len(created_ids),
                matter_id=anomalies[0].matter_id if anomalies else None,
            )

            return created_ids

        except Exception as e:
            logger.error(
                "anomaly_save_failed",
                error=str(e),
            )
            raise AnomalyServiceError(
                f"Failed to save anomalies: {e}",
                code="ANOMALY_SAVE_FAILED",
            )

    def save_anomalies_sync(
        self,
        anomalies: list[AnomalyCreate],
    ) -> list[str]:
        """Synchronous wrapper for save_anomalies (for Celery tasks)."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context (shouldn't happen in Celery, but handle it)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.save_anomalies(anomalies))
                return future.result()
        else:
            return asyncio.run(self.save_anomalies(anomalies))

    async def get_anomalies_for_matter(
        self,
        matter_id: str,
        page: int = 1,
        per_page: int = 20,
        severity: str | None = None,
        anomaly_type: str | None = None,
        dismissed: bool | None = None,
    ) -> AnomaliesListResponse:
        """Get paginated anomalies for a matter.

        Args:
            matter_id: Matter UUID.
            page: Page number (1-indexed).
            per_page: Items per page.
            severity: Optional severity filter.
            anomaly_type: Optional type filter.
            dismissed: Optional dismissed filter (True/False/None).

        Returns:
            AnomaliesListResponse with paginated anomalies.
        """
        try:
            # Build query
            query = self.client.table("anomalies").select(
                "*", count="exact"
            ).eq("matter_id", matter_id)

            # Apply filters
            if severity:
                query = query.eq("severity", severity)
            if anomaly_type:
                query = query.eq("anomaly_type", anomaly_type)
            if dismissed is not None:
                query = query.eq("dismissed", dismissed)

            # Order by severity (critical > high > medium > low), then by date
            # Note: Custom ordering requires a different approach
            # For now, order by created_at DESC
            query = query.order("created_at", desc=True)

            # Apply pagination
            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            response = query.execute()

            # Map to response models
            items = []
            for row in response.data:
                items.append(
                    AnomalyListItem(
                        id=row["id"],
                        anomaly_type=row["anomaly_type"],
                        severity=row["severity"],
                        title=row["title"],
                        explanation=row["explanation"],
                        event_ids=row["event_ids"],
                        gap_days=row.get("gap_days"),
                        confidence=row["confidence"],
                        verified=row["verified"],
                        dismissed=row["dismissed"],
                        created_at=datetime.fromisoformat(
                            row["created_at"].replace("Z", "+00:00")
                        ),
                    )
                )

            total = response.count or 0
            total_pages = ceil(total / per_page) if per_page > 0 else 0

            return AnomaliesListResponse(
                data=items,
                meta=PaginationMeta(
                    total=total,
                    page=page,
                    per_page=per_page,
                    total_pages=total_pages,
                ),
            )

        except Exception as e:
            logger.error(
                "anomaly_list_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise AnomalyServiceError(
                f"Failed to list anomalies: {e}",
                code="ANOMALY_LIST_FAILED",
            )

    async def get_anomaly_by_id(
        self,
        anomaly_id: str,
        matter_id: str,
    ) -> Anomaly | None:
        """Get a single anomaly by ID.

        Args:
            anomaly_id: Anomaly UUID.
            matter_id: Matter UUID (for access control).

        Returns:
            Anomaly if found, None otherwise.
        """
        try:
            response = (
                self.client.table("anomalies")
                .select("*")
                .eq("id", anomaly_id)
                .eq("matter_id", matter_id)
                .single()
                .execute()
            )

            if not response.data:
                return None

            row = response.data
            return Anomaly(
                id=row["id"],
                matter_id=row["matter_id"],
                anomaly_type=AnomalyType(row["anomaly_type"]),
                severity=AnomalySeverity(row["severity"]),
                title=row["title"],
                explanation=row["explanation"],
                event_ids=row["event_ids"],
                expected_order=row.get("expected_order"),
                actual_order=row.get("actual_order"),
                gap_days=row.get("gap_days"),
                confidence=row["confidence"],
                verified=row["verified"],
                dismissed=row["dismissed"],
                verified_by=row.get("verified_by"),
                verified_at=(
                    datetime.fromisoformat(row["verified_at"].replace("Z", "+00:00"))
                    if row.get("verified_at")
                    else None
                ),
                created_at=datetime.fromisoformat(
                    row["created_at"].replace("Z", "+00:00")
                ),
                updated_at=datetime.fromisoformat(
                    row["updated_at"].replace("Z", "+00:00")
                ),
            )

        except Exception as e:
            # Check if it's just a not found
            if "No rows found" in str(e) or "not found" in str(e).lower():
                return None
            logger.error(
                "anomaly_get_failed",
                anomaly_id=anomaly_id,
                matter_id=matter_id,
                error=str(e),
            )
            raise AnomalyServiceError(
                f"Failed to get anomaly: {e}",
                code="ANOMALY_GET_FAILED",
            )

    async def dismiss_anomaly(
        self,
        anomaly_id: str,
        matter_id: str,
        user_id: str,
    ) -> Anomaly | None:
        """Dismiss an anomaly as not a real issue.

        Args:
            anomaly_id: Anomaly UUID.
            matter_id: Matter UUID (for access control).
            user_id: User performing the dismissal.

        Returns:
            Updated Anomaly if found, None otherwise.
        """
        try:
            response = (
                self.client.table("anomalies")
                .update({
                    "dismissed": True,
                    "verified": False,  # Can't be both
                    "verified_by": user_id,
                    "verified_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", anomaly_id)
                .eq("matter_id", matter_id)
                .execute()
            )

            if not response.data:
                return None

            logger.info(
                "anomaly_dismissed",
                anomaly_id=anomaly_id,
                matter_id=matter_id,
                user_id=user_id,
            )

            return await self.get_anomaly_by_id(anomaly_id, matter_id)

        except Exception as e:
            logger.error(
                "anomaly_dismiss_failed",
                anomaly_id=anomaly_id,
                error=str(e),
            )
            raise AnomalyServiceError(
                f"Failed to dismiss anomaly: {e}",
                code="ANOMALY_DISMISS_FAILED",
            )

    async def verify_anomaly(
        self,
        anomaly_id: str,
        matter_id: str,
        user_id: str,
    ) -> Anomaly | None:
        """Verify an anomaly as a real issue.

        Args:
            anomaly_id: Anomaly UUID.
            matter_id: Matter UUID (for access control).
            user_id: User performing the verification.

        Returns:
            Updated Anomaly if found, None otherwise.
        """
        try:
            response = (
                self.client.table("anomalies")
                .update({
                    "verified": True,
                    "dismissed": False,  # Can't be both
                    "verified_by": user_id,
                    "verified_at": datetime.now(UTC).isoformat(),
                })
                .eq("id", anomaly_id)
                .eq("matter_id", matter_id)
                .execute()
            )

            if not response.data:
                return None

            logger.info(
                "anomaly_verified",
                anomaly_id=anomaly_id,
                matter_id=matter_id,
                user_id=user_id,
            )

            return await self.get_anomaly_by_id(anomaly_id, matter_id)

        except Exception as e:
            logger.error(
                "anomaly_verify_failed",
                anomaly_id=anomaly_id,
                error=str(e),
            )
            raise AnomalyServiceError(
                f"Failed to verify anomaly: {e}",
                code="ANOMALY_VERIFY_FAILED",
            )

    async def delete_anomalies_for_matter(
        self,
        matter_id: str,
    ) -> int:
        """Delete all anomalies for a matter (for reprocessing).

        Args:
            matter_id: Matter UUID.

        Returns:
            Number of deleted anomalies.
        """
        try:
            # Get count first
            count_response = (
                self.client.table("anomalies")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )
            deleted_count = count_response.count or 0

            # Delete all
            self.client.table("anomalies").delete().eq(
                "matter_id", matter_id
            ).execute()

            logger.info(
                "anomalies_deleted",
                matter_id=matter_id,
                count=deleted_count,
            )

            return deleted_count

        except Exception as e:
            logger.error(
                "anomaly_delete_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise AnomalyServiceError(
                f"Failed to delete anomalies: {e}",
                code="ANOMALY_DELETE_FAILED",
            )

    def delete_anomalies_for_matter_sync(
        self,
        matter_id: str,
    ) -> int:
        """Synchronous wrapper for delete_anomalies_for_matter (for Celery tasks)."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context (shouldn't happen in Celery, but handle it)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.delete_anomalies_for_matter(matter_id))
                return future.result()
        else:
            return asyncio.run(self.delete_anomalies_for_matter(matter_id))

    async def get_anomaly_summary(
        self,
        matter_id: str,
    ) -> AnomalySummaryResponse:
        """Get anomaly summary counts for attention banner.

        Args:
            matter_id: Matter UUID.

        Returns:
            AnomalySummaryResponse with counts.
        """
        try:
            # Get all anomalies for the matter
            response = (
                self.client.table("anomalies")
                .select("severity, anomaly_type, verified, dismissed")
                .eq("matter_id", matter_id)
                .execute()
            )

            data = response.data or []

            # Calculate counts
            total = len(data)
            by_severity: dict[str, int] = {}
            by_type: dict[str, int] = {}
            verified = 0
            dismissed = 0
            unreviewed = 0

            for row in data:
                # Count by severity
                sev = row["severity"]
                by_severity[sev] = by_severity.get(sev, 0) + 1

                # Count by type
                atype = row["anomaly_type"]
                by_type[atype] = by_type.get(atype, 0) + 1

                # Count review status
                if row["verified"]:
                    verified += 1
                elif row["dismissed"]:
                    dismissed += 1
                else:
                    unreviewed += 1

            return AnomalySummaryResponse(
                data=AnomalySummaryData(
                    total=total,
                    by_severity=by_severity,
                    by_type=by_type,
                    unreviewed=unreviewed,
                    verified=verified,
                    dismissed=dismissed,
                )
            )

        except Exception as e:
            logger.error(
                "anomaly_summary_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise AnomalyServiceError(
                f"Failed to get anomaly summary: {e}",
                code="ANOMALY_SUMMARY_FAILED",
            )

    async def count_anomalies_for_matter(
        self,
        matter_id: str,
    ) -> int:
        """Count total anomalies for a matter.

        Args:
            matter_id: Matter UUID.

        Returns:
            Total count of anomalies.
        """
        try:
            response = (
                self.client.table("anomalies")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )

            return response.count or 0

        except Exception as e:
            logger.error(
                "anomaly_count_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return 0


# =============================================================================
# Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_anomaly_service() -> AnomalyService:
    """Get a cached AnomalyService instance.

    Returns:
        AnomalyService singleton.
    """
    return AnomalyService()
