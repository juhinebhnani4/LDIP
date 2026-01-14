"""Engine Orchestrator for routing queries to appropriate analysis engines.

Epic 6: Engine Orchestrator

Pipeline stages:
1. Query Intent Analysis (Story 6-1) - Classify query and determine routing
2. Engine Execution Ordering (Story 6-2) - Execute engines and aggregate results
3. Audit Trail Logging (Story 6-3) - Log all operations for compliance

This module provides the orchestration components for routing user queries
to the appropriate analysis engines (Citation, Timeline, Contradiction, RAG).
"""

from app.engines.orchestrator.intent_analyzer import (
    IntentAnalyzer,
    IntentAnalyzerError,
    IntentParseError,
    OpenAIConfigurationError,
    get_intent_analyzer,
)
from app.engines.orchestrator.prompts import (
    INTENT_CLASSIFICATION_RESPONSE_SCHEMA,
    INTENT_CLASSIFICATION_SYSTEM_PROMPT,
    INTENT_CLASSIFICATION_USER_PROMPT,
    format_intent_prompt,
    validate_intent_response,
)

__all__ = [
    # Story 6-1: Intent Analysis
    "IntentAnalyzer",
    "IntentAnalyzerError",
    "IntentParseError",
    "OpenAIConfigurationError",
    "get_intent_analyzer",
    # Prompts
    "INTENT_CLASSIFICATION_RESPONSE_SCHEMA",
    "INTENT_CLASSIFICATION_SYSTEM_PROMPT",
    "INTENT_CLASSIFICATION_USER_PROMPT",
    "format_intent_prompt",
    "validate_intent_response",
]
