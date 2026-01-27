"""Queue metrics service for Celery queue monitoring.

Story 5.6: Queue Depth Visibility Dashboard

Provides metrics for Celery queue depths, active workers, and processing trends.
Uses direct Redis LLEN queries on Celery queue keys for real-time visibility.

CRITICAL: Celery stores queues in Redis as lists. The queue names in Redis are:
- "celery" for the default queue (task_default_queue="default" maps to "celery" key)
- "high" for high priority queue
- "low" for low priority queue
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Queue configuration
# Maps logical queue names to Redis key names
QUEUE_REDIS_KEYS = {
    "default": "celery",  # Celery's default queue is named "celery" in Redis
    "high": "high",
    "low": "low",
}

# Default alert threshold (jobs pending before alert triggers)
DEFAULT_ALERT_THRESHOLD = 100


@dataclass
class QueueMetricsData:
    """Internal data class for queue metrics."""

    queue_name: str
    pending_count: int
    active_count: int
    failed_count: int
    completed_24h: int
    avg_processing_time_ms: int
    trend: Literal["increasing", "decreasing", "stable"]
    alert_triggered: bool


class QueueMetricsService:
    """Service for collecting Celery queue metrics from Redis.

    Story 5.6: Queue Depth Visibility Dashboard

    This service queries Redis directly to get queue depths and worker status.
    It uses the same Redis broker that Celery uses for task queuing.

    Pre-mortem fixes implemented:
    - Include `last_checked_at` timestamp in response
    - Add health check endpoint for staleness detection
    - Integration tested with actual Celery task enqueue
    """

    def __init__(
        self,
        redis_client: object | None = None,
        alert_threshold: int = DEFAULT_ALERT_THRESHOLD,
    ):
        """Initialize queue metrics service.

        Args:
            redis_client: Optional Redis client. If None, will create one.
            alert_threshold: Pending job count that triggers alerts.
        """
        self._redis = redis_client
        self._alert_threshold = alert_threshold
        self._settings = get_settings()

    async def _get_redis(self) -> object:
        """Get or create Redis client connected to Celery broker.

        Returns:
            Async Redis client instance.
        """
        if self._redis is not None:
            return self._redis

        # Connect to Celery broker URL (same Redis as task queue)
        import redis.asyncio as redis

        broker_url = self._settings.celery_broker_url

        # Handle SSL for Upstash (rediss:// protocol)
        if broker_url.startswith("rediss://"):
            import ssl

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            self._redis = redis.from_url(
                broker_url,
                decode_responses=True,
                ssl=ssl_context,
            )
        else:
            self._redis = redis.from_url(broker_url, decode_responses=True)

        return self._redis

    async def get_queue_metrics(self, queue_name: str) -> QueueMetricsData:
        """Get metrics for a single queue.

        Args:
            queue_name: Logical queue name (default, high, low).

        Returns:
            QueueMetricsData with current metrics.
        """
        redis_key = QUEUE_REDIS_KEYS.get(queue_name, queue_name)

        try:
            redis_client = await self._get_redis()
            pending_count = await redis_client.llen(redis_key)
        except Exception as e:
            logger.warning(
                "queue_metrics_redis_error",
                queue_name=queue_name,
                redis_key=redis_key,
                error=str(e),
            )
            pending_count = 0

        # Determine trend (simplified - always stable for MVP)
        # Future: Compare against historical data stored in separate Redis key
        trend: Literal["increasing", "decreasing", "stable"] = "stable"

        alert_triggered = pending_count >= self._alert_threshold

        return QueueMetricsData(
            queue_name=queue_name,
            pending_count=pending_count,
            active_count=0,  # Would require Celery inspect() - expensive
            failed_count=0,  # Would require result backend query
            completed_24h=0,  # Would require result backend query
            avg_processing_time_ms=0,  # Would require timing data
            trend=trend,
            alert_triggered=alert_triggered,
        )

    async def get_all_queue_metrics(self) -> list[QueueMetricsData]:
        """Get metrics for all configured queues.

        Returns:
            List of QueueMetricsData for each queue.
        """
        metrics = []
        for queue_name in QUEUE_REDIS_KEYS.keys():
            try:
                queue_metrics = await self.get_queue_metrics(queue_name)
                metrics.append(queue_metrics)
            except Exception as e:
                logger.error(
                    "queue_metrics_collection_failed",
                    queue_name=queue_name,
                    error=str(e),
                )
                # Add placeholder metrics on error
                metrics.append(
                    QueueMetricsData(
                        queue_name=queue_name,
                        pending_count=0,
                        active_count=0,
                        failed_count=0,
                        completed_24h=0,
                        avg_processing_time_ms=0,
                        trend="stable",
                        alert_triggered=False,
                    )
                )

        return metrics

    async def get_active_worker_count(self) -> int:
        """Get count of active Celery workers.

        Uses Celery inspect() to query workers. This is relatively expensive
        so should be called sparingly.

        Returns:
            Number of active workers, or 0 if unable to determine.
        """
        try:
            from app.workers.celery import celery_app

            # inspect().active() returns dict of {worker_name: [tasks]}
            # This is a synchronous call but fast
            inspector = celery_app.control.inspect()
            active = inspector.active()

            if active is None:
                logger.warning("celery_inspect_returned_none")
                return 0

            return len(active)
        except Exception as e:
            logger.warning(
                "celery_worker_count_failed",
                error=str(e),
            )
            return 0

    async def check_health(self) -> dict:
        """Check queue system health.

        Pre-mortem fix: Add health check endpoint for staleness detection.

        Returns:
            Health status dict with redis connection and worker status.
        """
        redis_connected = False
        worker_count = 0
        error_message = None

        try:
            redis_client = await self._get_redis()
            # Ping Redis to verify connection
            await redis_client.ping()
            redis_connected = True
        except Exception as e:
            error_message = str(e)
            logger.error("queue_health_redis_failed", error=error_message)

        try:
            worker_count = await self.get_active_worker_count()
        except Exception as e:
            logger.warning("queue_health_worker_check_failed", error=str(e))

        status = "healthy" if redis_connected else "unhealthy"
        if redis_connected and worker_count == 0:
            status = "degraded"  # Redis OK but no workers

        return {
            "status": status,
            "redisConnected": redis_connected,
            "workerCount": worker_count,
            "lastCheckedAt": datetime.now(timezone.utc).isoformat(),
            "error": error_message,
        }


# Singleton instance for dependency injection
_queue_metrics_service: QueueMetricsService | None = None


def get_queue_metrics_service(
    alert_threshold: int = DEFAULT_ALERT_THRESHOLD,
) -> QueueMetricsService:
    """Get or create queue metrics service singleton.

    Args:
        alert_threshold: Pending job threshold for alerts.

    Returns:
        QueueMetricsService instance.
    """
    global _queue_metrics_service

    if _queue_metrics_service is None:
        _queue_metrics_service = QueueMetricsService(
            alert_threshold=alert_threshold,
        )

    return _queue_metrics_service


def reset_queue_metrics_service() -> None:
    """Reset service singleton for testing."""
    global _queue_metrics_service
    _queue_metrics_service = None
