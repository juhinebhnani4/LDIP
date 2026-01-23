"""Act Discovery Service for generating the Missing Acts Report.

Provides functionality for the Act Discovery Report showing which Acts
are referenced but not yet uploaded, enabling user action.

Story 3-1: Act Citation Extraction (AC: #4)
Story 3-3: Citation Verification (trigger_verification_on_upload)
"""

from dataclasses import dataclass
from functools import lru_cache

import structlog

from app.engines.citation.abbreviations import get_display_name, normalize_act_name
from app.engines.citation.storage import get_citation_storage_service
from app.models.citation import (
    ActDiscoverySummary,
    ActResolution,
    ActResolutionStatus,
    UserAction,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Centralized Stats Calculation (Single Source of Truth)
# =============================================================================


@dataclass
class ActResolutionStats:
    """Centralized statistics for act resolutions.

    This ensures stats and discovery report use identical counting logic.
    """
    total_acts: int = 0  # Excludes invalid acts
    missing_count: int = 0
    available_count: int = 0
    auto_fetched_count: int = 0
    skipped_count: int = 0
    invalid_count: int = 0
    total_citations: int = 0

    # Data consistency tracking
    inconsistencies: list[dict] = None

    def __post_init__(self):
        if self.inconsistencies is None:
            self.inconsistencies = []

    def to_dict(self) -> dict:
        """Convert to dict for API responses."""
        return {
            "total_acts": self.total_acts,
            "missing_count": self.missing_count,
            "available_count": self.available_count,
            "auto_fetched_count": self.auto_fetched_count,
            "skipped_count": self.skipped_count,
            "invalid_count": self.invalid_count,
            "total_citations": self.total_citations,
        }


def compute_resolution_stats(
    resolutions: list[ActResolution],
    include_invalid: bool = False,
    check_consistency: bool = True,
) -> ActResolutionStats:
    """Centralized function to compute stats from resolutions.

    This is the SINGLE SOURCE OF TRUTH for counting act resolutions.
    Both get_discovery_stats() and get_discovery_report() should use this
    to ensure consistency.

    Args:
        resolutions: List of ActResolution objects.
        include_invalid: Whether to include invalid acts in total_acts.
        check_consistency: Whether to check for data inconsistencies.

    Returns:
        ActResolutionStats with computed values.
    """
    stats = ActResolutionStats()

    for resolution in resolutions:
        stats.total_citations += resolution.citation_count

        # Check for data inconsistencies
        if check_consistency:
            # Inconsistency: has document_id but marked as missing
            if (
                resolution.act_document_id
                and resolution.resolution_status == ActResolutionStatus.MISSING
            ):
                stats.inconsistencies.append({
                    "type": "document_status_mismatch",
                    "act_name": resolution.act_name_normalized,
                    "issue": "Has document_id but status is 'missing'",
                    "document_id": resolution.act_document_id,
                })

        # Count by status
        if resolution.resolution_status == ActResolutionStatus.MISSING:
            stats.missing_count += 1
            stats.total_acts += 1
        elif resolution.resolution_status == ActResolutionStatus.AVAILABLE:
            stats.available_count += 1
            stats.total_acts += 1
        elif resolution.resolution_status == ActResolutionStatus.AUTO_FETCHED:
            stats.auto_fetched_count += 1
            stats.total_acts += 1
        elif resolution.resolution_status == ActResolutionStatus.SKIPPED:
            stats.skipped_count += 1
            stats.total_acts += 1
        elif resolution.resolution_status == ActResolutionStatus.INVALID:
            stats.invalid_count += 1
            # Invalid acts excluded from total_acts unless explicitly included
            if include_invalid:
                stats.total_acts += 1

    # Log any inconsistencies found
    if stats.inconsistencies:
        logger.warning(
            "data_inconsistencies_detected",
            count=len(stats.inconsistencies),
            inconsistencies=stats.inconsistencies,
        )

    return stats


# =============================================================================
# Service Implementation
# =============================================================================


class ActDiscoveryService:
    """Service for generating Act Discovery Reports.

    Aggregates citation data to show which Acts are referenced
    in case documents and their resolution status.

    Example:
        >>> discovery = ActDiscoveryService()
        >>> report = await discovery.get_discovery_report(matter_id)
        >>> for act in report:
        ...     print(f"{act.act_name}: {act.citation_count} citations")
    """

    def __init__(self) -> None:
        """Initialize act discovery service."""
        self._storage = get_citation_storage_service()

    async def get_discovery_report(
        self,
        matter_id: str,
        include_available: bool = True,
        include_invalid: bool = False,
    ) -> list[ActDiscoverySummary]:
        """Generate Act Discovery Report for a matter.

        Args:
            matter_id: Matter UUID.
            include_available: Whether to include Acts that are already available.
            include_invalid: Whether to include invalid (garbage) acts. Default False.

        Returns:
            List of ActDiscoverySummary items sorted by citation count.
        """
        try:
            # Get all act resolutions for the matter
            resolutions = await self._storage.get_act_resolutions(matter_id)

            # Get citation counts for accurate counts
            counts = await self._storage.get_citation_counts_by_act(matter_id)
            count_map = {c["act_name"]: c["citation_count"] for c in counts}

            # Build summary list
            summaries: list[ActDiscoverySummary] = []

            for resolution in resolutions:
                # Skip invalid acts (garbage extractions) unless explicitly requested
                if (
                    not include_invalid
                    and resolution.resolution_status == ActResolutionStatus.INVALID
                ):
                    continue

                # Skip available/auto-fetched if not requested
                if not include_available:
                    if resolution.resolution_status in (
                        ActResolutionStatus.AVAILABLE,
                        ActResolutionStatus.AUTO_FETCHED,
                    ):
                        continue

                # Get display name
                display_name = resolution.act_name_display or get_display_name(
                    resolution.act_name_normalized
                )

                # Get citation count from counts map if available
                citation_count = resolution.citation_count
                for act_name, count in count_map.items():
                    if normalize_act_name(act_name) == resolution.act_name_normalized:
                        citation_count = count
                        break

                summary = ActDiscoverySummary(
                    act_name=display_name,
                    act_name_normalized=resolution.act_name_normalized,
                    citation_count=citation_count,
                    resolution_status=resolution.resolution_status,
                    user_action=resolution.user_action,
                    act_document_id=resolution.act_document_id,
                )
                summaries.append(summary)

            # Sort by citation count (most referenced first)
            summaries.sort(key=lambda x: x.citation_count, reverse=True)

            logger.info(
                "act_discovery_report_generated",
                matter_id=matter_id,
                total_acts=len(summaries),
                missing_acts=sum(
                    1 for s in summaries
                    if s.resolution_status == ActResolutionStatus.MISSING
                ),
                available_acts=sum(
                    1 for s in summaries
                    if s.resolution_status in (
                        ActResolutionStatus.AVAILABLE,
                        ActResolutionStatus.AUTO_FETCHED,
                    )
                ),
                auto_fetched_acts=sum(
                    1 for s in summaries
                    if s.resolution_status == ActResolutionStatus.AUTO_FETCHED
                ),
            )

            return summaries

        except Exception as e:
            logger.error(
                "act_discovery_report_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return []

    async def get_missing_acts(
        self,
        matter_id: str,
    ) -> list[ActDiscoverySummary]:
        """Get only missing Acts (not uploaded and not skipped).

        Convenience method for getting Acts that need user action.

        Args:
            matter_id: Matter UUID.

        Returns:
            List of missing ActDiscoverySummary items.
        """
        report = await self.get_discovery_report(matter_id, include_available=False)
        return [
            act for act in report
            if act.resolution_status == ActResolutionStatus.MISSING
            and act.user_action == UserAction.PENDING
        ]

    async def get_act_resolution_by_name(
        self,
        matter_id: str,
        act_name: str,
    ) -> ActResolution | None:
        """Get act resolution for a specific Act.

        Args:
            matter_id: Matter UUID.
            act_name: Act name (will be normalized).

        Returns:
            ActResolution or None if not found.
        """
        try:
            normalized = normalize_act_name(act_name)
            resolutions = await self._storage.get_act_resolutions(matter_id)

            for resolution in resolutions:
                if resolution.act_name_normalized == normalized:
                    return resolution

            return None

        except Exception as e:
            logger.error(
                "get_act_resolution_by_name_failed",
                matter_id=matter_id,
                act_name=act_name,
                error=str(e),
            )
            return None

    async def mark_act_uploaded(
        self,
        matter_id: str,
        act_name: str,
        act_document_id: str,
    ) -> bool:
        """Mark an Act as uploaded.

        Updates the act resolution to indicate the Act document is available.

        Args:
            matter_id: Matter UUID.
            act_name: Act name (will be normalized).
            act_document_id: UUID of the uploaded Act document.

        Returns:
            True if updated successfully.
        """
        try:
            normalized = normalize_act_name(act_name)

            result = await self._storage.update_act_resolution(
                matter_id=matter_id,
                act_name_normalized=normalized,
                act_document_id=act_document_id,
                resolution_status=ActResolutionStatus.AVAILABLE,
                user_action=UserAction.UPLOADED,
            )

            if result:
                logger.info(
                    "act_marked_uploaded",
                    matter_id=matter_id,
                    act_name=act_name,
                    act_document_id=act_document_id,
                )
                return True

            return False

        except Exception as e:
            logger.error(
                "mark_act_uploaded_failed",
                matter_id=matter_id,
                act_name=act_name,
                error=str(e),
            )
            return False

    async def mark_act_skipped(
        self,
        matter_id: str,
        act_name: str,
    ) -> bool:
        """Mark an Act as skipped by user.

        User chose not to upload this Act (maybe they don't have it).

        Args:
            matter_id: Matter UUID.
            act_name: Act name (will be normalized).

        Returns:
            True if updated successfully.
        """
        try:
            normalized = normalize_act_name(act_name)

            result = await self._storage.update_act_resolution(
                matter_id=matter_id,
                act_name_normalized=normalized,
                resolution_status=ActResolutionStatus.SKIPPED,
                user_action=UserAction.SKIPPED,
            )

            if result:
                logger.info(
                    "act_marked_skipped",
                    matter_id=matter_id,
                    act_name=act_name,
                )
                return True

            return False

        except Exception as e:
            logger.error(
                "mark_act_skipped_failed",
                matter_id=matter_id,
                act_name=act_name,
                error=str(e),
            )
            return False

    async def trigger_verification_on_upload(
        self,
        matter_id: str,
        act_name: str,
        act_document_id: str,
    ) -> str | None:
        """Trigger verification for all citations when an Act is uploaded.

        Called after an Act document is uploaded to verify all citations
        referencing this Act.

        Args:
            matter_id: Matter UUID.
            act_name: Act name (will be normalized).
            act_document_id: UUID of the uploaded Act document.

        Returns:
            Celery task ID if verification was triggered, None otherwise.
        """
        try:
            # Import here to avoid circular import
            from app.workers.tasks.verification_tasks import verify_citations_for_act

            logger.info(
                "triggering_verification_on_upload",
                matter_id=matter_id,
                act_name=act_name,
                act_document_id=act_document_id,
            )

            # Start verification task
            task = verify_citations_for_act.delay(
                matter_id=matter_id,
                act_name=act_name,
                act_document_id=act_document_id,
            )

            logger.info(
                "verification_triggered_on_upload",
                matter_id=matter_id,
                act_name=act_name,
                task_id=task.id,
            )

            return task.id

        except Exception as e:
            logger.error(
                "trigger_verification_on_upload_failed",
                matter_id=matter_id,
                act_name=act_name,
                error=str(e),
            )
            return None

    async def get_discovery_stats(
        self,
        matter_id: str,
    ) -> dict:
        """Get summary statistics for Act Discovery.

        Args:
            matter_id: Matter UUID.

        Returns:
            Dict with total_acts, missing_count, available_count, auto_fetched_count,
            skipped_count, invalid_count.

        Note:
            Uses centralized compute_resolution_stats() to ensure consistency
            with get_discovery_report(). Invalid acts are excluded from total_acts.
        """
        try:
            resolutions = await self._storage.get_act_resolutions(matter_id)

            # Use centralized stats computation
            stats = compute_resolution_stats(
                resolutions,
                include_invalid=False,
                check_consistency=True,
            )

            return stats.to_dict()

        except Exception as e:
            logger.error(
                "get_discovery_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return ActResolutionStats().to_dict()


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_act_discovery_service() -> ActDiscoveryService:
    """Get singleton act discovery service instance.

    Returns:
        ActDiscoveryService instance.
    """
    return ActDiscoveryService()
