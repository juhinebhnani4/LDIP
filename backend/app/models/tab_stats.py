"""Tab Stats models for Workspace Tab Bar API.

Story 14.12: Tab Stats API

Pydantic models for tab statistics endpoint that provides counts and
processing status for each workspace tab.

CRITICAL: Response format uses camelCase aliases to match frontend TabStats interface.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Story 14.12: Task 1.2-1.3 - Core Types
# =============================================================================


class TabStats(BaseModel):
    """Statistics for a single tab.

    Story 14.12: AC #2 - Tab counts with issue counts.
    """

    model_config = ConfigDict(populate_by_name=True)

    count: int = Field(
        ...,
        ge=0,
        description="Number of items in this tab",
    )
    issue_count: int = Field(
        ...,
        alias="issueCount",
        ge=0,
        description="Number of issues requiring attention",
    )


TabProcessingStatus = Literal["ready", "processing"]
"""Processing status for a tab: 'ready' when data is loaded, 'processing' when jobs are active."""


# =============================================================================
# Story 14.12: Task 1.4 - Tab Stats Data
# =============================================================================


class TabCountsData(BaseModel):
    """Tab counts for all workspace tabs.

    Story 14.12: AC #2 - Aggregated counts per tab.
    """

    model_config = ConfigDict(populate_by_name=True)

    summary: TabStats = Field(
        ...,
        description="Summary tab stats (count=1, issueCount=0 by default)",
    )
    timeline: TabStats = Field(
        ...,
        description="Timeline tab stats - events count",
    )
    entities: TabStats = Field(
        ...,
        description="Entities tab stats - identity_nodes count, unresolved aliases",
    )
    citations: TabStats = Field(
        ...,
        description="Citations tab stats - citations count, unverified count",
    )
    contradictions: TabStats = Field(
        ...,
        description="Contradictions tab stats - all need attention",
    )
    verification: TabStats = Field(
        ...,
        description="Verification tab stats - pending findings, flagged count",
    )
    documents: TabStats = Field(
        ...,
        description="Documents tab stats - document count",
    )


class TabProcessingStatusData(BaseModel):
    """Processing status for all workspace tabs.

    Story 14.12: AC #3 - Status derived from active background jobs.
    """

    model_config = ConfigDict(populate_by_name=True)

    summary: TabProcessingStatus = Field(
        default="ready",
        description="Summary tab processing status",
    )
    timeline: TabProcessingStatus = Field(
        default="ready",
        description="Timeline tab processing status",
    )
    entities: TabProcessingStatus = Field(
        default="ready",
        description="Entities tab processing status",
    )
    citations: TabProcessingStatus = Field(
        default="ready",
        description="Citations tab processing status",
    )
    contradictions: TabProcessingStatus = Field(
        default="ready",
        description="Contradictions tab processing status",
    )
    verification: TabProcessingStatus = Field(
        default="ready",
        description="Verification tab processing status",
    )
    documents: TabProcessingStatus = Field(
        default="ready",
        description="Documents tab processing status",
    )


class TabStatsData(BaseModel):
    """Combined tab stats and processing status.

    Story 14.12: AC #5 - Response format matching frontend types.
    """

    model_config = ConfigDict(populate_by_name=True)

    tab_counts: TabCountsData = Field(
        ...,
        alias="tabCounts",
        description="Counts and issue counts for each tab",
    )
    tab_processing_status: TabProcessingStatusData = Field(
        ...,
        alias="tabProcessingStatus",
        description="Processing status for each tab",
    )


# =============================================================================
# Story 14.12: Task 1.5 - API Response Models
# =============================================================================


class TabStatsResponse(BaseModel):
    """API response wrapper for tab stats.

    Story 14.12: AC #5 - Follows project API pattern: { data: ... }
    """

    data: TabStatsData = Field(
        ...,
        description="Tab statistics data",
    )


# =============================================================================
# Story 14.12: Error Response Models
# =============================================================================


class TabStatsErrorDetail(BaseModel):
    """Error detail structure for tab stats API.

    Follows project API error pattern from project-context.md.
    """

    code: str = Field(
        ...,
        description="Machine-readable error code",
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
    details: dict = Field(
        default_factory=dict,
        description="Additional error context",
    )


class TabStatsErrorResponse(BaseModel):
    """Error response structure for tab stats API.

    Follows project API error pattern from project-context.md.
    """

    error: TabStatsErrorDetail
