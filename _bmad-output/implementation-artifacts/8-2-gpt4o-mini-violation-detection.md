# Story 8.2: Implement GPT-4o-mini Subtle Violation Detection

Status: review

## Story

As a **developer**,
I want **subtle legal conclusion requests detected by AI**,
So that **cleverly worded requests are still blocked**.

## Acceptance Criteria

1. **Given** a query passes regex detection
   **When** subtle detection runs via GPT-4o-mini
   **Then** the query is analyzed for implicit legal conclusions
   **And** violations are detected

2. **Given** a query asks "Based on this evidence, is it clear that..."
   **When** detection runs
   **Then** the implicit conclusion request is detected
   **And** the query is blocked

3. **Given** a violation is detected
   **When** the response is returned
   **Then** a contextual rewrite is suggested
   **And** the rewrite removes the conclusion-seeking aspect

4. **Given** GPT-4o-mini approves the query
   **When** processing continues
   **Then** the query is marked as safe
   **And** normal processing proceeds

## Tasks / Subtasks

- [x] Task 1: Extend Safety Models (AC: #1-4)
  - [x] 1.1: Add `SubtleViolationCheck` model to `backend/app/models/safety.py` with fields: is_safe, violation_detected, violation_type, explanation, suggested_rewrite, confidence, llm_cost_usd, check_time_ms
  - [x] 1.2: Add new violation types for subtle detection: "implicit_conclusion_request", "indirect_outcome_seeking", "hypothetical_legal_advice"
  - [x] 1.3: Extend `ViolationType` Literal to include new types
  - [x] 1.4: Add `SafetyCheckResult` model combining regex + LLM results

- [x] Task 2: Create GPT-4o-mini Detection Prompts (AC: #1-2)
  - [x] 2.1: Create `backend/app/services/safety/prompts.py`
  - [x] 2.2: Define `SUBTLE_DETECTION_SYSTEM_PROMPT` - instruct model to detect implicit legal conclusions
  - [x] 2.3: Define `SUBTLE_DETECTION_USER_PROMPT` template with query placeholder
  - [x] 2.4: Define `SUBTLE_DETECTION_RESPONSE_SCHEMA` for structured JSON output
  - [x] 2.5: Add example classifications (pass/fail cases)

- [x] Task 3: Create SubtleViolationDetector Service (AC: #1-4)
  - [x] 3.1: Create `backend/app/services/safety/subtle_detector.py`
  - [x] 3.2: Implement `SubtleViolationDetector` class with lazy OpenAI client initialization
  - [x] 3.3: Implement `detect_violation()` method - calls GPT-4o-mini with structured output
  - [x] 3.4: Implement response parsing with `_parse_llm_response()`
  - [x] 3.5: Implement cost tracking (input/output tokens)
  - [x] 3.6: Add retry logic with exponential backoff (MAX_RETRIES=3)
  - [x] 3.7: Implement singleton factory `get_subtle_violation_detector()`

- [x] Task 4: Create Contextual Rewrite Generator (AC: #3)
  - [x] 4.1: Implement `generate_contextual_rewrite()` in SubtleViolationDetector (via LLM response)
  - [x] 4.2: Use GPT-4o-mini to suggest safe alternative queries
  - [x] 4.3: Ensure rewrites preserve user's factual intent while removing conclusion-seeking

- [x] Task 5: Create Combined SafetyGuard Service (AC: #1-4)
  - [x] 5.1: Create `backend/app/services/safety/safety_guard.py`
  - [x] 5.2: Implement `SafetyGuard` class that combines regex + LLM detection
  - [x] 5.3: Implement `check_query()` pipeline: regex first, LLM if regex passes
  - [x] 5.4: Return `SafetyCheckResult` with combined results
  - [x] 5.5: Implement singleton factory `get_safety_guard()`

- [x] Task 6: Integrate with QueryOrchestrator (AC: #4)
  - [x] 6.1: Import SafetyGuard into `backend/app/engines/orchestrator/orchestrator.py`
  - [x] 6.2: Add SafetyGuard as orchestrator dependency (constructor parameter)
  - [x] 6.3: Call `safety_guard.check_query()` BEFORE intent analysis in `process_query()`
  - [x] 6.4: Return blocked result if safety check fails
  - [x] 6.5: Log blocked queries to audit trail (non-blocking)

- [x] Task 7: Add Configuration Settings (AC: #1-4)
  - [x] 7.1: Add `openai_safety_model: str = "gpt-4o-mini"` to `backend/app/core/config.py`
  - [x] 7.2: Add `safety_llm_timeout: float = 10.0` timeout setting
  - [x] 7.3: Add `safety_llm_enabled: bool = True` feature flag

- [x] Task 8: Create Unit Tests (AC: #1-4)
  - [x] 8.1: Create `backend/tests/services/safety/test_subtle_detector.py`
  - [x] 8.2: Test "Based on this evidence, is it clear that..." - BLOCKED
  - [x] 8.3: Test "Would you say the defendant is..." - BLOCKED
  - [x] 8.4: Test "Does the evidence support a finding of..." - BLOCKED
  - [x] 8.5: Test "What does the document say about..." - ALLOWED
  - [x] 8.6: Test contextual rewrite generation
  - [x] 8.7: Test LLM timeout handling
  - [x] 8.8: Test cost tracking accuracy
  - [x] 8.9: Mock OpenAI responses for all tests

- [x] Task 9: Create Integration Tests (AC: #4)
  - [x] 9.1: Create `backend/tests/services/safety/test_safety_guard.py`
  - [x] 9.2: Test regex → LLM pipeline (regex blocks first)
  - [x] 9.3: Test regex pass → LLM check flow
  - [x] 9.4: Test combined SafetyCheckResult structure
  - [x] 9.5: Test feature flag disabling LLM check

- [x] Task 10: Create Orchestrator Integration Tests (AC: #4)
  - [x] 10.1: Create `backend/tests/engines/orchestrator/test_orchestrator_safety.py`
  - [x] 10.2: Test blocked query returns immediately without engine execution
  - [x] 10.3: Test safe query proceeds to intent analysis
  - [x] 10.4: Test audit logging for blocked queries

- [x] Task 11: Update Module Exports
  - [x] 11.1: Update `backend/app/services/safety/__init__.py` with new exports
  - [x] 11.2: Export SubtleViolationDetector, SafetyGuard, get_safety_guard
  - [x] 11.3: Export new models from safety module

## Dev Notes

### Architecture Compliance

This story implements **Query Guardrails (Layer 2)** of the Safety Layer (Epic 8):

```
USER QUERY → [REGEX CHECK] → [GPT-4o-mini CHECK] → ORCHESTRATOR → ENGINES → [LANGUAGE POLICING] → RESPONSE
              ^^^^^^^^^^^    ^^^^^^^^^^^^^^^^^^                               ^^^^^^^^^^^^^^^^^^^^^
              Story 8-1      Story 8-2 (this)                                 Story 8-3
```

Two-phase guardrail design:
- **Phase 1 (Story 8-1)**: Fast regex patterns block obvious violations (< 5ms)
- **Phase 2 (Story 8-2)**: GPT-4o-mini catches subtle, cleverly-worded requests

This satisfies:
- **FR8**: Query Guardrails - Block dangerous queries before LLM processing
- **NFR22**: Safety - Prevent legal conclusions from being requested
- **Architecture Decision**: Use cheap/fast model (GPT-4o-mini) for safety checks

### Critical Implementation Details

1. **GPT-4o-mini Model Selection**

   Per LLM routing rules, use GPT-4o-mini for safety detection:
   ```python
   # Story 8-2: Safety detection is a classification task
   # GPT-4o-mini is sufficient - cheaper than GPT-4, faster, still capable
   MODEL_NAME = "gpt-4o-mini"  # NOT gpt-4
   ```

   **Cost comparison:**
   - GPT-4o-mini: ~$0.00015/1K input tokens, ~$0.0006/1K output tokens
   - GPT-4: ~$0.03/1K input tokens, ~$0.06/1K output tokens
   - **200x cheaper for input, 100x cheaper for output**

2. **SubtleViolationDetector Service Pattern**

   Follow the pattern from `IntentAnalyzer` (Story 6-1):
   ```python
   import asyncio
   import json
   import time
   from functools import lru_cache

   import structlog
   from openai import AsyncOpenAI

   from app.core.config import get_settings
   from app.models.safety import SubtleViolationCheck, ViolationType

   logger = structlog.get_logger(__name__)

   # Retry configuration
   MAX_RETRIES = 3
   INITIAL_RETRY_DELAY = 0.5
   MAX_RETRY_DELAY = 10.0


   class SubtleViolationDetector:
       """GPT-4o-mini based subtle violation detector.

       Story 8-2: Detects cleverly-worded legal conclusion requests
       that bypass regex patterns.

       Example:
           >>> detector = get_subtle_violation_detector()
           >>> check = await detector.detect_violation(
           ...     "Based on the evidence, is it clear that..."
           ... )
           >>> check.is_safe
           False
       """

       def __init__(self) -> None:
           """Initialize subtle violation detector."""
           settings = get_settings()
           self.api_key = settings.openai_api_key
           self.model_name = settings.openai_safety_model  # "gpt-4o-mini"
           self.timeout = settings.safety_llm_timeout  # 10.0 seconds
           self._client = None

           logger.info(
               "subtle_violation_detector_configured",
               model=self.model_name,
               timeout=self.timeout,
           )

       @property
       def client(self):
           """Get or create OpenAI client (lazy initialization).

           Returns:
               AsyncOpenAI client instance.

           Raises:
               OpenAIConfigurationError: If API key not configured.
           """
           if self._client is None:
               if not self.api_key:
                   raise OpenAIConfigurationError(
                       "OpenAI API key not configured. Set OPENAI_API_KEY."
                   )
               self._client = AsyncOpenAI(api_key=self.api_key)
               logger.info(
                   "subtle_detector_client_initialized",
                   model=self.model_name,
               )
           return self._client

       async def detect_violation(self, query: str) -> SubtleViolationCheck:
           """Detect subtle legal conclusion requests using GPT-4o-mini.

           Story 8-2: AC #1-2 - LLM-based detection.

           Args:
               query: User query that passed regex detection.

           Returns:
               SubtleViolationCheck with detection result.
           """
           start_time = time.perf_counter()

           # Call GPT-4o-mini with retry
           result = await self._call_llm_with_retry(query)

           check_time_ms = (time.perf_counter() - start_time) * 1000

           return SubtleViolationCheck(
               is_safe=result["is_safe"],
               violation_detected=not result["is_safe"],
               violation_type=result.get("violation_type"),
               explanation=result.get("explanation", ""),
               suggested_rewrite=result.get("suggested_rewrite", ""),
               confidence=result.get("confidence", 0.0),
               llm_cost_usd=result.get("cost_usd", 0.0),
               check_time_ms=check_time_ms,
           )
   ```

3. **System Prompt for Subtle Detection**

   ```python
   SUBTLE_DETECTION_SYSTEM_PROMPT = """You are a legal safety classifier for LDIP (Legal Document Intelligence Platform).

   Your task is to identify queries that implicitly seek legal conclusions, even when cleverly worded.

   LDIP can ONLY provide:
   - Factual information from documents
   - Document analysis and extraction
   - Timeline of events
   - Citation verification
   - Entity relationships

   LDIP CANNOT provide:
   - Legal advice or recommendations
   - Predictions about case outcomes
   - Conclusions about liability or guilt
   - Procedural recommendations

   Detect queries that IMPLICITLY seek these forbidden outputs, such as:
   - "Based on this evidence, is it clear that..." (seeking conclusion)
   - "Would you say the defendant is..." (seeking opinion/conclusion)
   - "Does the evidence support a finding of..." (seeking conclusion)
   - "If I were to argue that..., what would you say?" (hypothetical legal advice)
   - "What would a judge likely think about..." (seeking prediction)

   Respond with JSON:
   {
       "is_safe": boolean,
       "violation_type": "implicit_conclusion_request" | "indirect_outcome_seeking" | "hypothetical_legal_advice" | null,
       "explanation": "Why this query was blocked or allowed",
       "suggested_rewrite": "Safe alternative query that preserves factual intent",
       "confidence": 0.0-1.0
   }
   """
   ```

4. **Integration with QueryOrchestrator**

   ```python
   # In orchestrator.py - process_query method
   async def process_query(
       self,
       matter_id: str,
       query: str,
       user_id: str | None = None,
       context: dict[str, Any] | None = None,
   ) -> OrchestratorResult:
       """Process user query through full orchestration pipeline.

       Story 8-2: Safety check added before intent analysis.
       """
       start_time = time.time()

       # Step 0: Safety check (Story 8-1 regex + Story 8-2 LLM)
       safety_result = await self._safety_guard.check_query(query)
       if not safety_result.is_safe:
           logger.info(
               "query_blocked_by_safety",
               matter_id=matter_id,
               blocked_by=safety_result.blocked_by,  # "regex" or "llm"
               violation_type=safety_result.violation_type,
           )

           # Log to audit trail (non-blocking)
           if user_id:
               asyncio.create_task(
                   self._log_blocked_query_audit(
                       matter_id=matter_id,
                       user_id=user_id,
                       query=query,
                       safety_result=safety_result,
                   )
               )

           return OrchestratorResult(
               matter_id=matter_id,
               original_query=query,
               success=False,
               blocked=True,
               blocked_reason=safety_result.explanation,
               suggested_rewrite=safety_result.suggested_rewrite,
               wall_clock_time_ms=int((time.time() - start_time) * 1000),
           )

       # Step 1: Analyze intent (existing flow continues)
       intent_result = await self._intent_analyzer.analyze_intent(...)
   ```

5. **SafetyGuard Combined Service**

   ```python
   class SafetyGuard:
       """Combined safety guard with regex + LLM detection.

       Story 8-1 + 8-2: Two-phase safety checking.

       Pipeline:
       1. Fast regex check (< 5ms) - blocks obvious violations
       2. If regex passes, LLM check (~500-2000ms) - catches subtle violations

       Example:
           >>> guard = get_safety_guard()
           >>> result = await guard.check_query("Should I file an appeal?")
           >>> result.is_safe
           False
           >>> result.blocked_by
           "regex"
       """

       def __init__(
           self,
           guardrail_service: GuardrailService | None = None,
           subtle_detector: SubtleViolationDetector | None = None,
       ) -> None:
           """Initialize safety guard.

           Args:
               guardrail_service: Regex-based guardrail (Story 8-1).
               subtle_detector: LLM-based detector (Story 8-2).
           """
           self._guardrail = guardrail_service or get_guardrail_service()
           self._subtle_detector = subtle_detector or get_subtle_violation_detector()
           self._llm_enabled = get_settings().safety_llm_enabled

       async def check_query(self, query: str) -> SafetyCheckResult:
           """Check query against both regex and LLM guardrails.

           Story 8-1 + 8-2: Combined safety pipeline.

           Args:
               query: User query to check.

           Returns:
               SafetyCheckResult with combined results.
           """
           # Phase 1: Fast regex check (Story 8-1)
           regex_check = self._guardrail.check_query(query)
           if not regex_check.is_safe:
               return SafetyCheckResult(
                   is_safe=False,
                   blocked_by="regex",
                   violation_type=regex_check.violation_type,
                   explanation=regex_check.explanation,
                   suggested_rewrite=regex_check.suggested_rewrite,
                   regex_check_ms=regex_check.check_time_ms,
               )

           # Phase 2: LLM check if enabled (Story 8-2)
           if not self._llm_enabled:
               return SafetyCheckResult(
                   is_safe=True,
                   blocked_by=None,
                   regex_check_ms=regex_check.check_time_ms,
               )

           try:
               llm_check = await self._subtle_detector.detect_violation(query)
               if not llm_check.is_safe:
                   return SafetyCheckResult(
                       is_safe=False,
                       blocked_by="llm",
                       violation_type=llm_check.violation_type,
                       explanation=llm_check.explanation,
                       suggested_rewrite=llm_check.suggested_rewrite,
                       regex_check_ms=regex_check.check_time_ms,
                       llm_check_ms=llm_check.check_time_ms,
                       llm_cost_usd=llm_check.llm_cost_usd,
                   )

               return SafetyCheckResult(
                   is_safe=True,
                   blocked_by=None,
                   regex_check_ms=regex_check.check_time_ms,
                   llm_check_ms=llm_check.check_time_ms,
                   llm_cost_usd=llm_check.llm_cost_usd,
               )

           except Exception as e:
               # LLM failures should NOT block queries - fail open
               logger.warning(
                   "safety_llm_check_failed",
                   error=str(e),
                   fallback="allowing_query",
               )
               return SafetyCheckResult(
                   is_safe=True,
                   blocked_by=None,
                   regex_check_ms=regex_check.check_time_ms,
                   llm_check_failed=True,
               )
   ```

6. **SubtleViolationCheck Model**

   ```python
   class SubtleViolationCheck(BaseModel):
       """Result of GPT-4o-mini subtle violation detection.

       Story 8-2: AC #1-4 - LLM-based detection result.
       """

       is_safe: bool = Field(
           description="True if query passes LLM safety check",
       )
       violation_detected: bool = Field(
           default=False,
           description="True if subtle violation was detected",
       )
       violation_type: str | None = Field(
           default=None,
           description="Type of subtle violation detected",
       )
       explanation: str = Field(
           default="",
           description="LLM explanation for why query was blocked",
       )
       suggested_rewrite: str = Field(
           default="",
           description="Contextual safe alternative query",
       )
       confidence: float = Field(
           default=0.0,
           ge=0.0,
           le=1.0,
           description="LLM confidence in detection (0.0-1.0)",
       )
       llm_cost_usd: float = Field(
           default=0.0,
           ge=0.0,
           description="Cost of this LLM call in USD",
       )
       check_time_ms: float = Field(
           default=0.0,
           ge=0.0,
           description="Time taken for LLM check in milliseconds",
       )


   class SafetyCheckResult(BaseModel):
       """Combined result from regex + LLM safety checks.

       Story 8-1 + 8-2: Two-phase safety pipeline result.
       """

       is_safe: bool = Field(
           description="True if query passes ALL safety checks",
       )
       blocked_by: Literal["regex", "llm"] | None = Field(
           default=None,
           description="Which phase blocked the query (if blocked)",
       )
       violation_type: str | None = Field(
           default=None,
           description="Type of violation detected (if blocked)",
       )
       explanation: str = Field(
           default="",
           description="User-friendly explanation (if blocked)",
       )
       suggested_rewrite: str = Field(
           default="",
           description="Safe alternative query suggestion",
       )
       regex_check_ms: float = Field(
           default=0.0,
           ge=0.0,
           description="Time for regex check (always runs)",
       )
       llm_check_ms: float = Field(
           default=0.0,
           ge=0.0,
           description="Time for LLM check (if regex passed)",
       )
       llm_cost_usd: float = Field(
           default=0.0,
           ge=0.0,
           description="Cost of LLM call in USD",
       )
       llm_check_failed: bool = Field(
           default=False,
           description="True if LLM check failed (query allowed anyway)",
       )
   ```

### Existing Code to Reuse (DO NOT REINVENT)

| Component | Location | Purpose |
|-----------|----------|---------|
| `GuardrailService` | `services/safety/guardrail.py` | Regex-based detection (Story 8-1) |
| `GuardrailCheck` | `models/safety.py` | Regex check result model |
| `ViolationType` | `models/safety.py` | Violation type literals |
| `AsyncOpenAI` | `openai` | Async OpenAI client |
| `IntentAnalyzer` | `engines/orchestrator/intent_analyzer.py` | Pattern for LLM service with retry |
| `get_settings()` | `core/config.py` | Configuration access |
| `structlog` | All modules | Structured logging |

### Previous Story (8-1) Learnings

From Story 8-1 implementation and code review:

1. **Singleton Factory Pattern**: Use `threading.Lock()` for thread-safe initialization (but note that SubtleViolationDetector is async, so use `@lru_cache(maxsize=1)` instead)
2. **Timing Metrics**: Use `time.perf_counter()` for sub-millisecond accuracy
3. **Story References**: Include Story reference in all docstrings
4. **Pre-compiled Patterns**: Story 8-1 patterns are pre-compiled at module load
5. **Conservative Approach**: Block obvious, allow borderline (LLM catches subtle ones)
6. **Global Statement**: Use `# noqa: PLW0603` for global variable assignments

### File Structure

Extend safety service:

```
backend/app/
├── core/
│   └── config.py                     # ADD: openai_safety_model, safety_llm_timeout, safety_llm_enabled
├── models/
│   └── safety.py                     # ADD: SubtleViolationCheck, SafetyCheckResult, new ViolationTypes
├── services/
│   └── safety/
│       ├── __init__.py               # UPDATE: Add new exports
│       ├── patterns.py               # EXISTING (Story 8-1)
│       ├── guardrail.py              # EXISTING (Story 8-1)
│       ├── prompts.py                # NEW: LLM prompts for subtle detection
│       ├── subtle_detector.py        # NEW: SubtleViolationDetector service
│       └── safety_guard.py           # NEW: Combined SafetyGuard service
├── engines/
│   └── orchestrator/
│       └── orchestrator.py           # UPDATE: Add safety check before intent analysis
└── tests/
    ├── services/
    │   └── safety/
    │       ├── test_patterns.py      # EXISTING (Story 8-1)
    │       ├── test_guardrail.py     # EXISTING (Story 8-1)
    │       ├── test_subtle_detector.py   # NEW: LLM detection tests
    │       └── test_safety_guard.py      # NEW: Combined service tests
    └── engines/
        └── orchestrator/
            └── test_orchestrator_safety.py  # NEW: Integration tests
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/services/safety/` directory
- Use pytest-asyncio for async tests
- **Mock ALL OpenAI calls** - never hit real API in tests
- Include cost tracking validation

**Minimum Test Cases:**

```python
# test_subtle_detector.py

import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
class TestSubtleViolationDetector:
    """Test GPT-4o-mini subtle violation detection."""

    async def test_implicit_conclusion_blocked(self, detector, mock_openai_blocked):
        """Should block 'Based on this evidence, is it clear that...'"""
        check = await detector.detect_violation(
            "Based on this evidence, is it clear that the defendant breached the contract?"
        )
        assert check.is_safe is False
        assert check.violation_type == "implicit_conclusion_request"

    async def test_indirect_outcome_blocked(self, detector, mock_openai_blocked):
        """Should block 'Would you say the defendant is...'"""
        check = await detector.detect_violation(
            "Would you say the defendant is liable for the damages?"
        )
        assert check.is_safe is False
        assert check.violation_type == "indirect_outcome_seeking"

    async def test_hypothetical_advice_blocked(self, detector, mock_openai_blocked):
        """Should block 'If I were to argue that...'"""
        check = await detector.detect_violation(
            "If I were to argue that the contract is void, what would you say?"
        )
        assert check.is_safe is False
        assert check.violation_type == "hypothetical_legal_advice"

    async def test_factual_query_allowed(self, detector, mock_openai_allowed):
        """Should allow 'What does the document say about...'"""
        check = await detector.detect_violation(
            "What does the document say about the payment terms?"
        )
        assert check.is_safe is True
        assert check.violation_type is None

    async def test_contextual_rewrite_generated(self, detector, mock_openai_blocked):
        """Should generate contextual rewrite for blocked query."""
        check = await detector.detect_violation(
            "Does the evidence support a finding of negligence?"
        )
        assert len(check.suggested_rewrite) > 0
        assert "evidence" in check.suggested_rewrite.lower()

    async def test_cost_tracking(self, detector, mock_openai_blocked):
        """Should track LLM cost."""
        check = await detector.detect_violation("Some query")
        assert check.llm_cost_usd >= 0.0

    async def test_timeout_handling(self, detector):
        """Should handle LLM timeout gracefully."""
        with patch.object(detector, "_call_llm_with_retry", side_effect=asyncio.TimeoutError):
            # Should not raise - fail open
            check = await detector.detect_violation("Some query")
            # Behavior depends on implementation - could allow or use default


# test_safety_guard.py

@pytest.mark.asyncio
class TestSafetyGuard:
    """Test combined regex + LLM safety guard."""

    async def test_regex_blocks_first(self, safety_guard):
        """Regex violations should block before LLM is called."""
        result = await safety_guard.check_query("Should I file an appeal?")
        assert result.is_safe is False
        assert result.blocked_by == "regex"
        assert result.llm_check_ms == 0.0  # LLM not called

    async def test_llm_check_after_regex_pass(self, safety_guard, mock_openai_blocked):
        """LLM should check queries that pass regex."""
        result = await safety_guard.check_query(
            "Based on this evidence, is it clear that..."
        )
        assert result.is_safe is False
        assert result.blocked_by == "llm"
        assert result.llm_check_ms > 0.0

    async def test_safe_query_passes_both(self, safety_guard, mock_openai_allowed):
        """Safe queries should pass both checks."""
        result = await safety_guard.check_query(
            "What does Section 138 of NI Act say?"
        )
        assert result.is_safe is True
        assert result.blocked_by is None

    async def test_llm_failure_fails_open(self, safety_guard):
        """LLM failures should allow query (fail open)."""
        with patch.object(
            safety_guard._subtle_detector,
            "detect_violation",
            side_effect=Exception("LLM Error")
        ):
            result = await safety_guard.check_query("Some query")
            assert result.is_safe is True
            assert result.llm_check_failed is True
```

### Git Intelligence

Recent commit patterns:
- `feat(safety): implement regex pattern detection guardrails (Story 8-1)`
- `fix(review): code review fixes for Story 8-1`

Use: `feat(safety): implement GPT-4o-mini subtle violation detection (Story 8-2)`

### Security Considerations

1. **Fail Open**: LLM failures should NOT block queries - this prevents DoS via LLM unavailability
2. **No Query Logging**: Don't log full query text in production (contains sensitive case info)
3. **Cost Monitoring**: Track LLM costs to prevent runaway spending
4. **Timeout**: Hard timeout of 10s prevents hanging requests

### Environment Variables

Add to `backend/.env`:
```
# Story 8-2: Subtle Violation Detection
# OPENAI_API_KEY already exists
# OPENAI_SAFETY_MODEL=gpt-4o-mini  # Default in config.py
# SAFETY_LLM_TIMEOUT=10.0  # Default in config.py
# SAFETY_LLM_ENABLED=true  # Default in config.py
```

### Integration Points

1. **QueryOrchestrator (Epic 6)**: Calls SafetyGuard.check_query() before intent analysis
2. **Story 8-1**: GuardrailService provides fast-path regex detection
3. **Story 8-3**: Language policing on outputs (separate concern)
4. **Story 6-3**: Blocked queries should be logged to audit trail

### Dependencies

This story depends on:
- **Story 8-1**: GuardrailService (regex detection) - DONE

This story blocks:
- **Story 8-3**: Language Policing (may reuse similar LLM patterns)

### OrchestratorResult Extension

Extend `OrchestratorResult` model to support blocked queries:

```python
# In models/orchestrator.py

class OrchestratorResult(BaseModel):
    """Result from query orchestration."""

    # ... existing fields ...

    # Story 8-2: Safety blocking fields
    blocked: bool = Field(
        default=False,
        description="True if query was blocked by safety checks",
    )
    blocked_reason: str = Field(
        default="",
        description="Explanation for why query was blocked",
    )
    suggested_rewrite: str = Field(
        default="",
        description="Suggested safe alternative query",
    )
```

### Project Structure Notes

- Extend existing `services/safety/` directory
- Add new models to existing `models/safety.py`
- Update orchestrator to integrate safety checks
- **No database migrations needed** - pure service implementation

### References

- [Project Context](_bmad-output/project-context.md) - Naming conventions, testing rules
- [Architecture: Safety Layer](_bmad-output/architecture.md#safety-layer-mandatory) - Safety requirements
- [Story 8-1: Regex Detection](8-1-regex-pattern-detection.md) - Previous story patterns
- [IntentAnalyzer Pattern](backend/app/engines/orchestrator/intent_analyzer.py) - LLM service pattern
- [FR8 Requirement](_bmad-output/project-planning-artifacts/epics.md) - Query Guardrails specification

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - all tests passed on first implementation.

### Completion Notes List

1. Implemented two-phase safety pipeline: regex (fast-path) + GPT-4o-mini (subtle detection)
2. SubtleViolationDetector uses lazy OpenAI client initialization for cost efficiency
3. SafetyGuard combines both phases with fail-open behavior for LLM failures
4. Orchestrator integration blocks unsafe queries BEFORE intent analysis
5. All 33 new tests pass, 318 total tests in suite pass
6. GPT-4o-mini chosen for cost efficiency (200x cheaper than GPT-4 for input tokens)
7. Contextual rewrites generated by LLM preserve factual intent while removing conclusion-seeking

### File List

**New Files:**
- backend/app/services/safety/prompts.py - LLM prompts for subtle detection
- backend/app/services/safety/subtle_detector.py - SubtleViolationDetector service
- backend/app/services/safety/safety_guard.py - Combined SafetyGuard service
- backend/tests/services/safety/test_subtle_detector.py - Unit tests (17 tests)
- backend/tests/services/safety/test_safety_guard.py - Integration tests (10 tests)
- backend/tests/engines/orchestrator/test_orchestrator_safety.py - Orchestrator tests (6 tests)

**Modified Files:**
- backend/app/models/safety.py - Added SubtleViolationCheck, SafetyCheckResult, new ViolationTypes
- backend/app/models/orchestrator.py - Added blocked, blocked_reason, suggested_rewrite fields
- backend/app/core/config.py - Added openai_safety_model, safety_llm_timeout, safety_llm_enabled
- backend/app/services/safety/__init__.py - Added new exports
- backend/app/engines/orchestrator/orchestrator.py - Integrated SafetyGuard

## Change Log

- 2026-01-14: Story 8-2 created by create-story workflow - ready-for-dev
- 2026-01-14: Story 8-2 implemented - all tasks complete, 33 tests passing - review
