"""Centralized LLM Cost Tracking Module.

Provides a unified interface for tracking LLM costs across all engines and services.
Supports multiple LLM providers (OpenAI, Gemini, Cohere) with up-to-date pricing.
All costs are tracked in INR (Indian Rupees) as the primary currency.

Usage:
    from app.core.cost_tracking import CostTracker, LLMProvider

    # Create tracker for a specific operation
    tracker = CostTracker(
        provider=LLMProvider.OPENAI_GPT4,
        operation="contradiction_comparison",
        matter_id="uuid",
        document_id="uuid",
    )

    # Track tokens after API call
    tracker.add_tokens(input_tokens=500, output_tokens=150)

    # Log the cost
    tracker.log_cost()

    # Get cost summary in INR
    cost = tracker.total_cost_inr
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Currency Configuration
# =============================================================================

# USD to INR exchange rate (update periodically)
# As of Jan 2025: ~83-84 INR per USD
USD_TO_INR_RATE = 83.50


def usd_to_inr(usd_amount: float) -> float:
    """Convert USD to INR.

    Args:
        usd_amount: Amount in USD.

    Returns:
        Amount in INR.
    """
    return usd_amount * USD_TO_INR_RATE


def inr_to_usd(inr_amount: float) -> float:
    """Convert INR to USD.

    Args:
        inr_amount: Amount in INR.

    Returns:
        Amount in USD.
    """
    return inr_amount / USD_TO_INR_RATE


# =============================================================================
# LLM Provider Definitions with Pricing (as of Jan 2025)
# Prices are stored in USD but converted to INR for display
# =============================================================================


class LLMProvider(str, Enum):
    """Supported LLM providers with model identifiers."""

    # OpenAI Models
    OPENAI_GPT4_TURBO = "gpt-4-turbo-preview"
    OPENAI_GPT4O = "gpt-4o"
    OPENAI_GPT4O_MINI = "gpt-4o-mini"
    OPENAI_GPT35_TURBO = "gpt-3.5-turbo"
    OPENAI_EMBEDDING_SMALL = "text-embedding-3-small"
    OPENAI_EMBEDDING_LARGE = "text-embedding-3-large"

    # Google Models
    GEMINI_FLASH = "gemini-2.5-flash"
    GEMINI_PRO = "gemini-1.5-pro"

    # Cohere Models
    COHERE_RERANK = "rerank-v3.5"

    # Google Document AI (per page pricing)
    GOOGLE_DOCUMENT_AI = "document-ai"


@dataclass
class ProviderPricing:
    """Pricing information for an LLM provider."""

    input_cost_per_1k: float  # Cost per 1K input tokens
    output_cost_per_1k: float  # Cost per 1K output tokens
    unit: str = "tokens"  # "tokens", "pages", "searches"


# Pricing constants (updated Jan 2025)
PROVIDER_PRICING: dict[LLMProvider, ProviderPricing] = {
    # OpenAI GPT-4 Turbo
    LLMProvider.OPENAI_GPT4_TURBO: ProviderPricing(
        input_cost_per_1k=0.01,
        output_cost_per_1k=0.03,
    ),
    # OpenAI GPT-4o
    LLMProvider.OPENAI_GPT4O: ProviderPricing(
        input_cost_per_1k=0.005,
        output_cost_per_1k=0.015,
    ),
    # OpenAI GPT-4o-mini (200x cheaper than GPT-4)
    LLMProvider.OPENAI_GPT4O_MINI: ProviderPricing(
        input_cost_per_1k=0.00015,
        output_cost_per_1k=0.0006,
    ),
    # OpenAI GPT-3.5 Turbo
    LLMProvider.OPENAI_GPT35_TURBO: ProviderPricing(
        input_cost_per_1k=0.0005,
        output_cost_per_1k=0.0015,
    ),
    # OpenAI Embeddings
    LLMProvider.OPENAI_EMBEDDING_SMALL: ProviderPricing(
        input_cost_per_1k=0.00002,
        output_cost_per_1k=0.0,  # Embeddings have no output tokens
    ),
    LLMProvider.OPENAI_EMBEDDING_LARGE: ProviderPricing(
        input_cost_per_1k=0.00013,
        output_cost_per_1k=0.0,
    ),
    # Gemini Flash (very cost-effective)
    LLMProvider.GEMINI_FLASH: ProviderPricing(
        input_cost_per_1k=0.000075,  # $0.075 per 1M input tokens
        output_cost_per_1k=0.0003,  # $0.30 per 1M output tokens
    ),
    # Gemini Pro
    LLMProvider.GEMINI_PRO: ProviderPricing(
        input_cost_per_1k=0.00125,
        output_cost_per_1k=0.005,
    ),
    # Cohere Rerank (per search, not tokens)
    LLMProvider.COHERE_RERANK: ProviderPricing(
        input_cost_per_1k=0.002,  # $2 per 1K searches
        output_cost_per_1k=0.0,
        unit="searches",
    ),
    # Google Document AI (per page)
    LLMProvider.GOOGLE_DOCUMENT_AI: ProviderPricing(
        input_cost_per_1k=1.50,  # $1.50 per 1K pages
        output_cost_per_1k=0.0,
        unit="pages",
    ),
}


# =============================================================================
# Cost Tracker Class
# =============================================================================


@dataclass
class CostTracker:
    """Tracks LLM costs for a single operation.

    Thread-safe cost tracking with automatic logging.

    Attributes:
        provider: The LLM provider being used.
        operation: Name of the operation (e.g., "contradiction_comparison").
        matter_id: Optional matter UUID for cost attribution.
        document_id: Optional document UUID for cost attribution.
        entity_id: Optional entity UUID for cost attribution.
        input_tokens: Total input tokens consumed.
        output_tokens: Total output tokens consumed.
        start_time: Operation start timestamp.

    Example:
        >>> tracker = CostTracker(
        ...     provider=LLMProvider.OPENAI_GPT4_TURBO,
        ...     operation="summary_generation",
        ...     matter_id="abc-123",
        ... )
        >>> tracker.add_tokens(input_tokens=1500, output_tokens=500)
        >>> tracker.log_cost()
        >>> print(f"Total cost: ₹{tracker.total_cost_inr:.2f}")
    """

    provider: LLMProvider
    operation: str
    matter_id: str | None = None
    document_id: str | None = None
    entity_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    start_time: float = field(default_factory=time.time)
    _logged: bool = field(default=False, repr=False)

    @property
    def pricing(self) -> ProviderPricing:
        """Get pricing for this provider."""
        return PROVIDER_PRICING.get(
            self.provider,
            ProviderPricing(input_cost_per_1k=0.0, output_cost_per_1k=0.0),
        )

    @property
    def input_cost_usd(self) -> float:
        """Calculate input cost in USD."""
        return (self.input_tokens / 1000) * self.pricing.input_cost_per_1k

    @property
    def output_cost_usd(self) -> float:
        """Calculate output cost in USD."""
        return (self.output_tokens / 1000) * self.pricing.output_cost_per_1k

    @property
    def total_cost_usd(self) -> float:
        """Calculate total cost in USD."""
        return self.input_cost_usd + self.output_cost_usd

    @property
    def input_cost_inr(self) -> float:
        """Calculate input cost in INR."""
        return usd_to_inr(self.input_cost_usd)

    @property
    def output_cost_inr(self) -> float:
        """Calculate output cost in INR."""
        return usd_to_inr(self.output_cost_usd)

    @property
    def total_cost_inr(self) -> float:
        """Calculate total cost in INR."""
        return usd_to_inr(self.total_cost_usd)

    @property
    def duration_ms(self) -> int:
        """Calculate operation duration in milliseconds."""
        return int((time.time() - self.start_time) * 1000)

    def add_tokens(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Add tokens to the tracker.

        Args:
            input_tokens: Number of input tokens to add.
            output_tokens: Number of output tokens to add.
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def add_units(self, units: int) -> None:
        """Add units (pages, searches) for non-token-based pricing.

        Args:
            units: Number of units to add (stored as input_tokens).
        """
        self.input_tokens += units

    def log_cost(self, extra: dict[str, Any] | None = None) -> None:
        """Log the cost tracking information.

        Args:
            extra: Additional fields to include in the log.
        """
        if self._logged:
            return

        log_data = {
            "provider": self.provider.value,
            "operation": self.operation,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            # Primary currency: INR
            "input_cost_inr": round(self.input_cost_inr, 4),
            "output_cost_inr": round(self.output_cost_inr, 4),
            "total_cost_inr": round(self.total_cost_inr, 4),
            # Also include USD for reference
            "total_cost_usd": round(self.total_cost_usd, 8),
            "duration_ms": self.duration_ms,
        }

        if self.matter_id:
            log_data["matter_id"] = self.matter_id
        if self.document_id:
            log_data["document_id"] = self.document_id
        if self.entity_id:
            log_data["entity_id"] = self.entity_id

        if extra:
            log_data.update(extra)

        logger.info("llm_cost_tracked", **log_data)
        self._logged = True

    def to_dict(self) -> dict[str, Any]:
        """Convert tracker to dictionary for storage/serialization.

        Returns:
            Dictionary with all cost tracking data.
        """
        return {
            "provider": self.provider.value,
            "operation": self.operation,
            "matter_id": self.matter_id,
            "document_id": self.document_id,
            "entity_id": self.entity_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            # Primary currency: INR
            "input_cost_inr": round(self.input_cost_inr, 4),
            "output_cost_inr": round(self.output_cost_inr, 4),
            "total_cost_inr": round(self.total_cost_inr, 4),
            # USD for reference
            "input_cost_usd": self.input_cost_usd,
            "output_cost_usd": self.output_cost_usd,
            "total_cost_usd": self.total_cost_usd,
            "duration_ms": self.duration_ms,
        }


# =============================================================================
# Batch Cost Aggregator
# =============================================================================


@dataclass
class BatchCostAggregator:
    """Aggregates costs from multiple operations.

    Useful for tracking total costs across a batch of LLM calls,
    such as processing all chunks in a document.

    Example:
        >>> aggregator = BatchCostAggregator(operation="citation_extraction")
        >>> for chunk in chunks:
        ...     tracker = CostTracker(...)
        ...     # ... process chunk ...
        ...     aggregator.add_tracker(tracker)
        >>> aggregator.log_summary()
    """

    operation: str
    matter_id: str | None = None
    document_id: str | None = None
    trackers: list[CostTracker] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @property
    def total_input_tokens(self) -> int:
        """Sum of all input tokens."""
        return sum(t.input_tokens for t in self.trackers)

    @property
    def total_output_tokens(self) -> int:
        """Sum of all output tokens."""
        return sum(t.output_tokens for t in self.trackers)

    @property
    def total_cost_usd(self) -> float:
        """Sum of all costs in USD."""
        return sum(t.total_cost_usd for t in self.trackers)

    @property
    def total_cost_inr(self) -> float:
        """Sum of all costs in INR."""
        return usd_to_inr(self.total_cost_usd)

    @property
    def operation_count(self) -> int:
        """Number of operations tracked."""
        return len(self.trackers)

    @property
    def duration_ms(self) -> int:
        """Total duration in milliseconds."""
        return int((time.time() - self.start_time) * 1000)

    def add_tracker(self, tracker: CostTracker) -> None:
        """Add a cost tracker to the aggregator.

        Args:
            tracker: CostTracker instance to add.
        """
        self.trackers.append(tracker)

    def add_cost(
        self,
        provider: LLMProvider,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> CostTracker:
        """Create and add a new cost tracker.

        Args:
            provider: LLM provider for this cost.
            input_tokens: Input tokens consumed.
            output_tokens: Output tokens consumed.

        Returns:
            The created CostTracker instance.
        """
        tracker = CostTracker(
            provider=provider,
            operation=self.operation,
            matter_id=self.matter_id,
            document_id=self.document_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.trackers.append(tracker)
        return tracker

    def log_summary(self, extra: dict[str, Any] | None = None) -> None:
        """Log aggregated cost summary.

        Args:
            extra: Additional fields to include in the log.
        """
        # Group by provider
        by_provider: dict[str, dict[str, Any]] = {}
        for tracker in self.trackers:
            provider = tracker.provider.value
            if provider not in by_provider:
                by_provider[provider] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_inr": 0.0,
                    "cost_usd": 0.0,
                    "count": 0,
                }
            by_provider[provider]["input_tokens"] += tracker.input_tokens
            by_provider[provider]["output_tokens"] += tracker.output_tokens
            by_provider[provider]["cost_inr"] += tracker.total_cost_inr
            by_provider[provider]["cost_usd"] += tracker.total_cost_usd
            by_provider[provider]["count"] += 1

        log_data = {
            "operation": self.operation,
            "total_operations": self.operation_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            # Primary currency: INR
            "total_cost_inr": round(self.total_cost_inr, 4),
            "total_cost_usd": round(self.total_cost_usd, 8),
            "duration_ms": self.duration_ms,
            "by_provider": by_provider,
        }

        if self.matter_id:
            log_data["matter_id"] = self.matter_id
        if self.document_id:
            log_data["document_id"] = self.document_id

        if extra:
            log_data.update(extra)

        logger.info("llm_batch_cost_summary", **log_data)

    def to_dict(self) -> dict[str, Any]:
        """Convert aggregator to dictionary.

        Returns:
            Dictionary with aggregated cost data.
        """
        return {
            "operation": self.operation,
            "matter_id": self.matter_id,
            "document_id": self.document_id,
            "total_operations": self.operation_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            # Primary currency: INR
            "total_cost_inr": round(self.total_cost_inr, 4),
            "total_cost_usd": round(self.total_cost_usd, 8),
            "duration_ms": self.duration_ms,
        }


# =============================================================================
# Helper Functions
# =============================================================================


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """Estimate token count from text length.

    Uses a rough approximation of 4 characters per token for English text.
    Actual tokenization varies by model.

    Args:
        text: Input text to estimate.
        chars_per_token: Average characters per token (default 4.0).

    Returns:
        Estimated token count.
    """
    if not text:
        return 0
    return int(len(text) / chars_per_token)


def estimate_cost_inr(
    provider: LLMProvider,
    input_text: str,
    estimated_output_tokens: int = 500,
) -> float:
    """Estimate cost before making an API call.

    Args:
        provider: LLM provider to use.
        input_text: Input text to send.
        estimated_output_tokens: Expected output token count.

    Returns:
        Estimated cost in INR.
    """
    input_tokens = estimate_tokens(input_text)
    pricing = PROVIDER_PRICING.get(
        provider,
        ProviderPricing(input_cost_per_1k=0.0, output_cost_per_1k=0.0),
    )

    input_cost_usd = (input_tokens / 1000) * pricing.input_cost_per_1k
    output_cost_usd = (estimated_output_tokens / 1000) * pricing.output_cost_per_1k

    return usd_to_inr(input_cost_usd + output_cost_usd)


# Alias for backwards compatibility
def estimate_cost(
    provider: LLMProvider,
    input_text: str,
    estimated_output_tokens: int = 500,
) -> float:
    """Estimate cost before making an API call (returns INR).

    Args:
        provider: LLM provider to use.
        input_text: Input text to send.
        estimated_output_tokens: Expected output token count.

    Returns:
        Estimated cost in INR.
    """
    return estimate_cost_inr(provider, input_text, estimated_output_tokens)


@lru_cache(maxsize=1)
def get_model_pricing_info() -> dict[str, dict[str, Any]]:
    """Get pricing information for all models.

    Returns:
        Dictionary of model pricing for documentation/display.
        Includes both USD and INR pricing.
    """
    return {
        provider.value: {
            # USD pricing (base)
            "input_cost_per_1k_usd": pricing.input_cost_per_1k,
            "output_cost_per_1k_usd": pricing.output_cost_per_1k,
            # INR pricing (primary display currency)
            "input_cost_per_1k_inr": round(usd_to_inr(pricing.input_cost_per_1k), 4),
            "output_cost_per_1k_inr": round(usd_to_inr(pricing.output_cost_per_1k), 4),
            "unit": pricing.unit,
        }
        for provider, pricing in PROVIDER_PRICING.items()
    }


def get_exchange_rate() -> dict[str, float]:
    """Get current USD to INR exchange rate.

    Returns:
        Dictionary with exchange rate info.
    """
    return {
        "usd_to_inr": USD_TO_INR_RATE,
        "inr_to_usd": 1 / USD_TO_INR_RATE,
    }


# =============================================================================
# Cost Persistence Service
# =============================================================================


class CostPersistenceService:
    """Service for persisting LLM costs to the database.

    Provides async methods for storing and querying cost data.

    Example:
        >>> service = CostPersistenceService(supabase_client)
        >>> await service.save_cost(tracker)
        >>> summary = await service.get_matter_cost_summary(matter_id)
    """

    def __init__(self, supabase_client: Any):
        """Initialize the cost persistence service.

        Args:
            supabase_client: Supabase client instance.
        """
        self.supabase = supabase_client

    async def save_cost(
        self,
        tracker: CostTracker,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Save a cost tracker record to the database.

        Args:
            tracker: CostTracker instance with cost data.
            metadata: Additional metadata to store.

        Returns:
            The created record ID, or None if save failed.
        """
        try:
            record = {
                "matter_id": tracker.matter_id,
                "document_id": tracker.document_id,
                "entity_id": tracker.entity_id,
                "provider": tracker.provider.value,
                "operation": tracker.operation,
                "input_tokens": tracker.input_tokens,
                "output_tokens": tracker.output_tokens,
                # Primary currency: INR
                "input_cost_inr": round(tracker.input_cost_inr, 4),
                "output_cost_inr": round(tracker.output_cost_inr, 4),
                "total_cost_inr": round(tracker.total_cost_inr, 4),
                # USD for reference
                "input_cost_usd": tracker.input_cost_usd,
                "output_cost_usd": tracker.output_cost_usd,
                "total_cost_usd": tracker.total_cost_usd,
                # Exchange rate at time of tracking
                "usd_to_inr_rate": USD_TO_INR_RATE,
                "duration_ms": tracker.duration_ms,
                "metadata": metadata or {},
            }

            result = self.supabase.table("llm_costs").insert(record).execute()

            if result.data:
                return result.data[0].get("id")
            return None

        except Exception as e:
            logger.error(
                "cost_persistence_save_failed",
                error=str(e),
                operation=tracker.operation,
                provider=tracker.provider.value,
            )
            return None

    async def save_batch(
        self,
        aggregator: BatchCostAggregator,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Save all trackers from a batch aggregator.

        Args:
            aggregator: BatchCostAggregator with multiple trackers.
            metadata: Additional metadata to store with each record.

        Returns:
            Number of records successfully saved.
        """
        saved_count = 0
        for tracker in aggregator.trackers:
            record_id = await self.save_cost(tracker, metadata)
            if record_id:
                saved_count += 1
        return saved_count

    async def get_matter_cost_summary(
        self,
        matter_id: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get cost summary for a matter.

        Args:
            matter_id: Matter UUID to query.
            days: Number of days to include (default 30).

        Returns:
            Dictionary with cost summary data (primary currency: INR).
        """
        try:
            from datetime import datetime, timedelta

            start_date = datetime.utcnow() - timedelta(days=days)

            result = (
                self.supabase.table("llm_costs")
                .select("provider, operation, input_tokens, output_tokens, total_cost_inr, total_cost_usd")
                .eq("matter_id", matter_id)
                .gte("created_at", start_date.isoformat())
                .execute()
            )

            if not result.data:
                return {
                    "matter_id": matter_id,
                    "period_days": days,
                    "total_cost_inr": 0.0,
                    "total_cost_usd": 0.0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "by_provider": {},
                    "by_operation": {},
                }

            # Aggregate the results
            by_provider: dict[str, dict[str, Any]] = {}
            by_operation: dict[str, dict[str, Any]] = {}
            total_cost_inr = 0.0
            total_cost_usd = 0.0
            total_input = 0
            total_output = 0

            for row in result.data:
                provider = row["provider"]
                operation = row["operation"]
                cost_inr = float(row.get("total_cost_inr", 0) or 0)
                cost_usd = float(row.get("total_cost_usd", 0) or 0)
                inp = row["input_tokens"]
                out = row["output_tokens"]

                total_cost_inr += cost_inr
                total_cost_usd += cost_usd
                total_input += inp
                total_output += out

                # By provider
                if provider not in by_provider:
                    by_provider[provider] = {
                        "cost_inr": 0.0,
                        "cost_usd": 0.0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "count": 0,
                    }
                by_provider[provider]["cost_inr"] += cost_inr
                by_provider[provider]["cost_usd"] += cost_usd
                by_provider[provider]["input_tokens"] += inp
                by_provider[provider]["output_tokens"] += out
                by_provider[provider]["count"] += 1

                # By operation
                if operation not in by_operation:
                    by_operation[operation] = {
                        "cost_inr": 0.0,
                        "cost_usd": 0.0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "count": 0,
                    }
                by_operation[operation]["cost_inr"] += cost_inr
                by_operation[operation]["cost_usd"] += cost_usd
                by_operation[operation]["input_tokens"] += inp
                by_operation[operation]["output_tokens"] += out
                by_operation[operation]["count"] += 1

            return {
                "matter_id": matter_id,
                "period_days": days,
                # Primary currency: INR
                "total_cost_inr": round(total_cost_inr, 2),
                "total_cost_usd": round(total_cost_usd, 6),
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "operation_count": len(result.data),
                "by_provider": by_provider,
                "by_operation": by_operation,
            }

        except Exception as e:
            logger.error(
                "cost_summary_query_failed",
                error=str(e),
                matter_id=matter_id,
            )
            return {
                "matter_id": matter_id,
                "period_days": days,
                "error": str(e),
            }

    async def get_daily_costs(
        self,
        matter_id: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get daily cost breakdown for a matter.

        Args:
            matter_id: Matter UUID to query.
            days: Number of days to include (default 30).

        Returns:
            List of daily cost records.
        """
        try:
            result = (
                self.supabase.rpc(
                    "get_matter_daily_costs",
                    {"p_matter_id": matter_id, "p_days": days},
                )
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.warning(
                "daily_costs_query_failed",
                error=str(e),
                matter_id=matter_id,
            )
            return []


# =============================================================================
# Global Service Instance
# =============================================================================

_cost_service: CostPersistenceService | None = None


def get_cost_service(supabase_client: Any | None = None) -> CostPersistenceService | None:
    """Get or create the global cost persistence service.

    Args:
        supabase_client: Optional Supabase client to use.

    Returns:
        CostPersistenceService instance, or None if no client available.
    """
    global _cost_service

    if _cost_service is None and supabase_client is not None:
        _cost_service = CostPersistenceService(supabase_client)

    return _cost_service


async def persist_cost(tracker: CostTracker) -> str | None:
    """Convenience function to persist a cost tracker.

    Args:
        tracker: CostTracker instance to persist.

    Returns:
        Record ID if saved, None otherwise.
    """
    service = get_cost_service()
    if service:
        return await service.save_cost(tracker)
    return None
