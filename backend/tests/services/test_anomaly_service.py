"""Tests for Anomaly Service.

Story 4-4: Timeline Anomaly Detection
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.anomaly import (
    AnomaliesListResponse,
    AnomalyCreate,
    AnomalySeverity,
    AnomalySummaryResponse,
    AnomalyType,
)
from app.services.anomaly_service import (
    AnomalyService,
    get_anomaly_service,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def anomaly_service() -> AnomalyService:
    """Create a fresh AnomalyService instance."""
    return AnomalyService()


@pytest.fixture
def sample_anomaly_create() -> AnomalyCreate:
    """Create a sample AnomalyCreate for testing."""
    return AnomalyCreate(
        matter_id="matter-123",
        anomaly_type=AnomalyType.GAP,
        severity=AnomalySeverity.MEDIUM,
        title="Unusual gap between Notice and Filing",
        explanation="274 days between events exceeds threshold.",
        event_ids=["event-1", "event-2"],
        gap_days=274,
        confidence=0.95,
    )


@pytest.fixture
def mock_supabase_response() -> dict:
    """Create a mock Supabase response for anomaly."""
    return {
        "id": "anomaly-uuid-123",
        "matter_id": "matter-123",
        "anomaly_type": "gap",
        "severity": "medium",
        "title": "Unusual gap between Notice and Filing",
        "explanation": "274 days between events.",
        "event_ids": ["event-1", "event-2"],
        "expected_order": None,
        "actual_order": None,
        "gap_days": 274,
        "confidence": 0.95,
        "verified": False,
        "dismissed": False,
        "verified_by": None,
        "verified_at": None,
        "created_at": "2026-01-13T10:00:00+00:00",
        "updated_at": "2026-01-13T10:00:00+00:00",
    }


# =============================================================================
# Tests for Factory Function
# =============================================================================


class TestAnomalyServiceFactory:
    """Tests for get_anomaly_service factory."""

    def test_factory_returns_singleton(self) -> None:
        """Should return same instance on multiple calls."""
        # Clear the cache first
        get_anomaly_service.cache_clear()

        service1 = get_anomaly_service()
        service2 = get_anomaly_service()

        assert service1 is service2

        # Clean up
        get_anomaly_service.cache_clear()


# =============================================================================
# Tests for Save Anomalies
# =============================================================================


class TestSaveAnomalies:
    """Tests for saving anomalies to database."""

    @pytest.mark.asyncio
    async def test_save_empty_list_returns_empty(
        self, anomaly_service: AnomalyService
    ) -> None:
        """Should return empty list when saving empty anomalies."""
        result = await anomaly_service.save_anomalies([])
        assert result == []

    @pytest.mark.asyncio
    async def test_save_anomalies_success(
        self,
        anomaly_service: AnomalyService,
        sample_anomaly_create: AnomalyCreate,
    ) -> None:
        """Should save anomalies and return IDs."""
        mock_response = MagicMock()
        mock_response.data = [{"id": "anomaly-123"}]

        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = mock_response

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch.object(anomaly_service, "_client", mock_client):
            result = await anomaly_service.save_anomalies([sample_anomaly_create])

        assert result == ["anomaly-123"]
        mock_client.table.assert_called_with("anomalies")


# =============================================================================
# Tests for Get Anomalies
# =============================================================================


class TestGetAnomalies:
    """Tests for retrieving anomalies."""

    @pytest.mark.asyncio
    async def test_get_anomalies_for_matter(
        self,
        anomaly_service: AnomalyService,
        mock_supabase_response: dict,
    ) -> None:
        """Should retrieve paginated anomalies for matter."""
        mock_response = MagicMock()
        mock_response.data = [mock_supabase_response]
        mock_response.count = 1

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = mock_response

        mock_table = MagicMock()
        mock_table.select.return_value = mock_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch.object(anomaly_service, "_client", mock_client):
            result = await anomaly_service.get_anomalies_for_matter(
                matter_id="matter-123",
                page=1,
                per_page=20,
            )

        assert isinstance(result, AnomaliesListResponse)
        assert len(result.data) == 1
        assert result.data[0].id == "anomaly-uuid-123"
        assert result.meta.total == 1

    @pytest.mark.asyncio
    async def test_get_anomaly_by_id_found(
        self,
        anomaly_service: AnomalyService,
        mock_supabase_response: dict,
    ) -> None:
        """Should retrieve single anomaly by ID."""
        mock_response = MagicMock()
        mock_response.data = mock_supabase_response

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.single.return_value = mock_query
        mock_query.execute.return_value = mock_response

        mock_table = MagicMock()
        mock_table.select.return_value = mock_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch.object(anomaly_service, "_client", mock_client):
            result = await anomaly_service.get_anomaly_by_id(
                anomaly_id="anomaly-uuid-123",
                matter_id="matter-123",
            )

        assert result is not None
        assert result.id == "anomaly-uuid-123"
        assert result.anomaly_type == AnomalyType.GAP

    @pytest.mark.asyncio
    async def test_get_anomaly_by_id_not_found(
        self, anomaly_service: AnomalyService
    ) -> None:
        """Should return None when anomaly not found."""
        mock_response = MagicMock()
        mock_response.data = None

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.single.return_value = mock_query
        mock_query.execute.side_effect = Exception("No rows found")

        mock_table = MagicMock()
        mock_table.select.return_value = mock_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch.object(anomaly_service, "_client", mock_client):
            result = await anomaly_service.get_anomaly_by_id(
                anomaly_id="not-found",
                matter_id="matter-123",
            )

        assert result is None


# =============================================================================
# Tests for Dismiss/Verify Anomalies
# =============================================================================


class TestDismissVerify:
    """Tests for dismissing and verifying anomalies."""

    @pytest.mark.asyncio
    async def test_dismiss_anomaly(
        self,
        anomaly_service: AnomalyService,
        mock_supabase_response: dict,
    ) -> None:
        """Should dismiss anomaly and set dismissed flag."""
        # Update response for dismiss
        dismissed_response = mock_supabase_response.copy()
        dismissed_response["dismissed"] = True
        dismissed_response["verified_by"] = "user-123"
        dismissed_response["verified_at"] = "2026-01-13T12:00:00+00:00"

        mock_update_response = MagicMock()
        mock_update_response.data = [dismissed_response]

        mock_update_query = MagicMock()
        mock_update_query.eq.return_value = mock_update_query
        mock_update_query.execute.return_value = mock_update_response

        mock_select_response = MagicMock()
        mock_select_response.data = dismissed_response

        mock_select_query = MagicMock()
        mock_select_query.eq.return_value = mock_select_query
        mock_select_query.single.return_value = mock_select_query
        mock_select_query.execute.return_value = mock_select_response

        mock_table = MagicMock()
        mock_table.update.return_value = mock_update_query
        mock_table.select.return_value = mock_select_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch.object(anomaly_service, "_client", mock_client):
            result = await anomaly_service.dismiss_anomaly(
                anomaly_id="anomaly-uuid-123",
                matter_id="matter-123",
                user_id="user-123",
            )

        assert result is not None
        mock_table.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_anomaly(
        self,
        anomaly_service: AnomalyService,
        mock_supabase_response: dict,
    ) -> None:
        """Should verify anomaly and set verified flag."""
        verified_response = mock_supabase_response.copy()
        verified_response["verified"] = True
        verified_response["verified_by"] = "user-123"
        verified_response["verified_at"] = "2026-01-13T12:00:00+00:00"

        mock_update_response = MagicMock()
        mock_update_response.data = [verified_response]

        mock_update_query = MagicMock()
        mock_update_query.eq.return_value = mock_update_query
        mock_update_query.execute.return_value = mock_update_response

        mock_select_response = MagicMock()
        mock_select_response.data = verified_response

        mock_select_query = MagicMock()
        mock_select_query.eq.return_value = mock_select_query
        mock_select_query.single.return_value = mock_select_query
        mock_select_query.execute.return_value = mock_select_response

        mock_table = MagicMock()
        mock_table.update.return_value = mock_update_query
        mock_table.select.return_value = mock_select_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch.object(anomaly_service, "_client", mock_client):
            result = await anomaly_service.verify_anomaly(
                anomaly_id="anomaly-uuid-123",
                matter_id="matter-123",
                user_id="user-123",
            )

        assert result is not None
        mock_table.update.assert_called_once()


# =============================================================================
# Tests for Delete and Summary
# =============================================================================


class TestDeleteAndSummary:
    """Tests for delete and summary operations."""

    @pytest.mark.asyncio
    async def test_delete_anomalies_for_matter(
        self, anomaly_service: AnomalyService
    ) -> None:
        """Should delete all anomalies for matter."""
        mock_count_response = MagicMock()
        mock_count_response.count = 5

        mock_count_query = MagicMock()
        mock_count_query.eq.return_value = mock_count_query
        mock_count_query.execute.return_value = mock_count_response

        mock_delete_query = MagicMock()
        mock_delete_query.eq.return_value = mock_delete_query
        mock_delete_query.execute.return_value = MagicMock()

        mock_table = MagicMock()
        mock_table.select.return_value = mock_count_query
        mock_table.delete.return_value = mock_delete_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch.object(anomaly_service, "_client", mock_client):
            result = await anomaly_service.delete_anomalies_for_matter("matter-123")

        assert result == 5

    @pytest.mark.asyncio
    async def test_get_anomaly_summary(
        self, anomaly_service: AnomalyService
    ) -> None:
        """Should return summary counts."""
        mock_response = MagicMock()
        mock_response.data = [
            {"severity": "high", "anomaly_type": "gap", "verified": False, "dismissed": False},
            {"severity": "high", "anomaly_type": "sequence_violation", "verified": True, "dismissed": False},
            {"severity": "medium", "anomaly_type": "gap", "verified": False, "dismissed": True},
            {"severity": "low", "anomaly_type": "duplicate", "verified": False, "dismissed": False},
        ]

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = mock_response

        mock_table = MagicMock()
        mock_table.select.return_value = mock_query

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch.object(anomaly_service, "_client", mock_client):
            result = await anomaly_service.get_anomaly_summary("matter-123")

        assert isinstance(result, AnomalySummaryResponse)
        assert result.data.total == 4
        assert result.data.by_severity["high"] == 2
        assert result.data.by_severity["medium"] == 1
        assert result.data.by_severity["low"] == 1
        assert result.data.by_type["gap"] == 2
        assert result.data.verified == 1
        assert result.data.dismissed == 1
        assert result.data.unreviewed == 2
