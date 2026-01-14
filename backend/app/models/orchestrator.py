"""Orchestrator models for query intent analysis and engine routing.

Epic 6: Engine Orchestrator
Story 6-1: Query Intent Analysis

Models for classifying user queries and routing them to appropriate engines.

CRITICAL: Uses GPT-3.5 for query normalization per LLM routing rules (ADR-002).
Intent classification = simple task, cost-sensitive.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Enums (Subtasks 1.1, 1.2)
# =============================================================================


class QueryIntent(str, Enum):
    """Intent type for user queries.

    Story 6-1: Maps user questions to engine capabilities.

    Values:
        CITATION: Questions about Act citations, sections, legal references
        TIMELINE: Questions about chronological events, dates, sequences
        CONTRADICTION: Questions about inconsistencies, conflicts between statements
        RAG_SEARCH: General questions requiring document search (fallback)
        MULTI_ENGINE: Ambiguous query requiring multiple engines
    """

    CITATION = "citation"
    TIMELINE = "timeline"
    CONTRADICTION = "contradiction"
    RAG_SEARCH = "rag_search"
    MULTI_ENGINE = "multi_engine"


class EngineType(str, Enum):
    """Available analysis engines.

    Story 6-1: Engine identifiers for routing decisions.

    Values:
        CITATION: Citation extraction and verification engine (Epic 3)
        TIMELINE: Timeline construction engine (Epic 4)
        CONTRADICTION: Consistency and contradiction engine (Epic 5)
        RAG: RAG hybrid search for general questions (Epic 2B)
    """

    CITATION = "citation"
    TIMELINE = "timeline"
    CONTRADICTION = "contradiction"
    RAG = "rag"


# =============================================================================
# Classification Models (Subtasks 1.3, 1.4, 1.5)
# =============================================================================


class IntentClassification(BaseModel):
    """Result of intent classification.

    Story 6-1: Contains the classified intent, confidence, and routing info.

    Example:
        >>> classification = IntentClassification(
        ...     intent=QueryIntent.CITATION,
        ...     confidence=0.92,
        ...     required_engines=[EngineType.CITATION],
        ...     reasoning="Query asks about 'Section 138' citations",
        ... )
    """

    intent: QueryIntent = Field(
        description="Primary intent detected in the query"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) for the classification",
    )
    required_engines: list[EngineType] = Field(
        description="Engine(s) that should handle this query",
    )
    reasoning: str = Field(
        description="Brief explanation of classification decision",
    )


class IntentAnalysisRequest(BaseModel):
    """Request for intent analysis.

    Story 6-1: Input model for the IntentAnalyzer engine.
    """

    query: str = Field(
        min_length=1,
        description="User's natural language query",
    )
    matter_id: str = Field(
        min_length=1,
        description="Matter UUID for context and isolation",
    )
    context: str | None = Field(
        default=None,
        description="Reserved for future use: conversation context for disambiguation (Story 6-2+)",
    )


class IntentAnalysisCost(BaseModel):
    """Cost tracking for intent analysis.

    Story 6-1: Track LLM costs even for cheap GPT-3.5 calls.

    GPT-3.5-turbo pricing (as of Jan 2025):
    - Input: $0.0005 per 1K tokens
    - Output: $0.0015 per 1K tokens
    """

    input_tokens: int = Field(default=0, description="Input tokens used")
    output_tokens: int = Field(default=0, description="Output tokens used")
    total_cost_usd: float = Field(default=0.0, description="Total cost in USD")
    llm_call_made: bool = Field(
        default=False,
        description="False if fast-path was used (no LLM call)",
    )

    # GPT-3.5-turbo pricing
    INPUT_COST_PER_1K: float = 0.0005
    OUTPUT_COST_PER_1K: float = 0.0015

    def calculate_cost(self) -> float:
        """Calculate total cost based on token usage.

        Returns:
            Total cost in USD.
        """
        input_cost = (self.input_tokens / 1000) * self.INPUT_COST_PER_1K
        output_cost = (self.output_tokens / 1000) * self.OUTPUT_COST_PER_1K
        self.total_cost_usd = input_cost + output_cost
        return self.total_cost_usd


class IntentAnalysisResult(BaseModel):
    """Result of intent analysis.

    Story 6-1: API response model containing classification + metadata.
    """

    matter_id: str = Field(
        description="Matter UUID (echoed for verification)",
    )
    query: str = Field(
        description="Original query (echoed for verification)",
    )
    classification: IntentClassification = Field(
        description="Classification result",
    )
    fast_path_used: bool = Field(
        default=False,
        description="True if regex fast-path was used (no LLM call)",
    )
    cost: IntentAnalysisCost = Field(
        default_factory=IntentAnalysisCost,
        description="Cost tracking information",
    )


class IntentAnalysisResponse(BaseModel):
    """API response wrapper for intent analysis.

    Follows project-context.md API response format:
    - Success: { "data": {...} }
    """

    data: IntentAnalysisResult = Field(
        description="Intent analysis result",
    )


class IntentAnalysisErrorDetail(BaseModel):
    """Error detail for intent analysis failures."""

    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict)


class IntentAnalysisErrorResponse(BaseModel):
    """Error response for intent analysis.

    Follows project-context.md API response format:
    - Error: { "error": {...} }
    """

    error: IntentAnalysisErrorDetail = Field(
        description="Error information",
    )


# =============================================================================
# Constants (for use in other modules)
# =============================================================================

# Confidence threshold for multi-engine fallback
LOW_CONFIDENCE_THRESHOLD = 0.7

# Engine priority for multi-engine scenarios
# Lower index = higher priority
ENGINE_PRIORITY = [
    EngineType.CITATION,
    EngineType.TIMELINE,
    EngineType.CONTRADICTION,
    EngineType.RAG,
]
