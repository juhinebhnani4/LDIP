"""Reasoning trace models for legal defensibility (Story 4.1).

Epic 4: Legal Defensibility (Gap Remediation)

These models define the structure for storing and retrieving AI reasoning chains:
- EngineType: Enum for engines that produce reasoning traces
- ReasoningTrace: Complete reasoning trace record from database
- ReasoningTraceCreate: Input model for creating new traces
- ReasoningTraceSummary: Lightweight summary for API responses
- ReasoningTraceStats: Aggregate statistics for a matter

Implements:
- Gap #5: Reasoning trace/explainability
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EngineType(str, Enum):
    """Engine types that produce reasoning traces.

    Story 4.1: Identifies the source engine for each reasoning trace.
    """

    CITATION = "citation"
    TIMELINE = "timeline"
    CONTRADICTION = "contradiction"
    RAG = "rag"
    ENTITY = "entity"


class ReasoningTrace(BaseModel):
    """Complete reasoning trace record from database.

    Story 4.1: Full trace record with all fields for detail view.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Trace UUID")
    matter_id: str = Field(..., alias="matterId", description="Matter UUID")
    finding_id: str | None = Field(
        None,
        alias="findingId",
        description="Finding UUID (nullable if not linked to specific finding)",
    )

    engine_type: EngineType = Field(..., alias="engineType", description="Source engine")
    model_used: str = Field(..., alias="modelUsed", description="LLM model identifier")

    reasoning_text: str = Field(..., alias="reasoningText", description="Chain-of-thought explanation")
    reasoning_structured: dict[str, Any] | None = Field(
        None,
        alias="reasoningStructured",
        description="Optional structured breakdown",
    )

    input_summary: str | None = Field(
        None,
        alias="inputSummary",
        description="Truncated summary of input context",
    )
    prompt_template_version: str | None = Field(
        None,
        alias="promptTemplateVersion",
        description="Version of prompt template used",
    )

    confidence_score: float | None = Field(
        None,
        ge=0,
        le=1,
        alias="confidenceScore",
        description="Confidence score (0-1 scale)",
    )
    tokens_used: int | None = Field(
        None,
        ge=0,
        alias="tokensUsed",
        description="Total tokens consumed",
    )
    cost_usd: float | None = Field(
        None,
        ge=0,
        alias="costUsd",
        description="Estimated cost in USD",
    )

    created_at: datetime = Field(..., alias="createdAt", description="When trace was created")
    archived_at: datetime | None = Field(
        None,
        alias="archivedAt",
        description="When trace was archived to cold storage",
    )
    archive_path: str | None = Field(
        None,
        alias="archivePath",
        description="Supabase Storage path for archived content",
    )


class ReasoningTraceCreate(BaseModel):
    """Input for creating a reasoning trace.

    Story 4.1: Called by engines after LLM responses to store reasoning.
    """

    model_config = ConfigDict(populate_by_name=True)

    matter_id: str = Field(..., alias="matterId", description="Matter UUID")
    finding_id: str | None = Field(
        None,
        alias="findingId",
        description="Optional finding UUID to link",
    )
    engine_type: EngineType = Field(..., alias="engineType", description="Source engine")
    model_used: str = Field(..., alias="modelUsed", description="LLM model identifier")
    reasoning_text: str = Field(
        ...,
        min_length=1,
        alias="reasoningText",
        description="Chain-of-thought explanation",
    )
    reasoning_structured: dict[str, Any] | None = Field(
        None,
        alias="reasoningStructured",
        description="Optional structured breakdown",
    )
    input_summary: str | None = Field(
        None,
        alias="inputSummary",
        description="Truncated summary of input context (max 1000 chars)",
    )
    prompt_template_version: str | None = Field(
        None,
        alias="promptTemplateVersion",
        description="Version of prompt template used",
    )
    confidence_score: float | None = Field(
        None,
        ge=0,
        le=1,
        alias="confidenceScore",
        description="Confidence score (0-1 scale)",
    )
    tokens_used: int | None = Field(
        None,
        ge=0,
        alias="tokensUsed",
        description="Total tokens consumed",
    )
    cost_usd: float | None = Field(
        None,
        ge=0,
        alias="costUsd",
        description="Estimated cost in USD",
    )


class ReasoningTraceSummary(BaseModel):
    """Lightweight summary for API responses.

    Story 4.1: Optimized for list views and queue display.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Trace UUID")
    engine_type: EngineType = Field(..., alias="engineType", description="Source engine")
    model_used: str = Field(..., alias="modelUsed", description="LLM model identifier")
    reasoning_preview: str = Field(
        ...,
        alias="reasoningPreview",
        description="First 200 chars of reasoning text",
    )
    confidence_score: float | None = Field(
        None,
        ge=0,
        le=1,
        alias="confidenceScore",
        description="Confidence score (0-1 scale)",
    )
    created_at: datetime = Field(..., alias="createdAt", description="When trace was created")
    is_archived: bool = Field(..., alias="isArchived", description="Whether trace is in cold storage")


class ReasoningTraceStats(BaseModel):
    """Statistics for a matter's reasoning traces.

    Story 4.1/4.2: Aggregate stats for dashboard display.
    """

    model_config = ConfigDict(populate_by_name=True)

    total_traces: int = Field(0, ge=0, alias="totalTraces", description="Total reasoning traces")
    traces_by_engine: dict[str, int] = Field(
        default_factory=dict,
        alias="tracesByEngine",
        description="Count of traces per engine type",
    )
    hot_storage_count: int = Field(
        0,
        ge=0,
        alias="hotStorageCount",
        description="Traces in PostgreSQL (< 30 days)",
    )
    cold_storage_count: int = Field(
        0,
        ge=0,
        alias="coldStorageCount",
        description="Traces in Supabase Storage (archived)",
    )
    total_tokens_used: int = Field(
        0,
        ge=0,
        alias="totalTokensUsed",
        description="Sum of tokens across all traces",
    )
    total_cost_usd: float = Field(
        0.0,
        ge=0,
        alias="totalCostUsd",
        description="Sum of costs across all traces",
    )
    oldest_hot_trace: datetime | None = Field(
        None,
        alias="oldestHotTrace",
        description="Created_at of oldest non-archived trace",
    )
    newest_trace: datetime | None = Field(
        None,
        alias="newestTrace",
        description="Created_at of most recent trace",
    )


# =============================================================================
# Story 4.1: API Response Models
# =============================================================================


class ReasoningTraceResponse(BaseModel):
    """Response for single reasoning trace endpoint.

    Story 4.1: Follows project API response pattern with data wrapper.
    """

    data: ReasoningTrace = Field(..., description="Reasoning trace record")


class ReasoningTraceListResponse(BaseModel):
    """Response for reasoning trace list endpoint.

    Story 4.1: Follows project API response pattern.
    """

    data: list[ReasoningTraceSummary] = Field(
        default_factory=list,
        description="List of reasoning trace summaries",
    )
    meta: dict = Field(
        default_factory=dict,
        description="Pagination metadata",
    )


class ReasoningTraceStatsResponse(BaseModel):
    """Response for reasoning trace stats endpoint.

    Story 4.1: Dashboard statistics.
    """

    data: ReasoningTraceStats = Field(..., description="Reasoning trace statistics")
