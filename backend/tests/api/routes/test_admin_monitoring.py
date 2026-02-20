"""Tests for admin chunk metrics monitoring endpoint.

Gap 7: Vector Quantization — Monitoring Dashboard
Gap 8: HNSW Index Tuning — Index Configuration Visibility
"""

from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request

from app.api.routes.admin.monitoring import (
    GLOBAL_CHUNK_THRESHOLD,
    MATTER_CHUNK_THRESHOLD,
    _get_quantization_recommendation,
)


def _make_fake_request() -> Request:
    """Create a minimal Starlette Request that satisfies slowapi's type check."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/admin/chunk-metrics",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
    }
    return Request(scope)


# =============================================================================
# _get_quantization_recommendation unit tests
# =============================================================================


class TestGetQuantizationRecommendation:
    """Test the progressive recommendation logic."""

    def test_low_count_no_action(self):
        """Under 100K chunks, no alerts: 'No action needed'."""
        result = _get_quantization_recommendation(
            global_total=15_000,
            any_matter_alert=False,
            global_exceeds=False,
        )
        assert "No action needed" in result
        assert "float32" in result

    def test_approaching_threshold(self):
        """100K-500K chunks: 'Approaching threshold'."""
        result = _get_quantization_recommendation(
            global_total=150_000,
            any_matter_alert=False,
            global_exceeds=False,
        )
        assert "Approaching" in result
        assert "No action needed" in result

    def test_matter_alert_only(self):
        """Single matter exceeds 50K: matter-specific warning."""
        result = _get_quantization_recommendation(
            global_total=80_000,
            any_matter_alert=True,
            global_exceeds=False,
        )
        assert "50K chunks" in result
        assert "recall quality" in result

    def test_global_exceeds(self):
        """Global exceeds 500K: recommend halfvec."""
        result = _get_quantization_recommendation(
            global_total=600_000,
            any_matter_alert=False,
            global_exceeds=True,
        )
        assert "halfvec" in result
        assert "float16" in result

    def test_over_one_million_urgent(self):
        """Over 1M chunks: URGENT recommendation."""
        result = _get_quantization_recommendation(
            global_total=1_200_000,
            any_matter_alert=True,
            global_exceeds=True,
        )
        assert "URGENT" in result

    def test_priority_order_million_over_global(self):
        """1M+ takes priority over global_exceeds."""
        result = _get_quantization_recommendation(
            global_total=1_500_000,
            any_matter_alert=True,
            global_exceeds=True,
        )
        # Should hit the >1M branch, not the >500K branch
        assert "URGENT" in result

    def test_priority_order_global_over_matter(self):
        """Global exceeds takes priority over matter alert when both true."""
        result = _get_quantization_recommendation(
            global_total=600_000,
            any_matter_alert=True,
            global_exceeds=True,
        )
        # Should hit global_exceeds branch, not matter alert branch
        assert "halfvec" in result


# =============================================================================
# Threshold constants tests
# =============================================================================


class TestThresholdConstants:
    """Verify thresholds are set to expected values."""

    def test_matter_threshold(self):
        assert MATTER_CHUNK_THRESHOLD == 50_000

    def test_global_threshold(self):
        assert GLOBAL_CHUNK_THRESHOLD == 500_000


# =============================================================================
# Endpoint integration tests (mocked Supabase)
# =============================================================================


def _make_mock_rpc_response(data):
    """Create a mock Supabase RPC execute() response."""
    mock_response = MagicMock()
    mock_response.data = data
    return mock_response


def _make_mock_supabase(matter_data=None, global_data=None):
    """Create a mock Supabase client that returns data for both RPCs."""
    if matter_data is None:
        matter_data = [
            {
                "matter_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "matter_title": "Smith v Jones",
                "total_chunks": 5000,
                "parent_chunks": 800,
                "child_chunks": 4000,
                "table_chunks": 200,
                "has_voyage_embeddings": 4500,
            }
        ]
    if global_data is None:
        global_data = [
            {
                "total_chunks": 15000,
                "total_with_embedding": 14500,
                "total_with_voyage": 12000,
                "total_matters": 3,
            }
        ]

    mock_client = MagicMock()

    def rpc_side_effect(func_name):
        mock_chain = MagicMock()
        if func_name == "get_chunk_metrics":
            mock_chain.execute.return_value = _make_mock_rpc_response(matter_data)
        elif func_name == "get_global_chunk_count":
            mock_chain.execute.return_value = _make_mock_rpc_response(global_data)
        return mock_chain

    mock_client.rpc.side_effect = rpc_side_effect
    return mock_client


@pytest.mark.asyncio
async def test_chunk_metrics_builds_correct_response():
    """Test the endpoint handler builds correct response structure by calling it directly."""
    from app.api.routes.admin.monitoring import get_chunk_metrics

    mock_admin = MagicMock()
    mock_admin.id = "admin-user-id"
    mock_admin.email = "admin@example.com"

    mock_request = _make_fake_request()
    mock_supabase = _make_mock_supabase()

    with patch(
        "app.api.routes.admin.monitoring.get_service_client",
        return_value=mock_supabase,
    ):
        result = await get_chunk_metrics(request=mock_request, admin=mock_admin)

    # Verify top-level structure
    assert "global" in result
    assert "matters" in result
    assert "thresholds" in result
    assert "indexConfig" in result
    assert "alertsTriggered" in result
    assert "lastUpdated" in result

    # Verify global data
    g = result["global"]
    assert g["totalChunks"] == 15000
    assert g["totalWithEmbedding"] == 14500
    assert g["totalWithVoyage"] == 12000
    assert g["totalMatters"] == 3
    assert g["exceedsGlobalThreshold"] is False
    assert g["globalThreshold"] == GLOBAL_CHUNK_THRESHOLD

    # Verify matters
    assert len(result["matters"]) == 1
    m = result["matters"][0]
    assert m["matterId"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert m["matterTitle"] == "Smith v Jones"
    assert m["totalChunks"] == 5000
    assert m["parentChunks"] == 800
    assert m["childChunks"] == 4000
    assert m["tableChunks"] == 200
    assert m["hasVoyageEmbeddings"] == 4500
    assert m["exceedsThreshold"] is False

    # Verify thresholds
    assert result["thresholds"]["perMatter"] == MATTER_CHUNK_THRESHOLD
    assert result["thresholds"]["global"] == GLOBAL_CHUNK_THRESHOLD

    # Verify indexConfig
    ic = result["indexConfig"]
    assert ic["m"] == 16
    assert ic["efConstruction"] == 128
    assert ic["efSearch"] == 80
    assert ic["vectorDimensions"]["openai"] == 1536
    assert ic["vectorDimensions"]["voyage"] == 1024

    # Verify no alerts at 15K chunks
    assert result["alertsTriggered"] is False


@pytest.mark.asyncio
async def test_chunk_metrics_alerts_triggered_on_matter_threshold():
    """Test that alerts fire when a matter exceeds MATTER_CHUNK_THRESHOLD."""
    from app.api.routes.admin.monitoring import get_chunk_metrics

    mock_admin = MagicMock()
    mock_admin.id = "admin-user-id"
    mock_admin.email = "admin@example.com"

    mock_request = _make_fake_request()
    mock_supabase = _make_mock_supabase(
        matter_data=[
            {
                "matter_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "matter_title": "Big Matter",
                "total_chunks": 60_000,  # Exceeds 50K threshold
                "parent_chunks": 10_000,
                "child_chunks": 48_000,
                "table_chunks": 2_000,
                "has_voyage_embeddings": 55_000,
            }
        ],
        global_data=[
            {
                "total_chunks": 60_000,
                "total_with_embedding": 58_000,
                "total_with_voyage": 55_000,
                "total_matters": 1,
            }
        ],
    )

    with patch(
        "app.api.routes.admin.monitoring.get_service_client",
        return_value=mock_supabase,
    ):
        result = await get_chunk_metrics(request=mock_request, admin=mock_admin)

    assert result["alertsTriggered"] is True
    assert result["matters"][0]["exceedsThreshold"] is True
    assert "50K chunks" in result["indexConfig"]["recommendation"]


@pytest.mark.asyncio
async def test_chunk_metrics_alerts_triggered_on_global_threshold():
    """Test that alerts fire when global count exceeds GLOBAL_CHUNK_THRESHOLD."""
    from app.api.routes.admin.monitoring import get_chunk_metrics

    mock_admin = MagicMock()
    mock_admin.id = "admin-user-id"
    mock_admin.email = "admin@example.com"

    mock_request = _make_fake_request()
    mock_supabase = _make_mock_supabase(
        matter_data=[],
        global_data=[
            {
                "total_chunks": 600_000,  # Exceeds 500K threshold
                "total_with_embedding": 580_000,
                "total_with_voyage": 550_000,
                "total_matters": 20,
            }
        ],
    )

    with patch(
        "app.api.routes.admin.monitoring.get_service_client",
        return_value=mock_supabase,
    ):
        result = await get_chunk_metrics(request=mock_request, admin=mock_admin)

    assert result["alertsTriggered"] is True
    assert result["global"]["exceedsGlobalThreshold"] is True
    assert "halfvec" in result["indexConfig"]["recommendation"]


@pytest.mark.asyncio
async def test_chunk_metrics_empty_data():
    """Test graceful handling of empty RPC results."""
    from app.api.routes.admin.monitoring import get_chunk_metrics

    mock_admin = MagicMock()
    mock_admin.id = "admin-user-id"
    mock_admin.email = "admin@example.com"

    mock_request = _make_fake_request()
    mock_supabase = _make_mock_supabase(matter_data=[], global_data=[])

    with patch(
        "app.api.routes.admin.monitoring.get_service_client",
        return_value=mock_supabase,
    ):
        result = await get_chunk_metrics(request=mock_request, admin=mock_admin)

    assert result["global"]["totalChunks"] == 0
    assert result["matters"] == []
    assert result["alertsTriggered"] is False
