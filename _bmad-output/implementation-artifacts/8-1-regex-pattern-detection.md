# Story 8.1: Implement Fast-Path Regex Pattern Detection

Status: review

## Story

As a **developer**,
I want **dangerous query patterns blocked instantly**,
So that **obvious legal conclusion requests don't reach the LLM**.

## Acceptance Criteria

1. **Given** a query matches dangerous patterns
   **When** regex detection runs
   **Then** patterns like `/should (i|we|client) (file|appeal|settle)/i` are matched
   **And** the query is blocked before LLM processing

2. **Given** a query asks "Will the judge rule in my favor?"
   **When** detection runs
   **Then** it matches `/will (judge|court) (rule|decide|hold)/i`
   **And** the query is blocked with an explanation

3. **Given** a query asks "What are my chances of winning?"
   **When** detection runs
   **Then** it matches `/what are (my|our) chances/i`
   **And** the query is blocked

4. **Given** a query is blocked
   **When** the response is returned
   **Then** GuardrailCheck includes: is_safe=false, violation_type, explanation, suggested_rewrite

## Tasks / Subtasks

- [x] Task 1: Create Guardrail Models (AC: #4)
  - [x] 1.1: Create `GuardrailCheck` Pydantic model with fields: is_safe, violation_type, pattern_matched, explanation, suggested_rewrite, check_time_ms
  - [x] 1.2: Create `ViolationType` enum/Literal with values: legal_advice_request, outcome_prediction, liability_conclusion, procedural_recommendation
  - [x] 1.3: Create `GuardrailPattern` model with fields: pattern_id, pattern (compiled regex), violation_type, explanation_template, rewrite_template
  - [x] 1.4: Add models to `backend/app/models/safety.py` (NEW file)

- [x] Task 2: Create Pattern Registry (AC: #1-3)
  - [x] 2.1: Create `backend/app/services/safety/patterns.py` with compiled regex patterns
  - [x] 2.2: Implement legal advice patterns: "should (i|we|client) (file|appeal|settle|sue|proceed)"
  - [x] 2.3: Implement outcome prediction patterns: "will (judge|court) (rule|decide|hold|find|grant|deny)"
  - [x] 2.4: Implement chances patterns: "what are (my|our|the) chances", "likelihood of (winning|success)"
  - [x] 2.5: Implement liability patterns: "is (defendant|plaintiff|client) (guilty|liable|responsible)"
  - [x] 2.6: Implement procedural patterns: "should we (appeal|file|submit|respond)"
  - [x] 2.7: Add pattern metadata (explanation_template, suggested_rewrite_template for each)

- [x] Task 3: Create GuardrailService (AC: #1-4)
  - [x] 3.1: Create `backend/app/services/safety/guardrail.py`
  - [x] 3.2: Implement `check_query()` method - runs all patterns against query
  - [x] 3.3: Implement `get_violation_explanation()` method - generates user-friendly explanation
  - [x] 3.4: Implement `suggest_rewrite()` method - proposes safe alternative query
  - [x] 3.5: Return GuardrailCheck with timing metrics
  - [x] 3.6: Ensure check runs in < 5ms (regex only, no LLM)

- [x] Task 4: Create Pattern Tests (AC: #1-3)
  - [x] 4.1: Create `backend/tests/services/safety/test_patterns.py`
  - [x] 4.2: Test "Should I file an appeal?" - BLOCKED
  - [x] 4.3: Test "Will the judge rule in my favor?" - BLOCKED
  - [x] 4.4: Test "What are my chances of winning?" - BLOCKED
  - [x] 4.5: Test "Is the defendant guilty?" - BLOCKED
  - [x] 4.6: Test "What does Section 138 say?" - ALLOWED
  - [x] 4.7: Test "When did the loan default?" - ALLOWED
  - [x] 4.8: Test "What contradictions exist in witness statements?" - ALLOWED

- [x] Task 5: Create GuardrailService Tests (AC: #4)
  - [x] 5.1: Create `backend/tests/services/safety/test_guardrail.py`
  - [x] 5.2: Test GuardrailCheck response structure for blocked query
  - [x] 5.3: Test GuardrailCheck response structure for allowed query
  - [x] 5.4: Test explanation generation
  - [x] 5.5: Test rewrite suggestion
  - [x] 5.6: Test performance (< 5ms for single query)
  - [x] 5.7: Test case insensitivity
  - [x] 5.8: Test multiple patterns matching (returns first match)

- [x] Task 6: Update Module Exports (AC: #1-4)
  - [x] 6.1: Create `backend/app/services/safety/__init__.py` with exports
  - [x] 6.2: Export GuardrailService, get_guardrail_service, reset_guardrail_service
  - [x] 6.3: Export pattern registry
  - [x] 6.4: Create `backend/app/models/safety.py` exports

## Dev Notes

### Architecture Compliance

This story implements **Query Guardrails (Layer 1)** of the Safety Layer (Epic 8):

```
USER QUERY → [GUARDRAIL CHECK] → ORCHESTRATOR → ENGINES → [LANGUAGE POLICING] → RESPONSE
              ^^^^^^^^^^^^^                       ^^^^^^^^^^^^^^^^^^^^^
              Story 8-1 (this)                    Story 8-3
```

Query Guardrails satisfy:
- **FR8**: Query Guardrails - Block dangerous queries before LLM processing
- **NFR22**: Safety - Prevent legal conclusions from being requested
- **Architecture Decision**: Fast-path regex runs BEFORE any LLM calls (cost savings)

### Critical Implementation Details

1. **Pattern Design Philosophy**

   The regex patterns should be:
   - **Conservative**: Block obvious requests, allow borderline cases
   - **Fast**: Pre-compiled regex, no external calls
   - **Explainable**: Each block includes clear user explanation
   - **Recoverable**: Suggest safe rewrite for blocked queries

   ```python
   # GOOD: Clear legal advice request
   "Should I file an appeal?" → BLOCKED
   "Will the judge rule in my favor?" → BLOCKED

   # BORDERLINE - DO NOT BLOCK (let LLM + 8-2 handle):
   "What factors do judges consider in appeals?" → ALLOWED
   "What is the standard for granting relief?" → ALLOWED
   ```

2. **Regex Pattern Categories**

   **Category 1: Direct Legal Advice Requests**
   ```python
   # Pattern: /should (i|we|the client|my client) (file|appeal|settle|sue|proceed|respond)/i
   LEGAL_ADVICE_PATTERNS = [
       r"should\s+(i|we|the\s+client|my\s+client)\s+(file|appeal|settle|sue|proceed|respond|submit)",
       r"do\s+you\s+(recommend|advise|suggest)\s+(filing|appealing|settling|suing)",
       r"what\s+should\s+(i|we)\s+do\s+(next|now|about)",
   ]
   ```

   **Category 2: Outcome Predictions**
   ```python
   # Pattern: /will (the )?(judge|court) (rule|decide|hold|find|grant|deny)/i
   OUTCOME_PREDICTION_PATTERNS = [
       r"will\s+(the\s+)?(judge|court|tribunal|bench)\s+(rule|decide|hold|find|grant|deny|dismiss)",
       r"(what|how)\s+will\s+(the\s+)?(judge|court)\s+(rule|decide)",
       r"is\s+the\s+court\s+(likely|going)\s+to",
   ]
   ```

   **Category 3: Probability/Chances**
   ```python
   # Pattern: /what are (my|our|the) chances/i
   CHANCES_PATTERNS = [
       r"what\s+are\s+(my|our|the|client'?s?)\s+chances",
       r"(what|how\s+high)\s+is\s+the\s+(likelihood|probability|chance)\s+of",
       r"(will|can)\s+(i|we|they)\s+(win|succeed|prevail)",
   ]
   ```

   **Category 4: Liability Conclusions**
   ```python
   # Pattern: /is (defendant|plaintiff|client) (guilty|liable|responsible)/i
   LIABILITY_PATTERNS = [
       r"is\s+(the\s+)?(defendant|plaintiff|accused|client)\s+(guilty|liable|responsible|at\s+fault)",
       r"(did|has)\s+(the\s+)?(defendant|plaintiff)\s+(violate|breach|commit)",
   ]
   ```

3. **GuardrailCheck Response Model**

   ```python
   from pydantic import BaseModel, Field
   from typing import Literal

   ViolationType = Literal[
       "legal_advice_request",
       "outcome_prediction",
       "liability_conclusion",
       "procedural_recommendation",
   ]

   class GuardrailCheck(BaseModel):
       """Result of query guardrail check.

       Story 8-1: AC #4 - Response includes is_safe, violation_type, explanation, suggested_rewrite.
       """

       is_safe: bool = Field(description="True if query passes guardrail check")
       violation_type: ViolationType | None = Field(
           default=None,
           description="Type of violation detected (if blocked)",
       )
       pattern_matched: str | None = Field(
           default=None,
           description="Pattern ID that matched (for debugging)",
       )
       explanation: str = Field(
           default="",
           description="User-friendly explanation of why query was blocked",
       )
       suggested_rewrite: str = Field(
           default="",
           description="Suggested safe alternative query",
       )
       check_time_ms: float = Field(
           default=0.0,
           ge=0,
           description="Time taken for guardrail check in milliseconds",
       )
   ```

4. **Service Implementation Pattern**

   Follow the singleton pattern from `SessionMemoryService`:
   ```python
   import re
   import time
   import threading
   from functools import lru_cache

   import structlog
   from app.models.safety import GuardrailCheck, ViolationType

   logger = structlog.get_logger(__name__)

   class GuardrailService:
       """Fast-path regex guardrail for dangerous queries.

       Story 8-1: Blocks legal advice/outcome prediction requests
       before they reach LLM (cost + safety optimization).
       """

       _lock = threading.Lock()

       def __init__(self) -> None:
           self._patterns: list[CompiledPattern] = []
           self._load_patterns()
           logger.info("guardrail_service_initialized", pattern_count=len(self._patterns))

       def check_query(self, query: str) -> GuardrailCheck:
           """Check query against all guardrail patterns.

           Story 8-1: AC #1-3 - Pattern matching.

           Args:
               query: User query to check.

           Returns:
               GuardrailCheck with result and metadata.
           """
           start_time = time.perf_counter()

           query_lower = query.lower()

           for pattern in self._patterns:
               if pattern.regex.search(query_lower):
                   check_time_ms = (time.perf_counter() - start_time) * 1000

                   return GuardrailCheck(
                       is_safe=False,
                       violation_type=pattern.violation_type,
                       pattern_matched=pattern.pattern_id,
                       explanation=pattern.get_explanation(query),
                       suggested_rewrite=pattern.get_rewrite(query),
                       check_time_ms=check_time_ms,
                   )

           check_time_ms = (time.perf_counter() - start_time) * 1000

           return GuardrailCheck(
               is_safe=True,
               check_time_ms=check_time_ms,
           )

   # Factory pattern with thread safety
   _guardrail_service: GuardrailService | None = None
   _service_lock = threading.Lock()

   def get_guardrail_service() -> GuardrailService:
       """Get singleton guardrail service instance."""
       global _guardrail_service
       if _guardrail_service is None:
           with _service_lock:
               if _guardrail_service is None:
                   _guardrail_service = GuardrailService()
       return _guardrail_service

   def reset_guardrail_service() -> None:
       """Reset singleton for testing."""
       global _guardrail_service
       with _service_lock:
           _guardrail_service = None
   ```

5. **Integration Point with Orchestrator**

   The GuardrailService will be called by the QueryOrchestrator BEFORE intent analysis:

   ```python
   # In orchestrator.py - process_query method (Story 8-1 integration, implemented in Story 8-2)
   async def process_query(self, matter_id: str, query: str, ...) -> OrchestratorResult:
       # Step 0: Safety check (Story 8-1)
       guardrail_check = self._guardrail_service.check_query(query)
       if not guardrail_check.is_safe:
           return OrchestratorResult(
               success=False,
               blocked=True,
               blocked_reason=guardrail_check.explanation,
               suggested_rewrite=guardrail_check.suggested_rewrite,
               # ... other fields
           )

       # Step 1: Analyze intent (existing)
       intent_result = await self._intent_analyzer.analyze_intent(...)
   ```

   **Note:** The actual integration into orchestrator will be done in Story 8-2. This story only creates the GuardrailService.

6. **Explanation and Rewrite Templates**

   ```python
   EXPLANATION_TEMPLATES = {
       "legal_advice_request": (
           "This query appears to request legal advice about what action to take. "
           "LDIP analyzes documents and extracts facts - it cannot provide legal recommendations. "
           "Try asking about the facts or documents instead."
       ),
       "outcome_prediction": (
           "This query asks for a prediction about how a court will rule. "
           "LDIP cannot predict judicial outcomes. "
           "Try asking about relevant precedents or document contents instead."
       ),
       "liability_conclusion": (
           "This query asks for a conclusion about liability or guilt. "
           "LDIP identifies factual observations - only attorneys can draw legal conclusions. "
           "Try asking what the documents say about the relevant events."
       ),
       "procedural_recommendation": (
           "This query asks what procedural step to take next. "
           "LDIP cannot recommend legal procedures. "
           "Try asking about deadlines or requirements mentioned in the documents."
       ),
   }

   REWRITE_TEMPLATES = {
       "legal_advice_request": "What do the documents say about [topic]?",
       "outcome_prediction": "What precedents or rulings are cited in the documents?",
       "liability_conclusion": "What evidence is mentioned regarding [party]'s actions?",
       "procedural_recommendation": "What procedural requirements are mentioned in the documents?",
   }
   ```

### Existing Code to Reuse (DO NOT REINVENT)

| Component | Location | Purpose |
|-----------|----------|---------|
| `structlog` | All modules | Structured logging |
| `BaseModel` | pydantic | Model definitions |
| Factory pattern | `services/memory/session.py` | Singleton with thread safety |
| `threading.Lock` | stdlib | Thread-safe initialization |
| `time.perf_counter` | stdlib | High-precision timing |

### Previous Story (7-5) Learnings

From Story 7-5 implementation and code review:

1. **Thread Safety**: Use `threading.Lock()` for singleton factories
2. **Timing Metrics**: Use `time.perf_counter()` for sub-millisecond accuracy
3. **Error Handling**: Wrap operations in try/except with structured logging
4. **Constants**: Extract magic strings as module-level constants
5. **Type Hints**: Full type annotations on all methods
6. **Story References**: Include Story reference in all docstrings

### File Structure

Create new safety service:

```
backend/app/
├── models/
│   └── safety.py                     # NEW: GuardrailCheck, ViolationType models
├── services/
│   └── safety/
│       ├── __init__.py               # NEW: Module exports
│       ├── patterns.py               # NEW: Compiled regex patterns
│       └── guardrail.py              # NEW: GuardrailService
└── tests/
    └── services/
        └── safety/
            ├── __init__.py           # NEW: Test module
            ├── test_patterns.py      # NEW: Pattern matching tests
            └── test_guardrail.py     # NEW: Service tests
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/services/safety/` directory
- Use pytest for sync tests (no async needed for regex)
- Include performance assertion (< 5ms)

**Minimum Test Cases:**

```python
# test_patterns.py

class TestLegalAdvicePatterns:
    """Test legal advice request detection."""

    def test_should_i_file_blocked(self):
        """Should block 'Should I file an appeal?'"""
        check = guardrail_service.check_query("Should I file an appeal?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"

    def test_should_we_settle_blocked(self):
        """Should block 'Should we settle the case?'"""
        check = guardrail_service.check_query("Should we settle the case?")
        assert check.is_safe is False
        assert check.violation_type == "legal_advice_request"

    def test_case_insensitive(self):
        """Pattern matching should be case-insensitive."""
        check = guardrail_service.check_query("SHOULD I FILE AN APPEAL?")
        assert check.is_safe is False


class TestOutcomePredictionPatterns:
    """Test outcome prediction detection."""

    def test_will_judge_rule_blocked(self):
        """Should block 'Will the judge rule in my favor?'"""
        check = guardrail_service.check_query("Will the judge rule in my favor?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"

    def test_will_court_decide_blocked(self):
        """Should block 'Will the court decide against the defendant?'"""
        check = guardrail_service.check_query("Will the court decide against the defendant?")
        assert check.is_safe is False


class TestChancesPatterns:
    """Test probability/chances detection."""

    def test_what_are_my_chances_blocked(self):
        """Should block 'What are my chances of winning?'"""
        check = guardrail_service.check_query("What are my chances of winning?")
        assert check.is_safe is False
        assert check.violation_type == "outcome_prediction"


class TestAllowedQueries:
    """Test that legitimate queries pass through."""

    def test_factual_question_allowed(self):
        """Should allow 'What does Section 138 say?'"""
        check = guardrail_service.check_query("What does Section 138 say?")
        assert check.is_safe is True
        assert check.violation_type is None

    def test_timeline_question_allowed(self):
        """Should allow 'When did the loan default?'"""
        check = guardrail_service.check_query("When did the loan default?")
        assert check.is_safe is True

    def test_contradiction_question_allowed(self):
        """Should allow 'What contradictions exist in witness statements?'"""
        check = guardrail_service.check_query("What contradictions exist in witness statements?")
        assert check.is_safe is True


# test_guardrail.py

class TestGuardrailCheckResponse:
    """Test GuardrailCheck response structure."""

    def test_blocked_response_structure(self):
        """Blocked queries should include all required fields."""
        check = guardrail_service.check_query("Should I file an appeal?")
        assert check.is_safe is False
        assert check.violation_type is not None
        assert check.pattern_matched is not None
        assert len(check.explanation) > 0
        assert len(check.suggested_rewrite) > 0
        assert check.check_time_ms >= 0

    def test_allowed_response_structure(self):
        """Allowed queries should have minimal fields set."""
        check = guardrail_service.check_query("What does the document say?")
        assert check.is_safe is True
        assert check.violation_type is None
        assert check.check_time_ms >= 0


class TestPerformance:
    """Test guardrail performance requirements."""

    def test_check_under_5ms(self):
        """Single query check should complete in < 5ms."""
        check = guardrail_service.check_query("Should I file an appeal?")
        assert check.check_time_ms < 5.0

    def test_bulk_checks_performance(self):
        """100 queries should complete in < 500ms (avg < 5ms each)."""
        import time
        queries = ["Should I file?" for _ in range(100)]
        start = time.perf_counter()
        for q in queries:
            guardrail_service.check_query(q)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500
```

### Git Intelligence

Recent commit patterns:
- `feat(memory): implement query cache Redis storage (Story 7-5)`
- `fix(review): code review fixes for Story 7-5`

Use: `feat(safety): implement regex pattern detection guardrails (Story 8-1)`

### Security Considerations

1. **Pattern Complexity**: Keep patterns simple to avoid ReDoS (regex denial of service)
2. **No User Data Logging**: Don't log the full query in production (may contain sensitive case info)
3. **False Positive Handling**: Err on side of allowing borderline queries (Story 8-2 LLM will catch)

### Environment Variables

No new environment variables needed - pure Python implementation.

### Integration Points

1. **QueryOrchestrator (Epic 6)**: Will call `check_query()` before intent analysis (Story 8-2)
2. **Story 8-2**: GPT-4o-mini subtle detection for queries that pass regex
3. **Story 8-3**: Language policing on outputs (separate concern)
4. **Audit Trail (Story 6-3)**: Log blocked queries with violation type

### Dependencies

This story has no dependencies on other stories. It is foundational for Epic 8.

This story blocks:
- **Story 8-2**: GPT-4o-mini Subtle Violation Detection (needs GuardrailService as first pass)

### Project Structure Notes

- Create new `services/safety/` directory
- Create new `models/safety.py` file
- Tests in `tests/services/safety/`
- **No database migrations needed** - pure service implementation

### References

- [Project Context](_bmad-output/project-context.md) - Naming conventions, testing rules
- [Architecture: Safety Layer](_bmad-output/architecture.md#safety-layer-mandatory) - Safety requirements
- [Epic 8 Definition](_bmad-output/project-planning-artifacts/epics.md) - Story requirements
- [FR8 Requirement](_bmad-output/project-planning-artifacts/epics.md) - Query Guardrails specification
- [ADR-004](_bmad-output/architecture.md#adr-004-verification-tier-thresholds) - Verification tiers

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No debug issues encountered during implementation.

### Completion Notes List

- ✅ Implemented GuardrailService with fast-path regex pattern detection
- ✅ Created 13 compiled regex patterns covering 5 violation categories
- ✅ All patterns are pre-compiled at module load for < 5ms performance
- ✅ Implemented singleton factory pattern with thread-safe initialization
- ✅ Added comprehensive test coverage (57 tests, 100% pass rate)
- ✅ Full regression test suite passes (1902 tests, 9 skipped)
- ✅ Performance validated: single query checks complete in < 1ms typically
- ✅ Follows existing code patterns from SessionMemoryService (Story 7-1)
- ✅ Module exports added to models/__init__.py and services/safety/__init__.py

### File List

**New Files:**
- backend/app/models/safety.py - GuardrailCheck, ViolationType, GuardrailPattern models
- backend/app/services/safety/__init__.py - Module exports
- backend/app/services/safety/patterns.py - Compiled regex patterns and templates
- backend/app/services/safety/guardrail.py - GuardrailService implementation
- backend/tests/services/safety/__init__.py - Test module init
- backend/tests/services/safety/test_patterns.py - Pattern matching tests (33 tests)
- backend/tests/services/safety/test_guardrail.py - Service tests (24 tests)

**Modified Files:**
- backend/app/models/__init__.py - Added safety model exports

## Change Log

- 2026-01-14: Implemented Story 8-1 - Fast-path regex pattern detection guardrails (57 tests)
