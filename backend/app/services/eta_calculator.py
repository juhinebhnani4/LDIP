"""ETA calculator service for document processing time estimation.

Story 5.7: Processing ETA Display

Provides estimated completion times for document processing based on:
- Rolling average of historical processing times
- Weighted by page count for more accurate estimates
- Active worker count for parallelism adjustment
- Confidence ranges (min/max) instead of point estimates
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Configuration
FALLBACK_SECONDS_PER_PAGE = 3  # Fallback when no historical data
ROLLING_WINDOW_SIZE = 100  # Keep last N completions
MINIMUM_SAMPLES_FOR_CONFIDENCE = 10  # Need at least 10 samples for "high" confidence
REDIS_PROCESSING_TIMES_KEY = "metrics:processing_time:history"
REDIS_AVG_TIME_KEY = "metrics:processing_time:avg"
REDIS_AVG_TIME_TTL = 60  # Cache average for 60 seconds


@dataclass
class ETAResult:
    """Estimated completion time with confidence range.

    Story 5.7: Pre-mortem fix - Return range, not point estimate.

    Attributes:
        min_seconds: Optimistic estimate (fastest case).
        max_seconds: Pessimistic estimate (slowest case).
        best_guess_seconds: Most likely estimate.
        confidence: Confidence level based on sample size.
        factors: Dict explaining the calculation factors.
    """

    min_seconds: int
    max_seconds: int
    best_guess_seconds: int
    confidence: Literal["high", "medium", "low"]
    factors: dict


@dataclass
class ProcessingMetric:
    """A single document processing completion metric.

    Attributes:
        document_id: UUID of the processed document.
        page_count: Number of pages in the document.
        processing_time_ms: Total processing time in milliseconds.
        timestamp: When the processing completed (ISO format).
    """

    document_id: str
    page_count: int
    processing_time_ms: int
    timestamp: str


class ETACalculator:
    """Calculator for document processing ETAs.

    Story 5.7: Processing ETA Display

    Uses a weighted rolling average of historical processing times,
    accounting for document size (page count) and available workers.

    Pre-mortem fixes:
    - Weight by page count, not just document count
    - Query real workers via Celery inspect
    - Return confidence ranges (min/max/best)
    """

    def __init__(
        self,
        redis_client: object | None = None,
        queue_metrics_service: object | None = None,
    ):
        """Initialize ETA calculator.

        Args:
            redis_client: Optional Redis client. If None, will create one.
            queue_metrics_service: Optional QueueMetricsService for worker count.
        """
        self._redis = redis_client
        self._queue_metrics_service = queue_metrics_service
        self._settings = get_settings()

    async def _get_redis(self) -> object:
        """Get or create Redis client.

        Returns:
            Async Redis client instance.
        """
        if self._redis is not None:
            return self._redis

        from app.services.memory.redis_client import get_redis_client

        self._redis = await get_redis_client()
        return self._redis

    async def get_active_worker_count(self) -> int:
        """Get count of active Celery workers.

        Story 5.7: Pre-mortem fix - Query real workers, not config value.

        Uses QueueMetricsService if available, otherwise uses Celery inspect.

        Returns:
            Number of active workers, or fallback value if unable to determine.
        """
        # Try queue metrics service first
        if self._queue_metrics_service is not None:
            try:
                return await self._queue_metrics_service.get_active_worker_count()
            except Exception:
                pass

        # Fallback to Celery inspect
        try:
            from app.workers.celery import celery_app

            inspector = celery_app.control.inspect()
            active = inspector.active()
            if active:
                return len(active)
        except Exception as e:
            logger.warning("eta_worker_count_failed", error=str(e))

        # Final fallback: assume 2 workers (conservative estimate)
        return 2

    async def get_weighted_avg_time(self) -> tuple[float, int]:
        """Get rolling average processing time weighted by page count.

        Returns:
            Tuple of (avg_seconds_per_page, sample_count).
        """
        try:
            redis_client = await self._get_redis()

            # Check cache first
            cached_avg = await redis_client.get(REDIS_AVG_TIME_KEY)
            if cached_avg:
                try:
                    parts = cached_avg.split(":")
                    return float(parts[0]), int(parts[1])
                except (ValueError, IndexError):
                    pass

            # Calculate from history
            history_raw = await redis_client.lrange(
                REDIS_PROCESSING_TIMES_KEY, 0, ROLLING_WINDOW_SIZE - 1
            )

            if not history_raw:
                return FALLBACK_SECONDS_PER_PAGE, 0

            # Parse history entries: "page_count:time_ms"
            total_pages = 0
            total_time_ms = 0
            sample_count = 0

            for entry in history_raw:
                try:
                    parts = entry.split(":")
                    page_count = int(parts[0])
                    time_ms = int(parts[1])
                    total_pages += page_count
                    total_time_ms += time_ms
                    sample_count += 1
                except (ValueError, IndexError):
                    continue

            if total_pages == 0:
                return FALLBACK_SECONDS_PER_PAGE, sample_count

            # Calculate weighted average (seconds per page)
            avg_seconds_per_page = (total_time_ms / 1000) / total_pages

            # Cache the result
            await redis_client.set(
                REDIS_AVG_TIME_KEY,
                f"{avg_seconds_per_page}:{sample_count}",
                ex=REDIS_AVG_TIME_TTL,
            )

            return avg_seconds_per_page, sample_count

        except Exception as e:
            logger.warning("eta_avg_time_failed", error=str(e))
            return FALLBACK_SECONDS_PER_PAGE, 0

    async def get_processing_eta(
        self,
        matter_id: str,
        pending_docs: list[dict],
    ) -> ETAResult:
        """Calculate ETA with confidence range for pending documents.

        Story 5.7: Pre-mortem fix - Return range, not point estimate.

        Args:
            matter_id: UUID of the matter.
            pending_docs: List of pending documents with page_count.
                Each dict should have: {"page_count": int, ...}

        Returns:
            ETAResult with min/max/best estimates and confidence.
        """
        # Calculate total pages to process
        total_pages = sum(
            doc.get("page_count", 1) for doc in pending_docs
        )

        if total_pages == 0:
            return ETAResult(
                min_seconds=0,
                max_seconds=0,
                best_guess_seconds=0,
                confidence="high",
                factors={"reason": "no_pending_docs"},
            )

        # Get weighted average and sample count
        avg_seconds_per_page, sample_count = await self.get_weighted_avg_time()

        # Get active worker count for parallelism
        worker_count = await self.get_active_worker_count()
        worker_count = max(1, worker_count)  # Prevent division by zero

        # Determine confidence based on sample count
        if sample_count >= MINIMUM_SAMPLES_FOR_CONFIDENCE:
            confidence: Literal["high", "medium", "low"] = "high"
            variance_factor = 1.3  # ±30% for high confidence
        elif sample_count >= 5:
            confidence = "medium"
            variance_factor = 1.5  # ±50% for medium confidence
        else:
            confidence = "low"
            variance_factor = 2.0  # ±100% for low confidence

        # Calculate base estimate
        # Total time = (total_pages * avg_time_per_page) / workers
        base_seconds = (total_pages * avg_seconds_per_page) / worker_count

        # Calculate range
        best_guess_seconds = int(base_seconds)
        min_seconds = int(base_seconds / variance_factor)
        max_seconds = int(base_seconds * variance_factor)

        # Enforce minimum values
        min_seconds = max(min_seconds, 30)  # At least 30 seconds
        best_guess_seconds = max(best_guess_seconds, min_seconds)
        max_seconds = max(max_seconds, best_guess_seconds)

        logger.debug(
            "eta_calculated",
            matter_id=matter_id,
            total_pages=total_pages,
            pending_docs=len(pending_docs),
            avg_seconds_per_page=round(avg_seconds_per_page, 2),
            worker_count=worker_count,
            sample_count=sample_count,
            confidence=confidence,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
        )

        return ETAResult(
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            best_guess_seconds=best_guess_seconds,
            confidence=confidence,
            factors={
                "total_pages": total_pages,
                "pending_docs": len(pending_docs),
                "avg_seconds_per_page": round(avg_seconds_per_page, 2),
                "worker_count": worker_count,
                "sample_count": sample_count,
            },
        )

    async def record_completion(
        self,
        document_id: str,
        page_count: int,
        processing_time_ms: int,
    ) -> None:
        """Record a document completion for ETA calculation.

        Story 5.7: Pre-mortem fix - Weight by page count.

        Args:
            document_id: UUID of the completed document.
            page_count: Number of pages in the document.
            processing_time_ms: Total processing time in milliseconds.
        """
        if page_count <= 0 or processing_time_ms <= 0:
            logger.warning(
                "eta_invalid_completion_data",
                document_id=document_id,
                page_count=page_count,
                processing_time_ms=processing_time_ms,
            )
            return

        try:
            redis_client = await self._get_redis()

            # Store as "page_count:time_ms" for weighted average calculation
            entry = f"{page_count}:{processing_time_ms}"

            # Add to rolling window (LPUSH + LTRIM for bounded list)
            await redis_client.lpush(REDIS_PROCESSING_TIMES_KEY, entry)
            await redis_client.ltrim(
                REDIS_PROCESSING_TIMES_KEY, 0, ROLLING_WINDOW_SIZE - 1
            )

            # Invalidate cached average
            await redis_client.delete(REDIS_AVG_TIME_KEY)

            logger.debug(
                "eta_completion_recorded",
                document_id=document_id,
                page_count=page_count,
                processing_time_ms=processing_time_ms,
                seconds_per_page=round(processing_time_ms / 1000 / page_count, 2),
            )

        except Exception as e:
            logger.warning(
                "eta_completion_record_failed",
                document_id=document_id,
                error=str(e),
            )


# Singleton instance
_eta_calculator: ETACalculator | None = None


def get_eta_calculator() -> ETACalculator:
    """Get or create ETA calculator singleton.

    Returns:
        ETACalculator instance.
    """
    global _eta_calculator

    if _eta_calculator is None:
        # Optionally inject queue metrics service for worker count
        try:
            from app.services.queue_metrics_service import get_queue_metrics_service

            queue_service = get_queue_metrics_service()
        except ImportError:
            queue_service = None

        _eta_calculator = ETACalculator(queue_metrics_service=queue_service)

    return _eta_calculator


def reset_eta_calculator() -> None:
    """Reset singleton for testing."""
    global _eta_calculator
    _eta_calculator = None
