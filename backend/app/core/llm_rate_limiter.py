"""Centralized LLM Rate Limiter for API call throttling.

This module provides application-level rate limiting for LLM API calls
to prevent hitting provider rate limits (429 errors).

Rate Limits (verified Apr 2026 from AI Studio dashboard):
- Gemini 3.1 Flash Lite (Paid Tier 1): 4,000 RPM, 4M TPM, 150K RPD
- Gemini 2.5 Flash (Paid Tier 1): 1,000 RPM, 1M TPM, 10K RPD
- OpenAI GPT-4 (tier 1): ~500 RPM
- OpenAI GPT-4 (tier 5): ~10,000 RPM

Strategy:
- Use asyncio.Semaphore to limit concurrent requests per provider
- Add minimum delay between requests to spread load
- Token bucket algorithm for sustained throughput
"""

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class LLMProvider(str, Enum):
    """LLM providers with rate limiting."""

    GEMINI = "gemini"
    OPENAI = "openai"


@dataclass
class RateLimiterConfig:
    """Configuration for a rate limiter.

    Attributes:
        max_concurrent: Maximum concurrent requests allowed.
        min_delay_seconds: Minimum delay between requests.
        requests_per_minute: Target RPM (for logging/monitoring).
    """

    max_concurrent: int = 5
    min_delay_seconds: float = 0.1
    requests_per_minute: int = 60


# Default configurations per provider
# These match Paid Tier 1 limits (verified Apr 2026 from AI Studio dashboard)
DEFAULT_CONFIGS: dict[LLMProvider, RateLimiterConfig] = {
    LLMProvider.GEMINI: RateLimiterConfig(
        max_concurrent=10,  # Paid Tier 1: 4K RPM supports high concurrency
        min_delay_seconds=0.2,  # Burst dampener, not a throttle
        requests_per_minute=1000,  # Conservative vs 4K ceiling
    ),
    LLMProvider.OPENAI: RateLimiterConfig(
        max_concurrent=5,
        min_delay_seconds=0.1,
        requests_per_minute=500,
    ),
}


@dataclass
class RateLimiter:
    """Rate limiter for a specific LLM provider.

    Uses semaphore for concurrency limiting and tracks request timing
    to add delays between requests.

    Example:
        >>> limiter = RateLimiter(LLMProvider.GEMINI)
        >>> async with limiter:
        ...     result = await call_gemini_api()
    """

    provider: LLMProvider
    config: RateLimiterConfig = field(default_factory=RateLimiterConfig)
    _semaphore: asyncio.Semaphore = field(init=False)
    _last_request_time: float = field(default=0.0, init=False)
    _request_count: int = field(default=0, init=False)
    _rate_limited_count: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(init=False)

    def __post_init__(self):
        """Initialize semaphore and lock after dataclass init."""
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        """Acquire semaphore and enforce minimum delay."""
        await self._semaphore.acquire()

        # Enforce minimum delay between requests
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.config.min_delay_seconds:
                delay = self.config.min_delay_seconds - elapsed
                await asyncio.sleep(delay)

            self._last_request_time = time.time()
            self._request_count += 1

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release semaphore."""
        self._semaphore.release()

        # Track rate limit errors
        if exc_type is not None:
            error_str = str(exc_val).lower() if exc_val else ""
            if "429" in error_str or "rate" in error_str or "exhausted" in error_str:
                self._rate_limited_count += 1

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics.

        Returns:
            Dictionary with request counts and rate limit info.
        """
        return {
            "provider": self.provider.value,
            "max_concurrent": self.config.max_concurrent,
            "min_delay_seconds": self.config.min_delay_seconds,
            "total_requests": self._request_count,
            "rate_limited_count": self._rate_limited_count,
        }


class LLMRateLimiterRegistry:
    """Singleton registry for LLM rate limiters.

    Provides centralized access to rate limiters for all providers.
    """

    _instance: "LLMRateLimiterRegistry | None" = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "LLMRateLimiterRegistry":
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._limiters: dict[LLMProvider, RateLimiter] = {}
            cls._instance._initialized = False
        return cls._instance

    def _get_config(self, provider: LLMProvider) -> RateLimiterConfig:
        """Get configuration for a provider from settings or defaults."""
        settings = get_settings()

        if provider == LLMProvider.GEMINI:
            return RateLimiterConfig(
                max_concurrent=settings.gemini_max_concurrent_requests,
                min_delay_seconds=settings.gemini_min_request_delay,
                requests_per_minute=settings.gemini_requests_per_minute,
            )
        elif provider == LLMProvider.OPENAI:
            return RateLimiterConfig(
                max_concurrent=settings.openai_max_concurrent_requests,
                min_delay_seconds=settings.openai_min_request_delay,
                requests_per_minute=settings.openai_requests_per_minute,
            )

        return DEFAULT_CONFIGS.get(provider, RateLimiterConfig())

    def get(self, provider: LLMProvider) -> RateLimiter:
        """Get or create rate limiter for a provider.

        Args:
            provider: The LLM provider.

        Returns:
            RateLimiter instance for the provider.
        """
        if provider not in self._limiters:
            config = self._get_config(provider)
            self._limiters[provider] = RateLimiter(provider=provider, config=config)
            logger.info(
                "llm_rate_limiter_created",
                provider=provider.value,
                max_concurrent=config.max_concurrent,
                min_delay_seconds=config.min_delay_seconds,
            )
        return self._limiters[provider]

    def get_all_stats(self) -> list[dict[str, Any]]:
        """Get statistics for all rate limiters.

        Returns:
            List of stats dictionaries for all providers.
        """
        return [limiter.get_stats() for limiter in self._limiters.values()]


# Global registry instance
_registry = LLMRateLimiterRegistry()


def get_rate_limiter(provider: LLMProvider) -> RateLimiter:
    """Get rate limiter for a provider.

    Args:
        provider: The LLM provider.

    Returns:
        RateLimiter instance.
    """
    return _registry.get(provider)


def get_gemini_rate_limiter() -> RateLimiter:
    """Get rate limiter for Gemini API calls.

    Returns:
        RateLimiter configured for Gemini.
    """
    return get_rate_limiter(LLMProvider.GEMINI)


def get_openai_rate_limiter() -> RateLimiter:
    """Get rate limiter for OpenAI API calls.

    Returns:
        RateLimiter configured for OpenAI.
    """
    return get_rate_limiter(LLMProvider.OPENAI)


def with_rate_limit(
    provider: LLMProvider,
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Decorator to apply rate limiting to an async function.

    Args:
        provider: The LLM provider to rate limit for.

    Returns:
        Decorated function with rate limiting.

    Example:
        @with_rate_limit(LLMProvider.GEMINI)
        async def call_gemini(prompt: str) -> str:
            return await gemini_model.generate_content(prompt)
    """

    def decorator(
        func: Callable[P, Coroutine[Any, Any, T]],
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            limiter = get_rate_limiter(provider)
            async with limiter:
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Sync Rate Limiter (for non-async code paths)
# =============================================================================


@dataclass
class SyncRateLimiter:
    """Synchronous rate limiter for blocking code paths.

    Uses threading.Lock for concurrency limiting and tracks request timing
    to add delays between requests.

    Example:
        >>> limiter = SyncRateLimiter(LLMProvider.GEMINI)
        >>> with limiter:
        ...     result = call_gemini_api()  # blocking call
    """

    provider: LLMProvider
    config: RateLimiterConfig = field(default_factory=RateLimiterConfig)
    _semaphore: "threading.Semaphore" = field(init=False)
    _last_request_time: float = field(default=0.0, init=False)
    _request_count: int = field(default=0, init=False)
    _rate_limited_count: int = field(default=0, init=False)
    _lock: "threading.Lock" = field(init=False)

    def __post_init__(self):
        """Initialize semaphore and lock after dataclass init."""
        import threading

        self._semaphore = threading.Semaphore(self.config.max_concurrent)
        self._lock = threading.Lock()

    def __enter__(self):
        """Acquire semaphore and enforce minimum delay."""
        self._semaphore.acquire()

        # Enforce minimum delay between requests
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.config.min_delay_seconds:
                delay = self.config.min_delay_seconds - elapsed
                time.sleep(delay)

            self._last_request_time = time.time()
            self._request_count += 1

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release semaphore."""
        self._semaphore.release()

        # Track rate limit errors
        if exc_type is not None:
            error_str = str(exc_val).lower() if exc_val else ""
            if "429" in error_str or "rate" in error_str or "exhausted" in error_str:
                self._rate_limited_count += 1

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "provider": self.provider.value,
            "type": "sync",
            "max_concurrent": self.config.max_concurrent,
            "min_delay_seconds": self.config.min_delay_seconds,
            "total_requests": self._request_count,
            "rate_limited_count": self._rate_limited_count,
        }


class SyncRateLimiterRegistry:
    """Singleton registry for sync LLM rate limiters."""

    _instance: "SyncRateLimiterRegistry | None" = None
    _lock: "threading.Lock | None" = None

    def __new__(cls) -> "SyncRateLimiterRegistry":
        """Create singleton instance."""
        if cls._instance is None:
            import threading

            cls._instance = super().__new__(cls)
            cls._instance._limiters: dict[LLMProvider, SyncRateLimiter] = {}
            cls._lock = threading.Lock()
        return cls._instance

    def _get_config(self, provider: LLMProvider) -> RateLimiterConfig:
        """Get configuration for a provider from settings or defaults."""
        settings = get_settings()

        if provider == LLMProvider.GEMINI:
            return RateLimiterConfig(
                max_concurrent=settings.gemini_max_concurrent_requests,
                min_delay_seconds=settings.gemini_min_request_delay,
                requests_per_minute=settings.gemini_requests_per_minute,
            )
        elif provider == LLMProvider.OPENAI:
            return RateLimiterConfig(
                max_concurrent=settings.openai_max_concurrent_requests,
                min_delay_seconds=settings.openai_min_request_delay,
                requests_per_minute=settings.openai_requests_per_minute,
            )

        return DEFAULT_CONFIGS.get(provider, RateLimiterConfig())

    def get(self, provider: LLMProvider) -> SyncRateLimiter:
        """Get or create sync rate limiter for a provider."""
        with self._lock:
            if provider not in self._limiters:
                config = self._get_config(provider)
                self._limiters[provider] = SyncRateLimiter(provider=provider, config=config)
                logger.info(
                    "sync_llm_rate_limiter_created",
                    provider=provider.value,
                    max_concurrent=config.max_concurrent,
                    min_delay_seconds=config.min_delay_seconds,
                )
            return self._limiters[provider]


# Global sync registry instance
_sync_registry = SyncRateLimiterRegistry()


def get_sync_rate_limiter(provider: LLMProvider) -> SyncRateLimiter:
    """Get sync rate limiter for a provider.

    Args:
        provider: The LLM provider.

    Returns:
        SyncRateLimiter instance.
    """
    return _sync_registry.get(provider)


def get_gemini_sync_rate_limiter() -> SyncRateLimiter:
    """Get sync rate limiter for Gemini API calls.

    Returns:
        SyncRateLimiter configured for Gemini.
    """
    return get_sync_rate_limiter(LLMProvider.GEMINI)


# =============================================================================
# Distributed Rate Limiter (Redis-based for cross-worker coordination)
# =============================================================================


@dataclass
class DistributedRateLimiter:
    """Redis-based distributed rate limiter for LLM API calls.

    Uses Redis sorted sets for sliding window rate limiting across all workers.
    This ensures the global API quota is respected even with multiple Celery workers.

    Example:
        >>> limiter = DistributedRateLimiter(LLMProvider.GEMINI)
        >>> with limiter:
        ...     result = call_gemini_api()  # Blocks if rate limit exceeded
    """

    provider: LLMProvider
    max_requests_per_minute: int = 60  # Default for Gemini free tier
    _redis_key_prefix: str = "llm_rate_limit"

    def __post_init__(self):
        """Initialize rate limiter with provider-specific settings."""
        settings = get_settings()

        if self.provider == LLMProvider.GEMINI:
            self.max_requests_per_minute = settings.gemini_requests_per_minute
        elif self.provider == LLMProvider.OPENAI:
            self.max_requests_per_minute = settings.openai_requests_per_minute

    @property
    def _redis_key(self) -> str:
        """Redis key for this provider's rate limit."""
        return f"{self._redis_key_prefix}:{self.provider.value}"

    def _get_redis_client(self):
        """Get Redis client for distributed coordination."""
        from app.services.distributed_lock import get_sync_redis_client
        return get_sync_redis_client()

    def acquire(self, timeout: float = 30.0) -> bool:
        """Try to acquire a rate limit token, blocking if necessary.

        Uses sliding window algorithm with Redis sorted set.

        Args:
            timeout: Maximum seconds to wait for a token.

        Returns:
            True if token acquired, False if timeout exceeded.
        """
        import uuid

        try:
            redis_client = self._get_redis_client()
            start_time = time.time()
            window_seconds = 60  # 1 minute sliding window

            while time.time() - start_time < timeout:
                current_time = time.time()
                window_start = current_time - window_seconds

                # Remove old entries outside window
                redis_client.zremrangebyscore(self._redis_key, "-inf", window_start)

                # Count current entries in window
                current_count = redis_client.zcard(self._redis_key)

                if current_count < self.max_requests_per_minute:
                    # Add new entry with current timestamp as score
                    request_id = f"{current_time}:{uuid.uuid4().hex[:8]}"
                    redis_client.zadd(self._redis_key, {request_id: current_time})

                    # Set expiry on the key (cleanup for safety)
                    redis_client.expire(self._redis_key, window_seconds + 10)

                    logger.debug(
                        "distributed_rate_limit_acquired",
                        provider=self.provider.value,
                        current_count=current_count + 1,
                        max_rpm=self.max_requests_per_minute,
                    )
                    return True
                else:
                    # Get oldest entry to calculate wait time
                    oldest = redis_client.zrange(self._redis_key, 0, 0, withscores=True)
                    if oldest:
                        oldest_time = oldest[0][1]
                        wait_time = max(0.1, oldest_time + window_seconds - current_time)
                        wait_time = min(wait_time, 2.0)  # Cap wait to 2 seconds per iteration

                        logger.debug(
                            "distributed_rate_limit_waiting",
                            provider=self.provider.value,
                            current_count=current_count,
                            wait_time=wait_time,
                        )
                        time.sleep(wait_time)
                    else:
                        time.sleep(0.1)

            logger.warning(
                "distributed_rate_limit_timeout",
                provider=self.provider.value,
                timeout=timeout,
            )
            return False

        except Exception as e:
            # If Redis is unavailable, fall back to allowing the request
            # (better to risk rate limiting than block all requests)
            logger.warning(
                "distributed_rate_limit_redis_error",
                provider=self.provider.value,
                error=str(e),
            )
            return True

    def __enter__(self):
        """Acquire rate limit token on context enter."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """No cleanup needed on exit."""
        pass


@dataclass
class InProcessRateLimiter:
    """In-memory sliding window rate limiter for single-worker deployments.

    Eliminates ~3,000 Redis sorted-set ops per document by using a local
    deque instead of Redis for rate limiting. Same interface as DistributedRateLimiter.

    Rollback: Set WORKER_COUNT=2 to switch back to distributed mode.
    """

    provider: LLMProvider
    max_requests_per_minute: int = 60

    def __post_init__(self):
        """Initialize with provider-specific RPM from settings."""
        import threading
        from collections import deque

        settings = get_settings()

        if self.provider == LLMProvider.GEMINI:
            self.max_requests_per_minute = settings.gemini_requests_per_minute
        elif self.provider == LLMProvider.OPENAI:
            self.max_requests_per_minute = settings.openai_requests_per_minute

        self._lock = threading.Lock()
        self._timestamps: deque = deque()

    def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire a rate limit token using in-memory sliding window.

        Args:
            timeout: Maximum seconds to wait for a token.

        Returns:
            True if token acquired, False if timeout exceeded.
        """
        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                now = time.time()
                # Remove entries outside the 60s window
                while self._timestamps and self._timestamps[0] < now - 60:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.max_requests_per_minute:
                    self._timestamps.append(now)
                    return True
            time.sleep(0.1)

        logger.warning(
            "in_process_rate_limit_timeout",
            provider=self.provider.value,
            timeout=timeout,
        )
        return False

    def __enter__(self):
        """Acquire rate limit token on context enter."""
        self.acquire()
        return self

    def __exit__(self, *args):
        """No cleanup needed on exit."""
        pass


class DistributedRateLimiterRegistry:
    """Singleton registry for rate limiters (distributed or in-process)."""

    _instance: "DistributedRateLimiterRegistry | None" = None
    _lock = None

    def __new__(cls) -> "DistributedRateLimiterRegistry":
        """Create singleton instance."""
        if cls._instance is None:
            import threading

            cls._instance = super().__new__(cls)
            cls._instance._limiters: dict[LLMProvider, DistributedRateLimiter | InProcessRateLimiter] = {}
            cls._lock = threading.Lock()
        return cls._instance

    def get(self, provider: LLMProvider) -> DistributedRateLimiter | InProcessRateLimiter:
        """Get or create rate limiter for a provider.

        Uses in-process limiter when worker_count <= 1 (saves ~3,000 Redis ops/doc).
        Falls back to distributed limiter for multi-worker deployments.
        """
        with self._lock:
            if provider not in self._limiters:
                settings = get_settings()
                use_in_process = settings.worker_count <= 1

                if use_in_process:
                    self._limiters[provider] = InProcessRateLimiter(provider=provider)
                    logger.info(
                        "in_process_rate_limiter_created",
                        provider=provider.value,
                        max_rpm=self._limiters[provider].max_requests_per_minute,
                        reason="worker_count<=1",
                    )
                else:
                    self._limiters[provider] = DistributedRateLimiter(provider=provider)
                    logger.info(
                        "distributed_rate_limiter_created",
                        provider=provider.value,
                        max_rpm=self._limiters[provider].max_requests_per_minute,
                        worker_count=settings.worker_count,
                    )
            return self._limiters[provider]


# Global distributed registry instance
_distributed_registry = DistributedRateLimiterRegistry()


def get_distributed_rate_limiter(provider: LLMProvider) -> DistributedRateLimiter | InProcessRateLimiter:
    """Get rate limiter for a provider (distributed or in-process).

    Automatically selects in-process mode when WORKER_COUNT<=1
    to eliminate ~3,000 Redis ops per document.

    Use this for cross-worker rate limiting (e.g., in Celery tasks).

    Args:
        provider: The LLM provider.

    Returns:
        Rate limiter instance (DistributedRateLimiter or InProcessRateLimiter).
    """
    return _distributed_registry.get(provider)


def get_gemini_distributed_rate_limiter() -> DistributedRateLimiter | InProcessRateLimiter:
    """Get rate limiter for Gemini API calls.

    Use this in Celery tasks to coordinate rate limiting across workers.

    Returns:
        Rate limiter configured for Gemini.
    """
    return get_distributed_rate_limiter(LLMProvider.GEMINI)
