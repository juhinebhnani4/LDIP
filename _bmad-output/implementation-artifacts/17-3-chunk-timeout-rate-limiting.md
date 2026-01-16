# Story 17.3: Implement Per-Chunk Timeout and Rate Limiting

Status: ready-for-dev

## Story

As a system processing chunks in parallel,
I want per-chunk timeouts and rate limiting,
so that hung requests don't block processing and we stay within API quotas.

## Acceptance Criteria

1. **Per-Chunk Timeout**
   - Document AI call exceeding 60 seconds is cancelled with timeout error
   - Chunk status updated to 'failed' with "timeout" error_message
   - Other chunks continue processing

2. **Concurrency Limiting**
   - Semaphore limits concurrent Document AI calls to 5
   - Additional chunks wait for a slot to become available
   - Prevents overwhelming the API

3. **Rate Limit Handling**
   - Document AI 429 response triggers exponential backoff (2s, 4s, 8s, max 30s)
   - Chunk retried after backoff
   - Backoff state visible in job tracking

4. **Global Semaphore (PRE-MORTEM)**
   - Redis-based semaphore limits total concurrent API calls across all workers
   - Prevents 10 workers × 5 requests = 50 concurrent scenario
   - Key pattern: `docai_semaphore:{environment}`
   - Fallback to per-worker semaphore if Redis unavailable

5. **Rate Limit Transparency (SHARK TANK)**
   - Current backoff state visible in job tracking
   - Estimated delay shown to user
   - Metrics track rate limit events for capacity planning

## Tasks / Subtasks

- [ ] Task 1: Implement chunk timeout wrapper (AC: #1)
  - [ ] Create timeout decorator/context manager
  - [ ] Configure 60-second timeout for Document AI calls
  - [ ] Update chunk status on timeout
  - [ ] Ensure clean cancellation

- [ ] Task 2: Implement Redis-based global semaphore (AC: #2, #4)
  - [ ] Create `RedisSemaphore` class
  - [ ] Limit to 5 concurrent API calls globally
  - [ ] Implement acquire/release with TTL
  - [ ] Add fallback for Redis unavailability

- [ ] Task 3: Implement exponential backoff for 429s (AC: #3)
  - [ ] Detect rate limit responses (429)
  - [ ] Apply backoff: 2s, 4s, 8s, 16s, max 30s
  - [ ] Update job tracking with backoff state
  - [ ] Retry chunk after backoff

- [ ] Task 4: Add transparency and metrics (AC: #5)
  - [ ] Log rate limit events with context
  - [ ] Update job metadata with backoff info
  - [ ] Emit metrics for monitoring

- [ ] Task 5: Write tests (AC: #1-5)
  - [ ] Test timeout cancellation
  - [ ] Test semaphore limits concurrency
  - [ ] Test backoff calculation
  - [ ] Test global vs per-worker semaphore

## Dev Notes

### Architecture Compliance

**Rate Limiting Pattern:**
```python
# backend/app/services/rate_limiter.py
import asyncio
import time
from contextlib import asynccontextmanager

import structlog
from redis import Redis

from app.services.redis_client import get_redis_client

logger = structlog.get_logger(__name__)

CHUNK_TIMEOUT_SECONDS = 60
MAX_CONCURRENT_CALLS = 5
BACKOFF_BASE = 2
BACKOFF_MAX = 30


class RedisSemaphore:
    """Distributed semaphore using Redis for cross-worker coordination.

    Limits concurrent Document AI API calls across all workers.
    """

    def __init__(
        self,
        redis_client: Redis,
        name: str,
        max_concurrent: int = MAX_CONCURRENT_CALLS,
        ttl: int = 120,
    ):
        self.redis = redis_client
        self.name = f"semaphore:{name}"
        self.max_concurrent = max_concurrent
        self.ttl = ttl
        self._acquired_id = None

    def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire a semaphore slot.

        Args:
            timeout: Max time to wait for a slot.

        Returns:
            True if acquired, False if timed out.
        """
        import uuid
        slot_id = str(uuid.uuid4())
        deadline = time.time() + timeout

        while time.time() < deadline:
            # Try to add our slot
            current = self.redis.scard(self.name)
            if current < self.max_concurrent:
                self.redis.sadd(self.name, slot_id)
                self.redis.expire(self.name, self.ttl)
                self._acquired_id = slot_id
                logger.debug(
                    "semaphore_acquired",
                    name=self.name,
                    slot_id=slot_id,
                    current=current + 1,
                )
                return True

            # Wait and retry
            time.sleep(0.5)

        logger.warning(
            "semaphore_acquire_timeout",
            name=self.name,
            timeout=timeout,
        )
        return False

    def release(self) -> None:
        """Release the semaphore slot."""
        if self._acquired_id:
            self.redis.srem(self.name, self._acquired_id)
            logger.debug(
                "semaphore_released",
                name=self.name,
                slot_id=self._acquired_id,
            )
            self._acquired_id = None


@asynccontextmanager
async def rate_limited_api_call(
    name: str = "docai",
    timeout: float = CHUNK_TIMEOUT_SECONDS,
):
    """Context manager for rate-limited API calls with timeout.

    Acquires semaphore, applies timeout, handles rate limits.

    Usage:
        async with rate_limited_api_call() as limiter:
            result = await api_call()
            limiter.record_success()
    """
    redis = get_redis_client()
    semaphore = RedisSemaphore(redis, name)

    if not semaphore.acquire():
        raise RateLimitError("Could not acquire API slot")

    try:
        yield RateLimitContext(semaphore)
    finally:
        semaphore.release()


class RateLimitContext:
    """Context for tracking rate limit state."""

    def __init__(self, semaphore: RedisSemaphore):
        self.semaphore = semaphore
        self.backoff_seconds = 0

    def record_success(self) -> None:
        """Record successful API call."""
        self.backoff_seconds = 0

    def calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff.

        Args:
            attempt: Current attempt number (1-based).

        Returns:
            Backoff time in seconds.
        """
        backoff = min(BACKOFF_BASE ** attempt, BACKOFF_MAX)
        self.backoff_seconds = backoff
        return backoff


def process_chunk_with_timeout(
    chunk_bytes: bytes,
    ocr_processor,
    timeout: float = CHUNK_TIMEOUT_SECONDS,
) -> dict:
    """Process chunk with timeout protection.

    Args:
        chunk_bytes: PDF chunk content.
        ocr_processor: OCR processor instance.
        timeout: Max processing time in seconds.

    Returns:
        OCR result dict.

    Raises:
        TimeoutError: If processing exceeds timeout.
    """
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Chunk processing timed out after {timeout}s")

    # Set up timeout (Unix only)
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(timeout))

    try:
        return ocr_processor.process_sync(chunk_bytes)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


async def process_with_retry(
    chunk_bytes: bytes,
    ocr_processor,
    max_attempts: int = 4,
) -> dict:
    """Process chunk with exponential backoff on rate limits.

    Args:
        chunk_bytes: PDF chunk content.
        ocr_processor: OCR processor instance.
        max_attempts: Maximum retry attempts.

    Returns:
        OCR result dict.

    Raises:
        RateLimitError: If max attempts exceeded.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return process_chunk_with_timeout(chunk_bytes, ocr_processor)

        except RateLimitError as e:
            if attempt >= max_attempts:
                raise

            backoff = min(BACKOFF_BASE ** attempt, BACKOFF_MAX)
            logger.warning(
                "rate_limited_retrying",
                attempt=attempt,
                backoff_seconds=backoff,
                error=str(e),
            )
            await asyncio.sleep(backoff)

    raise RateLimitError("Max retry attempts exceeded")
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    services/
      rate_limiter.py        # NEW - Rate limiting and semaphore
    workers/
      tasks/
        document_tasks.py    # Modify - Integrate rate limiting
  tests/
    services/
      test_rate_limiter.py   # NEW - Tests
```

### Testing Requirements

```python
# tests/services/test_rate_limiter.py
import pytest
import time
from unittest.mock import MagicMock

from app.services.rate_limiter import (
    RedisSemaphore,
    process_chunk_with_timeout,
    CHUNK_TIMEOUT_SECONDS,
    MAX_CONCURRENT_CALLS,
)


class TestRedisSemaphore:
    def test_limits_concurrent_calls(self):
        redis = MagicMock()
        redis.scard.return_value = MAX_CONCURRENT_CALLS  # At limit

        semaphore = RedisSemaphore(redis, "test", max_concurrent=5)
        result = semaphore.acquire(timeout=1.0)

        assert result is False  # Should not acquire

    def test_acquires_when_slots_available(self):
        redis = MagicMock()
        redis.scard.return_value = 2  # 2 of 5 used

        semaphore = RedisSemaphore(redis, "test", max_concurrent=5)
        result = semaphore.acquire()

        assert result is True
        redis.sadd.assert_called_once()


class TestChunkTimeout:
    def test_timeout_raises_error(self):
        def slow_processor(_):
            time.sleep(5)
            return {}

        mock_processor = MagicMock()
        mock_processor.process_sync = slow_processor

        with pytest.raises(TimeoutError):
            process_chunk_with_timeout(
                b"chunk",
                mock_processor,
                timeout=1,
            )
```

### References

- [Source: epic-3-data-integrity-reliability-hardening.md#Story 3.3] - Full AC
- [Source: Story 17.2] - Circuit breaker (related)
- [Source: 13-3-rate-limiting-slowapi.md] - Existing rate limiting

### Critical Implementation Notes

**DO NOT:**
- Use local semaphore (not shared across workers)
- Skip timeout on API calls
- Ignore 429 responses
- Block forever waiting for semaphore

**MUST:**
- Use Redis for global semaphore
- Apply 60-second timeout to all Document AI calls
- Implement exponential backoff for 429s
- Log and track rate limit events
- Provide graceful fallback if Redis unavailable

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

