# Story 6.1: Implement Query Intent Analysis

Status: done

## Story

As an **attorney**,
I want **my questions automatically routed to the right analysis engine**,
So that **I get the best answer without knowing which engine to use**.

## Acceptance Criteria

1. **Given** I ask "What are all the citations in this case?"
   **When** intent analysis runs
   **Then** the query is routed to the Citation Engine
   **And** citation results are returned

2. **Given** I ask "What happened in chronological order?"
   **When** intent analysis runs
   **Then** the query is routed to the Timeline Engine
   **And** timeline results are returned

3. **Given** I ask "Are there any contradictions about the loan amount?"
   **When** intent analysis runs
   **Then** the query is routed to the Contradiction Engine
   **And** contradiction results are returned

4. **Given** I ask a general question
   **When** intent analysis runs
   **Then** RAG search is used
   **And** relevant chunks are returned with sources

5. **Given** intent classification confidence is low
   **When** routing decision is made
   **Then** multiple engines may be invoked as fallback
   **And** results are aggregated appropriately

## Tasks / Subtasks

- [x] Task 1: Create query intent models and enums (AC: #1-4)
  - [x] 1.1: Add `QueryIntent` enum: `CITATION`, `TIMELINE`, `CONTRADICTION`, `RAG_SEARCH`, `MULTI_ENGINE`
  - [x] 1.2: Add `EngineType` enum: `CITATION`, `TIMELINE`, `CONTRADICTION`, `RAG`
  - [x] 1.3: Create `IntentClassification` model with `intent`, `confidence`, `required_engines`, `reasoning`
  - [x] 1.4: Create `IntentAnalysisRequest` model with `query`, `matter_id`, `context` (optional)
  - [x] 1.5: Create `IntentAnalysisResult` model for API response with classification + metadata
  - [x] 1.6: Add models to `backend/app/models/orchestrator.py` (NEW file)

- [x] Task 2: Create intent classification prompts (AC: #1-4)
  - [x] 2.1: Create `INTENT_CLASSIFICATION_SYSTEM_PROMPT` with query type definitions
  - [x] 2.2: Create `INTENT_CLASSIFICATION_USER_PROMPT` template
  - [x] 2.3: Create `INTENT_CLASSIFICATION_RESPONSE_SCHEMA` for structured JSON output
  - [x] 2.4: Add `format_intent_prompt()` helper function
  - [x] 2.5: Add `validate_intent_response()` validation function
  - [x] 2.6: Create prompts in `backend/app/engines/orchestrator/prompts.py` (NEW)

- [x] Task 3: Implement intent analyzer engine (AC: #1-4)
  - [x] 3.1: Create `IntentAnalyzer` class in `backend/app/engines/orchestrator/intent_analyzer.py`
  - [x] 3.2: Implement `analyze_intent()` - classify query intent using GPT-3.5
  - [x] 3.3: Implement engine selection logic based on classification
  - [x] 3.4: Implement confidence-based multi-engine fallback (AC: #5)
  - [x] 3.5: Add `get_intent_analyzer()` factory function
  - [x] 3.6: Add cost tracking for LLM calls

- [x] Task 4: Implement classification rules and mapping (AC: #1-4)
  - [x] 4.1: Define keyword patterns for each engine type (fast-path)
  - [x] 4.2: Implement `_fast_path_classification()` using regex patterns
  - [x] 4.3: Implement `_llm_classification()` for complex queries
  - [x] 4.4: Implement confidence threshold logic (low confidence = multi-engine)
  - [x] 4.5: Define engine priority for multi-engine scenarios

- [x] Task 5: Create orchestrator module structure (AC: #1-4)
  - [x] 5.1: Create `backend/app/engines/orchestrator/` directory
  - [x] 5.2: Create `__init__.py` with exports
  - [x] 5.3: Update `backend/app/engines/__init__.py` to include orchestrator

- [x] Task 6: Write comprehensive tests (AC: #1-5)
  - [x] 6.1: Unit tests for `IntentAnalyzer` with mocked LLM
  - [x] 6.2: Test citation intent detection ("citations", "Act references", "Section X")
  - [x] 6.3: Test timeline intent detection ("chronological", "when", "dates", "sequence")
  - [x] 6.4: Test contradiction intent detection ("contradictions", "conflicts", "inconsistencies")
  - [x] 6.5: Test RAG fallback for general questions
  - [x] 6.6: Test low-confidence multi-engine fallback
  - [x] 6.7: Test fast-path keyword classification
  - [x] 6.8: Test matter isolation security (CRITICAL)
  - [x] 6.9: Integration test with mock engine responses

## Dev Notes

### Architecture Compliance

This story implements the **first stage** of the **Engine Orchestrator** (Epic 6):

```
INTENT ANALYSIS (6-1) 👈 → ENGINE EXECUTION (6-2) → AUDIT LOGGING (6-3)
```

Follow the established engine/service/route pattern from Epic 5 (Contradiction Engine).

### Critical Implementation Details

1. **LLM Routing: GPT-3.5 (Query Normalization Task)**

   Per project-context.md, query normalization/classification uses GPT-3.5:

   | Task Type | Model | Reason |
   |-----------|-------|--------|
   | Query normalization | GPT-3.5 | Simple, cost-sensitive |

   **DO NOT use GPT-4** for intent classification - it's 30x more expensive for a simple task.

2. **LLM Classification Approach (Confirmed in Brainstorming Session 2026-01-13)**

   From epics.md implementation notes:
   - Single LLM call for semantic routing (no agentic complexity)
   - Classification outputs: `question_type` + `required_engine`
   - Classification types: `timeline`, `citation`, `consistency`, `rag_search`
   - Fallback: Run multiple engines if classification confidence is low
   - Fits "no agentic complexity" philosophy - deterministic output

3. **Fast-Path Regex Patterns (Pre-LLM)**

   Check for obvious keywords BEFORE calling LLM to save cost:

   ```python
   CITATION_PATTERNS = [
       r'\b(citation|cite|act|section|statute|provision)\b',
       r'\bAct\s+\d{4}\b',  # "Act 1956"
       r'\bSection\s+\d+\b',  # "Section 138"
   ]

   TIMELINE_PATTERNS = [
       r'\b(timeline|chronolog|when|date|sequence|order|happened)\b',
       r'\b(before|after|between)\b.*\d{4}',  # date references
   ]

   CONTRADICTION_PATTERNS = [
       r'\b(contradict|inconsist|conflict|disagree|mismatch)\b',
       r'\bdifferent (amount|date|claim|statement)\b',
   ]
   ```

4. **Classification Response Schema**

   ```python
   class IntentClassification(BaseModel):
       intent: QueryIntent  # Primary intent
       confidence: float  # 0.0-1.0
       required_engines: list[EngineType]  # Engine(s) to invoke
       reasoning: str  # Brief explanation

   # Example response:
   {
       "intent": "citation",
       "confidence": 0.92,
       "required_engines": ["citation"],
       "reasoning": "Query asks about 'Section 138' citations"
   }
   ```

5. **Multi-Engine Fallback Strategy**

   When confidence < 0.7, invoke multiple engines:

   ```python
   LOW_CONFIDENCE_THRESHOLD = 0.7

   def determine_engines(classification: IntentClassification) -> list[EngineType]:
       if classification.confidence >= LOW_CONFIDENCE_THRESHOLD:
           return classification.required_engines

       # Low confidence: run probable engine + RAG fallback
       return classification.required_engines + [EngineType.RAG]
   ```

6. **Existing Code to Reuse (CRITICAL - DO NOT REINVENT)**

   | Component | Location | Purpose |
   |-----------|----------|---------|
   | `EngineBase` | `app/engines/base.py` | Base class pattern |
   | `EngineInput/Output` | `app/engines/base.py` | I/O models |
   | `get_*` factory pattern | `app/engines/*/` | Dependency injection |
   | Prompt formatting | `app/engines/contradiction/prompts.py` | Template pattern |
   | OpenAI client setup | `app/services/llm/` | LLM integration |
   | structlog | All engines | Structured logging |

### File Structure

Create the orchestrator engine structure:

```
backend/app/
├── engines/
│   ├── orchestrator/                    # NEW - Epic 6
│   │   ├── __init__.py                  # Exports
│   │   ├── intent_analyzer.py           # Story 6-1 (this story)
│   │   └── prompts.py                   # Intent classification prompts
│   ├── citation/                        # Epic 3 ✅
│   ├── timeline/                        # Epic 4 ✅
│   └── contradiction/                   # Epic 5 ✅
├── models/
│   └── orchestrator.py                  # NEW - QueryIntent, IntentClassification
└── tests/
    └── engines/
        └── orchestrator/
            ├── __init__.py
            └── test_intent_analyzer.py  # Story 6-1
```

### Intent Classification Prompt Design

```python
INTENT_CLASSIFICATION_SYSTEM_PROMPT = """You are a query router for a legal document analysis system.

Your task is to classify user queries to determine which analysis engine(s) should handle them.

AVAILABLE ENGINES:
1. citation - Handles queries about Act citations, sections, legal references
2. timeline - Handles queries about chronological events, dates, sequences
3. contradiction - Handles queries about inconsistencies, conflicts between statements
4. rag_search - Handles general questions requiring document search

CLASSIFICATION RULES:
1. Match query intent to the most specific engine
2. "citation" for: Act references, Section numbers, statutory provisions
3. "timeline" for: chronological order, when events happened, sequences
4. "contradiction" for: conflicts, inconsistencies, disagreements between statements
5. "rag_search" for: general questions that don't fit above categories

CONFIDENCE SCORING:
- 0.9-1.0: Query clearly matches single engine (explicit keywords)
- 0.7-0.9: Query likely matches engine (strong context clues)
- 0.5-0.7: Uncertain, might need multiple engines
- <0.5: Very uncertain, default to rag_search

Respond ONLY with valid JSON."""

INTENT_CLASSIFICATION_USER_PROMPT = """Classify this legal query:

Query: "{query}"

Respond with JSON:
{{
  "intent": "citation|timeline|contradiction|rag_search",
  "confidence": 0.0-1.0,
  "required_engines": ["engine_name"],
  "reasoning": "Brief explanation of classification"
}}"""
```

### Previous Epic (5) Learnings

From Story 5-4 implementation:

1. **Factory pattern**: Use `get_intent_analyzer()` for dependency injection
2. **Prompt validation**: Use `validate_intent_response()` like `validate_classification_response()`
3. **Cost tracking**: Track LLM costs even for cheap GPT-3.5 calls
4. **Rule-based first**: Try fast-path regex BEFORE LLM call (like severity scoring)
5. **100% test coverage**: Include edge cases, security tests, integration tests
6. **Clean models**: Use Pydantic v2 with type hints

### Git Intelligence

Recent commits show:
- Contradiction engine complete (Stories 5-1 through 5-4)
- Pattern: `feat(domain): description (Story X-Y)`
- Code review pattern: `fix(review): address code review issues for Story X-Y`
- All engines follow `engines/{domain}/` structure

### Testing Requirements

Per project-context.md:
- Backend: `tests/engines/orchestrator/` directory
- Use pytest-asyncio for async tests
- Mock OpenAI client for LLM tests
- Include matter isolation test (CRITICAL)

**Test Files to Create:**
- `tests/engines/orchestrator/__init__.py`
- `tests/engines/orchestrator/test_intent_analyzer.py`

**Minimum Test Cases:**

```python
@pytest.mark.asyncio
async def test_classify_citation_intent():
    """Query with 'Section 138' routes to citation engine."""
    analyzer = get_intent_analyzer()
    result = await analyzer.analyze_intent(
        matter_id="matter-123",
        query="What does Section 138 of the NI Act say?"
    )
    assert result.classification.intent == QueryIntent.CITATION
    assert EngineType.CITATION in result.classification.required_engines
    assert result.classification.confidence >= 0.7

@pytest.mark.asyncio
async def test_classify_timeline_intent():
    """Query about chronological events routes to timeline engine."""
    analyzer = get_intent_analyzer()
    result = await analyzer.analyze_intent(
        matter_id="matter-123",
        query="What happened in chronological order?"
    )
    assert result.classification.intent == QueryIntent.TIMELINE
    assert EngineType.TIMELINE in result.classification.required_engines

@pytest.mark.asyncio
async def test_classify_contradiction_intent():
    """Query about conflicts routes to contradiction engine."""
    analyzer = get_intent_analyzer()
    result = await analyzer.analyze_intent(
        matter_id="matter-123",
        query="Are there any contradictions about the loan amount?"
    )
    assert result.classification.intent == QueryIntent.CONTRADICTION
    assert EngineType.CONTRADICTION in result.classification.required_engines

@pytest.mark.asyncio
async def test_classify_general_query_to_rag():
    """General question falls back to RAG search."""
    analyzer = get_intent_analyzer()
    result = await analyzer.analyze_intent(
        matter_id="matter-123",
        query="What is this case about?"
    )
    assert result.classification.intent == QueryIntent.RAG_SEARCH
    assert EngineType.RAG in result.classification.required_engines

@pytest.mark.asyncio
async def test_low_confidence_multi_engine():
    """Low confidence triggers multi-engine fallback."""
    # Mock LLM to return low confidence
    result = await analyzer.analyze_intent(
        matter_id="matter-123",
        query="Tell me about the dates and citations mentioned"
    )
    # Should include multiple engines
    assert len(result.classification.required_engines) > 1

@pytest.mark.asyncio
async def test_fast_path_skips_llm():
    """Obvious keywords should skip LLM call."""
    # Create mock that tracks calls
    analyzer = get_intent_analyzer()
    result = await analyzer.analyze_intent(
        matter_id="matter-123",
        query="List all citations in the petition"
    )
    # Fast path should detect "citations"
    assert result.classification.intent == QueryIntent.CITATION

@pytest.mark.asyncio
async def test_matter_isolation():
    """Verify matter_id is included in all operations."""
    # CRITICAL: Security test
    analyzer = get_intent_analyzer()
    result = await analyzer.analyze_intent(
        matter_id="matter-123",
        query="Any contradictions?"
    )
    assert result.matter_id == "matter-123"
```

### Query Examples by Intent

**Citation Intent (route to Citation Engine):**
- "What are all the citations in this case?"
- "Which Acts are referenced in the petition?"
- "What does Section 138 of NI Act say?"
- "Are there any citations to the Companies Act?"
- "Show me the Act references"

**Timeline Intent (route to Timeline Engine):**
- "What happened in chronological order?"
- "When was the loan disbursed?"
- "Show me the sequence of events"
- "What happened between 2022 and 2024?"
- "What is the timeline of this matter?"

**Contradiction Intent (route to Contradiction Engine):**
- "Are there any contradictions about the loan amount?"
- "Do the documents disagree on any dates?"
- "Are there inconsistencies in Mr. Sharma's statements?"
- "Find conflicts between the petition and reply"
- "What do the parties disagree on?"

**RAG Search Intent (fallback):**
- "What is this case about?"
- "Who is the petitioner?"
- "Summarize the main issues"
- "What are the key facts?"

### Cost Tracking

Even though GPT-3.5 is cheap (~$0.002 per 1K tokens), track costs:

```python
@dataclass
class IntentAnalysisCost:
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    llm_call_made: bool = False  # False if fast-path used

    # GPT-3.5-turbo pricing
    INPUT_COST_PER_1K = 0.0005
    OUTPUT_COST_PER_1K = 0.0015

    def calculate_cost(self) -> float:
        input_cost = (self.input_tokens / 1000) * self.INPUT_COST_PER_1K
        output_cost = (self.output_tokens / 1000) * self.OUTPUT_COST_PER_1K
        self.total_cost_usd = input_cost + output_cost
        return self.total_cost_usd
```

### API Design Preview (Story 6-2)

This story focuses on the `IntentAnalyzer` engine. The API endpoint will be added in Story 6-2:

```python
# Future: Story 6-2 will add this endpoint
@router.post("/api/orchestrator/analyze")
async def analyze_query(
    request: QueryAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Supabase = Depends(get_supabase)
) -> QueryAnalysisResponse:
    ...
```

### Project Structure Notes

- Orchestrator logic goes in `engines/orchestrator/`
- New models in `models/orchestrator.py`
- Tests in `tests/engines/orchestrator/`
- Follow existing factory pattern (`get_intent_analyzer()`)

### References

- [Project Context](../_bmad-output/project-context.md) - LLM routing rules, naming conventions
- [Architecture: LLM Routing](../_bmad-output/architecture.md) - GPT-3.5 for query normalization
- [Epic 6 Definition](../_bmad-output/project-planning-artifacts/epics.md) - Implementation notes from brainstorming
- [Story 5-4 Implementation](./5-4-severity-scoring-explanation.md) - Pattern reference
- [Engine Base Class](../backend/app/engines/base.py) - Base class for engines
- [Contradiction Prompts](../backend/app/engines/contradiction/prompts.py) - Prompt template pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - All tests passed on first run after regex pattern fixes.

### Completion Notes List

- Implemented Query Intent Analysis engine for Epic 6 (Engine Orchestrator)
- Created models: QueryIntent, EngineType, IntentClassification, IntentAnalysisRequest, IntentAnalysisResult
- Implemented fast-path regex classification for obvious keywords (saves LLM costs)
- Implemented GPT-3.5 LLM classification for complex queries (cost-sensitive per ADR-002)
- Added multi-engine fallback for low confidence (<0.7) classifications
- All 32 tests pass including matter isolation security tests
- Fixed pre-existing syntax error in tests/api/routes/test_jobs.py

### File List

**New Files:**
- backend/app/models/orchestrator.py
- backend/app/engines/orchestrator/__init__.py
- backend/app/engines/orchestrator/prompts.py
- backend/app/engines/orchestrator/intent_analyzer.py
- backend/tests/engines/orchestrator/__init__.py
- backend/tests/engines/orchestrator/test_intent_analyzer.py

**Modified Files:**
- backend/app/core/config.py (added openai_intent_model setting)
- backend/app/engines/__init__.py (added orchestrator exports)
- backend/app/models/__init__.py (added orchestrator model exports)
- backend/tests/api/routes/test_jobs.py (fixed syntax error - unrelated to story)

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.5
**Date:** 2026-01-14
**Outcome:** ✅ APPROVED (all issues fixed)

### Review Summary

- **AC Validation:** All 5 ACs verified as implemented with test coverage
- **Task Audit:** All tasks marked [x] confirmed actually complete
- **Git vs Story:** File list matches git reality (0 discrepancies)

### Issues Found and Fixed

| Severity | Issue | Resolution |
|----------|-------|------------|
| HIGH | Missing prompt injection tests (per project-context.md) | Added `TestPromptInjection` class with 4 security tests |
| MEDIUM | Dead code: `GPT35_INPUT_COST_PER_1K` constants never used | Removed unused constants from intent_analyzer.py |
| MEDIUM | `matter_id` field missing validation | Added `min_length=1` to IntentAnalysisRequest.matter_id |
| MEDIUM | `context` parameter accepted but never used | Removed from function signature, marked reserved in model |
| MEDIUM | `OpenAIConfigurationError` not exported from engines/__init__.py | Added to exports |
| MEDIUM | Query not stripped before regex matching | Added `query.strip()` at start of analyze_intent() |
| LOW | Missing edge case tests | Added `TestEdgeCases` class (whitespace, unicode, long queries) |
| LOW | Inconsistent cost constant locations | Resolved by removing dead code (M1) |

### Test Results

```
41 passed in 0.86s
```

Tests added: 9 new tests (4 prompt injection + 5 edge cases)

## Change Log

- 2026-01-14: Code review complete - fixed 8 issues, 41 tests passing
- 2026-01-14: Implemented Story 6-1 Query Intent Analysis - all tasks complete, 32 tests passing
