# Story 17.2: Implement Circuit Breaker for Document AI

Status: ready-for-dev

## Story

As a system making Document AI API calls,
I want a circuit breaker to stop processing when the API is failing repeatedly,
so that we don't waste resources on doomed requests or hit rate limits harder.

## Acceptance Criteria

1. **Circuit Breaker Trigger**
   - 3 consecutive chunk failures with API errors (429, 500, timeout) trips the breaker
   - All remaining chunk tasks are cancelled
   - Document marked as 'ocr_failed' with circuit breaker reason
   - Job tracking shows "Processing stopped: API circuit breaker triggered"

2. **Open State Behavior**
   - When circuit breaker is open, new large document uploads are queued (not immediately failed)
   - User sees "High API load - document queued for processing"
   - Documents in queue processed when breaker closes

3. **Half-Open Recovery**
   - After 5 minutes open, breaker enters half-open state
   - One test request allowed through
   - Success closes the breaker, failure keeps it open

## Tasks / Subtasks

- [ ] Task 1: Create DocumentAICircuitBreaker service (AC: #1, #2, #3)
  - [ ] Create `backend/app/services/circuit_breaker.py`
  - [ ] Implement state machine: CLOSED → OPEN → HALF_OPEN → CLOSED
  - [ ] Store state in Redis for cross-worker consistency
  - [ ] Define `FAILURE_THRESHOLD = 3`, `RECOVERY_TIME = 300` (5 min)

- [ ] Task 2: Integrate with chunk processing (AC: #1)
  - [ ] Check circuit breaker before each chunk API call
  - [ ] Record failures to circuit breaker on API errors
  - [ ] Cancel remaining chunks when breaker trips
  - [ ] Update document and job status appropriately

- [ ] Task 3: Implement queuing for open state (AC: #2)
  - [ ] Queue new documents instead of immediate processing
  - [ ] Return appropriate status to user
  - [ ] Process queue when breaker closes

- [ ] Task 4: Implement half-open recovery (AC: #3)
  - [ ] Track time since breaker opened
  - [ ] Allow single test request after recovery time
  - [ ] Transition based on test result

- [ ] Task 5: Write tests (AC: #1-3)
  - [ ] Test breaker trips after 3 failures
  - [ ] Test state transitions
  - [ ] Test recovery after 5 minutes

## Dev Notes

### Architecture Compliance

**Circuit Breaker Pattern:**
```python
# backend/app/services/circuit_breaker.py
import time
from enum import Enum
from functools import lru_cache

import structlog
from redis import Redis

from app.services.redis_client import get_redis_client

logger = structlog.get_logger(__name__)

FAILURE_THRESHOLD = 3
RECOVERY_TIME_SECONDS = 300  # 5 minutes


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


class DocumentAICircuitBreaker:
    """Circuit breaker for Document AI API calls.

    Prevents cascading failures and protects against rate limiting
    by stopping requests when the API is failing repeatedly.

    State machine:
    - CLOSED: Normal operation, all requests allowed
    - OPEN: Blocking requests, entered after FAILURE_THRESHOLD failures
    - HALF_OPEN: After RECOVERY_TIME, allows one test request

    Uses Redis for cross-worker state consistency.
    """

    REDIS_KEY = "circuit_breaker:document_ai"
    REDIS_FAILURE_KEY = "circuit_breaker:document_ai:failures"
    REDIS_OPEN_TIME_KEY = "circuit_breaker:document_ai:open_time"

    def __init__(self, redis_client: Redis | None = None):
        self._redis = redis_client

    @property
    def redis(self) -> Redis:
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        state = self.redis.get(self.REDIS_KEY)
        if state is None:
            return CircuitState.CLOSED
        return CircuitState(state.decode())

    def is_request_allowed(self) -> bool:
        """Check if a request is allowed through the circuit breaker.

        Returns:
            True if request should proceed, False if blocked.
        """
        state = self.get_state()

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            # Check if recovery time has passed
            open_time = self.redis.get(self.REDIS_OPEN_TIME_KEY)
            if open_time:
                elapsed = time.time() - float(open_time.decode())
                if elapsed >= RECOVERY_TIME_SECONDS:
                    # Transition to half-open
                    self._set_state(CircuitState.HALF_OPEN)
                    logger.info("circuit_breaker_half_open")
                    return True  # Allow test request
            return False

        if state == CircuitState.HALF_OPEN:
            # Only one request allowed - check if already testing
            testing = self.redis.get(f"{self.REDIS_KEY}:testing")
            if testing:
                return False
            self.redis.setex(f"{self.REDIS_KEY}:testing", 60, "1")
            return True

        return False

    def record_success(self) -> None:
        """Record a successful API call."""
        state = self.get_state()

        if state == CircuitState.HALF_OPEN:
            # Test passed - close the circuit
            self._set_state(CircuitState.CLOSED)
            self.redis.delete(self.REDIS_FAILURE_KEY)
            self.redis.delete(f"{self.REDIS_KEY}:testing")
            logger.info("circuit_breaker_closed", reason="test_success")

        elif state == CircuitState.CLOSED:
            # Reset failure count on success
            self.redis.delete(self.REDIS_FAILURE_KEY)

    def record_failure(self, error: str) -> bool:
        """Record a failed API call.

        Args:
            error: Error message or code.

        Returns:
            True if circuit breaker tripped, False otherwise.
        """
        state = self.get_state()

        if state == CircuitState.HALF_OPEN:
            # Test failed - back to open
            self._set_state(CircuitState.OPEN)
            self.redis.set(self.REDIS_OPEN_TIME_KEY, str(time.time()))
            self.redis.delete(f"{self.REDIS_KEY}:testing")
            logger.warning("circuit_breaker_reopened", error=error)
            return True

        if state == CircuitState.CLOSED:
            # Increment failure count
            failures = self.redis.incr(self.REDIS_FAILURE_KEY)
            self.redis.expire(self.REDIS_FAILURE_KEY, 60)  # Reset after 1 min

            if failures >= FAILURE_THRESHOLD:
                # Trip the breaker
                self._set_state(CircuitState.OPEN)
                self.redis.set(self.REDIS_OPEN_TIME_KEY, str(time.time()))
                logger.warning(
                    "circuit_breaker_opened",
                    failures=failures,
                    threshold=FAILURE_THRESHOLD,
                    error=error,
                )
                return True

        return False

    def _set_state(self, state: CircuitState) -> None:
        """Set circuit breaker state."""
        self.redis.set(self.REDIS_KEY, state.value)


@lru_cache(maxsize=1)
def get_docai_circuit_breaker() -> DocumentAICircuitBreaker:
    """Get singleton circuit breaker instance."""
    return DocumentAICircuitBreaker()
```

**Integration in Chunk Processing:**
```python
# In document_tasks.py process_single_chunk

circuit_breaker = get_docai_circuit_breaker()

# Check before API call
if not circuit_breaker.is_request_allowed():
    raise CircuitBreakerOpenError(
        "Document AI circuit breaker is open"
    )

try:
    result = ocr_processor.process_sync(chunk_bytes)
    circuit_breaker.record_success()
except (TimeoutError, RateLimitError, APIError) as e:
    tripped = circuit_breaker.record_failure(str(e))
    if tripped:
        # Cancel remaining chunks for this document
        _cancel_remaining_chunks(document_id)
    raise
```

### Project Structure Notes

**File Locations:**
```
backend/
  app/
    services/
      circuit_breaker.py     # NEW - Circuit breaker service
    workers/
      tasks/
        document_tasks.py    # Modify - Integrate circuit breaker
  tests/
    services/
      test_circuit_breaker.py  # NEW - Tests
```

### Testing Requirements

```python
# tests/services/test_circuit_breaker.py
import pytest
import time
from unittest.mock import MagicMock, patch

from app.services.circuit_breaker import (
    DocumentAICircuitBreaker,
    CircuitState,
    FAILURE_THRESHOLD,
    RECOVERY_TIME_SECONDS,
)


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get.return_value = None
    redis.incr.return_value = 1
    return redis


class TestCircuitBreakerStates:
    def test_starts_closed(self, mock_redis):
        breaker = DocumentAICircuitBreaker(redis_client=mock_redis)
        assert breaker.get_state() == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self, mock_redis):
        mock_redis.incr.return_value = FAILURE_THRESHOLD
        breaker = DocumentAICircuitBreaker(redis_client=mock_redis)

        tripped = breaker.record_failure("API error")

        assert tripped is True
        mock_redis.set.assert_called()

    def test_allows_requests_when_closed(self, mock_redis):
        breaker = DocumentAICircuitBreaker(redis_client=mock_redis)
        assert breaker.is_request_allowed() is True

    def test_blocks_requests_when_open(self, mock_redis):
        mock_redis.get.side_effect = lambda k: {
            breaker.REDIS_KEY: b"open",
            breaker.REDIS_OPEN_TIME_KEY: str(time.time()).encode(),
        }.get(k)
        breaker = DocumentAICircuitBreaker(redis_client=mock_redis)

        assert breaker.is_request_allowed() is False


class TestHalfOpenRecovery:
    def test_transitions_to_half_open_after_recovery_time(self, mock_redis):
        # Open state with old timestamp
        old_time = time.time() - RECOVERY_TIME_SECONDS - 1
        mock_redis.get.side_effect = lambda k: {
            DocumentAICircuitBreaker.REDIS_KEY: b"open",
            DocumentAICircuitBreaker.REDIS_OPEN_TIME_KEY: str(old_time).encode(),
        }.get(k)

        breaker = DocumentAICircuitBreaker(redis_client=mock_redis)

        # Should transition to half-open and allow request
        assert breaker.is_request_allowed() is True

    def test_closes_on_success_in_half_open(self, mock_redis):
        mock_redis.get.return_value = b"half_open"
        breaker = DocumentAICircuitBreaker(redis_client=mock_redis)

        breaker.record_success()

        # Should set state to closed
        mock_redis.set.assert_called_with(
            DocumentAICircuitBreaker.REDIS_KEY,
            CircuitState.CLOSED.value,
        )
```

### References

- [Source: epic-3-data-integrity-reliability-hardening.md#Story 3.2] - Full AC
- [Source: project-context.md#Backend] - Error handling patterns
- [Source: 13-2-circuit-breakers-tenacity.md] - Existing tenacity circuit breakers

### Critical Implementation Notes

**DO NOT:**
- Use in-memory state (not shared across workers)
- Block indefinitely when circuit is open
- Skip recording successes (needed to close circuit)
- Forget to cancel remaining chunks when breaker trips

**MUST:**
- Use Redis for cross-worker state consistency
- Allow queuing of new documents when open
- Implement half-open test request pattern
- Log all state transitions for debugging
- Cancel remaining document chunks when breaker trips

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

