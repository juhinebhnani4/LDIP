"""Pydantic models for LLM quota monitoring.

Story gap-5.2: LLM Quota Monitoring Dashboard

Provides response models for the quota monitoring API endpoints.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ProviderQuota(BaseModel):
    """Quota information for a single LLM provider."""

    provider: str = Field(..., description="Provider identifier (gemini, openai)")
    current_rpm: int = Field(
        default=0, description="Current requests per minute (session)", alias="currentRpm"
    )
    rpm_limit: int = Field(default=0, description="Configured RPM limit", alias="rpmLimit")
    rpm_usage_pct: float = Field(
        default=0.0, description="RPM usage percentage", alias="rpmUsagePct"
    )
    daily_tokens_used: int = Field(
        default=0, description="Tokens used today", alias="dailyTokensUsed"
    )
    daily_token_limit: int | None = Field(
        default=None, description="Daily token limit (null = unlimited)", alias="dailyTokenLimit"
    )
    daily_cost_inr: float = Field(
        default=0.0, description="Cost today in INR", alias="dailyCostInr"
    )
    daily_cost_limit_inr: float | None = Field(
        default=None, description="Daily cost limit in INR", alias="dailyCostLimitInr"
    )
    rate_limited_count: int = Field(
        default=0, description="Times rate limited this session", alias="rateLimitedCount"
    )
    projected_exhaustion: str | None = Field(
        default=None,
        description="ISO date of projected exhaustion based on 7-day trend",
        alias="projectedExhaustion",
    )
    trend: Literal["increasing", "decreasing", "stable"] = Field(
        default="stable", description="Usage trend direction"
    )
    alert_triggered: bool = Field(
        default=False, description="True if usage >= alert threshold", alias="alertTriggered"
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "provider": "gemini",
                "currentRpm": 15,
                "rpmLimit": 60,
                "rpmUsagePct": 25.0,
                "dailyTokensUsed": 500000,
                "dailyTokenLimit": 1000000,
                "dailyCostInr": 250.50,
                "dailyCostLimitInr": 500.00,
                "rateLimitedCount": 0,
                "projectedExhaustion": "2026-02-15",
                "trend": "stable",
                "alertTriggered": False,
            }
        },
    }


class LLMQuotaData(BaseModel):
    """Aggregated LLM quota data for all providers."""

    providers: list[ProviderQuota] = Field(
        default_factory=list, description="Quota info for each provider"
    )
    last_updated: str = Field(
        ..., description="ISO timestamp of data collection", alias="lastUpdated"
    )
    alert_threshold_pct: int = Field(
        default=80, description="Default alert threshold percentage", alias="alertThresholdPct"
    )
    usd_to_inr_rate: float = Field(
        default=83.50, description="Current USD to INR exchange rate", alias="usdToInrRate"
    )

    model_config = {
        "populate_by_name": True,
    }


class LLMQuotaResponse(BaseModel):
    """API response for LLM quota monitoring endpoint."""

    data: LLMQuotaData

    model_config = {
        "json_schema_extra": {
            "example": {
                "data": {
                    "providers": [
                        {
                            "provider": "gemini",
                            "currentRpm": 15,
                            "rpmLimit": 60,
                            "rpmUsagePct": 25.0,
                            "dailyTokensUsed": 500000,
                            "dailyTokenLimit": 1000000,
                            "dailyCostInr": 250.50,
                            "dailyCostLimitInr": 500.00,
                            "rateLimitedCount": 0,
                            "projectedExhaustion": "2026-02-15",
                            "trend": "stable",
                            "alertTriggered": False,
                        },
                        {
                            "provider": "openai",
                            "currentRpm": 5,
                            "rpmLimit": 500,
                            "rpmUsagePct": 1.0,
                            "dailyTokensUsed": 100000,
                            "dailyTokenLimit": 500000,
                            "dailyCostInr": 1500.00,
                            "dailyCostLimitInr": 2500.00,
                            "rateLimitedCount": 0,
                            "projectedExhaustion": None,
                            "trend": "decreasing",
                            "alertTriggered": False,
                        },
                    ],
                    "lastUpdated": "2026-01-27T10:30:00Z",
                    "alertThresholdPct": 80,
                    "usdToInrRate": 83.50,
                }
            }
        }
    }
