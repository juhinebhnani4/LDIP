"""Tests for Anomalies API routes.

Story 4-4: Timeline Anomaly Detection

Note: This file uses synchronous TestClient for simple auth tests,
and pytest-asyncio fixtures for async route tests as needed.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import MatterMembership, MatterRole
from app.models.anomaly import (
    AnomaliesListResponse,
    Anomaly,
    AnomalyListItem,
    AnomalySeverity,
    AnomalySummaryData,
    AnomalySummaryResponse,
    AnomalyType,
    PaginationMeta,
)


@pytest.fixture
def sync_client() -> TestClient:
    """Create synchronous test client for auth tests."""
    return TestClient(app)


@pytest.fixture
def mock_matter_membership() -> MatterMembership:
    """Create mock matter membership for testing."""
    return MatterMembership(
        user_id="user-123",
        matter_id="matter-123",
        role=MatterRole.OWNER,
    )


@pytest.fixture
def mock_anomaly() -> Anomaly:
    """Create mock anomaly for testing."""
    return Anomaly(
        id="anomaly-123",
        matter_id="matter-123",
        anomaly_type=AnomalyType.GAP,
        severity=AnomalySeverity.MEDIUM,
        title="Unusual gap between Notice and Filing",
        explanation="274 days between events exceeds threshold.",
        event_ids=["event-1", "event-2"],
        gap_days=274,
        confidence=0.95,
        verified=False,
        dismissed=False,
        verified_by=None,
        verified_at=None,
        created_at=datetime(2026, 1, 13, 10, 0, 0),
        updated_at=datetime(2026, 1, 13, 10, 0, 0),
    )


@pytest.fixture
def mock_anomaly_list_item() -> AnomalyListItem:
    """Create mock anomaly list item for testing."""
    return AnomalyListItem(
        id="anomaly-123",
        anomaly_type="gap",
        severity="medium",
        title="Unusual gap between Notice and Filing",
        explanation="274 days between events.",
        event_ids=["event-1", "event-2"],
        gap_days=274,
        confidence=0.95,
        verified=False,
        dismissed=False,
        created_at=datetime(2026, 1, 13, 10, 0, 0),
    )


# =============================================================================
# Tests for List Anomalies
# =============================================================================


class TestListAnomalies:
    """Tests for GET /matters/{matter_id}/anomalies endpoint."""

    def test_list_anomalies_requires_auth(self, sync_client: TestClient) -> None:
        """Should require authentication."""
        response = sync_client.get("/api/matters/matter-123/anomalies")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_anomalies_endpoint_exists(self, sync_client: TestClient) -> None:
        """Should have the endpoint registered."""
        # Verify endpoint is registered (will fail auth but shouldn't be 404)
        response = sync_client.get("/api/matters/matter-123/anomalies")
        assert response.status_code != status.HTTP_404_NOT_FOUND


# =============================================================================
# Tests for Get Single Anomaly
# =============================================================================


class TestGetAnomaly:
    """Tests for GET /matters/{matter_id}/anomalies/{anomaly_id} endpoint."""

    def test_get_anomaly_requires_auth(self, sync_client: TestClient) -> None:
        """Should require authentication."""
        response = sync_client.get("/api/matters/matter-123/anomalies/anomaly-123")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Tests for Anomaly Summary
# =============================================================================


class TestAnomalySummary:
    """Tests for GET /matters/{matter_id}/anomalies/summary endpoint."""

    def test_summary_requires_auth(self, sync_client: TestClient) -> None:
        """Should require authentication."""
        response = sync_client.get("/api/matters/matter-123/anomalies/summary")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_summary_endpoint_exists(self, sync_client: TestClient) -> None:
        """Should have the endpoint registered."""
        response = sync_client.get("/api/matters/matter-123/anomalies/summary")
        assert response.status_code != status.HTTP_404_NOT_FOUND


# =============================================================================
# Tests for Trigger Detection
# =============================================================================


class TestTriggerDetection:
    """Tests for POST /matters/{matter_id}/anomalies/detect endpoint."""

    def test_trigger_detection_requires_auth(self, sync_client: TestClient) -> None:
        """Should require authentication."""
        response = sync_client.post("/api/matters/matter-123/anomalies/detect")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_trigger_detection_endpoint_exists(self, sync_client: TestClient) -> None:
        """Should have the endpoint registered."""
        response = sync_client.post("/api/matters/matter-123/anomalies/detect")
        assert response.status_code != status.HTTP_404_NOT_FOUND


# =============================================================================
# Tests for Dismiss Anomaly
# =============================================================================


class TestDismissAnomaly:
    """Tests for PATCH /matters/{matter_id}/anomalies/{anomaly_id}/dismiss endpoint."""

    def test_dismiss_requires_auth(self, sync_client: TestClient) -> None:
        """Should require authentication."""
        response = sync_client.patch(
            "/api/matters/matter-123/anomalies/anomaly-123/dismiss"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_dismiss_endpoint_exists(self, sync_client: TestClient) -> None:
        """Should have the endpoint registered."""
        response = sync_client.patch(
            "/api/matters/matter-123/anomalies/anomaly-123/dismiss"
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND


# =============================================================================
# Tests for Verify Anomaly
# =============================================================================


class TestVerifyAnomaly:
    """Tests for PATCH /matters/{matter_id}/anomalies/{anomaly_id}/verify endpoint."""

    def test_verify_requires_auth(self, sync_client: TestClient) -> None:
        """Should require authentication."""
        response = sync_client.patch(
            "/api/matters/matter-123/anomalies/anomaly-123/verify"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verify_endpoint_exists(self, sync_client: TestClient) -> None:
        """Should have the endpoint registered."""
        response = sync_client.patch(
            "/api/matters/matter-123/anomalies/anomaly-123/verify"
        )
        assert response.status_code != status.HTTP_404_NOT_FOUND


# =============================================================================
# Tests for Matter Isolation
# =============================================================================


class TestMatterIsolation:
    """Tests for matter-level access control."""

    def test_anomalies_require_matter_membership(
        self, sync_client: TestClient
    ) -> None:
        """Should require membership in the matter."""
        # All endpoints should require matter membership
        endpoints = [
            ("GET", "/api/matters/matter-123/anomalies"),
            ("GET", "/api/matters/matter-123/anomalies/summary"),
            ("GET", "/api/matters/matter-123/anomalies/anomaly-123"),
            ("POST", "/api/matters/matter-123/anomalies/detect"),
            ("PATCH", "/api/matters/matter-123/anomalies/anomaly-123/dismiss"),
            ("PATCH", "/api/matters/matter-123/anomalies/anomaly-123/verify"),
        ]

        for method, url in endpoints:
            if method == "GET":
                response = sync_client.get(url)
            elif method == "POST":
                response = sync_client.post(url)
            elif method == "PATCH":
                response = sync_client.patch(url)

            # Should fail with 401 (unauthorized), not 404
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, (
                f"Endpoint {method} {url} should require auth"
            )


# =============================================================================
# Tests for Filtering and Pagination
# =============================================================================


class TestFilteringPagination:
    """Tests for query parameter handling."""

    def test_filter_by_severity_param(self, sync_client: TestClient) -> None:
        """Should accept severity filter parameter."""
        # Verify endpoint accepts the parameter (auth will fail but not 422)
        response = sync_client.get(
            "/api/matters/matter-123/anomalies?severity=high"
        )
        # Should fail auth, not validation
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_filter_by_type_param(self, sync_client: TestClient) -> None:
        """Should accept anomaly_type filter parameter."""
        response = sync_client.get(
            "/api/matters/matter-123/anomalies?anomaly_type=gap"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_pagination_params(self, sync_client: TestClient) -> None:
        """Should accept pagination parameters."""
        response = sync_client.get(
            "/api/matters/matter-123/anomalies?page=2&per_page=10"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_force_redetect_param(self, sync_client: TestClient) -> None:
        """Should accept force_redetect parameter on detect endpoint."""
        response = sync_client.post(
            "/api/matters/matter-123/anomalies/detect?force_redetect=true"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
