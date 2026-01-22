# Tech Spec: Multi-Intent Classification & Intelligent Aggregation Redesign

**Created:** 2026-01-22
**Status:** Ready for Implementation
**Priority:** High
**Estimated Effort:** 2 weeks

---

## Problem Statement

The current RAG query orchestrator only runs **one engine per query** due to aggressive fast-path keyword matching. When a user asks:

> "Give me a complete analysis: summarize the case, list all legal citations, create a timeline of events, and identify any contradictions between parties."

The system matches "citations" via fast-path regex, returns `confidence: 0.95`, and runs **only** the Citation engine - ignoring RAG, Timeline, and Contradiction entirely.

**Root Cause:** The classification system treats intents as mutually exclusive (winner-takes-all) when user intent is often **additive**.

---

## Solution Overview

### Phase 1: Multi-Intent Classification
Replace single-intent classification with a system that:
1. Extracts **ALL** matching intent signals (not first-match)
2. Detects when multiple engines should run
3. Identifies **compound intents** (semantic relationships between intents)
4. Uses LLM refinement only when needed

### Phase 2: Intelligent Aggregation
Replace concatenation-based aggregation with:
1. Strategy-based result combination (`parallel_merge`, `weave`, `sequential`)
2. Narrative integration for compound intents
3. Source attribution preservation
4. Coherent unified responses

---

## Phase 1: Multi-Intent Classification

### New Data Models

**File:** `backend/app/engines/orchestrator/models.py` (NEW FILE)

```python
"""Multi-intent classification models."""
from dataclasses import dataclass, field
from enum import Enum
from app.engines.orchestrator.engine_types import EngineType


class IntentSource(str, Enum):
    """Source of intent signal."""
    PATTERN = "pattern"      # Fast-path regex match
    LLM = "llm"              # LLM classification
    FALLBACK = "fallback"    # Low-confidence safety net
    COMPOUND = "compound"    # Detected intent relationship


@dataclass
class IntentSignal:
    """Individual intent signal with confidence and provenance."""
    engine: EngineType
    confidence: float
    source: IntentSource
    pattern_matched: str | None = None  # Which regex matched

    def __hash__(self):
        return hash((self.engine, self.source))


@dataclass
class CompoundIntent:
    """When multiple intents form a semantic relationship."""
    name: str                    # e.g., "temporal_contradictions"
    primary_engine: EngineType   # Lead engine for response
    supporting_engines: list[EngineType]
    aggregation_strategy: str    # "weave" | "sequential" | "parallel_merge"


@dataclass
class MultiIntentClassification:
    """Complete multi-intent classification result."""
    signals: list[IntentSignal]
    compound_intent: CompoundIntent | None = None
    reasoning: str = ""
    llm_was_used: bool = False

    # Configurable thresholds
    INCLUSION_THRESHOLD: float = 0.5
    HIGH_CONFIDENCE_THRESHOLD: float = 0.85

    @property
    def is_multi_intent(self) -> bool:
        """True if multiple engines should run."""
        return len(self.required_engines) > 1

    @property
    def required_engines(self) -> set[EngineType]:
        """All engines meeting inclusion threshold."""
        return {s.engine for s in self.signals
                if s.confidence >= self.INCLUSION_THRESHOLD}

    @property
    def primary_engine(self) -> EngineType:
        """Highest confidence engine (for response ordering)."""
        if self.compound_intent:
            return self.compound_intent.primary_engine
        return max(self.signals, key=lambda s: s.confidence).engine

    @property
    def aggregation_strategy(self) -> str:
        """How to combine results."""
        if self.compound_intent:
            return self.compound_intent.aggregation_strategy
        return "parallel_merge" if self.is_multi_intent else "single"
```

---

### Intent Analyzer Redesign

**File:** `backend/app/engines/orchestrator/intent_analyzer.py` (MODIFY)

#### New Pattern Registry (extracts ALL matches)

```python
import re
from app.engines.orchestrator.models import (
    IntentSignal, IntentSource, CompoundIntent, MultiIntentClassification
)
from app.engines.orchestrator.engine_types import EngineType

# Pattern registry - returns ALL matches, not first match
INTENT_PATTERNS: dict[EngineType, list[tuple[re.Pattern, float]]] = {
    EngineType.CITATION: [
        (re.compile(r'\b(cite|citation|section\s+\d+|act\s+\d+|statute)', re.I), 0.9),
        (re.compile(r'\b(legal\s+reference|law\s+mention)', re.I), 0.7),
    ],
    EngineType.TIMELINE: [
        (re.compile(r'\b(timeline|chronolog|when\s+did|sequence\s+of\s+events)', re.I), 0.9),
        (re.compile(r'\b(dates?|order\s+of)', re.I), 0.6),
    ],
    EngineType.CONTRADICTION: [
        (re.compile(r'\b(contradiction|inconsisten|conflict|disagree)', re.I), 0.9),
        (re.compile(r'\b(differ|dispute|discrepanc)', re.I), 0.7),
    ],
    EngineType.RAG: [
        (re.compile(r'\b(summarize|summary|what\s+is|explain|tell\s+me\s+about)', re.I), 0.8),
        (re.compile(r'\b(search|find|look\s+for)', re.I), 0.6),
    ],
}
```

#### Compound Intent Detection

```python
# Compound intent definitions - semantic relationships between intents
COMPOUND_INTENTS: dict[frozenset[EngineType], CompoundIntent] = {
    frozenset({EngineType.CONTRADICTION, EngineType.TIMELINE}): CompoundIntent(
        name="temporal_contradictions",
        primary_engine=EngineType.CONTRADICTION,
        supporting_engines=[EngineType.TIMELINE],
        aggregation_strategy="weave",
    ),
    frozenset({EngineType.CITATION, EngineType.RAG}): CompoundIntent(
        name="cited_search",
        primary_engine=EngineType.RAG,
        supporting_engines=[EngineType.CITATION],
        aggregation_strategy="weave",
    ),
    frozenset({EngineType.TIMELINE, EngineType.RAG}): CompoundIntent(
        name="chronological_summary",
        primary_engine=EngineType.RAG,
        supporting_engines=[EngineType.TIMELINE],
        aggregation_strategy="sequential",
    ),
}

# Comprehensive analysis patterns - triggers ALL engines
COMPREHENSIVE_PATTERNS = [
    re.compile(r'\b(complete|full|comprehensive)\s+(analysis|review|report)', re.I),
    re.compile(r'\b(all|everything)\s+(about|regarding)', re.I),
    re.compile(r'(summarize|summary).+(citation|timeline|contradiction)', re.I),
]
```

#### New MultiIntentAnalyzer Class

```python
class MultiIntentAnalyzer:
    """Redesigned intent analyzer supporting multi-intent classification."""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    async def classify(self, query: str) -> MultiIntentClassification:
        """Main entry point for query classification.

        Flow:
        1. Extract all intent signals from patterns
        2. Check for comprehensive analysis request
        3. Determine if LLM refinement needed
        4. Detect compound intents
        5. Apply RAG fallback for ambiguous queries
        """

        # Stage 1: Extract all intent signals from patterns
        signals = self._extract_all_signals(query)

        # Stage 1b: Check for comprehensive analysis request
        if self._is_comprehensive_request(query):
            return self._build_comprehensive_classification(query)

        # Stage 2: Determine if LLM refinement needed
        needs_llm = self._needs_llm_refinement(signals)

        if needs_llm:
            signals = await self._llm_refine_signals(query, signals)

        # Stage 3: Detect compound intents
        compound = self._detect_compound_intent(signals)

        # Stage 4: Ensure RAG fallback for ambiguous queries
        signals = self._apply_rag_fallback(signals)

        return MultiIntentClassification(
            signals=signals,
            compound_intent=compound,
            reasoning=self._build_reasoning(signals, compound),
            llm_was_used=needs_llm,
        )

    def _extract_all_signals(self, query: str) -> list[IntentSignal]:
        """Extract ALL matching intent signals, not just first match."""
        signals = []

        for engine, patterns in INTENT_PATTERNS.items():
            best_confidence = 0.0
            best_pattern = None

            for pattern, confidence in patterns:
                if pattern.search(query):
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_pattern = pattern.pattern

            if best_confidence > 0:
                signals.append(IntentSignal(
                    engine=engine,
                    confidence=best_confidence,
                    source=IntentSource.PATTERN,
                    pattern_matched=best_pattern,
                ))

        return signals

    def _is_comprehensive_request(self, query: str) -> bool:
        """Check if user wants all engines."""
        return any(p.search(query) for p in COMPREHENSIVE_PATTERNS)

    def _build_comprehensive_classification(self, query: str) -> MultiIntentClassification:
        """Return classification requesting ALL engines."""
        signals = [
            IntentSignal(EngineType.RAG, 0.9, IntentSource.PATTERN),
            IntentSignal(EngineType.CITATION, 0.85, IntentSource.PATTERN),
            IntentSignal(EngineType.TIMELINE, 0.85, IntentSource.PATTERN),
            IntentSignal(EngineType.CONTRADICTION, 0.85, IntentSource.PATTERN),
        ]
        return MultiIntentClassification(
            signals=signals,
            compound_intent=CompoundIntent(
                name="comprehensive_analysis",
                primary_engine=EngineType.RAG,
                supporting_engines=[EngineType.CITATION, EngineType.TIMELINE, EngineType.CONTRADICTION],
                aggregation_strategy="weave",
            ),
            reasoning="User requested comprehensive analysis - all engines activated",
            llm_was_used=False,
        )

    def _needs_llm_refinement(self, signals: list[IntentSignal]) -> bool:
        """Determine if LLM should refine classification."""
        if not signals:
            return True

        high_confidence_count = sum(
            1 for s in signals
            if s.confidence >= MultiIntentClassification.HIGH_CONFIDENCE_THRESHOLD
        )

        # LLM needed if: multiple high-confidence OR no high-confidence
        return high_confidence_count > 1 or high_confidence_count == 0

    async def _llm_refine_signals(
        self, query: str, initial_signals: list[IntentSignal]
    ) -> list[IntentSignal]:
        """Use LLM to refine/validate intent signals."""
        if not self._llm:
            return initial_signals

        prompt = self._build_multi_intent_prompt(query, initial_signals)
        response = await self._llm.complete(prompt)

        return self._parse_llm_response(response, initial_signals)

    def _detect_compound_intent(self, signals: list[IntentSignal]) -> CompoundIntent | None:
        """Check if signals form a known compound intent."""
        active_engines = frozenset(
            s.engine for s in signals
            if s.confidence >= MultiIntentClassification.INCLUSION_THRESHOLD
        )

        for engine_combo, compound in COMPOUND_INTENTS.items():
            if engine_combo <= active_engines:
                return compound

        return None

    def _apply_rag_fallback(self, signals: list[IntentSignal]) -> list[IntentSignal]:
        """Add RAG as fallback if no high-confidence signal."""
        max_conf = max((s.confidence for s in signals), default=0)

        if max_conf < MultiIntentClassification.HIGH_CONFIDENCE_THRESHOLD:
            has_rag = any(s.engine == EngineType.RAG for s in signals)
            if not has_rag:
                signals.append(IntentSignal(
                    engine=EngineType.RAG,
                    confidence=0.6,
                    source=IntentSource.FALLBACK,
                ))

        return signals

    def _build_reasoning(
        self, signals: list[IntentSignal], compound: CompoundIntent | None
    ) -> str:
        """Build human-readable reasoning for classification."""
        parts = []

        for s in sorted(signals, key=lambda x: -x.confidence):
            parts.append(f"{s.engine.value}: {s.confidence:.0%} ({s.source.value})")

        reasoning = f"Intent signals: {', '.join(parts)}"

        if compound:
            reasoning += f" | Compound intent: {compound.name}"

        return reasoning
```

---

### LLM Prompt for Multi-Intent Classification

**File:** `backend/app/engines/orchestrator/prompts.py` (ADD)

```python
MULTI_INTENT_CLASSIFICATION_PROMPT = """You are a legal query intent classifier. Analyze the user's query and identify ALL relevant intents.

## Available Intents (select ALL that apply):
- RAG_SEARCH: General questions about facts, parties, case summary, document content
- CITATION: Questions about legal citations, acts, sections, statutes referenced
- TIMELINE: Questions about chronology, dates, sequence of events, when things happened
- CONTRADICTION: Questions about inconsistencies, conflicts, disagreements between parties

## Query to Classify:
"{query}"

## Initial Pattern Matches:
{initial_signals}

## Instructions:
1. Consider if the user wants MULTIPLE types of information
2. Phrases like "and", "also", "as well as" suggest multi-intent
3. Return confidence 0.0-1.0 for EACH intent (not just the top one)
4. If intents are RELATED (e.g., "contradictions in the timeline"), note this

## Response Format (JSON):
{{
  "intents": [
    {{"engine": "RAG_SEARCH", "confidence": 0.8, "reason": "..."}},
    {{"engine": "TIMELINE", "confidence": 0.9, "reason": "..."}}
  ],
  "relationship": "temporal_contradictions" | "cited_search" | "chronological_summary" | null,
  "reasoning": "Overall explanation of classification"
}}
"""
```

---

### Orchestrator Integration

**File:** `backend/app/engines/orchestrator/orchestrator.py` (MODIFY)

```python
# Replace old IntentAnalyzer usage with new MultiIntentAnalyzer

class StreamingOrchestrator:
    def __init__(self, ...):
        # OLD: self._intent_analyzer = IntentAnalyzer(...)
        # NEW:
        self._intent_analyzer = MultiIntentAnalyzer(llm_client=self._llm)

    async def process_streaming(self, matter_id, user_id, query, session_id):
        # ... existing safety checks ...

        # OLD: classification = await self._intent_analyzer.classify_intent(query)
        # NEW:
        classification = await self._intent_analyzer.classify(query)

        # OLD: engines_to_run = classification.required_engines  # Was single or list
        # NEW:
        engines_to_run = list(classification.required_engines)  # Now always a set

        # NEW: Pass aggregation strategy to executor/aggregator
        results = await self._executor.execute_engines(
            matter_id=matter_id,
            query=query,
            engines=engines_to_run,
            context=context,
        )

        # NEW: Use strategy-based aggregation
        aggregated = await self._aggregator.aggregate_results_async(
            matter_id=matter_id,
            query=query,
            results=results,
            wall_clock_time_ms=elapsed_ms,
            aggregation_strategy=classification.aggregation_strategy,  # NEW
            primary_engine=classification.primary_engine,              # NEW
            compound_intent=classification.compound_intent,            # NEW
        )

        # ... rest of streaming logic ...
```

---

## Phase 2: Intelligent Aggregation

### Aggregation Strategies

**File:** `backend/app/engines/orchestrator/aggregator.py` (MODIFY)

#### Strategy Definitions

| Strategy | Use Case | Behavior |
|----------|----------|----------|
| `single` | One engine only | Pass through, no aggregation |
| `parallel_merge` | Unrelated multi-intent | Section-based combination |
| `weave` | Compound intents | Narrative integration with inline references |
| `sequential` | Time-ordered intents | Chronological structure |

#### Strategy Implementation

```python
class ResultAggregator:
    """Aggregates results from multiple engines using strategy-based combination."""

    async def aggregate_results_async(
        self,
        matter_id: str,
        query: str,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: float,
        aggregation_strategy: str = "parallel_merge",
        primary_engine: EngineType | None = None,
        compound_intent: CompoundIntent | None = None,
    ) -> OrchestratorResult:
        """Aggregate engine results using the specified strategy."""

        match aggregation_strategy:
            case "single":
                return self._aggregate_single(results, wall_clock_time_ms)
            case "parallel_merge":
                return self._aggregate_parallel_merge(results, wall_clock_time_ms)
            case "weave":
                return await self._aggregate_weave(
                    query, results, wall_clock_time_ms, primary_engine, compound_intent
                )
            case "sequential":
                return self._aggregate_sequential(results, wall_clock_time_ms, primary_engine)
            case _:
                return self._aggregate_parallel_merge(results, wall_clock_time_ms)

    def _aggregate_parallel_merge(
        self, results: list[EngineExecutionResult], wall_clock_time_ms: float
    ) -> OrchestratorResult:
        """Section-based combination - clean sections, no weaving."""
        sections = []
        all_sources = []

        # Order: RAG first (context), then specialized engines
        engine_order = [EngineType.RAG, EngineType.TIMELINE, EngineType.CITATION, EngineType.CONTRADICTION]

        for engine_type in engine_order:
            result = next((r for r in results if r.engine_type == engine_type and r.success), None)
            if result and result.response_text:
                section_title = self._get_section_title(engine_type)
                sections.append(f"## {section_title}\n\n{result.response_text}")
                all_sources.extend(result.sources or [])

        unified_response = "\n\n".join(sections)

        return OrchestratorResult(
            response_text=unified_response,
            sources=self._dedupe_sources(all_sources),
            # ... other fields
        )

    async def _aggregate_weave(
        self,
        query: str,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: float,
        primary_engine: EngineType | None,
        compound_intent: CompoundIntent | None,
    ) -> OrchestratorResult:
        """Narrative integration with inline references from supporting engines."""

        # Get primary engine result as narrative backbone
        primary_result = next(
            (r for r in results if r.engine_type == primary_engine and r.success),
            None
        )

        if not primary_result:
            # Fallback to parallel_merge if primary missing
            return self._aggregate_parallel_merge(results, wall_clock_time_ms)

        # Collect supporting data for weaving
        supporting_data = {}
        for result in results:
            if result.engine_type != primary_engine and result.success:
                supporting_data[result.engine_type] = result

        # Use LLM to weave narrative (or template-based approach)
        woven_response = await self._weave_narrative(
            primary_text=primary_result.response_text,
            supporting_data=supporting_data,
            compound_intent=compound_intent,
        )

        # Merge all sources
        all_sources = list(primary_result.sources or [])
        for result in supporting_data.values():
            all_sources.extend(result.sources or [])

        return OrchestratorResult(
            response_text=woven_response,
            sources=self._dedupe_sources(all_sources),
            # ... other fields
        )

    def _aggregate_sequential(
        self,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: float,
        primary_engine: EngineType | None,
    ) -> OrchestratorResult:
        """Time-ordered structure with content woven per phase."""
        # Implementation for chronological ordering
        # Uses timeline events as structure, weaves other content per time period
        ...

    async def _weave_narrative(
        self,
        primary_text: str,
        supporting_data: dict[EngineType, EngineExecutionResult],
        compound_intent: CompoundIntent | None,
    ) -> str:
        """Weave supporting engine data into primary narrative."""

        # Template-based weaving for known compound intents
        if compound_intent and compound_intent.name == "comprehensive_analysis":
            return self._weave_comprehensive(primary_text, supporting_data)

        # For other cases, use inline integration
        woven = primary_text

        # Add timeline references inline
        if EngineType.TIMELINE in supporting_data:
            timeline_data = supporting_data[EngineType.TIMELINE]
            # Insert key dates at relevant points
            woven = self._insert_timeline_refs(woven, timeline_data)

        # Add contradiction highlights
        if EngineType.CONTRADICTION in supporting_data:
            contradiction_data = supporting_data[EngineType.CONTRADICTION]
            woven = self._insert_contradiction_refs(woven, contradiction_data)

        # Add citation references
        if EngineType.CITATION in supporting_data:
            citation_data = supporting_data[EngineType.CITATION]
            woven = self._insert_citation_refs(woven, citation_data)

        return woven

    def _get_section_title(self, engine_type: EngineType) -> str:
        """Get display title for engine section."""
        return {
            EngineType.RAG: "Summary",
            EngineType.TIMELINE: "Timeline",
            EngineType.CITATION: "Citations Found",
            EngineType.CONTRADICTION: "Contradictions Identified",
        }.get(engine_type, engine_type.value)
```

---

## Requirements

### REQ-CLASS-001: Multi-Signal Extraction
The classifier MUST extract ALL matching intent signals from a query, not just the first match.

### REQ-CLASS-002: Comprehensive Analysis Detection
Queries containing phrases like "complete analysis", "full review", or explicitly listing multiple intents MUST trigger all four engines.

### REQ-CLASS-003: Compound Intent Detection
When multiple intents have semantic relationships (e.g., "contradictions in the timeline"), the system MUST detect and handle them as compound intents.

### REQ-CLASS-004: LLM Refinement Trigger
LLM classification MUST be triggered when:
- Multiple high-confidence (>=0.85) signals are detected
- No high-confidence signals are detected
- Pattern matching is ambiguous

### REQ-AGG-001: Strategy Selection
The aggregator MUST select strategy based on `MultiIntentClassification.aggregation_strategy`.

### REQ-AGG-002: Primary Engine Precedence
When `weave` strategy is used, the `primary_engine` result forms the narrative backbone.

### REQ-AGG-003: Source Attribution
ALL aggregated content MUST maintain source attribution (document name + page number).

### REQ-AGG-004: Empty Result Handling
- `parallel_merge`: Omit empty sections entirely
- `weave`: Note absence naturally ("No specific citations were identified")

### REQ-AGG-005: Response Length Management
Aggregated response SHOULD NOT exceed 2x the length of longest individual engine response.

---

## Test Cases

### Classification Tests

```python
@pytest.mark.asyncio
async def test_comprehensive_request_triggers_all_engines():
    """Comprehensive analysis request should activate all engines."""
    analyzer = MultiIntentAnalyzer()

    result = await analyzer.classify(
        "Give me a complete analysis: summarize the case, list citations, "
        "create timeline, and identify contradictions."
    )

    assert result.is_multi_intent
    assert len(result.required_engines) == 4
    assert EngineType.RAG in result.required_engines
    assert EngineType.CITATION in result.required_engines
    assert EngineType.TIMELINE in result.required_engines
    assert EngineType.CONTRADICTION in result.required_engines
    assert result.aggregation_strategy == "weave"


@pytest.mark.asyncio
async def test_single_intent_still_works():
    """Simple single-intent queries should still fast-path correctly."""
    analyzer = MultiIntentAnalyzer()

    result = await analyzer.classify("What is the timeline of events?")

    assert EngineType.TIMELINE in result.required_engines
    # May or may not include RAG depending on confidence


@pytest.mark.asyncio
async def test_compound_intent_detection():
    """Compound intents should be detected and handled."""
    analyzer = MultiIntentAnalyzer()

    result = await analyzer.classify("What contradictions exist in the timeline?")

    assert result.compound_intent is not None
    assert result.compound_intent.name == "temporal_contradictions"
    assert result.aggregation_strategy == "weave"


@pytest.mark.asyncio
async def test_multi_keyword_triggers_multi_engine():
    """Multiple intent keywords should trigger multiple engines."""
    analyzer = MultiIntentAnalyzer()

    result = await analyzer.classify("Show me citations and contradictions")

    assert EngineType.CITATION in result.required_engines
    assert EngineType.CONTRADICTION in result.required_engines
```

### Aggregation Tests

```python
@pytest.mark.asyncio
async def test_parallel_merge_creates_sections():
    """Parallel merge should create clean sections."""
    aggregator = ResultAggregator()

    results = [
        EngineExecutionResult(engine_type=EngineType.RAG, success=True, response_text="RAG content"),
        EngineExecutionResult(engine_type=EngineType.TIMELINE, success=True, response_text="Timeline content"),
    ]

    output = await aggregator.aggregate_results_async(
        matter_id="test",
        query="test",
        results=results,
        wall_clock_time_ms=1000,
        aggregation_strategy="parallel_merge",
    )

    assert "## Summary" in output.response_text
    assert "## Timeline" in output.response_text


@pytest.mark.asyncio
async def test_weave_maintains_source_attribution():
    """Weave strategy must preserve all source attributions."""
    # Implementation test
    ...


@pytest.mark.asyncio
async def test_empty_results_handled_gracefully():
    """Empty engine results should not break aggregation."""
    aggregator = ResultAggregator()

    results = [
        EngineExecutionResult(engine_type=EngineType.RAG, success=True, response_text="Content"),
        EngineExecutionResult(engine_type=EngineType.CITATION, success=True, response_text=""),  # Empty
    ]

    output = await aggregator.aggregate_results_async(
        matter_id="test",
        query="test",
        results=results,
        wall_clock_time_ms=1000,
        aggregation_strategy="parallel_merge",
    )

    assert "## Citations" not in output.response_text  # Omitted when empty
```

---

## Implementation Plan

### Week 1: Phase 1 - Multi-Intent Classification

| Day | Task | Files |
|-----|------|-------|
| 1-2 | Create models.py, refactor intent_analyzer.py core logic | `models.py` (new), `intent_analyzer.py` |
| 3 | Add LLM prompt and integration | `prompts.py`, `intent_analyzer.py` |
| 4 | Update orchestrator.py to use new classification | `orchestrator.py` |
| 5 | Unit tests + manual testing with Playwright | `tests/engines/orchestrator/` |

### Week 2: Phase 2 - Intelligent Aggregation

| Day | Task | Files |
|-----|------|-------|
| 1-2 | Implement strategy-based aggregation | `aggregator.py` |
| 3 | Implement weave algorithm with source tracking | `aggregator.py` |
| 4 | Integration testing with real queries | `tests/integration/` |
| 5 | Polish, edge cases, documentation | All |

---

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `backend/app/engines/orchestrator/models.py` | CREATE | New data models for multi-intent |
| `backend/app/engines/orchestrator/intent_analyzer.py` | MODIFY | Replace single-intent with multi-intent |
| `backend/app/engines/orchestrator/prompts.py` | MODIFY | Add multi-intent LLM prompt |
| `backend/app/engines/orchestrator/orchestrator.py` | MODIFY | Use new classification, pass strategy |
| `backend/app/engines/orchestrator/aggregator.py` | MODIFY | Strategy-based aggregation |
| `backend/tests/engines/orchestrator/test_intent_analyzer.py` | CREATE | Classification tests |
| `backend/tests/engines/orchestrator/test_aggregator.py` | MODIFY | Aggregation tests |

---

## Rollback Plan

If issues arise:
1. Feature flag: `ENABLE_MULTI_INTENT_CLASSIFICATION=false` falls back to old behavior
2. Keep old `IntentAnalyzer` class as `LegacyIntentAnalyzer` for 2 weeks
3. Monitor engine trace metrics for anomalies (>4 engines, unexpected combos)

---

## Success Metrics

- [ ] Comprehensive queries trigger 4 engines (not 1)
- [ ] Engine trace shows correct engine count in UI
- [ ] Response quality improves for multi-part questions
- [ ] No regression in single-intent query performance
- [ ] All existing tests pass
- [ ] New test coverage >90% for classification logic
