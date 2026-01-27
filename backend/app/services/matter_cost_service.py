"""Matter Cost Service for per-matter cost tracking.

Story 7.1: Per-Matter Cost Tracking Widget

Provides cost aggregation and summary functionality for individual matters.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import structlog

from app.models.cost import (
    CostByOperation,
    CostByProvider,
    DailyCost,
    MatterCostSummary,
)
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


class MatterCostService:
    """Service for retrieving and aggregating matter-level costs.

    Story 7.1 AC:
    - Total LLM cost for this matter
    - Costs broken down by: embedding, analysis, Q&A
    - Daily and weekly rollups available
    """

    def __init__(self, supabase_client: Any):
        """Initialize the matter cost service.

        Args:
            supabase_client: Supabase client instance.
        """
        self.supabase = supabase_client

    def get_matter_cost_summary(
        self,
        matter_id: str,
        days: int = 30,
    ) -> MatterCostSummary:
        """Get cost summary for a specific matter.

        Note: This method is synchronous because the Supabase client
        uses synchronous HTTP calls. The API endpoint wraps this in
        run_in_executor if needed for async compatibility.

        Args:
            matter_id: Matter UUID to query.
            days: Number of days to include (default 30).

        Returns:
            MatterCostSummary with aggregated cost data.
        """
        logger.info("fetching_matter_costs", matter_id=matter_id, days=days)

        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # Fetch all cost records for this matter in the period
        result = (
            self.supabase.table("llm_costs")
            .select(
                "provider, operation, input_tokens, output_tokens, "
                "total_cost_inr, total_cost_usd, created_at"
            )
            .eq("matter_id", matter_id)
            .gte("created_at", start_date.isoformat())
            .execute()
        )

        records = result.data or []

        if not records:
            logger.debug("no_costs_found", matter_id=matter_id)
            return MatterCostSummary(
                matter_id=matter_id,
                period_days=days,
                total_cost_inr=0.0,
                total_cost_usd=0.0,
                total_input_tokens=0,
                total_output_tokens=0,
                operation_count=0,
                by_operation=[],
                by_provider=[],
                daily_costs=[],
                weekly_cost_inr=0.0,
                weekly_cost_usd=0.0,
            )

        # Aggregate totals
        total_cost_inr = 0.0
        total_cost_usd = 0.0
        total_input_tokens = 0
        total_output_tokens = 0

        # Aggregation dictionaries
        by_operation: dict[str, dict[str, Any]] = {}
        by_provider: dict[str, dict[str, Any]] = {}
        by_date: dict[str, dict[str, float]] = {}
        weekly_cost_inr = 0.0
        weekly_cost_usd = 0.0

        for row in records:
            cost_inr = float(row.get("total_cost_inr") or 0)
            cost_usd = float(row.get("total_cost_usd") or 0)
            input_tok = row.get("input_tokens") or 0
            output_tok = row.get("output_tokens") or 0
            operation = self._normalize_operation(row.get("operation", "unknown"))
            provider = row.get("provider", "unknown")
            created_at = row.get("created_at", "")

            # Totals
            total_cost_inr += cost_inr
            total_cost_usd += cost_usd
            total_input_tokens += input_tok
            total_output_tokens += output_tok

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
            by_operation[operation]["input_tokens"] += input_tok
            by_operation[operation]["output_tokens"] += output_tok
            by_operation[operation]["count"] += 1

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
            by_provider[provider]["input_tokens"] += input_tok
            by_provider[provider]["output_tokens"] += output_tok
            by_provider[provider]["count"] += 1

            # By date (for last 7 days only)
            if created_at:
                record_date = created_at[:10]  # YYYY-MM-DD
                if record_date not in by_date:
                    by_date[record_date] = {"cost_inr": 0.0, "cost_usd": 0.0}
                by_date[record_date]["cost_inr"] += cost_inr
                by_date[record_date]["cost_usd"] += cost_usd

                # Weekly totals
                try:
                    record_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if record_dt >= seven_days_ago:
                        weekly_cost_inr += cost_inr
                        weekly_cost_usd += cost_usd
                except (ValueError, TypeError):
                    pass

        # Build response models
        operation_list = [
            CostByOperation(
                operation=op,
                cost_inr=round(data["cost_inr"], 2),
                cost_usd=round(data["cost_usd"], 6),
                input_tokens=data["input_tokens"],
                output_tokens=data["output_tokens"],
                operation_count=data["count"],
            )
            for op, data in sorted(
                by_operation.items(), key=lambda x: x[1]["cost_inr"], reverse=True
            )
        ]

        provider_list = [
            CostByProvider(
                provider=prov,
                cost_inr=round(data["cost_inr"], 2),
                cost_usd=round(data["cost_usd"], 6),
                input_tokens=data["input_tokens"],
                output_tokens=data["output_tokens"],
                operation_count=data["count"],
            )
            for prov, data in sorted(
                by_provider.items(), key=lambda x: x[1]["cost_inr"], reverse=True
            )
        ]

        # Daily costs (last 7 days only, sorted by date)
        seven_day_dates = sorted(by_date.keys(), reverse=True)[:7]
        daily_list = [
            DailyCost(
                date=date,
                cost_inr=round(by_date[date]["cost_inr"], 2),
                cost_usd=round(by_date[date]["cost_usd"], 6),
            )
            for date in seven_day_dates
        ]

        logger.info(
            "matter_costs_aggregated",
            matter_id=matter_id,
            total_cost_inr=round(total_cost_inr, 2),
            operation_count=len(records),
            providers=list(by_provider.keys()),
        )

        return MatterCostSummary(
            matter_id=matter_id,
            period_days=days,
            total_cost_inr=round(total_cost_inr, 2),
            total_cost_usd=round(total_cost_usd, 6),
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            operation_count=len(records),
            by_operation=operation_list,
            by_provider=provider_list,
            daily_costs=daily_list,
            weekly_cost_inr=round(weekly_cost_inr, 2),
            weekly_cost_usd=round(weekly_cost_usd, 6),
        )

    def _normalize_operation(self, operation: str) -> str:
        """Normalize operation names for display.

        Groups similar operations into user-friendly categories.

        Args:
            operation: Raw operation name from database.

        Returns:
            Normalized operation name.
        """
        op_lower = operation.lower()

        # Embedding operations
        if "embed" in op_lower:
            return "Embedding"

        # Q&A and chat operations
        if any(x in op_lower for x in ["qa", "chat", "rag", "query"]):
            return "Q&A"

        # Citation extraction
        if "citation" in op_lower:
            return "Citations"

        # Entity extraction
        if "entity" in op_lower or "ner" in op_lower:
            return "Entities"

        # Contradiction detection
        if "contradiction" in op_lower:
            return "Contradictions"

        # Timeline extraction
        if "timeline" in op_lower or "event" in op_lower:
            return "Timeline"

        # Summary generation
        if "summar" in op_lower:
            return "Summary"

        # OCR and document processing
        if any(x in op_lower for x in ["ocr", "document_ai"]):
            return "OCR"

        # Default: capitalize first letter
        return operation.replace("_", " ").title()


# =============================================================================
# Dependency Injection
# =============================================================================


@lru_cache(maxsize=1)
def get_matter_cost_service() -> MatterCostService:
    """Get or create the matter cost service.

    Uses lru_cache for thread-safe singleton pattern.
    The cache can be cleared for testing via get_matter_cost_service.cache_clear().

    Returns:
        MatterCostService instance.
    """
    supabase = get_service_client()
    return MatterCostService(supabase)
