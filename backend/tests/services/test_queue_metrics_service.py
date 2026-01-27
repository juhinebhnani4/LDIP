"""Tests for Queue Metrics Service.

Story 5.6: Queue Depth Visibility Dashboard

Test Categories:
- Queue depth retrieval from Redis
- Worker count via Celery inspect
- Health check endpoint
- Alert threshold handling
- Error handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.queue_metrics_service import (
    QueueMetricsService,
    QueueMetricsData,
    QUEUE_REDIS_KEYS,
    DEFAULT_ALERT_THRESHOLD,
    get_queue_metrics_service,
    reset_queue_metrics_service,
)


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    redis = MagicMock()
    redis.llen = AsyncMock(return_value=50)
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def queue_service(mock_redis_client):
    """Create queue metrics service with mock Redis."""
    service = QueueMetricsService(
        redis_client=mock_redis_client,
        alert_threshold=100,
    )
    return service


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton between tests."""
    reset_queue_metrics_service()
    yield
    reset_queue_metrics_service()


# =============================================================================
# Queue Metrics Tests
# =============================================================================


class TestGetQueueMetrics:
    """Test single queue metrics retrieval."""

    @pytest.mark.asyncio
    async def test_returns_queue_metrics(self, queue_service, mock_redis_client) -> None:
        """Should return QueueMetricsData for a queue."""
        mock_redis_client.llen = AsyncMock(return_value=25)

        result = await queue_service.get_queue_metrics("default")

        assert isinstance(result, QueueMetricsData)
        assert result.queue_name == "default"
        assert result.pending_count == 25
        assert result.alert_triggered is False

    @pytest.mark.asyncio
    async def test_uses_correct_redis_key(self, queue_service, mock_redis_client) -> None:
        """Should use correct Redis key for default queue (celery)."""
        await queue_service.get_queue_metrics("default")

        mock_redis_client.llen.assert_called_with("celery")

    @pytest.mark.asyncio
    async def test_uses_queue_name_for_other_queues(self, queue_service, mock_redis_client) -> None:
        """Should use queue name as Redis key for other queues."""
        await queue_service.get_queue_metrics("high")

        mock_redis_client.llen.assert_called_with("high")

    @pytest.mark.asyncio
    async def test_triggers_alert_above_threshold(self, queue_service, mock_redis_client) -> None:
        """Should trigger alert when pending >= threshold."""
        mock_redis_client.llen = AsyncMock(return_value=100)

        result = await queue_service.get_queue_metrics("default")

        assert result.alert_triggered is True

    @pytest.mark.asyncio
    async def test_no_alert_below_threshold(self, queue_service, mock_redis_client) -> None:
        """Should not trigger alert when pending < threshold."""
        mock_redis_client.llen = AsyncMock(return_value=99)

        result = await queue_service.get_queue_metrics("default")

        assert result.alert_triggered is False

    @pytest.mark.asyncio
    async def test_handles_redis_error(self, queue_service, mock_redis_client) -> None:
        """Should return 0 pending on Redis error."""
        mock_redis_client.llen = AsyncMock(side_effect=Exception("Redis error"))

        result = await queue_service.get_queue_metrics("default")

        assert result.pending_count == 0
        assert result.alert_triggered is False

    @pytest.mark.asyncio
    async def test_trend_default_stable(self, queue_service) -> None:
        """Should return stable trend (MVP default)."""
        result = await queue_service.get_queue_metrics("default")

        assert result.trend == "stable"


# =============================================================================
# All Queues Tests
# =============================================================================


class TestGetAllQueueMetrics:
    """Test all queues retrieval."""

    @pytest.mark.asyncio
    async def test_returns_all_configured_queues(self, queue_service, mock_redis_client) -> None:
        """Should return metrics for all configured queues."""
        result = await queue_service.get_all_queue_metrics()

        assert len(result) == len(QUEUE_REDIS_KEYS)
        queue_names = {m.queue_name for m in result}
        assert queue_names == set(QUEUE_REDIS_KEYS.keys())

    @pytest.mark.asyncio
    async def test_continues_on_individual_queue_error(
        self, queue_service, mock_redis_client
    ) -> None:
        """Should continue if one queue fails."""
        call_count = 0

        async def conditional_error(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Redis error")
            return 25

        mock_redis_client.llen = conditional_error

        result = await queue_service.get_all_queue_metrics()

        # Should still return all queues, first one with 0
        assert len(result) == len(QUEUE_REDIS_KEYS)


# =============================================================================
# Worker Count Tests
# =============================================================================


class TestGetActiveWorkerCount:
    """Test worker count retrieval via Celery inspect."""

    @pytest.mark.asyncio
    async def test_returns_worker_count(self, queue_service) -> None:
        """Should return count of active workers."""
        with patch("app.workers.celery.celery_app") as mock_celery:
            mock_inspector = MagicMock()
            mock_inspector.active.return_value = {
                "worker1@host": [],
                "worker2@host": [],
                "worker3@host": [],
            }
            mock_celery.control.inspect.return_value = mock_inspector

            count = await queue_service.get_active_worker_count()

            assert count == 3

    @pytest.mark.asyncio
    async def test_returns_zero_when_none_response(self, queue_service) -> None:
        """Should return 0 when inspect returns None."""
        with patch("app.workers.celery.celery_app") as mock_celery:
            mock_inspector = MagicMock()
            mock_inspector.active.return_value = None
            mock_celery.control.inspect.return_value = mock_inspector

            count = await queue_service.get_active_worker_count()

            assert count == 0

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self, queue_service) -> None:
        """Should return 0 on Celery error."""
        with patch("app.workers.celery.celery_app") as mock_celery:
            mock_celery.control.inspect.side_effect = Exception("Celery error")

            count = await queue_service.get_active_worker_count()

            assert count == 0


# =============================================================================
# Health Check Tests
# =============================================================================


class TestCheckHealth:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_healthy_when_redis_connected(self, queue_service, mock_redis_client) -> None:
        """Should report healthy when Redis connected and workers exist."""
        mock_redis_client.ping = AsyncMock(return_value=True)

        with patch("app.workers.celery.celery_app") as mock_celery:
            mock_inspector = MagicMock()
            mock_inspector.active.return_value = {"worker1": []}
            mock_celery.control.inspect.return_value = mock_inspector

            result = await queue_service.check_health()

            assert result["status"] == "healthy"
            assert result["redisConnected"] is True
            assert result["workerCount"] == 1
            assert result["error"] is None

    @pytest.mark.asyncio
    async def test_degraded_when_no_workers(self, queue_service, mock_redis_client) -> None:
        """Should report degraded when Redis OK but no workers."""
        mock_redis_client.ping = AsyncMock(return_value=True)

        with patch("app.workers.celery.celery_app") as mock_celery:
            mock_inspector = MagicMock()
            mock_inspector.active.return_value = {}
            mock_celery.control.inspect.return_value = mock_inspector

            result = await queue_service.check_health()

            assert result["status"] == "degraded"
            assert result["redisConnected"] is True
            assert result["workerCount"] == 0

    @pytest.mark.asyncio
    async def test_unhealthy_when_redis_down(self, queue_service, mock_redis_client) -> None:
        """Should report unhealthy when Redis fails."""
        mock_redis_client.ping = AsyncMock(side_effect=Exception("Connection refused"))

        result = await queue_service.check_health()

        assert result["status"] == "unhealthy"
        assert result["redisConnected"] is False
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_includes_timestamp(self, queue_service, mock_redis_client) -> None:
        """Should include lastCheckedAt timestamp."""
        result = await queue_service.check_health()

        assert "lastCheckedAt" in result
        assert result["lastCheckedAt"] is not None


# =============================================================================
# Redis Connection Tests
# =============================================================================


class TestRedisConnection:
    """Test Redis connection handling."""

    @pytest.mark.asyncio
    async def test_creates_redis_client_if_none(self) -> None:
        """Should create Redis client if not provided."""
        service = QueueMetricsService(redis_client=None)

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_client.llen = AsyncMock(return_value=10)
            mock_from_url.return_value = mock_client

            await service.get_queue_metrics("default")

            mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_ssl_for_upstash(self) -> None:
        """Should use SSL for rediss:// URLs."""
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_client.llen = AsyncMock(return_value=10)
            mock_from_url.return_value = mock_client

            # Create service with settings that have rediss URL
            with patch("app.services.queue_metrics_service.get_settings") as mock_settings:
                settings = MagicMock()
                settings.celery_broker_url = "rediss://user:pass@host:6379"
                mock_settings.return_value = settings

                service = QueueMetricsService(redis_client=None)

                await service.get_queue_metrics("default")

                # Should be called with ssl parameter
                call_args = mock_from_url.call_args
                assert call_args is not None
                assert "ssl" in call_args.kwargs or any("ssl" in str(arg) for arg in call_args.args)


# =============================================================================
# Queue Key Mapping Tests
# =============================================================================


class TestQueueRedisKeys:
    """Test queue name to Redis key mapping."""

    def test_default_maps_to_celery(self) -> None:
        """Default queue should map to 'celery' Redis key."""
        assert QUEUE_REDIS_KEYS["default"] == "celery"

    def test_high_maps_to_high(self) -> None:
        """High priority queue should map to 'high'."""
        assert QUEUE_REDIS_KEYS["high"] == "high"

    def test_low_maps_to_low(self) -> None:
        """Low priority queue should map to 'low'."""
        assert QUEUE_REDIS_KEYS["low"] == "low"


# =============================================================================
# Alert Threshold Tests
# =============================================================================


class TestAlertThreshold:
    """Test alert threshold configuration."""

    def test_default_threshold_is_100(self) -> None:
        """Default alert threshold should be 100."""
        assert DEFAULT_ALERT_THRESHOLD == 100

    @pytest.mark.asyncio
    async def test_custom_threshold(self, mock_redis_client) -> None:
        """Should use custom threshold when specified."""
        service = QueueMetricsService(
            redis_client=mock_redis_client,
            alert_threshold=50,
        )
        mock_redis_client.llen = AsyncMock(return_value=50)

        result = await service.get_queue_metrics("default")

        assert result.alert_triggered is True

    @pytest.mark.asyncio
    async def test_threshold_boundary(self, mock_redis_client) -> None:
        """Should trigger alert exactly at threshold."""
        service = QueueMetricsService(
            redis_client=mock_redis_client,
            alert_threshold=50,
        )
        mock_redis_client.llen = AsyncMock(return_value=49)

        result = await service.get_queue_metrics("default")

        assert result.alert_triggered is False


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_returns_same_instance(self) -> None:
        """Should return same instance on multiple calls."""
        service1 = get_queue_metrics_service()
        service2 = get_queue_metrics_service()

        assert service1 is service2

    def test_reset_clears_instance(self) -> None:
        """Reset should clear the singleton."""
        service1 = get_queue_metrics_service()
        reset_queue_metrics_service()
        service2 = get_queue_metrics_service()

        assert service1 is not service2

    def test_get_accepts_custom_threshold(self) -> None:
        """Should accept custom threshold on first call."""
        reset_queue_metrics_service()
        service = get_queue_metrics_service(alert_threshold=200)

        assert service._alert_threshold == 200


# =============================================================================
# Data Class Tests
# =============================================================================


class TestQueueMetricsData:
    """Test QueueMetricsData data class."""

    def test_creates_valid_data(self) -> None:
        """Should create valid data instance."""
        data = QueueMetricsData(
            queue_name="default",
            pending_count=50,
            active_count=5,
            failed_count=2,
            completed_24h=100,
            avg_processing_time_ms=5000,
            trend="stable",
            alert_triggered=False,
        )

        assert data.queue_name == "default"
        assert data.pending_count == 50
        assert data.active_count == 5
        assert data.failed_count == 2
        assert data.completed_24h == 100
        assert data.avg_processing_time_ms == 5000
        assert data.trend == "stable"
        assert data.alert_triggered is False
