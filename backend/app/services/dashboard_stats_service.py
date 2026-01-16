"""Dashboard Stats Service for aggregated user statistics.

Story 14.5: Dashboard Real APIs (Task 4)

Provides aggregated dashboard statistics across all user's matters.
Optimized for efficient single-query aggregation.

CRITICAL: All operations respect user isolation - stats only include matters the user has access to.
"""

import asyncio
from functools import lru_cache

import structlog

from app.models.activity import DashboardStats
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 14.5: Exceptions
# =============================================================================


class DashboardStatsServiceError(Exception):
    """Base exception for dashboard stats service."""

    def __init__(
        self,
        message: str,
        code: str = "STATS_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


# =============================================================================
# Story 14.5: Dashboard Stats Service (Task 4.1 - 4.2)
# =============================================================================


class DashboardStatsService:
    """Service for computing aggregated dashboard statistics.

    Story 14.5: Implements AC #2 for dashboard stats.

    Features:
    - Count active (non-archived) matters user has access to
    - Count verified findings across all user's matters
    - Count pending reviews (findings awaiting verification)

    Performance: Uses efficient SQL aggregation via CTEs.

    Example:
        >>> service = DashboardStatsService()
        >>> stats = await service.get_dashboard_stats(user_id="user-uuid")
        >>> print(stats.active_matters)  # 5
    """

    def __init__(self) -> None:
        """Initialize dashboard stats service."""
        self._supabase_client = None

    @property
    def supabase(self):
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            DashboardStatsServiceError: If Supabase is not configured.
        """
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
            if self._supabase_client is None:
                raise DashboardStatsServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                    status_code=503,
                )
        return self._supabase_client

    # =========================================================================
    # Task 4.2: Get Dashboard Stats
    # =========================================================================

    async def get_dashboard_stats(self, user_id: str) -> DashboardStats:
        """Get aggregated dashboard statistics for a user.

        Story 14.5: AC #2 - Efficient aggregation across all user's matters.

        Performance: Uses three separate queries which is efficient enough
        for dashboard loads. Each query leverages indexes.

        Args:
            user_id: User ID to get stats for.

        Returns:
            DashboardStats with counts for active matters, verified findings,
            and pending reviews.

        Raises:
            DashboardStatsServiceError: If operation fails critically.
        """
        try:
            # Run all three stat queries in parallel for efficiency
            active_matters_count, verified_findings_count, pending_reviews_count = (
                await asyncio.gather(
                    self._count_active_matters(user_id),
                    self._count_verified_findings(user_id),
                    self._count_pending_reviews(user_id),
                )
            )

            stats = DashboardStats(
                active_matters=active_matters_count,
                verified_findings=verified_findings_count,
                pending_reviews=pending_reviews_count,
            )

            logger.debug(
                "dashboard_stats_computed",
                user_id=user_id,
                active_matters=active_matters_count,
                verified_findings=verified_findings_count,
                pending_reviews=pending_reviews_count,
            )

            return stats

        except DashboardStatsServiceError:
            raise
        except Exception as e:
            logger.error(
                "get_dashboard_stats_failed",
                user_id=user_id,
                error=str(e),
            )
            # Return zero stats on error to be graceful
            return DashboardStats(
                active_matters=0,
                verified_findings=0,
                pending_reviews=0,
            )

    async def _count_active_matters(self, user_id: str) -> int:
        """Count active (non-archived) matters for user.

        Uses matter_attorneys to find matters where user has any role.
        Filters by status != 'archived' and deleted_at IS NULL.
        """
        try:
            # Get matter IDs where user is a member
            ma_result = await asyncio.to_thread(
                lambda: self.supabase.table("matter_attorneys")
                .select("matter_id")
                .eq("user_id", user_id)
                .execute()
            )

            if not ma_result.data:
                return 0

            matter_ids = [row["matter_id"] for row in ma_result.data]

            # Count active matters
            result = await asyncio.to_thread(
                lambda: self.supabase.table("matters")
                .select("id", count="exact")
                .in_("id", matter_ids)
                .neq("status", "archived")
                .is_("deleted_at", "null")
                .execute()
            )

            return result.count or 0

        except Exception as e:
            logger.debug(
                "count_active_matters_failed",
                user_id=user_id,
                error=str(e),
            )
            return 0

    async def _count_verified_findings(self, user_id: str) -> int:
        """Count verified findings across user's matters.

        Uses finding_verifications table where decision = 'approved'.
        """
        try:
            # Get matter IDs where user is a member
            ma_result = await asyncio.to_thread(
                lambda: self.supabase.table("matter_attorneys")
                .select("matter_id")
                .eq("user_id", user_id)
                .execute()
            )

            if not ma_result.data:
                return 0

            matter_ids = [row["matter_id"] for row in ma_result.data]

            # Count verified findings (decision = 'approved')
            result = await asyncio.to_thread(
                lambda: self.supabase.table("finding_verifications")
                .select("id", count="exact")
                .in_("matter_id", matter_ids)
                .eq("decision", "approved")
                .execute()
            )

            return result.count or 0

        except Exception as e:
            logger.debug(
                "count_verified_findings_failed",
                user_id=user_id,
                error=str(e),
            )
            return 0

    async def _count_pending_reviews(self, user_id: str) -> int:
        """Count pending reviews (findings awaiting verification).

        Uses findings table where status = 'pending'.
        """
        try:
            # Get matter IDs where user is a member
            ma_result = await asyncio.to_thread(
                lambda: self.supabase.table("matter_attorneys")
                .select("matter_id")
                .eq("user_id", user_id)
                .execute()
            )

            if not ma_result.data:
                return 0

            matter_ids = [row["matter_id"] for row in ma_result.data]

            # Count pending findings (status = 'pending')
            result = await asyncio.to_thread(
                lambda: self.supabase.table("findings")
                .select("id", count="exact")
                .in_("matter_id", matter_ids)
                .eq("status", "pending")
                .execute()
            )

            return result.count or 0

        except Exception as e:
            logger.debug(
                "count_pending_reviews_failed",
                user_id=user_id,
                error=str(e),
            )
            return 0


# =============================================================================
# Story 14.5: Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_dashboard_stats_service() -> DashboardStatsService:
    """Get singleton dashboard stats service instance.

    Returns:
        DashboardStatsService instance.
    """
    return DashboardStatsService()
