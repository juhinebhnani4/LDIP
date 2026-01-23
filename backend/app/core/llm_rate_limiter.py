"""Centralized LLM Rate Limiter for API call throttling.

This module provides application-level rate limiting for LLM API calls
to prevent hitting provider rate limits (429 errors).

Rate Limits (as of Jan 2025):
- Gemini Flash (free tier): ~60 RPM, ~1M TPM
- Gemini Flash (paid tier): ~1000 RPM, ~4M TPM
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
# These are conservative defaults for free/low tiers
DEFAULT_CONFIGS: dict[LLMProvider, RateLimiterConfig] = {
    LLMProvider.GEMINI: RateLimiterConfig(
        max_concurrent=3,  # Conservative for free tier
        min_delay_seconds=0.2,  # ~300 RPM max theoretical
        requests_per_minute=60,
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
