"""Act Discovery Service for generating the Missing Acts Report.

Provides functionality for the Act Discovery Report showing which Acts
are referenced but not yet uploaded, enabling user action.

Story 3-1: Act Citation Extraction (AC: #4)
"""

from datetime import datetime
from functools import lru_cache
from typing import Final

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
    ) -> list[ActDiscoverySummary]:
        """Generate Act Discovery Report for a matter.

        Args:
            matter_id: Matter UUID.
            include_available: Whether to include Acts that are already available.

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
                # Skip available if not requested
                if (
                    not include_available
                    and resolution.resolution_status == ActResolutionStatus.AVAILABLE
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
                    if s.resolution_status == ActResolutionStatus.AVAILABLE
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

    async def get_discovery_stats(
        self,
        matter_id: str,
    ) -> dict:
        """Get summary statistics for Act Discovery.

        Args:
            matter_id: Matter UUID.

        Returns:
            Dict with total_acts, missing_count, available_count, skipped_count.
        """
        try:
            resolutions = await self._storage.get_act_resolutions(matter_id)

            stats = {
                "total_acts": len(resolutions),
                "missing_count": 0,
                "available_count": 0,
                "skipped_count": 0,
                "total_citations": 0,
            }

            for resolution in resolutions:
                stats["total_citations"] += resolution.citation_count

                if resolution.resolution_status == ActResolutionStatus.MISSING:
                    stats["missing_count"] += 1
                elif resolution.resolution_status == ActResolutionStatus.AVAILABLE:
                    stats["available_count"] += 1
                elif resolution.resolution_status == ActResolutionStatus.SKIPPED:
                    stats["skipped_count"] += 1

            return stats

        except Exception as e:
            logger.error(
                "get_discovery_stats_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return {
                "total_acts": 0,
                "missing_count": 0,
                "available_count": 0,
                "skipped_count": 0,
                "total_citations": 0,
            }


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
