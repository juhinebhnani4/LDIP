"""Tests for Act Discovery service.

Story 3-1: Act Citation Extraction (AC: #4)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.citation.discovery import (
    ActDiscoveryService,
    get_act_discovery_service,
)
from app.models.citation import (
    ActResolution,
    ActResolutionStatus,
    UserAction,
)


class TestGetDiscoveryReport:
    """Tests for get_discovery_report method."""

    @pytest.mark.asyncio
    async def test_returns_sorted_by_citation_count(self) -> None:
        """Should return summaries sorted by citation count descending."""
        mock_storage = MagicMock()
        mock_storage.get_act_resolutions = AsyncMock(
            return_value=[
                ActResolution(
                    id="res-1",
                    matter_id="matter-123",
                    act_name_normalized="act_a",
                    act_name_display="Act A",
                    resolution_status=ActResolutionStatus.MISSING,
                    user_action=UserAction.PENDING,
                    citation_count=5,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-2",
                    matter_id="matter-123",
                    act_name_normalized="act_b",
                    act_name_display="Act B",
                    resolution_status=ActResolutionStatus.MISSING,
                    user_action=UserAction.PENDING,
                    citation_count=15,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-3",
                    matter_id="matter-123",
                    act_name_normalized="act_c",
                    act_name_display="Act C",
                    resolution_status=ActResolutionStatus.AVAILABLE,
                    user_action=UserAction.UPLOADED,
                    citation_count=10,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
            ]
        )
        mock_storage.get_citation_counts_by_act = AsyncMock(return_value=[])

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            report = await service.get_discovery_report("matter-123")

            # Should be sorted: Act B (15), Act C (10), Act A (5)
            assert len(report) == 3
            assert report[0].act_name == "Act B"
            assert report[0].citation_count == 15
            assert report[1].act_name == "Act C"
            assert report[1].citation_count == 10
            assert report[2].act_name == "Act A"
            assert report[2].citation_count == 5

    @pytest.mark.asyncio
    async def test_excludes_available_when_requested(self) -> None:
        """Should exclude available Acts when include_available=False."""
        mock_storage = MagicMock()
        mock_storage.get_act_resolutions = AsyncMock(
            return_value=[
                ActResolution(
                    id="res-1",
                    matter_id="matter-123",
                    act_name_normalized="act_a",
                    act_name_display="Act A",
                    resolution_status=ActResolutionStatus.MISSING,
                    user_action=UserAction.PENDING,
                    citation_count=5,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-2",
                    matter_id="matter-123",
                    act_name_normalized="act_b",
                    act_name_display="Act B",
                    resolution_status=ActResolutionStatus.AVAILABLE,
                    user_action=UserAction.UPLOADED,
                    citation_count=10,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
            ]
        )
        mock_storage.get_citation_counts_by_act = AsyncMock(return_value=[])

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            report = await service.get_discovery_report(
                "matter-123",
                include_available=False,
            )

            assert len(report) == 1
            assert report[0].act_name == "Act A"

    @pytest.mark.asyncio
    async def test_includes_all_statuses_by_default(self) -> None:
        """Should include all statuses when include_available=True."""
        mock_storage = MagicMock()
        mock_storage.get_act_resolutions = AsyncMock(
            return_value=[
                ActResolution(
                    id="res-1",
                    matter_id="matter-123",
                    act_name_normalized="act_a",
                    act_name_display="Act A",
                    resolution_status=ActResolutionStatus.MISSING,
                    user_action=UserAction.PENDING,
                    citation_count=5,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-2",
                    matter_id="matter-123",
                    act_name_normalized="act_b",
                    act_name_display="Act B",
                    resolution_status=ActResolutionStatus.AVAILABLE,
                    user_action=UserAction.UPLOADED,
                    citation_count=10,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-3",
                    matter_id="matter-123",
                    act_name_normalized="act_c",
                    act_name_display="Act C",
                    resolution_status=ActResolutionStatus.SKIPPED,
                    user_action=UserAction.SKIPPED,
                    citation_count=3,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
            ]
        )
        mock_storage.get_citation_counts_by_act = AsyncMock(return_value=[])

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            report = await service.get_discovery_report("matter-123")

            assert len(report) == 3

    @pytest.mark.asyncio
    async def test_handles_storage_error(self) -> None:
        """Should return empty list on storage error."""
        mock_storage = MagicMock()
        mock_storage.get_act_resolutions = AsyncMock(
            side_effect=Exception("Database error")
        )

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            report = await service.get_discovery_report("matter-123")

            assert len(report) == 0


class TestGetMissingActs:
    """Tests for get_missing_acts method."""

    @pytest.mark.asyncio
    async def test_returns_only_missing_pending(self) -> None:
        """Should return only missing Acts with pending user action."""
        mock_storage = MagicMock()
        mock_storage.get_act_resolutions = AsyncMock(
            return_value=[
                ActResolution(
                    id="res-1",
                    matter_id="matter-123",
                    act_name_normalized="act_missing",
                    act_name_display="Missing Act",
                    resolution_status=ActResolutionStatus.MISSING,
                    user_action=UserAction.PENDING,
                    citation_count=5,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-2",
                    matter_id="matter-123",
                    act_name_normalized="act_available",
                    act_name_display="Available Act",
                    resolution_status=ActResolutionStatus.AVAILABLE,
                    user_action=UserAction.UPLOADED,
                    citation_count=10,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-3",
                    matter_id="matter-123",
                    act_name_normalized="act_skipped",
                    act_name_display="Skipped Act",
                    resolution_status=ActResolutionStatus.SKIPPED,
                    user_action=UserAction.SKIPPED,
                    citation_count=3,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
            ]
        )
        mock_storage.get_citation_counts_by_act = AsyncMock(return_value=[])

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            missing = await service.get_missing_acts("matter-123")

            assert len(missing) == 1
            assert missing[0].act_name == "Missing Act"


class TestGetActResolutionByName:
    """Tests for get_act_resolution_by_name method."""

    @pytest.mark.asyncio
    async def test_finds_by_name(self) -> None:
        """Should find resolution by act name."""
        mock_storage = MagicMock()
        mock_storage.get_act_resolutions = AsyncMock(
            return_value=[
                ActResolution(
                    id="res-1",
                    matter_id="matter-123",
                    act_name_normalized="negotiable_instruments_act_1881",
                    act_name_display="Negotiable Instruments Act, 1881",
                    resolution_status=ActResolutionStatus.MISSING,
                    user_action=UserAction.PENDING,
                    citation_count=5,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
            ]
        )

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            resolution = await service.get_act_resolution_by_name(
                "matter-123",
                "NI Act",  # Should normalize to match
            )

            assert resolution is not None
            assert "Negotiable Instruments" in resolution.act_name_display

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown(self) -> None:
        """Should return None for unknown act."""
        mock_storage = MagicMock()
        mock_storage.get_act_resolutions = AsyncMock(return_value=[])

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            resolution = await service.get_act_resolution_by_name(
                "matter-123",
                "Unknown Act",
            )

            assert resolution is None


class TestMarkActUploaded:
    """Tests for mark_act_uploaded method."""

    @pytest.mark.asyncio
    async def test_updates_resolution_status(self) -> None:
        """Should update resolution to available status."""
        mock_storage = MagicMock()
        mock_storage.update_act_resolution = AsyncMock(
            return_value=ActResolution(
                id="res-1",
                matter_id="matter-123",
                act_name_normalized="ni_act",
                act_name_display="NI Act",
                act_document_id="act-doc-1",
                resolution_status=ActResolutionStatus.AVAILABLE,
                user_action=UserAction.UPLOADED,
                citation_count=5,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            result = await service.mark_act_uploaded(
                matter_id="matter-123",
                act_name="NI Act",
                act_document_id="act-doc-1",
            )

            assert result is True
            mock_storage.update_act_resolution.assert_called_once()
            call_args = mock_storage.update_act_resolution.call_args
            assert call_args.kwargs["resolution_status"] == ActResolutionStatus.AVAILABLE
            assert call_args.kwargs["user_action"] == UserAction.UPLOADED

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self) -> None:
        """Should return False when update fails."""
        mock_storage = MagicMock()
        mock_storage.update_act_resolution = AsyncMock(return_value=None)

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            result = await service.mark_act_uploaded(
                matter_id="matter-123",
                act_name="NI Act",
                act_document_id="act-doc-1",
            )

            assert result is False


class TestMarkActSkipped:
    """Tests for mark_act_skipped method."""

    @pytest.mark.asyncio
    async def test_updates_to_skipped_status(self) -> None:
        """Should update resolution to skipped status."""
        mock_storage = MagicMock()
        mock_storage.update_act_resolution = AsyncMock(
            return_value=ActResolution(
                id="res-1",
                matter_id="matter-123",
                act_name_normalized="ni_act",
                act_name_display="NI Act",
                resolution_status=ActResolutionStatus.SKIPPED,
                user_action=UserAction.SKIPPED,
                citation_count=5,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            result = await service.mark_act_skipped(
                matter_id="matter-123",
                act_name="NI Act",
            )

            assert result is True
            call_args = mock_storage.update_act_resolution.call_args
            assert call_args.kwargs["resolution_status"] == ActResolutionStatus.SKIPPED
            assert call_args.kwargs["user_action"] == UserAction.SKIPPED


class TestGetDiscoveryStats:
    """Tests for get_discovery_stats method."""

    @pytest.mark.asyncio
    async def test_aggregates_stats_correctly(self) -> None:
        """Should aggregate stats from resolutions."""
        mock_storage = MagicMock()
        mock_storage.get_act_resolutions = AsyncMock(
            return_value=[
                ActResolution(
                    id="res-1",
                    matter_id="matter-123",
                    act_name_normalized="act_a",
                    act_name_display="Act A",
                    resolution_status=ActResolutionStatus.MISSING,
                    user_action=UserAction.PENDING,
                    citation_count=5,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-2",
                    matter_id="matter-123",
                    act_name_normalized="act_b",
                    act_name_display="Act B",
                    resolution_status=ActResolutionStatus.MISSING,
                    user_action=UserAction.PENDING,
                    citation_count=10,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-3",
                    matter_id="matter-123",
                    act_name_normalized="act_c",
                    act_name_display="Act C",
                    resolution_status=ActResolutionStatus.AVAILABLE,
                    user_action=UserAction.UPLOADED,
                    citation_count=15,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                ActResolution(
                    id="res-4",
                    matter_id="matter-123",
                    act_name_normalized="act_d",
                    act_name_display="Act D",
                    resolution_status=ActResolutionStatus.SKIPPED,
                    user_action=UserAction.SKIPPED,
                    citation_count=3,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
            ]
        )

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            stats = await service.get_discovery_stats("matter-123")

            assert stats["total_acts"] == 4
            assert stats["missing_count"] == 2
            assert stats["available_count"] == 1
            assert stats["skipped_count"] == 1
            assert stats["total_citations"] == 33  # 5 + 10 + 15 + 3

    @pytest.mark.asyncio
    async def test_returns_zeros_on_error(self) -> None:
        """Should return zero stats on error."""
        mock_storage = MagicMock()
        mock_storage.get_act_resolutions = AsyncMock(
            side_effect=Exception("Database error")
        )

        with patch(
            "app.engines.citation.discovery.get_citation_storage_service",
            return_value=mock_storage,
        ):
            service = ActDiscoveryService()

            stats = await service.get_discovery_stats("matter-123")

            assert stats["total_acts"] == 0
            assert stats["missing_count"] == 0
            assert stats["available_count"] == 0
            assert stats["skipped_count"] == 0
            assert stats["total_citations"] == 0


class TestGetActDiscoveryService:
    """Tests for factory function."""

    def test_returns_singleton(self) -> None:
        """Should return same instance on multiple calls."""
        get_act_discovery_service.cache_clear()

        service1 = get_act_discovery_service()
        service2 = get_act_discovery_service()

        assert service1 is service2

    def test_returns_service_instance(self) -> None:
        """Should return ActDiscoveryService instance."""
        get_act_discovery_service.cache_clear()

        service = get_act_discovery_service()

        assert isinstance(service, ActDiscoveryService)
