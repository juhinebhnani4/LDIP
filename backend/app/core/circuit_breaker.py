"""Centralized circuit breaker module for external API resilience (Story 13.2).

This module provides a unified circuit breaker pattern with tenacity retries
for all external API calls (OpenAI, Gemini, Cohere, DocumentAI). Features:

1. Service-specific circuit breakers with configurable thresholds
2. Exponential backoff with jitter to prevent thundering herd
3. Graceful degradation with fallback responses
4. Structured logging with correlation_id integration

Circuit States:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit tripped, requests fail fast without calling API
- HALF_OPEN: Testing if service recovered with single request

Usage:
    from app.core.circuit_breaker import with_circuit_breaker, CircuitService

    @with_circuit_breaker(CircuitService.OPENAI_EMBEDDINGS)
    async def embed_text(text: str) -> list[float]:
        return await client.embeddings.create(...)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from threading import Lock
from typing import TYPE_CHECKING, Any, TypeVar

import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.correlation import get_correlation_id

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = structlog.get_logger(__name__)

# =============================================================================
# Type Variables
# =============================================================================

T = TypeVar("T")


# =============================================================================
# Circuit State Enum
# =============================================================================


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


# =============================================================================
# Service Definitions
# =============================================================================


class CircuitService(str, Enum):
    """External services with circuit breaker protection."""

    OPENAI_EMBEDDINGS = "openai_embeddings"
    OPENAI_CHAT = "openai_chat"
    GEMINI_FLASH = "gemini_flash"
    COHERE_RERANK = "cohere_rerank"
    DOCUMENTAI_OCR = "documentai_ocr"


# =============================================================================
# Retryable Exceptions
# =============================================================================

# Standard Python exceptions that are retryable
RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
)


def is_retryable_exception(exc: Exception) -> bool:
    """Check if an exception is retryable.

    Checks both exception types and error context to determine if an
    operation should be retried. Handles OpenAI, Cohere, and Gemini errors.

    Args:
        exc: The exception to check.

    Returns:
        True if the exception should trigger a retry.
    """
    # Check standard exceptions first
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True

    # Check for OpenAI SDK exceptions by class name (avoids hard import)
    exc_class_name = type(exc).__name__
    openai_retryable = (
        "RateLimitError",
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "ServiceUnavailableError",
    )
    if exc_class_name in openai_retryable:
        return True

    # Check for Cohere API errors
    if exc_class_name == "ApiError":
        # Cohere ApiError - check status code if available
        status_code = getattr(exc, "status_code", None)
        if status_code is not None and status_code in (429, 500, 502, 503, 504):
            return True

    # Check for Google/Gemini errors
    google_retryable = (
        "ResourceExhausted",
        "ServiceUnavailable",
        "DeadlineExceeded",
        "Unavailable",
    )
    if exc_class_name in google_retryable:
        return True

    # Check HTTP status code in exception attributes (common pattern)
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status_code, int) and status_code in (429, 500, 502, 503, 504):
        return True

    # Fallback: Check error message for specific HTTP status patterns
    # Use stricter patterns to avoid false positives
    error_str = str(exc).lower()
    retryable_patterns = (
        "status code 429",
        "status code 500",
        "status code 502",
        "status code 503",
        "status code 504",
        "status_code=429",
        "status_code=500",
        "status_code=502",
        "status_code=503",
        "status_code=504",
        "rate limit",
        "rate_limit",
        "ratelimit",
        "quota exceeded",
        "resource exhausted",
        "temporarily unavailable",
        "service unavailable",
    )

    return any(pattern in error_str for pattern in retryable_patterns)


# =============================================================================
# Circuit Breaker Configuration
# =============================================================================


@dataclass
class CircuitConfig:
    """Configuration for a circuit breaker.

    Attributes:
        failure_threshold: Failures before opening circuit.
        recovery_timeout: Seconds before attempting recovery.
        timeout_seconds: Per-request timeout.
        max_retries: Maximum retry attempts.
        initial_wait: Initial wait between retries (seconds).
        max_wait: Maximum wait between retries (seconds).
        jitter: Random jitter added to wait (seconds).
    """

    failure_threshold: int = 5
    recovery_timeout: int = 60
    timeout_seconds: int = 30
    max_retries: int = 3
    initial_wait: float = 1.0
    max_wait: float = 10.0
    jitter: float = 2.0


# Service-specific configurations per architecture requirements
SERVICE_CONFIGS: dict[CircuitService, CircuitConfig] = {
    CircuitService.OPENAI_EMBEDDINGS: CircuitConfig(
        failure_threshold=5,
        recovery_timeout=60,
        timeout_seconds=30,
        max_retries=3,
    ),
    CircuitService.OPENAI_CHAT: CircuitConfig(
        failure_threshold=5,
        recovery_timeout=60,
        timeout_seconds=30,
        max_retries=3,
    ),
    CircuitService.GEMINI_FLASH: CircuitConfig(
        failure_threshold=5,
        recovery_timeout=60,
        timeout_seconds=30,
        max_retries=3,
    ),
    CircuitService.COHERE_RERANK: CircuitConfig(
        failure_threshold=5,
        recovery_timeout=60,
        timeout_seconds=10,  # Shorter timeout for rerank
        max_retries=3,
    ),
    CircuitService.DOCUMENTAI_OCR: CircuitConfig(
        failure_threshold=3,  # Lower threshold for OCR
        recovery_timeout=120,  # Longer recovery for OCR
        timeout_seconds=60,  # Longer timeout for OCR
        max_retries=2,  # Fewer retries for expensive OCR
    ),
}


# =============================================================================
# Circuit Breaker Implementation
# =============================================================================


@dataclass
class CircuitBreaker:
    """Thread-safe circuit breaker implementation.

    Implements the circuit breaker pattern with three states:
    - CLOSED: Normal operation
    - OPEN: Failing fast (after failure_threshold failures)
    - HALF_OPEN: Testing recovery (after recovery_timeout)

    Example:
        >>> breaker = CircuitBreaker("openai", config)
        >>> if breaker.is_open:
        ...     raise CircuitOpenError("Circuit is open")
        >>> try:
        ...     result = await api_call()
        ...     breaker.record_success()
        ... except Exception:
        ...     breaker.record_failure()
    """

    name: str
    config: CircuitConfig
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float | None = field(default=None, init=False)
    _last_state_change: float = field(default_factory=time.time, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, auto-transitioning if needed."""
        with self._lock:
            # Check if recovery timeout has passed when circuit is open
            if (
                self._state == CircuitState.OPEN
                and self._last_failure_time is not None
            ):
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.config.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        with self._lock:
            return self._failure_count

    @property
    def last_failure_time(self) -> float | None:
        """Get timestamp of last failure."""
        with self._lock:
            return self._last_failure_time

    @property
    def cooldown_remaining(self) -> float:
        """Get seconds remaining in cooldown period."""
        with self._lock:
            if self._state != CircuitState.OPEN or self._last_failure_time is None:
                return 0.0
            elapsed = time.time() - self._last_failure_time
            remaining = self.config.recovery_timeout - elapsed
            return max(0.0, remaining)

    def record_success(self) -> None:
        """Record a successful API call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Success in half-open state: close circuit
                self._transition_to(CircuitState.CLOSED)
            self._failure_count = 0
            self._success_count += 1

    def record_failure(self) -> None:
        """Record a failed API call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Failure in half-open state: reopen circuit
                self._transition_to(CircuitState.OPEN)
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.config.failure_threshold
            ):
                # Threshold reached: open circuit
                self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new circuit state with logging.

        Args:
            new_state: The state to transition to.
        """
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()

        # Reset counters on state change
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0

        # Log state change with correlation_id
        logger.warning(
            "circuit_state_change",
            circuit_name=self.name,
            old_state=old_state.value,
            new_state=new_state.value,
            failure_count=self._failure_count,
            correlation_id=get_correlation_id(),
        )

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status for health endpoint.

        Returns:
            Dictionary with circuit status details.
        """
        with self._lock:
            # Calculate cooldown inline to avoid deadlock (lock is not re-entrant)
            cooldown = 0.0
            if self._state == CircuitState.OPEN and self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                cooldown = max(0.0, self.config.recovery_timeout - elapsed)

            return {
                "circuit_name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure": self._last_failure_time,
                "cooldown_remaining": cooldown,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout": self.config.recovery_timeout,
                    "timeout_seconds": self.config.timeout_seconds,
                },
            }


# =============================================================================
# Circuit Breaker Registry
# =============================================================================


class CircuitBreakerRegistry:
    """Singleton registry for managing circuit breakers.

    Provides centralized access to circuit breakers for all services.
    Thread-safe for concurrent access.

    Example:
        >>> registry = CircuitBreakerRegistry()
        >>> breaker = registry.get(CircuitService.OPENAI_EMBEDDINGS)
        >>> breaker.is_open
        False
    """

    _instance: CircuitBreakerRegistry | None = None
    _lock = Lock()

    def __new__(cls) -> CircuitBreakerRegistry:
        """Create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._circuits: dict[CircuitService, CircuitBreaker] = {}
                    cls._instance._circuits_lock = Lock()
                    cls._instance._initialized = False
        return cls._instance

    def get(self, service: CircuitService) -> CircuitBreaker:
        """Get or create circuit breaker for a service.

        Thread-safe: uses locking to prevent duplicate circuit creation.

        Args:
            service: The external service.

        Returns:
            CircuitBreaker instance for the service.
        """
        # Fast path: check without lock first (safe for read)
        if service in self._circuits:
            return self._circuits[service]

        # Slow path: acquire lock to create circuit
        with self._circuits_lock:
            # Double-check after acquiring lock
            if service not in self._circuits:
                config = SERVICE_CONFIGS.get(service, CircuitConfig())
                self._circuits[service] = CircuitBreaker(
                    name=service.value,
                    config=config,
                )
                logger.info(
                    "circuit_breaker_created",
                    circuit_name=service.value,
                    failure_threshold=config.failure_threshold,
                    recovery_timeout=config.recovery_timeout,
                )
            return self._circuits[service]

    def get_all_status(self) -> list[dict[str, Any]]:
        """Get status of all registered circuit breakers.

        Returns:
            List of status dictionaries for all circuits.
        """
        return [breaker.get_status() for breaker in self._circuits.values()]

    def reset(self, service: CircuitService | None = None) -> None:
        """Reset circuit breaker(s) to closed state.

        Args:
            service: Specific service to reset, or None to reset all.
        """
        if service is not None:
            if service in self._circuits:
                breaker = self._circuits[service]
                with breaker._lock:
                    breaker._state = CircuitState.CLOSED
                    breaker._failure_count = 0
                    breaker._success_count = 0
                logger.info("circuit_breaker_reset", circuit_name=service.value)
        else:
            for svc in list(self._circuits.keys()):
                self.reset(svc)


# Global registry instance
_registry = CircuitBreakerRegistry()


def get_circuit_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry.

    Returns:
        The singleton CircuitBreakerRegistry instance.
    """
    return _registry


# =============================================================================
# Circuit Open Error
# =============================================================================


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open.

    This exception indicates that the circuit breaker has tripped
    and requests are being rejected without calling the external API.

    Attributes:
        circuit_name: Name of the open circuit.
        cooldown_remaining: Seconds until circuit attempts recovery.
    """

    def __init__(
        self,
        circuit_name: str,
        cooldown_remaining: float = 0.0,
    ):
        self.circuit_name = circuit_name
        self.cooldown_remaining = cooldown_remaining
        super().__init__(
            f"Circuit '{circuit_name}' is open. "
            f"Retry after {cooldown_remaining:.1f}s"
        )


# =============================================================================
# Circuit Breaker Decorator
# =============================================================================


def with_circuit_breaker(
    service: CircuitService,
    *,
    timeout_override: int | None = None,
    max_retries_override: int | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator that wraps an async function with circuit breaker and retry logic.

    Combines tenacity retries with circuit breaker pattern:
    1. Check if circuit is open (fail fast if so)
    2. Execute function with timeout
    3. Retry on retryable errors with exponential backoff + jitter
    4. Record success/failure to circuit breaker

    Args:
        service: The external service this function calls.
        timeout_override: Override the default timeout (optional).
        max_retries_override: Override the default max retries (optional).

    Returns:
        Decorated async function with circuit breaker protection.

    Example:
        @with_circuit_breaker(CircuitService.OPENAI_EMBEDDINGS)
        async def embed_text(text: str) -> list[float]:
            return await client.embeddings.create(...)
    """

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            registry = get_circuit_registry()
            breaker = registry.get(service)
            config = breaker.config

            # Check if circuit is open
            if breaker.is_open:
                logger.warning(
                    "circuit_breaker_rejected",
                    circuit_name=service.value,
                    cooldown_remaining=breaker.cooldown_remaining,
                    correlation_id=get_correlation_id(),
                )
                raise CircuitOpenError(
                    circuit_name=service.value,
                    cooldown_remaining=breaker.cooldown_remaining,
                )

            # Configure timeout and retries
            timeout = timeout_override or config.timeout_seconds
            max_retries = max_retries_override or config.max_retries

            # Attempt with retries
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(max_retries),
                    wait=wait_exponential_jitter(
                        initial=config.initial_wait,
                        max=config.max_wait,
                        jitter=config.jitter,
                    ),
                    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
                    reraise=True,
                ):
                    with attempt:
                        # Execute with timeout
                        result = await asyncio.wait_for(
                            func(*args, **kwargs),
                            timeout=timeout,
                        )
                        # Record success
                        breaker.record_success()
                        return result

            except RetryError as e:
                # All retries exhausted
                breaker.record_failure()
                logger.error(
                    "circuit_breaker_retries_exhausted",
                    circuit_name=service.value,
                    max_retries=max_retries,
                    error=str(e.last_attempt.exception()) if e.last_attempt else "unknown",
                    correlation_id=get_correlation_id(),
                )
                # Re-raise the underlying exception
                if e.last_attempt and e.last_attempt.exception():
                    raise e.last_attempt.exception() from e
                raise

            except TimeoutError as e:
                breaker.record_failure()
                logger.warning(
                    "circuit_breaker_timeout",
                    circuit_name=service.value,
                    timeout_seconds=timeout,
                    correlation_id=get_correlation_id(),
                )
                raise TimeoutError(
                    f"{service.value} request timed out after {timeout}s"
                ) from e

            except Exception as e:
                # Check if retryable for potential circuit trip
                if is_retryable_exception(e):
                    breaker.record_failure()
                    logger.warning(
                        "circuit_breaker_failure",
                        circuit_name=service.value,
                        error=str(e),
                        error_type=type(e).__name__,
                        correlation_id=get_correlation_id(),
                    )
                raise

            # This should never be reached due to the return in the loop
            # but is needed for type checker
            raise RuntimeError("Unexpected state in circuit breaker")

        return wrapper

    return decorator


# =============================================================================
# Utility Functions
# =============================================================================


def get_circuit_status(service: CircuitService) -> dict[str, Any]:
    """Get status of a specific circuit breaker.

    Args:
        service: The external service.

    Returns:
        Dictionary with circuit status details.
    """
    registry = get_circuit_registry()
    breaker = registry.get(service)
    return breaker.get_status()


def get_all_circuits_status() -> list[dict[str, Any]]:
    """Get status of all circuit breakers.

    Returns:
        List of status dictionaries for all circuits.
    """
    registry = get_circuit_registry()
    return registry.get_all_status()


def is_circuit_open(service: CircuitService) -> bool:
    """Check if a circuit is open.

    Args:
        service: The external service.

    Returns:
        True if the circuit is open.
    """
    registry = get_circuit_registry()
    breaker = registry.get(service)
    return breaker.is_open


# =============================================================================
# Synchronous Circuit Breaker Decorator (Story 17.2)
# =============================================================================


def with_sync_circuit_breaker(
    service: CircuitService,
    *,
    max_retries_override: int | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for SYNCHRONOUS functions with circuit breaker protection.

    Story 17.2: Circuit Breaker for Document AI Chunk Processing

    This is the synchronous version of with_circuit_breaker for use in
    Celery tasks that call blocking APIs (like Document AI).

    Combines retry logic with circuit breaker pattern:
    1. Check if circuit is open (fail fast if so)
    2. Execute function with retries
    3. Record success/failure to circuit breaker

    Args:
        service: The external service this function calls.
        max_retries_override: Override the default max retries (optional).

    Returns:
        Decorated sync function with circuit breaker protection.

    Example:
        @with_sync_circuit_breaker(CircuitService.DOCUMENTAI_OCR)
        def process_document(content: bytes) -> OCRResult:
            return client.process_document(...)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            import time

            registry = get_circuit_registry()
            breaker = registry.get(service)
            config = breaker.config

            # Check if circuit is open
            if breaker.is_open:
                logger.warning(
                    "sync_circuit_breaker_rejected",
                    circuit_name=service.value,
                    cooldown_remaining=breaker.cooldown_remaining,
                    correlation_id=get_correlation_id(),
                )
                raise CircuitOpenError(
                    circuit_name=service.value,
                    cooldown_remaining=breaker.cooldown_remaining,
                )

            max_retries = max_retries_override or config.max_retries
            last_exception: Exception | None = None

            # Attempt with manual retries (exponential backoff)
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    breaker.record_success()
                    return result

                except Exception as e:
                    last_exception = e

                    if is_retryable_exception(e):
                        breaker.record_failure()

                        if attempt < max_retries - 1:
                            # Calculate backoff with jitter
                            wait_time = min(
                                config.initial_wait * (2 ** attempt) + (config.jitter * (0.5 + 0.5 * time.time() % 1)),
                                config.max_wait,
                            )
                            logger.warning(
                                "sync_circuit_breaker_retry",
                                circuit_name=service.value,
                                attempt=attempt + 1,
                                max_retries=max_retries,
                                wait_seconds=round(wait_time, 2),
                                error=str(e),
                                correlation_id=get_correlation_id(),
                            )
                            time.sleep(wait_time)
                        else:
                            # All retries exhausted
                            logger.error(
                                "sync_circuit_breaker_retries_exhausted",
                                circuit_name=service.value,
                                max_retries=max_retries,
                                error=str(e),
                                correlation_id=get_correlation_id(),
                            )
                            raise
                    else:
                        # Non-retryable exception
                        logger.error(
                            "sync_circuit_breaker_non_retryable",
                            circuit_name=service.value,
                            error=str(e),
                            error_type=type(e).__name__,
                            correlation_id=get_correlation_id(),
                        )
                        raise

            # This should never be reached
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in sync circuit breaker")

        return wrapper

    return decorator
