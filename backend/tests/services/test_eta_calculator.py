"""Tests for ETA Calculator Service.

Story 5.7: Processing ETA Display

Test Categories:
- ETA calculation with various scenarios
- Rolling average computation
- Worker count integration
- Completion recording
- Confidence levels
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.eta_calculator import (
    ETACalculator,
    ETAResult,
    FALLBACK_SECONDS_PER_PAGE,
    MINIMUM_SAMPLES_FOR_CONFIDENCE,
    REDIS_PROCESSING_TIMES_KEY,
    REDIS_AVG_TIME_KEY,
)


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.lpush = AsyncMock()
    redis.ltrim = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def mock_queue_metrics_service():
    """Create mock queue metrics service."""
    service = MagicMock()
    service.get_active_worker_count = AsyncMock(return_value=2)
    return service


@pytest.fixture
def eta_calculator(mock_redis_client, mock_queue_metrics_service):
    """Create ETA calculator with mocks."""
    calc = ETACalculator(
        redis_client=mock_redis_client,
        queue_metrics_service=mock_queue_metrics_service,
    )
    return calc


# =============================================================================
# ETA Calculation Tests
# =============================================================================


class TestGetProcessingEta:
    """Test ETA calculation logic."""

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_pending_docs(self, eta_calculator) -> None:
        """Should return zero ETA when no pending documents."""
        result = await eta_calculator.get_processing_eta("matter-123", [])

        assert result.min_seconds == 0
        assert result.max_seconds == 0
        assert result.best_guess_seconds == 0
        assert result.confidence == "high"
        assert result.factors.get("reason") == "no_pending_docs"

    @pytest.mark.asyncio
    async def test_uses_fallback_time_when_no_history(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should use fallback seconds per page when no history."""
        mock_redis_client.lrange = AsyncMock(return_value=[])

        pending_docs = [{"page_count": 10}, {"page_count": 20}]
        result = await eta_calculator.get_processing_eta("matter-123", pending_docs)

        # 30 pages * 3 seconds/page / 2 workers = 45 seconds base
        assert result.best_guess_seconds >= 30  # Minimum floor
        assert result.confidence == "low"  # No samples
        assert result.factors["total_pages"] == 30
        assert result.factors["sample_count"] == 0

    @pytest.mark.asyncio
    async def test_uses_historical_average_when_available(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should calculate weighted average from history."""
        # History entries: "page_count:time_ms"
        mock_redis_client.lrange = AsyncMock(
            return_value=[
                "10:20000",  # 10 pages, 20s = 2s/page
                "20:40000",  # 20 pages, 40s = 2s/page
                "5:10000",   # 5 pages, 10s = 2s/page
            ]
        )

        pending_docs = [{"page_count": 10}]
        result = await eta_calculator.get_processing_eta("matter-123", pending_docs)

        # Average is 2s/page, 10 pages / 2 workers = 10 seconds base
        assert result.confidence == "low"  # Only 3 samples
        assert result.factors["sample_count"] == 3
        assert result.factors["avg_seconds_per_page"] == 2.0

    @pytest.mark.asyncio
    async def test_high_confidence_with_enough_samples(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should report high confidence with 10+ samples."""
        # Create 15 sample entries
        history = [f"10:{20000}" for _ in range(15)]
        mock_redis_client.lrange = AsyncMock(return_value=history)

        pending_docs = [{"page_count": 10}]
        result = await eta_calculator.get_processing_eta("matter-123", pending_docs)

        assert result.confidence == "high"
        assert result.factors["sample_count"] == 15

    @pytest.mark.asyncio
    async def test_medium_confidence_with_some_samples(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should report medium confidence with 5-9 samples."""
        history = [f"10:{20000}" for _ in range(7)]
        mock_redis_client.lrange = AsyncMock(return_value=history)

        pending_docs = [{"page_count": 10}]
        result = await eta_calculator.get_processing_eta("matter-123", pending_docs)

        assert result.confidence == "medium"
        assert result.factors["sample_count"] == 7

    @pytest.mark.asyncio
    async def test_uses_cached_average(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should use cached average when available."""
        mock_redis_client.get = AsyncMock(return_value="2.5:20")  # 2.5s/page, 20 samples

        pending_docs = [{"page_count": 10}]
        result = await eta_calculator.get_processing_eta("matter-123", pending_docs)

        assert result.factors["avg_seconds_per_page"] == 2.5
        assert result.factors["sample_count"] == 20
        assert result.confidence == "high"

    @pytest.mark.asyncio
    async def test_handles_missing_page_count(self, eta_calculator, mock_redis_client) -> None:
        """Should default to 1 page when page_count missing."""
        mock_redis_client.lrange = AsyncMock(return_value=[])

        pending_docs = [{"name": "doc1"}, {"page_count": 10}]  # First doc missing page_count
        result = await eta_calculator.get_processing_eta("matter-123", pending_docs)

        # 11 pages total (1 default + 10)
        assert result.factors["total_pages"] == 11

    @pytest.mark.asyncio
    async def test_min_seconds_floor(self, eta_calculator, mock_redis_client) -> None:
        """Should enforce minimum 30 seconds floor."""
        mock_redis_client.get = AsyncMock(return_value="0.1:50")  # Very fast: 0.1s/page

        pending_docs = [{"page_count": 1}]
        result = await eta_calculator.get_processing_eta("matter-123", pending_docs)

        assert result.min_seconds >= 30


# =============================================================================
# Worker Count Tests
# =============================================================================


class TestGetActiveWorkerCount:
    """Test worker count retrieval."""

    @pytest.mark.asyncio
    async def test_uses_queue_metrics_service(
        self, eta_calculator, mock_queue_metrics_service
    ) -> None:
        """Should use queue metrics service when available."""
        mock_queue_metrics_service.get_active_worker_count = AsyncMock(return_value=5)

        count = await eta_calculator.get_active_worker_count()

        assert count == 5
        mock_queue_metrics_service.get_active_worker_count.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_service_error(self, mock_redis_client) -> None:
        """Should fall back to Celery inspect on service error."""
        failing_service = MagicMock()
        failing_service.get_active_worker_count = AsyncMock(side_effect=Exception("Error"))

        calc = ETACalculator(
            redis_client=mock_redis_client,
            queue_metrics_service=failing_service,
        )

        with patch("app.workers.celery.celery_app") as mock_celery:
            mock_inspector = MagicMock()
            mock_inspector.active.return_value = {"worker1": [], "worker2": []}
            mock_celery.control.inspect.return_value = mock_inspector

            count = await calc.get_active_worker_count()

            assert count == 2

    @pytest.mark.asyncio
    async def test_default_fallback_when_all_fail(self, mock_redis_client) -> None:
        """Should return 2 as final fallback."""
        calc = ETACalculator(redis_client=mock_redis_client, queue_metrics_service=None)

        with patch("app.workers.celery.celery_app") as mock_celery:
            mock_celery.control.inspect.side_effect = Exception("Celery error")

            count = await calc.get_active_worker_count()

            assert count == 2  # Conservative fallback


# =============================================================================
# Completion Recording Tests
# =============================================================================


class TestRecordCompletion:
    """Test recording document completions."""

    @pytest.mark.asyncio
    async def test_records_valid_completion(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should record completion to Redis."""
        await eta_calculator.record_completion(
            document_id="doc-123",
            page_count=10,
            processing_time_ms=30000,
        )

        mock_redis_client.lpush.assert_called_once_with(
            REDIS_PROCESSING_TIMES_KEY, "10:30000"
        )
        mock_redis_client.ltrim.assert_called_once()
        mock_redis_client.delete.assert_called_once_with(REDIS_AVG_TIME_KEY)

    @pytest.mark.asyncio
    async def test_ignores_invalid_page_count(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should not record if page_count is invalid."""
        await eta_calculator.record_completion(
            document_id="doc-123",
            page_count=0,
            processing_time_ms=30000,
        )

        mock_redis_client.lpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_invalid_processing_time(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should not record if processing_time is invalid."""
        await eta_calculator.record_completion(
            document_id="doc-123",
            page_count=10,
            processing_time_ms=0,
        )

        mock_redis_client.lpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_redis_error(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should handle Redis errors gracefully."""
        mock_redis_client.lpush = AsyncMock(side_effect=Exception("Redis error"))

        # Should not raise
        await eta_calculator.record_completion(
            document_id="doc-123",
            page_count=10,
            processing_time_ms=30000,
        )


# =============================================================================
# Weighted Average Tests
# =============================================================================


class TestGetWeightedAvgTime:
    """Test weighted average calculation."""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_empty_history(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should return fallback when no history."""
        mock_redis_client.lrange = AsyncMock(return_value=[])

        avg, count = await eta_calculator.get_weighted_avg_time()

        assert avg == FALLBACK_SECONDS_PER_PAGE
        assert count == 0

    @pytest.mark.asyncio
    async def test_computes_weighted_average(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should compute weighted average by page count."""
        mock_redis_client.lrange = AsyncMock(
            return_value=[
                "10:10000",  # 10 pages, 10s
                "20:60000",  # 20 pages, 60s
            ]
        )

        avg, count = await eta_calculator.get_weighted_avg_time()

        # Total: 30 pages, 70s = 2.33s/page
        expected_avg = 70 / 30
        assert abs(avg - expected_avg) < 0.01
        assert count == 2

    @pytest.mark.asyncio
    async def test_skips_malformed_entries(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should skip malformed history entries."""
        mock_redis_client.lrange = AsyncMock(
            return_value=[
                "10:10000",
                "invalid",
                "20:20000",
            ]
        )

        avg, count = await eta_calculator.get_weighted_avg_time()

        # Only valid entries: 30 pages, 30s = 1s/page
        assert count == 2

    @pytest.mark.asyncio
    async def test_caches_computed_average(
        self, eta_calculator, mock_redis_client
    ) -> None:
        """Should cache computed average."""
        mock_redis_client.lrange = AsyncMock(return_value=["10:20000"])

        await eta_calculator.get_weighted_avg_time()

        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert REDIS_AVG_TIME_KEY in call_args[0]


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_zero_workers(
        self, eta_calculator, mock_queue_metrics_service, mock_redis_client
    ) -> None:
        """Should use minimum 1 worker to prevent division by zero."""
        mock_queue_metrics_service.get_active_worker_count = AsyncMock(return_value=0)
        mock_redis_client.get = AsyncMock(return_value="2:10")

        pending_docs = [{"page_count": 10}]
        result = await eta_calculator.get_processing_eta("matter-123", pending_docs)

        # Should not raise, should use 1 worker minimum
        assert result.best_guess_seconds > 0
        assert result.factors["worker_count"] >= 1

    @pytest.mark.asyncio
    async def test_handles_redis_connection_error(self, mock_queue_metrics_service) -> None:
        """Should handle Redis connection errors."""
        failing_redis = MagicMock()
        failing_redis.get = AsyncMock(side_effect=Exception("Connection refused"))
        failing_redis.lrange = AsyncMock(side_effect=Exception("Connection refused"))

        calc = ETACalculator(
            redis_client=failing_redis,
            queue_metrics_service=mock_queue_metrics_service,
        )

        pending_docs = [{"page_count": 10}]
        result = await calc.get_processing_eta("matter-123", pending_docs)

        # Should use fallback values
        assert result.factors["avg_seconds_per_page"] == FALLBACK_SECONDS_PER_PAGE
