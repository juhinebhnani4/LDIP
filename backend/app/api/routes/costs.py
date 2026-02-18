"""Cost Comparison API for A/B Testing Provider Analysis.

Provides cost comparison data between OpenAI vs Voyage embeddings
and Cohere vs Voyage reranking for informed decision-making.

Endpoints:
- GET /api/costs/comparison - Provider cost comparison with savings
"""

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.rate_limit import READONLY_RATE_LIMIT, limiter
from app.core.security import get_current_user
from app.models.auth import AuthenticatedUser
from app.services.supabase.client import get_supabase_client

router = APIRouter(prefix="/costs", tags=["costs"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Response Models
# =============================================================================


class ProviderCostStats(BaseModel):
    """Cost stats for a single provider."""

    model_config = ConfigDict(populate_by_name=True)

    total_inr: float = Field(0.0, alias="totalInr")
    total_usd: float = Field(0.0, alias="totalUsd")
    query_count: int = Field(0, alias="queryCount")
    avg_cost_per_query_inr: float = Field(0.0, alias="avgCostPerQueryInr")


class CategoryComparison(BaseModel):
    """Side-by-side comparison for one cost category."""

    model_config = ConfigDict(populate_by_name=True)

    openai: ProviderCostStats | None = None
    voyage: ProviderCostStats | None = None
    cohere: ProviderCostStats | None = None


class Savings(BaseModel):
    """Calculated savings from using Voyage vs incumbent providers."""

    model_config = ConfigDict(populate_by_name=True)

    embedding_inr: float = Field(0.0, alias="embeddingInr")
    reranking_inr: float = Field(0.0, alias="rerankingInr")
    total_inr: float = Field(0.0, alias="totalInr")


class CostComparisonData(BaseModel):
    """Full cost comparison response data."""

    model_config = ConfigDict(populate_by_name=True)

    embedding: CategoryComparison = Field(default_factory=CategoryComparison)
    reranking: CategoryComparison = Field(default_factory=CategoryComparison)
    savings: Savings = Field(default_factory=Savings)
    period_days: int = Field(30, alias="periodDays")


class CostComparisonResponse(BaseModel):
    """API response wrapper."""

    data: CostComparisonData


# =============================================================================
# Provider name mappings
# =============================================================================

EMBEDDING_PROVIDERS = {
    "openai": ["text-embedding-3-small"],
    "voyage": ["voyage-law-2"],
}

RERANKING_PROVIDERS = {
    "cohere": ["cohere-rerank-v3.5", "rerank-english-v3.0"],
    "voyage": ["voyage-rerank-2.5"],
}


# =============================================================================
# Endpoint
# =============================================================================


@router.get(
    "/comparison",
    response_model=CostComparisonResponse,
    response_model_by_alias=True,
    summary="Get Cost Comparison",
    description="Compare costs between OpenAI vs Voyage embeddings and Cohere vs Voyage reranking.",
)
@limiter.limit(READONLY_RATE_LIMIT)
async def get_cost_comparison(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    matter_id: str | None = Query(default=None, description="Filter by matter ID"),
) -> CostComparisonResponse:
    """Get cost comparison between providers for A/B testing analysis."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error": {"code": "SERVICE_UNAVAILABLE", "message": "Database not configured"}},
            )

        since = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()

        # Build query for all embedding + reranking providers
        all_provider_names = []
        for names in EMBEDDING_PROVIDERS.values():
            all_provider_names.extend(names)
        for names in RERANKING_PROVIDERS.values():
            all_provider_names.extend(names)

        query = (
            supabase.table("llm_costs")
            .select("provider, total_cost_inr, total_cost_usd")
            .in_("provider", all_provider_names)
            .gte("created_at", since)
        )

        if matter_id:
            query = query.eq("matter_id", matter_id)

        result = await asyncio.to_thread(lambda: query.execute())

        if not result.data:
            return CostComparisonResponse(data=CostComparisonData(period_days=days))

        # Aggregate costs per provider
        aggregated: dict[str, dict] = {}
        for row in result.data:
            prov = row["provider"]
            if prov not in aggregated:
                aggregated[prov] = {"total_inr": 0.0, "total_usd": 0.0, "count": 0}
            aggregated[prov]["total_inr"] += float(row.get("total_cost_inr") or 0)
            aggregated[prov]["total_usd"] += float(row.get("total_cost_usd") or 0)
            aggregated[prov]["count"] += 1

        def _stats(provider_names: list[str]) -> ProviderCostStats:
            total_inr = 0.0
            total_usd = 0.0
            count = 0
            for name in provider_names:
                if name in aggregated:
                    total_inr += aggregated[name]["total_inr"]
                    total_usd += aggregated[name]["total_usd"]
                    count += aggregated[name]["count"]
            return ProviderCostStats(
                total_inr=round(total_inr, 4),
                total_usd=round(total_usd, 8),
                query_count=count,
                avg_cost_per_query_inr=round(total_inr / count, 4) if count > 0 else 0.0,
            )

        # Build comparison
        openai_embed = _stats(EMBEDDING_PROVIDERS["openai"])
        voyage_embed = _stats(EMBEDDING_PROVIDERS["voyage"])
        cohere_rerank = _stats(RERANKING_PROVIDERS["cohere"])
        voyage_rerank = _stats(RERANKING_PROVIDERS["voyage"])

        # Calculate savings (positive = Voyage is cheaper)
        embed_savings = openai_embed.total_inr - voyage_embed.total_inr
        rerank_savings = cohere_rerank.total_inr - voyage_rerank.total_inr

        comparison = CostComparisonData(
            embedding=CategoryComparison(openai=openai_embed, voyage=voyage_embed),
            reranking=CategoryComparison(cohere=cohere_rerank, voyage=voyage_rerank),
            savings=Savings(
                embedding_inr=round(embed_savings, 4),
                reranking_inr=round(rerank_savings, 4),
                total_inr=round(embed_savings + rerank_savings, 4),
            ),
            period_days=days,
        )

        logger.debug(
            "cost_comparison_computed",
            user_id=current_user.id,
            period_days=days,
            matter_id=matter_id,
        )

        return CostComparisonResponse(data=comparison)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "cost_comparison_failed",
            user_id=current_user.id,
            error=str(e),
        )
        return CostComparisonResponse(data=CostComparisonData(period_days=days))
