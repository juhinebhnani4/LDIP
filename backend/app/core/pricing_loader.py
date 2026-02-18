"""DB-backed LLM pricing loader with hardcoded fallback.

Priority 3: Replaces hardcoded PROVIDER_PRICING dict with Supabase-backed
pricing that can be updated without code deploys.

Usage:
    # At startup (main.py / celery.py):
    from app.core.pricing_loader import initialize_pricing
    initialize_pricing(supabase)

    # In cost calculations:
    from app.core.pricing_loader import get_pricing
    pricing = get_pricing("gpt-4o")  # or get_pricing(LLMProvider.OPENAI_GPT4O)
"""

from typing import Any

import structlog

from app.core.cost_tracking import PROVIDER_PRICING, ProviderPricing

logger = structlog.get_logger(__name__)

# Module-level state
_db_pricing: dict[str, ProviderPricing] | None = None
_supabase_client: Any = None


def load_pricing_from_db(supabase: Any) -> dict[str, ProviderPricing]:
    """Load active pricing from llm_pricing table.

    Args:
        supabase: Supabase client instance.

    Returns:
        Dictionary keyed by provider string with ProviderPricing values.
    """
    result = (
        supabase.table("llm_pricing")
        .select("provider, input_cost_per_1k, output_cost_per_1k, unit")
        .is_("effective_to", "null")
        .execute()
    )

    pricing = {}
    for row in result.data or []:
        pricing[row["provider"]] = ProviderPricing(
            input_cost_per_1k=float(row["input_cost_per_1k"]),
            output_cost_per_1k=float(row["output_cost_per_1k"]),
            unit=row.get("unit", "tokens"),
        )

    logger.info("pricing_loaded_from_db", provider_count=len(pricing))
    return pricing


def initialize_pricing(supabase: Any) -> None:
    """Initialize DB-backed pricing at startup.

    Called from main.py lifespan and celery.py worker_ready signal.
    Falls back to hardcoded PROVIDER_PRICING if DB load fails.

    Args:
        supabase: Supabase client instance.
    """
    global _db_pricing, _supabase_client
    _supabase_client = supabase

    try:
        _db_pricing = load_pricing_from_db(supabase)
        logger.info(
            "pricing_loader_initialized",
            source="database",
            provider_count=len(_db_pricing),
        )
    except Exception as e:
        logger.warning(
            "pricing_loader_db_failed",
            error=str(e),
            hint="Falling back to hardcoded PROVIDER_PRICING",
        )
        _db_pricing = None


def get_provider_pricing() -> dict[str, ProviderPricing]:
    """Get all provider pricing (DB-backed or hardcoded fallback).

    Returns:
        Dictionary keyed by provider string with ProviderPricing values.
    """
    if _db_pricing is not None:
        return _db_pricing

    # Fallback: convert LLMProvider enum keys to string keys
    return {provider.value: pricing for provider, pricing in PROVIDER_PRICING.items()}


def get_pricing(provider: Any) -> ProviderPricing:
    """Get pricing for a single provider.

    Args:
        provider: LLMProvider enum or provider string (e.g. "gpt-4o").

    Returns:
        ProviderPricing for the provider, or zero-cost default if not found.
    """
    key = provider.value if hasattr(provider, "value") else str(provider)
    return get_provider_pricing().get(
        key,
        ProviderPricing(input_cost_per_1k=0.0, output_cost_per_1k=0.0),
    )


def refresh_pricing() -> None:
    """Reload pricing from DB and clear LRU caches.

    Call after updating prices in llm_pricing table.
    """
    global _db_pricing

    if _supabase_client is not None:
        try:
            _db_pricing = load_pricing_from_db(_supabase_client)

            # Clear the get_model_pricing_info LRU cache so it picks up new prices
            from app.core.cost_tracking import get_model_pricing_info
            get_model_pricing_info.cache_clear()

            logger.info("pricing_refreshed", provider_count=len(_db_pricing))
        except Exception as e:
            logger.error("pricing_refresh_failed", error=str(e))
    else:
        logger.warning("pricing_refresh_skipped", reason="no_supabase_client")
