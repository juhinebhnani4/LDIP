"""Pydantic models for per-matter cost tracking.

Story 7.1: Per-Matter Cost Tracking Widget

Provides response models for matter cost API endpoints.
"""

from pydantic import BaseModel, Field


class CostByOperation(BaseModel):
    """Cost breakdown by operation type."""

    operation: str = Field(
        ..., description="Operation type (e.g., embedding, analysis, qa)"
    )
    cost_inr: float = Field(..., alias="costInr", description="Total cost in INR")
    cost_usd: float = Field(
        ..., alias="costUsd", description="Total cost in USD for reference"
    )
    input_tokens: int = Field(
        ..., alias="inputTokens", description="Total input tokens"
    )
    output_tokens: int = Field(
        ..., alias="outputTokens", description="Total output tokens"
    )
    operation_count: int = Field(
        ..., alias="operationCount", description="Number of operations"
    )

    model_config = {
        "populate_by_name": True,
    }


class CostByProvider(BaseModel):
    """Cost breakdown by LLM provider."""

    provider: str = Field(..., description="Provider identifier (e.g., gpt-4, gemini)")
    cost_inr: float = Field(..., alias="costInr", description="Total cost in INR")
    cost_usd: float = Field(
        ..., alias="costUsd", description="Total cost in USD for reference"
    )
    input_tokens: int = Field(
        ..., alias="inputTokens", description="Total input tokens"
    )
    output_tokens: int = Field(
        ..., alias="outputTokens", description="Total output tokens"
    )
    operation_count: int = Field(
        ..., alias="operationCount", description="Number of operations"
    )

    model_config = {
        "populate_by_name": True,
    }


class DailyCost(BaseModel):
    """Daily cost entry for time-series display."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    cost_inr: float = Field(
        ..., alias="costInr", description="Cost for this day in INR"
    )
    cost_usd: float = Field(
        ..., alias="costUsd", description="Cost for this day in USD"
    )

    model_config = {
        "populate_by_name": True,
    }


class MatterCostSummary(BaseModel):
    """Complete cost summary for a matter.

    Story 7.1 AC:
    - Total LLM cost for the matter
    - Costs broken down by: embedding, analysis, Q&A
    - Daily and weekly rollups available
    """

    matter_id: str = Field(..., alias="matterId", description="Matter UUID")
    period_days: int = Field(
        default=30, alias="periodDays", description="Number of days in the period"
    )
    total_cost_inr: float = Field(
        ..., alias="totalCostInr", description="Total cost in INR"
    )
    total_cost_usd: float = Field(
        ..., alias="totalCostUsd", description="Total cost in USD"
    )
    total_input_tokens: int = Field(
        default=0, alias="totalInputTokens", description="Total input tokens"
    )
    total_output_tokens: int = Field(
        default=0, alias="totalOutputTokens", description="Total output tokens"
    )
    operation_count: int = Field(
        default=0, alias="operationCount", description="Total number of LLM operations"
    )
    by_operation: list[CostByOperation] = Field(
        default_factory=list,
        alias="byOperation",
        description="Cost breakdown by operation type",
    )
    by_provider: list[CostByProvider] = Field(
        default_factory=list,
        alias="byProvider",
        description="Cost breakdown by LLM provider",
    )
    daily_costs: list[DailyCost] = Field(
        default_factory=list,
        alias="dailyCosts",
        description="Daily cost breakdown (last 7 days)",
    )
    weekly_cost_inr: float = Field(
        default=0.0,
        alias="weeklyCostInr",
        description="Total cost for the last 7 days in INR",
    )
    weekly_cost_usd: float = Field(
        default=0.0,
        alias="weeklyCostUsd",
        description="Total cost for the last 7 days in USD",
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "matterId": "550e8400-e29b-41d4-a716-446655440000",
                "periodDays": 30,
                "totalCostInr": 1250.50,
                "totalCostUsd": 14.97,
                "totalInputTokens": 500000,
                "totalOutputTokens": 125000,
                "operationCount": 150,
                "byOperation": [
                    {
                        "operation": "embedding",
                        "costInr": 250.00,
                        "costUsd": 2.99,
                        "inputTokens": 400000,
                        "outputTokens": 0,
                        "operationCount": 50,
                    },
                    {
                        "operation": "qa_generation",
                        "costInr": 750.50,
                        "costUsd": 8.99,
                        "inputTokens": 80000,
                        "outputTokens": 100000,
                        "operationCount": 75,
                    },
                ],
                "byProvider": [
                    {
                        "provider": "gpt-4o",
                        "costInr": 800.00,
                        "costUsd": 9.58,
                        "inputTokens": 50000,
                        "outputTokens": 100000,
                        "operationCount": 50,
                    },
                    {
                        "provider": "gemini-2.5-flash",
                        "costInr": 450.50,
                        "costUsd": 5.39,
                        "inputTokens": 450000,
                        "outputTokens": 25000,
                        "operationCount": 100,
                    },
                ],
                "dailyCosts": [
                    {"date": "2026-01-27", "costInr": 125.50, "costUsd": 1.50},
                    {"date": "2026-01-26", "costInr": 200.00, "costUsd": 2.40},
                ],
                "weeklyCostInr": 850.00,
                "weeklyCostUsd": 10.18,
            }
        },
    }


class MatterCostResponse(BaseModel):
    """API response wrapper for matter cost endpoint."""

    data: MatterCostSummary

    model_config = {
        "populate_by_name": True,
    }


# =============================================================================
# Admin Cost Report Models (Story 7.2)
# =============================================================================


class PracticeGroupCost(BaseModel):
    """Cost summary for a single practice group."""

    practice_group: str = Field(
        ..., alias="practiceGroup", description="Practice group name"
    )
    matter_count: int = Field(
        ..., alias="matterCount", description="Number of matters in this group"
    )
    document_count: int = Field(
        ..., alias="documentCount", description="Total documents processed"
    )
    total_cost_inr: float = Field(
        ..., alias="totalCostInr", description="Total cost in INR"
    )
    total_cost_usd: float = Field(
        ..., alias="totalCostUsd", description="Total cost in USD"
    )

    model_config = {
        "populate_by_name": True,
    }


class MonthlyCostReport(BaseModel):
    """Monthly cost report by practice group.

    Story 7.2 AC:
    - Report showing costs by practice group
    - Includes: matter count, document count, total cost per group
    - Exportable as CSV or PDF
    """

    report_month: str = Field(
        ..., alias="reportMonth", description="Report month in YYYY-MM format"
    )
    generated_at: str = Field(
        ..., alias="generatedAt", description="ISO timestamp of report generation"
    )
    total_cost_inr: float = Field(
        ..., alias="totalCostInr", description="Total cost across all groups in INR"
    )
    total_cost_usd: float = Field(
        ..., alias="totalCostUsd", description="Total cost across all groups in USD"
    )
    practice_groups: list[PracticeGroupCost] = Field(
        default_factory=list,
        alias="practiceGroups",
        description="Cost breakdown by practice group",
    )

    model_config = {
        "populate_by_name": True,
    }


class MonthlyCostReportResponse(BaseModel):
    """API response wrapper for monthly cost report."""

    data: MonthlyCostReport

    model_config = {
        "populate_by_name": True,
    }


# =============================================================================
# Usage Dashboard Models (Full Cost Tracking)
# =============================================================================


class DailyUsage(BaseModel):
    """Daily spend entry for time-series chart."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    spend_usd: float = Field(..., alias="spendUsd", description="Spend in USD")
    spend_inr: float = Field(..., alias="spendInr", description="Spend in INR")
    requests: int = Field(default=0, description="Number of API requests")
    tokens: int = Field(default=0, description="Total tokens used")

    model_config = {"populate_by_name": True}


class ProviderUsage(BaseModel):
    """Usage breakdown by provider."""

    provider: str = Field(..., description="Provider model name")
    spend_usd: float = Field(..., alias="spendUsd")
    spend_inr: float = Field(..., alias="spendInr")
    requests: int = Field(default=0)
    input_tokens: int = Field(default=0, alias="inputTokens")
    output_tokens: int = Field(default=0, alias="outputTokens")

    model_config = {"populate_by_name": True}


class OperationUsage(BaseModel):
    """Usage breakdown by operation type."""

    operation: str = Field(..., description="Operation name")
    spend_usd: float = Field(..., alias="spendUsd")
    spend_inr: float = Field(..., alias="spendInr")
    requests: int = Field(default=0)
    input_tokens: int = Field(default=0, alias="inputTokens")
    output_tokens: int = Field(default=0, alias="outputTokens")

    model_config = {"populate_by_name": True}


class MatterUsage(BaseModel):
    """Usage breakdown by matter."""

    matter_id: str = Field(..., alias="matterId")
    spend_usd: float = Field(..., alias="spendUsd")
    spend_inr: float = Field(..., alias="spendInr")
    requests: int = Field(default=0)

    model_config = {"populate_by_name": True}


class UsageDashboardResponse(BaseModel):
    """Full usage dashboard response (OpenAI-style)."""

    month: str = Field(..., description="Month in YYYY-MM format")
    total_spend_usd: float = Field(..., alias="totalSpendUsd")
    total_spend_inr: float = Field(..., alias="totalSpendInr")
    budget_usd: float = Field(..., alias="budgetUsd")
    total_tokens: int = Field(default=0, alias="totalTokens")
    total_requests: int = Field(default=0, alias="totalRequests")
    daily_spend: list[DailyUsage] = Field(default_factory=list, alias="dailySpend")
    by_provider: list[ProviderUsage] = Field(default_factory=list, alias="byProvider")
    by_operation: list[OperationUsage] = Field(
        default_factory=list, alias="byOperation"
    )
    by_matter: list[MatterUsage] = Field(default_factory=list, alias="byMatter")

    model_config = {"populate_by_name": True}
