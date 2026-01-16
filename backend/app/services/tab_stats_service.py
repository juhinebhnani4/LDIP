"""Tab Stats Service for Workspace Tab Bar API.

Story 14.12: Tab Stats API (Task 2)

Provides aggregated tab statistics for a single matter:
- Counts for each tab (timeline events, entities, citations, etc.)
- Issue counts (unresolved aliases, unverified citations, etc.)
- Processing status derived from active background jobs

CRITICAL: All operations filter by matter_id for Layer 4 security.
"""

import asyncio
from functools import lru_cache

import structlog

from app.models.job import JobStatus, JobType
from app.models.tab_stats import (
    TabCountsData,
    TabProcessingStatus,
    TabProcessingStatusData,
    TabStats,
    TabStatsData,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


# =============================================================================
# Story 14.12: Job Type to Tab Mapping (AC #3)
# =============================================================================


JOB_TYPE_TO_TAB: dict[str, str] = {
    JobType.ENTITY_EXTRACTION.value: "entities",
    JobType.ALIAS_RESOLUTION.value: "entities",
    JobType.DATE_EXTRACTION.value: "timeline",
    JobType.EVENT_CLASSIFICATION.value: "timeline",
    JobType.ENTITY_LINKING.value: "timeline",
    JobType.ANOMALY_DETECTION.value: "timeline",
    JobType.OCR.value: "documents",
    JobType.VALIDATION.value: "documents",
    JobType.DOCUMENT_PROCESSING.value: "documents",
    JobType.CHUNKING.value: "documents",
    JobType.EMBEDDING.value: "documents",
    # TODO: Add mappings when these JobTypes are added to job.py:
    # - "CITATION_EXTRACTION": "citations"
    # - "CONTRADICTION_DETECTION": "contradictions"
    # - "VERIFICATION_PROCESSING": "verification"
    # - "SUMMARY_GENERATION": "summary"
}
"""Maps job_type to workspace tab for processing status derivation."""


# =============================================================================
# Story 14.12: Exceptions
# =============================================================================


class TabStatsServiceError(Exception):
    """Base exception for tab stats service."""

    def __init__(
        self,
        message: str,
        code: str = "TAB_STATS_ERROR",
        status_code: int = 500,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


# =============================================================================
# Story 14.12: Tab Stats Service (Task 2.1 - 2.10)
# =============================================================================


class TabStatsService:
    """Service for computing aggregated tab statistics for a matter.

    Story 14.12: Implements AC #2, #3 for tab counts and processing status.

    Features:
    - Count timeline events, entities, citations, contradictions, verification items, documents
    - Compute issue counts (unresolved aliases, unverified citations, flagged findings)
    - Derive processing status from active background jobs

    Performance: Uses parallel async queries for efficiency.

    Example:
        >>> service = TabStatsService()
        >>> stats = await service.get_tab_stats(matter_id="matter-uuid")
        >>> print(stats.tab_counts.timeline.count)  # 24
    """

    def __init__(self) -> None:
        """Initialize tab stats service."""
        self._supabase_client = None

    @property
    def supabase(self):
        """Get Supabase client.

        Returns:
            Supabase client instance.

        Raises:
            TabStatsServiceError: If Supabase is not configured.
        """
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
            if self._supabase_client is None:
                raise TabStatsServiceError(
                    "Supabase not configured",
                    code="SUPABASE_NOT_CONFIGURED",
                    status_code=503,
                )
        return self._supabase_client

    # =========================================================================
    # Task 2.2: Main Entry Point
    # =========================================================================

    async def get_tab_stats(self, matter_id: str) -> TabStatsData:
        """Get aggregated tab statistics for a matter.

        Story 14.12: AC #2, #3 - Counts, issue counts, and processing status.

        Performance: Runs all count queries in parallel for efficiency.

        Args:
            matter_id: Matter UUID to get stats for.

        Returns:
            TabStatsData with counts and processing status for all tabs.

        Raises:
            TabStatsServiceError: If operation fails critically.
        """
        try:
            # Run all queries in parallel for efficiency
            (
                timeline_stats,
                entities_stats,
                citations_stats,
                contradictions_stats,
                verification_stats,
                documents_stats,
                processing_status,
            ) = await asyncio.gather(
                self._get_timeline_stats(matter_id),
                self._get_entities_stats(matter_id),
                self._get_citations_stats(matter_id),
                self._get_contradictions_stats(matter_id),
                self._get_verification_stats(matter_id),
                self._get_documents_stats(matter_id),
                self._get_processing_status(matter_id),
            )

            # Summary is static for now (AC #2)
            summary_stats = TabStats(count=1, issue_count=0)

            tab_counts = TabCountsData(
                summary=summary_stats,
                timeline=timeline_stats,
                entities=entities_stats,
                citations=citations_stats,
                contradictions=contradictions_stats,
                verification=verification_stats,
                documents=documents_stats,
            )

            stats = TabStatsData(
                tab_counts=tab_counts,
                tab_processing_status=processing_status,
            )

            logger.debug(
                "tab_stats_computed",
                matter_id=matter_id,
                timeline_count=timeline_stats.count,
                entities_count=entities_stats.count,
                citations_count=citations_stats.count,
            )

            return stats

        except TabStatsServiceError:
            raise
        except Exception as e:
            logger.error(
                "get_tab_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            raise TabStatsServiceError(
                f"Failed to get tab stats: {e}",
                code="TAB_STATS_QUERY_FAILED",
                status_code=500,
            )

    # =========================================================================
    # Task 2.3: Timeline Stats
    # =========================================================================

    async def _get_timeline_stats(self, matter_id: str) -> TabStats:
        """Get timeline tab statistics.

        Story 14.12: AC #2 - Count events, issueCount = 0.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("events")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )

            count = result.count or 0
            return TabStats(count=count, issue_count=0)

        except Exception as e:
            logger.debug(
                "timeline_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return TabStats(count=0, issue_count=0)

    # =========================================================================
    # Task 2.4: Entities Stats
    # =========================================================================

    async def _get_entities_stats(self, matter_id: str) -> TabStats:
        """Get entities tab statistics.

        Story 14.12: AC #2 - Count identity_nodes, issueCount = unresolved aliases.
        """
        try:
            # Get total count
            count_result = await asyncio.to_thread(
                lambda: self.supabase.table("identity_nodes")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )

            count = count_result.count or 0

            # Get issue count - entities with unresolved aliases
            # An entity has unresolved aliases if it has aliases that haven't been merged
            issue_result = await asyncio.to_thread(
                lambda: self.supabase.table("identity_nodes")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("has_unresolved_alias", True)
                .execute()
            )

            issue_count = issue_result.count or 0

            return TabStats(count=count, issue_count=issue_count)

        except Exception as e:
            logger.debug(
                "entities_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return TabStats(count=0, issue_count=0)

    # =========================================================================
    # Task 2.5: Citations Stats
    # =========================================================================

    async def _get_citations_stats(self, matter_id: str) -> TabStats:
        """Get citations tab statistics.

        Story 14.12: AC #2 - Count citations, issueCount = unverified.
        """
        try:
            # Get total count
            count_result = await asyncio.to_thread(
                lambda: self.supabase.table("citations")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )

            count = count_result.count or 0

            # Get issue count - citations not verified
            issue_result = await asyncio.to_thread(
                lambda: self.supabase.table("citations")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .neq("verification_status", "verified")
                .execute()
            )

            issue_count = issue_result.count or 0

            return TabStats(count=count, issue_count=issue_count)

        except Exception as e:
            logger.debug(
                "citations_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return TabStats(count=0, issue_count=0)

    # =========================================================================
    # Task 2.6: Contradictions Stats
    # =========================================================================

    async def _get_contradictions_stats(self, matter_id: str) -> TabStats:
        """Get contradictions tab statistics.

        Story 14.12: AC #2 - Count contradictions, issueCount = same (all need attention).
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("contradictions")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )

            count = result.count or 0
            # All contradictions are issues that need attention
            return TabStats(count=count, issue_count=count)

        except Exception as e:
            logger.debug(
                "contradictions_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return TabStats(count=0, issue_count=0)

    # =========================================================================
    # Task 2.7: Verification Stats
    # =========================================================================

    async def _get_verification_stats(self, matter_id: str) -> TabStats:
        """Get verification tab statistics.

        Story 14.12: AC #2 - Count pending verifications, issueCount = flagged or low confidence.
        """
        try:
            # Get total pending count (decision IS NULL)
            count_result = await asyncio.to_thread(
                lambda: self.supabase.table("finding_verifications")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .is_("decision", "null")
                .execute()
            )

            count = count_result.count or 0

            # Get issue count - flagged OR low confidence (mutually exclusive queries)
            # Query 1: Flagged findings (any confidence level)
            flagged_result = await asyncio.to_thread(
                lambda: self.supabase.table("finding_verifications")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .eq("decision", "flagged")
                .execute()
            )

            # Query 2: Low confidence pending findings (decision IS NULL and confidence < 70)
            # These are mutually exclusive from flagged since flagged has decision='flagged'
            low_confidence_result = await asyncio.to_thread(
                lambda: self.supabase.table("finding_verifications")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .lt("confidence", 70)
                .is_("decision", "null")
                .execute()
            )

            flagged_count = flagged_result.count or 0
            low_confidence_count = low_confidence_result.count or 0

            # These are mutually exclusive: flagged has decision='flagged', low_confidence has decision=null
            issue_count = flagged_count + low_confidence_count

            return TabStats(count=count, issue_count=issue_count)

        except Exception as e:
            logger.debug(
                "verification_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return TabStats(count=0, issue_count=0)

    # =========================================================================
    # Task 2.8: Documents Stats
    # =========================================================================

    async def _get_documents_stats(self, matter_id: str) -> TabStats:
        """Get documents tab statistics.

        Story 14.12: AC #2 - Count documents, issueCount = 0.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("documents")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )

            count = result.count or 0
            return TabStats(count=count, issue_count=0)

        except Exception as e:
            logger.debug(
                "documents_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return TabStats(count=0, issue_count=0)

    # =========================================================================
    # Task 2.9-2.10: Processing Status
    # =========================================================================

    async def _get_processing_status(self, matter_id: str) -> TabProcessingStatusData:
        """Get processing status for all tabs based on active jobs.

        Story 14.12: AC #3 - Derive status from background jobs.
        """
        try:
            # Query active jobs (queued or processing)
            result = await asyncio.to_thread(
                lambda: self.supabase.table("processing_jobs")
                .select("job_type")
                .eq("matter_id", matter_id)
                .in_("status", [JobStatus.QUEUED.value, JobStatus.PROCESSING.value])
                .execute()
            )

            # Build set of tabs with active jobs
            processing_tabs: set[str] = set()
            for row in result.data or []:
                job_type = row.get("job_type")
                if job_type and job_type in JOB_TYPE_TO_TAB:
                    processing_tabs.add(JOB_TYPE_TO_TAB[job_type])

            # Build status data
            def get_status(tab: str) -> TabProcessingStatus:
                return "processing" if tab in processing_tabs else "ready"

            return TabProcessingStatusData(
                summary=get_status("summary"),
                timeline=get_status("timeline"),
                entities=get_status("entities"),
                citations=get_status("citations"),
                contradictions=get_status("contradictions"),
                verification=get_status("verification"),
                documents=get_status("documents"),
            )

        except Exception as e:
            logger.debug(
                "processing_status_failed",
                matter_id=matter_id,
                error=str(e),
            )
            # Return all ready on error (graceful degradation)
            return TabProcessingStatusData()


# =============================================================================
# Story 14.12: Factory Function
# =============================================================================


@lru_cache(maxsize=1)
def get_tab_stats_service() -> TabStatsService:
    """Get singleton tab stats service instance.

    Returns:
        TabStatsService instance.
    """
    return TabStatsService()
