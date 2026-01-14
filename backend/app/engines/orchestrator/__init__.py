"""Engine Orchestrator for routing queries to appropriate analysis engines.

Epic 6: Engine Orchestrator

Pipeline stages:
1. Query Intent Analysis (Story 6-1) - Classify query and determine routing
2. Engine Execution Ordering (Story 6-2) - Execute engines and aggregate results
3. Audit Trail Logging (Story 6-3) - Log all operations for compliance

This module provides the orchestration components for routing user queries
to the appropriate analysis engines (Citation, Timeline, Contradiction, RAG).
"""

# Story 6-1: Intent Analysis
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

# Story 6-2: Engine Execution and Aggregation
from app.engines.orchestrator.planner import (
    ENGINE_DEPENDENCIES,
    ExecutionPlanner,
    get_execution_planner,
)
from app.engines.orchestrator.executor import (
    ENGINE_TIMEOUT_SECONDS,
    EngineExecutor,
    get_engine_executor,
)
from app.engines.orchestrator.aggregator import (
    ENGINE_CONFIDENCE_WEIGHTS,
    ResultAggregator,
    get_result_aggregator,
)
from app.engines.orchestrator.adapters import (
    ADAPTER_REGISTRY,
    CitationEngineAdapter,
    ContradictionEngineAdapter,
    EngineAdapter,
    RAGEngineAdapter,
    TimelineEngineAdapter,
    get_adapter,
    get_cached_adapter,
)
from app.engines.orchestrator.orchestrator import (
    QueryOrchestrator,
    get_query_orchestrator,
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
    # Story 6-2: Execution Planner
    "ENGINE_DEPENDENCIES",
    "ExecutionPlanner",
    "get_execution_planner",
    # Story 6-2: Engine Executor
    "ENGINE_TIMEOUT_SECONDS",
    "EngineExecutor",
    "get_engine_executor",
    # Story 6-2: Result Aggregator
    "ENGINE_CONFIDENCE_WEIGHTS",
    "ResultAggregator",
    "get_result_aggregator",
    # Story 6-2: Engine Adapters
    "ADAPTER_REGISTRY",
    "CitationEngineAdapter",
    "ContradictionEngineAdapter",
    "EngineAdapter",
    "RAGEngineAdapter",
    "TimelineEngineAdapter",
    "get_adapter",
    "get_cached_adapter",
    # Story 6-2: Query Orchestrator
    "QueryOrchestrator",
    "get_query_orchestrator",
]
