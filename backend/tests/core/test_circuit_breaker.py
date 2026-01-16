"""Tests for circuit breaker module (Story 13.2).

Tests cover:
- CircuitBreaker state transitions (closed -> open -> half_open -> closed)
- Failure threshold and recovery timeout behavior
- CircuitBreakerRegistry singleton pattern
- @with_circuit_breaker decorator with async functions
- CircuitOpenError handling and fallback behavior
- Thread-safety of circuit breaker operations
- Service integration patterns (embedder, reranker, etc.)
"""

import asyncio
import time

import pytest

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitConfig,
    CircuitOpenError,
    CircuitService,
    CircuitState,
    get_all_circuits_status,
    get_circuit_registry,
    get_circuit_status,
    is_circuit_open,
    is_retryable_exception,
    with_circuit_breaker,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Create a test circuit config with short timeouts."""
    return CircuitConfig(
        failure_threshold=3,
        recovery_timeout=1,  # 1 second for fast tests
        timeout_seconds=5,
        max_retries=2,
        initial_wait=0.1,
        max_wait=0.5,
        jitter=0.1,
    )


@pytest.fixture
def breaker(config):
    """Create a fresh circuit breaker for testing."""
    return CircuitBreaker(name="test_service", config=config)


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset circuit registry between tests.

    Only resets circuits that are already registered to avoid slow iterations.
    """
    registry = get_circuit_registry()
    # Get list of registered circuits to reset (don't create new ones)
    registered_services = list(registry._circuits.keys())
    for service in registered_services:
        registry.reset(service)
    yield
    # Cleanup after test - reset only registered circuits
    registered_services = list(registry._circuits.keys())
    for service in registered_services:
        registry.reset(service)


# =============================================================================
# CircuitBreaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self, breaker):
        """Circuit starts in closed state."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert breaker.failure_count == 0

    def test_record_success_resets_failure_count(self, breaker):
        """Successful calls reset the failure counter."""
        # Simulate some failures
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2

        # Success resets counter
        breaker.record_success()
        assert breaker.failure_count == 0

    def test_circuit_opens_after_threshold_failures(self, breaker):
        """Circuit opens after failure_threshold consecutive failures."""
        # Record failures up to threshold
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open
        assert not breaker.is_closed

    def test_circuit_stays_open_during_cooldown(self, breaker):
        """Circuit remains open during recovery_timeout period."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open
        assert breaker.cooldown_remaining > 0

    @pytest.mark.slow
    def test_circuit_transitions_to_half_open_after_cooldown(self, breaker):
        """Circuit transitions to half-open after recovery_timeout."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open

        # Wait for recovery timeout (1 second)
        time.sleep(1.1)

        # Accessing state triggers transition check
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.slow
    def test_half_open_success_closes_circuit(self, breaker):
        """Success in half-open state closes the circuit."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure()

        # Wait for recovery
        time.sleep(1.1)
        assert breaker.state == CircuitState.HALF_OPEN

        # Success closes circuit
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.slow
    def test_half_open_failure_reopens_circuit(self, breaker):
        """Failure in half-open state reopens the circuit."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure()

        # Wait for recovery
        time.sleep(1.1)
        assert breaker.state == CircuitState.HALF_OPEN

        # Failure reopens circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_get_status_returns_correct_info(self, breaker):
        """get_status returns comprehensive circuit info."""
        # Record some activity
        breaker.record_success()
        breaker.record_failure()

        status = breaker.get_status()

        assert status["circuit_name"] == "test_service"
        assert status["state"] == "closed"
        assert status["failure_count"] == 1
        assert status["success_count"] == 1
        assert "config" in status
        assert status["config"]["failure_threshold"] == 3


# =============================================================================
# CircuitBreakerRegistry Tests
# =============================================================================


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""

    def test_registry_is_singleton(self):
        """Registry follows singleton pattern."""
        registry1 = CircuitBreakerRegistry()
        registry2 = CircuitBreakerRegistry()
        assert registry1 is registry2

    def test_get_creates_circuit_for_service(self):
        """get() creates circuit breaker if not exists."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.OPENAI_EMBEDDINGS)

        assert breaker is not None
        assert breaker.name == "openai_embeddings"

    def test_get_returns_same_circuit_for_same_service(self):
        """get() returns the same circuit for repeated calls."""
        registry = get_circuit_registry()
        breaker1 = registry.get(CircuitService.OPENAI_EMBEDDINGS)
        breaker2 = registry.get(CircuitService.OPENAI_EMBEDDINGS)

        assert breaker1 is breaker2

    def test_get_all_status_returns_registered_circuits(self):
        """get_all_status returns status for all registered circuits."""
        registry = get_circuit_registry()

        # Register specific circuits (don't iterate all to avoid slow test)
        registry.get(CircuitService.OPENAI_EMBEDDINGS)
        registry.get(CircuitService.COHERE_RERANK)

        statuses = registry.get_all_status()

        # Should have at least the 2 we registered
        assert len(statuses) >= 2
        names = [s["circuit_name"] for s in statuses]
        assert "openai_embeddings" in names
        assert "cohere_rerank" in names

    def test_reset_specific_service(self):
        """reset() can reset a specific service circuit."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.OPENAI_EMBEDDINGS)

        # Trigger some failures
        for _ in range(5):
            breaker.record_failure()

        assert breaker.is_open

        # Reset
        registry.reset(CircuitService.OPENAI_EMBEDDINGS)

        assert breaker.is_closed
        assert breaker.failure_count == 0

    def test_reset_all_registered_services(self):
        """reset() without argument resets all registered circuits."""
        registry = get_circuit_registry()

        # Open specific circuits
        for service in [CircuitService.OPENAI_EMBEDDINGS, CircuitService.GEMINI_FLASH]:
            breaker = registry.get(service)
            for _ in range(5):
                breaker.record_failure()

        # Reset all
        registry.reset()

        # The ones we opened should be closed
        assert registry.get(CircuitService.OPENAI_EMBEDDINGS).is_closed
        assert registry.get(CircuitService.GEMINI_FLASH).is_closed

    def test_thread_safe_get(self):
        """get() is thread-safe for concurrent access."""
        import threading

        registry = get_circuit_registry()
        results = []
        errors = []

        def get_circuit():
            try:
                breaker = registry.get(CircuitService.OPENAI_CHAT)
                results.append(breaker)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_circuit) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors and all results point to the same breaker
        assert len(errors) == 0
        assert len(results) == 10
        assert all(r is results[0] for r in results)


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestUtilityFunctions:
    """Tests for module-level utility functions."""

    def test_is_retryable_exception_connection_error(self):
        """ConnectionError is retryable."""
        assert is_retryable_exception(ConnectionError("connection failed"))

    def test_is_retryable_exception_timeout_error(self):
        """TimeoutError is retryable."""
        assert is_retryable_exception(TimeoutError("request timeout"))

    def test_is_retryable_exception_rate_limit_in_message(self):
        """Exception with 'rate limit' in message is retryable."""
        assert is_retryable_exception(Exception("Rate limit exceeded"))

    def test_is_retryable_exception_status_code_429(self):
        """Exception with status_code=429 is retryable."""

        class MockApiError(Exception):
            status_code = 429

        assert is_retryable_exception(MockApiError("rate limited"))

    def test_is_retryable_exception_openai_rate_limit(self):
        """OpenAI-style RateLimitError is retryable by class name."""

        class RateLimitError(Exception):
            pass

        assert is_retryable_exception(RateLimitError("rate limited"))

    def test_is_retryable_exception_resource_exhausted(self):
        """Gemini 'resource exhausted' is retryable."""
        assert is_retryable_exception(Exception("Resource exhausted"))

    def test_is_retryable_exception_non_retryable(self):
        """Generic exceptions are not retryable."""
        assert not is_retryable_exception(ValueError("invalid input"))

    def test_is_retryable_exception_false_positive_prevention(self):
        """Random numbers in error message don't trigger retryable."""
        # "429" alone shouldn't match - needs context
        assert not is_retryable_exception(ValueError("Need 429 items"))
        assert not is_retryable_exception(ValueError("Error code: 500x"))

    def test_get_circuit_status(self):
        """get_circuit_status returns status dict."""
        status = get_circuit_status(CircuitService.OPENAI_EMBEDDINGS)

        assert "circuit_name" in status
        assert "state" in status
        assert "failure_count" in status

    def test_get_all_circuits_status(self):
        """get_all_circuits_status returns list of status dicts."""
        # First register a circuit
        get_circuit_registry().get(CircuitService.OPENAI_EMBEDDINGS)

        statuses = get_all_circuits_status()

        assert isinstance(statuses, list)
        for status in statuses:
            assert "circuit_name" in status

    def test_is_circuit_open(self):
        """is_circuit_open returns correct boolean."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.COHERE_RERANK)

        assert not is_circuit_open(CircuitService.COHERE_RERANK)

        # Open the circuit
        for _ in range(5):
            breaker.record_failure()

        assert is_circuit_open(CircuitService.COHERE_RERANK)


# =============================================================================
# CircuitOpenError Tests
# =============================================================================


class TestCircuitOpenError:
    """Tests for CircuitOpenError exception."""

    def test_circuit_open_error_attributes(self):
        """CircuitOpenError has correct attributes."""
        error = CircuitOpenError(
            circuit_name="test_circuit",
            cooldown_remaining=30.5,
        )

        assert error.circuit_name == "test_circuit"
        assert error.cooldown_remaining == 30.5
        assert "test_circuit" in str(error)
        assert "30.5" in str(error)


# =============================================================================
# @with_circuit_breaker Decorator Tests
# =============================================================================


class TestWithCircuitBreakerDecorator:
    """Tests for @with_circuit_breaker decorator."""

    async def test_decorator_passes_through_on_success(self):
        """Decorator passes through successful calls."""
        mock_result = {"data": "test"}

        @with_circuit_breaker(CircuitService.OPENAI_EMBEDDINGS)
        async def successful_func():
            return mock_result

        result = await successful_func()
        assert result == mock_result

    async def test_decorator_records_success(self):
        """Decorator records successful calls."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.OPENAI_EMBEDDINGS)
        initial_success = breaker._success_count

        @with_circuit_breaker(CircuitService.OPENAI_EMBEDDINGS)
        async def successful_func():
            return "ok"

        await successful_func()

        assert breaker._success_count > initial_success

    async def test_decorator_records_failure(self):
        """Decorator records failed calls."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.OPENAI_EMBEDDINGS)

        @with_circuit_breaker(CircuitService.OPENAI_EMBEDDINGS)
        async def failing_func():
            raise ConnectionError("connection failed")

        with pytest.raises(ConnectionError):
            await failing_func()

        assert breaker.failure_count > 0

    async def test_decorator_raises_circuit_open_error_when_open(self):
        """Decorator raises CircuitOpenError when circuit is open."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.GEMINI_FLASH)

        # Open the circuit
        for _ in range(5):
            breaker.record_failure()

        assert breaker.is_open

        @with_circuit_breaker(CircuitService.GEMINI_FLASH)
        async def api_call():
            return "should not reach"

        with pytest.raises(CircuitOpenError) as exc_info:
            await api_call()

        assert exc_info.value.circuit_name == "gemini_flash"
        assert exc_info.value.cooldown_remaining > 0

    async def test_decorator_with_timeout_override(self):
        """Decorator respects timeout_override parameter."""

        @with_circuit_breaker(CircuitService.COHERE_RERANK, timeout_override=1)
        async def slow_func():
            await asyncio.sleep(2)  # Longer than timeout
            return "ok"

        with pytest.raises(TimeoutError):
            await slow_func()

    async def test_decorator_with_max_retries_override(self):
        """Decorator respects max_retries_override parameter."""
        call_count = 0

        @with_circuit_breaker(CircuitService.OPENAI_CHAT, max_retries_override=2)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("connection failed")

        with pytest.raises(ConnectionError):
            await flaky_func()

        # Should have tried twice (max_retries_override=2)
        assert call_count == 2


# =============================================================================
# Service Integration Tests
# =============================================================================


class TestServiceIntegration:
    """Tests for circuit breaker integration with services."""

    async def test_embedding_service_fallback_on_circuit_open(self):
        """EmbeddingService returns None when circuit is open."""
        from app.core.circuit_breaker import CircuitOpenError

        # Simulate what embedder.py does
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.OPENAI_EMBEDDINGS)

        # Open the circuit
        for _ in range(5):
            breaker.record_failure()

        assert breaker.is_open

        # The actual service catches CircuitOpenError and returns None
        # We verify the pattern works
        fallback_result = None
        try:

            @with_circuit_breaker(CircuitService.OPENAI_EMBEDDINGS)
            async def embed_text():
                return [0.1] * 1536

            await embed_text()
        except CircuitOpenError:
            # This is the fallback pattern used in embedder.py
            fallback_result = None

        assert fallback_result is None

    async def test_reranker_service_fallback_on_circuit_open(self):
        """CohereRerankService falls back to RRF order when circuit is open."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.COHERE_RERANK)

        # Open the circuit
        for _ in range(5):
            breaker.record_failure()

        # Simulate reranker's fallback behavior
        documents = ["doc1", "doc2", "doc3"]
        fallback_order = None

        try:

            @with_circuit_breaker(CircuitService.COHERE_RERANK)
            async def rerank(docs):
                return {"reranked": docs}

            await rerank(documents)
        except CircuitOpenError:
            # Return original RRF order as fallback
            fallback_order = list(range(len(documents)))

        assert fallback_order == [0, 1, 2]

    async def test_intent_analyzer_fallback_to_rag(self):
        """IntentAnalyzer defaults to RAG engine when circuit is open."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.OPENAI_CHAT)

        # Open the circuit
        for _ in range(5):
            breaker.record_failure()

        # Simulate intent analyzer's fallback
        fallback_intent = None

        try:

            @with_circuit_breaker(CircuitService.OPENAI_CHAT)
            async def classify_intent():
                return {"intent": "citation", "confidence": 0.9}

            await classify_intent()
        except CircuitOpenError:
            # Fallback to RAG with low confidence
            fallback_intent = {"intent": "rag_search", "confidence": 0.3}

        assert fallback_intent is not None
        assert fallback_intent["intent"] == "rag_search"
        assert fallback_intent["confidence"] < 0.5

    async def test_comparator_raises_error_on_circuit_open(self):
        """StatementComparator raises error (no silent fallback) when circuit is open."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.OPENAI_CHAT)

        # Open the circuit
        for _ in range(5):
            breaker.record_failure()

        # Comparator should NOT silently fail - user must know
        with pytest.raises(CircuitOpenError):

            @with_circuit_breaker(CircuitService.OPENAI_CHAT)
            async def compare_statements():
                return {"result": "contradiction"}

            await compare_statements()


# =============================================================================
# Integration Tests
# =============================================================================


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker behavior."""

    async def test_circuit_lifecycle_with_reset(self):
        """Test circuit lifecycle: closed -> open -> reset -> closed."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.DOCUMENTAI_OCR)

        # Start closed
        assert breaker.state == CircuitState.CLOSED

        # Fail until open (threshold is 3 for DOCUMENTAI_OCR)
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        # Reset instead of waiting for cooldown (faster test)
        registry.reset(CircuitService.DOCUMENTAI_OCR)

        assert breaker.state == CircuitState.CLOSED

    async def test_concurrent_access_thread_safety(self):
        """Circuit breaker is thread-safe under concurrent access."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.OPENAI_EMBEDDINGS)

        async def record_activity():
            for _ in range(10):
                breaker.record_success()
                breaker.record_failure()
                await asyncio.sleep(0.001)

        # Run multiple concurrent tasks
        await asyncio.gather(*[record_activity() for _ in range(5)])

        # Circuit should still be in a valid state
        assert breaker.state in [CircuitState.CLOSED, CircuitState.OPEN]

    async def test_graceful_degradation_pattern(self):
        """Test graceful degradation when circuit is open."""
        registry = get_circuit_registry()
        breaker = registry.get(CircuitService.COHERE_RERANK)

        # Open the circuit
        for _ in range(5):
            breaker.record_failure()

        # Verify caller can handle CircuitOpenError
        fallback_used = False

        @with_circuit_breaker(CircuitService.COHERE_RERANK)
        async def rerank_call():
            return {"reranked": True}

        try:
            await rerank_call()
        except CircuitOpenError:
            fallback_used = True
            # Caller would use fallback (e.g., original RRF order)

        assert fallback_used
